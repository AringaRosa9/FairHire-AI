from __future__ import annotations

import socket
import threading
import time
from collections import defaultdict
from urllib.parse import urlparse
from urllib.request import urlopen

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import Settings

BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
_lock = threading.Lock()
_request_count: dict[tuple[str, str, int], int] = defaultdict(int)
_duration_count: dict[tuple[str, str], int] = defaultdict(int)
_duration_sum: dict[tuple[str, str], float] = defaultdict(float)
_duration_buckets: dict[tuple[str, str, float], int] = defaultdict(int)


def observe_request(request: Request, status_code: int, duration: float) -> None:
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    method = request.method
    with _lock:
        _request_count[(method, path, status_code)] += 1
        _duration_count[(method, path)] += 1
        _duration_sum[(method, path)] += duration
        for bucket in BUCKETS:
            if duration <= bucket:
                _duration_buckets[(method, path, bucket)] += 1


def prometheus_metrics() -> str:
    lines = [
        "# HELP fairhire_http_requests_total HTTP requests handled by the API.",
        "# TYPE fairhire_http_requests_total counter",
    ]
    with _lock:
        for (method, path, status_code), value in sorted(_request_count.items()):
            lines.append(
                f'fairhire_http_requests_total{{method="{method}",route="{path}",'
                f'status="{status_code}"}} {value}'
            )
        lines.extend(
            [
                "# HELP fairhire_http_request_duration_seconds API request latency.",
                "# TYPE fairhire_http_request_duration_seconds histogram",
            ]
        )
        for method, path in sorted(_duration_count):
            for bucket in BUCKETS:
                lines.append(
                    "fairhire_http_request_duration_seconds_bucket"
                    f'{{method="{method}",route="{path}",le="{bucket}"}} '
                    f"{_duration_buckets[(method, path, bucket)]}"
                )
            lines.append(
                "fairhire_http_request_duration_seconds_bucket"
                f'{{method="{method}",route="{path}",le="+Inf"}} '
                f"{_duration_count[(method, path)]}"
            )
            lines.append(
                "fairhire_http_request_duration_seconds_sum"
                f'{{method="{method}",route="{path}"}} '
                f"{_duration_sum[(method, path)]:.9f}"
            )
            lines.append(
                "fairhire_http_request_duration_seconds_count"
                f'{{method="{method}",route="{path}"}} '
                f"{_duration_count[(method, path)]}"
            )
    return "\n".join(lines) + "\n"


def _redis_ready(redis_url: str) -> bool:
    parsed = urlparse(redis_url)
    with socket.create_connection(
        (parsed.hostname or "localhost", parsed.port or 6379), timeout=2
    ) as connection:
        connection.sendall(b"*1\r\n$4\r\nPING\r\n")
        return connection.recv(16).startswith(b"+PONG")


def readiness(db: Session, settings: Settings) -> tuple[bool, dict[str, str]]:
    checks: dict[str, str] = {}
    started = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
    try:
        checks["redis"] = "ok" if _redis_ready(settings.redis_url) else "unavailable"
    except OSError:
        checks["redis"] = "unavailable"
    try:
        endpoint = settings.s3_endpoint.rstrip("/") + "/minio/health/ready"
        with urlopen(endpoint, timeout=2) as response:
            checks["object_store"] = "ok" if response.status == 200 else "unavailable"
    except (OSError, ValueError):
        checks["object_store"] = "unavailable"
    checks["check_duration_ms"] = str(round((time.perf_counter() - started) * 1000, 2))
    return all(value == "ok" for key, value in checks.items() if key != "check_duration_ms"), checks


def readiness_metrics(db: Session, settings: Settings) -> str:
    _, checks = readiness(db, settings)
    lines = [
        "# HELP fairhire_dependency_ready Whether a required API dependency is ready.",
        "# TYPE fairhire_dependency_ready gauge",
    ]
    for dependency in ("database", "redis", "object_store"):
        lines.append(
            f'fairhire_dependency_ready{{dependency="{dependency}"}} '
            f"{1 if checks.get(dependency) == 'ok' else 0}"
        )
    return "\n".join(lines) + "\n"
