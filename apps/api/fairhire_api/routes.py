import hashlib
import hmac
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from fairhire_domain.access import Permission
from fairhire_domain.audit import validate_audit_config
from fairhire_domain.data_contract import FieldRole
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import __version__
from .config import Settings, get_settings
from .db import get_db
from .ids import new_id
from .jobs import dispatch_job, revoke_job
from .ledger import append_event, verify_chain
from .models import (
    AISystem,
    AuditEvent,
    AuditRun,
    BackgroundJob,
    Dataset,
    DatasetField,
    IdempotencyRecord,
    MetricResult,
    ModelVersion,
    OnboardingDraft,
    Organization,
    RegulatoryAssessment,
)
from .schemas import (
    AISystemCreate,
    AISystemListResponse,
    AISystemResponse,
    AssessmentCreate,
    AssessmentResponse,
    AuditEventListResponse,
    AuditEventResponse,
    AuditMetricSummary,
    AuditRunCreate,
    AuditRunResponse,
    BackgroundJobResponse,
    DatasetFieldResponse,
    DatasetResponse,
    DraftResponse,
    DraftUpdate,
    FieldMappingsCreate,
    LedgerVerificationResponse,
    MetricResultResponse,
    ModelVersionCreate,
    ModelVersionResponse,
    PortfolioSummary,
    SessionResponse,
    UploadComplete,
    UploadInitiate,
    UploadInitiateResponse,
)
from .security import Principal, get_principal, require_idempotency_key, require_permission
from .storage import presign_upload

router = APIRouter(prefix="/v1")
ALLOWED_FORMATS = {".csv": "csv", ".parquet": "parquet", ".jsonl": "jsonl"}
UNSAFE_FORMATS = {".pkl", ".pickle", ".joblib"}


class EmptyCommand(BaseModel):
    pass


def _request_hash(action: str, payload: BaseModel) -> str:
    body = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{action}:{body}".encode()).hexdigest()


def _replay[ResponseModel: BaseModel](
    db: Session,
    organization_id: str,
    key: str,
    action: str,
    payload: BaseModel,
    response_model: type[ResponseModel],
) -> ResponseModel | None:
    record = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.organization_id == organization_id,
            IdempotencyRecord.key == key,
        )
    )
    if not record:
        return None
    if record.request_hash != _request_hash(action, payload):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Idempotency-Key was reused for another request"
        )
    if record.response_body is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The original request is still being processed"
        )
    return response_model.model_validate(record.response_body)


def _record_response(
    db: Session,
    organization_id: str,
    key: str,
    action: str,
    payload: BaseModel,
    response: BaseModel,
    response_code: int,
) -> None:
    db.add(
        IdempotencyRecord(
            id=new_id("idem"),
            organization_id=organization_id,
            key=key,
            request_hash=_request_hash(action, payload),
            response_code=response_code,
            response_body=response.model_dump(mode="json"),
        )
    )


def _owned(db: Session, model: Any, resource_id: str, organization_id: str) -> Any:
    resource = db.scalar(
        select(model).where(model.id == resource_id, model.organization_id == organization_id)
    )
    if not resource:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found")
    return resource


def _dataset_response(db: Session, dataset: Dataset) -> DatasetResponse:
    fields = db.scalars(
        select(DatasetField)
        .where(
            DatasetField.dataset_id == dataset.id,
            DatasetField.organization_id == dataset.organization_id,
        )
        .order_by(DatasetField.name)
    ).all()
    return DatasetResponse(
        **DatasetResponse.model_validate(dataset).model_dump(exclude={"fields"}),
        fields=[DatasetFieldResponse.model_validate(field) for field in fields],
    )


@router.get("/health", tags=["platform"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/session", response_model=SessionResponse, tags=["identity"])
def session(principal: Annotated[Principal, Depends(get_principal)]) -> SessionResponse:
    return SessionResponse(
        user_id=principal.user_id,
        email=principal.email,
        display_name=principal.display_name,
        organization_id=principal.organization_id,
        organization_name=principal.organization_name,
        role=principal.role,
        permissions=sorted(permission.value for permission in principal.permissions),
    )


@router.get("/portfolio", response_model=PortfolioSummary, tags=["portfolio"])
def portfolio(
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> PortfolioSummary:
    release_rows = db.execute(
        select(AISystem.release_status, func.count())
        .where(AISystem.organization_id == principal.organization_id)
        .group_by(AISystem.release_status)
    ).all()
    return PortfolioSummary(
        total_systems=sum(row[1] for row in release_rows),
        release_counts={row[0]: row[1] for row in release_rows},
        ready_datasets=db.scalar(
            select(func.count())
            .select_from(Dataset)
            .where(
                Dataset.organization_id == principal.organization_id,
                Dataset.upload_status == "ready",
            )
        )
        or 0,
        active_audit_runs=db.scalar(
            select(func.count())
            .select_from(AuditRun)
            .where(
                AuditRun.organization_id == principal.organization_id,
                AuditRun.status.in_(["queued", "running", "cancelling"]),
            )
        )
        or 0,
        failed_jobs=db.scalar(
            select(func.count())
            .select_from(BackgroundJob)
            .where(
                BackgroundJob.organization_id == principal.organization_id,
                BackgroundJob.status == "failed",
            )
        )
        or 0,
    )


@router.get("/ai-systems", response_model=AISystemListResponse, tags=["registry"])
def list_ai_systems(
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_READ))],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> AISystemListResponse:
    predicate = AISystem.organization_id == principal.organization_id
    total = db.scalar(select(func.count()).select_from(AISystem).where(predicate)) or 0
    systems = db.scalars(
        select(AISystem)
        .where(predicate)
        .order_by(AISystem.next_review_at.asc().nullslast(), AISystem.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AISystemListResponse(
        items=[AISystemResponse.model_validate(system) for system in systems],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/ai-systems/{system_id}", response_model=AISystemResponse, tags=["registry"])
def get_ai_system(
    system_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> AISystemResponse:
    return AISystemResponse.model_validate(
        _owned(db, AISystem, system_id, principal.organization_id)
    )


@router.post(
    "/ai-systems",
    response_model=AISystemResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["registry"],
)
def create_ai_system(
    payload: AISystemCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_WRITE))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> AISystemResponse:
    if replay := _replay(
        db,
        principal.organization_id,
        idempotency_key,
        "create_ai_system",
        payload,
        AISystemResponse,
    ):
        return replay
    system = AISystem(
        id=new_id("sys"),
        organization_id=principal.organization_id,
        assessment_version=0,
        **payload.model_dump(),
    )
    db.add(system)
    db.flush()
    response = AISystemResponse.model_validate(system)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="ai_system.created",
        resource_type="ai_system",
        resource_id=system.id,
        payload={"name": system.name, "release_status": system.release_status},
    )
    _record_response(
        db, principal.organization_id, idempotency_key, "create_ai_system", payload, response, 201
    )
    db.commit()
    return response


@router.post(
    "/ai-systems/{system_id}/assessments",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["registry"],
)
def create_assessment(
    system_id: str,
    payload: AssessmentCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_WRITE))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> AssessmentResponse:
    action = f"create_assessment:{system_id}"
    if replay := _replay(
        db, principal.organization_id, idempotency_key, action, payload, AssessmentResponse
    ):
        return replay
    system: AISystem = _owned(db, AISystem, system_id, principal.organization_id)
    if not system.purpose or not system.jurisdictions or not system.decision_impact:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Intended purpose, jurisdictions and decision impact are required before assessment",
        )
    organization = db.get(Organization, principal.organization_id)
    if not organization:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    flags = []
    if payload.uses_emotion_inference:
        flags.append("workplace_emotion_inference")
    if payload.uses_sensitive_trait_inference:
        flags.append("sensitive_trait_inference")
    high_risk = payload.employment_use and system.decision_impact != "support_only"
    risk_class = "prohibited_practice_review" if flags else "high_risk" if high_risk else "limited"
    version = (
        db.scalar(
            select(func.max(RegulatoryAssessment.version)).where(
                RegulatoryAssessment.organization_id == principal.organization_id,
                RegulatoryAssessment.ai_system_id == system_id,
            )
        )
        or 0
    ) + 1
    assessment = RegulatoryAssessment(
        id=new_id("asm"),
        organization_id=principal.organization_id,
        ai_system_id=system_id,
        version=version,
        rule_pack_version=organization.policy_pack,
        organization_roles=list(payload.organization_roles),
        answers=payload.model_dump(mode="json"),
        risk_class=risk_class,
        high_risk=high_risk,
        prohibited_practice_flags=flags,
        legal_review_required=True,
        rationale=(
            "Employment decision support is likely within the high-risk category; legal review "
            "must "
            "confirm the facts and any claimed exception."
            if high_risk
            else "The current answers do not establish a high-risk classification; legal review "
            "is required."
        ),
        basis_links=[
            "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
            "https://eur-lex.europa.eu/eli/reg/2016/679/oj",
        ],
        answered_by=principal.user_id,
    )
    db.add(assessment)
    system.assessment_version = version
    system.organization_roles = list(payload.organization_roles)
    system.release_status = "blocked" if flags else "review_required"
    db.flush()
    response = AssessmentResponse.model_validate(assessment)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="assessment.version_created",
        resource_type="regulatory_assessment",
        resource_id=assessment.id,
        payload={"system_id": system_id, "version": version, "risk_class": risk_class},
    )
    _record_response(db, principal.organization_id, idempotency_key, action, payload, response, 201)
    db.commit()
    return response


@router.get(
    "/ai-systems/{system_id}/assessments",
    response_model=list[AssessmentResponse],
    tags=["registry"],
)
def list_assessments(
    system_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> list[AssessmentResponse]:
    _owned(db, AISystem, system_id, principal.organization_id)
    assessments = db.scalars(
        select(RegulatoryAssessment)
        .where(
            RegulatoryAssessment.organization_id == principal.organization_id,
            RegulatoryAssessment.ai_system_id == system_id,
        )
        .order_by(RegulatoryAssessment.version.desc())
    ).all()
    return [AssessmentResponse.model_validate(item) for item in assessments]


@router.post(
    "/ai-systems/{system_id}/model-versions",
    response_model=ModelVersionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["registry"],
)
def create_model_version(
    system_id: str,
    payload: ModelVersionCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_WRITE))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ModelVersionResponse:
    if payload.artifact_ref and Path(payload.artifact_ref).suffix.lower() in UNSAFE_FORMATS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Unsafe serialized models are not accepted; upload prediction outputs instead",
        )
    action = f"create_model_version:{system_id}"
    if replay := _replay(
        db, principal.organization_id, idempotency_key, action, payload, ModelVersionResponse
    ):
        return replay
    _owned(db, AISystem, system_id, principal.organization_id)
    model = ModelVersion(
        id=new_id("mdl"),
        organization_id=principal.organization_id,
        ai_system_id=system_id,
        created_by=principal.user_id,
        **payload.model_dump(),
    )
    db.add(model)
    db.flush()
    response = ModelVersionResponse.model_validate(model)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="model_version.created",
        resource_type="model_version",
        resource_id=model.id,
        payload={"system_id": system_id, "version_label": model.version_label},
    )
    _record_response(db, principal.organization_id, idempotency_key, action, payload, response, 201)
    db.commit()
    return response


@router.get(
    "/ai-systems/{system_id}/model-versions",
    response_model=list[ModelVersionResponse],
    tags=["registry"],
)
def list_model_versions(
    system_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> list[ModelVersionResponse]:
    _owned(db, AISystem, system_id, principal.organization_id)
    versions = db.scalars(
        select(ModelVersion)
        .where(
            ModelVersion.organization_id == principal.organization_id,
            ModelVersion.ai_system_id == system_id,
        )
        .order_by(ModelVersion.created_at.desc())
    ).all()
    return [ModelVersionResponse.model_validate(item) for item in versions]


@router.get("/onboarding-draft", response_model=DraftResponse | None, tags=["onboarding"])
def get_onboarding_draft(
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_WRITE))],
    db: Annotated[Session, Depends(get_db)],
) -> DraftResponse | None:
    draft = db.scalar(
        select(OnboardingDraft).where(
            OnboardingDraft.organization_id == principal.organization_id,
            OnboardingDraft.user_id == principal.user_id,
        )
    )
    return DraftResponse.model_validate(draft) if draft else None


@router.put("/onboarding-draft", response_model=DraftResponse, tags=["onboarding"])
def save_onboarding_draft(
    payload: DraftUpdate,
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_WRITE))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> DraftResponse:
    if replay := _replay(
        db,
        principal.organization_id,
        idempotency_key,
        "save_onboarding_draft",
        payload,
        DraftResponse,
    ):
        return replay
    draft = db.scalar(
        select(OnboardingDraft).where(
            OnboardingDraft.organization_id == principal.organization_id,
            OnboardingDraft.user_id == principal.user_id,
        )
    )
    if draft:
        draft.current_step = payload.current_step
        draft.state = payload.state
        draft.updated_at = datetime.now(UTC)
    else:
        draft = OnboardingDraft(
            id=new_id("draft"),
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            **payload.model_dump(),
        )
        db.add(draft)
    db.flush()
    response = DraftResponse.model_validate(draft)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="onboarding.draft_saved",
        resource_type="onboarding_draft",
        resource_id=draft.id,
        payload={"current_step": payload.current_step},
    )
    _record_response(
        db,
        principal.organization_id,
        idempotency_key,
        "save_onboarding_draft",
        payload,
        response,
        200,
    )
    db.commit()
    return response


@router.post(
    "/datasets/initiate-upload",
    response_model=UploadInitiateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["ingestion"],
)
def initiate_upload(
    payload: UploadInitiate,
    principal: Annotated[Principal, Depends(require_permission(Permission.DATASET_WRITE))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> UploadInitiateResponse:
    suffix = Path(payload.filename).suffix.lower()
    if suffix in UNSAFE_FORMATS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Pickle and Joblib are rejected; provide CSV, Parquet, or JSONL prediction outputs",
        )
    if suffix not in ALLOWED_FORMATS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Only CSV, Parquet, and JSONL are accepted"
        )
    if replay := _replay(
        db,
        principal.organization_id,
        idempotency_key,
        "initiate_upload",
        payload,
        UploadInitiateResponse,
    ):
        return replay
    _owned(db, AISystem, payload.ai_system_id, principal.organization_id)
    if payload.model_version_id:
        model: ModelVersion = _owned(
            db, ModelVersion, payload.model_version_id, principal.organization_id
        )
        if model.ai_system_id != payload.ai_system_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Model version belongs to another system"
            )
    dataset_id = new_id("data")
    safe_name = Path(payload.filename).name.replace(" ", "_")
    object_key = (
        f"{principal.organization_id}/systems/{payload.ai_system_id}/datasets/"
        f"{dataset_id}/{safe_name}"
    )
    dataset = Dataset(
        id=dataset_id,
        organization_id=principal.organization_id,
        ai_system_id=payload.ai_system_id,
        model_version_id=payload.model_version_id,
        filename=Path(payload.filename).name,
        object_key=object_key,
        format=ALLOWED_FORMATS[suffix],
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        expected_hash=payload.sha256.lower(),
        created_by=principal.user_id,
    )
    db.add(dataset)
    url, headers, expires_at = presign_upload(
        settings=settings,
        object_key=object_key,
        content_type=payload.content_type,
        checksum=payload.sha256.lower(),
    )
    response = UploadInitiateResponse(
        dataset_id=dataset_id,
        object_key=object_key,
        upload_url=url,
        upload_headers=headers,
        expires_at=expires_at,
        status="initiated",
    )
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="dataset.upload_initiated",
        resource_type="dataset",
        resource_id=dataset_id,
        payload={"filename": dataset.filename, "size_bytes": dataset.size_bytes},
    )
    _record_response(
        db, principal.organization_id, idempotency_key, "initiate_upload", payload, response, 201
    )
    db.commit()
    return response


@router.post(
    "/datasets/{dataset_id}/complete-upload",
    response_model=DatasetResponse,
    tags=["ingestion"],
)
def complete_upload(
    dataset_id: str,
    payload: UploadComplete,
    principal: Annotated[Principal, Depends(require_permission(Permission.DATASET_WRITE))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    scanner_attestation: Annotated[str | None, Header(alias="X-Scanner-Attestation")] = None,
) -> DatasetResponse:
    attestation_body = f"{dataset_id}:{payload.model_dump_json()}"
    expected_attestation = (
        hmac.new(
            settings.scanner_attestation_secret.encode(),
            attestation_body.encode(),
            hashlib.sha256,
        ).hexdigest()
        if settings.scanner_attestation_secret
        else None
    )
    development_attestation = settings.app_env in {
        "development",
        "test",
    } and payload.scanner_reference.startswith("development-scanner:")
    if not development_attestation and (
        not expected_attestation
        or not scanner_attestation
        or not hmac.compare_digest(scanner_attestation, expected_attestation)
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "A valid scanner attestation is required before ingestion can complete",
        )
    action = f"complete_upload:{dataset_id}"
    if replay := _replay(
        db,
        principal.organization_id,
        idempotency_key,
        action,
        payload,
        DatasetResponse,
    ):
        return replay
    dataset: Dataset = _owned(db, Dataset, dataset_id, principal.organization_id)
    if dataset.upload_status != "initiated":
        raise HTTPException(status.HTTP_409_CONFLICT, "Upload has already been completed")
    dataset.content_hash = payload.content_hash.lower()
    dataset.scan_status = payload.scan_status
    if dataset.content_hash != dataset.expected_hash or payload.scan_status == "rejected":
        dataset.upload_status = "rejected"
        append_event(
            db,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            action="dataset.upload_rejected",
            resource_type="dataset",
            resource_id=dataset.id,
            payload={
                "scanner_reference": payload.scanner_reference,
                "scan_status": payload.scan_status,
            },
        )
        db.commit()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Upload checksum mismatch or malware scan rejection",
        )
    dataset.upload_status = "mapped_pending"
    dataset.row_count = payload.row_count
    dataset.time_range_start = payload.time_range_start
    dataset.time_range_end = payload.time_range_end
    dataset.inferred_schema = [field.model_dump(mode="json") for field in payload.inferred_fields]
    for field in payload.inferred_fields:
        db.add(
            DatasetField(
                id=new_id("fld"),
                organization_id=principal.organization_id,
                dataset_id=dataset.id,
                name=field.name,
                inferred_type=field.inferred_type,
                nullable=field.nullable,
                missing_rate=field.missing_rate,
            )
        )
    db.flush()
    response = _dataset_response(db, dataset)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="dataset.scan_and_schema_completed",
        resource_type="dataset",
        resource_id=dataset.id,
        payload={
            "scanner_reference": payload.scanner_reference,
            "row_count": payload.row_count,
            "field_count": len(payload.inferred_fields),
        },
    )
    _record_response(
        db,
        principal.organization_id,
        idempotency_key,
        action,
        payload,
        response,
        200,
    )
    db.commit()
    return response


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse, tags=["ingestion"])
def get_dataset(
    dataset_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.DATASET_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> DatasetResponse:
    dataset = _owned(db, Dataset, dataset_id, principal.organization_id)
    return _dataset_response(db, dataset)


@router.post(
    "/datasets/{dataset_id}/field-mappings",
    response_model=DatasetResponse,
    tags=["ingestion"],
)
def save_field_mappings(
    dataset_id: str,
    payload: FieldMappingsCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.DATASET_WRITE))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> DatasetResponse:
    action = f"save_field_mappings:{dataset_id}"
    if replay := _replay(
        db,
        principal.organization_id,
        idempotency_key,
        action,
        payload,
        DatasetResponse,
    ):
        return replay
    dataset: Dataset = _owned(db, Dataset, dataset_id, principal.organization_id)
    fields = db.scalars(
        select(DatasetField).where(
            DatasetField.organization_id == principal.organization_id,
            DatasetField.dataset_id == dataset.id,
        )
    ).all()
    fields_by_id = {field.id: field for field in fields}
    if set(fields_by_id) != {mapping.field_id for mapping in payload.mappings}:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Every inferred field must be mapped exactly once",
        )
    roles = [mapping.role for mapping in payload.mappings]
    required_missing = (
        roles.count(FieldRole.IDENTIFIER) != 1
        or FieldRole.DECISION not in roles
        or FieldRole.TIMESTAMP not in roles
    )
    if required_missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Mappings require exactly one identifier, a decision, and a timestamp",
        )
    protected = [m for m in payload.mappings if m.role == FieldRole.PROTECTED_ATTRIBUTE]
    if protected and not payload.sensitive_attribute_necessity:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Sensitive attribute necessity is required for protected attributes",
        )
    for mapping in payload.mappings:
        if mapping.role == FieldRole.PROTECTED_ATTRIBUTE and not mapping.vault_only:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Protected attributes must remain vault-only",
            )
        field = fields_by_id[mapping.field_id]
        field.role = mapping.role.value
        field.vault_only = mapping.vault_only
        field.confirmed_by = principal.user_id
        field.confirmed_at = datetime.now(UTC)
    dataset.source = payload.source
    dataset.collection_purpose = payload.collection_purpose
    dataset.lawful_basis_ref = payload.lawful_basis_ref
    dataset.sensitive_attribute_necessity = payload.sensitive_attribute_necessity
    dataset.retention_expires_at = payload.retention_expires_at
    dataset.upload_status = "ready"
    db.flush()
    response = _dataset_response(db, dataset)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="dataset.field_mapping_confirmed",
        resource_type="dataset",
        resource_id=dataset.id,
        payload={
            "schema_version": dataset.schema_version,
            "roles": [role.value for role in roles],
        },
    )
    _record_response(
        db,
        principal.organization_id,
        idempotency_key,
        action,
        payload,
        response,
        200,
    )
    db.commit()
    return response


@router.post(
    "/audit-runs",
    response_model=AuditRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["audits"],
)
def create_audit_run(
    payload: AuditRunCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.AUDIT_RUN))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> AuditRunResponse:
    if replay := _replay(
        db,
        principal.organization_id,
        idempotency_key,
        "create_audit_run",
        payload,
        AuditRunResponse,
    ):
        return replay
    system: AISystem = _owned(db, AISystem, payload.ai_system_id, principal.organization_id)
    model: ModelVersion = _owned(
        db, ModelVersion, payload.model_version_id, principal.organization_id
    )
    dataset: Dataset = _owned(db, Dataset, payload.dataset_id, principal.organization_id)
    if model.ai_system_id != system.id or dataset.ai_system_id != system.id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "System, model, and dataset do not match"
        )
    if system.assessment_version < 1:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "A versioned applicability assessment is required",
        )
    if dataset.upload_status != "ready" or not dataset.content_hash:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Dataset upload and field mapping are incomplete",
        )
    run_id = new_id("run")
    job_id = new_id("job")
    mapped_fields = db.scalars(
        select(DatasetField).where(
            DatasetField.organization_id == principal.organization_id,
            DatasetField.dataset_id == dataset.id,
        )
    ).all()
    role_fields: dict[str, list[str]] = {}
    for field in mapped_fields:
        if field.role:
            role_fields.setdefault(field.role, []).append(field.name)
    audit_config = {
        "minimum_samples": 200,
        "hard_suppression_floor": 20,
        "minimum_time_coverage_days": 28,
        "bootstrap_iterations": 1000,
        "random_seed": 1729,
        "decision_positive_value": True,
        "label_positive_value": True,
        "demographic_parity_ratio_threshold": 0.8,
        "difference_threshold": 0.1,
        "threshold_source": {
            "source_type": "rule_pack",
            "source_id": payload.policy_pack_version,
            "version": payload.policy_pack_version,
            "approved_by": None,
            "legal_determination": False,
        },
        **payload.config,
        "identifier_field": role_fields[FieldRole.IDENTIFIER.value][0],
        "decision_field": role_fields[FieldRole.DECISION.value][0],
        "timestamp_field": role_fields[FieldRole.TIMESTAMP.value][0],
        "protected_attributes": role_fields.get(FieldRole.PROTECTED_ATTRIBUTE.value, []),
        "feature_fields": role_fields.get(FieldRole.FEATURE.value, []),
        "label_field": next(iter(role_fields.get(FieldRole.LABEL.value, [])), None),
        "score_field": next(iter(role_fields.get(FieldRole.PREDICTION.value, [])), None),
    }
    try:
        validate_audit_config(audit_config)
    except (TypeError, ValueError) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error
    fingerprint_source = ":".join(
        [
            dataset.content_hash,
            model.content_hash or model.version_label,
            json.dumps(audit_config, sort_keys=True),
        ]
    )
    run = AuditRun(
        id=run_id,
        organization_id=principal.organization_id,
        ai_system_id=system.id,
        model_version_id=model.id,
        dataset_id=dataset.id,
        policy_pack_version=payload.policy_pack_version,
        config_snapshot={
            **audit_config,
            "data_window_start": (
                payload.data_window_start.isoformat() if payload.data_window_start else None
            ),
            "data_window_end": (
                payload.data_window_end.isoformat() if payload.data_window_end else None
            ),
            "assessment_version": system.assessment_version,
        },
        data_fingerprint=hashlib.sha256(fingerprint_source.encode()).hexdigest(),
        status="queued",
        job_id=job_id,
        submitted_by=principal.user_id,
    )
    job = BackgroundJob(
        id=job_id,
        organization_id=principal.organization_id,
        task_name="audit.analyze",
        resource_type="audit_run",
        resource_id=run_id,
        status="queued",
    )
    db.add_all([run, job])
    db.flush()
    response = AuditRunResponse.model_validate(run)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="audit_run.queued",
        resource_type="audit_run",
        resource_id=run.id,
        payload={"job_id": job.id, "data_fingerprint": run.data_fingerprint},
    )
    _record_response(
        db,
        principal.organization_id,
        idempotency_key,
        "create_audit_run",
        payload,
        response,
        202,
    )
    db.commit()
    try:
        dispatch_job(
            settings,
            task_name="audit.analyze",
            job_id=job.id,
            kwargs={
                "organization_id": principal.organization_id,
                "audit_run_id": run.id,
                "dataset_id": dataset.id,
                "artifact_key": dataset.object_key,
                "dataset_format": dataset.format,
                "config": audit_config,
            },
        )
    except Exception as exc:
        job.status = "failed"
        job.error_code = "queue_unavailable"
        job.error_detail = str(exc)
        run.status = "failed"
        run.error_code = job.error_code
        run.error_detail = job.error_detail
        append_event(
            db,
            organization_id=principal.organization_id,
            actor_id="platform",
            action="job.dispatch_failed",
            resource_type="job",
            resource_id=job.id,
            payload={"error_code": job.error_code},
        )
        response = AuditRunResponse.model_validate(run)
        record = db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.organization_id == principal.organization_id,
                IdempotencyRecord.key == idempotency_key,
            )
        )
        if record:
            record.response_body = response.model_dump(mode="json")
        db.commit()
    return response


@router.get("/audit-runs/{run_id}", response_model=AuditRunResponse, tags=["audits"])
def get_audit_run(
    run_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> AuditRunResponse:
    return AuditRunResponse.model_validate(_owned(db, AuditRun, run_id, principal.organization_id))


@router.get(
    "/audit-runs/{run_id}/metrics",
    response_model=AuditMetricSummary,
    tags=["audits"],
)
def get_audit_metrics(
    run_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_READ))],
    db: Annotated[Session, Depends(get_db)],
    category: Annotated[Literal["data_quality", "fairness"] | None, Query()] = None,
) -> AuditMetricSummary:
    _owned(db, AuditRun, run_id, principal.organization_id)
    query = select(MetricResult).where(
        MetricResult.organization_id == principal.organization_id,
        MetricResult.audit_run_id == run_id,
    )
    if category:
        query = query.where(MetricResult.category == category)
    metrics = db.scalars(
        query.order_by(
            MetricResult.category,
            MetricResult.protected_attribute,
            MetricResult.metric_key,
            MetricResult.comparison_group,
        )
    ).all()
    status_counts: dict[str, int] = {}
    evidence_gaps: list[str] = []
    for metric in metrics:
        status_counts[metric.status] = status_counts.get(metric.status, 0) + 1
        if metric.status == "insufficient_evidence":
            label = metric.metric_key.replace("_", " ")
            if metric.comparison_group:
                label += f" · {metric.comparison_group}"
            evidence_gaps.append(label)
    return AuditMetricSummary(
        audit_run_id=run_id,
        calculation_version=metrics[0].calculation_version if metrics else None,
        status_counts=status_counts,
        evidence_gaps=evidence_gaps,
        items=[MetricResultResponse.model_validate(metric) for metric in metrics],
    )


@router.post("/audit-runs/{run_id}/cancel", response_model=AuditRunResponse, tags=["audits"])
def cancel_audit_run(
    run_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.AUDIT_RUN))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuditRunResponse:
    command = EmptyCommand()
    action = f"cancel_audit_run:{run_id}"
    if replay := _replay(
        db,
        principal.organization_id,
        idempotency_key,
        action,
        command,
        AuditRunResponse,
    ):
        return replay
    run: AuditRun = _owned(db, AuditRun, run_id, principal.organization_id)
    if run.status in {"succeeded", "failed", "cancelled"}:
        raise HTTPException(status.HTTP_409_CONFLICT, "Completed runs cannot be cancelled")
    job: BackgroundJob = _owned(db, BackgroundJob, run.job_id, principal.organization_id)
    job.cancellation_requested = True
    job.status = "cancelling"
    run.status = "cancelling"
    db.flush()
    response = AuditRunResponse.model_validate(run)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="audit_run.cancellation_requested",
        resource_type="audit_run",
        resource_id=run.id,
        payload={"job_id": job.id},
    )
    _record_response(
        db,
        principal.organization_id,
        idempotency_key,
        action,
        command,
        response,
        200,
    )
    db.commit()
    revoke_job(settings, job_id=job.id)
    return response


@router.get("/jobs/{job_id}", response_model=BackgroundJobResponse, tags=["jobs"])
def get_job(
    job_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> BackgroundJobResponse:
    job = _owned(db, BackgroundJob, job_id, principal.organization_id)
    return BackgroundJobResponse.model_validate(job)


@router.post("/jobs/{job_id}/retry", response_model=BackgroundJobResponse, tags=["jobs"])
def retry_job(
    job_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.AUDIT_RUN))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BackgroundJobResponse:
    command = EmptyCommand()
    action = f"retry_job:{job_id}"
    if replay := _replay(
        db,
        principal.organization_id,
        idempotency_key,
        action,
        command,
        BackgroundJobResponse,
    ):
        return replay
    job: BackgroundJob = _owned(db, BackgroundJob, job_id, principal.organization_id)
    if job.status != "failed" or job.attempt >= job.max_attempts:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only failed jobs below the retry limit can be retried",
        )
    job.attempt += 1
    job.status = "queued"
    job.progress = 0
    job.error_code = None
    job.error_detail = None
    job.cancellation_requested = False
    run: AuditRun | None = None
    dataset: Dataset | None = None
    if job.resource_type == "audit_run":
        run = _owned(db, AuditRun, job.resource_id, principal.organization_id)
        dataset = _owned(db, Dataset, run.dataset_id, principal.organization_id)
        run.status = "queued"
        run.error_code = None
        run.error_detail = None
    db.flush()
    response = BackgroundJobResponse.model_validate(job)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="job.retry_queued",
        resource_type="job",
        resource_id=job.id,
        payload={"attempt": job.attempt, "max_attempts": job.max_attempts},
    )
    _record_response(
        db,
        principal.organization_id,
        idempotency_key,
        action,
        command,
        response,
        200,
    )
    db.commit()
    if run is not None and dataset is not None:
        try:
            dispatch_job(
                settings,
                task_name=job.task_name,
                job_id=job.id,
                kwargs={
                    "organization_id": principal.organization_id,
                    "audit_run_id": run.id,
                    "dataset_id": dataset.id,
                    "artifact_key": dataset.object_key,
                    "dataset_format": dataset.format,
                    "config": run.config_snapshot,
                },
            )
        except Exception as exc:
            job.status = "failed"
            job.error_code = "queue_unavailable"
            job.error_detail = str(exc)
            run.status = "failed"
            run.error_code = job.error_code
            run.error_detail = job.error_detail
            append_event(
                db,
                organization_id=principal.organization_id,
                actor_id="platform",
                action="job.dispatch_failed",
                resource_type="job",
                resource_id=job.id,
                payload={"error_code": job.error_code, "attempt": job.attempt},
            )
            response = BackgroundJobResponse.model_validate(job)
            record = db.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.organization_id == principal.organization_id,
                    IdempotencyRecord.key == idempotency_key,
                )
            )
            if record:
                record.response_body = response.model_dump(mode="json")
            db.commit()
    return response


@router.get("/audit-events", response_model=AuditEventListResponse, tags=["ledger"])
def list_audit_events(
    principal: Annotated[Principal, Depends(require_permission(Permission.AUDIT_LOG_READ))],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> AuditEventListResponse:
    predicate = AuditEvent.organization_id == principal.organization_id
    total = db.scalar(select(func.count()).select_from(AuditEvent).where(predicate)) or 0
    events = db.scalars(
        select(AuditEvent)
        .where(predicate)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AuditEventListResponse(
        items=[AuditEventResponse.model_validate(event) for event in events],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/audit-events/verify", response_model=LedgerVerificationResponse, tags=["ledger"])
def verify_audit_events(
    principal: Annotated[Principal, Depends(require_permission(Permission.AUDIT_LOG_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> LedgerVerificationResponse:
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.organization_id == principal.organization_id)
        .order_by(AuditEvent.occurred_at, AuditEvent.id)
    ).all()
    valid, broken_event_id = verify_chain(list(events))
    return LedgerVerificationResponse(
        valid=valid, checked_events=len(events), broken_event_id=broken_event_id
    )
