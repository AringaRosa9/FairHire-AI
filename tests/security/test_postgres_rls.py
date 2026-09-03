import os

import psycopg
import pytest

APP_DATABASE_URL = os.getenv("APP_DATABASE_URL")


@pytest.mark.skipif(not APP_DATABASE_URL, reason="requires a migrated PostgreSQL app-role database")
def test_rls_hides_other_tenant_systems() -> None:
    assert APP_DATABASE_URL is not None
    with psycopg.connect(APP_DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.organization_id', %s, true)", ("org-northstar",))
        cursor.execute("SELECT id FROM ai_systems ORDER BY id")
        ids = [row[0] for row in cursor.fetchall()]
        assert "sys-talentrank" in ids
        assert "sys-other-secret" not in ids


@pytest.mark.skipif(not APP_DATABASE_URL, reason="requires a migrated PostgreSQL app-role database")
def test_rls_rejects_cross_tenant_insert() -> None:
    assert APP_DATABASE_URL is not None
    with psycopg.connect(APP_DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.organization_id', %s, true)", ("org-northstar",))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute(
                """
                INSERT INTO ai_systems (
                    id, organization_id, name, purpose, lifecycle_status, release_status,
                    provider_type, jurisdictions, owner_name, assessment_version
                ) VALUES (
                    'sys-cross-tenant-test', 'org-other', 'Forbidden',
                    'Attempted cross-tenant write', 'draft', 'draft', 'internal',
                    '[\"EU\"]'::json, 'Attacker', 1
                )
                """
            )


@pytest.mark.skipif(not APP_DATABASE_URL, reason="requires a migrated PostgreSQL app-role database")
def test_all_tenant_tables_through_governance_loop_force_rls() -> None:
    assert APP_DATABASE_URL is not None
    expected = {
        "regulatory_assessments",
        "model_versions",
        "onboarding_drafts",
        "datasets",
        "dataset_fields",
        "audit_runs",
        "background_jobs",
        "metric_results",
        "findings",
        "remediation_tasks",
        "finding_retests",
        "approvals",
    }
    with psycopg.connect(APP_DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = ANY(%s)
              AND c.relrowsecurity
              AND c.relforcerowsecurity
            """,
            (list(expected),),
        )
        protected = {row[0] for row in cursor.fetchall()}
        assert protected == expected
