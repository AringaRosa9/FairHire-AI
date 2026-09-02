# Binary classification audit contract v1.0.0

The machine-readable schema is `packages/policy-schemas/binary-classification/1.0.0.schema.json`; the Pydantic enforcement lives in `python/fairhire_domain`. Ranking fields are reserved for a later additive schema and are not interpreted as ranking metrics in MVP.

## Required roles

| Role | Cardinality | Rule |
|---|---:|---|
| `identifier` | exactly 1 | Anonymous stable candidate ID; never a report dimension |
| `decision` | exactly 1 | Binary shortlist/select decision with explicit positive value |
| `timestamp` | at least 1 | Decision or observation time in UTC with source timezone recorded |
| `prediction` | 0–1 | Score or predicted class; scale and threshold are metadata |
| `label` | 0–1 | Real outcome; absence disables label-dependent metrics |
| `protected_attribute` | 0+ | Customer-provided under a documented lawful basis; `vault_only=true` |
| `feature` | 0+ | Model-visible input; must not silently include protected attributes |
| `metadata` | 0+ | Source/batch/reference data excluded from model analysis by default |

Accepted containers are CSV, Parquet and JSONL. The ingestion service records content hash, size, MIME, schema version, row count, missingness, time range, source, collection purpose, lawful-basis reference and retention deadline. Pickle and Joblib are rejected.

## Minimum sample policy

- Proposed organization default: 200 rows per reported comparison group.
- Hard suppression floor: 20 rows; below it, raw cell counts and derived ratios are hidden from standard export.
- Below 200, status is `insufficient_evidence`, never Pass. The result may still carry a wide interval for authorized analysts above the suppression floor.
- Default confidence level: 95%. Bootstrap random seed, replicate count and stratification fields are saved with the result.
- Intersections use the same threshold; the system does not combine or relabel groups to manufacture sufficiency.

The values are policy defaults awaiting DPO/Responsible AI approval, not legal thresholds.

## Metric definitions

Let TP, FP, TN and FN be raw counts for a named group and let `selected` be the positive decision.

| Metric | Definition | Labels required | Uncertainty |
|---|---|---:|---|
| Selection rate | selected / applicants | No | Wilson interval for group rate |
| Demographic parity difference | group selection rate − reference rate | No | Stratified bootstrap |
| Demographic parity ratio | group selection rate / reference rate | No | Stratified bootstrap; undefined when reference is zero |
| True positive rate | TP / (TP + FN) | Yes | Bootstrap or Wilson per group |
| False positive rate | FP / (FP + TN) | Yes | Bootstrap or Wilson per group |
| Equal opportunity difference | group TPR − reference TPR | Yes | Stratified bootstrap |
| Equalized odds difference | max absolute TPR/FPR difference | Yes | Stratified bootstrap |
| Precision | TP / (TP + FP) | Yes | Wilson interval |
| Calibration | observed outcome by score bin | Yes + score | Calibration curve with bin counts |
| Error rate | (FP + FN) / total labeled | Yes | Wilson interval |

Undefined denominators produce `insufficient_evidence`. Unknown or missing groups remain visible in data quality results but are not silently assigned to a protected category.

## Threshold provenance

Every comparison must reference an `organization_policy`, `rule_pack`, or `approved_test_strategy`, including source ID, semantic version, approver, and effective date. `legal_determination` is fixed to false in this schema. Changing threshold or source creates a new audit configuration and requires re-approval; history is not recalculated in place.

