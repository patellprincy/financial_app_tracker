"""
Feature engineering for supervised anomaly detection.

Features extracted:

  From transaction_date (direct):
    day_of_week       -- 0=Monday ... 6=Sunday; model learns weekday spending patterns
    day_of_month      -- 1-31; captures recurring payments (rent on 1st, salary biweekly)
    month             -- 1-12; captures seasonal patterns
    hour              -- 0-23; detects late-night anomalous timing
    is_weekend        -- 0/1; weekday vs. weekend spending pattern

  From amount (numeric transforms):
    log_amount        -- log1p(amount); compresses the wide $ range (coffee to rent)
    amount_zscore     -- std deviations from this user's mean in this category;
                        captures 'unusually high for THIS user in THIS category'
    category_percentile -- rank within user's category history (0=cheapest, 1=most expensive);
                          complements z-score with an outlier rank signal

  From transaction history (behavioral):
    spending_freq_7d  -- count of same-category transactions in the prior 7 days;
                        captures card-compromise-style burst frequency anomalies

  Categorical (encoded in pipeline.py):
    user_id, merchant, category, transaction_type

How behavioral features work at inference:
  The caller passes history (recent past transactions).
  History + new transaction are combined into one DataFrame.
  Features for the new transaction are computed relative to history.
  This means z-score and percentile reflect THIS user's actual spending pattern,
  not population averages -- giving the model a personalised view of 'normal'.
"""
import numpy as np
import pandas as pd

# Numeric features the model receives after encoding + scaling
NUMERIC_FEATURES: list[str] = [
    "log_amount",
    "amount_zscore",
    "category_percentile",
    "spending_freq_7d",
    "day_of_week",
    "day_of_month",
    "month",
    "hour",
    "is_weekend",
]

CATEGORICAL_FEATURES: list[str] = ["user_id", "merchant", "category", "transaction_type"]

# Final ordered feature list that the model expects
ALL_FEATURE_COLUMNS: list[str] = NUMERIC_FEATURES + [f"{c}_enc" for c in CATEGORICAL_FEATURES]


# ── Individual transformations ─────────────────────────────────────────────────

def extract_date_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract temporal signals from transaction_date."""
    df = df.copy()
    dt = pd.to_datetime(df["transaction_date"])
    df["day_of_week"]  = dt.dt.dayofweek          # 0=Monday, 6=Sunday
    df["day_of_month"] = dt.dt.day
    df["month"]        = dt.dt.month
    df["hour"]         = dt.dt.hour
    df["is_weekend"]   = (dt.dt.dayofweek >= 5).astype(int)
    return df


def compute_log_amount(df: pd.DataFrame) -> pd.DataFrame:
    """
    Log1p-transform amount.
    Why: amounts range from $4 (coffee) to $15,000 (luxury goods).
    Linear scale would make the model disproportionately sensitive to large-amount anomalies.
    Log scale preserves the ordering while compressing extreme values.
    """
    df = df.copy()
    df["log_amount"] = np.log1p(df["amount"].astype(float))
    return df


def compute_amount_zscore(df: pd.DataFrame) -> pd.DataFrame:
    """
    Z-score of amount within each (user_id, category) group.

    Meaning: how many standard deviations is this transaction above/below
    the user's average spending in this category?

    Example:
      User's average Food spending: $18, std $7.
      A $200 food charge -> z-score = (200 - 18) / 7 = 26.0
      This signals a massive anomaly within food spending.

    Groups with only one transaction get z-score=0 (no comparison possible).
    At inference with empty history: z-score defaults to 0.
    """
    df = df.copy()
    group_mean = df.groupby(["user_id", "category"])["amount"].transform("mean")
    group_std  = df.groupby(["user_id", "category"])["amount"].transform("std")
    df["amount_zscore"] = (df["amount"] - group_mean) / group_std.replace(0.0, np.nan)
    df["amount_zscore"] = df["amount_zscore"].fillna(0.0)
    return df


def compute_category_percentile(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rank of each transaction's amount within the user's same-category history.

    0.0 = the cheapest transaction this user ever made in this category
    1.0 = the most expensive

    A $500 food charge in a history of mostly $10-$25 food charges -> percentile ~= 1.0
    This signal is complementary to z-score: even if std is large, rank is still extreme.
    """
    df = df.copy()
    df["category_percentile"] = df.groupby(["user_id", "category"])["amount"].transform(
        lambda x: x.rank(pct=True)
    )
    df["category_percentile"] = df["category_percentile"].fillna(0.5)
    return df


def compute_spending_frequency(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each transaction, count how many same-category transactions the same user
    made in the 7-day window ending on that transaction's date (inclusive).

    A value of 15 for Food & Dining in one week is anomalous for a user who
    normally makes 6 food transactions per week.

    At inference: computed from the history provided in the API request.
                  Pass 30-90 days of history for best results.

    Implementation: uses np.searchsorted (O(n log n) per group) instead of
    a boolean-mask scan (O(n^2)) so it stays fast at 500k+ rows.
    """
    df = df.copy()
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df_sorted   = df.sort_values(["user_id", "transaction_date"])
    seven_days  = np.timedelta64(7, "D")

    freq_map: dict = {}
    for (_, _), group in df_sorted.groupby(["user_id", "category"]):
        dates = group["transaction_date"].values   # sorted ascending
        for i, idx in enumerate(group.index):
            window_start = dates[i] - seven_days
            # searchsorted gives the leftmost index where window_start fits;
            # rows from that index to i (inclusive) are within the 7-day window.
            left = np.searchsorted(dates[: i + 1], window_start, side="left")
            freq_map[idx] = i + 1 - left

    df["spending_freq_7d"] = df.index.map(freq_map).fillna(1).astype(int)
    return df


# ── Combined pipeline ──────────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply all feature engineering steps in sequence.

    Input:  raw transaction DataFrame (must contain transaction_date, amount,
            user_id, category columns).
    Output: enriched DataFrame with all ML feature columns added.
    """
    df = extract_date_features(df)
    df = compute_log_amount(df)
    df = compute_amount_zscore(df)
    df = compute_category_percentile(df)
    df = compute_spending_frequency(df)
    return df
