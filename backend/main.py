# Backwards-compatible entry point. Prefer the explicit form:
#
#   uvicorn app.main:app --reload --port 8000
#
# This file is retained so that `uvicorn main:app --port 8000` (run from
# inside backend/) also works without breaking existing scripts.
#
# The AI service is now a separate process:
#   uvicorn ai.app:app --reload --port 8001

from app.app import app  # noqa: F401

__all__ = ["app"]
