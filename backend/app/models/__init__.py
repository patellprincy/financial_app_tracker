# Import all models so they are registered on Base.metadata and visible to
# any tool that introspects the ORM (e.g. Alembic).
from app.models.user import User  # noqa: F401
from app.models.category import Category  # noqa: F401
from app.models.transaction import Transaction  # noqa: F401
from app.models.statement_upload import StatementUpload  # noqa: F401
from app.models.merchant_cache import MerchantClassificationCache  # noqa: F401
