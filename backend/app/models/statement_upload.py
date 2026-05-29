import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class StatementUpload(Base):
    __tablename__ = "statement_uploads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="uploaded")
    total_transactions = Column(Integer, nullable=True)
    imported_transactions = Column(Integer, nullable=True)
    failed_transactions = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
