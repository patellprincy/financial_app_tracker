"""
Prediction service — supervised anomaly detection inference.

Complete inference flow:
  1. Apply safeguards (cold-start, same-amount, tolerance).  If any trigger,
     return early without touching the ML model.
  2. Receive transaction dict + history list and build a DataFrame.
  3. Apply feature engineering to the full context.
  4. Extract the last row = the new transaction with all features computed.
  5. preprocessor.transform() — encode + scale using the fitted pipeline.
  6. model.predict() → is_anomaly (0 or 1)
     model.predict_proba() → [prob_normal, prob_anomaly]
  7. Build a human-readable reason string from the feature values.
  8. Return is_anomaly, anomaly_status, confidence, reason, model_version.

Safeguard order (checked before the ML model runs):
  1. Cold-start total: < 10 expense transactions in history → insufficient_history
  2. Cold-start category: < 5 same-category transactions → insufficient_history
  3. Same-amount: exact match (within $0.01) in same category → normal
  4. Tolerance: amount within 20 % of category mean or max → normal

Why history matters:
  amount_zscore and category_percentile are relative to the user's own history.
  Without history these features default to neutral values (zscore=0, pct=0.5),
  which reduces the model's ability to personalise detection.
  Pass 30-90 days of past transactions for best results.
"""
import logging
import os
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from preprocessing.feature_engineering import engineer_features
from preprocessing.pipeline import AnomalyPreprocessor

logger = logging.getLogger(__name__)

THRESHOLD = 0.3

# Cold-start thresholds
COLD_START_TOTAL_MIN    = 10   # minimum total expense transactions in history
COLD_START_CATEGORY_MIN = 5    # minimum same-category expense transactions
TOLERANCE_PCT           = 0.20  # 20 % band around category mean / max

_MODEL_PATH        = os.getenv("RF_MODEL_PATH",        "saved_models/random_forest.pkl")
_PREPROCESSOR_PATH = os.getenv("RF_PREPROCESSOR_PATH", "saved_models/preprocessor.pkl")


# ── Artifact loading (cached — loaded once per process) ───────────────────────

@lru_cache(maxsize=1)
def _load_model() -> dict:
    if not os.path.exists(_MODEL_PATH):
        raise FileNotFoundError(
            f"Model not found: {_MODEL_PATH}\n"
            "Run:  cd backend/ml && python -m training.train"
        )
    artifact = joblib.load(_MODEL_PATH)
    logger.info(
        "Model loaded: %s  version=%s  trained_on=%s  recall=%.3f  f1=%.3f  f2=%.3f",
        artifact["model_name"],
        artifact["model_version"],
        artifact["trained_on"],
        artifact["metrics"]["recall"],
        artifact["metrics"]["f1"],
        artifact["metrics"].get("f2", 0.0),
    )
    return artifact


@lru_cache(maxsize=1)
def _load_preprocessor() -> AnomalyPreprocessor:
    if not os.path.exists(_PREPROCESSOR_PATH):
        raise FileNotFoundError(
            f"Preprocessor not found: {_PREPROCESSOR_PATH}\n"
            "Run:  cd backend/ml && python -m training.train"
        )
    preprocessor = AnomalyPreprocessor.load(_PREPROCESSOR_PATH)
    logger.info("Preprocessor loaded — %d features", len(preprocessor.feature_columns))
    return preprocessor


# ── Safeguards (run before ML model) ──────────────────────────────────────────

def _apply_safeguards(transaction: dict, history: list[dict]) -> dict | None:
    """
    Return an early-exit result dict if a safeguard triggers, else None.

    None means all safeguards passed — the caller should run the ML model.
    """
    category = str(transaction.get("category", ""))
    amount   = float(transaction.get("amount", 0))
    txn_id   = str(transaction.get("transaction_id", ""))
    user_id  = str(transaction.get("user_id", ""))

    expense_history  = [
        h for h in history
        if str(h.get("transaction_type", "")).lower() == "expense"
    ]
    category_history = [
        h for h in expense_history
        if str(h.get("category", "")) == category
    ]

    base = {
        "transaction_id": txn_id,
        "user_id":        user_id,
        "confidence":     0.0,
        "reason":         None,
        "model_version":  None,
    }

    # 1. Cold-start: not enough total expense history
    if len(expense_history) < COLD_START_TOTAL_MIN:
        logger.info(
            "txn=%s  cold-start: total_expense=%d < %d",
            txn_id, len(expense_history), COLD_START_TOTAL_MIN,
        )
        return {**base, "is_anomaly": False, "anomaly_status": "insufficient_history"}

    # 2. Cold-start: not enough category history
    if len(category_history) < COLD_START_CATEGORY_MIN:
        logger.info(
            "txn=%s  cold-start: category=%r count=%d < %d",
            txn_id, category, len(category_history), COLD_START_CATEGORY_MIN,
        )
        return {**base, "is_anomaly": False, "anomaly_status": "insufficient_history"}

    category_amounts = [float(h.get("amount", 0)) for h in category_history]

    # 3. Same-amount safeguard (exact match within $0.01 for floating-point safety)
    if any(abs(amount - a) < 0.01 for a in category_amounts):
        logger.info("txn=%s  same-amount match (%.2f) in category=%r → normal", txn_id, amount, category)
        return {**base, "is_anomaly": False, "anomaly_status": "normal"}

    # 4. Tolerance safeguard: within 20 % of category mean or max
    cat_mean = sum(category_amounts) / len(category_amounts)
    cat_max  = max(category_amounts)
    within_mean = (abs(amount - cat_mean) / cat_mean <= TOLERANCE_PCT) if cat_mean > 0 else False
    within_max  = (abs(amount - cat_max)  / cat_max  <= TOLERANCE_PCT) if cat_max  > 0 else False
    if within_mean or within_max:
        logger.info(
            "txn=%s  tolerance: amount=%.2f within %.0f%% of mean=%.2f max=%.2f → normal",
            txn_id, amount, TOLERANCE_PCT * 100, cat_mean, cat_max,
        )
        return {**base, "is_anomaly": False, "anomaly_status": "normal"}

    return None  # all safeguards passed — run ML model


# ── Inference helpers ──────────────────────────────────────────────────────────

def _build_context_df(transaction: dict, history: list[dict]) -> pd.DataFrame:
    """
    Combine history + new transaction into one DataFrame.

    Feature engineering is then applied to the whole context, so behavioral
    features (zscore, percentile, freq) for the new transaction are computed
    relative to the user's actual recent history.

    After sorting by date, the new transaction is always the last row.
    """
    all_rows = history + [transaction]
    df = pd.DataFrame(all_rows)
    # Dates arrive as ISO8601 strings from the backend, but with mixed precision
    # (imported rows are midnight 'YYYY-MM-DDTHH:MM:SS+00:00'; manual rows carry
    # microseconds). format="ISO8601" parses each element on its own so the two
    # variants don't clash. errors="coerce" keeps one bad value from 500-ing.
    df["transaction_date"] = pd.to_datetime(
        df["transaction_date"], format="ISO8601", errors="coerce"
    )
    df["amount"] = df["amount"].astype(float)
    df = df.sort_values("transaction_date").reset_index(drop=True)
    return df


def _build_reason(row: pd.Series, is_anomaly: bool, confidence: float) -> str | None:
    """
    Return a short, user-friendly explanation for a flagged transaction.
    Returns None for normal transactions.

    Three signals are checked: high amount (z-score or percentile), high
    category frequency in the past 7 days, and unusual transaction hour.
    Each combination of signals produces a specific natural-language sentence
    so the message always reads as flowing prose, not a semicolon list.
    """
    if not is_anomaly:
        return None

    category = str(row.get("category", "this category"))
    zscore   = float(row.get("amount_zscore", 0))
    freq     = int(row.get("spending_freq_7d", 1))
    pct      = float(row.get("category_percentile", 0))
    hour     = int(row.get("hour", 12))

    high_amount  = zscore > 2.0 or pct > 0.95
    high_freq    = freq > 5
    unusual_time = 1 <= hour <= 4

    # ── No signals → generic fallback ────────────────────────────────────────
    if not high_amount and not high_freq and not unusual_time:
        return "This transaction looks different from your usual spending pattern."

    # ── Single signal ─────────────────────────────────────────────────────────
    if high_amount and not high_freq and not unusual_time:
        return f"This is one of your higher {category} transactions."

    if high_freq and not high_amount and not unusual_time:
        return (
            f"You've made {freq} {category} purchases in the past 7 days, "
            f"which is higher than usual."
        )

    if unusual_time and not high_amount and not high_freq:
        return "This transaction happened at an unusual time — it may be worth reviewing."

    # ── Two signals ───────────────────────────────────────────────────────────
    if high_amount and high_freq and not unusual_time:
        return (
            f"This is one of your higher {category} transactions, "
            f"and you've made {freq} purchases in this category recently."
        )

    if high_amount and unusual_time and not high_freq:
        return (
            f"This is one of your higher {category} transactions, "
            f"and it happened at an unusual time."
        )

    if high_freq and unusual_time and not high_amount:
        return (
            f"You've made {freq} {category} purchases in the past 7 days, "
            f"and it also happened at an unusual time."
        )

    # ── All three signals ─────────────────────────────────────────────────────
    return (
        f"This is one of your higher {category} transactions. "
        f"You've also made {freq} purchases in this category recently, "
        f"and the transaction time was unusual."
    )


# ── Public entry points ────────────────────────────────────────────────────────

def predict_anomaly_batch(
    transactions: list[dict],
    history: list[dict],
) -> list[dict]:
    """
    Predict anomalies for a list of transactions using a shared history.

    Each transaction is evaluated independently against the same history list
    (the user's pre-existing transactions, not other members of this batch).
    The model and preprocessor are loaded once via lru_cache and reused for
    every transaction.

    Returns a list of result dicts in the same order as transactions.
    Never raises — individual transaction failures are caught and returned
    as safe fallback dicts so one bad row cannot abort the whole batch.
    """
    history_dicts = list(history)  # avoid re-converting if already a list
    results: list[dict] = []

    for txn in transactions:
        try:
            result = predict_anomaly(transaction=txn, history=history_dicts)
        except Exception as exc:
            txn_id = str(txn.get("transaction_id", "unknown"))
            user_id = str(txn.get("user_id", "unknown"))
            logger.error(
                "predict_anomaly_batch: prediction failed for txn=%s — using fallback: %s",
                txn_id, exc,
            )
            result = {
                "transaction_id": txn_id,
                "user_id": user_id,
                "is_anomaly": False,
                "anomaly_status": "insufficient_history",
                "confidence": 0.0,
                "reason": None,
                "model_version": None,
            }
        results.append(result)

    anomaly_count = sum(1 for r in results if r.get("is_anomaly"))
    logger.info(
        "predict_anomaly_batch: processed=%d anomalies=%d",
        len(results), anomaly_count,
    )
    return results


def predict_anomaly(transaction: dict, history: list[dict]) -> dict:
    """
    Predict whether a transaction is anomalous.

    Safeguards are checked first. If any trigger, the ML model is skipped and
    an early result is returned with anomaly_status set accordingly.

    Args:
        transaction: dict matching TransactionInput schema.
        history:     list of recent past transaction dicts for the same user.
                     Used for safeguard checks and behavioral feature computation.

    Returns:
        dict with keys:
          transaction_id, user_id, is_anomaly (bool), anomaly_status (str),
          confidence (float 0-1), reason (str|None), model_version (str|None)
    """
    early = _apply_safeguards(transaction, history)
    if early is not None:
        return early

    artifact     = _load_model()
    preprocessor = _load_preprocessor()
    model        = artifact["model"]

    # Build context and compute features
    df = _build_context_df(transaction, history)
    df = engineer_features(df)

    # Last row after chronological sort = the new transaction
    target_row = df.iloc[-1]
    target_df  = pd.DataFrame([target_row])

    # Encode + scale using the fitted preprocessor
    X = preprocessor.transform(target_df)

    # Predict
    is_anomaly_pred = bool(model.predict(X)[0])
    proba           = model.predict_proba(X)[0]
    confidence      = float(proba[1])   # probability of class 1 = anomaly

    reason         = _build_reason(target_row, is_anomaly_pred, confidence)
    anomaly_status = "confirmed_anomaly" if is_anomaly_pred else "normal"

    result = {
        "transaction_id": str(transaction.get("transaction_id", "")),
        "user_id":        str(transaction.get("user_id", "")),
        "is_anomaly":     is_anomaly_pred,
        "anomaly_status": anomaly_status,
        "confidence":     round(confidence, 4),
        "reason":         reason,
        "model_version":  artifact["model_version"],
    }

    logger.info(
        "txn=%s  user=%s  amount=%.2f  category=%s → is_anomaly=%s  status=%s  confidence=%.3f",
        result["transaction_id"],
        result["user_id"],
        transaction.get("amount"),
        transaction.get("category"),
        is_anomaly_pred,
        anomaly_status,
        confidence,
    )
    return result
