# API conventions

- Base path is `/v1`; OpenAPI is `/v1/openapi.json` and checked into `contracts/openapi.json`.
- The OIDC subject establishes identity. `X-Organization-ID` selects one of that subject's active memberships; it never grants access by itself.
- All writes require `Idempotency-Key` (maximum 128 characters). The database uniqueness boundary is organization + key.
- Long-running operations return HTTP 202 with `job_id`, state, submission time and poll URL. Initial states are `queued`, `running`, `succeeded`, `failed`, `cancelling`, `cancelled`.
- Errors use `application/problem+json` with `type`, `title`, `status`, `detail`, `instance` and a stable optional `code`.
- Pagination uses `page`, `page_size` and `total`; page size is capped at 100 in the foundation API.
- Datetimes are RFC 3339 UTC. IDs are opaque strings. Money is not represented as binary float.
- Upload initialization will return a short-lived signed URL constrained by object key, MIME, size and checksum. The API does not proxy file bytes.
- Historical assessment/config/report/approval resources do not support destructive updates; new versions are created.

The generated TypeScript client wraps the checked-in OpenAPI schema and supplies organization/auth headers explicitly. CI fails when the API-generated contract differs from the checked-in artifact.

