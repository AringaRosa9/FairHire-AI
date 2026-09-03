from celery import Celery  # type: ignore[import-untyped]

from .config import Settings


def dispatch_job(
    settings: Settings, *, task_name: str, job_id: str, kwargs: dict[str, object]
) -> str | None:
    """Publish through Celery while preserving the database job as the source of truth."""
    if not settings.job_dispatch_enabled:
        return None
    app = Celery("fairhire_api_dispatch", broker=settings.redis_url, backend=settings.redis_url)
    result = app.send_task(task_name, kwargs={**kwargs, "job_id": job_id}, task_id=job_id)
    return str(result.id)


def revoke_job(settings: Settings, *, job_id: str) -> bool:
    """Request cooperative cancellation without terminating a worker process."""
    if not settings.job_dispatch_enabled:
        return False
    app = Celery("fairhire_api_dispatch", broker=settings.redis_url, backend=settings.redis_url)
    app.control.revoke(job_id, terminate=False)
    return True
