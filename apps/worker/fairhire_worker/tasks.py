import os
from datetime import UTC, datetime
from typing import Any, cast

from fairhire_domain.audit import CALCULATION_VERSION, run_binary_audit
from fairhire_domain.ledger import event_hash

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
        string_values = [value for value in non_null if isinstance(value, str)]
        for value in string_values:
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


@app.task(name="platform.health")  # type: ignore[untyped-decorator]
def health() -> dict[str, str]:
    return {"status": "ok", "worker": "fairhire-analytics"}


@app.task(  # type: ignore[untyped-decorator]
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


def _load_rows(artifact_key: str, dataset_format: str) -> list[dict[str, object]]:
    """Read an approved object without exposing a public URL or executing customer code."""
    import boto3  # type: ignore[import-not-found]
    import polars as pl  # type: ignore[import-not-found]

    client = boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT", "http://localhost:9100"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY", "fairhire"),
        aws_secret_access_key=os.getenv("S3_SECRET_KEY", "fairhire_local_only"),
        region_name=os.getenv("S3_REGION", "us-east-1"),
    )
    response = client.get_object(Bucket=os.getenv("S3_BUCKET", "fairhire-local"), Key=artifact_key)
    payload = response["Body"].read()
    if dataset_format == "csv":
        frame = pl.read_csv(payload)
    elif dataset_format == "parquet":
        frame = pl.read_parquet(payload)
    elif dataset_format == "jsonl":
        frame = pl.read_ndjson(payload)
    else:
        raise ValueError("Only CSV, Parquet, and JSONL datasets are accepted")
    return cast(list[dict[str, object]], frame.to_dicts())


def _persist_audit_result(
    *,
    organization_id: str,
    audit_run_id: str,
    job_id: str,
    result: dict[str, object],
) -> None:
    import uuid

    import psycopg
    from psycopg.types.json import Jsonb

    database_url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    now = datetime.now(UTC)
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.organization_id', %s, true)", (organization_id,))
        cursor.execute(
            "UPDATE background_jobs SET status = 'running', progress = 70, updated_at = %s "
            "WHERE id = %s AND organization_id = %s",
            (now, job_id, organization_id),
        )
        cursor.execute(
            "DELETE FROM metric_results WHERE audit_run_id = %s AND organization_id = %s",
            (audit_run_id, organization_id),
        )
        metrics = cast(list[dict[str, object]], result["metrics"])
        for metric in metrics:
            cursor.execute(
                """
                INSERT INTO metric_results (
                  id, organization_id, audit_run_id, category, metric_key,
                  protected_attribute, reference_group, comparison_group, value,
                  lower_bound, upper_bound, status, threshold, threshold_operator,
                  threshold_source, raw_counts, method, calculation_version, details, created_at
                ) VALUES (
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    f"met_{uuid.uuid4().hex}",
                    organization_id,
                    audit_run_id,
                    metric["category"],
                    metric["metric_key"],
                    metric.get("protected_attribute"),
                    metric.get("reference_group"),
                    metric.get("comparison_group"),
                    metric.get("value"),
                    metric.get("lower_bound"),
                    metric.get("upper_bound"),
                    metric["status"],
                    metric.get("threshold"),
                    metric.get("threshold_operator"),
                    Jsonb(metric.get("threshold_source", {})),
                    Jsonb(metric.get("raw_counts", {})),
                    metric["method"],
                    CALCULATION_VERSION,
                    Jsonb(metric.get("details", {})),
                    now,
                ),
            )
        cursor.execute(
            "UPDATE audit_runs SET status = 'succeeded', completed_at = %s, "
            "error_code = NULL, error_detail = NULL "
            "WHERE id = %s AND organization_id = %s",
            (now, audit_run_id, organization_id),
        )
        cursor.execute(
            "UPDATE background_jobs SET status = 'succeeded', progress = 100, updated_at = %s, "
            "error_code = NULL, error_detail = NULL "
            "WHERE id = %s AND organization_id = %s",
            (now, job_id, organization_id),
        )
        cursor.execute(
            "SELECT current_hash FROM audit_events WHERE organization_id = %s "
            "ORDER BY occurred_at DESC, id DESC LIMIT 1 FOR UPDATE",
            (organization_id,),
        )
        previous = cursor.fetchone()
        previous_hash = previous[0] if previous else None
        event_id = f"evt_{uuid.uuid4().hex}"
        event_payload: dict[str, object] = {
            "metric_count": len(metrics),
            "calculation_version": CALCULATION_VERSION,
            "status_counts": result.get("status_counts", {}),
            "correlation_id": f"corr_{uuid.uuid4().hex}",
        }
        current_hash = event_hash(
            event_id=event_id,
            organization_id=organization_id,
            actor_id="fairhire-analytics",
            action="audit_run.metrics_published",
            resource_type="audit_run",
            resource_id=audit_run_id,
            payload=event_payload,
            previous_hash=previous_hash,
            occurred_at=now,
        )
        cursor.execute(
            "INSERT INTO audit_events (id, organization_id, actor_id, action, resource_type, "
            "resource_id, payload, previous_hash, current_hash, occurred_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                event_id,
                organization_id,
                "fairhire-analytics",
                "audit_run.metrics_published",
                "audit_run",
                audit_run_id,
                Jsonb(event_payload),
                previous_hash,
                current_hash,
                now,
            ),
        )


def _set_run_state(
    *,
    organization_id: str,
    audit_run_id: str,
    job_id: str,
    status: str,
    progress: int,
    error: Exception | None = None,
) -> None:
    import psycopg

    database_url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    now = datetime.now(UTC)
    error_code = type(error).__name__ if error else None
    error_detail = str(error)[:4000] if error else None
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.organization_id', %s, true)", (organization_id,))
        cursor.execute(
            "UPDATE audit_runs SET status = %s, started_at = COALESCE(started_at, %s), "
            "completed_at = CASE WHEN %s IN ('failed', 'cancelled') THEN %s "
            "ELSE completed_at END, error_code = %s, error_detail = %s "
            "WHERE id = %s AND organization_id = %s",
            (
                status,
                now,
                status,
                now,
                error_code,
                error_detail,
                audit_run_id,
                organization_id,
            ),
        )
        cursor.execute(
            "UPDATE background_jobs SET status = %s, progress = %s, error_code = %s, "
            "error_detail = %s, updated_at = %s WHERE id = %s AND organization_id = %s",
            (status, progress, error_code, error_detail, now, job_id, organization_id),
        )


def _cancellation_requested(*, organization_id: str, job_id: str) -> bool:
    import psycopg

    database_url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.organization_id', %s, true)", (organization_id,))
        cursor.execute(
            "SELECT cancellation_requested FROM background_jobs "
            "WHERE id = %s AND organization_id = %s",
            (job_id, organization_id),
        )
        row = cursor.fetchone()
        return bool(row and row[0])


@app.task(bind=True, name="audit.analyze")  # type: ignore[untyped-decorator]
def analyze_audit(
    self: Any,
    *,
    organization_id: str,
    audit_run_id: str,
    dataset_id: str,
    artifact_key: str,
    dataset_format: str,
    config: dict[str, object],
    job_id: str,
) -> dict[str, object]:
    """Load a vault-approved dataset, compute metrics, and atomically publish results."""
    try:
        prepare_audit.run(
            organization_id=organization_id,
            audit_run_id=audit_run_id,
            dataset_id=dataset_id,
            artifact_key=artifact_key,
            job_id=job_id,
        )
        if _cancellation_requested(organization_id=organization_id, job_id=job_id):
            _set_run_state(
                organization_id=organization_id,
                audit_run_id=audit_run_id,
                job_id=job_id,
                status="cancelled",
                progress=100,
            )
            return {"status": "cancelled", "audit_run_id": audit_run_id}
        _set_run_state(
            organization_id=organization_id,
            audit_run_id=audit_run_id,
            job_id=job_id,
            status="running",
            progress=10,
        )
        rows = _load_rows(artifact_key, dataset_format)
        result = run_binary_audit(rows, config)
        if _cancellation_requested(organization_id=organization_id, job_id=job_id):
            _set_run_state(
                organization_id=organization_id,
                audit_run_id=audit_run_id,
                job_id=job_id,
                status="cancelled",
                progress=100,
            )
            return {"status": "cancelled", "audit_run_id": audit_run_id}
        _persist_audit_result(
            organization_id=organization_id,
            audit_run_id=audit_run_id,
            job_id=job_id,
            result=result,
        )
    except Exception as error:
        _set_run_state(
            organization_id=organization_id,
            audit_run_id=audit_run_id,
            job_id=job_id,
            status="failed",
            progress=100,
            error=error,
        )
        raise
    return {
        "status": "succeeded",
        "audit_run_id": audit_run_id,
        "metric_count": len(cast(list[object], result["metrics"])),
        "calculation_version": CALCULATION_VERSION,
    }


@app.task(  # type: ignore[untyped-decorator]
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
