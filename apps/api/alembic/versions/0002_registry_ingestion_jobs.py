"""Add registry, ingestion, audit-run, and background-job resources."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_registry_ingestion_jobs"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "regulatory_assessments",
    "model_versions",
    "onboarding_drafts",
    "datasets",
    "dataset_fields",
    "audit_runs",
    "background_jobs",
)


def _tenant_table(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table_name} "
        "USING (organization_id = current_setting('app.organization_id', true)) "
        "WITH CHECK (organization_id = current_setting('app.organization_id', true))"
    )


def upgrade() -> None:
    op.add_column("ai_systems", sa.Column("actual_use", sa.Text()))
    op.add_column("ai_systems", sa.Column("affected_people", sa.Text()))
    op.add_column("ai_systems", sa.Column("decision_impact", sa.String(40)))
    op.add_column("ai_systems", sa.Column("human_oversight", sa.Text()))
    op.add_column(
        "ai_systems",
        sa.Column("organization_roles", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "ai_systems",
        sa.Column("profiling", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "ai_systems",
        sa.Column("solely_automated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "regulatory_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("ai_system_id", sa.String(36), sa.ForeignKey("ai_systems.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rule_pack_version", sa.String(100), nullable=False),
        sa.Column("organization_roles", sa.JSON(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("risk_class", sa.String(40), nullable=False),
        sa.Column("high_risk", sa.Boolean(), nullable=False),
        sa.Column("prohibited_practice_flags", sa.JSON(), nullable=False),
        sa.Column("legal_review_required", sa.Boolean(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("basis_links", sa.JSON(), nullable=False),
        sa.Column("answered_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "ai_system_id", "version"),
    )
    op.create_index(
        "ix_regulatory_assessments_organization_id", "regulatory_assessments", ["organization_id"]
    )
    op.create_index(
        "ix_regulatory_assessments_ai_system_id", "regulatory_assessments", ["ai_system_id"]
    )
    op.create_table(
        "model_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("ai_system_id", sa.String(36), sa.ForeignKey("ai_systems.id"), nullable=False),
        sa.Column("version_label", sa.String(100), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("framework", sa.String(100)),
        sa.Column("artifact_ref", sa.Text()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("release_state", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "ai_system_id", "version_label"),
    )
    op.create_index("ix_model_versions_organization_id", "model_versions", ["organization_id"])
    op.create_index("ix_model_versions_ai_system_id", "model_versions", ["ai_system_id"])
    op.create_table(
        "onboarding_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id"),
    )
    op.create_index(
        "ix_onboarding_drafts_organization_id", "onboarding_drafts", ["organization_id"]
    )
    op.create_index("ix_onboarding_drafts_user_id", "onboarding_drafts", ["user_id"])
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("ai_system_id", sa.String(36), sa.ForeignKey("ai_systems.id"), nullable=False),
        sa.Column("model_version_id", sa.String(36), sa.ForeignKey("model_versions.id")),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("object_key", sa.String(700), nullable=False, unique=True),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("expected_hash", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("upload_status", sa.String(24), nullable=False),
        sa.Column("scan_status", sa.String(24), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("inferred_schema", sa.JSON(), nullable=False),
        sa.Column("row_count", sa.BigInteger()),
        sa.Column("missing_rates", sa.JSON(), nullable=False),
        sa.Column("time_range_start", sa.DateTime(timezone=True)),
        sa.Column("time_range_end", sa.DateTime(timezone=True)),
        sa.Column("source", sa.Text()),
        sa.Column("collection_purpose", sa.Text()),
        sa.Column("lawful_basis_ref", sa.Text()),
        sa.Column("sensitive_attribute_necessity", sa.Text()),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_datasets_organization_id", "datasets", ["organization_id"])
    op.create_index("ix_datasets_ai_system_id", "datasets", ["ai_system_id"])
    op.create_table(
        "dataset_fields",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("inferred_type", sa.String(32), nullable=False),
        sa.Column("nullable", sa.Boolean(), nullable=False),
        sa.Column("missing_rate", sa.Float(), nullable=False),
        sa.Column("role", sa.String(32)),
        sa.Column("vault_only", sa.Boolean(), nullable=False),
        sa.Column("confirmed_by", sa.String(200)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "dataset_id", "name"),
    )
    op.create_index("ix_dataset_fields_organization_id", "dataset_fields", ["organization_id"])
    op.create_index("ix_dataset_fields_dataset_id", "dataset_fields", ["dataset_id"])
    op.create_table(
        "audit_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("ai_system_id", sa.String(36), sa.ForeignKey("ai_systems.id"), nullable=False),
        sa.Column(
            "model_version_id", sa.String(36), sa.ForeignKey("model_versions.id"), nullable=False
        ),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column("policy_pack_version", sa.String(100), nullable=False),
        sa.Column("config_snapshot", sa.JSON(), nullable=False),
        sa.Column("data_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False, unique=True),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_detail", sa.Text()),
        sa.Column("submitted_by", sa.String(200), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_audit_runs_organization_id", "audit_runs", ["organization_id"])
    op.create_index("ix_audit_runs_ai_system_id", "audit_runs", ["ai_system_id"])
    op.create_index("ix_audit_runs_model_version_id", "audit_runs", ["model_version_id"])
    op.create_index("ix_audit_runs_dataset_id", "audit_runs", ["dataset_id"])
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("task_name", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_detail", sa.Text()),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_background_jobs_organization_id", "background_jobs", ["organization_id"])

    for table_name in TENANT_TABLES:
        _tenant_table(table_name)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON regulatory_assessments, model_versions, "
        "onboarding_drafts, datasets, dataset_fields, audit_runs, background_jobs TO fairhire_app"
    )


def downgrade() -> None:
    for table_name in reversed(TENANT_TABLES):
        op.drop_table(table_name)
    for column in (
        "solely_automated",
        "profiling",
        "organization_roles",
        "human_oversight",
        "decision_impact",
        "affected_people",
        "actual_use",
    ):
        op.drop_column("ai_systems", column)
