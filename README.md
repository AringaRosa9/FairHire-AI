# FairHire AI

Recruitment AI assurance and evidence workspace. This repository contains the Week 1–2 engineering foundation described in `DEVELOPMENT_PLAN.md`.

## What is included

- Next.js workspace with responsive Welcome, Portfolio and Systems flows.
- Shared semantic design tokens and accessible status/severity primitives.
- FastAPI health/session/AI systems foundation with organization context and RBAC checks.
- PostgreSQL schema, Alembic migration and row-level security policies.
- Celery worker plus Redis and S3-compatible MinIO local services.
- Versioned binary-classification schema, OpenAPI contract and generated TypeScript types.
- CI, unit, contract and Playwright smoke-test baselines.
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

## Verify

```bash
npm run lint
npm run typecheck
npm test
npm run build
docker compose run --rm api pytest
npm run test:e2e
```

Generate the checked-in API contract and TypeScript client after API changes:

```bash
make contract
```
