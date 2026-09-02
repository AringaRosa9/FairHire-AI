FROM python:3.12.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /workspace
COPY python/fairhire_domain python/fairhire_domain
COPY apps/api apps/api
RUN pip install --no-cache-dir ./python/fairhire_domain './apps/api[test]'
WORKDIR /workspace/apps/api
EXPOSE 8000
CMD ["uvicorn", "fairhire_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
