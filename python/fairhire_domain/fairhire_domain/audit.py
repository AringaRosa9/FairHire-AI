"""Deterministic binary-classification audit engine.

The engine intentionally accepts ordinary Python rows.  File decoding and protected
attribute vault access stay at the worker boundary; the calculations remain small,
testable, and independent from storage and web frameworks.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Callable, Iterable
from contextlib import suppress
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Literal

from .advanced_audit import (
    counterfactual_results,
    drift_results,
    explainability_results,
    proxy_results,
)

CALCULATION_VERSION = "fairhire-binary-audit@2.0.0"
MetricStatus = Literal["pass", "review_required", "insufficient_evidence", "warning", "critical"]


def _missing(value: object) -> bool:
    return (
        value is None
        or (isinstance(value, str) and not value.strip())
        or (isinstance(value, float) and math.isnan(value))
    )


def _positive(value: object, expected: object) -> bool:
    return value == expected


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _number(value: float | int | None) -> float | None:
    return float(value) if value is not None else None


def _count(value: float | int | None) -> int:
    return int(value or 0)


def _parse_timestamp(value: object) -> datetime:
    parsed = (
        value
        if isinstance(value, datetime)
        else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    )
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    if total <= 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    spread = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total)
    spread /= denominator
    return max(0.0, centre - spread), min(1.0, centre + spread)


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot take a percentile of an empty sample")
    index = (len(ordered) - 1) * quantile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)


def _bootstrap_comparison(
    comparison: list[dict[str, Any]],
    reference: list[dict[str, Any]],
    statistic: Callable[[list[dict[str, Any]], list[dict[str, Any]]], float | None],
    *,
    iterations: int,
    seed: int,
) -> tuple[float, float] | None:
    if not comparison or not reference or iterations < 1:
        return None
    generator = random.Random(seed)
    estimates: list[float] = []
    for _ in range(iterations):
        sampled_comparison = [generator.choice(comparison) for _ in comparison]
        sampled_reference = [generator.choice(reference) for _ in reference]
        estimate = statistic(sampled_comparison, sampled_reference)
        if estimate is not None and math.isfinite(estimate):
            estimates.append(estimate)
    if len(estimates) < max(20, iterations // 5):
        return None
    return _percentile(estimates, 0.025), _percentile(estimates, 0.975)


def _confusion(
    rows: Iterable[dict[str, Any]],
    decision_field: str,
    label_field: str,
    decision_positive: object,
    label_positive: object,
) -> dict[str, int]:
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for row in rows:
        if _missing(row.get(label_field)) or _missing(row.get(decision_field)):
            continue
        decision = _positive(row[decision_field], decision_positive)
        label = _positive(row[label_field], label_positive)
        if decision and label:
            counts["tp"] += 1
        elif decision:
            counts["fp"] += 1
        elif label:
            counts["fn"] += 1
        else:
            counts["tn"] += 1
    return counts


def _rates(
    rows: list[dict[str, Any]],
    *,
    decision_field: str,
    decision_positive: object,
    label_field: str | None,
    label_positive: object,
    score_field: str | None,
) -> dict[str, float | int | None]:
    usable = [row for row in rows if not _missing(row.get(decision_field))]
    selected = sum(_positive(row[decision_field], decision_positive) for row in usable)
    result: dict[str, float | int | None] = {
        "n": len(rows),
        "decision_n": len(usable),
        "selected": selected,
        "selection_rate": _ratio(selected, len(usable)),
    }
    if label_field is None:
        return result
    confusion = _confusion(usable, decision_field, label_field, decision_positive, label_positive)
    result.update(confusion)
    result["labeled_n"] = sum(confusion.values())
    result["true_positive_rate"] = _ratio(confusion["tp"], confusion["tp"] + confusion["fn"])
    result["false_positive_rate"] = _ratio(confusion["fp"], confusion["fp"] + confusion["tn"])
    result["precision"] = _ratio(confusion["tp"], confusion["tp"] + confusion["fp"])
    result["error_rate"] = _ratio(confusion["fp"] + confusion["fn"], sum(confusion.values()))
    if score_field:
        scored = [
            row
            for row in usable
            if not _missing(row.get(score_field)) and not _missing(row.get(label_field))
        ]
        try:
            mean_score = sum(float(row[score_field]) for row in scored) / len(scored)
            observed = sum(_positive(row[label_field], label_positive) for row in scored) / len(
                scored
            )
            result["calibration"] = mean_score - observed
            result["scored_n"] = len(scored)
        except (TypeError, ValueError, ZeroDivisionError):
            result["calibration"] = None
    return result


def _status(
    *,
    sample_sizes: Iterable[int],
    value: float | None,
    min_samples: int,
    review: bool,
) -> MetricStatus:
    if value is None or any(size < min_samples for size in sample_sizes):
        return "insufficient_evidence"
    return "review_required" if review else "pass"


def _quality_result(
    key: str,
    value: float | None,
    status: MetricStatus,
    *,
    raw_counts: dict[str, object],
    details: dict[str, object],
) -> dict[str, object]:
    return {
        "category": "data_quality",
        "metric_key": key,
        "protected_attribute": None,
        "reference_group": None,
        "comparison_group": None,
        "value": value,
        "lower_bound": None,
        "upper_bound": None,
        "status": status,
        "raw_counts": raw_counts,
        "method": "deterministic_scan",
        "details": details,
    }


def data_quality_results(
    rows: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, object]]:
    """Return explicit quality checks, including evidence gaps and unknown groups."""
    total = len(rows)
    fields = list(rows[0]) if rows else []
    identifier = str(config.get("identifier_field", "candidate_id"))
    decision = str(config.get("decision_field", "decision"))
    timestamp = str(config.get("timestamp_field", "timestamp"))
    protected = [str(item) for item in config.get("protected_attributes", [])]
    features = [str(item) for item in config.get("feature_fields", [])]
    label = str(config["label_field"]) if config.get("label_field") else None
    min_samples = int(config.get("minimum_samples", 200))
    hard_floor = int(config.get("hard_suppression_floor", 20))
    missing_cells = sum(_missing(row.get(field)) for row in rows for field in fields)
    missing_rate = _ratio(missing_cells, total * len(fields)) if fields else None
    identifiers = [row.get(identifier) for row in rows if not _missing(row.get(identifier))]
    duplicate_count = len(identifiers) - len(set(map(str, identifiers)))
    missing_required = sum(
        _missing(row.get(field)) for row in rows for field in (identifier, decision, timestamp)
    )
    results = [
        _quality_result(
            "missing_values",
            missing_rate,
            "review_required" if missing_required else "pass",
            raw_counts={"missing_cells": missing_cells, "total_cells": total * len(fields)},
            details={"missing_required_cells": missing_required, "field_count": len(fields)},
        ),
        _quality_result(
            "duplicate_identifiers",
            _ratio(duplicate_count, total),
            "review_required"
            if duplicate_count
            else ("pass" if len(identifiers) == total else "insufficient_evidence"),
            raw_counts={"duplicate_rows": duplicate_count, "rows": total},
            details={"identifier_field": identifier},
        ),
        _quality_result(
            "sample_size",
            float(total),
            "pass" if total >= min_samples else "insufficient_evidence",
            raw_counts={"rows": total},
            details={"minimum_samples": min_samples},
        ),
    ]

    # Tukey fences are stable, explainable, and do not assume normality.
    outlier_count = 0
    numeric_fields = 0
    for field in features:
        try:
            values = sorted(float(row[field]) for row in rows if not _missing(row.get(field)))
        except (TypeError, ValueError):
            continue
        if len(values) < 4:
            continue
        numeric_fields += 1
        q1, q3 = _percentile(values, 0.25), _percentile(values, 0.75)
        lower, upper = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        outlier_count += sum(value < lower or value > upper for value in values)
    results.append(
        _quality_result(
            "outliers",
            _ratio(outlier_count, total),
            "review_required"
            if outlier_count
            else ("pass" if numeric_fields else "insufficient_evidence"),
            raw_counts={"outlier_cells": outlier_count, "rows": total},
            details={"method": "tukey_1.5_iqr", "numeric_feature_count": numeric_fields},
        )
    )

    unknown_groups: dict[str, int] = {}
    coverage: dict[str, dict[str, int]] = {}
    for attribute in protected:
        counts = Counter(
            "Unknown" if _missing(row.get(attribute)) else str(row[attribute]) for row in rows
        )
        coverage[attribute] = dict(sorted(counts.items()))
        unknown_groups[attribute] = counts.get("Unknown", 0)
    low_groups = {
        f"{attribute}:{group}": count
        for attribute, groups in coverage.items()
        for group, count in groups.items()
        if group != "Unknown" and count < min_samples
    }
    results.append(
        _quality_result(
            "group_coverage",
            None,
            "insufficient_evidence"
            if not protected or low_groups or any(unknown_groups.values())
            else "pass",
            raw_counts={
                "groups": {
                    attribute: {
                        group: count if count >= hard_floor else None
                        for group, count in groups.items()
                    }
                    for attribute, groups in coverage.items()
                },
                "unknown": {
                    attribute: count if count >= hard_floor else None
                    for attribute, count in unknown_groups.items()
                },
            },
            details={
                "groups_below_minimum": sorted(low_groups),
                "minimum_samples": min_samples,
                "hard_suppression_floor": hard_floor,
                "protected_attributes_supplied": bool(protected),
            },
        )
    )

    parsed_times: list[datetime] = []
    for row in rows:
        value = row.get(timestamp)
        with suppress(TypeError, ValueError):
            parsed_times.append(_parse_timestamp(value))
    coverage_days = (
        (max(parsed_times) - min(parsed_times)).total_seconds() / 86400
        if len(parsed_times) > 1
        else None
    )
    minimum_days = float(config.get("minimum_time_coverage_days", 28))
    results.append(
        _quality_result(
            "time_coverage",
            coverage_days,
            _status(
                sample_sizes=[len(parsed_times)],
                value=coverage_days,
                min_samples=2,
                review=coverage_days is not None and coverage_days < minimum_days,
            ),
            raw_counts={"valid_timestamps": len(parsed_times), "rows": total},
            details={"minimum_days": minimum_days},
        )
    )

    leakage_fields: list[str] = []
    targets = [field for field in (label, decision) if field]
    for feature in features:
        for target in targets:
            comparable = [
                row
                for row in rows
                if not _missing(row.get(feature)) and not _missing(row.get(target))
            ]
            if comparable and all(str(row[feature]) == str(row[target]) for row in comparable):
                leakage_fields.append(feature)
                break
    results.append(
        _quality_result(
            "label_leakage",
            float(len(leakage_fields)),
            "review_required"
            if leakage_fields
            else ("pass" if features and label else "insufficient_evidence"),
            raw_counts={"suspected_fields": len(leakage_fields)},
            details={"fields": sorted(leakage_fields), "method": "exact_target_duplication"},
        )
    )

    training_hashes = {str(item) for item in config.get("training_identifier_hashes", [])}
    audit_hashes = {sha256(str(identifier).encode()).hexdigest() for identifier in identifiers}
    overlap = len(training_hashes.intersection(audit_hashes))
    results.append(
        _quality_result(
            "train_test_overlap",
            _ratio(overlap, len(identifiers)),
            "review_required"
            if overlap
            else ("pass" if training_hashes else "insufficient_evidence"),
            raw_counts={"overlapping_identifiers": overlap, "audit_identifiers": len(identifiers)},
            details={"training_reference_supplied": bool(training_hashes)},
        )
    )
    return results


def _comparison_value(
    metric: str,
    group_rows: list[dict[str, Any]],
    reference_rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> float | None:
    kwargs = {
        "decision_field": str(config.get("decision_field", "decision")),
        "decision_positive": config.get("decision_positive_value", True),
        "label_field": str(config["label_field"]) if config.get("label_field") else None,
        "label_positive": config.get("label_positive_value", True),
        "score_field": str(config["score_field"]) if config.get("score_field") else None,
    }
    group = _rates(group_rows, **kwargs)
    reference = _rates(reference_rows, **kwargs)
    group_selection = _number(group.get("selection_rate"))
    reference_selection = _number(reference.get("selection_rate"))
    group_tpr = _number(group.get("true_positive_rate"))
    reference_tpr = _number(reference.get("true_positive_rate"))
    group_fpr = _number(group.get("false_positive_rate"))
    reference_fpr = _number(reference.get("false_positive_rate"))
    if metric == "demographic_parity_difference":
        return (
            group_selection - reference_selection
            if group_selection is not None and reference_selection is not None
            else None
        )
    if metric == "demographic_parity_ratio":
        return (
            _ratio(group_selection, reference_selection)
            if group_selection is not None and reference_selection is not None
            else None
        )
    if metric == "equal_opportunity_difference":
        return (
            group_tpr - reference_tpr
            if group_tpr is not None and reference_tpr is not None
            else None
        )
    if metric == "equalized_odds_difference":
        if any(value is None for value in (group_tpr, reference_tpr, group_fpr, reference_fpr)):
            return None
        assert group_tpr is not None
        assert reference_tpr is not None
        assert group_fpr is not None
        assert reference_fpr is not None
        return max(
            abs(group_tpr - reference_tpr),
            abs(group_fpr - reference_fpr),
        )
    raise ValueError(f"Unsupported comparison metric: {metric}")


def fairness_results(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, object]]:
    """Calculate group rates and reference comparisons with reproducible uncertainty."""
    attributes = [str(item) for item in config.get("protected_attributes", [])]
    if len(attributes) > 1 and bool(config.get("include_intersections", True)):
        intersection = " + ".join(attributes)
        prepared = [
            dict(
                row, **{intersection: " + ".join(str(row.get(a) or "Unknown") for a in attributes)}
            )
            for row in rows
        ]
        dimensions = [(attribute, rows) for attribute in attributes] + [(intersection, prepared)]
    else:
        dimensions = [(attribute, rows) for attribute in attributes]
    min_samples = int(config.get("minimum_samples", 200))
    hard_floor = int(config.get("hard_suppression_floor", 20))
    iterations = int(config.get("bootstrap_iterations", 1000))
    seed = int(config.get("random_seed", 1729))
    ratio_threshold = float(config.get("demographic_parity_ratio_threshold", 0.8))
    difference_threshold = float(config.get("difference_threshold", 0.1))
    threshold_source = dict(
        config.get(
            "threshold_source",
            {
                "source_type": "approved_test_strategy",
                "source_id": "strategy-eu-binary-v1",
                "version": "1.0.0",
                "legal_determination": False,
            },
        )
    )
    label_field = str(config["label_field"]) if config.get("label_field") else None
    score_field = str(config["score_field"]) if config.get("score_field") else None
    results: list[dict[str, object]] = []
    for attribute, dimension_rows in dimensions:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in dimension_rows:
            group = "Unknown" if _missing(row.get(attribute)) else str(row[attribute])
            grouped.setdefault(group, []).append(row)
        eligible = {group: values for group, values in grouped.items() if group != "Unknown"}
        if not eligible:
            continue
        configured_reference = dict(config.get("reference_groups", {})).get(attribute)

        def reference_rank(
            group: str, groups: dict[str, list[dict[str, Any]]] = eligible
        ) -> tuple[float, int, str]:
            rates = _rates(
                groups[group],
                decision_field=str(config.get("decision_field", "decision")),
                decision_positive=config.get("decision_positive_value", True),
                label_field=None,
                label_positive=config.get("label_positive_value", True),
                score_field=None,
            )
            return (_number(rates.get("selection_rate")) or -1.0, len(groups[group]), group)

        reference_group = (
            str(configured_reference)
            if configured_reference in eligible
            else max(eligible, key=reference_rank)
        )
        reference_rows = eligible[reference_group]
        for group, group_rows in sorted(grouped.items()):
            rates = _rates(
                group_rows,
                decision_field=str(config.get("decision_field", "decision")),
                decision_positive=config.get("decision_positive_value", True),
                label_field=label_field,
                label_positive=config.get("label_positive_value", True),
                score_field=score_field,
            )
            suppressed = len(group_rows) < hard_floor
            raw_counts = {key: value for key, value in rates.items() if isinstance(value, int)}
            for metric in (
                "selection_rate",
                "true_positive_rate",
                "false_positive_rate",
                "precision",
                "calibration",
                "error_rate",
            ):
                unavailable = (metric != "selection_rate" and label_field is None) or (
                    metric == "calibration" and score_field is None
                )
                value = None if unavailable else rates.get(metric)
                interval = None
                if metric == "selection_rate":
                    interval = _wilson(_count(rates["selected"]), _count(rates["decision_n"]))
                elif metric in {
                    "true_positive_rate",
                    "false_positive_rate",
                    "precision",
                    "error_rate",
                }:
                    numerator_denominator = {
                        "true_positive_rate": (
                            _count(rates.get("tp")),
                            _count(rates.get("tp")) + _count(rates.get("fn")),
                        ),
                        "false_positive_rate": (
                            _count(rates.get("fp")),
                            _count(rates.get("fp")) + _count(rates.get("tn")),
                        ),
                        "precision": (
                            _count(rates.get("tp")),
                            _count(rates.get("tp")) + _count(rates.get("fp")),
                        ),
                        "error_rate": (
                            _count(rates.get("fp")) + _count(rates.get("fn")),
                            _count(rates.get("labeled_n")),
                        ),
                    }[metric]
                    interval = _wilson(*numerator_denominator)
                effective_sample = {
                    "selection_rate": _count(rates.get("decision_n")),
                    "true_positive_rate": _count(rates.get("tp")) + _count(rates.get("fn")),
                    "false_positive_rate": _count(rates.get("fp")) + _count(rates.get("tn")),
                    "precision": _count(rates.get("tp")) + _count(rates.get("fp")),
                    "calibration": _count(rates.get("scored_n")),
                    "error_rate": _count(rates.get("labeled_n")),
                }[metric]
                results.append(
                    {
                        "category": "fairness",
                        "metric_key": metric,
                        "protected_attribute": attribute,
                        "reference_group": reference_group,
                        "comparison_group": group,
                        "value": value,
                        "lower_bound": interval[0] if interval else None,
                        "upper_bound": interval[1] if interval else None,
                        "status": _status(
                            sample_sizes=[effective_sample],
                            value=float(value) if value is not None else None,
                            min_samples=min_samples,
                            review=False,
                        )
                        if group != "Unknown"
                        else "insufficient_evidence",
                        "threshold": None,
                        "threshold_operator": None,
                        "threshold_source": threshold_source,
                        "raw_counts": {} if suppressed else raw_counts,
                        "method": "wilson"
                        if interval
                        else ("calibration_gap" if metric == "calibration" else "not_available"),
                        "details": {
                            "calculation_version": CALCULATION_VERSION,
                            "suppressed_below_floor": suppressed,
                            "hard_suppression_floor": hard_floor,
                            "labels_available": label_field is not None,
                            "effective_sample_size": effective_sample,
                        },
                    }
                )
            if group == reference_group:
                continue
            for metric in (
                "demographic_parity_difference",
                "demographic_parity_ratio",
                "equal_opportunity_difference",
                "equalized_odds_difference",
            ):
                value = _comparison_value(metric, group_rows, reference_rows, config)
                threshold = ratio_threshold if metric.endswith("ratio") else difference_threshold
                review = value is not None and (
                    value < threshold if metric.endswith("ratio") else abs(value) > threshold
                )

                def comparison_statistic(
                    left: list[dict[str, Any]],
                    right: list[dict[str, Any]],
                    metric_key: str = metric,
                ) -> float | None:
                    return _comparison_value(metric_key, left, right, config)

                interval = _bootstrap_comparison(
                    group_rows,
                    reference_rows,
                    comparison_statistic,
                    iterations=iterations,
                    seed=seed + sum(map(ord, f"{attribute}:{group}:{metric}")),
                )
                results.append(
                    {
                        "category": "fairness",
                        "metric_key": metric,
                        "protected_attribute": attribute,
                        "reference_group": reference_group,
                        "comparison_group": group,
                        "value": value,
                        "lower_bound": interval[0] if interval else None,
                        "upper_bound": interval[1] if interval else None,
                        "status": _status(
                            sample_sizes=[len(group_rows), len(reference_rows)],
                            value=value,
                            min_samples=min_samples,
                            review=review,
                        )
                        if group != "Unknown"
                        else "insufficient_evidence",
                        "threshold": threshold,
                        "threshold_operator": ">=" if metric.endswith("ratio") else "abs<=",
                        "threshold_source": threshold_source,
                        "raw_counts": (
                            {}
                            if suppressed or len(reference_rows) < hard_floor
                            else {
                                "comparison": raw_counts,
                                "reference": {
                                    key: count
                                    for key, count in _rates(
                                        reference_rows,
                                        decision_field=str(
                                            config.get("decision_field", "decision")
                                        ),
                                        decision_positive=config.get(
                                            "decision_positive_value", True
                                        ),
                                        label_field=label_field,
                                        label_positive=config.get("label_positive_value", True),
                                        score_field=score_field,
                                    ).items()
                                    if isinstance(count, int)
                                },
                            }
                        ),
                        "method": "stratified_bootstrap_percentile",
                        "details": {
                            "calculation_version": CALCULATION_VERSION,
                            "bootstrap_iterations": iterations,
                            "random_seed": seed,
                            "legal_determination": False,
                            "suppressed_below_floor": suppressed,
                        },
                    }
                )
    return results


def run_binary_audit(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
    baseline_rows: list[dict[str, Any]] | None = None,
) -> dict[str, object]:
    if not rows:
        raise ValueError("At least one row is required for an audit")
    validate_audit_config(config)
    metrics = (
        data_quality_results(rows, config)
        + fairness_results(rows, config)
        + proxy_results(rows, config)
        + counterfactual_results(rows, config)
        + explainability_results(rows, config)
        + drift_results(rows, baseline_rows, config)
    )
    counts = Counter(str(metric["status"]) for metric in metrics)
    return {
        "calculation_version": CALCULATION_VERSION,
        "random_seed": int(config.get("random_seed", 1729)),
        "row_count": len(rows),
        "status_counts": dict(counts),
        "metrics": metrics,
    }


def validate_audit_config(config: dict[str, Any]) -> None:
    """Reject configurations that could turn weak evidence into an apparent pass."""
    minimum_samples = int(config.get("minimum_samples", 200))
    hard_floor = int(config.get("hard_suppression_floor", 20))
    iterations = int(config.get("bootstrap_iterations", 1000))
    if hard_floor < 5:
        raise ValueError("hard_suppression_floor must be at least 5")
    if minimum_samples < 20 or minimum_samples < hard_floor:
        raise ValueError("minimum_samples must be at least 20 and not below the privacy floor")
    if not 20 <= iterations <= 10_000:
        raise ValueError("bootstrap_iterations must be between 20 and 10000")
    ratio_threshold = float(config.get("demographic_parity_ratio_threshold", 0.8))
    difference_threshold = float(config.get("difference_threshold", 0.1))
    if not 0 <= ratio_threshold <= 1 or not 0 <= difference_threshold <= 1:
        raise ValueError("fairness thresholds must be between 0 and 1")
    warning = float(config.get("drift_warning_threshold", 0.1))
    critical = float(config.get("drift_critical_threshold", 0.2))
    if not 0 <= warning < critical <= 1:
        raise ValueError("drift thresholds must satisfy 0 <= warning < critical <= 1")
    performance_warning = float(config.get("performance_drift_warning_threshold", 0.03))
    performance_critical = float(config.get("performance_drift_critical_threshold", 0.08))
    if not 0 <= performance_warning < performance_critical <= 1:
        raise ValueError("performance drift thresholds must satisfy 0 <= warning < critical <= 1")
    proxy_association = float(config.get("proxy_association_threshold", 0.1))
    proxy_impact = float(config.get("proxy_output_impact_threshold", 0.05))
    if not 0 <= proxy_association <= 1 or not 0 <= proxy_impact <= 1:
        raise ValueError("proxy thresholds must be between 0 and 1")
    consistency = float(config.get("counterfactual_consistency_threshold", 0.98))
    minimum_pairs = int(config.get("counterfactual_minimum_pairs", 20))
    if not 0 <= consistency <= 1 or minimum_pairs < 1:
        raise ValueError("counterfactual threshold must be 0..1 and minimum_pairs at least 1")
    source = config.get(
        "threshold_source",
        {
            "source_type": "approved_test_strategy",
            "source_id": "strategy-eu-binary-v1",
            "version": "1.0.0",
            "legal_determination": False,
        },
    )
    if not isinstance(source, dict):
        raise ValueError("threshold_source is required")
    if source.get("source_type") not in {
        "organization_policy",
        "rule_pack",
        "approved_test_strategy",
    }:
        raise ValueError("threshold_source must name an approved source type")
    if not source.get("source_id") or not source.get("version"):
        raise ValueError("threshold_source requires source_id and version")
    if source.get("legal_determination") is not False:
        raise ValueError("threshold_source.legal_determination must be false")
