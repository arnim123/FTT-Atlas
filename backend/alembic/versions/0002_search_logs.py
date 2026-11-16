"""search logs and filename trigram index

Revision ID: 0002_search_logs
Revises: 0001_initial
Create Date: 2026-11-16 06:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_search_logs"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

actor_channel = postgresql.ENUM("web", "rest", "mcp", name="actor_channel", create_type=False)


def upgrade() -> None:
    op.create_index(
        "ix_documents_original_filename_trgm",
        "documents",
        ["original_filename"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"original_filename": "gin_trgm_ops"},
    )
    op.create_table(
        "search_logs",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("channel", actor_channel, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("result_count >= 0", name=op.f("ck_search_logs_result_count_nonnegative")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_search_logs_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_logs")),
    )
    op.create_index("ix_search_logs_user_id_created_at", "search_logs", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_search_logs_user_id_created_at", table_name="search_logs")
    op.drop_table("search_logs")
    op.drop_index("ix_documents_original_filename_trgm", table_name="documents", postgresql_using="gin")
