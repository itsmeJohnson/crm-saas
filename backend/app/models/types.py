import sqlalchemy as sa
from sqlalchemy.types import TypeDecorator
from app.core.email_utils import normalize_email

class NormalizedEmail(TypeDecorator):
    """
    SQLAlchemy TypeDecorator for normalized email fields.
    Automatically normalizes emails on insert/update (bind params) and queries.
    """
    impl = sa.String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return normalize_email(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return normalize_email(value)
