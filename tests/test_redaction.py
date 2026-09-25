from siro.redaction import redact_mapping


def test_sensitive_names_are_redacted() -> None:
    result = redact_mapping(
        {
            "provider": "example",
            "api_key": "sample-value",  # pragma: allowlist secret
            "access-token": "sample-value",  # pragma: allowlist secret
            "password": "sample-value",  # pragma: allowlist secret
        }
    )

    assert result == {
        "provider": "example",
        "api_key": "[REDACTED]",
        "access-token": "[REDACTED]",
        "password": "[REDACTED]",
    }
