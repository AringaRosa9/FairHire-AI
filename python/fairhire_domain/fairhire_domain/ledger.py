import hashlib
import json
from datetime import UTC, datetime


def iso_utc(value: datetime) -> str:
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(UTC).isoformat()


def event_hash(
    *,
    event_id: str,
    organization_id: str,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    payload: dict[str, object],
    previous_hash: str | None,
    occurred_at: datetime,
) -> str:
    canonical = json.dumps(
        {
            "id": event_id,
            "organization_id": organization_id,
            "actor_id": actor_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "payload": payload,
            "previous_hash": previous_hash,
            "occurred_at": iso_utc(occurred_at),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
