from datetime import datetime
from typing import Any

from .app import app

UNSAFE_MODEL_SUFFIXES = (".pkl", ".pickle", ".joblib")
ALLOWED_DATA_SUFFIXES = (".csv", ".parquet", ".jsonl")


def _infer_type(values: list[object]) -> str:
    non_null = [value for value in values if value is not None and value != ""]
    if not non_null:
        return "string"
    if all(isinstance(value, bool) for value in non_null):
        return "boolean"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in non_null):
        return "integer"
    if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in non_null):
        return "number"
    if all(isinstance(value, str) for value in non_null):
        parsed = 0
        for value in non_null:
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                parsed += 1
            except ValueError:
                pass
        if parsed == len(non_null):
            return "datetime"
        unique_ratio = len(set(non_null)) / len(non_null)
        if len(non_null) >= 3 and unique_ratio <= 0.2:
            return "category"
    return "string"


def infer_schema(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Infer conservative field metadata from a bounded, scanner-approved preview."""
    if not rows:
        raise ValueError("At least one preview row is required for schema inference")
    names = list(rows[0])
    if any(set(row) != set(names) for row in rows):
        raise ValueError("Preview rows do not have a stable schema")
    return [
        {
            "name": name,
            "inferred_type": _infer_type([row[name] for row in rows]),
            "nullable": any(row[name] is None or row[name] == "" for row in rows),
            "missing_rate": sum(row[name] is None or row[name] == "" for row in rows) / len(rows),
        }
        for name in names
    ]


@app.task(name="platform.health")
def health() -> dict[str, str]:
    return {"status": "ok", "worker": "fairhire-analytics"}


@app.task(
    bind=True, name="audit.prepare", autoretry_for=(OSError,), retry_backoff=True, max_retries=3
)
def prepare_audit(
    self: Any,
    *,
    organization_id: str,
    audit_run_id: str,
    dataset_id: str,
    artifact_key: str,
    job_id: str | None = None,
) -> dict[str, str]:
    """Validate orchestration metadata without loading or executing customer model code."""
    if artifact_key.lower().endswith(UNSAFE_MODEL_SUFFIXES):
        raise ValueError(
            "Unsafe serialized models are not accepted; provide predictions, ONNX, "
            "or a controlled endpoint"
        )
    expected_prefix = f"{organization_id}/systems/"
    owns_dataset = f"/datasets/{dataset_id}/" in artifact_key
    if not artifact_key.startswith(expected_prefix) or not owns_dataset:
        raise ValueError("Artifact key is outside the organization/dataset boundary")
    return {
        "status": "ready",
        "audit_run_id": audit_run_id,
        "dataset_id": dataset_id,
        "artifact_key": artifact_key,
        "job_id": job_id or "untracked",
    }


@app.task(
    bind=True,
    name="ingestion.inspect",
    autoretry_for=(OSError,),
    retry_backoff=True,
    max_retries=3,
)
def inspect_dataset(
    self: Any,
    *,
    organization_id: str,
    dataset_id: str,
    artifact_key: str,
    filename: str,
    scanner_reference: str,
    scan_status: str,
    preview_rows: list[dict[str, object]],
) -> dict[str, object]:
    """Accept metadata only after the external malware scanner reports a clean object."""
    suffix = filename.lower().rsplit(".", maxsplit=1)[-1]
    if f".{suffix}" not in ALLOWED_DATA_SUFFIXES:
        raise ValueError("Only CSV, Parquet, and JSONL datasets are accepted")
    expected_prefix = f"{organization_id}/systems/"
    if not artifact_key.startswith(expected_prefix) or f"/{dataset_id}/" not in artifact_key:
        raise ValueError("Artifact key is outside the organization/dataset boundary")
    if scan_status != "clean" or not scanner_reference:
        raise ValueError("Dataset must have a clean malware scan before schema inference")
    return {
        "status": "mapped_pending",
        "dataset_id": dataset_id,
        "scanner_reference": scanner_reference,
        "inferred_fields": infer_schema(preview_rows),
    }
