from siro.core.authorization import (
    AuthorizationRequest,
    AuthorizationService,
    PermissionDecision,
    PermissionPolicy,
)


def request(arguments: dict[str, object] | None = None) -> AuthorizationRequest:
    return AuthorizationRequest(
        "action-1",
        "owner",
        "filesystem.read",
        arguments or {"path": "/tmp/safe"},
        {"path": ("/tmp/safe",)},
    )


def test_policy_defaults_deny_and_allow_issues_one_use_grant() -> None:
    denied = AuthorizationService(PermissionPolicy({}), b"secret").authorize(request())
    assert denied.decision is PermissionDecision.DENY
    assert denied.grant is None

    service = AuthorizationService(
        PermissionPolicy({"filesystem.read": PermissionDecision.ALLOW}), b"secret"
    )
    allowed = service.authorize(request())
    assert allowed.decision is PermissionDecision.ALLOW
    assert allowed.grant is not None


def test_ask_binds_approval_to_action_and_exact_arguments() -> None:
    service = AuthorizationService(
        PermissionPolicy({"filesystem.read": PermissionDecision.ASK}), b"secret"
    )
    pending = service.authorize(request())
    assert pending.decision is PermissionDecision.ASK
    changed = service.resolve("action-1", approved=True, arguments={"path": "/etc/passwd"})
    assert changed.decision is PermissionDecision.DENY
    assert changed.reason == "arguments_changed"

    service.authorize(request())
    approved = service.resolve("action-1", approved=True, arguments={"path": "/tmp/safe"})
    assert approved.decision is PermissionDecision.ALLOW
    assert approved.grant is not None
    replay = service.resolve("action-1", approved=True, arguments={"path": "/tmp/safe"})
    assert replay.decision is PermissionDecision.DENY
