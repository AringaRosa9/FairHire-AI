# Threat model v1

Method: STRIDE-inspired review of the Week 1–2 architecture. Severity uses impact and exploitability, not regulatory certainty.

## Assets and boundaries

Critical assets are candidate pseudonymous data, protected attributes, model outputs, audit configuration, metric evidence, approval identity, reports, signing/hash material and tenant routing context. The attribute vault, main tenant data, aggregate evidence and audit ledger are separate security domains.

| ID | Threat | Severity | Engineering control | Verification |
|---|---|---:|---|---|
| T01 | Cross-tenant IDOR through path/query ID | Critical | API organization predicate + PostgreSQL forced RLS + scoped object prefixes | Cross-tenant API/RLS tests |
| T02 | Forged organization header | Critical | Header selects context only; membership is revalidated against authenticated OIDC subject | Session integration tests |
| T03 | Development auth enabled in production | Critical | Settings validation refuses production startup | Configuration unit test |
| T04 | Malicious pickle/joblib executes code | Critical | Formats rejected at ingestion and worker entry; JSON-only tasks | Worker unit/security test |
| T05 | Path traversal or cross-tenant object key | High | Server-generated keys, normalized allow-list, prefix validation, short-lived signed URLs | Fuzz prefix tests |
| T06 | Oversized/compressed/MIME-confused upload | High | Direct upload size limits, magic-byte detection, decompression ratio limit, malware hook | Upload integration corpus |
| T07 | CSV formula injection in exports | High | Prefix dangerous formula cells; use typed CSV writer; warn on spreadsheet import | Golden export tests |
| T08 | Queue starvation / noisy tenant | High | Per-tenant quotas, prefetch 1, hard/soft timeouts, worker isolation | Load and cancellation tests |
| T09 | Threshold changed to manufacture Pass | High | Versioned test strategy, approver, audit event, recalculation/new run only | Workflow/ledger tests |
| T10 | Audit evidence altered or deleted | High | Append-only events, hash chain, immutable report version and content hash | Ledger verification tests |
| T11 | Small-cell re-identification | High | 20-row suppression floor, 200-row conclusion floor, restricted raw export | Report privacy tests |
| T12 | Sensitive attribute leaks into evaluated features | High | `vault_only` contract, separated storage key/domain, mapping validation | Contract and ingestion tests |
| T13 | Sensitive data in logs/traces | High | Identifier allow-list, structured redaction, no rows in error telemetry | Logging review and DLP scan |
| T14 | OIDC token replay/wrong audience | High | Issuer/audience/signature/expiry checks, short token life, TLS | Auth negative tests |
| T15 | Prompt injection in evidence document | High | Read-only assistant tools, tenant filter before retrieval, citations, no workflow write capability | Adversarial assistant suite |
| T16 | Dependency or image compromise | Medium | Lockfiles, digest-pinned production images, SBOM and vulnerability scan | CI supply-chain gate |
| T17 | Backup outlives deletion request | High | Dataset-level expiry propagated to backups and restore tombstones | Restore/delete exercise |

## Residual items before pilot

Key-management design, managed-service network policy, malware scanner choice, signed-URL envelope, production OIDC provider, WAF/egress policy and incident runbook are intentionally open. None may be represented as implemented controls until deployed and tested.

