from fastapi import FastAPI
from app.app import app as backend_app
from ai.app import app as ai_app

main_app = FastAPI(title="FinSight AI Gateway", version="1.0.0")

main_app.mount("/api", backend_app)
main_app.mount("/ai", ai_app)

app = main_app
