"""Proxy, counterfactual, explainability, and drift evidence.

The functions in this module deliberately operate on plain rows. Model execution and
vault access remain worker concerns; this layer only turns approved inputs into
deterministic, reviewable evidence.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any, cast


def _missing(value: object) -> bool:
    return (
        value is None
        or (isinstance(value, str) and not value.strip())
        or (isinstance(value, float) and math.isnan(value))
    )


def _numeric(values: Iterable[object]) -> list[float] | None:
    converted: list[float] = []
    try:
        for value in values:
            if _missing(value):
                continue
            converted.append(float(cast(Any, value)))
    except (TypeError, ValueError):
        return None
    return converted or None


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower, upper = math.floor(index), math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)


def _categories(values: list[object], *, boundaries: list[float] | None = None) -> list[str]:
    numeric = _numeric(values)
    if numeric is not None and len(numeric) == sum(not _missing(value) for value in values):
        cuts = boundaries or sorted({_percentile(numeric, q) for q in (0.2, 0.4, 0.6, 0.8)})
        return [
            "Unknown"
            if _missing(value)
            else f"bin-{sum(float(cast(Any, value)) > boundary for boundary in cuts)}"
            for value in values
        ]
    return ["Unknown" if _missing(value) else str(value) for value in values]


def _entropy(values: list[str]) -> float:
    counts = Counter(values)
    total = len(values)
    return (
        -sum((count / total) * math.log(count / total) for count in counts.values()) if total else 0
    )


def normalized_mutual_information(left: list[object], right: list[object]) -> float | None:
    """Return symmetric, bounded association after deterministic numeric binning."""
    pairs = [
        (a, b) for a, b in zip(left, right, strict=True) if not _missing(a) and not _missing(b)
    ]
    if len(pairs) < 2:
        return None
    left_categories = _categories([pair[0] for pair in pairs])
    right_categories = _categories([pair[1] for pair in pairs])
    left_entropy, right_entropy = _entropy(left_categories), _entropy(right_categories)
    denominator = min(left_entropy, right_entropy)
    if denominator <= 0:
        return 0.0
    total = len(pairs)
    left_counts, right_counts = Counter(left_categories), Counter(right_categories)
    joint = Counter(zip(left_categories, right_categories, strict=True))
    mutual_information = sum(
        count
        / total
        * math.log((count * total) / (left_counts[left_value] * right_counts[right_value]))
        for (left_value, right_value), count in joint.items()
    )
    return max(0.0, min(1.0, mutual_information / denominator))


def _predictability(
    feature: list[object], protected: list[object]
) -> tuple[float | None, float | None]:
    pairs = [
        (a, b)
        for a, b in zip(feature, protected, strict=True)
        if not _missing(a) and not _missing(b)
    ]
    if len(pairs) < 2:
        return None, None
    feature_categories = _categories([pair[0] for pair in pairs])
    protected_categories = [str(pair[1]) for pair in pairs]
    baseline = max(Counter(protected_categories).values()) / len(pairs)
    buckets: dict[str, Counter[str]] = defaultdict(Counter)
    for feature_value, protected_value in zip(
        feature_categories, protected_categories, strict=True
    ):
        buckets[feature_value][protected_value] += 1
    accuracy = sum(max(counts.values()) for counts in buckets.values()) / len(pairs)
    lift = (accuracy - baseline) / (1 - baseline) if baseline < 1 else 0.0
    return accuracy, max(0.0, lift)


def _feature_output_dependence(
    rows: list[dict[str, Any]], feature: str, output: str
) -> float | None:
    return normalized_mutual_information(
        [row.get(feature) for row in rows], [row.get(output) for row in rows]
    )


def _threshold_source(config: dict[str, Any]) -> dict[str, object]:
    return dict(config.get("threshold_source", {}))


def proxy_results(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, object]]:
    """Produce one finding per feature/protected pair with both required evidence paths."""
    features = [str(item) for item in config.get("feature_fields", [])]
    protected_attributes = [str(item) for item in config.get("protected_attributes", [])]
    decision_field = str(config.get("score_field") or config.get("decision_field", "decision"))
    ablation_effects = dict(config.get("ablation_effects", {}))
    association_threshold = float(config.get("proxy_association_threshold", 0.1))
    impact_threshold = float(config.get("proxy_output_impact_threshold", 0.05))
    minimum_samples = int(config.get("minimum_samples", 200))
    risk_tokens = ("zip", "postal", "school", "language", "name", "gap", "age", "location")
    results: list[dict[str, object]] = []
    for protected in protected_attributes:
        for feature in features:
            usable = [
                row
                for row in rows
                if not _missing(row.get(feature)) and not _missing(row.get(protected))
            ]
            association = normalized_mutual_information(
                [row[feature] for row in usable], [row[protected] for row in usable]
            )
            predictability, predictability_lift = _predictability(
                [row[feature] for row in usable], [row[protected] for row in usable]
            )
            explicit_ablation = feature in ablation_effects
            if explicit_ablation:
                try:
                    output_impact = abs(float(ablation_effects[feature]))
                except (TypeError, ValueError):
                    output_impact = None
            else:
                output_impact = _feature_output_dependence(usable, feature, decision_field)
            association_signal = max(
                [value for value in (association, predictability_lift) if value is not None],
                default=None,
            )
            has_both = association_signal is not None and output_impact is not None
            review = (
                association_signal is not None
                and output_impact is not None
                and association_signal >= association_threshold
                and output_impact >= impact_threshold
            )
            status = (
                "insufficient_evidence"
                if len(usable) < minimum_samples or not has_both
                else "review_required"
                if review
                else "pass"
            )
            confidence = (
                "high"
                if status != "insufficient_evidence" and explicit_ablation
                else "medium"
                if status != "insufficient_evidence"
                else "low"
            )
            results.append(
                {
                    "category": "proxy",
                    "metric_key": "proxy_risk",
                    "protected_attribute": protected,
                    "reference_group": None,
                    "comparison_group": feature,
                    "value": math.sqrt(association_signal * output_impact)
                    if association_signal is not None and output_impact is not None
                    else None,
                    "lower_bound": None,
                    "upper_bound": None,
                    "status": status,
                    "threshold": max(association_threshold, impact_threshold),
                    "threshold_operator": "dual_evidence",
                    "threshold_source": _threshold_source(config),
                    "raw_counts": {"usable_rows": len(usable)},
                    "method": "dual_evidence_proxy_screen",
                    "details": {
                        "feature": feature,
                        "confidence": confidence,
                        "semantic_risk_hint": any(
                            token in feature.lower() for token in risk_tokens
                        ),
                        "association_evidence": {
                            "normalized_mutual_information": association,
                            "protected_attribute_predictability": predictability,
                            "predictability_lift_over_majority": predictability_lift,
                            "threshold": association_threshold,
                        },
                        "output_impact_evidence": {
                            "value": output_impact,
                            "method": (
                                "controlled_ablation"
                                if explicit_ablation
                                else "observational_output_dependence"
                            ),
                            "threshold": impact_threshold,
                            "causal": explicit_ablation,
                        },
                        "limitation": (
                            "Association is a screening signal, not proof that the feature "
                            "is a proxy."
                            if explicit_ablation
                            else "No controlled ablation was supplied; output impact is "
                            "observational."
                        ),
                    },
                }
            )
    age_fields = [feature for feature in features if "age" in feature.lower()]
    for age_field in age_fields:
        output_field = str(config.get("score_field") or config.get("decision_field", "decision"))
        paired = [
            (row.get(age_field), row.get(output_field))
            for row in rows
            if not _missing(row.get(age_field)) and not _missing(row.get(output_field))
        ]
        ages = _numeric(pair[0] for pair in paired)
        outputs = _numeric(pair[1] for pair in paired)
        trend = (
            _pearson(ages, outputs)
            if ages is not None and outputs is not None and len(ages) == len(outputs)
            else None
        )
        results.append(
            {
                "category": "proxy",
                "metric_key": "age_output_trend",
                "protected_attribute": "age",
                "reference_group": None,
                "comparison_group": age_field,
                "value": trend,
                "lower_bound": None,
                "upper_bound": None,
                "status": (
                    "insufficient_evidence"
                    if trend is None or len(paired) < minimum_samples
                    else "review_required"
                    if abs(trend) >= impact_threshold
                    else "pass"
                ),
                "threshold": impact_threshold,
                "threshold_operator": "abs<=",
                "threshold_source": _threshold_source(config),
                "raw_counts": {"usable_rows": len(paired)},
                "method": "continuous_age_output_trend",
                "details": {
                    "feature": age_field,
                    "protected_attribute": "age",
                    "limitation": "A trend is not evidence of an unlawful age decision rule.",
                },
            }
        )
        configured_thresholds = dict(config.get("age_thresholds", {})).get(age_field, [])
        bandwidth = float(config.get("age_threshold_bandwidth", 2))
        for threshold_value in configured_thresholds:
            try:
                threshold = float(threshold_value)
            except (TypeError, ValueError):
                continue
            below = [
                float(cast(Any, output))
                for age, output in paired
                if threshold - bandwidth <= float(cast(Any, age)) < threshold
            ]
            above = [
                float(cast(Any, output))
                for age, output in paired
                if threshold <= float(cast(Any, age)) <= threshold + bandwidth
            ]
            discontinuity = (
                sum(above) / len(above) - sum(below) / len(below) if below and above else None
            )
            results.append(
                {
                    "category": "proxy",
                    "metric_key": "age_threshold_discontinuity",
                    "protected_attribute": "age",
                    "reference_group": f"below_{threshold:g}",
                    "comparison_group": f"at_or_above_{threshold:g}",
                    "value": discontinuity,
                    "lower_bound": None,
                    "upper_bound": None,
                    "status": (
                        "insufficient_evidence"
                        if discontinuity is None or min(len(below), len(above)) < minimum_samples
                        else "review_required"
                        if abs(discontinuity) >= impact_threshold
                        else "pass"
                    ),
                    "threshold": impact_threshold,
                    "threshold_operator": "abs<=",
                    "threshold_source": _threshold_source(config),
                    "raw_counts": {"below": len(below), "above": len(above)},
                    "method": "age_threshold_local_discontinuity",
                    "details": {
                        "age_field": age_field,
                        "age_threshold": threshold,
                        "bandwidth_years": bandwidth,
                    },
                }
            )
    return results


def _pair_specs(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, object]]:
    explicit = config.get("counterfactual_pairs")
    if isinstance(explicit, list):
        return [dict(item) for item in explicit if isinstance(item, dict)]
    pair_field = config.get("counterfactual_pair_field")
    if not pair_field:
        return []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not _missing(row.get(str(pair_field))):
            grouped[str(row[str(pair_field)])].append(row)
    pairs: list[dict[str, object]] = []
    for pair_id, pair_rows in grouped.items():
        if len(pair_rows) == 2:
            pairs.append(
                {"pair_id": pair_id, "original": pair_rows[0], "counterfactual": pair_rows[1]}
            )
    return pairs


def counterfactual_results(
    rows: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, object]]:
    decision_field = str(config.get("decision_field", "decision"))
    score_field = str(config["score_field"]) if config.get("score_field") else None
    identifier_field = str(config.get("identifier_field", "candidate_id"))
    ignored = {
        decision_field,
        identifier_field,
        str(config.get("timestamp_field", "timestamp")),
        str(config.get("counterfactual_pair_field", "")),
        str(config.get("counterfactual_variant_field", "")),
    }
    if score_field:
        ignored.add(score_field)
    requested_change_fields = set(map(str, config.get("counterfactual_change_fields", [])))
    records: list[dict[str, object]] = []
    invalid: list[dict[str, object]] = []
    output_changes = 0
    score_deltas: list[float] = []
    for index, pair in enumerate(_pair_specs(rows, config)):
        original = pair.get("original")
        counterfactual = pair.get("counterfactual")
        if not isinstance(original, dict) or not isinstance(counterfactual, dict):
            invalid.append({"pair_id": pair.get("pair_id", index), "reason": "missing_pair_rows"})
            continue
        keys = set(original).union(counterfactual) - ignored - {""}
        changes = [key for key in sorted(keys) if original.get(key) != counterfactual.get(key)]
        declared_field = pair.get("changed_field")
        valid = len(changes) == 1 and (not declared_field or str(declared_field) == changes[0])
        if requested_change_fields and valid:
            valid = changes[0] in requested_change_fields
        if not valid:
            invalid.append(
                {
                    "pair_id": pair.get("pair_id", index),
                    "reason": "not_exactly_one_allowed_input_change",
                    "observed_changes": changes,
                }
            )
            continue
        decision_changed = original.get(decision_field) != counterfactual.get(decision_field)
        score_delta = None
        if score_field:
            try:
                score_delta = float(counterfactual[score_field]) - float(original[score_field])
                score_deltas.append(abs(score_delta))
            except (KeyError, TypeError, ValueError):
                pass
        materially_changed = decision_changed or (
            score_delta is not None
            and abs(score_delta) > float(config.get("counterfactual_score_tolerance", 0.01))
        )
        output_changes += int(materially_changed)
        records.append(
            {
                "pair_id": pair.get("pair_id", index),
                "changed_field": changes[0],
                "original_value": original.get(changes[0]),
                "counterfactual_value": counterfactual.get(changes[0]),
                "original_decision": original.get(decision_field),
                "counterfactual_decision": counterfactual.get(decision_field),
                "score_delta": score_delta,
                "output_changed": materially_changed,
            }
        )
    threshold = float(config.get("counterfactual_consistency_threshold", 0.98))
    consistency = 1 - output_changes / len(records) if records else None
    minimum_pairs = int(config.get("counterfactual_minimum_pairs", 20))
    status = (
        "insufficient_evidence"
        if len(records) < minimum_pairs
        else "review_required"
        if consistency is not None and consistency < threshold
        else "pass"
    )
    return [
        {
            "category": "counterfactual",
            "metric_key": "counterfactual_consistency",
            "protected_attribute": None,
            "reference_group": "original",
            "comparison_group": "counterfactual",
            "value": consistency,
            "lower_bound": None,
            "upper_bound": None,
            "status": status,
            "threshold": threshold,
            "threshold_operator": ">=",
            "threshold_source": _threshold_source(config),
            "raw_counts": {
                "valid_pairs": len(records),
                "invalid_pairs": len(invalid),
                "output_changes": output_changes,
            },
            "method": "matched_pair_single_variable",
            "details": {
                "minimum_pairs": minimum_pairs,
                "score_tolerance": float(config.get("counterfactual_score_tolerance", 0.01)),
                "mean_absolute_score_delta": (
                    sum(score_deltas) / len(score_deltas) if score_deltas else None
                ),
                "pair_records": records[:50],
                "invalid_pair_records": invalid[:50],
                "reproducibility": {
                    "random_seed": int(config.get("random_seed", 1729)),
                    "pair_source": (
                        "config_snapshot"
                        if isinstance(config.get("counterfactual_pairs"), list)
                        else "dataset_pair_field"
                    ),
                },
            },
        }
    ]


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    mean_left, mean_right = sum(left) / len(left), sum(right) / len(right)
    numerator = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right, strict=True))
    left_scale = math.sqrt(sum((a - mean_left) ** 2 for a in left))
    right_scale = math.sqrt(sum((b - mean_right) ** 2 for b in right))
    return numerator / (left_scale * right_scale) if left_scale and right_scale else 0.0


def _importance(rows: list[dict[str, Any]], feature: str, output: str) -> float | None:
    pairs = [
        (row.get(feature), row.get(output))
        for row in rows
        if not _missing(row.get(feature)) and not _missing(row.get(output))
    ]
    if len(pairs) < 2:
        return None
    left_numeric, right_numeric = (
        _numeric(pair[0] for pair in pairs),
        _numeric(pair[1] for pair in pairs),
    )
    if left_numeric is not None and right_numeric is not None:
        correlation = _pearson(left_numeric, right_numeric)
        return abs(correlation) if correlation is not None else None
    return normalized_mutual_information([pair[0] for pair in pairs], [pair[1] for pair in pairs])


def explanation_importances(
    rows: list[dict[str, Any]], config: dict[str, Any]
) -> tuple[dict[str, float], str]:
    shap_fields = config.get("shap_value_fields")
    if isinstance(shap_fields, dict) and shap_fields:
        importances = {}
        for feature, field in shap_fields.items():
            values = _numeric(row.get(str(field)) for row in rows)
            if values:
                importances[str(feature)] = sum(abs(value) for value in values) / len(values)
        return importances, str(config.get("shap_method", "precomputed_global_shap"))
    output = str(config.get("score_field") or config.get("decision_field", "decision"))
    return {
        feature: value
        for feature in map(str, config.get("feature_fields", []))
        if (value := _importance(rows, feature, output)) is not None
    }, "black_box_sensitivity"


def explainability_results(
    rows: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, object]]:
    importances, method = explanation_importances(rows, config)
    shap_compatible = method != "black_box_sensitivity"
    ordered = sorted(importances, key=lambda feature: (-importances[feature], feature))
    correlated: dict[str, list[str]] = defaultdict(list)
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            association = normalized_mutual_information(
                [row.get(left) for row in rows], [row.get(right) for row in rows]
            )
            if association is not None and association >= 0.8:
                correlated[left].append(right)
                correlated[right].append(left)
    background = config.get("explanation_background_dataset")
    seed = int(config.get("random_seed", 1729))
    results: list[dict[str, object]] = []
    for rank, feature in enumerate(ordered, start=1):
        results.append(
            {
                "category": "explainability",
                "metric_key": "global_feature_importance",
                "protected_attribute": None,
                "reference_group": None,
                "comparison_group": feature,
                "value": importances[feature],
                "lower_bound": None,
                "upper_bound": None,
                "status": (
                    "pass"
                    if shap_compatible and background
                    else "insufficient_evidence"
                    if shap_compatible
                    else "review_required"
                ),
                "threshold": None,
                "threshold_operator": None,
                "threshold_source": _threshold_source(config),
                "raw_counts": {"rows": len(rows)},
                "method": method,
                "details": {
                    "rank": rank,
                    "model_compatible_with_shap": shap_compatible,
                    "background_dataset": background if shap_compatible else None,
                    "random_seed": seed,
                    "correlated_features": correlated.get(feature, []),
                    "attribution_warning": (
                        "Correlated features can split attribution; importance is not causal."
                        if correlated.get(feature)
                        else "Feature importance describes model behavior, not causality."
                    ),
                    "method_boundary": (
                        "Aggregated SHAP values supplied by the controlled model adapter."
                        if shap_compatible
                        else "SHAP was unavailable; this is observational black-box sensitivity."
                    ),
                },
            }
        )
    if results:
        return results
    return [
        {
            "category": "explainability",
            "metric_key": "explanation_available",
            "protected_attribute": None,
            "reference_group": None,
            "comparison_group": None,
            "value": None,
            "lower_bound": None,
            "upper_bound": None,
            "status": "insufficient_evidence",
            "threshold": None,
            "threshold_operator": None,
            "threshold_source": _threshold_source(config),
            "raw_counts": {"rows": len(rows)},
            "method": "not_available",
            "details": {
                "background_dataset": None,
                "random_seed": seed,
                "method_boundary": "No feature fields or trusted SHAP values were supplied.",
            },
        }
    ]


def _js_divergence(current: list[object], baseline: list[object]) -> float | None:
    if not current or not baseline:
        return None
    current_counts, baseline_counts = Counter(map(str, current)), Counter(map(str, baseline))
    keys = set(current_counts).union(baseline_counts)
    result = 0.0
    for key in keys:
        p = current_counts[key] / len(current)
        q = baseline_counts[key] / len(baseline)
        midpoint = (p + q) / 2
        if p:
            result += 0.5 * p * math.log(p / midpoint)
        if q:
            result += 0.5 * q * math.log(q / midpoint)
    return result / math.log(2)


def _wasserstein(current: list[float], baseline: list[float]) -> float | None:
    if not current or not baseline:
        return None
    size = max(len(current), len(baseline))
    current_quantiles = [_percentile(current, index / max(size - 1, 1)) for index in range(size)]
    baseline_quantiles = [_percentile(baseline, index / max(size - 1, 1)) for index in range(size)]
    distance = (
        sum(abs(a - b) for a, b in zip(current_quantiles, baseline_quantiles, strict=True)) / size
    )
    scale = max(baseline) - min(baseline)
    return distance / scale if scale else (0.0 if distance == 0 else 1.0)


def _binary_performance(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, float]:
    decision_field = str(config.get("decision_field", "decision"))
    label_field = str(config["label_field"]) if config.get("label_field") else None
    if not label_field:
        return {}
    decision_positive = config.get("decision_positive_value", True)
    label_positive = config.get("label_positive_value", True)
    counts = Counter[str]()
    for row in rows:
        if _missing(row.get(decision_field)) or _missing(row.get(label_field)):
            continue
        decision = row[decision_field] == decision_positive
        label = row[label_field] == label_positive
        counts["tp" if decision and label else "fp" if decision else "fn" if label else "tn"] += 1
    total = sum(counts.values())
    metrics = {}
    if total:
        metrics["accuracy"] = (counts["tp"] + counts["tn"]) / total
    if counts["tp"] + counts["fp"]:
        metrics["precision"] = counts["tp"] / (counts["tp"] + counts["fp"])
    if counts["tp"] + counts["fn"]:
        metrics["recall"] = counts["tp"] / (counts["tp"] + counts["fn"])
    score_field = str(config["score_field"]) if config.get("score_field") else None
    if score_field:
        scored: list[tuple[float, bool]] = []
        for row in rows:
            if _missing(row.get(score_field)) or _missing(row.get(label_field)):
                continue
            try:
                scored.append(
                    (float(cast(Any, row[score_field])), row[label_field] == label_positive)
                )
            except (TypeError, ValueError):
                continue
        scored.sort(key=lambda item: item[0])
        positives = sum(label for _, label in scored)
        negatives = len(scored) - positives
        if positives and negatives:
            positive_rank_sum = 0.0
            index = 0
            while index < len(scored):
                end = index + 1
                while end < len(scored) and scored[end][0] == scored[index][0]:
                    end += 1
                average_rank = ((index + 1) + end) / 2
                positive_rank_sum += average_rank * sum(label for _, label in scored[index:end])
                index = end
            metrics["auc"] = (positive_rank_sum - positives * (positives + 1) / 2) / (
                positives * negatives
            )
    return metrics


def _drift_status(value: float | None, warning: float, critical: float) -> str:
    if value is None:
        return "insufficient_evidence"
    magnitude = abs(value)
    return "critical" if magnitude >= critical else "warning" if magnitude >= warning else "pass"


def drift_results(
    rows: list[dict[str, Any]], baseline_rows: list[dict[str, Any]] | None, config: dict[str, Any]
) -> list[dict[str, object]]:
    if not baseline_rows:
        return [
            {
                "category": "drift",
                "metric_key": "baseline_available",
                "protected_attribute": None,
                "reference_group": None,
                "comparison_group": None,
                "value": None,
                "lower_bound": None,
                "upper_bound": None,
                "status": "insufficient_evidence",
                "threshold": None,
                "threshold_operator": None,
                "threshold_source": _threshold_source(config),
                "raw_counts": {"current_rows": len(rows), "baseline_rows": 0},
                "method": "explicit_approved_baseline_required",
                "details": {
                    "drift_type": "baseline",
                    "interpretation": (
                        "No explicit baseline run was selected; no drift conclusion was made."
                    ),
                },
            }
        ]
    warning = float(config.get("drift_warning_threshold", 0.1))
    critical = float(config.get("drift_critical_threshold", 0.2))
    fields = list(
        dict.fromkeys(
            [
                *map(str, config.get("feature_fields", [])),
                *map(str, config.get("protected_attributes", [])),
            ]
        )
    )
    results: list[dict[str, object]] = []
    for field in fields:
        current_values = [row[field] for row in rows if not _missing(row.get(field))]
        baseline_values = [row[field] for row in baseline_rows if not _missing(row.get(field))]
        current_numeric, baseline_numeric = _numeric(current_values), _numeric(baseline_values)
        if current_numeric is not None and baseline_numeric is not None:
            value = _wasserstein(current_numeric, baseline_numeric)
            method = "normalized_wasserstein"
        else:
            value = _js_divergence(current_values, baseline_values)
            method = "jensen_shannon"
        results.append(
            {
                "category": "drift",
                "metric_key": "data_distribution_drift",
                "protected_attribute": field
                if field in config.get("protected_attributes", [])
                else None,
                "reference_group": "baseline",
                "comparison_group": field,
                "value": value,
                "lower_bound": None,
                "upper_bound": None,
                "status": _drift_status(value, warning, critical),
                "threshold": warning,
                "threshold_operator": "abs<=",
                "threshold_source": _threshold_source(config),
                "raw_counts": {
                    "current_rows": len(current_values),
                    "baseline_rows": len(baseline_values),
                },
                "method": method,
                "details": {
                    "drift_type": "data",
                    "change_kind": "distribution_change",
                    "harmful_performance_decline": False,
                    "warning_threshold": warning,
                    "critical_threshold": critical,
                    "seasonal_baseline": bool(config.get("seasonal_baseline", False)),
                },
            }
        )
    current_performance = _binary_performance(rows, config)
    baseline_performance = _binary_performance(baseline_rows, config)
    performance_warning = float(config.get("performance_drift_warning_threshold", 0.03))
    performance_critical = float(config.get("performance_drift_critical_threshold", 0.08))
    for metric in sorted(set(current_performance).intersection(baseline_performance)):
        delta = current_performance[metric] - baseline_performance[metric]
        harmful = delta < 0
        results.append(
            {
                "category": "drift",
                "metric_key": "performance_drift",
                "protected_attribute": None,
                "reference_group": "baseline",
                "comparison_group": metric,
                "value": delta,
                "lower_bound": None,
                "upper_bound": None,
                "status": _drift_status(delta, performance_warning, performance_critical)
                if harmful
                else "pass",
                "threshold": -performance_warning,
                "threshold_operator": ">=",
                "threshold_source": _threshold_source(config),
                "raw_counts": {"current_rows": len(rows), "baseline_rows": len(baseline_rows)},
                "method": "metric_delta",
                "details": {
                    "drift_type": "performance",
                    "baseline_value": baseline_performance[metric],
                    "current_value": current_performance[metric],
                    "change_kind": "harmful_performance_decline"
                    if harmful
                    else "performance_change",
                    "harmful_performance_decline": harmful,
                    "warning_threshold": performance_warning,
                    "critical_threshold": performance_critical,
                },
            }
        )
    decision_field = str(config.get("decision_field", "decision"))
    decision_positive = config.get("decision_positive_value", True)
    label_field = str(config["label_field"]) if config.get("label_field") else None
    label_positive = config.get("label_positive_value", True)
    score_field = str(config["score_field"]) if config.get("score_field") else None

    def group_monitor_values(group_rows: list[dict[str, Any]]) -> dict[str, float]:
        usable = [row for row in group_rows if not _missing(row.get(decision_field))]
        values: dict[str, float] = {}
        if usable:
            values["selection"] = sum(
                row.get(decision_field) == decision_positive for row in usable
            ) / len(usable)
        if label_field:
            labeled = [row for row in usable if not _missing(row.get(label_field))]
            if labeled:
                values["error"] = sum(
                    (row.get(decision_field) == decision_positive)
                    != (row.get(label_field) == label_positive)
                    for row in labeled
                ) / len(labeled)
                if score_field:
                    scored = [row for row in labeled if not _missing(row.get(score_field))]
                    try:
                        if scored:
                            mean_score = sum(
                                float(cast(Any, row[score_field])) for row in scored
                            ) / len(scored)
                            observed = sum(
                                row.get(label_field) == label_positive for row in scored
                            ) / len(scored)
                            values["calibration"] = mean_score - observed
                    except (TypeError, ValueError):
                        pass
        return values

    for protected in map(str, config.get("protected_attributes", [])):
        current_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        baseline_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            current_groups[str(row.get(protected, "Unknown"))].append(row)
        for row in baseline_rows:
            baseline_groups[str(row.get(protected, "Unknown"))].append(row)
        for group in sorted(
            set(current_groups).intersection(baseline_groups) - {"Unknown", "None"}
        ):
            current_group_metrics = group_monitor_values(current_groups[group])
            baseline_group_metrics = group_monitor_values(baseline_groups[group])
            for monitored_metric in sorted(
                set(current_group_metrics).intersection(baseline_group_metrics)
            ):
                delta = (
                    current_group_metrics[monitored_metric]
                    - baseline_group_metrics[monitored_metric]
                )
                results.append(
                    {
                        "category": "drift",
                        "metric_key": f"fairness_{monitored_metric}_drift",
                        "protected_attribute": protected,
                        "reference_group": "baseline",
                        "comparison_group": group,
                        "value": delta,
                        "lower_bound": None,
                        "upper_bound": None,
                        "status": _drift_status(delta, warning, critical),
                        "threshold": warning,
                        "threshold_operator": "abs<=",
                        "threshold_source": _threshold_source(config),
                        "raw_counts": {
                            "current_rows": len(current_groups[group]),
                            "baseline_rows": len(baseline_groups[group]),
                        },
                        "method": "group_rate_delta",
                        "details": {
                            "drift_type": "fairness",
                            "tracked_metric": monitored_metric,
                            "baseline_value": baseline_group_metrics[monitored_metric],
                            "current_value": current_group_metrics[monitored_metric],
                            "change_kind": "group_outcome_change",
                            "harmful_performance_decline": False,
                            "warning_threshold": warning,
                            "critical_threshold": critical,
                        },
                    }
                )
    current_importance, current_method = explanation_importances(rows, config)
    baseline_importance, _ = explanation_importances(baseline_rows, config)
    shared_features = set(current_importance).intersection(baseline_importance)
    if shared_features:
        current_rank = {
            feature: index
            for index, feature in enumerate(
                sorted(shared_features, key=lambda key: (-current_importance[key], key)), start=1
            )
        }
        baseline_rank = {
            feature: index
            for index, feature in enumerate(
                sorted(shared_features, key=lambda key: (-baseline_importance[key], key)), start=1
            )
        }
        max_distance = max(1, len(shared_features) * max(1, len(shared_features) - 1))
        rank_drift = (
            sum(abs(current_rank[feature] - baseline_rank[feature]) for feature in shared_features)
            / max_distance
        )
        results.append(
            {
                "category": "drift",
                "metric_key": "explanation_rank_drift",
                "protected_attribute": None,
                "reference_group": "baseline",
                "comparison_group": "global_feature_ranking",
                "value": rank_drift,
                "lower_bound": None,
                "upper_bound": None,
                "status": _drift_status(rank_drift, warning, critical),
                "threshold": warning,
                "threshold_operator": "<=",
                "threshold_source": _threshold_source(config),
                "raw_counts": {"shared_features": len(shared_features)},
                "method": "normalized_rank_footrule",
                "details": {
                    "drift_type": "explanation",
                    "explanation_method": current_method,
                    "baseline_ranks": baseline_rank,
                    "current_ranks": current_rank,
                    "change_kind": "attribution_change",
                    "harmful_performance_decline": False,
                    "warning_threshold": warning,
                    "critical_threshold": critical,
                },
            }
        )
        shap_fields = config.get("shap_value_fields")
        for feature in sorted(shared_features):
            method = "importance_delta"
            contribution_drift = abs(current_importance[feature] - baseline_importance[feature])
            if isinstance(shap_fields, dict) and feature in shap_fields:
                shap_field = str(shap_fields[feature])
                current_contributions = _numeric(row.get(shap_field) for row in rows)
                baseline_contributions = _numeric(row.get(shap_field) for row in baseline_rows)
                if current_contributions and baseline_contributions:
                    contribution_drift = (
                        _wasserstein(current_contributions, baseline_contributions) or 0.0
                    )
                    method = "normalized_wasserstein_shap_distribution"
            results.append(
                {
                    "category": "drift",
                    "metric_key": "explanation_contribution_drift",
                    "protected_attribute": None,
                    "reference_group": "baseline",
                    "comparison_group": feature,
                    "value": contribution_drift,
                    "lower_bound": None,
                    "upper_bound": None,
                    "status": _drift_status(contribution_drift, warning, critical),
                    "threshold": warning,
                    "threshold_operator": "<=",
                    "threshold_source": _threshold_source(config),
                    "raw_counts": {"current_rows": len(rows), "baseline_rows": len(baseline_rows)},
                    "method": method,
                    "details": {
                        "drift_type": "explanation",
                        "baseline_value": baseline_importance[feature],
                        "current_value": current_importance[feature],
                        "change_kind": "contribution_distribution_change",
                        "harmful_performance_decline": False,
                        "warning_threshold": warning,
                        "critical_threshold": critical,
                    },
                }
            )
    return results
