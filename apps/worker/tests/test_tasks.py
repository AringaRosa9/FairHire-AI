import pytest

from fairhire_worker.tasks import analyze_audit, infer_schema, inspect_dataset, prepare_audit


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


def test_analyze_audit_computes_and_persists_results(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {
            "candidate_id": f"candidate-{index}",
            "selected": index % 3 != 0,
            "group": "A" if index < 30 else "B",
            "decision_at": "2026-08-01T00:00:00Z",
        }
        for index in range(60)
    ]
    persisted: dict[str, object] = {}
    monkeypatch.setattr("fairhire_worker.tasks._load_rows", lambda *_: rows)
    monkeypatch.setattr("fairhire_worker.tasks._set_run_state", lambda **_: None)
    monkeypatch.setattr("fairhire_worker.tasks._cancellation_requested", lambda **_: False)
    monkeypatch.setattr(
        "fairhire_worker.tasks._persist_audit_result", lambda **kwargs: persisted.update(kwargs)
    )
    result = analyze_audit.run(
        organization_id="org-1",
        audit_run_id="run-1",
        dataset_id="data-1",
        artifact_key="org-1/systems/sys-1/datasets/data-1/decisions.csv",
        dataset_format="csv",
        config={
            "identifier_field": "candidate_id",
            "decision_field": "selected",
            "timestamp_field": "decision_at",
            "protected_attributes": ["group"],
            "minimum_samples": 20,
            "bootstrap_iterations": 40,
        },
        job_id="job-1",
    )
    assert result["status"] == "succeeded"
    assert result["metric_count"] > 0
    assert persisted["audit_run_id"] == "run-1"


def test_analyze_audit_honors_cooperative_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    states: list[str] = []
    monkeypatch.setattr("fairhire_worker.tasks._cancellation_requested", lambda **_: True)
    monkeypatch.setattr(
        "fairhire_worker.tasks._set_run_state",
        lambda **kwargs: states.append(str(kwargs["status"])),
    )
    result = analyze_audit.run(
        organization_id="org-1",
        audit_run_id="run-1",
        dataset_id="data-1",
        artifact_key="org-1/systems/sys-1/datasets/data-1/decisions.csv",
        dataset_format="csv",
        config={},
        job_id="job-1",
    )
    assert result["status"] == "cancelled"
    assert states == ["cancelled"]


def test_analyze_audit_loads_explicit_baseline_for_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_rows = [
        {
            "candidate_id": f"current-{index}",
            "selected": index % 2 == 0,
            "qualified": index % 2 == 0,
            "experience": index + 10,
            "group": "A" if index < 20 else "B",
            "decision_at": "2026-09-01T00:00:00Z",
        }
        for index in range(40)
    ]
    baseline_rows = [
        {
            "candidate_id": f"baseline-{index}",
            "selected": index % 2 == 0,
            "qualified": index % 2 == 0,
            "experience": index,
            "group": "A" if index < 20 else "B",
            "decision_at": "2026-08-01T00:00:00Z",
        }
        for index in range(40)
    ]
    loaded: list[str] = []

    def load_rows(key: str, _: str) -> list[dict[str, object]]:
        loaded.append(key)
        return baseline_rows if "baseline" in key else current_rows

    persisted: dict[str, object] = {}
    monkeypatch.setattr("fairhire_worker.tasks._load_rows", load_rows)
    monkeypatch.setattr("fairhire_worker.tasks._set_run_state", lambda **_: None)
    monkeypatch.setattr("fairhire_worker.tasks._cancellation_requested", lambda **_: False)
    monkeypatch.setattr(
        "fairhire_worker.tasks._persist_audit_result", lambda **kwargs: persisted.update(kwargs)
    )
    result = analyze_audit.run(
        organization_id="org-1",
        audit_run_id="run-current",
        dataset_id="data-current",
        artifact_key="org-1/systems/sys-1/datasets/data-current/current.csv",
        dataset_format="csv",
        baseline_artifact_key=("org-1/systems/sys-1/datasets/data-baseline/baseline.csv"),
        baseline_dataset_id="data-baseline",
        baseline_dataset_format="csv",
        config={
            "identifier_field": "candidate_id",
            "decision_field": "selected",
            "label_field": "qualified",
            "timestamp_field": "decision_at",
            "protected_attributes": ["group"],
            "feature_fields": ["experience"],
            "minimum_samples": 20,
            "bootstrap_iterations": 40,
        },
        job_id="job-current",
    )
    metrics = persisted["result"]["metrics"]
    assert result["status"] == "succeeded"
    assert len(loaded) == 2
    assert any(metric["metric_key"] == "data_distribution_drift" for metric in metrics)
