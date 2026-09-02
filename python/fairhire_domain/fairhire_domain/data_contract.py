from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class FieldRole(StrEnum):
    IDENTIFIER = "identifier"
    FEATURE = "feature"
    PROTECTED_ATTRIBUTE = "protected_attribute"
    LABEL = "label"
    PREDICTION = "prediction"
    DECISION = "decision"
    TIMESTAMP = "timestamp"
    METADATA = "metadata"


class FieldDefinition(BaseModel):
    name: str
    role: FieldRole
    data_type: Literal["string", "integer", "number", "boolean", "date", "datetime", "category"]
    nullable: bool = False
    allowed_values: list[str | int | float | bool] | None = None
    vault_only: bool = False

    @model_validator(mode="after")
    def protected_fields_stay_in_vault(self) -> "FieldDefinition":
        if self.role == FieldRole.PROTECTED_ATTRIBUTE and not self.vault_only:
            raise ValueError("protected attributes must be vault_only")
        return self


class MinimumSampleStrategy(BaseModel):
    organization_default: Annotated[int, Field(ge=20)] = 200
    hard_suppression_floor: Annotated[int, Field(ge=5)] = 20
    confidence_level: Annotated[float, Field(gt=0.5, lt=1)] = 0.95
    conclusion_when_below_default: Literal["insufficient_evidence"] = "insufficient_evidence"
    suppress_raw_counts_below_floor: Literal[True] = True


class ThresholdSource(BaseModel):
    source_type: Literal["organization_policy", "rule_pack", "approved_test_strategy"]
    source_id: str
    version: str
    approved_by: str | None = None
    effective_from: str
    legal_determination: Literal[False] = False


class MetricDefinition(BaseModel):
    key: Literal[
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
    ]
    requires_label: bool
    value_range: tuple[float, float]
    comparison: Literal["absolute", "difference", "ratio", "curve"]
    uncertainty_method: Literal["bootstrap_percentile", "wilson", "calibration_curve"]


class BinaryClassificationContract(BaseModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    task_type: Literal["binary_classification"] = "binary_classification"
    decision_positive_value: str | int | bool
    label_positive_value: str | int | bool | None = None
    fields: Annotated[list[FieldDefinition], Field(min_length=3)]
    minimum_samples: MinimumSampleStrategy = MinimumSampleStrategy()
    threshold_source: ThresholdSource
    metrics: Annotated[list[MetricDefinition], Field(min_length=1)]

    @model_validator(mode="after")
    def require_core_roles(self) -> "BinaryClassificationContract":
        roles = {field.role for field in self.fields}
        required = {FieldRole.IDENTIFIER, FieldRole.DECISION, FieldRole.TIMESTAMP}
        missing = required - roles
        if missing:
            raise ValueError(f"missing required field roles: {', '.join(sorted(missing))}")
        if sum(field.role == FieldRole.IDENTIFIER for field in self.fields) != 1:
            raise ValueError("exactly one anonymous identifier is required")
        return self
