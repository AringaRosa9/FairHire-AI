import hashlib
import hmac
import os
from datetime import UTC, datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ENDPOINT = os.getenv("S3_ENDPOINT", "http://minio:9000").rstrip("/")
ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "fairhire")
SECRET_KEY = os.getenv("S3_SECRET_KEY", "fairhire_local_only")
BUCKET = os.getenv("S3_BUCKET", "fairhire-local")
REGION = os.getenv("S3_REGION", "us-east-1")


def _sign(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode(), hashlib.sha256).digest()


def put(*, query: str = "", body: bytes = b"") -> None:
    now = datetime.now(UTC)
    date = now.strftime("%Y%m%d")
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    host = ENDPOINT.split("//", maxsplit=1)[-1]
    payload_hash = hashlib.sha256(body).hexdigest()
    request_headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": timestamp,
    }
    signed_headers = ";".join(sorted(request_headers))
    canonical_headers = "".join(
        f"{name}:{request_headers[name]}\n" for name in sorted(request_headers)
    )
    canonical_request = "\n".join(
        ["PUT", f"/{BUCKET}", query, canonical_headers, signed_headers, payload_hash]
    )
    scope = f"{date}/{REGION}/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            timestamp,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )
    date_key = _sign(f"AWS4{SECRET_KEY}".encode(), date)
    region_key = _sign(date_key, REGION)
    service_key = _sign(region_key, "s3")
    signing_key = _sign(service_key, "aws4_request")
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={ACCESS_KEY}/{scope},"
        f"SignedHeaders={signed_headers},Signature={signature}"
    )
    suffix = f"?{query}" if query else ""
    request = Request(
        f"{ENDPOINT}/{BUCKET}{suffix}",
        method="PUT",
        data=body,
        headers={
            "Authorization": authorization,
            **request_headers,
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            if response.status not in {200, 204}:
                raise RuntimeError(f"Object store returned {response.status}")
    except HTTPError as exc:
        if not query and exc.code == 409:
            return
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"Object store initialization failed ({exc.code}): {detail}") from exc


if __name__ == "__main__":
    put()
    print(f"Object store bucket {BUCKET} is ready")
