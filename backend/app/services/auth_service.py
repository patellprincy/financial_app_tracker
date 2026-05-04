import logging
from datetime import timedelta
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError, SQLAlchemyError
from sqlalchemy.orm import Session
from app.config import settings
from app.models.user import User
from app.schemas.auth import SignupRequest, LoginRequest
from app.core.security import hash_password, verify_password, create_access_token

logger = logging.getLogger(__name__)


def signup_user(request: SignupRequest, db: Session) -> dict:
    logger.info("signup_user: start — email=%s", request.email)
    try:
        logger.info("signup_user: checking for existing user")
        existing = db.query(User).filter(User.email == request.email).first()
        if existing:
            logger.info("signup_user: duplicate email — %s", request.email)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        logger.info("signup_user: hashing password")
        password_hash = hash_password(request.password)

        logger.info("signup_user: creating User object")
        user = User(
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            password_hash=password_hash,
        )

        logger.info("signup_user: db.add")
        db.add(user)

        logger.info("signup_user: db.commit")
        db.commit()

        logger.info("signup_user: db.refresh")
        db.refresh(user)

        logger.info("signup_user: user inserted — id=%s", user.id)

    except HTTPException:
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.error("signup_user: IntegrityError — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    except ProgrammingError as exc:
        db.rollback()
        logger.error("signup_user: ProgrammingError (table missing?) — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database schema error. Ensure the users table exists. Detail: {exc.orig}",
        )
    except OperationalError as exc:
        db.rollback()
        logger.error("signup_user: OperationalError — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection error. Detail: {exc.orig}",
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("signup_user: SQLAlchemyError — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(exc)}",
        )

    try:
        logger.info("signup_user: creating access token")
        token = create_access_token(
            {"sub": str(user.id), "email": user.email},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
    except Exception as exc:
        logger.error("signup_user: token creation failed — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token creation failed: {str(exc)}",
        )

    logger.info("signup_user: success — returning token")
    return {"access_token": token, "token_type": "bearer", "user": user}


def login_user(request: LoginRequest, db: Session) -> dict:
    logger.info("login_user: start — email=%s", request.email)
    try:
        logger.info("login_user: querying user")
        user = db.query(User).filter(User.email == request.email).first()
    except OperationalError as exc:
        logger.error("login_user: OperationalError — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection error. Detail: {exc.orig}",
        )
    except SQLAlchemyError as exc:
        logger.error("login_user: SQLAlchemyError — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(exc)}",
        )

    logger.info("login_user: verifying credentials — user_found=%s", user is not None)
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    try:
        logger.info("login_user: creating access token")
        token = create_access_token(
            {"sub": str(user.id), "email": user.email},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
    except Exception as exc:
        logger.error("login_user: token creation failed — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token creation failed: {str(exc)}",
        )

    logger.info("login_user: success")
    return {"access_token": token, "token_type": "bearer", "user": user}
