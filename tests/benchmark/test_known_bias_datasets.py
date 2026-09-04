from __future__ import annotations

from fairhire_domain.audit import run_binary_audit

from .known_bias_cases import AUDIT_CONFIG, CASES


def test_three_known_bias_patterns_have_expected_direction_and_uncertainty() -> None:
    for build_case in CASES:
        case = build_case()
        result = run_binary_audit(case.rows, dict(AUDIT_CONFIG))
        matches = [
            metric
            for metric in result["metrics"]
            if metric["metric_key"] == case.expected_metric
            and metric["comparison_group"] == "comparison"
        ]
        assert len(matches) == 1, case.key
        metric = matches[0]
        assert metric["status"] == case.expected_status, case.key
        if case.expected_sign:
            assert metric["value"] is not None
            assert float(metric["value"]) * case.expected_sign > 0, case.key
            assert metric["lower_bound"] is not None
            assert metric["upper_bound"] is not None
            assert float(metric["lower_bound"]) <= float(metric["value"])
            assert float(metric["value"]) <= float(metric["upper_bound"])


def test_metric_values_cross_check_against_independent_count_formulas() -> None:
    selection_case = CASES[0]()
    selection_result = run_binary_audit(selection_case.rows, dict(AUDIT_CONFIG))
    ratio = next(
        metric
        for metric in selection_result["metrics"]
        if metric["metric_key"] == "demographic_parity_ratio"
        and metric["comparison_group"] == "comparison"
    )
    assert ratio["value"] == (250 / 500) / (400 / 500)

    opportunity_case = CASES[1]()
    opportunity_result = run_binary_audit(opportunity_case.rows, dict(AUDIT_CONFIG))
    difference = next(
        metric
        for metric in opportunity_result["metrics"]
        if metric["metric_key"] == "equal_opportunity_difference"
        and metric["comparison_group"] == "comparison"
    )
    assert difference["value"] == (150 / 300) - (240 / 300)
