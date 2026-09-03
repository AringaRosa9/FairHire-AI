import base64
import hmac
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from urllib.parse import quote, urlencode

from .config import Settings


def _sign(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode(), sha256).digest()


def presign_upload(
    *, settings: Settings, object_key: str, content_type: str, checksum: str
) -> tuple[str, dict[str, str], datetime]:
    """Create a SigV4 PUT URL without routing customer bytes through the API."""
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=settings.upload_url_ttl_seconds)
    date = now.strftime("%Y%m%d")
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    scope = f"{date}/{settings.s3_region}/s3/aws4_request"
    credential = f"{settings.s3_access_key}/{scope}"
    canonical_uri = f"/{quote(settings.s3_bucket)}/{quote(object_key, safe='/')}"
    signed_headers = "content-type;host;x-amz-checksum-sha256"
    endpoint = (settings.s3_public_endpoint or settings.s3_endpoint).rstrip("/")
    host = endpoint.split("//", maxsplit=1)[-1]
    query = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": credential,
        "X-Amz-Date": timestamp,
        "X-Amz-Expires": str(settings.upload_url_ttl_seconds),
        "X-Amz-SignedHeaders": signed_headers,
    }
    canonical_query = urlencode(sorted(query.items()), quote_via=quote)
    checksum_base64 = base64.b64encode(bytes.fromhex(checksum)).decode()
    canonical_headers = (
        f"content-type:{content_type}\nhost:{host}\nx-amz-checksum-sha256:{checksum_base64}\n"
    )
    canonical_request = "\n".join(
        [
            "PUT",
            canonical_uri,
            canonical_query,
            canonical_headers,
            signed_headers,
            "UNSIGNED-PAYLOAD",
        ]
    )
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            timestamp,
            scope,
            sha256(canonical_request.encode()).hexdigest(),
        ]
    )
    date_key = _sign(f"AWS4{settings.s3_secret_key}".encode(), date)
    region_key = _sign(date_key, settings.s3_region)
    service_key = _sign(region_key, "s3")
    signing_key = _sign(service_key, "aws4_request")
    query["X-Amz-Signature"] = hmac.new(signing_key, string_to_sign.encode(), sha256).hexdigest()
    url = f"{endpoint}{canonical_uri}?{urlencode(sorted(query.items()), quote_via=quote)}"
    headers = {"Content-Type": content_type, "x-amz-checksum-sha256": checksum_base64}
    return url, headers, expires_at
