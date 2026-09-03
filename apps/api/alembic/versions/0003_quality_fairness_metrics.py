"""Add reproducible data-quality and fairness metric results."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_quality_fairness_metrics"
down_revision: str | None = "0002_registry_ingestion_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metric_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("audit_run_id", sa.String(36), sa.ForeignKey("audit_runs.id"), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("metric_key", sa.String(80), nullable=False),
        sa.Column("protected_attribute", sa.String(200)),
        sa.Column("reference_group", sa.String(300)),
        sa.Column("comparison_group", sa.String(300)),
        sa.Column("value", sa.Float()),
        sa.Column("lower_bound", sa.Float()),
        sa.Column("upper_bound", sa.Float()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("threshold", sa.Float()),
        sa.Column("threshold_operator", sa.String(16)),
        sa.Column("threshold_source", sa.JSON(), nullable=False),
        sa.Column("raw_counts", sa.JSON(), nullable=False),
        sa.Column("method", sa.String(80), nullable=False),
        sa.Column("calculation_version", sa.String(100), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "audit_run_id",
            "metric_key",
            "protected_attribute",
            "comparison_group",
        ),
    )
    op.create_index("ix_metric_results_organization_id", "metric_results", ["organization_id"])
    op.create_index("ix_metric_results_audit_run_id", "metric_results", ["audit_run_id"])
    op.execute("ALTER TABLE metric_results ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE metric_results FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON metric_results "
        "USING (organization_id = current_setting('app.organization_id', true)) "
        "WITH CHECK (organization_id = current_setting('app.organization_id', true))"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON metric_results TO fairhire_app")


def downgrade() -> None:
    op.drop_table("metric_results")
