"""Opt-in smoke check for the Week 3-5 API, PostgreSQL, and MinIO path."""

import hashlib
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx

BASE_URL = os.getenv("FAIRHIRE_API_URL", "http://127.0.0.1:8001/v1")
HEADERS = {
    "X-Organization-ID": "org-northstar",
    "X-Dev-User": "maya.chen@fairhire.test",
}


def post(client: httpx.Client, path: str, payload: dict[str, object], key: str) -> dict:
    response = client.post(
        path,
        json=payload,
        headers={**HEADERS, "Idempotency-Key": key},
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    marker = uuid4().hex[:8]
    data = (
        b"candidate_id,selected,decision_at,gender\n"
        b"anon-1,true,2026-08-01T10:00:00Z,A\n"
        b"anon-2,false,2026-08-02T10:00:00Z,B\n"
    )
    digest = hashlib.sha256(data).hexdigest()
    with httpx.Client(base_url=BASE_URL, timeout=20) as client:
        system = post(
            client,
            "/ai-systems",
            {
                "name": f"Integration screening {marker}",
                "purpose": "Prioritizes applications for a human recruiter to review",
                "actual_use": "Ranks a recruiting platform export",
                "affected_people": "Applicants in Germany",
                "decision_impact": "screening",
                "human_oversight": "A recruiter reviews each recommendation",
                "organization_roles": ["provider", "deployer"],
                "provider_type": "internal",
                "jurisdictions": ["EU", "DE"],
                "owner_name": "Maya Chen",
            },
            f"smoke-system-{marker}",
        )
        post(
            client,
            f"/ai-systems/{system['id']}/assessments",
            {
                "organization_roles": ["provider", "deployer"],
                "employment_use": True,
            },
            f"smoke-assessment-{marker}",
        )
        model = post(
            client,
            f"/ai-systems/{system['id']}/model-versions",
            {"version_label": marker, "source_type": "prediction_output"},
            f"smoke-model-{marker}",
        )
        upload = post(
            client,
            "/datasets/initiate-upload",
            {
                "ai_system_id": system["id"],
                "model_version_id": model["id"],
                "filename": "decisions.csv",
                "content_type": "text/csv",
                "size_bytes": len(data),
                "sha256": digest,
            },
            f"smoke-upload-{marker}",
        )
        object_response = httpx.put(
            upload["upload_url"],
            headers=upload["upload_headers"],
            content=data,
            timeout=20,
        )
        object_response.raise_for_status()
        dataset = post(
            client,
            f"/datasets/{upload['dataset_id']}/complete-upload",
            {
                "content_hash": digest,
                "scanner_reference": f"development-scanner:{marker}",
                "scan_status": "clean",
                "row_count": 2,
                "inferred_fields": [
                    {"name": "candidate_id", "inferred_type": "string"},
                    {"name": "selected", "inferred_type": "boolean"},
                    {"name": "decision_at", "inferred_type": "datetime"},
                    {"name": "gender", "inferred_type": "category"},
                ],
            },
            f"smoke-complete-{marker}",
        )
        fields = {field["name"]: field for field in dataset["fields"]}
        post(
            client,
            f"/datasets/{dataset['id']}/field-mappings",
            {
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
                "source": "Integration export",
                "collection_purpose": "Verify the ingestion control path",
                "lawful_basis_ref": "TEST-DPIA",
                "sensitive_attribute_necessity": "Test-only aggregate fairness field",
                "retention_expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            },
            f"smoke-mapping-{marker}",
        )
        run = post(
            client,
            "/audit-runs",
            {
                "ai_system_id": system["id"],
                "model_version_id": model["id"],
                "dataset_id": dataset["id"],
                "policy_pack_version": "eu-core+de@2026.09",
            },
            f"smoke-run-{marker}",
        )
        verification = client.get("/audit-events/verify", headers=HEADERS)
        verification.raise_for_status()
        assert verification.json()["valid"] is True
        print(f"Verified first registration run {run['id']} with job {run['job_id']}")


if __name__ == "__main__":
    main()
