# Governance loop

The Week 10–11 implementation turns audit evidence into an accountable release decision. All governance records are organization-scoped in the API and protected by forced PostgreSQL row-level security.

## Finding lifecycle

```text
Open → Triaged → Mitigating → Ready for retest → Resolved
          └──────────────→ Accepted (time-limited)
Accepted --expiry--> Open
Resolved --regression/manual decision--> Open
```

- A finding binds its AI system, optional audit run and source metric, evidence references, control references, affected groups, severity, confidence, owner and due date.
- State changes require a reason and create a named `finding.status_changed` ledger event containing before/after state.
- Risk acceptance requires residual risk, a reason, an approving identity and a future expiry. Expired acceptances reopen on governance access and create `finding.acceptance_expired`.
- A remediation task cannot be completed without at least one evidence reference.
- A retest must use a successful audit run for the same AI system. Only a finding in `ready_for_retest` can receive a retest outcome.

## Approval chain and Release Gate

Each chain is append-versioned and always uses this order:

1. Responsible AI
2. HR
3. Legal / DPO

The API enforces both role and sequence. An earlier stage must be approved before a later stage can approve. A rejected or expired approval prevents release.

The Release Gate has three outcomes:

- `blocked`: an unresolved Critical finding lacks a valid exception, or a reviewer rejected the release.
- `review_required`: no blocker exists, but the latest approval chain is incomplete.
- `approved`: all three stages in the latest chain are valid and no Critical blocker exists.

The final Legal/DPO approval returns `409` while a Critical blocker exists. Gate recalculation synchronizes `AI_System.release_status`; any change creates `release_gate.status_changed` with before/after values.

## API surface

- `POST/GET /v1/findings`, `GET /v1/findings/{id}`
- `POST /v1/findings/{id}/transition`, `/accept`, `/tasks`, `/retests`
- `GET /v1/remediation-tasks`, `POST /v1/remediation-tasks/{id}/status`
- `POST /v1/ai-systems/{id}/approval-chain`
- `GET /v1/approvals`, `POST /v1/approvals/{id}/decision`
- `GET /v1/ai-systems/{id}/release-gate`

Every write requires an `Idempotency-Key`. Threshold provenance and the effective threshold snapshot are also captured when an audit run is queued.
