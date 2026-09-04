"""Add explicit policy-pack expiry for release-gate enforcement."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_pilot_readiness"
down_revision: str | None = "0006_evidence_assistant"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("policy_pack_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "policy_pack_expires_at")
