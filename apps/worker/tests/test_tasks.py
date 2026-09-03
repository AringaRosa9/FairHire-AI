import pytest

from fairhire_worker.tasks import infer_schema, inspect_dataset, prepare_audit


def test_prepare_audit_rejects_pickle() -> None:
    with pytest.raises(ValueError, match="Unsafe serialized models"):
        prepare_audit.run(
            organization_id="org-1",
            audit_run_id="run-1",
            dataset_id="data-1",
            artifact_key="org-1/systems/sys-1/datasets/data-1/model.pkl",
        )


def test_prepare_audit_enforces_object_prefix() -> None:
    with pytest.raises(ValueError, match="outside"):
        prepare_audit.run(
            organization_id="org-1",
            audit_run_id="run-1",
            dataset_id="data-1",
            artifact_key="org-2/systems/sys-1/datasets/data-1/data.parquet",
        )


def test_prepare_audit_accepts_registered_dataset_object() -> None:
    result = prepare_audit.run(
        organization_id="org-1",
        audit_run_id="run-1",
        dataset_id="data-1",
        artifact_key="org-1/systems/sys-1/datasets/data-1/data.parquet",
    )
    assert result["status"] == "ready"
    assert result["dataset_id"] == "data-1"


def test_schema_inference_is_conservative_and_tracks_missingness() -> None:
    fields = infer_schema(
        [
            {"candidate_id": "anon-1", "selected": True, "score": 0.8, "group": "A"},
            {"candidate_id": "anon-2", "selected": False, "score": 0.4, "group": None},
            {"candidate_id": "anon-3", "selected": True, "score": 0.9, "group": "A"},
        ]
    )
    by_name = {field["name"]: field for field in fields}
    assert by_name["selected"]["inferred_type"] == "boolean"
    assert by_name["score"]["inferred_type"] == "number"
    assert by_name["group"]["nullable"] is True


def test_inspection_requires_external_clean_scan() -> None:
    with pytest.raises(ValueError, match="clean malware scan"):
        inspect_dataset.run(
            organization_id="org-1",
            dataset_id="data-1",
            artifact_key="org-1/systems/sys-1/datasets/data-1/decisions.csv",
            filename="decisions.csv",
            scanner_reference="clamav:scan-1",
            scan_status="rejected",
            preview_rows=[{"candidate_id": "anon-1"}],
        )
