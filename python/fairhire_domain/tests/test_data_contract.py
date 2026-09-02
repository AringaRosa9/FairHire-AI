import pytest
from fairhire_domain.data_contract import BinaryClassificationContract
from pydantic import ValidationError


def test_binary_contract_rejects_unisolated_protected_attributes() -> None:
    with pytest.raises(ValidationError, match="vault_only"):
        BinaryClassificationContract.model_validate(
            {
                "decision_positive_value": True,
                "fields": [
                    {"name": "candidate_id", "role": "identifier", "data_type": "string"},
                    {"name": "selected", "role": "decision", "data_type": "boolean"},
                    {"name": "event_at", "role": "timestamp", "data_type": "datetime"},
                    {"name": "gender", "role": "protected_attribute", "data_type": "category"},
                ],
                "threshold_source": {
                    "source_type": "approved_test_strategy",
                    "source_id": "strategy-1",
                    "version": "1",
                    "effective_from": "2026-09-01",
                },
                "metrics": [
                    {
                        "key": "selection_rate",
                        "requires_label": False,
                        "value_range": [0, 1],
                        "comparison": "absolute",
                        "uncertainty_method": "wilson",
                    }
                ],
            }
        )
