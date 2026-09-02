from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

import jwt
from fairhire_domain.access import ROLE_PERMISSIONS, Permission, Role
from fastapi import Depends, Header, HTTPException, Request, status
from jwt import PyJWKClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .db import get_db
from .models import Membership, Organization


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str
    display_name: str
    organization_id: str
    organization_name: str
    role: Role

    @property
    def permissions(self) -> frozenset[Permission]:
        return ROLE_PERMISSIONS[self.role]


class OIDCVerifier:
    def __init__(self, issuer: str, audience: str) -> None:
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self.jwks = PyJWKClient(f"{self.issuer}/.well-known/jwks.json")

    def verify(self, token: str) -> dict[str, object]:
        key = self.jwks.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            key.key,
            algorithms=["RS256", "ES256"],
            audience=self.audience,
            issuer=self.issuer,
        )


def _set_tenant_context(db: Session, organization_id: str) -> None:
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT set_config('app.organization_id', :organization_id, true)"),
            {"organization_id": organization_id},
        )


def get_principal(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    organization_id: Annotated[str | None, Header(alias="X-Organization-ID")] = None,
    dev_user: Annotated[str | None, Header(alias="X-Dev-User")] = None,
) -> Principal:
    if not organization_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "X-Organization-ID is required")
    user_id: str
    if settings.dev_auth_enabled:
        if not dev_user:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "X-Dev-User is required in development mode"
            )
        user_id = dev_user
    else:
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bearer token is required")
        try:
            claims = OIDCVerifier(settings.oidc_issuer, settings.oidc_audience).verify(
                authorization.removeprefix("Bearer ")
            )
            user_id = str(claims["sub"])
        except (jwt.PyJWTError, KeyError) as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid identity token") from exc

    _set_tenant_context(db, organization_id)
    membership = db.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
            Membership.active.is_(True),
        )
    )
    organization = db.get(Organization, organization_id)
    if not membership or not organization:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No active membership in this organization")
    return Principal(
        user_id=user_id,
        email=membership.email,
        display_name=membership.display_name,
        organization_id=organization_id,
        organization_name=organization.name,
        role=Role(membership.role),
    )


def require_permission(permission: Permission) -> Callable[..., Principal]:
    def dependency(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if permission not in principal.permissions:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {permission}")
        return principal

    return dependency


def require_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    if not idempotency_key or len(idempotency_key) > 128:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "A valid Idempotency-Key header is required"
        )
    return idempotency_key
