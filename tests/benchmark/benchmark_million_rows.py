from __future__ import annotations

import argparse
import json
import platform
import resource
import sys
import time
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fairhire_domain.audit import CALCULATION_VERSION, run_binary_audit

FEATURE_COUNT = 50
FEATURE_NAMES = tuple(f"feature_{index:02d}" for index in range(FEATURE_COUNT))
BASE_KEYS = (
    "candidate_id",
    "group",
    "selected",
    "qualified",
    "score",
    "decision_at",
)


class CompactRow(Mapping[str, object]):
    """A memory-bounded synthetic row that still exposes all 50 real feature columns."""

    __slots__ = ("index", "split")

    def __init__(self, index: int, split: int) -> None:
        self.index = index
        self.split = split

    def __getitem__(self, key: str) -> object:
        if key == "candidate_id":
            return self.index
        if key == "group":
            return "reference" if self.index < self.split else "comparison"
        if key == "qualified":
            return self.index % 10 < 7
        if key == "selected":
            qualified = self.index % 10 < 7
            reference = self.index < self.split
            return qualified and (self.index % 20 < (14 if reference else 10))
        if key == "score":
            return (self.index % 100) / 100
        if key == "decision_at":
            return "2026-01-01T00:00:00Z" if self.index % 2 else "2026-06-30T00:00:00Z"
        if key.startswith("feature_"):
            feature_index = int(key.removeprefix("feature_"))
            return (self.index * (feature_index + 3)) % 101
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(BASE_KEYS + FEATURE_NAMES)

    def __len__(self) -> int:
        return len(BASE_KEYS) + FEATURE_COUNT


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Week 14 base-audit load target")
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--max-seconds", type=float, default=1_200)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.rows < 1_000:
        parser.error("--rows must be at least 1000")

    rows = [CompactRow(index, args.rows // 2) for index in range(args.rows)]
    config: dict[str, Any] = {
        "identifier_field": "candidate_id",
        "decision_field": "selected",
        "label_field": "qualified",
        "score_field": "score",
        "timestamp_field": "decision_at",
        "protected_attributes": ["group"],
        "feature_fields": list(FEATURE_NAMES),
        "reference_groups": {"group": "reference"},
        "minimum_samples": 200,
        "hard_suppression_floor": 20,
        "bootstrap_iterations": 20,
        "bootstrap_max_sample_size": 10_000,
        "random_seed": 20260904,
        "minimum_time_coverage_days": 28,
        "basic_audit_only": True,
    }
    started = time.perf_counter()
    result = run_binary_audit(rows, config)  # type: ignore[arg-type]
    elapsed = time.perf_counter() - started
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_bytes = peak_rss if sys.platform == "darwin" else peak_rss * 1024
    evidence = {
        "scenario": f"base_fairness_audit_{args.rows}_rows_50_features",
        "recorded_at": datetime.now(UTC).isoformat(),
        "rows": args.rows,
        "features": FEATURE_COUNT,
        "elapsed_seconds": round(elapsed, 3),
        "target_seconds": args.max_seconds,
        "passed": elapsed < args.max_seconds,
        "metric_count": len(result["metrics"]),
        "calculation_version": CALCULATION_VERSION,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "peak_rss_bytes": peak_rss_bytes,
        "random_seed": config["random_seed"],
    }
    encoded = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
