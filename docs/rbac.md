# RBAC permission matrix

Roles are organization-scoped memberships. A person may have different roles in different organizations. All access additionally requires the row's `organization_id` to match the active organization context.

| Permission | Admin | Responsible AI | HR reviewer | Legal/DPO | Model developer | Auditor | Procurement |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Read system registry | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Edit system registry | ✓ | ✓ | — | — | ✓ | — | — |
| Read ordinary datasets | ✓ | ✓ | ✓ | — | ✓ | ✓ | — |
| Upload/map datasets | ✓ | ✓ | — | — | ✓ | — | — |
| Read Audit Attribute Vault | ✓ | ✓ | — | ✓ | — | ✓ | — |
| Run/retest audit | ✓ | ✓ | — | — | ✓ | — | — |
| Edit finding/remediation | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ |
| Submit approval | ✓ | ✓ | ✓ | ✓ | — | — | — |
| Accept residual risk | ✓ | ✓ | — | ✓ | — | — | — |
| Read reports | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Approve/freeze report | ✓ | ✓ | — | ✓ | — | — | — |
| Verify audit log | ✓ | ✓ | — | ✓ | — | ✓ | — |
| Administer access | ✓ | — | — | — | — | — | — |
| Administer policy/thresholds | ✓ | ✓ | — | — | — | — | — |

Controls:

- Vault access is an additional permission and does not imply export permission.
- A user cannot approve their own risk acceptance or final report; separation-of-duties checks are enforced by workflow policy in Sprint 3.
- Organization switching requires a membership lookup after tenant context is set. IDs from request paths never establish tenant authority.
- Access changes, vault reads, report exports, approvals and policy changes are mandatory audit events.
- Quarterly access review and immediate deprovisioning are operational requirements; SSO/MFA remain identity-provider controls.

