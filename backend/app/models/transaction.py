from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    merchant = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    notes = Column(String, nullable=False, default="")
    transaction_type = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    category_name = Column(String, nullable=False)
    confidence = Column(Float, nullable=False, default=0.5)
    reason = Column(String, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # ML anomaly detection results
    is_anomaly = Column(Boolean, nullable=False, default=False)
    anomaly_score = Column(Float, nullable=True)
    anomaly_reason = Column(Text, nullable=True)
    anomaly_checked_at = Column(DateTime(timezone=True), nullable=True)
    ml_model_version = Column(String, nullable=True)
