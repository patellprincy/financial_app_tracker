from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, Integer, String
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class MerchantClassificationCache(Base):
    """
    Per-user cache of AI classification results keyed by normalized merchant name.

    Rows are inserted on the first AI classification for a given
    (user_id, normalized_merchant, transaction_type) triple and reused on
    subsequent imports or manual entries that resolve to the same key.

    user_id is nullable to allow a future global cache (user_id IS NULL) that
    serves as a cross-user fallback.  All current queries filter by a specific
    user_id.  The partial unique indexes in the SQL migration enforce uniqueness
    separately for user-scoped rows and global rows.
    """

    __tablename__ = "merchant_classification_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # NULL means global / shared across all users (reserved for future use).
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Normalised form of the raw merchant/description string.
    normalized_merchant = Column(String, nullable=False)

    # "expense" or "income" — part of the cache key because the same merchant
    # can legitimately appear as both (e.g. a refund from a shop).
    transaction_type = Column(String, nullable=False)

    # Classification payload.
    category_name = Column(String, nullable=False)
    normalized_category = Column(String, nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)
    reason = Column(String, nullable=False, default="")

    # "ai" for real classifications; "fallback" is never persisted (filtered
    # out before saving) but the column exists for manual overrides.
    source = Column(String, nullable=False, default="ai")

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        # Fast lookup index — uniqueness is enforced by the partial indexes
        # defined in sql/add_merchant_cache.sql.
        Index(
            "idx_mcc_lookup",
            "user_id",
            "normalized_merchant",
            "transaction_type",
        ),
    )
