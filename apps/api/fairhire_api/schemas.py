from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from fairhire_domain.access import Role
from fairhire_domain.data_contract import FieldRole
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
    code: str | None = None


class Pagination(BaseModel):
    page: int = 1
    page_size: int = 25
    total: int


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    poll_url: str
    submitted_at: datetime


class SessionResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    organization_id: str
    organization_name: str
    role: Role
    permissions: list[str]


class PolicyPackUpdate(BaseModel):
    version: Annotated[str, Field(min_length=3, max_length=100)]
    expires_at: datetime
    reason: Annotated[str, Field(min_length=10, max_length=2000)]


class OrganizationPolicyResponse(BaseModel):
    organization_id: str
    version: str
    expires_at: datetime


class AISystemBase(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=200)]
    purpose: Annotated[str, Field(min_length=10, max_length=4000)]
    actual_use: Annotated[str | None, Field(max_length=4000)] = None
    affected_people: Annotated[str | None, Field(max_length=4000)] = None
    decision_impact: (
        Literal["screening", "ranking", "recommendation", "employment_decision", "support_only"]
        | None
    ) = None
    human_oversight: Annotated[str | None, Field(max_length=4000)] = None
    organization_roles: list[Literal["provider", "deployer", "importer", "distributor"]] = []
    profiling: bool = False
    solely_automated: bool = False
    lifecycle_status: Literal["draft", "trial", "active", "retired"] = "draft"
    release_status: Literal[
        "approved", "review_required", "blocked", "draft", "insufficient_evidence"
    ] = "draft"
    provider_type: Literal["internal", "third_party"]
    provider_name: str | None = None
    jurisdictions: Annotated[list[str], Field(min_length=1)]
    owner_name: Annotated[str, Field(min_length=2, max_length=160)]
    next_review_at: datetime | None = None


class AISystemCreate(AISystemBase):
    pass


class AISystemResponse(AISystemBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    assessment_version: int


class AISystemListResponse(Pagination):
    items: list[AISystemResponse]


class AssessmentCreate(BaseModel):
    organization_roles: Annotated[
        list[Literal["provider", "deployer", "importer", "distributor"]], Field(min_length=1)
    ]
    employment_use: bool
    uses_emotion_inference: bool = False
    uses_sensitive_trait_inference: bool = False
    safety_component: bool = False
    exception_claimed: bool = False
    exception_justification: Annotated[str | None, Field(max_length=4000)] = None
    notes: Annotated[str | None, Field(max_length=4000)] = None


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    ai_system_id: str
    version: int
    rule_pack_version: str
    organization_roles: list[str]
    answers: dict[str, object]
    risk_class: str
    high_risk: bool
    prohibited_practice_flags: list[str]
    legal_review_required: bool
    rationale: str
    basis_links: list[str]
    answered_by: str
    created_at: datetime


class ModelVersionCreate(BaseModel):
    version_label: Annotated[str, Field(min_length=1, max_length=100)]
    source_type: Literal["internal", "third_party", "prediction_output", "endpoint"]
    framework: Annotated[str | None, Field(max_length=100)] = None
    artifact_ref: Annotated[str | None, Field(max_length=2000)] = None
    content_hash: Annotated[str | None, Field(pattern=r"^[a-fA-F0-9]{64}$")] = None
    input_schema: dict[str, object] = {}
    release_state: Literal["draft", "trial", "approved", "retired"] = "draft"


class ModelVersionResponse(ModelVersionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    ai_system_id: str
    created_by: str
    created_at: datetime


class DraftUpdate(BaseModel):
    current_step: Annotated[int, Field(ge=1, le=5)]
    state: dict[str, object]


class DraftResponse(DraftUpdate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    user_id: str
    updated_at: datetime


class DatasetFieldInferred(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    inferred_type: Literal["string", "integer", "number", "boolean", "date", "datetime", "category"]
    nullable: bool = False
    missing_rate: Annotated[float, Field(ge=0, le=1)] = 0


class UploadInitiate(BaseModel):
    ai_system_id: str
    model_version_id: str | None = None
    filename: Annotated[str, Field(min_length=1, max_length=255)]
    content_type: Annotated[str, Field(min_length=1, max_length=120)]
    size_bytes: Annotated[int, Field(gt=0, le=5_000_000_000)]
    sha256: Annotated[str, Field(pattern=r"^[a-fA-F0-9]{64}$")]


class UploadInitiateResponse(BaseModel):
    dataset_id: str
    object_key: str
    upload_url: str
    upload_headers: dict[str, str]
    expires_at: datetime
    status: str


class UploadComplete(BaseModel):
    content_hash: Annotated[str, Field(pattern=r"^[a-fA-F0-9]{64}$")]
    scanner_reference: Annotated[str, Field(min_length=3, max_length=200)]
    scan_status: Literal["clean", "rejected"]
    row_count: Annotated[int, Field(gt=0)]
    inferred_fields: Annotated[list[DatasetFieldInferred], Field(min_length=1)]
    time_range_start: datetime | None = None
    time_range_end: datetime | None = None


class DatasetFieldResponse(DatasetFieldInferred):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: FieldRole | None
    vault_only: bool
    confirmed_by: str | None
    confirmed_at: datetime | None


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    ai_system_id: str
    model_version_id: str | None
    filename: str
    object_key: str
    format: str
    content_type: str
    size_bytes: int
    expected_hash: str
    content_hash: str | None
    upload_status: str
    scan_status: str
    schema_version: int
    row_count: int | None
    time_range_start: datetime | None
    time_range_end: datetime | None
    source: str | None
    collection_purpose: str | None
    lawful_basis_ref: str | None
    sensitive_attribute_necessity: str | None
    retention_expires_at: datetime | None
    fields: list[DatasetFieldResponse] = []


class FieldMapping(BaseModel):
    field_id: str
    role: FieldRole
    vault_only: bool = False


class FieldMappingsCreate(BaseModel):
    mappings: Annotated[list[FieldMapping], Field(min_length=3)]
    source: Annotated[str, Field(min_length=3, max_length=4000)]
    collection_purpose: Annotated[str, Field(min_length=3, max_length=4000)]
    lawful_basis_ref: Annotated[str, Field(min_length=3, max_length=4000)]
    sensitive_attribute_necessity: Annotated[str | None, Field(max_length=4000)] = None
    retention_expires_at: datetime


class AuditRunCreate(BaseModel):
    ai_system_id: str
    model_version_id: str
    dataset_id: str
    baseline_run_id: str | None = None
    baseline_change_reason: Annotated[str | None, Field(max_length=2000)] = None
    baseline_approval_ref: Annotated[str | None, Field(max_length=300)] = None
    policy_pack_version: Annotated[str, Field(min_length=3, max_length=100)]
    data_window_start: datetime | None = None
    data_window_end: datetime | None = None
    config: dict[str, object] = {}

    @model_validator(mode="after")
    def require_baseline_governance(self) -> "AuditRunCreate":
        if self.baseline_run_id and (
            not self.baseline_change_reason
            or len(self.baseline_change_reason.strip()) < 10
            or not self.baseline_approval_ref
        ):
            raise ValueError(
                "baseline_change_reason and baseline_approval_ref are required "
                "when selecting a baseline"
            )
        if not self.baseline_run_id and (self.baseline_change_reason or self.baseline_approval_ref):
            raise ValueError("baseline governance metadata requires baseline_run_id")
        return self


class AuditRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    ai_system_id: str
    model_version_id: str
    dataset_id: str
    baseline_run_id: str | None
    config_version: int
    policy_pack_version: str
    config_snapshot: dict[str, object]
    data_fingerprint: str
    status: JobStatus
    job_id: str
    error_code: str | None
    error_detail: str | None
    submitted_by: str
    submitted_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class MetricResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    audit_run_id: str
    category: Literal[
        "data_quality", "fairness", "proxy", "counterfactual", "explainability", "drift"
    ]
    metric_key: str
    protected_attribute: str | None
    reference_group: str | None
    comparison_group: str | None
    value: float | None
    lower_bound: float | None
    upper_bound: float | None
    status: Literal["pass", "review_required", "insufficient_evidence", "warning", "critical"]
    threshold: float | None
    threshold_operator: str | None
    threshold_source: dict[str, object]
    raw_counts: dict[str, object]
    method: str
    calculation_version: str
    details: dict[str, object]
    created_at: datetime


class AuditMetricSummary(BaseModel):
    audit_run_id: str
    calculation_version: str | None
    status_counts: dict[str, int]
    evidence_gaps: list[str]
    items: list[MetricResultResponse]


class MetricComparison(BaseModel):
    category: str
    metric_key: str
    protected_attribute: str | None
    comparison_group: str | None
    baseline_value: float | None
    current_value: float | None
    delta: float | None
    baseline_status: str
    current_status: str


class AuditComparisonResponse(BaseModel):
    current_run_id: str
    baseline_run_id: str
    current_model_version_id: str
    baseline_model_version_id: str
    current_data_fingerprint: str
    baseline_data_fingerprint: str
    baseline_change_reason: str
    baseline_approval_ref: str
    items: list[MetricComparison]


FindingStatus = Literal["open", "triaged", "mitigating", "ready_for_retest", "resolved", "accepted"]
FindingSeverity = Literal["critical", "high", "medium", "low"]


class FindingCreate(BaseModel):
    ai_system_id: str
    audit_run_id: str | None = None
    source_metric_id: str | None = None
    title: Annotated[str, Field(min_length=3, max_length=240)]
    description: Annotated[str, Field(min_length=10, max_length=8000)]
    severity: FindingSeverity
    confidence: Literal["high", "medium", "low"]
    affected_groups: list[str] = []
    evidence_refs: Annotated[list[str], Field(min_length=1)]
    control_refs: list[str] = []
    recommended_control: Annotated[str | None, Field(max_length=4000)] = None
    owner_id: Annotated[str, Field(min_length=2, max_length=200)]
    owner_name: Annotated[str, Field(min_length=2, max_length=160)]
    due_at: datetime


class FindingResponse(FindingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    status: FindingStatus
    residual_risk: str | None
    acceptance_reason: str | None
    accepted_by: str | None
    accepted_at: datetime | None
    accepted_until: datetime | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class FindingListResponse(Pagination):
    items: list[FindingResponse]


class FindingTransition(BaseModel):
    status: FindingStatus
    reason: Annotated[str, Field(min_length=5, max_length=2000)]


class RiskAcceptanceCreate(BaseModel):
    residual_risk: Annotated[str, Field(min_length=10, max_length=4000)]
    reason: Annotated[str, Field(min_length=10, max_length=4000)]
    expires_at: datetime


class RemediationTaskCreate(BaseModel):
    title: Annotated[str, Field(min_length=3, max_length=240)]
    description: Annotated[str | None, Field(max_length=4000)] = None
    owner_id: Annotated[str, Field(min_length=2, max_length=200)]
    owner_name: Annotated[str, Field(min_length=2, max_length=160)]
    due_at: datetime


class RemediationTaskResponse(RemediationTaskCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    finding_id: str
    status: Literal["open", "in_progress", "completed", "cancelled"]
    evidence_refs: list[str]
    completed_at: datetime | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class RemediationTaskListResponse(Pagination):
    items: list[RemediationTaskResponse]


class RemediationTaskUpdate(BaseModel):
    status: Literal["open", "in_progress", "completed", "cancelled"]
    reason: Annotated[str, Field(min_length=5, max_length=2000)]
    evidence_refs: list[str] = []


class FindingRetestCreate(BaseModel):
    audit_run_id: str
    outcome: Literal["resolved", "improved", "persisted", "regressed"]
    notes: Annotated[str, Field(min_length=10, max_length=4000)]


class FindingRetestResponse(FindingRetestCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    finding_id: str
    performed_by: str
    performed_at: datetime


class FindingDetailResponse(FindingResponse):
    tasks: list[RemediationTaskResponse]
    retests: list[FindingRetestResponse]


class ApprovalChainCreate(BaseModel):
    reason: Annotated[str, Field(min_length=5, max_length=2000)]


class ApprovalDecisionCreate(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: Annotated[str, Field(min_length=5, max_length=4000)]
    expires_at: datetime | None = None


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    ai_system_id: str
    chain_version: int
    stage: Literal["responsible_ai", "hr", "legal_dpo"]
    sequence: int
    decision: Literal["pending", "approved", "rejected", "expired"]
    approver_id: str | None
    approver_name: str | None
    reason: str | None
    decided_at: datetime | None
    expires_at: datetime | None
    created_by: str
    created_at: datetime


class ApprovalListResponse(Pagination):
    items: list[ApprovalResponse]


class ApprovalChainResponse(BaseModel):
    ai_system_id: str
    chain_version: int
    items: list[ApprovalResponse]


class ReleaseGateBlocker(BaseModel):
    code: str
    message: str
    resource_id: str | None = None


class ReleaseGateResponse(BaseModel):
    ai_system_id: str
    status: Literal["approved", "review_required", "blocked"]
    chain_version: int | None
    required_stages: list[str]
    approved_stages: list[str]
    blockers: list[ReleaseGateBlocker]
    evaluated_at: datetime


class BackgroundJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    task_name: str
    resource_type: str
    resource_id: str
    status: JobStatus
    attempt: int
    max_attempts: int
    progress: int
    error_code: str | None
    error_detail: str | None
    cancellation_requested: bool
    submitted_at: datetime
    updated_at: datetime


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    payload: dict[str, object]
    previous_hash: str | None
    current_hash: str
    occurred_at: datetime


class AuditEventListResponse(Pagination):
    items: list[AuditEventResponse]


class LedgerVerificationResponse(BaseModel):
    valid: bool
    checked_events: int
    broken_event_id: str | None = None


class PortfolioSummary(BaseModel):
    total_systems: int
    release_counts: dict[str, int]
    ready_datasets: int
    active_audit_runs: int
    failed_jobs: int
    open_findings: int
    overdue_tasks: int
    pending_approvals: int
    critical_blockers: int


ReportStatus = Literal["draft", "approved", "superseded"]


class ReportCreate(BaseModel):
    ai_system_id: str
    audit_run_id: str
    title: Annotated[str | None, Field(min_length=3, max_length=240)] = None


class ReportSection(BaseModel):
    key: Literal[
        "executive_summary",
        "fairness",
        "explainability",
        "model_system_card",
        "risk_assessment",
        "audit_log",
        "evidence_gap",
    ]
    title: str
    summary: str
    items: list[dict[str, object]] = []


class EvidenceTrace(BaseModel):
    reference: str
    audit_run_id: str
    metric_result_id: str | None = None
    label: str
    value: float | None = None
    method: str | None = None
    calculation_version: str | None = None


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    ai_system_id: str
    audit_run_id: str
    previous_report_id: str | None
    version: int
    title: str
    status: ReportStatus
    policy_pack_version: str
    sections: list[ReportSection]
    evidence_index: list[EvidenceTrace]
    evidence_gaps: list[str]
    content_hash: str
    created_by: str
    approved_by: str | None
    approved_at: datetime | None
    superseded_at: datetime | None
    created_at: datetime


class ReportListResponse(Pagination):
    items: list[ReportResponse]


class ReportApprovalCreate(BaseModel):
    reason: Annotated[str, Field(min_length=5, max_length=4000)]


class ReportDifference(BaseModel):
    path: str
    before: object | None = None
    after: object | None = None


class ReportDiffResponse(BaseModel):
    report_id: str
    compared_report_id: str
    changes: list[ReportDifference]


class KnowledgeSourceCreate(BaseModel):
    source_key: Annotated[str, Field(min_length=2, max_length=120)]
    source_type: Literal["official", "organization_policy"]
    title: Annotated[str, Field(min_length=3, max_length=300)]
    publisher: Annotated[str, Field(min_length=2, max_length=200)]
    uri: Annotated[str, Field(min_length=8, max_length=2000)]
    jurisdiction: Annotated[str | None, Field(max_length=80)] = None
    version: Annotated[str, Field(min_length=1, max_length=80)]
    effective_at: datetime
    reviewed_at: datetime
    content: Annotated[str, Field(min_length=20, max_length=100_000)]
    allowed_roles: list[Role] = []
    active: bool = True


class KnowledgeSourceResponse(KnowledgeSourceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    content_hash: str
    created_by: str
    created_at: datetime


class KnowledgeSourceListResponse(Pagination):
    items: list[KnowledgeSourceResponse]


class AssistantAnswerCreate(BaseModel):
    question: Annotated[str, Field(min_length=3, max_length=4000)]
    ai_system_id: str | None = None


class AssistantParagraph(BaseModel):
    classification: Literal["fact", "inference", "recommendation"]
    text: str
    citation_ids: list[str]


class AssistantCitation(BaseModel):
    id: str
    source_type: Literal["official", "organization_policy", "project_evidence"]
    title: str
    locator: str
    uri: str | None = None
    effective_at: datetime | None = None


class RuleDate(BaseModel):
    source_id: str
    version: str
    effective_at: datetime
    reviewed_at: datetime


class AssistantAnswerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    ai_system_id: str | None
    question: str
    paragraphs: list[AssistantParagraph]
    citations: list[AssistantCitation]
    rule_dates: list[RuleDate]
    evidence_refs: list[str]
    injection_detected: bool
    created_by: str
    created_at: datetime


class AssistantAnswerListResponse(Pagination):
    items: list[AssistantAnswerResponse]
