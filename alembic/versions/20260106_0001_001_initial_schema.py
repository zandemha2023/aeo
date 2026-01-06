"""Initial schema with multi-tenancy

Revision ID: 001
Revises:
Create Date: 2026-01-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === ORGANIZATIONS (tenant) ===
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("plan", sa.String(50), server_default="free"),
        sa.Column("monthly_llm_budget_usd", sa.Numeric(10, 2), server_default="100.00"),
        sa.Column("rate_limit_rpm", sa.Integer(), server_default="60"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # === USERS ===
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("role", sa.String(50), server_default="member"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("email_verified", sa.Boolean(), server_default="false"),
        sa.Column("last_login_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("ix_users_org_email", "users", ["organization_id", "email"])

    # === API KEYS ===
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), server_default="[]"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("last_used_at", sa.DateTime()),
        sa.Column("expires_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_api_keys_organization_id", "api_keys", ["organization_id"])

    # === LLM USAGE (cost tracking) ===
    op.create_table(
        "llm_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent", sa.String(100), nullable=False),
        sa.Column("workflow", sa.String(100)),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("success", sa.Boolean(), server_default="true"),
        sa.Column("error_message", sa.Text()),
        sa.Column("client_id", postgresql.UUID(as_uuid=True)),  # FK added after clients table
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_llm_usage_organization_id", "llm_usage", ["organization_id"])
    op.create_index("ix_llm_usage_org_created", "llm_usage", ["organization_id", "created_at"])
    op.create_index("ix_llm_usage_org_agent", "llm_usage", ["organization_id", "agent"])

    # === AEO CLIENTS ===
    op.create_table(
        "aeo_clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(100)),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_aeo_clients_organization_id", "aeo_clients", ["organization_id"])
    op.create_index("ix_clients_org_status", "aeo_clients", ["organization_id", "status"])
    op.create_unique_constraint("uq_client_org_domain", "aeo_clients", ["organization_id", "domain"])

    # Add FK from llm_usage to clients (now that clients exist)
    op.create_foreign_key(
        "fk_llm_usage_client",
        "llm_usage",
        "aeo_clients",
        ["client_id"],
        ["id"],
    )

    # === CLIENT INTELLIGENCE ===
    op.create_table(
        "client_intelligence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("aeo_clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("intelligence_type", sa.String(50), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_client_intelligence_organization_id", "client_intelligence", ["organization_id"])
    op.create_index(
        "ix_intel_org_client_type",
        "client_intelligence",
        ["organization_id", "client_id", "intelligence_type"],
    )

    # === MONITORING QUERIES ===
    op.create_table(
        "monitoring_queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("aeo_clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("query_type", sa.String(50)),
        sa.Column("priority", sa.Integer(), server_default="50"),
        sa.Column("active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_monitoring_queries_organization_id", "monitoring_queries", ["organization_id"])
    op.create_index(
        "ix_queries_org_client_active",
        "monitoring_queries",
        ["organization_id", "client_id", "active"],
    )

    # === MONITORING RESULTS ===
    op.create_table(
        "monitoring_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("aeo_clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "query_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("monitoring_queries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("engine", sa.String(50), nullable=False),
        sa.Column("response_text", sa.Text()),
        sa.Column("brand_mentioned", sa.Boolean(), server_default="false"),
        sa.Column("mention_position", sa.Integer()),
        sa.Column("mention_type", sa.String(50)),
        sa.Column("recommended", sa.Boolean(), server_default="false"),
        sa.Column("sentiment", sa.String(20)),
        sa.Column("accuracy", sa.String(20)),
        sa.Column("sources_cited", postgresql.JSONB()),
        sa.Column("competitors_mentioned", postgresql.JSONB()),
        sa.Column("mention_quality_score", sa.Float()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_monitoring_results_organization_id", "monitoring_results", ["organization_id"])
    op.create_index(
        "ix_results_org_client_created",
        "monitoring_results",
        ["organization_id", "client_id", "created_at"],
    )

    # === ALERTS ===
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("aeo_clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), server_default="new"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("acknowledged_at", sa.DateTime()),
        sa.Column("resolved_at", sa.DateTime()),
    )
    op.create_index("ix_alerts_organization_id", "alerts", ["organization_id"])
    op.create_index(
        "ix_alerts_org_client_status",
        "alerts",
        ["organization_id", "client_id", "status"],
    )

    # === PERFORMANCE SNAPSHOTS ===
    op.create_table(
        "performance_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("aeo_clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("snapshot_date", sa.DateTime(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("benchmarks", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_performance_snapshots_organization_id", "performance_snapshots", ["organization_id"])
    op.create_index(
        "ix_snapshots_org_client_date",
        "performance_snapshots",
        ["organization_id", "client_id", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_table("performance_snapshots")
    op.drop_table("alerts")
    op.drop_table("monitoring_results")
    op.drop_table("monitoring_queries")
    op.drop_table("client_intelligence")
    op.drop_constraint("fk_llm_usage_client", "llm_usage", type_="foreignkey")
    op.drop_table("aeo_clients")
    op.drop_table("llm_usage")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("organizations")
