from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class BiasCase:
    key: str
    description: str
    rows: list[dict[str, object]]
    expected_metric: str
    expected_status: str
    expected_sign: int


def _row(index: int, group: str, *, selected: bool, qualified: bool) -> dict[str, object]:
    return {
        "candidate_id": f"candidate-{group}-{index}",
        "group": group,
        "selected": selected,
        "qualified": qualified,
        "score": 0.85 if selected else 0.25,
        "decision_at": f"2026-{1 + index % 6:02d}-{1 + index % 27:02d}T00:00:00Z",
        "experience": index % 20,
    }


def disparate_selection() -> BiasCase:
    rows: list[dict[str, object]] = []
    for index in range(500):
        rows.append(_row(index, "reference", selected=index < 400, qualified=index < 350))
        rows.append(_row(index, "comparison", selected=index < 250, qualified=index < 350))
    return BiasCase(
        key="disparate_selection",
        description="Equal-sized groups with 80% versus 50% selection rates.",
        rows=rows,
        expected_metric="demographic_parity_ratio",
        expected_status="review_required",
        expected_sign=1,
    )


def equal_selection_unequal_opportunity() -> BiasCase:
    rows: list[dict[str, object]] = []
    for index in range(500):
        qualified = index < 300
        reference_selected = index < 240 or 300 <= index < 360
        comparison_selected = index < 150 or 300 <= index < 450
        rows.append(_row(index, "reference", selected=reference_selected, qualified=qualified))
        rows.append(_row(index, "comparison", selected=comparison_selected, qualified=qualified))
    return BiasCase(
        key="equal_selection_unequal_opportunity",
        description="Both groups select 60%, while true-positive rates are 80% and 50%.",
        rows=rows,
        expected_metric="equal_opportunity_difference",
        expected_status="review_required",
        expected_sign=-1,
    )


def sparse_and_unknown_group() -> BiasCase:
    rows = [
        _row(
            index,
            "reference" if index < 480 else ("comparison" if index < 495 else "Unknown"),
            selected=index % 2 == 0,
            qualified=index % 3 != 0,
        )
        for index in range(500)
    ]
    for row in rows[-5:]:
        row["group"] = None
    return BiasCase(
        key="sparse_and_unknown_group",
        description="A comparison group is below the evidence floor and unknown values remain.",
        rows=rows,
        expected_metric="demographic_parity_ratio",
        expected_status="insufficient_evidence",
        expected_sign=0,
    )


CASES: tuple[Callable[[], BiasCase], ...] = (
    disparate_selection,
    equal_selection_unequal_opportunity,
    sparse_and_unknown_group,
)


AUDIT_CONFIG: dict[str, object] = {
    "identifier_field": "candidate_id",
    "decision_field": "selected",
    "label_field": "qualified",
    "score_field": "score",
    "timestamp_field": "decision_at",
    "protected_attributes": ["group"],
    "feature_fields": ["experience"],
    "reference_groups": {"group": "reference"},
    "minimum_samples": 200,
    "hard_suppression_floor": 20,
    "bootstrap_iterations": 80,
    "bootstrap_max_sample_size": 10_000,
    "random_seed": 20260904,
    "basic_audit_only": True,
}
