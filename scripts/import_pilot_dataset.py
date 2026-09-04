"""Import a scanner-approved pilot CSV through the same signed-upload path as the UI."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx


def _post(
    client: httpx.Client,
    path: str,
    payload: dict[str, object],
    headers: dict[str, str],
    key: str,
    scanner_attestation: str | None = None,
) -> dict[str, object]:
    request_headers = {**headers, "Idempotency-Key": key}
    if scanner_attestation:
        request_headers["X-Scanner-Attestation"] = scanner_attestation
    response = client.post(path, json=payload, headers=request_headers)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--system-id", required=True)
    parser.add_argument("--model-version-id", required=True)
    parser.add_argument("--identifier", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--timestamp", required=True)
    parser.add_argument("--protected", action="append", default=[])
    parser.add_argument("--label")
    parser.add_argument("--prediction")
    parser.add_argument("--source", required=True)
    parser.add_argument("--lawful-basis-ref", required=True)
    parser.add_argument("--sensitive-attribute-necessity")
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument("--scanner-reference", required=True)
    parser.add_argument("--scanner-attestation")
    parser.add_argument(
        "--api-url", default=os.getenv("FAIRHIRE_API_URL", "http://127.0.0.1:8000/v1")
    )
    parser.add_argument(
        "--organization-id", default=os.getenv("FAIRHIRE_ORGANIZATION_ID", "org-northstar")
    )
    parser.add_argument(
        "--dev-user", default=os.getenv("FAIRHIRE_DEV_USER", "maya.chen@fairhire.test")
    )
    args = parser.parse_args()
    if not args.csv_file.is_file() or args.csv_file.suffix.lower() != ".csv":
        parser.error("csv_file must be an existing .csv file")
    if not 1 <= args.retention_days <= 365:
        parser.error("--retention-days must be between 1 and 365")

    payload = args.csv_file.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    with args.csv_file.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            parser.error("CSV must contain a header row")
        rows = list(reader)
    if not rows:
        parser.error("CSV must contain at least one data row")
    required = {args.identifier, args.decision, args.timestamp, *args.protected}
    missing = required.difference(reader.fieldnames)
    if missing:
        parser.error(f"CSV is missing mapped fields: {', '.join(sorted(missing))}")

    marker = uuid4().hex
    auth_headers = {
        "X-Organization-ID": args.organization_id,
        "X-Dev-User": args.dev_user,
    }
    with httpx.Client(base_url=args.api_url, timeout=60) as client:
        upload = _post(
            client,
            "/datasets/initiate-upload",
            {
                "ai_system_id": args.system_id,
                "model_version_id": args.model_version_id,
                "filename": args.csv_file.name,
                "content_type": "text/csv",
                "size_bytes": len(payload),
                "sha256": digest,
            },
            auth_headers,
            f"pilot-upload-{marker}",
        )
        object_response = httpx.put(
            str(upload["upload_url"]),
            headers=dict(upload["upload_headers"]),  # type: ignore[arg-type]
            content=payload,
            timeout=60,
        )
        object_response.raise_for_status()
        fields = [
            {
                "name": name,
                "inferred_type": "string",
                "nullable": any(not row.get(name, "").strip() for row in rows[:1000]),
                "missing_rate": sum(not row.get(name, "").strip() for row in rows[:1000])
                / min(len(rows), 1000),
            }
            for name in reader.fieldnames
        ]
        dataset = _post(
            client,
            f"/datasets/{upload['dataset_id']}/complete-upload",
            {
                "content_hash": digest,
                "scanner_reference": args.scanner_reference,
                "scan_status": "clean",
                "row_count": len(rows),
                "inferred_fields": fields,
            },
            auth_headers,
            f"pilot-complete-{marker}",
            args.scanner_attestation,
        )
        by_name = {str(field["name"]): field for field in dataset["fields"]}  # type: ignore[union-attr]
        roles: dict[str, str] = {
            args.identifier: "identifier",
            args.decision: "decision",
            args.timestamp: "timestamp",
            **{name: "protected_attribute" for name in args.protected},
        }
        if args.label:
            roles[args.label] = "label"
        if args.prediction:
            roles[args.prediction] = "prediction"
        mappings = [
            {
                "field_id": by_name[name]["id"],
                "role": role,
                "vault_only": role == "protected_attribute",
            }
            for name, role in roles.items()
        ]
        imported = _post(
            client,
            f"/datasets/{dataset['id']}/field-mappings",
            {
                "mappings": mappings,
                "source": args.source,
                "collection_purpose": "Monitored FairHire pilot fairness audit",
                "lawful_basis_ref": args.lawful_basis_ref,
                "sensitive_attribute_necessity": args.sensitive_attribute_necessity,
                "retention_expires_at": (
                    datetime.now(UTC) + timedelta(days=args.retention_days)
                ).isoformat(),
            },
            auth_headers,
            f"pilot-map-{marker}",
        )
    print(f"Imported pilot dataset {imported['id']} with {len(rows)} rows; status=ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
