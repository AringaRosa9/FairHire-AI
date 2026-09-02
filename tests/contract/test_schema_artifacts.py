import json
from pathlib import Path

from fairhire_domain.data_contract import BinaryClassificationContract

ROOT = Path(__file__).resolve().parents[2]


def test_checked_in_binary_contract_example_is_valid() -> None:
    payload = json.loads(
        (ROOT / "packages/policy-schemas/binary-classification/example.json").read_text()
    )
    contract = BinaryClassificationContract.model_validate(payload)
    assert contract.minimum_samples.conclusion_when_below_default == "insufficient_evidence"
    assert all(field.vault_only for field in contract.fields if field.role == "protected_attribute")
