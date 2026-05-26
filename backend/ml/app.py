"""
FinSight AI — ML Anomaly Detection Microservice
Port: 8002

Communication rule:
  Android App  →  Main Backend (8000)  →  ML Service (8002)
  ML results flow back to the main backend only — never directly to Android.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as anomaly_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FinSight AI — ML Anomaly Detection",
    version="1.0.0",
    description=(
        "Supervised RandomForest anomaly detection microservice. "
        "Internal service — called by the main backend only."
    ),
)

# Only accept calls from the main backend, not from external clients.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(anomaly_router)


@app.on_event("startup")
async def startup() -> None:
    model_path = os.getenv("RF_MODEL_PATH", "saved_models/random_forest.pkl")
    logger.info("=== FinSight ML Microservice starting on port 8002 ===")
    if os.path.exists(model_path):
        logger.info("STARTUP: Trained model found — %s", model_path)
    else:
        logger.warning(
            "STARTUP: No trained model at '%s'. "
            "Generate data:  python -m data.generate_dataset  "
            "Then train:     python -m training.train",
            model_path,
        )
    logger.info("=== Ready — POST /anomaly/detect ===")


@app.get("/")
def root() -> dict:
    return {
        "service": "FinSight ML Anomaly Detection",
        "status": "running",
        "port": 8002,
    }


@app.get("/health")
def health() -> dict:
    model_path = os.getenv("RF_MODEL_PATH", "saved_models/random_forest.pkl")
    return {
        "status": "healthy",
        "model_ready": os.path.exists(model_path),
    }
