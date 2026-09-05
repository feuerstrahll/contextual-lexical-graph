"""Create the initial domain model.

Revision ID: 0001_initial_domain_model
Revises:
"""
from alembic import op

from app.db import Base
import app.models  # noqa: F401

revision = "0001_initial_domain_model"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
