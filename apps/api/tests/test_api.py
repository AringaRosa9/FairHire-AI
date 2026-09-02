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
