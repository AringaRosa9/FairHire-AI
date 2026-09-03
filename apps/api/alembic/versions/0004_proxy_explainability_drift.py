"""Add explicit audit baselines for proxy, explanation, and drift analysis."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_proxy_explainability_drift"
down_revision: str | None = "0003_quality_fairness_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audit_runs",
        sa.Column("baseline_run_id", sa.String(36), sa.ForeignKey("audit_runs.id")),
    )
    op.create_index("ix_audit_runs_baseline_run_id", "audit_runs", ["baseline_run_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_runs_baseline_run_id", table_name="audit_runs")
    op.drop_column("audit_runs", "baseline_run_id")
