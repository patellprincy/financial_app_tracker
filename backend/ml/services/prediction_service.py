"""
Prediction service — supervised anomaly detection inference.

Complete inference flow:
  1. Receive transaction dict + history list from the API route.
  2. Merge history + transaction into a single DataFrame.
  3. Apply feature engineering to the full context (history gives behavioral baseline).
  4. Extract the last row = the new transaction with all features computed.
  5. preprocessor.transform() — encode + scale using the fitted pipeline.
  6. model.predict() → is_anomaly (0 or 1)
     model.predict_proba() → [prob_normal, prob_anomaly]
  7. Build a human-readable reason string from the feature values.
  8. Return is_anomaly, confidence (prob_anomaly), reason, model_version.

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
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df["amount"] = df["amount"].astype(float)
    df = df.sort_values("transaction_date").reset_index(drop=True)
    return df


def _build_reason(row: pd.Series, is_anomaly: bool, confidence: float) -> str | None:
    """Build a human-readable explanation from feature values. Returns None for normal transactions."""
    if not is_anomaly:
        return None

    reasons: list[str] = []
    amount   = float(row.get("amount", 0))
    category = str(row.get("category", "this category"))
    zscore   = float(row.get("amount_zscore", 0))
    freq     = int(row.get("spending_freq_7d", 1))
    pct      = float(row.get("category_percentile", 0))
    hour     = int(row.get("hour", 12))

    if zscore > 3.0:
        reasons.append(
            f"${amount:.2f} is {zscore:.1f} standard deviations above your normal "
            f"{category} spending"
        )
    elif zscore > 2.0:
        reasons.append(f"${amount:.2f} is unusually high for {category}")

    if freq > 5:
        reasons.append(
            f"unusually high spending frequency: {freq} {category} "
            f"transactions in the past 7 days"
        )

    if 1 <= hour <= 4:
        reasons.append(f"transaction occurred at an unusual hour ({hour}:00)")

    if pct > 0.95:
        reasons.append(
            f"amount is in the top {(1 - pct) * 100:.0f}% of your "
            f"{category} spending history"
        )

    if not reasons:
        reasons.append(
            f"spending pattern deviates from your learned behaviour "
            f"(model confidence: {confidence * 100:.1f}%)"
        )

    return "; ".join(reasons)


# ── Public entry point ─────────────────────────────────────────────────────────

def predict_anomaly(transaction: dict, history: list[dict]) -> dict:
    """
    Predict whether a transaction is anomalous.

    Args:
        transaction: dict matching TransactionInput schema.
        history:     list of recent past transaction dicts for the same user.
                     Used to compute personalised behavioral features.

    Returns:
        dict with keys:
          transaction_id, user_id, is_anomaly (bool),
          confidence (float 0-1), reason (str|None), model_version (str)
    """
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

    reason = _build_reason(target_row, is_anomaly_pred, confidence)

    result = {
        "transaction_id": str(transaction.get("transaction_id", "")),
        "user_id":        str(transaction.get("user_id", "")),
        "is_anomaly":     is_anomaly_pred,
        "confidence":     round(confidence, 4),
        "reason":         reason,
        "model_version":  artifact["model_version"],
    }

    logger.info(
        "txn=%s  user=%s  amount=%.2f  category=%s → is_anomaly=%s  confidence=%.3f",
        result["transaction_id"],
        result["user_id"],
        transaction.get("amount"),
        transaction.get("category"),
        is_anomaly_pred,
        confidence,
    )
    return result
