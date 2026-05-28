# FinSight AI — ML Anomaly Detection Microservice

Supervised RandomForest anomaly detection for financial transactions.
Runs as a separate internal service on **port 8002**.

---

## Architecture

```
Android App
     │
     ▼
Main Backend  (port 8000)
     │  POST /ml/detect  (internal call)
     ▼
ML Service    (port 8002)   ← this service
     │
     └── RandomForestClassifier
         trained on labelled transaction data
```

The Android app **never** calls this service directly.
Only the main backend calls `POST /anomaly/detect` on the ML service.

---

## Folder Structure

```
ml/
├── api/
│   └── routes.py               FastAPI route: POST /anomaly/detect
├── data/
│   └── generate_dataset.py     Generates ~2,150 labelled rows for user_0001
├── models/
│   └── random_forest.py        RF hyperparameters + build_model()
├── preprocessing/
│   ├── feature_engineering.py  Date + behavioral feature extraction
│   └── pipeline.py             LabelEncoder + StandardScaler pipeline
├── services/
│   └── prediction_service.py   Inference logic (loads model, runs prediction)
├── training/
│   └── train.py                Full training pipeline with metrics
├── utils/
│   └── model_io.py             Save/load helpers
├── saved_models/
│   ├── random_forest.pkl       Trained model artifact (after training)
│   └── preprocessor.pkl        Fitted encoder + scaler (after training)
├── main.py                     FastAPI app entry point
├── schemas.py                  Pydantic request / response models
└── requirements.txt
```

---

## Quick Start

```bash
# 1. Navigate to the ml folder
cd backend/ml/

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Generate the labelled dataset
python -m data.generate_dataset
# Output: data/transactions_user_0001.csv  (~2,150 rows)

# 5. Train the RandomForest model
python -m training.train
# Output: saved_models/random_forest.pkl
#         saved_models/preprocessor.pkl
# Prints: accuracy, precision, recall, F1, confusion matrix, feature importances

# 6. Start the ML microservice
uvicorn main:app --reload --port 8002
```

---

## API Reference

### POST /anomaly/detect

**Request body:**
```json
{
  "transaction": {
    "transaction_id": "TXN00123",
    "user_id": "user_0001",
    "transaction_date": "2024-08-15 23:47:00",
    "merchant": "Casino Royale",
    "amount": 1500.00,
    "category": "Entertainment",
    "transaction_type": "expense",
    "notes": ""
  },
  "history": [
    {
      "transaction_id": "TXN00120",
      "user_id": "user_0001",
      "transaction_date": "2024-08-14 12:30:00",
      "merchant": "Starbucks",
      "amount": 6.50,
      "category": "Food & Dining",
      "transaction_type": "expense",
      "notes": ""
    }
  ]
}
```

**Response:**
```json
{
  "transaction_id": "TXN00123",
  "user_id": "user_0001",
  "is_anomaly": true,
  "confidence": 0.9241,
  "reason": "$1500.00 is 28.3 standard deviations above your normal Entertainment spending; transaction occurred at an unusual hour (23:00)",
  "model_version": "supervised_v1"
}
```

**Confidence score:**
- `0.0 – 0.49` → normal (is_anomaly = false)
- `0.50 – 0.74` → low-confidence anomaly
- `0.75 – 1.0` → high-confidence anomaly

---

## How the Model Learns User Behaviour

### Features used

| Feature | Type | What it captures |
|---|---|---|
| `log_amount` | numeric | Raw spending level (log-compressed) |
| `amount_zscore` | numeric | Is this amount unusual **for this user** in **this category**? |
| `category_percentile` | numeric | Rank within user's category history (0=cheapest, 1=most expensive) |
| `spending_freq_7d` | numeric | How many same-category purchases in the past 7 days? |
| `day_of_week` | numeric | Weekday vs. weekend patterns |
| `day_of_month` | numeric | Recurring payment dates (rent on 1st, salary biweekly) |
| `month` | numeric | Seasonal spending patterns |
| `hour` | numeric | Time-of-day patterns (late-night = suspicious) |
| `is_weekend` | numeric | Spending pattern by day type |
| `user_id_enc` | encoded | Per-user identity (scales to multi-user naturally) |
| `merchant_enc` | encoded | Known vs. unknown merchants |
| `category_enc` | encoded | Spending category |
| `transaction_type_enc` | encoded | Expense vs. income |

### How user_id influences training

`user_id_enc` lets the model distinguish between users.
When trained on multiple users, a $200 food charge that's normal for user_0042
(who regularly dines at expensive restaurants) but anomalous for user_0001
(who averages $18/meal) will be treated differently.

For single-user training, `user_id` is constant — it becomes discriminative
the moment a second user is added to the training data.

### How transaction_date influences training

`transaction_date` is decomposed into 5 features:
- `day_of_week`: user normally spends Mon–Fri; a large charge on Sunday at 3 am is unusual
- `day_of_month`: the model learns rent comes on the 1st, salary every 14 days
- `month`: captures seasonal variation (holiday shopping in December)
- `hour`: learns that 2 am transactions are unusual for this user
- `is_weekend`: weekend vs. weekday spending profile differs

### Anomaly types the model learns

| Anomaly Type | Key features triggered |
|---|---|
| Large amount | High `amount_zscore`, high `category_percentile` |
| Burst frequency | High `spending_freq_7d` |
| Suspicious merchant | `merchant_enc` = unknown (`__unseen__` class) |
| Late-night | `hour` in 1–4, `is_late_night` signal |

---

## Backend Integration — How to Call This Service

Add an HTTP client to the main backend's transaction service.
The call happens internally after a transaction is saved.

```python
# backend/app/services/ml_client.py
import httpx
import logging

logger = logging.getLogger(__name__)

ML_SERVICE_URL = "http://localhost:8002"
_TIMEOUT = 5.0

async def check_anomaly(transaction: dict, history: list[dict]) -> dict | None:
    """
    Call the ML anomaly detection service.
    Returns the anomaly result dict, or None if the service is unavailable.
    Never raises — the main backend must not fail because ML is down.
    """
    payload = {"transaction": transaction, "history": history}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(f"{ML_SERVICE_URL}/anomaly/detect", json=payload)
            response.raise_for_status()
            return response.json()
    except Exception as exc:
        logger.error("ML service unavailable: %s", exc)
        return None
```

**Call it from transaction_service.py after saving the transaction:**
```python
ml_result = await check_anomaly(
    transaction={
        "transaction_id": str(txn.id),
        "user_id":         str(user_id),
        "transaction_date": txn.created_at.isoformat(),
        "merchant":         txn.merchant,
        "amount":           txn.amount,
        "category":         txn.category_name,
        "transaction_type": txn.transaction_type,
        "notes":            txn.notes,
    },
    history=recent_transactions_as_dicts,   # last 60-90 days
)

if ml_result and ml_result["is_anomaly"]:
    logger.warning("ANOMALY detected: txn=%s  confidence=%.2f  reason=%s",
                   txn.id, ml_result["confidence"], ml_result["reason"])
    # Store anomaly flag on the transaction or notify the user
```

---

## Adding a Second User

The architecture scales to multi-user automatically:

1. Add a new entry in `data/generate_dataset.py → USER_PROFILES`:
   ```python
   USER_PROFILES["user_0002"] = { "categories": {...}, "income_sources": [...] }
   ```

2. Generate combined dataset:
   ```python
   df = pd.concat([generate_dataset("user_0001"), generate_dataset("user_0002")])
   ```

3. Retrain — the model will now learn per-user spending fingerprints via `user_id_enc`
   and the behavioral features (zscore, percentile) already grouped by `user_id`.
