FROM python:3.12.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /workspace
COPY python/fairhire_domain python/fairhire_domain
COPY apps/worker apps/worker
RUN pip install --no-cache-dir ./python/fairhire_domain ./apps/worker
WORKDIR /workspace/apps/worker
CMD ["celery", "-A", "fairhire_worker.app", "worker", "--loglevel=INFO"]
