import pytest

from fairhire_worker.tasks import prepare_audit


def test_prepare_audit_rejects_pickle() -> None:
    with pytest.raises(ValueError, match="Unsafe serialized models"):
        prepare_audit.run(
            organization_id="org-1",
            audit_run_id="run-1",
            artifact_key="org-1/audit-runs/run-1/model.pkl",
        )


def test_prepare_audit_enforces_object_prefix() -> None:
    with pytest.raises(ValueError, match="outside"):
        prepare_audit.run(
            organization_id="org-1",
            audit_run_id="run-1",
            artifact_key="org-2/audit-runs/run-1/data.parquet",
        )
