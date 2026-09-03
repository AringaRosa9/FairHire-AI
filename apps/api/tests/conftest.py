from collections.abc import Generator

import pytest
from fairhire_domain.access import Role
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from fairhire_api.db import Base, get_db
from fairhire_api.main import app
from fairhire_api.models import AISystem, AuditRun, MetricResult, Organization
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
                Organization(
                    id="org-one",
                    name="Northstar",
                    region="eu",
                    policy_pack="eu-core+de@2026.09",
                    retention_policy={"candidate_raw_days": 30},
                ),
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
                AuditRun(
                    id="run-metrics",
                    organization_id="org-one",
                    ai_system_id="sys-one",
                    model_version_id="model-one",
                    dataset_id="dataset-one",
                    policy_pack_version="eu-core+de@2026.09",
                    config_snapshot={"random_seed": 42},
                    data_fingerprint="f" * 64,
                    status="succeeded",
                    job_id="job-metrics",
                    submitted_by="user-one",
                ),
                MetricResult(
                    id="metric-one",
                    organization_id="org-one",
                    audit_run_id="run-metrics",
                    category="fairness",
                    metric_key="demographic_parity_ratio",
                    protected_attribute="gender",
                    reference_group="women",
                    comparison_group="men",
                    value=0.78,
                    lower_bound=0.69,
                    upper_bound=0.88,
                    status="review_required",
                    threshold=0.8,
                    threshold_operator=">=",
                    threshold_source={
                        "source_type": "approved_test_strategy",
                        "source_id": "strategy-eu-binary-v1",
                        "legal_determination": False,
                    },
                    raw_counts={"comparison": {"n": 250, "selected": 98}},
                    method="stratified_bootstrap_percentile",
                    calculation_version="fairhire-binary-audit@1.0.0",
                    details={"bootstrap_iterations": 1000, "random_seed": 42},
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
