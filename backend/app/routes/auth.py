import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.auth import SignupRequest, LoginRequest, AuthResponse
from app.schemas.user import UserResponse
from app.services.auth_service import signup_user, login_user
from app.core.security import get_current_user
from app.core.rate_limit import limiter
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse, status_code=201)
@limiter.limit("3/minute")
async def signup(request: Request, body: SignupRequest, db: Session = Depends(get_db)):
    logger.info("POST /auth/signup — email=%s", body.email)
    return signup_user(body, db)


@router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    logger.info("POST /auth/login — email=%s", body.email)
    return login_user(body, db)


@router.get("/me", response_model=UserResponse)
@limiter.limit("30/minute")
async def me(request: Request, current_user: User = Depends(get_current_user)):
    return current_user
