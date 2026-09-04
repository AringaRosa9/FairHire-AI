"""Add versioned evidence reports and read-only assistant records."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_evidence_assistant"
down_revision: str | None = "0005_governance_loop"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = ("reports", "knowledge_sources", "assistant_answers")


def _tenant_table(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table_name} "
        "USING (organization_id = current_setting('app.organization_id', true)) "
        "WITH CHECK (organization_id = current_setting('app.organization_id', true))"
    )


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("ai_system_id", sa.String(36), sa.ForeignKey("ai_systems.id"), nullable=False),
        sa.Column("audit_run_id", sa.String(36), sa.ForeignKey("audit_runs.id"), nullable=False),
        sa.Column(
            "previous_report_id", sa.String(36), sa.ForeignKey("reports.id", ondelete="SET NULL")
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("policy_pack_version", sa.String(100), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("evidence_index", sa.JSON(), nullable=False),
        sa.Column("evidence_gaps", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("approved_by", sa.String(200)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "ai_system_id", "version"),
    )
    for column in ("organization_id", "ai_system_id", "audit_run_id", "status"):
        op.create_index(f"ix_reports_{column}", "reports", [column])

    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("source_key", sa.String(120), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("publisher", sa.String(200), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.String(80)),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("allowed_roles", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "source_key", "version"),
    )
    for column in ("organization_id", "active"):
        op.create_index(f"ix_knowledge_sources_{column}", "knowledge_sources", [column])

    op.create_table(
        "assistant_answers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("ai_system_id", sa.String(36), sa.ForeignKey("ai_systems.id")),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("paragraphs", sa.JSON(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("rule_dates", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("injection_detected", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("organization_id", "ai_system_id"):
        op.create_index(f"ix_assistant_answers_{column}", "assistant_answers", [column])

    for table_name in TENANT_TABLES:
        _tenant_table(table_name)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON reports, knowledge_sources, "
        "assistant_answers TO fairhire_app"
    )


def downgrade() -> None:
    for table_name in reversed(TENANT_TABLES):
        op.drop_table(table_name)
