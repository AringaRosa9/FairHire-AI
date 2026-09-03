from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[str] = mapped_column(String(24), nullable=False, default="eu")
    policy_pack: Mapped[str] = mapped_column(String(100), nullable=False)
    retention_policy: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    organization: Mapped[Organization] = relationship()


class AISystem(Base):
    __tablename__ = "ai_systems"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    actual_use: Mapped[str | None] = mapped_column(Text)
    affected_people: Mapped[str | None] = mapped_column(Text)
    decision_impact: Mapped[str | None] = mapped_column(String(40))
    human_oversight: Mapped[str | None] = mapped_column(Text)
    organization_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    profiling: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    solely_automated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lifecycle_status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    release_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    provider_type: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(200))
    jurisdictions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    owner_name: Mapped[str] = mapped_column(String(160), nullable=False)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assessment_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RegulatoryAssessment(Base):
    __tablename__ = "regulatory_assessments"
    __table_args__ = (UniqueConstraint("organization_id", "ai_system_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    ai_system_id: Mapped[str] = mapped_column(ForeignKey("ai_systems.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_pack_version: Mapped[str] = mapped_column(String(100), nullable=False)
    organization_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    answers: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    risk_class: Mapped[str] = mapped_column(String(40), nullable=False)
    high_risk: Mapped[bool] = mapped_column(Boolean, nullable=False)
    prohibited_practice_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    legal_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    basis_links: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    answered_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("organization_id", "ai_system_id", "version_label"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    ai_system_id: Mapped[str] = mapped_column(ForeignKey("ai_systems.id"), index=True)
    version_label: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    framework: Mapped[str | None] = mapped_column(String(100))
    artifact_ref: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    input_schema: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    release_state: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OnboardingDraft(Base):
    __tablename__ = "onboarding_drafts"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    ai_system_id: Mapped[str] = mapped_column(ForeignKey("ai_systems.id"), index=True)
    model_version_id: Mapped[str | None] = mapped_column(ForeignKey("model_versions.id"))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(700), nullable=False, unique=True)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expected_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    upload_status: Mapped[str] = mapped_column(String(24), nullable=False, default="initiated")
    scan_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    inferred_schema: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    row_count: Mapped[int | None] = mapped_column(BigInteger)
    missing_rates: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False, default=dict)
    time_range_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    time_range_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str | None] = mapped_column(Text)
    collection_purpose: Mapped[str | None] = mapped_column(Text)
    lawful_basis_ref: Mapped[str | None] = mapped_column(Text)
    sensitive_attribute_necessity: Mapped[str | None] = mapped_column(Text)
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class DatasetField(Base):
    __tablename__ = "dataset_fields"
    __table_args__ = (UniqueConstraint("organization_id", "dataset_id", "name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    inferred_type: Mapped[str] = mapped_column(String(32), nullable=False)
    nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    missing_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    role: Mapped[str | None] = mapped_column(String(32))
    vault_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmed_by: Mapped[str | None] = mapped_column(String(200))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditRun(Base):
    __tablename__ = "audit_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    ai_system_id: Mapped[str] = mapped_column(ForeignKey("ai_systems.id"), index=True)
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"), index=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    policy_pack_version: Mapped[str] = mapped_column(String(100), nullable=False)
    config_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    data_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    job_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(Text)
    submitted_by: Mapped[str] = mapped_column(String(200), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BackgroundJob(Base):
    __tablename__ = "background_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    task_name: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(Text)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("organization_id", "key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_code: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
