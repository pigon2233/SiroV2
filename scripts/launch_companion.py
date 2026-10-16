"""Start the configured companion, never silently substitute a deterministic demo."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from siro.core.releases import ReleaseLaunchError, ReleaseManager, VerifiedRelease
from siro.persistence.sqlite import load_migrations

_SIGNED_BOOTSTRAP = """import sys
from pathlib import Path
directory, version, digest, schema = sys.argv[1:5]
sys.path.insert(0, str(Path(directory) / 'src'))
from siro.core.releases import VerifiedRelease
from siro.services.presentation.gateway import main
main(verified_release=VerifiedRelease(version, digest, Path(directory), int(schema)))
"""


def _selected_release(root: Path) -> VerifiedRelease | None:
    selected = os.environ.get("SIRO_RELEASE_ROOT")
    if selected is None:
        return None
    key = os.environ.get("SIRO_RELEASE_SIGNING_KEY")
    if not selected or not key:
        raise SystemExit("SIRO release launch refused: missing_release_configuration")
    data = Path(os.environ.get("SIRO_DATA_DIR", ".siro-data"))
    if not data.is_absolute():
        data = root / data
    manager = ReleaseManager(
        Path(selected),
        key.encode(),
        current_schema=len(load_migrations()),
        database=data / "siro.db",
    )
    try:
        return manager.resolve_launch_target()
    except ReleaseLaunchError as error:
        raise SystemExit(str(error)) from None


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    selected = _selected_release(root)
    settings = root / ".env.local"
    allowed = {
        "SIRO_OPENAI_BASE_URL",
        "SIRO_OPENAI_MODEL",
        "SIRO_OPENAI_API_KEY",
        "SIRO_OLLAMA_MODEL",
    }
    if settings.is_file():
        for line in settings.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.removeprefix("export ").split("=", 1)
            if key.strip() in allowed:
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    if not (
        os.environ.get("SIRO_OLLAMA_MODEL")
        or (os.environ.get("SIRO_OPENAI_MODEL") and os.environ.get("SIRO_OPENAI_API_KEY"))
    ):
        raise SystemExit(
            "尚未設定對話模型。請設定 .env.local 的模型連線。正式入口不使用固定回覆示範。"
        )
    if os.environ.get("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "1") == "1" and not (
        not os.environ.get("SIRO_OLLAMA_MODEL")
        and os.environ.get("SIRO_OPENAI_MODEL") == "openai/gpt-oss-20b"
        and "api.groq.com" in os.environ.get("SIRO_OPENAI_BASE_URL", "https://api.groq.com/openai")
    ):
        raise SystemExit(
            "此模型尚無已驗證的 token 預算設定。請使用已支援的 Groq GPT-OSS20b。"
            "或明確設定 SIRO_CONTEXT_TOKEN_BUDGET_ENABLED=0 使用既有 byte 預算。"
        )
    os.environ["SIRO_RUNTIME_PROFILE"] = "candidate"
    for key in (
        "SIRO_WORKSPACE_ENABLED",
        "SIRO_MEMORY_ORGANIZATION_ENABLED",
        "SIRO_CONTEXT_SUMMARY_ENABLED",
        "SIRO_RATE_LIMIT_RECOVERY_ENABLED",
    ):
        os.environ.setdefault(key, "1")
    binary = root / "target/debug/siro-runtime"
    os.environ.setdefault("SIRO_RUNTIME_BINARY", str(binary))
    if not Path(os.environ["SIRO_RUNTIME_BINARY"]).is_file():
        if selected is not None:
            raise SystemExit("SIRO release launch refused: runtime_asset_missing")
        subprocess.run(["cargo", "build", "--locked", "-p", "siro-runtime"], check=True)
    demo = root / "models/live2d-sdk-5-r.5/CubismSdkForWeb-5-r.5/Samples/TypeScript/Demo"
    if not os.environ.get("SIRO_LIVE2D_DIST") and (demo / "src/main.ts").is_file():
        if selected is not None:
            raise SystemExit("SIRO release launch refused: renderer_asset_missing")
        subprocess.run(
            [sys.executable, str(root / "scripts/repair_companion_renderer.py"), str(demo)],
            check=True,
        )
        os.environ["SIRO_LIVE2D_DIST"] = str(demo / "dist")
    renderer = os.environ.get("SIRO_LIVE2D_DIST")
    if not renderer or not (Path(renderer) / "index.html").is_file():
        raise SystemExit("找不到已準備的 Live2D 角色。請先準備本機角色或指定 SIRO_LIVE2D_DIST。")
    if (
        os.environ.get("SIRO_OPENAI_MODEL") == "openai/gpt-oss-20b"
        and os.environ.get("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "1") == "1"
        and selected is None
    ):
        directory = os.environ.get(
            "SIRO_CONTEXT_TOKENIZER_DIR", str(root / ".siro-data/tokenizers/gpt-oss-20b")
        )
        subprocess.run(
            [
                sys.executable,
                str(root / "scripts/setup_context_tokenizer.py"),
                "--directory",
                directory,
            ],
            check=True,
        )
    if selected is not None:
        environment = dict(os.environ)
        environment.pop("SIRO_RELEASE_SIGNING_KEY", None)
        environment["SIRO_DATA_DIR"] = str(
            Path(os.environ.get("SIRO_DATA_DIR", ".siro-data")).resolve()
        )
        os.execve(
            sys.executable,
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                _SIGNED_BOOTSTRAP,
                str(selected.directory),
                selected.version,
                selected.source_sha256,
                str(selected.schema_version),
            ],
            environment,
        )
        return
    os.execv(
        sys.executable,
        [sys.executable, "-c", "from siro.services.presentation.gateway import main; main()"],
    )


if __name__ == "__main__":
    main()
