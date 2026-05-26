"""
Reusable preprocessing pipeline: LabelEncoder + StandardScaler.

Critical rule:
  Fit ONLY on training data.
  Apply the same fitted instance to test data and at inference.

  If you fit on the whole dataset (train+test), the scaler's mean and std
  are influenced by test values — this is called data leakage.
  Data leakage causes optimistic evaluation metrics that don't reflect
  real-world performance.

Flow:
  Training:   preprocessor.fit(X_train_df)
              X_train = preprocessor.transform(X_train_df)
              X_test  = preprocessor.transform(X_test_df)   ← same fitted instance

  Inference:  preprocessor = AnomalyPreprocessor.load(path)
              X_new = preprocessor.transform(new_transaction_df)

Unseen values at inference:
  If a new merchant or category appears at inference that was not seen during
  training, the LabelEncoder maps it to '__unseen__', which was included in
  every encoder's class list during fit.  This prevents KeyError crashes.
"""
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler

from preprocessing.feature_engineering import ALL_FEATURE_COLUMNS, CATEGORICAL_FEATURES


class AnomalyPreprocessor:

    def __init__(self) -> None:
        self.label_encoders: dict[str, LabelEncoder] = {}
        self.scaler = StandardScaler()
        self.feature_columns: list[str] = ALL_FEATURE_COLUMNS
        self.is_fitted: bool = False

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _fit_encoders(self, df: pd.DataFrame) -> None:
        for col in CATEGORICAL_FEATURES:
            le = LabelEncoder()
            # Include '__unseen__' so inference never crashes on unknown values
            values = df[col].astype(str).fillna("unknown").tolist() + ["__unseen__"]
            le.fit(values)
            self.label_encoders[col] = le

    def _apply_encoders(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col, le in self.label_encoders.items():
            raw   = df[col].astype(str).fillna("unknown")
            known = set(le.classes_)
            # Unknown values at inference → '__unseen__' (always safe to encode)
            mapped = raw.apply(lambda v: v if v in known else "__unseen__")
            df[f"{col}_enc"] = le.transform(mapped)
        return df

    # ── Public interface ───────────────────────────────────────────────────────

    def fit(self, df: pd.DataFrame) -> "AnomalyPreprocessor":
        """Fit encoders and scaler on training data only."""
        self._fit_encoders(df)
        df_enc = self._apply_encoders(df)
        X = df_enc[self.feature_columns].values
        self.scaler.fit(X)
        self.is_fitted = True
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """Encode categoricals, then scale all features. Returns numpy array."""
        if not self.is_fitted:
            raise RuntimeError("Call fit() before transform().")
        df_enc = self._apply_encoders(df)
        X = df_enc[self.feature_columns].values
        return self.scaler.transform(X)

    def fit_transform(self, df: pd.DataFrame) -> np.ndarray:
        return self.fit(df).transform(df)

    # ── Persistence ────────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        joblib.dump(self, path)
        print(f"  Preprocessor saved: {path}")

    @classmethod
    def load(cls, path: str) -> "AnomalyPreprocessor":
        obj = joblib.load(path)
        if not isinstance(obj, cls):
            raise TypeError(f"Expected AnomalyPreprocessor, got {type(obj)}")
        return obj
