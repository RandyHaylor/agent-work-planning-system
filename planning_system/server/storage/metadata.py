"""The one SQLAlchemy MetaData every module declares its tables on (one Alembic history)."""
from sqlalchemy import MetaData

METADATA = MetaData()
