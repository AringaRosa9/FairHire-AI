from datetime import UTC, datetime
from typing import Annotated, Literal

from fairhire_domain.access import Permission, Role
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import get_db
from .ids import new_id
from .ledger import append_event
from .models import (
    AISystem,
    Approval,
    AuditRun,
    Finding,
    FindingRetest,
    MetricResult,
    Organization,
    RemediationTask,
)
from .routes import _owned, _record_response, _replay
from .schemas import (
    ApprovalChainCreate,
    ApprovalChainResponse,
    ApprovalDecisionCreate,
    ApprovalListResponse,
    ApprovalResponse,
    FindingCreate,
    FindingDetailResponse,
    FindingListResponse,
    FindingResponse,
    FindingRetestCreate,
    FindingRetestResponse,
    FindingTransition,
    ReleaseGateBlocker,
    ReleaseGateResponse,
    RemediationTaskCreate,
    RemediationTaskListResponse,
    RemediationTaskResponse,
    RemediationTaskUpdate,
    RiskAcceptanceCreate,
)
from .security import Principal, require_idempotency_key, require_permission

router = APIRouter(prefix="/v1")
REQUIRED_APPROVAL_STAGES = (("responsible_ai", 1), ("hr", 2), ("legal_dpo", 3))
ALLOWED_FINDING_TRANSITIONS: dict[str, set[str]] = {
    "open": {"triaged"},
    "triaged": {"mitigating"},
    "mitigating": {"ready_for_retest"},
    "ready_for_retest": {"mitigating", "resolved"},
    "resolved": {"open"},
    "accepted": {"open", "mitigating"},
}
ALLOWED_TASK_TRANSITIONS: dict[str, set[str]] = {
    "open": {"in_progress", "cancelled"},
    "in_progress": {"open", "completed", "cancelled"},
    "completed": {"in_progress"},
    "cancelled": {"open"},
}


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _latest_chain_version(db: Session, organization_id: str, system_id: str) -> int | None:
    return db.scalar(
        select(func.max(Approval.chain_version)).where(
            Approval.organization_id == organization_id,
            Approval.ai_system_id == system_id,
        )
    )


def _reopen_expired_acceptances(db: Session, organization_id: str, *, now: datetime) -> list[str]:
    expired = db.scalars(
        select(Finding).where(
            Finding.organization_id == organization_id,
            Finding.status == "accepted",
            Finding.accepted_until.is_not(None),
            Finding.accepted_until <= now,
        )
    ).all()
    for finding in expired:
        previous_until = finding.accepted_until
        assert previous_until is not None
        finding.status = "open"
        append_event(
            db,
            organization_id=organization_id,
            actor_id="platform",
            action="finding.acceptance_expired",
            resource_type="finding",
            resource_id=finding.id,
            payload={
                "before": {"status": "accepted", "accepted_until": previous_until.isoformat()},
                "after": {"status": "open"},
            },
            reason="Risk acceptance reached its configured expiry",
        )
    return [finding.id for finding in expired]


def _expire_approvals(db: Session, organization_id: str, *, now: datetime) -> list[str]:
    expired = db.scalars(
        select(Approval).where(
            Approval.organization_id == organization_id,
            Approval.decision == "approved",
            Approval.expires_at.is_not(None),
            Approval.expires_at <= now,
        )
    ).all()
    for approval in expired:
        assert approval.expires_at is not None
        approval.decision = "expired"
        append_event(
            db,
            organization_id=organization_id,
            actor_id="platform",
            action="approval.expired",
            resource_type="approval",
            resource_id=approval.id,
            payload={"stage": approval.stage, "expires_at": approval.expires_at.isoformat()},
            reason="Approval reached its configured expiry",
        )
    return [approval.id for approval in expired]


def _release_gate(
    db: Session,
    organization_id: str,
    system: AISystem,
    *,
    actor_id: str,
) -> ReleaseGateResponse:
    now = datetime.now(UTC)
    _reopen_expired_acceptances(db, organization_id, now=now)
    _expire_approvals(db, organization_id, now=now)
    findings = db.scalars(
        select(Finding).where(
            Finding.organization_id == organization_id,
            Finding.ai_system_id == system.id,
            Finding.severity == "critical",
            Finding.status.not_in(["resolved", "accepted"]),
        )
    ).all()
    blockers = [
        ReleaseGateBlocker(
            code="critical_finding",
            message=(
                f"Critical finding is not resolved or covered by a valid exception: {item.title}"
            ),
            resource_id=item.id,
        )
        for item in findings
    ]
    latest_run = db.scalar(
        select(AuditRun)
        .where(
            AuditRun.organization_id == organization_id,
            AuditRun.ai_system_id == system.id,
            AuditRun.status == "succeeded",
        )
        .order_by(AuditRun.completed_at.desc().nullslast(), AuditRun.submitted_at.desc())
        .limit(1)
    )
    if latest_run is not None:
        insufficient_metrics = list(
            db.scalars(
                select(MetricResult).where(
                    MetricResult.organization_id == organization_id,
                    MetricResult.audit_run_id == latest_run.id,
                    MetricResult.status == "insufficient_evidence",
                )
            ).all()
        )
        blockers.extend(
            ReleaseGateBlocker(
                code="insufficient_evidence",
                message=f"Latest audit has insufficient evidence: {item.metric_key}",
                resource_id=item.id,
            )
            for item in insufficient_metrics
        )
        organization = db.get(Organization, organization_id)
        if organization is not None and latest_run.policy_pack_version != organization.policy_pack:
            blockers.append(
                ReleaseGateBlocker(
                    code="rule_pack_outdated",
                    message=(
                        "Latest audit used an outdated rule pack: "
                        f"{latest_run.policy_pack_version}; current is {organization.policy_pack}"
                    ),
                    resource_id=latest_run.id,
                )
            )
    else:
        blockers.append(
            ReleaseGateBlocker(
                code="audit_missing",
                message="No successful Audit Run is available for this system",
                resource_id=system.id,
            )
        )
    organization = db.get(Organization, organization_id)
    if (
        organization is not None
        and organization.policy_pack_expires_at is not None
        and _utc(organization.policy_pack_expires_at) <= now
    ):
        blockers.append(
            ReleaseGateBlocker(
                code="rule_pack_expired",
                message=f"Rule pack {organization.policy_pack} has expired and must be reviewed",
                resource_id=organization.id,
            )
        )
    chain_version = _latest_chain_version(db, organization_id, system.id)
    approvals: list[Approval] = []
    if chain_version is not None:
        approvals = list(
            db.scalars(
                select(Approval)
                .where(
                    Approval.organization_id == organization_id,
                    Approval.ai_system_id == system.id,
                    Approval.chain_version == chain_version,
                )
                .order_by(Approval.sequence)
            ).all()
        )
    approved_stages = [item.stage for item in approvals if item.decision == "approved"]
    rejected = [item for item in approvals if item.decision == "rejected"]
    if rejected:
        blockers.extend(
            ReleaseGateBlocker(
                code="approval_rejected",
                message=f"{item.stage} rejected the release: {item.reason}",
                resource_id=item.id,
            )
            for item in rejected
        )
    if blockers:
        gate_status: Literal["approved", "review_required", "blocked"] = "blocked"
    elif set(approved_stages) == {stage for stage, _ in REQUIRED_APPROVAL_STAGES}:
        gate_status = "approved"
    else:
        gate_status = "review_required"
    if system.release_status != gate_status:
        previous = system.release_status
        system.release_status = gate_status
        append_event(
            db,
            organization_id=organization_id,
            actor_id=actor_id,
            action="release_gate.status_changed",
            resource_type="ai_system",
            resource_id=system.id,
            payload={
                "before": {"release_status": previous},
                "after": {"release_status": gate_status},
            },
            reason="Release gate recalculated from current findings and approvals",
        )
    return ReleaseGateResponse(
        ai_system_id=system.id,
        status=gate_status,
        chain_version=chain_version,
        required_stages=[stage for stage, _ in REQUIRED_APPROVAL_STAGES],
        approved_stages=approved_stages,
        blockers=blockers,
        evaluated_at=now,
    )


def _finding_detail(db: Session, finding: Finding) -> FindingDetailResponse:
    tasks = db.scalars(
        select(RemediationTask)
        .where(
            RemediationTask.organization_id == finding.organization_id,
            RemediationTask.finding_id == finding.id,
        )
        .order_by(RemediationTask.due_at, RemediationTask.created_at)
    ).all()
    retests = db.scalars(
        select(FindingRetest)
        .where(
            FindingRetest.organization_id == finding.organization_id,
            FindingRetest.finding_id == finding.id,
        )
        .order_by(FindingRetest.performed_at.desc())
    ).all()
    return FindingDetailResponse(
        **FindingResponse.model_validate(finding).model_dump(),
        tasks=[RemediationTaskResponse.model_validate(item) for item in tasks],
        retests=[FindingRetestResponse.model_validate(item) for item in retests],
    )


@router.post("/findings", response_model=FindingResponse, status_code=201, tags=["governance"])
def create_finding(
    payload: FindingCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.FINDING_WRITE))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> FindingResponse:
    action = "create_finding"
    if replay := _replay(
        db, principal.organization_id, idempotency_key, action, payload, FindingResponse
    ):
        return replay
    _owned(db, AISystem, payload.ai_system_id, principal.organization_id)
    if payload.audit_run_id:
        run: AuditRun = _owned(db, AuditRun, payload.audit_run_id, principal.organization_id)
        if run.ai_system_id != payload.ai_system_id:
            raise HTTPException(422, "Audit run belongs to another AI system")
    if payload.source_metric_id:
        metric: MetricResult = _owned(
            db, MetricResult, payload.source_metric_id, principal.organization_id
        )
        if not payload.audit_run_id or metric.audit_run_id != payload.audit_run_id:
            raise HTTPException(422, "Source metric must belong to the finding audit run")
    finding = Finding(
        id=new_id("fnd"),
        organization_id=principal.organization_id,
        status="open",
        created_by=principal.user_id,
        **payload.model_dump(),
    )
    db.add(finding)
    db.flush()
    response = FindingResponse.model_validate(finding)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="finding.created",
        resource_type="finding",
        resource_id=finding.id,
        payload={
            "severity": finding.severity,
            "confidence": finding.confidence,
            "evidence_refs": finding.evidence_refs,
            "control_refs": finding.control_refs,
            "owner_id": finding.owner_id,
            "due_at": finding.due_at.isoformat(),
        },
    )
    _record_response(db, principal.organization_id, idempotency_key, action, payload, response, 201)
    system: AISystem = _owned(db, AISystem, finding.ai_system_id, principal.organization_id)
    _release_gate(db, principal.organization_id, system, actor_id=principal.user_id)
    db.commit()
    return response


@router.get("/findings", response_model=FindingListResponse, tags=["governance"])
def list_findings(
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_READ))],
    db: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    severity: str | None = None,
    ai_system_id: str | None = None,
    due_before: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> FindingListResponse:
    _reopen_expired_acceptances(db, principal.organization_id, now=datetime.now(UTC))
    predicates = [Finding.organization_id == principal.organization_id]
    if status_filter:
        predicates.append(Finding.status == status_filter)
    if severity:
        predicates.append(Finding.severity == severity)
    if ai_system_id:
        predicates.append(Finding.ai_system_id == ai_system_id)
    if due_before:
        predicates.append(Finding.due_at <= due_before)
    total = db.scalar(select(func.count()).select_from(Finding).where(*predicates)) or 0
    items = db.scalars(
        select(Finding)
        .where(*predicates)
        .order_by(Finding.due_at, Finding.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    db.commit()
    return FindingListResponse(
        items=[FindingResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/findings/{finding_id}", response_model=FindingDetailResponse, tags=["governance"])
def get_finding(
    finding_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> FindingDetailResponse:
    _reopen_expired_acceptances(db, principal.organization_id, now=datetime.now(UTC))
    finding = _owned(db, Finding, finding_id, principal.organization_id)
    response = _finding_detail(db, finding)
    db.commit()
    return response


@router.post(
    "/findings/{finding_id}/transition",
    response_model=FindingResponse,
    tags=["governance"],
)
def transition_finding(
    finding_id: str,
    payload: FindingTransition,
    principal: Annotated[Principal, Depends(require_permission(Permission.FINDING_WRITE))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> FindingResponse:
    action = f"transition_finding:{finding_id}"
    if replay := _replay(
        db, principal.organization_id, idempotency_key, action, payload, FindingResponse
    ):
        return replay
    finding: Finding = _owned(db, Finding, finding_id, principal.organization_id)
    if payload.status == "accepted":
        raise HTTPException(422, "Use the risk acceptance endpoint to accept a finding")
    if payload.status not in ALLOWED_FINDING_TRANSITIONS.get(finding.status, set()):
        raise HTTPException(
            409, f"Cannot transition finding from {finding.status} to {payload.status}"
        )
    previous = finding.status
    finding.status = payload.status
    db.flush()
    response = FindingResponse.model_validate(finding)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="finding.status_changed",
        resource_type="finding",
        resource_id=finding.id,
        payload={"before": {"status": previous}, "after": {"status": finding.status}},
        reason=payload.reason,
    )
    _record_response(db, principal.organization_id, idempotency_key, action, payload, response, 200)
    system: AISystem = _owned(db, AISystem, finding.ai_system_id, principal.organization_id)
    _release_gate(db, principal.organization_id, system, actor_id=principal.user_id)
    db.commit()
    return response


@router.post("/findings/{finding_id}/accept", response_model=FindingResponse, tags=["governance"])
def accept_finding(
    finding_id: str,
    payload: RiskAcceptanceCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.RISK_ACCEPT))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> FindingResponse:
    action = f"accept_finding:{finding_id}"
    if replay := _replay(
        db, principal.organization_id, idempotency_key, action, payload, FindingResponse
    ):
        return replay
    finding: Finding = _owned(db, Finding, finding_id, principal.organization_id)
    if finding.status not in {"triaged", "mitigating", "ready_for_retest"}:
        raise HTTPException(409, f"Cannot accept a finding in {finding.status} state")
    now = datetime.now(UTC)
    if _utc(payload.expires_at) <= now:
        raise HTTPException(422, "Risk acceptance expiry must be in the future")
    previous = finding.status
    finding.status = "accepted"
    finding.residual_risk = payload.residual_risk
    finding.acceptance_reason = payload.reason
    finding.accepted_by = principal.user_id
    finding.accepted_at = now
    finding.accepted_until = payload.expires_at
    db.flush()
    response = FindingResponse.model_validate(finding)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="finding.risk_accepted",
        resource_type="finding",
        resource_id=finding.id,
        payload={
            "before": {"status": previous},
            "after": {"status": "accepted", "accepted_until": payload.expires_at.isoformat()},
            "residual_risk": payload.residual_risk,
        },
        reason=payload.reason,
    )
    _record_response(db, principal.organization_id, idempotency_key, action, payload, response, 200)
    system: AISystem = _owned(db, AISystem, finding.ai_system_id, principal.organization_id)
    _release_gate(db, principal.organization_id, system, actor_id=principal.user_id)
    db.commit()
    return response


@router.post(
    "/findings/{finding_id}/tasks",
    response_model=RemediationTaskResponse,
    status_code=201,
    tags=["governance"],
)
def create_remediation_task(
    finding_id: str,
    payload: RemediationTaskCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.FINDING_WRITE))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> RemediationTaskResponse:
    action = f"create_remediation_task:{finding_id}"
    if replay := _replay(
        db, principal.organization_id, idempotency_key, action, payload, RemediationTaskResponse
    ):
        return replay
    finding: Finding = _owned(db, Finding, finding_id, principal.organization_id)
    task = RemediationTask(
        id=new_id("tsk"),
        organization_id=principal.organization_id,
        finding_id=finding.id,
        status="open",
        evidence_refs=[],
        created_by=principal.user_id,
        **payload.model_dump(),
    )
    db.add(task)
    db.flush()
    response = RemediationTaskResponse.model_validate(task)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="remediation_task.created",
        resource_type="remediation_task",
        resource_id=task.id,
        payload={
            "finding_id": finding.id,
            "owner_id": task.owner_id,
            "due_at": task.due_at.isoformat(),
        },
    )
    _record_response(db, principal.organization_id, idempotency_key, action, payload, response, 201)
    db.commit()
    return response


@router.get("/remediation-tasks", response_model=RemediationTaskListResponse, tags=["governance"])
def list_remediation_tasks(
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_READ))],
    db: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    finding_id: str | None = None,
    due_before: datetime | None = None,
    overdue_only: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> RemediationTaskListResponse:
    predicates = [RemediationTask.organization_id == principal.organization_id]
    if status_filter:
        predicates.append(RemediationTask.status == status_filter)
    if finding_id:
        predicates.append(RemediationTask.finding_id == finding_id)
    if due_before:
        predicates.append(RemediationTask.due_at <= due_before)
    if overdue_only:
        predicates.extend(
            [
                RemediationTask.due_at < datetime.now(UTC),
                RemediationTask.status.in_(["open", "in_progress"]),
            ]
        )
    total = db.scalar(select(func.count()).select_from(RemediationTask).where(*predicates)) or 0
    items = db.scalars(
        select(RemediationTask)
        .where(*predicates)
        .order_by(RemediationTask.due_at, RemediationTask.created_at)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return RemediationTaskListResponse(
        items=[RemediationTaskResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/remediation-tasks/{task_id}/status",
    response_model=RemediationTaskResponse,
    tags=["governance"],
)
def update_remediation_task(
    task_id: str,
    payload: RemediationTaskUpdate,
    principal: Annotated[Principal, Depends(require_permission(Permission.FINDING_WRITE))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> RemediationTaskResponse:
    action = f"update_remediation_task:{task_id}"
    if replay := _replay(
        db, principal.organization_id, idempotency_key, action, payload, RemediationTaskResponse
    ):
        return replay
    task: RemediationTask = _owned(db, RemediationTask, task_id, principal.organization_id)
    if payload.status not in ALLOWED_TASK_TRANSITIONS.get(task.status, set()):
        raise HTTPException(409, f"Cannot transition task from {task.status} to {payload.status}")
    if payload.status == "completed" and not payload.evidence_refs:
        raise HTTPException(422, "Completion requires at least one evidence reference")
    previous = task.status
    task.status = payload.status
    task.evidence_refs = payload.evidence_refs
    task.completed_at = datetime.now(UTC) if payload.status == "completed" else None
    db.flush()
    response = RemediationTaskResponse.model_validate(task)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="remediation_task.status_changed",
        resource_type="remediation_task",
        resource_id=task.id,
        payload={
            "before": {"status": previous},
            "after": {"status": task.status},
            "evidence_refs": task.evidence_refs,
        },
        reason=payload.reason,
    )
    _record_response(db, principal.organization_id, idempotency_key, action, payload, response, 200)
    db.commit()
    return response


@router.post(
    "/findings/{finding_id}/retests",
    response_model=FindingRetestResponse,
    status_code=201,
    tags=["governance"],
)
def record_finding_retest(
    finding_id: str,
    payload: FindingRetestCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.FINDING_WRITE))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> FindingRetestResponse:
    action = f"record_finding_retest:{finding_id}"
    if replay := _replay(
        db, principal.organization_id, idempotency_key, action, payload, FindingRetestResponse
    ):
        return replay
    finding: Finding = _owned(db, Finding, finding_id, principal.organization_id)
    if finding.status != "ready_for_retest":
        raise HTTPException(409, "Finding must be ready for retest")
    run: AuditRun = _owned(db, AuditRun, payload.audit_run_id, principal.organization_id)
    if run.ai_system_id != finding.ai_system_id or run.status != "succeeded":
        raise HTTPException(422, "Retest must be a succeeded audit run for the same AI system")
    retest = FindingRetest(
        id=new_id("rts"),
        organization_id=principal.organization_id,
        finding_id=finding.id,
        performed_by=principal.user_id,
        **payload.model_dump(),
    )
    previous = finding.status
    finding.status = "resolved" if payload.outcome == "resolved" else "mitigating"
    db.add(retest)
    db.flush()
    response = FindingRetestResponse.model_validate(retest)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="finding.retested",
        resource_type="finding",
        resource_id=finding.id,
        payload={
            "audit_run_id": run.id,
            "outcome": retest.outcome,
            "before": {"status": previous},
            "after": {"status": finding.status},
        },
        reason=payload.notes,
    )
    _record_response(db, principal.organization_id, idempotency_key, action, payload, response, 201)
    system: AISystem = _owned(db, AISystem, finding.ai_system_id, principal.organization_id)
    _release_gate(db, principal.organization_id, system, actor_id=principal.user_id)
    db.commit()
    return response


@router.post(
    "/ai-systems/{system_id}/approval-chain",
    response_model=ApprovalChainResponse,
    status_code=201,
    tags=["approvals"],
)
def start_approval_chain(
    system_id: str,
    payload: ApprovalChainCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.APPROVAL_WRITE))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ApprovalChainResponse:
    action = f"start_approval_chain:{system_id}"
    if replay := _replay(
        db,
        principal.organization_id,
        idempotency_key,
        action,
        payload,
        ApprovalChainResponse,
    ):
        return replay
    system: AISystem = _owned(db, AISystem, system_id, principal.organization_id)
    version = (_latest_chain_version(db, principal.organization_id, system.id) or 0) + 1
    approvals = [
        Approval(
            id=new_id("apr"),
            organization_id=principal.organization_id,
            ai_system_id=system.id,
            chain_version=version,
            stage=stage,
            sequence=sequence,
            decision="pending",
            created_by=principal.user_id,
        )
        for stage, sequence in REQUIRED_APPROVAL_STAGES
    ]
    db.add_all(approvals)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="approval_chain.started",
        resource_type="ai_system",
        resource_id=system.id,
        payload={
            "chain_version": version,
            "stages": [item.stage for item in approvals],
            "idempotency_key": idempotency_key,
        },
        reason=payload.reason,
    )
    _release_gate(db, principal.organization_id, system, actor_id=principal.user_id)
    response = ApprovalChainResponse(
        ai_system_id=system.id,
        chain_version=version,
        items=[ApprovalResponse.model_validate(item) for item in approvals],
    )
    _record_response(
        db,
        principal.organization_id,
        idempotency_key,
        action,
        payload,
        response,
        201,
    )
    db.commit()
    return response


@router.get("/approvals", response_model=ApprovalListResponse, tags=["approvals"])
def list_approvals(
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_READ))],
    db: Annotated[Session, Depends(get_db)],
    decision: str | None = None,
    ai_system_id: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ApprovalListResponse:
    _expire_approvals(db, principal.organization_id, now=datetime.now(UTC))
    predicates = [Approval.organization_id == principal.organization_id]
    if decision:
        predicates.append(Approval.decision == decision)
    if ai_system_id:
        predicates.append(Approval.ai_system_id == ai_system_id)
    total = db.scalar(select(func.count()).select_from(Approval).where(*predicates)) or 0
    items = db.scalars(
        select(Approval)
        .where(*predicates)
        .order_by(Approval.created_at.desc(), Approval.sequence)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    db.commit()
    return ApprovalListResponse(
        items=[ApprovalResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


def _can_approve_stage(role: Role, stage: str) -> bool:
    allowed = {
        "responsible_ai": {Role.ADMIN, Role.RESPONSIBLE_AI},
        "hr": {Role.ADMIN, Role.HR_REVIEWER},
        "legal_dpo": {Role.ADMIN, Role.LEGAL_REVIEWER},
    }
    return role in allowed[stage]


@router.post(
    "/approvals/{approval_id}/decision", response_model=ApprovalResponse, tags=["approvals"]
)
def decide_approval(
    approval_id: str,
    payload: ApprovalDecisionCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.APPROVAL_WRITE))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ApprovalResponse:
    action = f"decide_approval:{approval_id}"
    if replay := _replay(
        db, principal.organization_id, idempotency_key, action, payload, ApprovalResponse
    ):
        return replay
    approval: Approval = _owned(db, Approval, approval_id, principal.organization_id)
    if approval.decision != "pending":
        raise HTTPException(409, "Approval has already been decided")
    if not _can_approve_stage(principal.role, approval.stage):
        raise HTTPException(403, f"Role {principal.role.value} cannot decide {approval.stage}")
    if payload.expires_at and _utc(payload.expires_at) <= datetime.now(UTC):
        raise HTTPException(422, "Approval expiry must be in the future")
    previous_stages = db.scalars(
        select(Approval).where(
            Approval.organization_id == principal.organization_id,
            Approval.ai_system_id == approval.ai_system_id,
            Approval.chain_version == approval.chain_version,
            Approval.sequence < approval.sequence,
        )
    ).all()
    if payload.decision == "approved" and any(
        item.decision != "approved" for item in previous_stages
    ):
        raise HTTPException(409, "Earlier approval stages must be approved first")
    if payload.decision == "approved" and approval.stage == "legal_dpo":
        _reopen_expired_acceptances(db, principal.organization_id, now=datetime.now(UTC))
        critical_blockers = db.scalar(
            select(func.count())
            .select_from(Finding)
            .where(
                Finding.organization_id == principal.organization_id,
                Finding.ai_system_id == approval.ai_system_id,
                Finding.severity == "critical",
                Finding.status.not_in(["resolved", "accepted"]),
            )
        )
        if critical_blockers:
            db.commit()
            raise HTTPException(
                409, "Critical findings require resolution or a valid risk exception"
            )
    approval.decision = payload.decision
    approval.reason = payload.reason
    approval.approver_id = principal.user_id
    approval.approver_name = principal.display_name
    approval.decided_at = datetime.now(UTC)
    approval.expires_at = payload.expires_at
    db.flush()
    response = ApprovalResponse.model_validate(approval)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="approval.decided",
        resource_type="approval",
        resource_id=approval.id,
        payload={
            "stage": approval.stage,
            "decision": approval.decision,
            "chain_version": approval.chain_version,
            "expires_at": payload.expires_at.isoformat() if payload.expires_at else None,
        },
        reason=payload.reason,
    )
    _record_response(db, principal.organization_id, idempotency_key, action, payload, response, 200)
    system = _owned(db, AISystem, approval.ai_system_id, principal.organization_id)
    _release_gate(db, principal.organization_id, system, actor_id=principal.user_id)
    db.commit()
    return response


@router.get(
    "/ai-systems/{system_id}/release-gate", response_model=ReleaseGateResponse, tags=["approvals"]
)
def get_release_gate(
    system_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> ReleaseGateResponse:
    system: AISystem = _owned(db, AISystem, system_id, principal.organization_id)
    result = _release_gate(db, principal.organization_id, system, actor_id=principal.user_id)
    db.commit()
    return result
