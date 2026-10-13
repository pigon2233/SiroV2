from __future__ import annotations

from pathlib import Path

import pytest

from siro.services.tools.execution import ExecutionContext
from siro.services.tools.workspace import WorkspaceRuntime


@pytest.mark.asyncio
async def test_real_workspace_scope_authorization_lifecycle(tmp_path: Path) -> None:
    binary = Path(__file__).parents[2] / "target/debug/siro-runtime"
    assert binary.exists(), "build siro-runtime before this integration gate"
    root = tmp_path / "共享資料夾"
    root.mkdir()
    (root / "筆記.txt").write_text("hello SIRO", encoding="utf-8")
    outside = tmp_path / "private.txt"
    outside.write_text("private")
    (root / "escape").symlink_to(outside)
    service = WorkspaceRuntime(root, binary)
    await service.start()
    context = ExecutionContext("r", "s", "e", proposal_id="p", authorized=True)
    try:
        assert service.available
        assert (await service.execute("filesystem.read", {"path": "筆記.txt"}, context)) == {
            "text": "hello SIRO"
        }
        listing = await service.execute("filesystem.list", {"path": "."}, context)
        assert "筆記.txt" in str(listing)
        for path in ("../private.txt", "escape", str(outside)):
            with pytest.raises(PermissionError):
                await service.execute("filesystem.read", {"path": path}, context)
        with pytest.raises(PermissionError):
            await service.execute(
                "filesystem.read", {"path": "筆記.txt"}, ExecutionContext("r", "s", "e")
            )
        context.cancellation.cancel()
        with pytest.raises(Exception, match="cancelled"):
            await service.execute("filesystem.read", {"path": "筆記.txt"}, context)
    finally:
        await service.close()
    assert not service.available
    assert service._process is None


@pytest.mark.asyncio
async def test_missing_runtime_is_unavailable_not_chat_startup_failure(tmp_path: Path) -> None:
    service = WorkspaceRuntime(tmp_path / "shared", tmp_path / "missing")
    await service.start()
    assert not service.available
    await service.close()
