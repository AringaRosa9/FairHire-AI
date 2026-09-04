from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest

from fairhire_api.config import Settings
from fairhire_api.evidence_routes import _safe_csv_value
from fairhire_api.storage import presign_upload


def test_production_refuses_development_identity_and_missing_scanner_secret() -> None:
    with pytest.raises(ValueError, match="DEV_AUTH_ENABLED"):
        Settings(app_env="production", dev_auth_enabled=True)
    with pytest.raises(ValueError, match="SCANNER_ATTESTATION_SECRET"):
        Settings(
            app_env="production",
            dev_auth_enabled=False,
            scanner_attestation_secret=None,
        )


def test_signed_upload_is_short_lived_checksum_bound_and_tenant_scoped() -> None:
    settings = Settings(
        app_env="test",
        dev_auth_enabled=True,
        s3_public_endpoint="https://uploads.example.test",
        s3_access_key="test-access",
        s3_secret_key="test-secret",
        s3_bucket="pilot",
        upload_url_ttl_seconds=300,
    )
    object_key = "org-one/systems/sys-one/datasets/data-one/decisions.csv"
    url, headers, expires_at = presign_upload(
        settings=settings,
        object_key=object_key,
        content_type="text/csv",
        checksum="a" * 64,
    )
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.path == f"/pilot/{object_key}"
    assert query["X-Amz-Expires"] == ["300"]
    assert query["X-Amz-SignedHeaders"] == ["content-type;host;x-amz-checksum-sha256"]
    assert "x-amz-checksum-sha256" in headers
    assert 0 < (expires_at - datetime.now(UTC)).total_seconds() <= 300
    assert "test-secret" not in url


@pytest.mark.parametrize("value", ["=cmd()", "+SUM(A1:A2)", "-2+3", "@IMPORTDATA(x)"])
def test_csv_exports_neutralize_spreadsheet_formulas(value: str) -> None:
    assert _safe_csv_value(value) == f"'{value}"


def test_csv_exports_leave_normal_evidence_unchanged() -> None:
    assert _safe_csv_value("demographic parity ratio") == "demographic parity ratio"
    assert _safe_csv_value(0.73) == 0.73
