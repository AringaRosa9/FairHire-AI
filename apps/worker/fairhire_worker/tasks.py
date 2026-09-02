from typing import Any

from .app import app

UNSAFE_MODEL_SUFFIXES = (".pkl", ".pickle", ".joblib")


@app.task(name="platform.health")
def health() -> dict[str, str]:
    return {"status": "ok", "worker": "fairhire-analytics"}


@app.task(
    bind=True, name="audit.prepare", autoretry_for=(OSError,), retry_backoff=True, max_retries=3
)
def prepare_audit(
    self: Any, *, organization_id: str, audit_run_id: str, artifact_key: str
) -> dict[str, str]:
    """Validate orchestration metadata without loading or executing customer model code."""
    if artifact_key.lower().endswith(UNSAFE_MODEL_SUFFIXES):
        raise ValueError(
            "Unsafe serialized models are not accepted; provide predictions, ONNX, "
            "or a controlled endpoint"
        )
    expected_prefix = f"{organization_id}/audit-runs/{audit_run_id}/"
    if not artifact_key.startswith(expected_prefix):
        raise ValueError("Artifact key is outside the organization/audit-run boundary")
    return {"status": "ready", "audit_run_id": audit_run_id, "artifact_key": artifact_key}
