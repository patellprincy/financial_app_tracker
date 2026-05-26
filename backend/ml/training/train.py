"""
Supervised anomaly detection - full training pipeline.

Steps:
  1  Load labeled dataset (auto-generates if CSV not found)
  2  Feature engineering
  3  Stratified train-test split  (80 / 20)
  4  Fit AnomalyPreprocessor on training data only
  5  Transform both splits
  6  Train RandomForestClassifier
  7  Evaluate: accuracy, precision, recall, F1, F2, confusion matrix
  8  Print feature importances
  9  Save model artifact + preprocessor to saved_models/

Usage:
  cd backend/ml/
  python -m training.train
"""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split

from data.generate_dataset import generate_multiuser_dataset
from models.random_forest import RF_PARAMS, build_model
from preprocessing.feature_engineering import engineer_features
from preprocessing.pipeline import AnomalyPreprocessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
_ML_ROOT        = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH       = os.path.join(_ML_ROOT, "data", "transactions_multiuser.csv")
SAVED_DIR       = os.path.join(_ML_ROOT, "saved_models")
MODEL_PATH      = os.path.join(SAVED_DIR, "random_forest.pkl")
PREPROCESSOR_PATH = os.path.join(SAVED_DIR, "preprocessor.pkl")

TEST_SIZE      = 0.20
RANDOM_STATE   = 42
DROP_COLUMNS   = ["is_anomaly", "transaction_id", "notes"]


# ── Display helpers ────────────────────────────────────────────────────────────

def _sep(title: str = "") -> None:
    print(f"\n{'-' * 62}")
    if title:
        print(f"  {title}")
        print(f"{'-' * 62}")


def _print_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    acc  = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec  = recall_score(y_true, y_pred, zero_division=0)
    f1   = f1_score(y_true, y_pred, zero_division=0)
    # beta=2 weights recall twice as heavily as precision.
    # In fraud/anomaly detection, a missed real anomaly (false negative) is
    # far more costly than a false alarm (false positive), so F2 is a better
    # single-number summary than F1 for this use case.
    f2   = fbeta_score(y_true, y_pred, beta=2, zero_division=0)
    cm   = confusion_matrix(y_true, y_pred)

    # Accuracy alone is misleading on imbalanced datasets: a model that
    # labels every transaction as normal would score ~90% accuracy while
    # catching zero anomalies. Always read recall and F2 alongside accuracy.
    print(f"\n  Accuracy   : {acc:.4f}  [misleading alone on imbalanced data -- see recall]")
    print(f"  Precision  : {prec:.4f}  [of all flagged anomalies, how many are real]")
    # Recall = TP / (TP + FN). Maximising this minimises missed fraud.
    print(f"  Recall     : {rec:.4f}  [of all real anomalies, how many were caught] [PRIORITY]")
    print(f"  F1-Score   : {f1:.4f}  [harmonic mean of precision and recall -- equal weight]")
    print(f"  F2-Score   : {f2:.4f}  [prioritizes recall over precision -- penalizes missed anomalies more]")

    tn, fp, fn, tp = cm.ravel()
    print(f"\n  Confusion Matrix:")
    print(f"  {'':30}  Predicted Normal   Predicted Anomaly")
    print(f"  {'Actual Normal':30}      {tn:>6}              {fp:>6}")
    print(f"  {'Actual Anomaly':30}      {fn:>6}              {tp:>6}")
    print()
    print("  Interpretation:")
    print(f"    True  Positives (TP) : {tp}  -real anomalies correctly caught")
    print(f"    False Negatives (FN) : {fn}  -real anomalies missed  [minimise this]")
    print(f"    False Positives (FP) : {fp}  -normal transactions incorrectly flagged")
    print(f"    True  Negatives (TN) : {tn}  -normal transactions correctly passed")

    print(f"\n  Per-class Report:")
    print(classification_report(
        y_true, y_pred,
        target_names=["Normal (0)", "Anomaly (1)"],
        zero_division=0,
    ))

    print("  F2-Score interpretation:")
    print("    F2 = (1 + 2^2) * (precision * recall) / (2^2 * precision + recall)")
    print("    Beta=2 means recall is weighted 4x as much as precision in the denominator.")
    print("    A high F2 with lower F1 means the model catches most anomalies (good),")
    print("    but may produce some false alarms (acceptable in fraud detection).")
    print("    A low F2 means too many real anomalies are being missed (dangerous).")

    return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1, "f2": f2}


# ── Training pipeline ──────────────────────────────────────────────────────────

def train() -> None:
    os.makedirs(SAVED_DIR, exist_ok=True)

    # ── Step 1: Load Dataset ──────────────────────────────────────────────────
    _sep("Step 1 - Load Dataset")
    if os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH, parse_dates=["transaction_date"])
        print(f"  Loaded from: {DATA_PATH}")
    else:
        print("  CSV not found -generating multi-user dataset now  (this takes ~5 min) ...")
        df = generate_multiuser_dataset()
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        df.to_csv(DATA_PATH, index=False)
        print(f"  Dataset saved: {DATA_PATH}")

    n_total = len(df)
    n_anom  = int(df["is_anomaly"].sum())
    n_norm  = n_total - n_anom
    n_users = df["user_id"].nunique()
    print(f"\n  Total rows   : {n_total:,}")
    print(f"  Users        : {n_users}")
    print(f"  Normal   (0) : {n_norm:,}  ({n_norm / n_total * 100:.1f}%)")
    print(f"  Anomaly  (1) : {n_anom:,}  ({n_anom / n_total * 100:.1f}%)")
    print(f"\n  Columns: {list(df.columns)}")

    # ── Step 2: Feature Engineering ───────────────────────────────────────────
    _sep("Step 2 -Feature Engineering")
    print("  Extracting date features:        day_of_week, day_of_month, month, hour, is_weekend")
    print("  Computing behavioral features:   log_amount, amount_zscore, category_percentile")
    print("  Computing frequency feature:     spending_freq_7d  (7-day rolling window)")
    df = engineer_features(df)
    print("  Done.")

    # ── Step 3: Train-Test Split ──────────────────────────────────────────────
    _sep("Step 3 -Stratified Train-Test Split  (80 / 20)")
    X_raw = df.drop(columns=DROP_COLUMNS, errors="ignore")
    y     = df["is_anomaly"].values

    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X_raw, y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )
    print(f"\n  Train : {len(y_train):>6,} rows  | anomalies = {y_train.sum():,} ({y_train.mean()*100:.1f}%)")
    print(f"  Test  : {len(y_test):>6,} rows  | anomalies = {y_test.sum():,} ({y_test.mean()*100:.1f}%)")
    print()
    print("  stratify=y ensures both splits have the same anomaly percentage.")

    # ── Step 4: Preprocessing ─────────────────────────────────────────────────
    _sep("Step 4 -Preprocessing  (fit on training data only)")
    print("  Fitting LabelEncoders for: user_id, merchant, category, transaction_type")
    print("  Fitting StandardScaler on all 13 feature columns")

    preprocessor = AnomalyPreprocessor()
    X_train = preprocessor.fit_transform(X_train_raw)
    X_test  = preprocessor.transform(X_test_raw)

    print(f"\n  X_train shape : {X_train.shape}  ({X_train.shape[1]} features)")
    print(f"  X_test  shape : {X_test.shape}")

    # ── Step 5: Train RandomForestClassifier ─────────────────────────────────
    _sep("Step 5 -Training RandomForestClassifier")
    print(f"  Parameters: {RF_PARAMS}")
    print()
    print("  class_weight='balanced' explanation:")
    print(f"    Anomaly rate ~{n_anom/n_total*100:.1f}%  normal/anomaly ratio ~{n_norm//n_anom}:1")
    print(f"    balanced weight automatically makes each anomaly count ~{n_norm//n_anom}x more")
    print(f"    than a normal transaction during training.")

    model = build_model()
    model.fit(X_train, y_train)
    print("\n  Training complete.")

# --------------------------------------------------------------
# STEP 6 - PREDICTIONS WITH CUSTOM THRESHOLD
# --------------------------------------------------------------

    # Get probability scores for anomaly class (class 1)
    y_probs = model.predict_proba(X_test)[:, 1]

    # Lower threshold to improve recall
    THRESHOLD = 0.3

    # Convert probabilities into final predictions
    y_pred = (y_probs >= THRESHOLD).astype(int)

    print("\n--------------------------------------------------------------")
    print(f" Using custom anomaly threshold: {THRESHOLD}")
    print(" Lower threshold = higher recall / more anomaly detection")
    print("--------------------------------------------------------------")

    # ── Step 6: Evaluate ──────────────────────────────────────────────────────
    _sep("Step 6 -Evaluation on Test Set")
    metrics = _print_metrics(y_test, y_pred)

    # ── Step 7: Feature Importances ───────────────────────────────────────────
    _sep("Step 7 -Feature Importances  (which signals drive detection)")
    pairs = sorted(
        zip(preprocessor.feature_columns, model.feature_importances_),
        key=lambda x: x[1],
        reverse=True,
    )
    print()
    for feat, imp in pairs:
        bar = "#" * int(imp * 350)
        print(f"  {feat:<32} {imp:.4f}  {bar}")
    print()
    print("  High importance on amount_zscore / category_percentile means the model relies on")
    print("  personalised spending behaviour, not just raw amounts.")

    # ── Step 8: Save Artifacts ────────────────────────────────────────────────
    _sep("Step 8 -Saving Artifacts to saved_models/")
    artifact = {
        "model":           model,
        "model_name":      "RandomForestClassifier",
        "model_version":   "supervised_v2",
        "trained_on":      f"multiuser_{n_users}",
        "feature_columns": preprocessor.feature_columns,
        "rf_params":       RF_PARAMS,
        "threshold": THRESHOLD,
        "metrics":         metrics,
    }
    joblib.dump(artifact, MODEL_PATH)
    print(f"  Model saved:        {MODEL_PATH}")
    preprocessor.save(PREPROCESSOR_PATH)

    _sep()
    print("  Training pipeline complete.\n")
    print(f"  Accuracy   : {metrics['accuracy']:.4f}")
    print(f"  Precision  : {metrics['precision']:.4f}")
    print(f"  Recall     : {metrics['recall']:.4f}  [primary metric - catching real anomalies]")
    print(f"  F1-Score   : {metrics['f1']:.4f}  [equal weight on precision and recall]")
    print(f"  F2-Score   : {metrics['f2']:.4f}  [recall-weighted -- primary for fraud detection]")
    print()
    print("  Start the ML service:")
    print("    uvicorn main:app --reload --port 8002")


if __name__ == "__main__":
    train()
