# FairHire AI

Recruitment AI assurance and evidence workspace. This repository contains the engineering foundation and first-registration milestone through Week 5 described in `DEVELOPMENT_PLAN.md`.

## What is included

- Next.js workspace with responsive Welcome, Portfolio, Systems and five-step first-audit flows.
- Shared semantic design tokens and accessible status/severity primitives.
- FastAPI registry, applicability assessment, model-version, dataset, audit-run, job and append-only ledger APIs with idempotent writes.
- PostgreSQL schema, Alembic migrations and forced row-level security policies across tenant data.
- Direct CSV/Parquet/JSONL uploads to S3-compatible MinIO, checksum-bound URLs, scanner attestation, schema confirmation and field mapping.
- Celery worker plus Redis-backed job dispatch, status, retry and cancellation state.
- Locally persisted and server-synced onboarding drafts with validation and recovery.
- Versioned binary-classification schema, OpenAPI contract and generated TypeScript types.
- Unit, contract, PostgreSQL RLS, API-to-MinIO integration and Playwright regression tests.
- ERD, RBAC, threat model, retention matrix and responsive page specifications.

## Start locally

Requirements: Docker Desktop, Node.js 22+ and npm 11+.

```bash
cp .env.example .env
npm install
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000). The API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs), and MinIO is at [http://localhost:9101](http://localhost:9101).

The local infrastructure uses host ports `55432` (PostgreSQL), `56379` (Redis), `9100` (S3 API) and `9101` (MinIO console) to avoid common workstation conflicts. Containers continue to use their standard internal ports.

Development authentication is intentionally explicit: requests use `X-Dev-User` and `X-Organization-ID` only while `DEV_AUTH_ENABLED=true`. Production refuses this mode. Database migrations use the owner account from `MIGRATION_DATABASE_URL`; the API uses the non-superuser `fairhire_app` account so PostgreSQL forced RLS remains effective.

Uploads never pass through the API process. The browser uploads directly with a short-lived, checksum-bound signed URL. Upload completion accepts only a clean malware-scan result; production additionally requires an HMAC scanner attestation using `SCANNER_ATTESTATION_SECRET`. The `development-scanner:` reference is intentionally limited to development and test environments.

## Verify

```bash
npm run lint
npm run typecheck
npm test
npm run build
docker compose run --rm api pytest
npm run test:e2e
```

With the Docker Compose services running, the opt-in first-registration smoke test exercises the complete API → signed upload → field mapping → Audit Run chain:

```bash
FAIRHIRE_API_URL=http://localhost:8000/v1 \
.venv/bin/python tests/integration/verify_week3_5.py
```

Generate the checked-in API contract and TypeScript client after API changes:

```bash
make contract
```
