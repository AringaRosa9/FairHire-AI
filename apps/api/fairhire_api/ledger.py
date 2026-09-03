import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ids import new_id
from .models import AuditEvent


def _iso_utc(value: datetime) -> str:
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(UTC).isoformat()


def _event_hash(
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
            "occurred_at": _iso_utc(occurred_at),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def append_event(
    db: Session,
    *,
    organization_id: str,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    payload: dict[str, object] | None = None,
    reason: str | None = None,
    correlation_id: str | None = None,
) -> AuditEvent:
    previous = db.scalar(
        select(AuditEvent)
        .where(AuditEvent.organization_id == organization_id)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(1)
    )
    event_id = new_id("evt")
    occurred_at = datetime.now(UTC)
    event_payload: dict[str, object] = {
        **(payload or {}),
        "correlation_id": correlation_id or new_id("corr"),
    }
    if reason:
        event_payload["reason"] = reason
    previous_hash = previous.current_hash if previous else None
    current_hash = _event_hash(
        event_id=event_id,
        organization_id=organization_id,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=event_payload,
        previous_hash=previous_hash,
        occurred_at=occurred_at,
    )
    event = AuditEvent(
        id=event_id,
        organization_id=organization_id,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=event_payload,
        previous_hash=previous_hash,
        current_hash=current_hash,
        occurred_at=occurred_at,
    )
    db.add(event)
    return event


def verify_chain(events: list[AuditEvent]) -> tuple[bool, str | None]:
    previous_hash: str | None = None
    for event in events:
        expected = _event_hash(
            event_id=event.id,
            organization_id=event.organization_id,
            actor_id=event.actor_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            payload=event.payload,
            previous_hash=previous_hash,
            occurred_at=event.occurred_at,
        )
        if event.previous_hash != previous_hash or event.current_hash != expected:
            return False, event.id
        previous_hash = event.current_hash
    return True, None
