from uuid import uuid4


def new_id(prefix: str) -> str:
    """Return a prefixed opaque identifier that fits the platform's VARCHAR(36) contract."""
    suffix_length = 35 - len(prefix)
    if suffix_length < 8:
        raise ValueError("ID prefix is too long")
    return f"{prefix}-{uuid4().hex[:suffix_length]}"
