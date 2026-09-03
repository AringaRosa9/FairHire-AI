import pytest
from fairhire_domain.audit import run_binary_audit, validate_audit_config


def _rows(size: int = 240) -> list[dict[str, object]]:
    rows = []
    for index in range(size):
        group = "A" if index < size // 2 else "B"
        qualified = index % 3 != 0
        selected = qualified if group == "A" else qualified and index % 4 != 0
        rows.append(
            {
                "candidate_id": f"anon-{index}",
                "decision": selected,
                "label": qualified,
                "score": 0.8 if selected else 0.2,
                "group": group,
                "timestamp": f"2026-0{1 + index // 100}-01T00:00:00Z",
                "experience": index % 20,
            }
        )
    return rows


def test_binary_audit_is_reproducible_and_includes_required_metrics() -> None:
    config = {
        "identifier_field": "candidate_id",
        "decision_field": "decision",
        "label_field": "label",
        "score_field": "score",
        "timestamp_field": "timestamp",
        "protected_attributes": ["group"],
        "feature_fields": ["experience"],
        "minimum_samples": 100,
        "bootstrap_iterations": 100,
        "random_seed": 42,
    }
    first = run_binary_audit(_rows(), config)
    second = run_binary_audit(_rows(), config)
    assert first == second
    keys = {metric["metric_key"] for metric in first["metrics"]}
    assert {
        "selection_rate",
        "demographic_parity_difference",
        "demographic_parity_ratio",
        "true_positive_rate",
        "false_positive_rate",
        "equal_opportunity_difference",
        "equalized_odds_difference",
        "precision",
        "calibration",
        "error_rate",
    } <= keys
    ratio = next(
        metric for metric in first["metrics"] if metric["metric_key"] == "demographic_parity_ratio"
    )
    assert ratio["reference_group"] == "A"
    assert ratio["comparison_group"] == "B"
    assert ratio["value"] == 0.75
    assert ratio["status"] == "review_required"


def test_small_and_unknown_groups_are_never_reported_as_pass() -> None:
    rows = _rows(24)
    rows[0]["group"] = None
    result = run_binary_audit(
        rows,
        {
            "decision_field": "decision",
            "label_field": "label",
            "timestamp_field": "timestamp",
            "protected_attributes": ["group"],
            "minimum_samples": 20,
            "hard_suppression_floor": 15,
            "bootstrap_iterations": 40,
        },
    )
    fairness = [metric for metric in result["metrics"] if metric["category"] == "fairness"]
    assert fairness
    assert all(metric["status"] != "pass" for metric in fairness)
    group_quality = next(
        metric for metric in result["metrics"] if metric["metric_key"] == "group_coverage"
    )
    assert group_quality["status"] == "insufficient_evidence"


def test_missing_labels_disable_label_dependent_metrics() -> None:
    rows = [{key: value for key, value in row.items() if key != "label"} for row in _rows()]
    result = run_binary_audit(
        rows,
        {
            "decision_field": "decision",
            "timestamp_field": "timestamp",
            "protected_attributes": ["group"],
            "minimum_samples": 100,
            "bootstrap_iterations": 40,
        },
    )
    label_metrics = {
        "true_positive_rate",
        "false_positive_rate",
        "equal_opportunity_difference",
        "equalized_odds_difference",
        "precision",
        "calibration",
        "error_rate",
    }
    assert all(
        metric["status"] == "insufficient_evidence"
        for metric in result["metrics"]
        if metric["metric_key"] in label_metrics
    )


def test_distinct_decision_and_label_positive_values_are_respected() -> None:
    rows = [
        {
            "candidate_id": f"anon-{index}",
            "decision": "advance" if index % 2 == 0 else "decline",
            "label": "qualified" if index % 2 == 0 else "not_qualified",
            "group": "A" if index < 20 else "B",
            "timestamp": "2026-08-01T00:00:00Z",
        }
        for index in range(40)
    ]
    result = run_binary_audit(
        rows,
        {
            "decision_field": "decision",
            "decision_positive_value": "advance",
            "label_field": "label",
            "label_positive_value": "qualified",
            "timestamp_field": "timestamp",
            "protected_attributes": ["group"],
            "minimum_samples": 20,
            "bootstrap_iterations": 40,
        },
    )
    true_positive_rates = [
        metric for metric in result["metrics"] if metric["metric_key"] == "true_positive_rate"
    ]
    assert all(metric["value"] == 1.0 for metric in true_positive_rates)


def test_config_cannot_lower_evidence_floor_or_claim_a_legal_determination() -> None:
    with pytest.raises(ValueError, match="minimum_samples"):
        validate_audit_config({"minimum_samples": 4})
    with pytest.raises(ValueError, match="legal_determination"):
        validate_audit_config(
            {
                "threshold_source": {
                    "source_type": "rule_pack",
                    "source_id": "eu-core",
                    "version": "1",
                    "legal_determination": True,
                }
            }
        )


def test_missing_protected_attributes_create_an_evidence_gap() -> None:
    result = run_binary_audit(
        _rows(),
        {
            "decision_field": "decision",
            "label_field": "label",
            "timestamp_field": "timestamp",
            "protected_attributes": [],
            "minimum_samples": 100,
            "bootstrap_iterations": 40,
        },
    )
    coverage = next(
        metric for metric in result["metrics"] if metric["metric_key"] == "group_coverage"
    )
    assert coverage["status"] == "insufficient_evidence"
    assert coverage["details"]["protected_attributes_supplied"] is False
