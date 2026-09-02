from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    RESPONSIBLE_AI = "responsible_ai"
    HR_REVIEWER = "hr_reviewer"
    LEGAL_REVIEWER = "legal_reviewer"
    MODEL_DEVELOPER = "model_developer"
    AUDITOR = "auditor"
    PROCUREMENT = "procurement"


class Permission(StrEnum):
    SYSTEM_READ = "system:read"
    SYSTEM_WRITE = "system:write"
    DATASET_READ = "dataset:read"
    DATASET_WRITE = "dataset:write"
    SENSITIVE_ATTRIBUTE_READ = "sensitive_attribute:read"
    AUDIT_RUN = "audit:run"
    FINDING_WRITE = "finding:write"
    APPROVAL_WRITE = "approval:write"
    RISK_ACCEPT = "risk:accept"
    REPORT_READ = "report:read"
    REPORT_APPROVE = "report:approve"
    AUDIT_LOG_READ = "audit_log:read"
    ACCESS_ADMIN = "access:admin"
    POLICY_ADMIN = "policy:admin"


READ_BASELINE = {
    Permission.SYSTEM_READ,
    Permission.REPORT_READ,
}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.RESPONSIBLE_AI: frozenset(
        READ_BASELINE
        | {
            Permission.SYSTEM_WRITE,
            Permission.DATASET_READ,
            Permission.DATASET_WRITE,
            Permission.SENSITIVE_ATTRIBUTE_READ,
            Permission.AUDIT_RUN,
            Permission.FINDING_WRITE,
            Permission.APPROVAL_WRITE,
            Permission.RISK_ACCEPT,
            Permission.REPORT_APPROVE,
            Permission.AUDIT_LOG_READ,
            Permission.POLICY_ADMIN,
        }
    ),
    Role.HR_REVIEWER: frozenset(
        READ_BASELINE
        | {
            Permission.DATASET_READ,
            Permission.FINDING_WRITE,
            Permission.APPROVAL_WRITE,
        }
    ),
    Role.LEGAL_REVIEWER: frozenset(
        READ_BASELINE
        | {
            Permission.SENSITIVE_ATTRIBUTE_READ,
            Permission.FINDING_WRITE,
            Permission.APPROVAL_WRITE,
            Permission.RISK_ACCEPT,
            Permission.REPORT_APPROVE,
            Permission.AUDIT_LOG_READ,
        }
    ),
    Role.MODEL_DEVELOPER: frozenset(
        READ_BASELINE
        | {
            Permission.SYSTEM_WRITE,
            Permission.DATASET_READ,
            Permission.DATASET_WRITE,
            Permission.AUDIT_RUN,
            Permission.FINDING_WRITE,
        }
    ),
    Role.AUDITOR: frozenset(
        READ_BASELINE
        | {
            Permission.DATASET_READ,
            Permission.SENSITIVE_ATTRIBUTE_READ,
            Permission.AUDIT_LOG_READ,
        }
    ),
    Role.PROCUREMENT: frozenset(READ_BASELINE | {Permission.FINDING_WRITE}),
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]
