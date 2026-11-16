"""oauth authorization server tables

Revision ID: 0003_oauth
Revises: 0002_search_logs
Create Date: 2026-11-16 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_oauth"
down_revision: Union[str, Sequence[str], None] = "0002_search_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oauth_clients",
        sa.Column("client_id", sa.Text(), nullable=False),
        sa.Column("client_secret_hash", sa.Text(), nullable=True),
        sa.Column("client_name", sa.Text(), nullable=False),
        sa.Column("redirect_uris", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("grant_types", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("response_types", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("token_endpoint_auth_method", sa.Text(), nullable=False),
        sa.Column("registration_kind", sa.Text(), nullable=False),
        sa.Column("source_ip", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "registration_kind IN ('dynamic', 'metadata')",
            name=op.f("ck_oauth_clients_registration_kind"),
        ),
        sa.CheckConstraint(
            "token_endpoint_auth_method IN ('none', 'client_secret_basic', 'client_secret_post')",
            name=op.f("ck_oauth_clients_token_endpoint_auth_method"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_clients")),
        sa.UniqueConstraint("client_id", name=op.f("uq_oauth_clients_client_id")),
    )
    op.create_index(op.f("ix_oauth_clients_source_ip"), "oauth_clients", ["source_ip"], unique=False)
    op.create_table(
        "oauth_grants",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("oauth_client_id", sa.UUID(), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["oauth_client_id"], ["oauth_clients.id"], name=op.f("fk_oauth_grants_oauth_client_id_oauth_clients"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_oauth_grants_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_grants")),
    )
    op.create_index(op.f("ix_oauth_grants_user_id"), "oauth_grants", ["user_id"], unique=False)
    op.create_index(op.f("ix_oauth_grants_oauth_client_id"), "oauth_grants", ["oauth_client_id"], unique=False)
    op.create_table(
        "oauth_authorization_codes",
        sa.Column("oauth_client_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("grant_id", sa.UUID(), nullable=True),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("requested_scopes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("granted_scopes", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("code_challenge", sa.Text(), nullable=False),
        sa.Column("code_challenge_method", sa.Text(), nullable=False),
        sa.Column("resource", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("code_hash", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("denied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["grant_id"], ["oauth_grants.id"], name=op.f("fk_oauth_authorization_codes_grant_id_oauth_grants"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["oauth_client_id"], ["oauth_clients.id"], name=op.f("fk_oauth_authorization_codes_oauth_client_id_oauth_clients"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_oauth_authorization_codes_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_authorization_codes")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_oauth_authorization_codes_code_hash")),
    )
    op.create_index(op.f("ix_oauth_authorization_codes_expires_at"), "oauth_authorization_codes", ["expires_at"], unique=False)
    op.create_table(
        "oauth_tokens",
        sa.Column("grant_id", sa.UUID(), nullable=False),
        sa.Column("oauth_client_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("audience", sa.Text(), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('access', 'refresh')", name=op.f("ck_oauth_tokens_kind")),
        sa.ForeignKeyConstraint(["grant_id"], ["oauth_grants.id"], name=op.f("fk_oauth_tokens_grant_id_oauth_grants"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["oauth_client_id"], ["oauth_clients.id"], name=op.f("fk_oauth_tokens_oauth_client_id_oauth_clients"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_oauth_tokens_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_oauth_tokens_token_hash")),
    )
    op.create_index(op.f("ix_oauth_tokens_expires_at"), "oauth_tokens", ["expires_at"], unique=False)
    op.create_index(op.f("ix_oauth_tokens_grant_id"), "oauth_tokens", ["grant_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_api_audit_logs_oauth_client_id_oauth_clients"),
        "api_audit_logs",
        "oauth_clients",
        ["oauth_client_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_api_audit_logs_oauth_client_id_oauth_clients"), "api_audit_logs", type_="foreignkey")
    op.drop_index(op.f("ix_oauth_tokens_grant_id"), table_name="oauth_tokens")
    op.drop_index(op.f("ix_oauth_tokens_expires_at"), table_name="oauth_tokens")
    op.drop_table("oauth_tokens")
    op.drop_index(op.f("ix_oauth_authorization_codes_expires_at"), table_name="oauth_authorization_codes")
    op.drop_table("oauth_authorization_codes")
    op.drop_index(op.f("ix_oauth_grants_oauth_client_id"), table_name="oauth_grants")
    op.drop_index(op.f("ix_oauth_grants_user_id"), table_name="oauth_grants")
    op.drop_table("oauth_grants")
    op.drop_index(op.f("ix_oauth_clients_source_ip"), table_name="oauth_clients")
    op.drop_table("oauth_clients")
