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


def test_proxy_finding_keeps_association_and_output_impact_together() -> None:
    rows = _rows(240)
    for index, row in enumerate(rows):
        row["postal_code"] = "north" if row["group"] == "A" else "south"
        row["decision"] = row["group"] == "A" or index % 5 == 0
    result = run_binary_audit(
        rows,
        {
            "decision_field": "decision",
            "timestamp_field": "timestamp",
            "protected_attributes": ["group"],
            "feature_fields": ["postal_code"],
            "ablation_effects": {"postal_code": 0.18},
            "minimum_samples": 100,
            "bootstrap_iterations": 40,
        },
    )
    finding = next(metric for metric in result["metrics"] if metric["category"] == "proxy")
    assert finding["status"] == "review_required"
    assert finding["details"]["association_evidence"]["normalized_mutual_information"] == 1
    assert finding["details"]["output_impact_evidence"]["method"] == "controlled_ablation"
    assert finding["details"]["confidence"] == "high"


def test_counterfactual_pairs_reject_multi_variable_changes_and_keep_records() -> None:
    pairs = []
    for index in range(20):
        pairs.append(
            {
                "pair_id": f"pair-{index}",
                "changed_field": "name_signal",
                "original": {
                    "candidate_id": f"a-{index}",
                    "name_signal": "A",
                    "experience": 5,
                    "decision": True,
                },
                "counterfactual": {
                    "candidate_id": f"b-{index}",
                    "name_signal": "B",
                    "experience": 5,
                    "decision": index != 0,
                },
            }
        )
    pairs.append(
        {
            "pair_id": "invalid",
            "original": {"name_signal": "A", "experience": 5, "decision": True},
            "counterfactual": {"name_signal": "B", "experience": 8, "decision": False},
        }
    )
    result = run_binary_audit(
        _rows(),
        {
            "decision_field": "decision",
            "timestamp_field": "timestamp",
            "protected_attributes": ["group"],
            "feature_fields": ["experience"],
            "counterfactual_pairs": pairs,
            "counterfactual_change_fields": ["name_signal"],
            "minimum_samples": 100,
            "bootstrap_iterations": 40,
        },
    )
    finding = next(
        metric
        for metric in result["metrics"]
        if metric["metric_key"] == "counterfactual_consistency"
    )
    assert finding["raw_counts"] == {
        "valid_pairs": 20,
        "invalid_pairs": 1,
        "output_changes": 1,
    }
    assert finding["details"]["pair_records"][0]["changed_field"] == "name_signal"


def test_explainability_uses_shap_metadata_or_names_the_fallback() -> None:
    rows = _rows()
    for row in rows:
        row["shap_experience"] = float(row["experience"]) / 20
    shap_result = run_binary_audit(
        rows,
        {
            "decision_field": "decision",
            "timestamp_field": "timestamp",
            "protected_attributes": ["group"],
            "feature_fields": ["experience"],
            "shap_value_fields": {"experience": "shap_experience"},
            "explanation_background_dataset": "data-background@sha256:abc",
            "random_seed": 73,
            "minimum_samples": 100,
            "bootstrap_iterations": 40,
        },
    )
    explanation = next(
        metric for metric in shap_result["metrics"] if metric["category"] == "explainability"
    )
    assert explanation["method"] == "precomputed_global_shap"
    assert explanation["details"]["background_dataset"] == "data-background@sha256:abc"
    assert explanation["details"]["random_seed"] == 73
    fallback = run_binary_audit(
        rows,
        {
            "decision_field": "decision",
            "timestamp_field": "timestamp",
            "protected_attributes": ["group"],
            "feature_fields": ["experience"],
            "minimum_samples": 100,
            "bootstrap_iterations": 40,
        },
    )
    fallback_explanation = next(
        metric for metric in fallback["metrics"] if metric["category"] == "explainability"
    )
    assert fallback_explanation["method"] == "black_box_sensitivity"
    assert "SHAP was unavailable" in fallback_explanation["details"]["method_boundary"]


def test_drift_separates_distribution_change_from_harmful_performance_decline() -> None:
    baseline = _rows()
    current = _rows()
    for index, row in enumerate(current):
        row["experience"] = int(row["experience"]) + 20
        if index % 4 == 0:
            row["decision"] = not bool(row["label"])
    result = run_binary_audit(
        current,
        {
            "decision_field": "decision",
            "label_field": "label",
            "timestamp_field": "timestamp",
            "protected_attributes": ["group"],
            "feature_fields": ["experience"],
            "minimum_samples": 100,
            "bootstrap_iterations": 40,
            "drift_warning_threshold": 0.05,
            "drift_critical_threshold": 0.15,
        },
        baseline,
    )
    data_drift = next(
        metric
        for metric in result["metrics"]
        if metric["metric_key"] == "data_distribution_drift"
        and metric["comparison_group"] == "experience"
    )
    performance = next(
        metric
        for metric in result["metrics"]
        if metric["metric_key"] == "performance_drift" and metric["comparison_group"] == "accuracy"
    )
    assert data_drift["details"]["change_kind"] == "distribution_change"
    assert data_drift["details"]["harmful_performance_decline"] is False
    assert performance["details"]["harmful_performance_decline"] is True
    assert performance["status"] in {"warning", "critical"}
