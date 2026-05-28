"""
Unit tests for prediction_service safeguards and full prediction pipeline.

Run from backend/ml/:
    pytest tests/test_prediction_service.py -v

Tests that reach the ML model mock _load_model and _load_preprocessor so
the pkl files do not need to be present.
"""
import pytest
from unittest.mock import MagicMock, patch

from services.prediction_service import _apply_safeguards, predict_anomaly


# ── Helpers ────────────────────────────────────────────────────────────────────

def _txn(category: str, amount: float, txn_id: str = "t-new", txn_type: str = "expense") -> dict:
    return {
        "transaction_id": txn_id,
        "user_id": "user-001",
        "transaction_date": "2024-06-01 14:00:00",
        "merchant": "TestMerchant",
        "amount": amount,
        "category": category,
        "transaction_type": txn_type,
    }


def _hist(category: str, amounts: list[float], txn_type: str = "expense") -> list[dict]:
    return [
        {
            "transaction_id": f"h-{i}",
            "user_id": "user-001",
            "transaction_date": f"2024-05-{i + 1:02d} 10:00:00",
            "merchant": "Merchant",
            "amount": a,
            "category": category,
            "transaction_type": txn_type,
        }
        for i, a in enumerate(amounts)
    ]


def _rich_history(category: str, cat_amounts: list[float]) -> list[dict]:
    """
    Build a history that passes both cold-start checks:
      - >= COLD_START_CATEGORY_MIN (5) transactions in the given category
      - >= COLD_START_TOTAL_MIN (10) expense transactions overall

    Category is padded to 5 by repeating the last amount.
    Filler 'Other' transactions make up any remaining slots.
    """
    padded = list(cat_amounts)
    while len(padded) < 5:
        padded.append(padded[-1])

    cat_hist     = _hist(category, padded)
    extra_needed = max(0, 10 - len(padded))
    filler       = _hist("Other", [50.0] * extra_needed)
    return cat_hist + filler


# ── Cold-start: new user (zero history) ────────────────────────────────────────

def test_new_user_first_transaction_is_insufficient_history():
    """New user with no history: first transaction must never be flagged anomaly."""
    txn    = _txn("Shopping", 1000.0)
    result = _apply_safeguards(txn, history=[])

    assert result is not None
    assert result["is_anomaly"] is False
    assert result["anomaly_status"] == "insufficient_history"


def test_single_category_transaction_is_insufficient_history():
    """
    The original bug: Shopping history [1001], new $1001 produced a false anomaly.
    With cold-start protection (< 5 category transactions) the result must be
    insufficient_history (is_anomaly=False), never confirmed_anomaly.
    """
    history = _hist("Shopping", [1001.0])   # only 1 category transaction
    txn     = _txn("Shopping", 1001.0)
    result  = _apply_safeguards(txn, history)

    assert result is not None
    assert result["is_anomaly"] is False
    # Could be insufficient_history (cold-start fires first) — the key contract
    # is is_anomaly=False, not confirmed_anomaly.
    assert result["anomaly_status"] != "confirmed_anomaly"


# ── Cold-start: fewer than 10 total expense transactions ──────────────────────

def test_insufficient_total_expense_history():
    # 9 expense transactions total — one short of the threshold
    history = _hist("Shopping", [100, 200, 300, 400, 500, 600, 700, 800, 900])
    txn     = _txn("Shopping", 1000.0)
    result  = _apply_safeguards(txn, history)

    assert result is not None
    assert result["is_anomaly"] is False
    assert result["anomaly_status"] == "insufficient_history"


# ── Cold-start: fewer than 5 same-category transactions ──────────────────────

def test_insufficient_category_history():
    # 10+ total but only 4 in Shopping
    cat_hist = _hist("Shopping", [200, 300, 400, 500])         # 4 — one short
    filler   = _hist("Other", [50, 60, 70, 80, 90, 100])       # 6 more
    txn      = _txn("Shopping", 1001.0)
    result   = _apply_safeguards(txn, cat_hist + filler)

    assert result is not None
    assert result["is_anomaly"] is False
    assert result["anomaly_status"] == "insufficient_history"


# ── Same-amount safeguard (fires only after cold-start passes) ────────────────

def test_same_amount_exact_match_is_normal():
    # Shopping has >= 5 history including 1001; new $1001 is an exact repeat
    history = _rich_history("Shopping", [1001.0])
    txn     = _txn("Shopping", 1001.0)
    result  = _apply_safeguards(txn, history)

    assert result is not None
    assert result["is_anomaly"] is False
    assert result["anomaly_status"] == "normal"


def test_same_amount_floating_point_tolerance():
    # $1001.00 vs $1000.999 — within $0.01 floating-point tolerance
    history = _rich_history("Shopping", [1000.999])
    txn     = _txn("Shopping", 1001.0)
    result  = _apply_safeguards(txn, history)

    assert result is not None
    assert result["is_anomaly"] is False
    assert result["anomaly_status"] == "normal"


# ── Tolerance safeguard (within 20% of category mean / max) ──────────────────

def test_new_amount_within_1pct_of_mean_is_normal():
    # Shopping history: [1000, …], new $1001 → |1001−1000|/1000 = 0.1% < 20%
    history = _rich_history("Shopping", [1000.0])
    txn     = _txn("Shopping", 1001.0)
    result  = _apply_safeguards(txn, history)

    assert result is not None
    assert result["is_anomaly"] is False
    assert result["anomaly_status"] == "normal"


def test_new_amount_within_10pct_of_mean_is_normal():
    # Shopping history: [1000, …], new $1100 → 10% above mean < 20%
    history = _rich_history("Shopping", [1000.0])
    txn     = _txn("Shopping", 1100.0)
    result  = _apply_safeguards(txn, history)

    assert result is not None
    assert result["is_anomaly"] is False
    assert result["anomaly_status"] == "normal"


def test_new_amount_at_tolerance_boundary_is_normal():
    # Exactly 20% above mean — should still be normal (boundary inclusive)
    history = _rich_history("Shopping", [1000.0])
    txn     = _txn("Shopping", 1200.0)
    result  = _apply_safeguards(txn, history)

    assert result is not None
    assert result["is_anomaly"] is False
    assert result["anomaly_status"] == "normal"


def test_new_amount_beyond_tolerance_passes_to_ml():
    # 21% above mean — safeguards should NOT trigger (return None so ML runs)
    history = _rich_history("Shopping", [1000.0])
    txn     = _txn("Shopping", 1210.0)
    result  = _apply_safeguards(txn, history)

    assert result is None   # caller must run the ML model


# ── Food spike: far outside tolerance → ML flags anomaly ─────────────────────

def test_food_large_amount_passes_safeguards_and_ml_flags_anomaly():
    """
    Food history [20, 25, 30, 35, 40], new $350.
    mean=30, max=40 — both more than 20% away from 350.
    Safeguards pass → ML model runs and flags confirmed_anomaly.
    """
    cat_amounts = [20.0, 25.0, 30.0, 35.0, 40.0]
    history     = _rich_history("Food", cat_amounts)
    txn         = _txn("Food", 350.0)

    # Verify safeguards pass (return None)
    assert _apply_safeguards(txn, history) is None, \
        "Safeguards should not catch a 10× spike in Food spending"

    # Full predict_anomaly with mocked ML → confirmed_anomaly
    mock_model = MagicMock()
    mock_model.predict.return_value = [1]
    mock_model.predict_proba.return_value = [[0.1, 0.9]]

    mock_artifact = {
        "model": mock_model,
        "model_version": "rf-test-v1",
        "model_name": "RandomForestClassifier",
        "trained_on": "2024-01-01",
        "metrics": {"recall": 0.9, "f1": 0.85, "f2": 0.88},
    }

    import pandas as pd
    mock_preprocessor = MagicMock()
    mock_preprocessor.feature_columns = ["log_amount"]
    mock_preprocessor.transform.return_value = pd.DataFrame([[1.0]], columns=["log_amount"])

    with patch("services.prediction_service._load_model", return_value=mock_artifact), \
         patch("services.prediction_service._load_preprocessor", return_value=mock_preprocessor), \
         patch("services.prediction_service.engineer_features", side_effect=lambda df: df):
        result = predict_anomaly(txn, history)

    assert result["is_anomaly"] is True
    assert result["anomaly_status"] == "confirmed_anomaly"
    assert result["model_version"] == "rf-test-v1"


# ── Income transactions excluded from expense counts ─────────────────────────

def test_income_transactions_do_not_count_toward_expense_threshold():
    # 15 income transactions — expense count remains 0 → cold-start
    income_history = _hist("Salary", [3000.0] * 15, txn_type="income")
    txn            = _txn("Shopping", 1000.0)
    result         = _apply_safeguards(txn, income_history)

    assert result is not None
    assert result["anomaly_status"] == "insufficient_history"


# ── predict_anomaly returns correct fields for safeguard exits ────────────────

def test_predict_anomaly_insufficient_history_fields():
    txn    = _txn("Shopping", 500.0)
    result = predict_anomaly(txn, history=[])

    assert result["is_anomaly"] is False
    assert result["anomaly_status"] == "insufficient_history"
    assert result["confidence"] == 0.0
    assert result["reason"] is None
    assert result["model_version"] is None
    assert result["transaction_id"] == "t-new"
    assert result["user_id"] == "user-001"


def test_predict_anomaly_same_amount_returns_normal_fields():
    history = _rich_history("Shopping", [999.0])
    txn     = _txn("Shopping", 999.0)
    result  = predict_anomaly(txn, history)

    assert result["is_anomaly"] is False
    assert result["anomaly_status"] == "normal"
    assert result["model_version"] is None


# ── User-dismissed anomaly stays off insights ─────────────────────────────────

def test_ml_normal_prediction_returns_normal_status():
    """
    When the ML model says not anomaly, anomaly_status must be 'normal'
    so insights query (which filters confirmed_anomaly) excludes it.
    """
    cat_amounts = [20.0, 25.0, 30.0, 35.0, 40.0]
    history     = _rich_history("Food", cat_amounts)
    txn         = _txn("Food", 350.0)

    mock_model = MagicMock()
    mock_model.predict.return_value = [0]           # model says normal
    mock_model.predict_proba.return_value = [[0.85, 0.15]]

    mock_artifact = {
        "model": mock_model,
        "model_version": "rf-test-v1",
        "model_name": "RandomForestClassifier",
        "trained_on": "2024-01-01",
        "metrics": {"recall": 0.9, "f1": 0.85, "f2": 0.88},
    }

    import pandas as pd
    mock_preprocessor = MagicMock()
    mock_preprocessor.feature_columns = ["log_amount"]
    mock_preprocessor.transform.return_value = pd.DataFrame([[1.0]], columns=["log_amount"])

    with patch("services.prediction_service._load_model", return_value=mock_artifact), \
         patch("services.prediction_service._load_preprocessor", return_value=mock_preprocessor), \
         patch("services.prediction_service.engineer_features", side_effect=lambda df: df):
        result = predict_anomaly(txn, history)

    assert result["is_anomaly"] is False
    assert result["anomaly_status"] == "normal"
    # A transaction with anomaly_status != "confirmed_anomaly" will not appear
    # in the insights query (which filters on confirmed_anomaly only).
    assert result["anomaly_status"] != "confirmed_anomaly"
