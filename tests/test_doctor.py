from siro.doctor import CheckResult, checks_as_dicts, collect_checks


def test_doctor_never_exposes_environment_values(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("VERY_SECRET_TOKEN", "do-not-print")

    serialized = str(checks_as_dicts(collect_checks(dict())))

    assert "do-not-print" not in serialized
    assert "VERY_SECRET_TOKEN" not in serialized


def test_check_serialization_is_stable() -> None:
    check = CheckResult("python", "available", "3.x", "minimal")

    assert checks_as_dicts([check]) == [
        {
            "name": "python",
            "state": "available",
            "detail": "3.x",
            "required_for": "minimal",
        }
    ]
