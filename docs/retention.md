# Data retention matrix

These are proposed EU SaaS defaults. Customer policy may shorten them. Legal holds require a named approver, scope, reason and expiry; they never silently apply to unrelated raw candidate data.

| Data class | Default | Storage boundary | Expiry behavior | Access |
|---|---:|---|---|---|
| Raw candidate rows/pseudonymous IDs | 30 days after audit completion | Encrypted tenant dataset domain | Delete object/version; propagate tombstone to backup catalogue | Responsible AI, model developer, authorized data reviewer |
| Protected attributes | 30 days, separately configurable | Audit Attribute Vault, separate key | Cryptographic/key-scoped deletion plus object deletion | Vault permission only |
| Uploaded model predictions | 90 days | Tenant audit-run path | Delete raw file; preserve fingerprint and aggregate provenance | Audit operators |
| Inferred schema/field mappings | 2 years | PostgreSQL tenant tables | Delete when related evidence retention ends | Audit/review roles |
| Aggregate metric results | 7 years proposal | Evidence domain | Preserve immutable version; restrict small cells | Report readers by role |
| Findings, controls, approvals | 7 years proposal | Governance domain | Append superseding state; no in-place history deletion | Governance and audit roles |
| Approved reports/evidence package | 7 years proposal | Immutable evidence domain | Expire by policy version unless legal hold | Report readers/export permission |
| Draft reports | 180 days after superseded | Evidence domain | Delete draft artifact; retain audit event | Author/reviewer |
| Application audit events | 7 years proposal | Append-only ledger | Partition expiry only through controlled retention job | Admin, Responsible AI, legal, auditor |
| Assistant prompts/answers | 90 days | Separate assistant domain | Delete text; keep minimal safety/accounting record | Requester and authorized reviewers |
| API/security logs | 30 days hot + 335 days archive | Security logging account | Automated lifecycle and redaction | Security operations |
| Backups | 35 days rolling | EU backup account/key | Expire automatically; deletion tombstones re-applied on restore | Restricted operations |

Raw identifiers and protected attributes use different storage prefixes, encryption keys and IAM roles from aggregate evidence. Signed URLs are short-lived and never cached in application logs. Retention changes create a versioned organization policy and audit event.

