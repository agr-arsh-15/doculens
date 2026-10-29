"""Multi-user schema: profiles, per-user documents and analyses, usage events, app settings.

Creates every table on a fresh database. On a database from the single-user version it adds the new
columns and assigns existing rows to the local user, so a laptop install keeps its history.

Revision ID: 0001_multi_user
Revises:
Create Date: 2026-10-29
"""
import sqlalchemy as sa
from alembic import op
from sqlmodel import SQLModel

from app.storage import db  # noqa: F401  (registers the tables)

revision = "0001_multi_user"
down_revision = None
branch_labels = None
depends_on = None

LEGACY_OWNER = "local-user"


def _columns(inspector, table):
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "documents" in existing and "user_id" not in _columns(inspector, "documents"):
        with op.batch_alter_table("documents") as batch:
            batch.add_column(sa.Column("user_id", sa.String(), nullable=False, server_default=LEGACY_OWNER))
            batch.add_column(sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"))
        op.create_index("ix_documents_user_id", "documents", ["user_id"])
        op.create_index("uq_documents_user_hash", "documents", ["user_id", "content_hash"], unique=True)
    if "analyses" in existing and "user_id" not in _columns(inspector, "analyses"):
        with op.batch_alter_table("analyses") as batch:
            batch.add_column(sa.Column("user_id", sa.String(), nullable=False, server_default=LEGACY_OWNER))
        op.create_index("ix_analyses_user_id", "analyses", ["user_id"])
        op.create_index("ix_analyses_user_created", "analyses", ["user_id", "created_at"])

    # Fresh tables (and fresh databases) come straight from the models.
    SQLModel.metadata.create_all(bind)

    if bind.dialect.name == "postgresql":
        # The API connects as the table owner and scopes every query by user_id itself. Row Level Security
        # with no policies blocks Supabase's public (anon/authenticated) REST access to these tables.
        for table in ("profiles", "documents", "analyses", "usage_events", "app_settings", "alembic_version"):
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    for table in ("usage_events", "app_settings", "profiles"):
        op.drop_table(table)
