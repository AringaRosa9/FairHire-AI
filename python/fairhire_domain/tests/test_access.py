from fairhire_domain.access import Permission, Role, has_permission


def test_auditor_is_read_only_but_can_inspect_audit_log() -> None:
    assert has_permission(Role.AUDITOR, Permission.AUDIT_LOG_READ)
    assert not has_permission(Role.AUDITOR, Permission.SYSTEM_WRITE)
    assert not has_permission(Role.AUDITOR, Permission.APPROVAL_WRITE)


def test_only_explicit_roles_can_read_sensitive_attributes() -> None:
    assert has_permission(Role.RESPONSIBLE_AI, Permission.SENSITIVE_ATTRIBUTE_READ)
    assert has_permission(Role.LEGAL_REVIEWER, Permission.SENSITIVE_ATTRIBUTE_READ)
    assert not has_permission(Role.HR_REVIEWER, Permission.SENSITIVE_ATTRIBUTE_READ)
    assert not has_permission(Role.MODEL_DEVELOPER, Permission.SENSITIVE_ATTRIBUTE_READ)
