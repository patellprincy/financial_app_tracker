"""
RandomForestClassifier configuration for supervised anomaly detection.

Why RandomForest works for financial anomaly detection:
  - Handles mixed features naturally: numeric amounts alongside encoded categories.
  - class_weight='balanced' compensates for the low anomaly rate (~10%) automatically.
    The model penalises missing a real anomaly proportionally more than a false alarm.
  - predict_proba() returns well-calibrated probability scores without extra tuning.
  - Feature importances expose which signals drive each detection decision.
  - Robust to outliers in feature values -- important because anomaly amounts are extreme.
  - Ensemble of 200 decision trees: each tree votes, and the majority wins.
    This prevents any single noisy pattern from dominating predictions.

How it learns user behaviour:
  Each decision tree in the forest splits on feature thresholds, for example:
    if amount_zscore > 4.2 AND spending_freq_7d > 7 -> likely anomaly
    if hour < 5 AND category_percentile > 0.95      -> likely anomaly
    if merchant_enc == <known_normal> AND log_amount < 3.5 -> likely normal
  After 200 such trees vote, the majority class wins.
  The forest learns that the COMBINATION of signals, not any single signal,
  defines an anomaly for this specific user.
"""
from sklearn.ensemble import RandomForestClassifier

RF_PARAMS: dict = {
    "n_estimators":    50,        # 50 trees for stable probability estimates
    "max_depth":       10,       # unlimited depth: learn complex spending patterns
    "min_samples_split": 5,        # prevent splits on tiny noisy groups
    "min_samples_leaf":  2,        # each leaf needs 2+ samples (avoids overfitting)
    "class_weight":   "balanced",  # auto-upweight anomaly class by ~1/anomaly_rate
    "random_state":    42,
    "n_jobs":         -1,          # use all CPU cores during training
}


def build_model() -> RandomForestClassifier:
    """Return a freshly configured, unfitted RandomForestClassifier."""
    return RandomForestClassifier(**RF_PARAMS)
