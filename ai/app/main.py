from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.classify import router as classify_router

app = FastAPI(title="AI Classification Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(classify_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-classification"}
