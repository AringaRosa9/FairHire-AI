from datetime import UTC, datetime, timedelta

import pytest
from fairhire_domain.access import Role
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fairhire_api.main import app
from fairhire_api.models import AuditRun, Finding, MetricResult
from fairhire_api.security import Principal, get_principal


def test_health_is_public_and_versioned(client: TestClient) -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_session_exposes_effective_permissions(client: TestClient) -> None:
    response = client.get("/v1/session")
    assert response.status_code == 200
    assert response.json()["organization_id"] == "org-one"
    assert "system:read" in response.json()["permissions"]


def test_system_list_filters_by_organization_even_without_rls(client: TestClient) -> None:
    response = client.get("/v1/ai-systems")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["id"] for item in payload["items"]] == ["sys-one"]
    assert "Other Tenant Secret" not in response.text


def test_writes_require_idempotency_key(client: TestClient) -> None:
    response = client.post(
        "/v1/ai-systems",
        json={
            "name": "New System",
            "purpose": "Screens applications for recruiter review and decision support",
            "provider_type": "internal",
            "jurisdictions": ["EU"],
            "owner_name": "Maya Chen",
        },
    )
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")


def test_first_registration_creates_traceable_audit_run(client: TestClient) -> None:
    system_response = client.post(
        "/v1/ai-systems",
        headers={"Idempotency-Key": "system-create-1"},
        json={
            "name": "Screening assistant",
            "purpose": "Prioritizes applications for a human recruiter to review",
            "actual_use": "Ranks incoming applications in the recruiting workspace",
            "affected_people": "Applicants for roles in Germany",
            "decision_impact": "screening",
            "human_oversight": "A recruiter reviews every recommendation before shortlisting",
            "organization_roles": ["provider", "deployer"],
            "provider_type": "internal",
            "jurisdictions": ["EU", "DE"],
            "owner_name": "Maya Chen",
        },
    )
    assert system_response.status_code == 201
    system = system_response.json()
    replay = client.post(
        "/v1/ai-systems",
        headers={"Idempotency-Key": "system-create-1"},
        json={
            "name": "Screening assistant",
            "purpose": "Prioritizes applications for a human recruiter to review",
            "actual_use": "Ranks incoming applications in the recruiting workspace",
            "affected_people": "Applicants for roles in Germany",
            "decision_impact": "screening",
            "human_oversight": "A recruiter reviews every recommendation before shortlisting",
            "organization_roles": ["provider", "deployer"],
            "provider_type": "internal",
            "jurisdictions": ["EU", "DE"],
            "owner_name": "Maya Chen",
        },
    )
    assert replay.json()["id"] == system["id"]

    assessment = client.post(
        f"/v1/ai-systems/{system['id']}/assessments",
        headers={"Idempotency-Key": "assessment-create-1"},
        json={
            "organization_roles": ["provider", "deployer"],
            "employment_use": True,
        },
    )
    assert assessment.status_code == 201
    assert assessment.json()["risk_class"] == "high_risk"
    assert assessment.json()["legal_review_required"] is True

    model_response = client.post(
        f"/v1/ai-systems/{system['id']}/model-versions",
        headers={"Idempotency-Key": "model-create-1"},
        json={
            "version_label": "2026.09",
            "source_type": "prediction_output",
            "content_hash": "b" * 64,
        },
    )
    assert model_response.status_code == 201
    model = model_response.json()

    upload_response = client.post(
        "/v1/datasets/initiate-upload",
        headers={"Idempotency-Key": "upload-create-1"},
        json={
            "ai_system_id": system["id"],
            "model_version_id": model["id"],
            "filename": "decisions.csv",
            "content_type": "text/csv",
            "size_bytes": 128,
            "sha256": "a" * 64,
        },
    )
    assert upload_response.status_code == 201
    assert "/fairhire-local/org-one/systems/" in upload_response.json()["upload_url"]
    dataset_id = upload_response.json()["dataset_id"]

    complete_response = client.post(
        f"/v1/datasets/{dataset_id}/complete-upload",
        headers={"Idempotency-Key": "upload-complete-1"},
        json={
            "content_hash": "a" * 64,
            "scanner_reference": "development-scanner:test-clean",
            "scan_status": "clean",
            "row_count": 250,
            "inferred_fields": [
                {"name": "candidate_id", "inferred_type": "string"},
                {"name": "selected", "inferred_type": "boolean"},
                {"name": "decision_at", "inferred_type": "datetime"},
                {"name": "gender", "inferred_type": "category", "nullable": True},
            ],
        },
    )
    assert complete_response.status_code == 200
    fields = {field["name"]: field for field in complete_response.json()["fields"]}

    mapping_response = client.post(
        f"/v1/datasets/{dataset_id}/field-mappings",
        headers={"Idempotency-Key": "mapping-create-1"},
        json={
            "mappings": [
                {"field_id": fields["candidate_id"]["id"], "role": "identifier"},
                {"field_id": fields["selected"]["id"], "role": "decision"},
                {"field_id": fields["decision_at"]["id"], "role": "timestamp"},
                {
                    "field_id": fields["gender"]["id"],
                    "role": "protected_attribute",
                    "vault_only": True,
                },
            ],
            "source": "Recruiting platform export",
            "collection_purpose": "Evaluate selection outcomes",
            "lawful_basis_ref": "DPIA-2026-014",
            "sensitive_attribute_necessity": "Aggregate bias testing approved by the DPO",
            "retention_expires_at": "2026-10-03T00:00:00Z",
        },
    )
    assert mapping_response.status_code == 200
    assert mapping_response.json()["upload_status"] == "ready"

    run_response = client.post(
        "/v1/audit-runs",
        headers={"Idempotency-Key": "run-create-1"},
        json={
            "ai_system_id": system["id"],
            "model_version_id": model["id"],
            "dataset_id": dataset_id,
            "policy_pack_version": "eu-core+de@2026.09",
        },
    )
    assert run_response.status_code == 202
    run = run_response.json()
    assert run["status"] == "queued"
    assert client.get(f"/v1/jobs/{run['job_id']}").json()["attempt"] == 1

    cancel_response = client.post(
        f"/v1/audit-runs/{run['id']}/cancel",
        headers={"Idempotency-Key": "cancel-run-1"},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelling"
    assert client.get("/v1/audit-events/verify").json()["valid"] is True


def test_tenant_path_ids_do_not_leak_resources(client: TestClient) -> None:
    assert client.get("/v1/ai-systems/sys-secret").status_code == 404


def test_pickle_upload_is_rejected_with_safe_alternative(client: TestClient) -> None:
    response = client.post(
        "/v1/datasets/initiate-upload",
        headers={"Idempotency-Key": "unsafe-upload"},
        json={
            "ai_system_id": "sys-one",
            "filename": "candidate-model.pkl",
            "content_type": "application/octet-stream",
            "size_bytes": 100,
            "sha256": "a" * 64,
        },
    )
    assert response.status_code == 422
    assert "prediction outputs" in response.json()["detail"]


def test_metric_results_include_uncertainty_counts_and_threshold_provenance(
    client: TestClient,
) -> None:
    response = client.get("/v1/audit-runs/run-metrics/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status_counts"] == {"review_required": 1}
    metric = payload["items"][0]
    assert metric["lower_bound"] == 0.69
    assert metric["raw_counts"]["comparison"]["n"] == 250
    assert metric["threshold_source"]["legal_determination"] is False
    assert metric["calculation_version"] == "fairhire-binary-audit@1.0.0"


def test_metric_results_are_scoped_to_the_audit_run_tenant(client: TestClient) -> None:
    assert client.get("/v1/audit-runs/run-other/metrics").status_code == 404


def test_version_comparison_uses_explicit_same_tenant_baseline(
    client: TestClient, db: Session
) -> None:
    baseline = AuditRun(
        id="run-baseline",
        organization_id="org-one",
        ai_system_id="sys-one",
        model_version_id="model-baseline",
        dataset_id="dataset-baseline",
        policy_pack_version="eu-core+de@2026.08",
        config_snapshot={"random_seed": 42},
        data_fingerprint="b" * 64,
        status="succeeded",
        job_id="job-baseline",
        submitted_by="user-one",
    )
    db.add(baseline)
    db.add(
        MetricResult(
            id="metric-baseline",
            organization_id="org-one",
            audit_run_id=baseline.id,
            category="fairness",
            metric_key="demographic_parity_ratio",
            protected_attribute="gender",
            reference_group="women",
            comparison_group="men",
            value=0.86,
            status="pass",
            threshold=0.8,
            threshold_operator=">=",
            threshold_source={"source_id": "strategy-eu-binary-v1"},
            raw_counts={},
            method="stratified_bootstrap_percentile",
            calculation_version="fairhire-binary-audit@1.0.0",
            details={},
        )
    )
    db.commit()
    response = client.get("/v1/audit-runs/run-metrics/comparison?baseline_run_id=run-baseline")
    assert response.status_code == 200
    comparison = response.json()
    assert comparison["baseline_run_id"] == "run-baseline"
    assert comparison["items"][0]["delta"] == pytest.approx(-0.08)


def test_version_comparison_does_not_leak_cross_tenant_baselines(
    client: TestClient, db: Session
) -> None:
    db.add(
        AuditRun(
            id="run-secret-baseline",
            organization_id="org-other",
            ai_system_id="sys-secret",
            model_version_id="model-secret",
            dataset_id="dataset-secret",
            policy_pack_version="eu-core@2026.08",
            config_snapshot={},
            data_fingerprint="c" * 64,
            status="succeeded",
            job_id="job-secret",
            submitted_by="other",
        )
    )
    db.commit()
    response = client.get(
        "/v1/audit-runs/run-metrics/comparison?baseline_run_id=run-secret-baseline"
    )
    assert response.status_code == 404


def _create_finding(
    client: TestClient,
    *,
    severity: str = "critical",
    key: str = "finding-create",
) -> dict[str, object]:
    response = client.post(
        "/v1/findings",
        headers={"Idempotency-Key": key},
        json={
            "ai_system_id": "sys-one",
            "audit_run_id": "run-metrics",
            "source_metric_id": "metric-one",
            "title": "Selection rate gap exceeds the approved internal threshold",
            "description": (
                "The latest audit shows a material selection-rate gap that requires "
                "an accountable review."
            ),
            "severity": severity,
            "confidence": "high",
            "affected_groups": ["women"],
            "evidence_refs": ["metric:metric-one", "audit:run-metrics"],
            "control_refs": ["POL-FR-02", "EU-AI-ACT-ART-10"],
            "recommended_control": "Review features and retrain before release.",
            "owner_id": "maya@example.test",
            "owner_name": "Maya Chen",
            "due_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()


def _transition(client: TestClient, finding_id: str, target: str, key: str) -> dict[str, object]:
    response = client.post(
        f"/v1/findings/{finding_id}/transition",
        headers={"Idempotency-Key": key},
        json={"status": target, "reason": f"Move to {target} after accountable review"},
    )
    assert response.status_code == 200
    return response.json()


def test_critical_finding_blocks_final_approval_until_valid_exception(
    client: TestClient,
) -> None:
    finding = _create_finding(client)
    finding_id = str(finding["id"])
    assert client.get("/v1/ai-systems/sys-one/release-gate").json()["status"] == "blocked"

    chain_response = client.post(
        "/v1/ai-systems/sys-one/approval-chain",
        headers={"Idempotency-Key": "chain-start"},
        json={"reason": "Release candidate is ready for accountable review"},
    )
    assert chain_response.status_code == 201
    approvals = chain_response.json()["items"]
    for approval in approvals[:2]:
        response = client.post(
            f"/v1/approvals/{approval['id']}/decision",
            headers={"Idempotency-Key": f"approve-{approval['stage']}"},
            json={"decision": "approved", "reason": "Evidence reviewed and accepted"},
        )
        assert response.status_code == 200

    final_response = client.post(
        f"/v1/approvals/{approvals[2]['id']}/decision",
        headers={"Idempotency-Key": "approve-legal-blocked"},
        json={"decision": "approved", "reason": "Legal review completed"},
    )
    assert final_response.status_code == 409
    assert "Critical findings" in final_response.json()["detail"]

    _transition(client, finding_id, "triaged", "finding-triage")
    acceptance = client.post(
        f"/v1/findings/{finding_id}/accept",
        headers={"Idempotency-Key": "finding-accept"},
        json={
            "residual_risk": "A temporary disparity may remain during the monitored pilot.",
            "reason": "Legal and Responsible AI approved a time-limited monitored exception.",
            "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        },
    )
    assert acceptance.status_code == 200
    assert acceptance.json()["status"] == "accepted"

    final_response = client.post(
        f"/v1/approvals/{approvals[2]['id']}/decision",
        headers={"Idempotency-Key": "approve-legal-valid"},
        json={"decision": "approved", "reason": "Time-limited exception verified"},
    )
    assert final_response.status_code == 200
    gate = client.get("/v1/ai-systems/sys-one/release-gate").json()
    assert gate["status"] == "approved"
    assert gate["approved_stages"] == ["responsible_ai", "hr", "legal_dpo"]


def test_expired_risk_acceptance_reopens_and_reblocks_release(
    client: TestClient, db: Session
) -> None:
    finding = _create_finding(client, key="finding-expiry")
    finding_id = str(finding["id"])
    _transition(client, finding_id, "triaged", "expiry-triage")
    accepted = client.post(
        f"/v1/findings/{finding_id}/accept",
        headers={"Idempotency-Key": "expiry-accept"},
        json={
            "residual_risk": "Pilot remains human-reviewed while the control is implemented.",
            "reason": "Short-lived exception for a monitored test window only.",
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert accepted.status_code == 200
    stored = db.get(Finding, finding_id)
    assert stored is not None
    stored.accepted_until = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()

    gate = client.get("/v1/ai-systems/sys-one/release-gate")
    assert gate.status_code == 200
    assert gate.json()["status"] == "blocked"
    assert db.get(Finding, finding_id).status == "open"  # type: ignore[union-attr]
    events = client.get("/v1/audit-events").json()["items"]
    assert any(item["action"] == "finding.acceptance_expired" for item in events)


def test_remediation_task_and_retest_close_the_finding(client: TestClient) -> None:
    finding = _create_finding(client, severity="high", key="finding-remediation")
    finding_id = str(finding["id"])
    _transition(client, finding_id, "triaged", "remediation-triage")
    _transition(client, finding_id, "mitigating", "remediation-start")
    task_response = client.post(
        f"/v1/findings/{finding_id}/tasks",
        headers={"Idempotency-Key": "task-create"},
        json={
            "title": "Remove proxy feature and retrain candidate model",
            "description": "Ship a new model version and attach the change record.",
            "owner_id": "developer@example.test",
            "owner_name": "Model Developer",
            "due_at": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
        },
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["id"]
    task_list = client.get(f"/v1/remediation-tasks?finding_id={finding_id}")
    assert task_list.status_code == 200
    assert task_list.json()["total"] == 1
    assert (
        client.post(
            f"/v1/remediation-tasks/{task_id}/status",
            headers={"Idempotency-Key": "task-start"},
            json={"status": "in_progress", "reason": "Implementation has started"},
        ).status_code
        == 200
    )
    completed = client.post(
        f"/v1/remediation-tasks/{task_id}/status",
        headers={"Idempotency-Key": "task-complete"},
        json={
            "status": "completed",
            "reason": "Replacement model and peer review are complete",
            "evidence_refs": ["model:model-one", "change:CR-104"],
        },
    )
    assert completed.status_code == 200
    assert completed.json()["completed_at"] is not None

    _transition(client, finding_id, "ready_for_retest", "retest-ready")
    retest = client.post(
        f"/v1/findings/{finding_id}/retests",
        headers={"Idempotency-Key": "retest-record"},
        json={
            "audit_run_id": "run-metrics",
            "outcome": "resolved",
            "notes": "The approved rerun is within threshold with adequate sample coverage.",
        },
    )
    assert retest.status_code == 201
    detail = client.get(f"/v1/findings/{finding_id}").json()
    assert detail["status"] == "resolved"
    assert detail["tasks"][0]["status"] == "completed"
    assert detail["retests"][0]["outcome"] == "resolved"


def test_approval_stage_requires_the_matching_accountable_role(client: TestClient) -> None:
    chain = client.post(
        "/v1/ai-systems/sys-one/approval-chain",
        headers={"Idempotency-Key": "role-chain"},
        json={"reason": "Submit evidence for role enforcement review"},
    ).json()
    responsible_ai_approval = chain["items"][0]
    app.dependency_overrides[get_principal] = lambda: Principal(
        user_id="hr-reviewer",
        email="hr@example.test",
        display_name="HR Reviewer",
        organization_id="org-one",
        organization_name="Northstar",
        role=Role.HR_REVIEWER,
    )
    response = client.post(
        f"/v1/approvals/{responsible_ai_approval['id']}/decision",
        headers={"Idempotency-Key": "wrong-role-decision"},
        json={"decision": "approved", "reason": "Attempted out-of-stage approval"},
    )
    assert response.status_code == 403
    assert "cannot decide responsible_ai" in response.json()["detail"]
