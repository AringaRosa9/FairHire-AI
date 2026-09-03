from fastapi.testclient import TestClient


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
