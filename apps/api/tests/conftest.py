from collections.abc import Generator

import pytest
from fairhire_domain.access import Role
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from fairhire_api.db import Base, get_db
from fairhire_api.main import app
from fairhire_api.models import AISystem
from fairhire_api.security import Principal, get_principal


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add_all(
            [
                AISystem(
                    id="sys-one",
                    organization_id="org-one",
                    name="Visible System",
                    purpose="Scores candidate applications for reviewer prioritization",
                    lifecycle_status="active",
                    release_status="review_required",
                    provider_type="internal",
                    jurisdictions=["EU"],
                    owner_name="Maya Chen",
                    assessment_version=1,
                ),
                AISystem(
                    id="sys-secret",
                    organization_id="org-other",
                    name="Other Tenant Secret",
                    purpose="Must be inaccessible to the active organization",
                    lifecycle_status="active",
                    release_status="approved",
                    provider_type="internal",
                    jurisdictions=["EU"],
                    owner_name="Other User",
                    assessment_version=1,
                ),
            ]
        )
        session.commit()
        yield session


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    principal = Principal(
        user_id="user-one",
        email="maya@example.test",
        display_name="Maya Chen",
        organization_id="org-one",
        organization_name="Northstar",
        role=Role.ADMIN,
    )
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: principal
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
