"""Model and artifact persistence utilities."""
import logging
import os

import joblib

logger = logging.getLogger(__name__)

_ML_ROOT = os.path.join(os.path.dirname(__file__), "..")

SAVED_MODELS_DIR    = os.path.join(_ML_ROOT, "saved_models")
MODEL_PATH          = os.path.join(SAVED_MODELS_DIR, "random_forest.pkl")
PREPROCESSOR_PATH   = os.path.join(SAVED_MODELS_DIR, "preprocessor.pkl")


def save_artifact(obj: object, path: str) -> None:
    """Save any Python object to disk with joblib."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    joblib.dump(obj, path)
    logger.info("Saved → %s", path)


def load_artifact(path: str) -> object:
    """Load a joblib artifact. Raises FileNotFoundError if the path does not exist."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Artifact not found: {path}")
    obj = joblib.load(path)
    logger.info("Loaded → %s", path)
    return obj
