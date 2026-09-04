import csv
import hashlib
import io
import json
import re
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fairhire_domain.access import Permission
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import get_db
from .ids import new_id
from .ledger import append_event
from .models import (
    AISystem,
    Approval,
    AssistantAnswer,
    AuditEvent,
    AuditRun,
    Finding,
    KnowledgeSource,
    MetricResult,
    ModelVersion,
    RegulatoryAssessment,
    Report,
)
from .routes import _owned, _record_response, _replay
from .schemas import (
    AssistantAnswerCreate,
    AssistantAnswerListResponse,
    AssistantAnswerResponse,
    KnowledgeSourceCreate,
    KnowledgeSourceListResponse,
    KnowledgeSourceResponse,
    ReportApprovalCreate,
    ReportCreate,
    ReportDifference,
    ReportDiffResponse,
    ReportListResponse,
    ReportResponse,
)
from .security import Principal, require_idempotency_key, require_permission

router = APIRouter(prefix="/v1")


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _report_response(report: Report) -> ReportResponse:
    return ReportResponse.model_validate(report)


def _metric_item(metric: MetricResult) -> dict[str, object]:
    return {
        "metric_result_id": metric.id,
        "metric_key": metric.metric_key,
        "protected_attribute": metric.protected_attribute,
        "reference_group": metric.reference_group,
        "comparison_group": metric.comparison_group,
        "value": metric.value,
        "lower_bound": metric.lower_bound,
        "upper_bound": metric.upper_bound,
        "status": metric.status,
        "threshold": metric.threshold,
        "threshold_operator": metric.threshold_operator,
        "threshold_source": metric.threshold_source,
        "raw_counts": metric.raw_counts,
        "method": metric.method,
        "calculation_version": metric.calculation_version,
        "evidence_ref": f"metric:{metric.id}",
    }


def _generate_report_content(
    db: Session, *, organization_id: str, system: AISystem, run: AuditRun
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
    metrics = list(
        db.scalars(
            select(MetricResult)
            .where(
                MetricResult.organization_id == organization_id,
                MetricResult.audit_run_id == run.id,
            )
            .order_by(MetricResult.category, MetricResult.metric_key, MetricResult.id)
        ).all()
    )
    findings = list(
        db.scalars(
            select(Finding)
            .where(
                Finding.organization_id == organization_id,
                Finding.ai_system_id == system.id,
            )
            .order_by(Finding.severity, Finding.created_at)
        ).all()
    )
    assessments = list(
        db.scalars(
            select(RegulatoryAssessment)
            .where(
                RegulatoryAssessment.organization_id == organization_id,
                RegulatoryAssessment.ai_system_id == system.id,
            )
            .order_by(RegulatoryAssessment.version.desc())
            .limit(1)
        ).all()
    )
    model = db.scalar(
        select(ModelVersion).where(
            ModelVersion.organization_id == organization_id,
            ModelVersion.id == run.model_version_id,
        )
    )
    approvals = list(
        db.scalars(
            select(Approval)
            .where(
                Approval.organization_id == organization_id,
                Approval.ai_system_id == system.id,
            )
            .order_by(Approval.chain_version.desc(), Approval.sequence)
        ).all()
    )
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.organization_id == organization_id,
                (
                    (AuditEvent.resource_id == system.id)
                    | (AuditEvent.resource_id == run.id)
                    | (AuditEvent.resource_id.in_([finding.id for finding in findings]))
                ),
            )
            .order_by(AuditEvent.occurred_at)
        ).all()
    )
    evidence_gaps: list[str] = []
    if not metrics:
        evidence_gaps.append("The selected Audit Run has no published Metric Results.")
    evidence_gaps.extend(
        f"{item.metric_key} is marked insufficient evidence."
        for item in metrics
        if item.status == "insufficient_evidence"
    )
    if not assessments:
        evidence_gaps.append("No regulatory assessment is linked to this AI system.")
    if model is None:
        evidence_gaps.append("The Audit Run model version record is unavailable.")

    fairness = [item for item in metrics if item.category == "fairness"]
    explainability = [item for item in metrics if item.category == "explainability"]
    status_counts: dict[str, int] = {}
    for metric in metrics:
        status_counts[metric.status] = status_counts.get(metric.status, 0) + 1
    open_findings = [item for item in findings if item.status not in {"resolved", "accepted"}]
    latest_assessment = assessments[0] if assessments else None

    sections: list[dict[str, object]] = [
        {
            "key": "executive_summary",
            "title": "Executive Summary",
            "summary": (
                f"Audit Run {run.id} produced {len(metrics)} traceable Metric Results and "
                f"{len(open_findings)} unresolved findings. This is risk evidence, "
                "not a legal determination."
            ),
            "items": [
                {
                    "audit_run_id": run.id,
                    "status": run.status,
                    "status_counts": status_counts,
                    "data_fingerprint": run.data_fingerprint,
                    "evidence_ref": f"audit:{run.id}",
                }
            ],
        },
        {
            "key": "fairness",
            "title": "Fairness",
            "summary": (
                f"{len(fairness)} fairness measures preserve counts, uncertainty, "
                "method and threshold provenance."
            ),
            "items": [_metric_item(item) for item in fairness],
        },
        {
            "key": "explainability",
            "title": "Explainability",
            "summary": (
                f"{len(explainability)} explainability results record method boundaries "
                "and calculation versions."
            ),
            "items": [_metric_item(item) for item in explainability],
        },
        {
            "key": "model_system_card",
            "title": "Model / System Card",
            "summary": (
                "Declared purpose, deployment context and the exact model and data "
                "snapshot under review."
            ),
            "items": [
                {
                    "system_id": system.id,
                    "name": system.name,
                    "purpose": system.purpose,
                    "actual_use": system.actual_use,
                    "human_oversight": system.human_oversight,
                    "jurisdictions": system.jurisdictions,
                    "model_version_id": run.model_version_id,
                    "model_version": model.version_label if model else None,
                    "model_content_hash": model.content_hash if model else None,
                    "dataset_id": run.dataset_id,
                    "data_fingerprint": run.data_fingerprint,
                    "evidence_ref": f"audit:{run.id}",
                }
            ],
        },
        {
            "key": "risk_assessment",
            "title": "Risk Assessment",
            "summary": (
                "Regulatory applicability, unresolved risks and accountable approvals "
                "are presented without automatic compliance claims."
            ),
            "items": [
                {
                    "assessment_id": latest_assessment.id if latest_assessment else None,
                    "risk_class": latest_assessment.risk_class if latest_assessment else None,
                    "rationale": latest_assessment.rationale if latest_assessment else None,
                    "basis_links": latest_assessment.basis_links if latest_assessment else [],
                    "findings": [
                        {
                            "id": item.id,
                            "title": item.title,
                            "severity": item.severity,
                            "status": item.status,
                            "evidence_refs": item.evidence_refs,
                        }
                        for item in findings
                    ],
                    "approvals": [
                        {
                            "id": item.id,
                            "stage": item.stage,
                            "decision": item.decision,
                            "approver": item.approver_name,
                        }
                        for item in approvals
                    ],
                }
            ],
        },
        {
            "key": "audit_log",
            "title": "Audit Log",
            "summary": (
                f"{len(events)} append-only events connect evidence creation to "
                "accountable decisions."
            ),
            "items": [
                {
                    "id": item.id,
                    "action": item.action,
                    "actor_id": item.actor_id,
                    "resource_type": item.resource_type,
                    "resource_id": item.resource_id,
                    "occurred_at": item.occurred_at.isoformat(),
                    "current_hash": item.current_hash,
                }
                for item in events
            ],
        },
        {
            "key": "evidence_gap",
            "title": "Evidence Gap",
            "summary": (
                "No unresolved evidence gaps were detected."
                if not evidence_gaps
                else f"{len(evidence_gaps)} limitations prevent stronger conclusions."
            ),
            "items": [{"gap": item} for item in evidence_gaps],
        },
    ]
    evidence_index: list[dict[str, object]] = [
        {
            "reference": f"metric:{item.id}",
            "audit_run_id": run.id,
            "metric_result_id": item.id,
            "label": item.metric_key,
            "value": item.value,
            "method": item.method,
            "calculation_version": item.calculation_version,
        }
        for item in metrics
    ]
    evidence_index.append(
        {
            "reference": f"audit:{run.id}",
            "audit_run_id": run.id,
            "metric_result_id": None,
            "label": "Audit Run provenance",
            "value": None,
            "method": "reproducible_audit_snapshot",
            "calculation_version": next((item.calculation_version for item in metrics), None),
        }
    )
    return sections, evidence_index, evidence_gaps


@router.post("/reports", response_model=ReportResponse, status_code=201, tags=["evidence"])
def create_report(
    payload: ReportCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.REPORT_APPROVE))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ReportResponse:
    action = "create_report"
    if replay := _replay(
        db, principal.organization_id, idempotency_key, action, payload, ReportResponse
    ):
        return replay
    system: AISystem = _owned(db, AISystem, payload.ai_system_id, principal.organization_id)
    run: AuditRun = _owned(db, AuditRun, payload.audit_run_id, principal.organization_id)
    if run.ai_system_id != system.id:
        raise HTTPException(422, "Audit Run belongs to another AI system")
    if run.status != "succeeded":
        raise HTTPException(409, "Only a succeeded Audit Run can be packaged as evidence")
    latest = db.scalar(
        select(Report)
        .where(
            Report.organization_id == principal.organization_id,
            Report.ai_system_id == system.id,
        )
        .order_by(Report.version.desc())
        .limit(1)
    )
    version = (latest.version if latest else 0) + 1
    sections, evidence_index, evidence_gaps = _generate_report_content(
        db, organization_id=principal.organization_id, system=system, run=run
    )
    snapshot = {
        "ai_system_id": system.id,
        "audit_run_id": run.id,
        "policy_pack_version": run.policy_pack_version,
        "sections": sections,
        "evidence_index": evidence_index,
        "evidence_gaps": evidence_gaps,
    }
    report = Report(
        id=new_id("rpt"),
        organization_id=principal.organization_id,
        ai_system_id=system.id,
        audit_run_id=run.id,
        previous_report_id=latest.id if latest else None,
        version=version,
        title=payload.title or f"{system.name} evidence package",
        status="draft",
        policy_pack_version=run.policy_pack_version,
        sections=sections,
        evidence_index=evidence_index,
        evidence_gaps=evidence_gaps,
        content_hash=_canonical_hash(snapshot),
        created_by=principal.user_id,
    )
    db.add(report)
    db.flush()
    response = _report_response(report)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="report.created",
        resource_type="report",
        resource_id=report.id,
        payload={
            "version": version,
            "audit_run_id": run.id,
            "content_hash": report.content_hash,
            "evidence_gap_count": len(evidence_gaps),
        },
    )
    _record_response(db, principal.organization_id, idempotency_key, action, payload, response, 201)
    db.commit()
    return response


@router.get("/reports", response_model=ReportListResponse, tags=["evidence"])
def list_reports(
    principal: Annotated[Principal, Depends(require_permission(Permission.REPORT_READ))],
    db: Annotated[Session, Depends(get_db)],
    ai_system_id: str | None = None,
    status: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ReportListResponse:
    predicates: list[Any] = [Report.organization_id == principal.organization_id]
    if ai_system_id:
        predicates.append(Report.ai_system_id == ai_system_id)
    if status:
        predicates.append(Report.status == status)
    total = db.scalar(select(func.count()).select_from(Report).where(*predicates)) or 0
    items = list(
        db.scalars(
            select(Report)
            .where(*predicates)
            .order_by(Report.created_at.desc(), Report.version.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return ReportListResponse(
        items=[_report_response(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/reports/{report_id}", response_model=ReportResponse, tags=["evidence"])
def get_report(
    report_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.REPORT_READ))],
    db: Annotated[Session, Depends(get_db)],
) -> ReportResponse:
    return _report_response(_owned(db, Report, report_id, principal.organization_id))


@router.post("/reports/{report_id}/approve", response_model=ReportResponse, tags=["evidence"])
def approve_report(
    report_id: str,
    payload: ReportApprovalCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.REPORT_APPROVE))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> ReportResponse:
    action = f"approve_report:{report_id}"
    if replay := _replay(
        db, principal.organization_id, idempotency_key, action, payload, ReportResponse
    ):
        return replay
    report: Report = _owned(db, Report, report_id, principal.organization_id)
    if report.status != "draft":
        raise HTTPException(409, "Only a draft report can be approved")
    if report.evidence_gaps:
        raise HTTPException(409, "Resolve or explicitly document all Evidence Gaps before approval")
    now = datetime.now(UTC)
    previous_approved = list(
        db.scalars(
            select(Report).where(
                Report.organization_id == principal.organization_id,
                Report.ai_system_id == report.ai_system_id,
                Report.status == "approved",
            )
        ).all()
    )
    for previous in previous_approved:
        previous.status = "superseded"
        previous.superseded_at = now
    report.status = "approved"
    report.approved_by = principal.user_id
    report.approved_at = now
    db.flush()
    response = _report_response(report)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="report.approved",
        resource_type="report",
        resource_id=report.id,
        payload={
            "content_hash": report.content_hash,
            "superseded_report_ids": [item.id for item in previous_approved],
        },
        reason=payload.reason,
    )
    _record_response(db, principal.organization_id, idempotency_key, action, payload, response, 200)
    db.commit()
    return response


def _diff(before: object, after: object, path: str = "$") -> list[ReportDifference]:
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[ReportDifference] = []
        for key in sorted(set(before) | set(after)):
            changes.extend(_diff(before.get(key), after.get(key), f"{path}.{key}"))
        return changes
    if isinstance(before, list) and isinstance(after, list):
        changes = []
        for index in range(max(len(before), len(after))):
            changes.extend(
                _diff(
                    before[index] if index < len(before) else None,
                    after[index] if index < len(after) else None,
                    f"{path}[{index}]",
                )
            )
        return changes
    return [] if before == after else [ReportDifference(path=path, before=before, after=after)]


@router.get("/reports/{report_id}/diff", response_model=ReportDiffResponse, tags=["evidence"])
def diff_report(
    report_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.REPORT_READ))],
    db: Annotated[Session, Depends(get_db)],
    compared_report_id: str | None = None,
) -> ReportDiffResponse:
    report: Report = _owned(db, Report, report_id, principal.organization_id)
    compare_id = compared_report_id or report.previous_report_id
    if not compare_id:
        raise HTTPException(404, "No earlier report version is available")
    previous: Report = _owned(db, Report, compare_id, principal.organization_id)
    if previous.ai_system_id != report.ai_system_id:
        raise HTTPException(422, "Reports belong to different AI systems")
    before = {
        "policy_pack_version": previous.policy_pack_version,
        "sections": previous.sections,
        "evidence_index": previous.evidence_index,
        "evidence_gaps": previous.evidence_gaps,
    }
    after = {
        "policy_pack_version": report.policy_pack_version,
        "sections": report.sections,
        "evidence_index": report.evidence_index,
        "evidence_gaps": report.evidence_gaps,
    }
    return ReportDiffResponse(
        report_id=report.id,
        compared_report_id=previous.id,
        changes=_diff(before, after),
    )


def _pdf_bytes(report: Report) -> bytes:
    lines = [
        report.title,
        f"Version {report.version} | {report.status.upper()}",
        f"Content hash: {report.content_hash}",
        f"Audit Run: {report.audit_run_id}",
        "Risk evidence only; not a legal determination.",
    ]
    for section in report.sections:
        lines.extend(["", str(section["title"]), str(section["summary"])])
    lines.extend(["", "Metric provenance"])
    for trace in report.evidence_index:
        lines.extend(
            [
                f"{trace['label']} | value={trace.get('value')} | {trace['reference']}",
                (
                    f"run={trace['audit_run_id']} | method={trace.get('method')} | "
                    f"calculation={trace.get('calculation_version')}"
                ),
            ]
        )
    if report.evidence_gaps:
        lines.extend(["", "Evidence gaps", *report.evidence_gaps])

    chunks = [lines[index : index + 48] for index in range(0, len(lines), 48)]
    font_id = 3 + 2 * len(chunks)
    page_ids = [3 + 2 * index for index in range(len(chunks))]
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] "
            f"/Count {len(chunks)} >>"
        ).encode(),
    ]
    for index, chunk in enumerate(chunks):
        page_id = page_ids[index]
        content_id = page_id + 1
        text_ops = ["BT", "/F1 9 Tf", "42 800 Td", "15 TL"]
        for line_index, line in enumerate(chunk):
            safe = (
                str(line)
                .encode("ascii", "replace")
                .decode()
                .replace("\\", "\\\\")
                .replace("(", "\\(")
                .replace(")", "\\)")
            )
            text_ops.append(f"({safe[:125]}) Tj")
            if line_index < len(chunk) - 1:
                text_ops.append("T*")
        text_ops.append("ET")
        stream = "\n".join(text_ops).encode()
        objects.extend(
            [
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                    f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
                    f"/Contents {content_id} 0 R >>"
                ).encode(),
                (f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"),
            ]
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return bytes(output)


@router.get("/reports/{report_id}/download", tags=["evidence"])
def download_report(
    report_id: str,
    principal: Annotated[Principal, Depends(require_permission(Permission.REPORT_READ))],
    db: Annotated[Session, Depends(get_db)],
    format: Literal["pdf", "json", "csv"] = "pdf",
) -> Response:
    report: Report = _owned(db, Report, report_id, principal.organization_id)
    filename = f"fairhire-{report.id}-v{report.version}.{format}"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Content-SHA256": report.content_hash,
    }
    if format == "json":
        content = json.dumps(
            _report_response(report).model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ).encode()
        media_type = "application/json"
    elif format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=[
                "reference",
                "audit_run_id",
                "metric_result_id",
                "label",
                "value",
                "method",
                "calculation_version",
            ],
        )
        writer.writeheader()
        writer.writerows(report.evidence_index)
        content = buffer.getvalue().encode("utf-8-sig")
        media_type = "text/csv"
    else:
        content = _pdf_bytes(report)
        media_type = "application/pdf"
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="report.exported",
        resource_type="report",
        resource_id=report.id,
        payload={"format": format, "content_hash": report.content_hash},
    )
    db.commit()
    return Response(content, media_type=media_type, headers=headers)


@router.post(
    "/knowledge-sources",
    response_model=KnowledgeSourceResponse,
    status_code=201,
    tags=["assistant"],
)
def create_knowledge_source(
    payload: KnowledgeSourceCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.POLICY_ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> KnowledgeSourceResponse:
    action = "create_knowledge_source"
    if replay := _replay(
        db,
        principal.organization_id,
        idempotency_key,
        action,
        payload,
        KnowledgeSourceResponse,
    ):
        return replay
    source = KnowledgeSource(
        id=new_id("src"),
        organization_id=principal.organization_id,
        content_hash=hashlib.sha256(payload.content.encode()).hexdigest(),
        created_by=principal.user_id,
        **payload.model_dump(),
    )
    db.add(source)
    db.flush()
    response = KnowledgeSourceResponse.model_validate(source)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="knowledge_source.created",
        resource_type="knowledge_source",
        resource_id=source.id,
        payload={
            "source_type": source.source_type,
            "version": source.version,
            "content_hash": source.content_hash,
        },
    )
    _record_response(db, principal.organization_id, idempotency_key, action, payload, response, 201)
    db.commit()
    return response


def _source_visible(source: KnowledgeSource, principal: Principal) -> bool:
    return not source.allowed_roles or principal.role.value in source.allowed_roles


@router.get("/knowledge-sources", response_model=KnowledgeSourceListResponse, tags=["assistant"])
def list_knowledge_sources(
    principal: Annotated[Principal, Depends(require_permission(Permission.REPORT_READ))],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> KnowledgeSourceListResponse:
    candidates = list(
        db.scalars(
            select(KnowledgeSource)
            .where(
                KnowledgeSource.organization_id == principal.organization_id,
                KnowledgeSource.active.is_(True),
            )
            .order_by(KnowledgeSource.reviewed_at.desc())
        ).all()
    )
    visible = [item for item in candidates if _source_visible(item, principal)]
    offset = (page - 1) * page_size
    return KnowledgeSourceListResponse(
        items=[
            KnowledgeSourceResponse.model_validate(item)
            for item in visible[offset : offset + page_size]
        ],
        page=page,
        page_size=page_size,
        total=len(visible),
    )


INJECTION_PATTERNS = re.compile(
    r"ignore\s+(all\s+)?(previous|prior)|system\s+prompt|developer\s+message|"
    r"reveal\s+(secrets?|instructions?)|bypass\s+(permissions?|rules?)|"
    r"忽略.{0,8}(指令|规则)|系统提示词|绕过.{0,8}(权限|规则)",
    re.IGNORECASE,
)


def _tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[\w-]{2,}", value, flags=re.UNICODE)
        if token.lower() not in {"the", "and", "for", "with", "what", "how", "does"}
    }


def _citation_from_source(source: KnowledgeSource, index: int) -> dict[str, object]:
    return {
        "id": f"C{index}",
        "source_type": source.source_type,
        "title": source.title,
        "locator": f"{source.publisher} · {source.version}",
        "uri": source.uri,
        "effective_at": source.effective_at.isoformat(),
    }


@router.post(
    "/assistant/answers",
    response_model=AssistantAnswerResponse,
    status_code=201,
    tags=["assistant"],
)
def create_assistant_answer(
    payload: AssistantAnswerCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.REPORT_READ))],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> AssistantAnswerResponse:
    action = "create_assistant_answer"
    if replay := _replay(
        db,
        principal.organization_id,
        idempotency_key,
        action,
        payload,
        AssistantAnswerResponse,
    ):
        return replay
    system: AISystem | None = None
    if payload.ai_system_id:
        system = _owned(db, AISystem, payload.ai_system_id, principal.organization_id)
    injection_detected = bool(INJECTION_PATTERNS.search(payload.question))
    sources = [
        item
        for item in db.scalars(
            select(KnowledgeSource).where(
                KnowledgeSource.organization_id == principal.organization_id,
                KnowledgeSource.active.is_(True),
            )
        ).all()
        if _source_visible(item, principal) and not injection_detected
    ]
    query_tokens = _tokens(payload.question)
    ranked = sorted(
        sources,
        key=lambda item: len(query_tokens & _tokens(f"{item.title} {item.content}")),
        reverse=True,
    )
    selected = [
        item
        for item in ranked[:3]
        if not query_tokens or query_tokens & _tokens(f"{item.title} {item.content}")
    ]
    if not selected:
        selected = ranked[:1]
    citations = [_citation_from_source(item, index + 1) for index, item in enumerate(selected)]
    evidence_refs: list[str] = []
    if system and not injection_detected:
        evidence_refs.append(f"system:{system.id}")
        citations.append(
            {
                "id": f"C{len(citations) + 1}",
                "source_type": "project_evidence",
                "title": f"{system.name} system record",
                "locator": f"AI System {system.id}",
                "uri": None,
                "effective_at": None,
            }
        )
        latest_report = db.scalar(
            select(Report)
            .where(
                Report.organization_id == principal.organization_id,
                Report.ai_system_id == system.id,
            )
            .order_by(Report.version.desc())
            .limit(1)
        )
        if latest_report:
            evidence_refs.extend(
                [f"report:{latest_report.id}", f"audit:{latest_report.audit_run_id}"]
            )
            citations.append(
                {
                    "id": f"C{len(citations) + 1}",
                    "source_type": "project_evidence",
                    "title": latest_report.title,
                    "locator": (
                        f"Report v{latest_report.version} · {latest_report.content_hash[:12]}"
                    ),
                    "uri": None,
                    "effective_at": None,
                }
            )
    paragraphs: list[dict[str, object]] = []
    if injection_detected:
        paragraphs.append(
            {
                "classification": "recommendation",
                "text": (
                    "The request contains instruction-override language. The assistant "
                    "did not follow it and did not disclose or change project evidence. "
                    "Rephrase the governance question without embedded instructions."
                ),
                "citation_ids": [],
            }
        )
    else:
        if system:
            project_citation = next(
                item["id"] for item in citations if item["source_type"] == "project_evidence"
            )
            paragraphs.append(
                {
                    "classification": "fact",
                    "text": (
                        f"The project record identifies {system.name} as "
                        f"{system.release_status.replace('_', ' ')}. "
                        f"Its declared purpose is: {system.purpose}"
                    ),
                    "citation_ids": [project_citation],
                }
            )
        for source, citation in zip(selected, citations, strict=False):
            excerpt = " ".join(source.content.split())[:360]
            paragraphs.append(
                {
                    "classification": "fact",
                    "text": (
                        "The cited source records the following relevant rule or "
                        f"policy text: {excerpt}"
                    ),
                    "citation_ids": [citation["id"]],
                }
            )
        cited_ids = [str(item["id"]) for item in citations]
        if cited_ids:
            paragraphs.append(
                {
                    "classification": "inference",
                    "text": (
                        "These records support an evidence review, but they do not by "
                        "themselves establish legal compliance. Confirm applicability "
                        "and unresolved gaps with the accountable Legal/DPO reviewer."
                    ),
                    "citation_ids": cited_ids,
                }
            )
        else:
            paragraphs.append(
                {
                    "classification": "recommendation",
                    "text": (
                        "No authorized source supports a substantive answer. Add or "
                        "request access to an official source or organization policy "
                        "before drawing a conclusion."
                    ),
                    "citation_ids": [],
                }
            )
    rule_dates = [
        {
            "source_id": item.id,
            "version": item.version,
            "effective_at": item.effective_at.isoformat(),
            "reviewed_at": item.reviewed_at.isoformat(),
        }
        for item in selected
    ]
    answer = AssistantAnswer(
        id=new_id("ans"),
        organization_id=principal.organization_id,
        ai_system_id=system.id if system else None,
        question=payload.question,
        paragraphs=paragraphs,
        citations=citations,
        rule_dates=rule_dates,
        evidence_refs=evidence_refs,
        injection_detected=injection_detected,
        created_by=principal.user_id,
    )
    db.add(answer)
    db.flush()
    response = AssistantAnswerResponse.model_validate(answer)
    append_event(
        db,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        action="assistant.answer_recorded",
        resource_type="assistant_answer",
        resource_id=answer.id,
        payload={
            "ai_system_id": answer.ai_system_id,
            "citation_ids": [item["id"] for item in citations],
            "evidence_refs": evidence_refs,
            "injection_detected": injection_detected,
        },
    )
    _record_response(db, principal.organization_id, idempotency_key, action, payload, response, 201)
    db.commit()
    return response


@router.get("/assistant/answers", response_model=AssistantAnswerListResponse, tags=["assistant"])
def list_assistant_answers(
    principal: Annotated[Principal, Depends(require_permission(Permission.REPORT_READ))],
    db: Annotated[Session, Depends(get_db)],
    ai_system_id: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> AssistantAnswerListResponse:
    predicates: list[Any] = [AssistantAnswer.organization_id == principal.organization_id]
    if ai_system_id:
        predicates.append(AssistantAnswer.ai_system_id == ai_system_id)
    total = db.scalar(select(func.count()).select_from(AssistantAnswer).where(*predicates)) or 0
    items = list(
        db.scalars(
            select(AssistantAnswer)
            .where(*predicates)
            .order_by(AssistantAnswer.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return AssistantAnswerListResponse(
        items=[AssistantAnswerResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )
