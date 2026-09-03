"""Add findings, remediation, retests, approvals, and release governance."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_governance_loop"
down_revision: str | None = "0004_proxy_explainability_drift"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = ("findings", "remediation_tasks", "finding_retests", "approvals")


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
        "findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("ai_system_id", sa.String(36), sa.ForeignKey("ai_systems.id"), nullable=False),
        sa.Column("audit_run_id", sa.String(36), sa.ForeignKey("audit_runs.id")),
        sa.Column(
            "source_metric_id",
            sa.String(36),
            sa.ForeignKey("metric_results.id", ondelete="SET NULL"),
        ),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("affected_groups", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("control_refs", sa.JSON(), nullable=False),
        sa.Column("recommended_control", sa.Text()),
        sa.Column("owner_id", sa.String(200), nullable=False),
        sa.Column("owner_name", sa.String(160), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("residual_risk", sa.Text()),
        sa.Column("acceptance_reason", sa.Text()),
        sa.Column("accepted_by", sa.String(200)),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_until", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in (
        "organization_id",
        "ai_system_id",
        "audit_run_id",
        "due_at",
        "status",
        "accepted_until",
    ):
        op.create_index(f"ix_findings_{column}", "findings", [column])

    op.create_table(
        "remediation_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("finding_id", sa.String(36), sa.ForeignKey("findings.id"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("owner_id", sa.String(200), nullable=False),
        sa.Column("owner_name", sa.String(160), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("organization_id", "finding_id", "due_at", "status"):
        op.create_index(f"ix_remediation_tasks_{column}", "remediation_tasks", [column])

    op.create_table(
        "finding_retests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("finding_id", sa.String(36), sa.ForeignKey("findings.id"), nullable=False),
        sa.Column("audit_run_id", sa.String(36), sa.ForeignKey("audit_runs.id"), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("performed_by", sa.String(200), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("organization_id", "finding_id", "audit_run_id"):
        op.create_index(f"ix_finding_retests_{column}", "finding_retests", [column])

    op.create_table(
        "approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("ai_system_id", sa.String(36), sa.ForeignKey("ai_systems.id"), nullable=False),
        sa.Column("chain_version", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("approver_id", sa.String(200)),
        sa.Column("approver_name", sa.String(160)),
        sa.Column("reason", sa.Text()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "ai_system_id", "chain_version", "stage"),
    )
    for column in ("organization_id", "ai_system_id", "decision", "expires_at"):
        op.create_index(f"ix_approvals_{column}", "approvals", [column])

    for table_name in TENANT_TABLES:
        _tenant_table(table_name)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON findings, remediation_tasks, "
        "finding_retests, approvals TO fairhire_app"
    )


def downgrade() -> None:
    for table_name in reversed(TENANT_TABLES):
        op.drop_table(table_name)
