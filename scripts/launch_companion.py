"""Start the configured companion, never silently substitute a deterministic demo."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
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
    ):
        os.environ.setdefault(key, "1")
    binary = root / "target/debug/siro-runtime"
    os.environ.setdefault("SIRO_RUNTIME_BINARY", str(binary))
    if not Path(os.environ["SIRO_RUNTIME_BINARY"]).is_file():
        subprocess.run(["cargo", "build", "--locked", "-p", "siro-runtime"], check=True)
    demo = root / "models/live2d-sdk-5-r.5/CubismSdkForWeb-5-r.5/Samples/TypeScript/Demo"
    if not os.environ.get("SIRO_LIVE2D_DIST") and (demo / "src/main.ts").is_file():
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
    os.execv(
        sys.executable,
        [sys.executable, "-c", "from siro.services.presentation.gateway import main; main()"],
    )


if __name__ == "__main__":
    main()
