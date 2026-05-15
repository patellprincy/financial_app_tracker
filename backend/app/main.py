# Entry point for the main backend service.
#
# Run locally:
#   cd backend/
#   uvicorn app.main:app --reload --port 8000
#
# The AI classification service runs separately:
#   uvicorn ai.app:app --reload --port 8001

from app.app import app  # noqa: F401 — re-exported for uvicorn

__all__ = ["app"]
