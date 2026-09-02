from typing import Annotated
from uuid import uuid4

from fairhire_domain.access import Permission
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import __version__
from .db import get_db
from .models import AISystem
from .schemas import AISystemCreate, AISystemListResponse, AISystemResponse, SessionResponse
from .security import Principal, get_principal, require_idempotency_key, require_permission

router = APIRouter(prefix="/v1")


@router.get("/health", tags=["platform"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/session", response_model=SessionResponse, tags=["identity"])
def session(principal: Annotated[Principal, Depends(get_principal)]) -> SessionResponse:
    return SessionResponse(
        user_id=principal.user_id,
        email=principal.email,
        display_name=principal.display_name,
        organization_id=principal.organization_id,
        organization_name=principal.organization_name,
        role=principal.role,
        permissions=sorted(permission.value for permission in principal.permissions),
    )


@router.get("/ai-systems", response_model=AISystemListResponse, tags=["registry"])
def list_ai_systems(
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_READ))],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> AISystemListResponse:
    predicate = AISystem.organization_id == principal.organization_id
    total = db.scalar(select(func.count()).select_from(AISystem).where(predicate)) or 0
    systems = db.scalars(
        select(AISystem)
        .where(predicate)
        .order_by(AISystem.next_review_at.asc().nullslast(), AISystem.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AISystemListResponse(
        items=[AISystemResponse.model_validate(system) for system in systems],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/ai-systems",
    response_model=AISystemResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["registry"],
)
def create_ai_system(
    payload: AISystemCreate,
    principal: Annotated[Principal, Depends(require_permission(Permission.SYSTEM_WRITE))],
    db: Annotated[Session, Depends(get_db)],
    _idempotency_key: Annotated[str, Depends(require_idempotency_key)],
) -> AISystemResponse:
    system = AISystem(
        id=f"sys-{uuid4()}",
        organization_id=principal.organization_id,
        assessment_version=1,
        **payload.model_dump(),
    )
    db.add(system)
    db.commit()
    db.refresh(system)
    return AISystemResponse.model_validate(system)
