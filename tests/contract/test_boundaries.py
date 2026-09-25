from pathlib import Path

from siro.contracts.boundaries import find_core_import_violations


def test_current_core_has_no_adapter_dependencies() -> None:
    root = Path(__file__).parents[2] / "src" / "siro" / "core"

    assert find_core_import_violations(root) == []


def test_forbidden_core_import_is_reported(tmp_path: Path) -> None:
    core = tmp_path / "core"
    core.mkdir()
    (core / "bad.py").write_text("from siro.adapters.models import provider\n", encoding="utf-8")

    violations = find_core_import_violations(core)

    assert len(violations) == 1
    assert "forbidden import siro.adapters.models" in violations[0]
