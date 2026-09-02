# Versioned open decisions

Unresolved items are evidence gaps, not approvals. They do not block the engineering foundation but must be assigned before the end of the second product sprint.

| ID | Decision | Proposed baseline | Accountable owner | Due | Product behavior until resolved |
|---|---|---|---|---|---|
| D-001 | Germany labor-law extension wording and controls | EU core + Germany extension package, separately versioned | Legal / DPO | 2026-09-11 | `Needs legal confirmation`; never Approved from the rule suggestion alone |
| D-002 | Lawful basis and necessity test for protected attributes | Required reference before upload completion | DPO | 2026-09-11 | Vault upload blocked; Evidence Gap shown |
| D-003 | Vault roles and default protected-attribute retention | RAI, Legal/DPO and read-only Auditor; 30 days | DPO + Security | 2026-09-11 | Use restrictive code baseline; no export permission |
| D-004 | Release gate and residual-risk acceptor | Critical unresolved blocks release; RAI + Legal dual approval for exception | Responsible AI lead | 2026-09-11 | Blocked remains Blocked; no default exception |
| D-005 | Official assistant sources and freshness owner | EU official sources plus approved organization policy only | Legal Operations | 2026-09-18 | Assistant unavailable for legal conclusions |
| D-006 | Pilot file volume and identity provider | 1M rows, 50 features; OIDC provider TBD | Pilot owner + DevOps | 2026-09-18 | Synthetic fixtures and local dev identity only |
| D-007 | Retention period for aggregate evidence and ledger | 7-year proposal | DPO + Records Management | 2026-09-11 | Mark as proposed; do not promise deletion/retention guarantee |
| D-008 | Statistical test-strategy approvers | Responsible AI + independent reviewer | Model Risk | 2026-09-11 | Threshold source remains unapproved and cannot yield Pass |

