"""Create organization, registry, idempotency and audit ledger foundation."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("region", sa.String(24), nullable=False),
        sa.Column("policy_pack", sa.String(100), nullable=False),
        sa.Column("retention_policy", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "user_id"),
    )
    op.create_index("ix_memberships_organization_id", "memberships", ["organization_id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_table(
        "ai_systems",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("lifecycle_status", sa.String(24), nullable=False),
        sa.Column("release_status", sa.String(32), nullable=False),
        sa.Column("provider_type", sa.String(24), nullable=False),
        sa.Column("provider_name", sa.String(200)),
        sa.Column("jurisdictions", sa.JSON(), nullable=False),
        sa.Column("owner_name", sa.String(160), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True)),
        sa.Column("assessment_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ai_systems_organization_id", "ai_systems", ["organization_id"])
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_code", sa.Integer()),
        sa.Column("response_body", sa.JSON()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("organization_id", "key"),
    )
    op.create_index(
        "ix_idempotency_records_organization_id", "idempotency_records", ["organization_id"]
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("previous_hash", sa.String(64)),
        sa.Column("current_hash", sa.String(64), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"])

    op.bulk_insert(
        sa.table(
            "organizations",
            sa.column("id", sa.String),
            sa.column("name", sa.String),
            sa.column("region", sa.String),
            sa.column("policy_pack", sa.String),
            sa.column("retention_policy", sa.JSON),
        ),
        [
            {
                "id": "org-northstar",
                "name": "Northstar Hiring Group",
                "region": "eu",
                "policy_pack": "eu-core+de@2026.09",
                "retention_policy": {"candidate_raw_days": 30, "aggregate_days": 730},
            },
            {
                "id": "org-other",
                "name": "Other Tenant",
                "region": "eu",
                "policy_pack": "eu-core@2026.09",
                "retention_policy": {"candidate_raw_days": 14, "aggregate_days": 365},
            },
        ],
    )
    op.bulk_insert(
        sa.table(
            "memberships",
            sa.column("id", sa.String),
            sa.column("organization_id", sa.String),
            sa.column("user_id", sa.String),
            sa.column("email", sa.String),
            sa.column("display_name", sa.String),
            sa.column("role", sa.String),
            sa.column("active", sa.Boolean),
        ),
        [
            {
                "id": "mem-maya",
                "organization_id": "org-northstar",
                "user_id": "maya.chen@fairhire.test",
                "email": "maya.chen@fairhire.test",
                "display_name": "Maya Chen",
                "role": "admin",
                "active": True,
            },
            {
                "id": "mem-other",
                "organization_id": "org-other",
                "user_id": "other@fairhire.test",
                "email": "other@fairhire.test",
                "display_name": "Other User",
                "role": "admin",
                "active": True,
            },
        ],
    )
    systems = [
        (
            "sys-talentrank",
            "TalentRank EU",
            "Scores candidate applications for recruiter review",
            "active",
            "review_required",
            "internal",
            None,
            ["EU", "DE", "FR", "NL"],
            "Maya Chen",
            "2026-09-03 09:00:00+00",
            3,
        ),
        (
            "sys-cvlens",
            "CV Lens",
            "Reads resumes and extracts job-relevant evidence",
            "active",
            "approved",
            "third_party",
            "Asteria ATS",
            ["EU"],
            "Ana Silva",
            "2026-11-15 09:00:00+00",
            2,
        ),
        (
            "sys-interviewsense",
            "InterviewSense EU",
            "Reviews video interviews during a controlled trial",
            "trial",
            "blocked",
            "third_party",
            "Outside supplier",
            ["DE"],
            "Ana Silva",
            "2026-09-01 13:00:00+00",
            1,
        ),
        (
            "sys-rolematch",
            "RoleMatch",
            "Recommends suitable open roles to candidates",
            "active",
            "approved",
            "internal",
            None,
            ["EU"],
            "Jon Bell",
            "2026-12-01 09:00:00+00",
            4,
        ),
        (
            "sys-other-secret",
            "Other Tenant System",
            "Must never be visible to Northstar",
            "active",
            "approved",
            "internal",
            None,
            ["EU"],
            "Other User",
            None,
            1,
        ),
    ]
    table = sa.table(
        "ai_systems",
        sa.column("id", sa.String),
        sa.column("organization_id", sa.String),
        sa.column("name", sa.String),
        sa.column("purpose", sa.Text),
        sa.column("lifecycle_status", sa.String),
        sa.column("release_status", sa.String),
        sa.column("provider_type", sa.String),
        sa.column("provider_name", sa.String),
        sa.column("jurisdictions", sa.JSON),
        sa.column("owner_name", sa.String),
        sa.column("next_review_at", sa.DateTime(timezone=True)),
        sa.column("assessment_version", sa.Integer),
    )
    op.bulk_insert(
        table,
        [
            dict(
                zip(
                    [column.name for column in table.columns],
                    (
                        system[0],
                        "org-other" if system[0] == "sys-other-secret" else "org-northstar",
                        *system[1:],
                    ),
                    strict=True,
                )
            )
            for system in systems
        ],
    )

    for table_name in ("memberships", "ai_systems", "idempotency_records", "audit_events"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            "USING (organization_id = current_setting('app.organization_id', true)) "
            "WITH CHECK (organization_id = current_setting('app.organization_id', true))"
        )
    op.execute("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organizations FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY organization_isolation ON organizations "
        "USING (id = current_setting('app.organization_id', true))"
    )
    op.execute("CREATE RULE audit_events_no_update AS ON UPDATE TO audit_events DO INSTEAD NOTHING")
    op.execute("CREATE RULE audit_events_no_delete AS ON DELETE TO audit_events DO INSTEAD NOTHING")
    op.execute("GRANT USAGE ON SCHEMA public TO fairhire_app")
    op.execute("GRANT SELECT ON organizations, memberships TO fairhire_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON ai_systems TO fairhire_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON idempotency_records TO fairhire_app")
    op.execute("GRANT SELECT, INSERT ON audit_events TO fairhire_app")


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("idempotency_records")
    op.drop_table("ai_systems")
    op.drop_table("memberships")
    op.drop_table("organizations")
