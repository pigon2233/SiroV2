"""Command-line entry point for SIRO development and diagnostics."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from siro import __version__
from siro.config import SiroSettings, load_settings
from siro.doctor import checks_as_dicts, collect_checks


async def _run_demo(arguments: argparse.Namespace) -> int:
    from siro.adapters.models.mock import OfflineDemoModel
    from siro.core.companion import CompanionCore
    from siro.core.conversation import ConversationEngine
    from siro.core.identity import (
        IdentityService,
        ImmutableCore,
        OwnerAuthorization,
    )
    from siro.core.memory import MemoryService
    from siro.persistence.conversation import SQLiteConversationRepository
    from siro.persistence.memory import SQLiteMemoryRepository
    from siro.persistence.sqlite import SQLiteStore
    from siro.persistence.state import SQLiteIdentityRepository

    store = SQLiteStore(Path(arguments.data) / "siro.db")
    await store.initialize()
    identities = SQLiteIdentityRepository(store)
    identity_service = IdentityService(identities)
    core = ImmutableCore(
        name=arguments.name,
        baseline_identity=arguments.persona,
        core_values=("誠實", "尊重來源"),
        creator_relationship="由本機 owner 建立的持續夥伴",
    )
    existing = await identities.get("siro")
    if existing is None:
        await identity_service.create("siro", core, now=datetime.now(UTC))
    elif existing.core != core and arguments.edit_persona:
        await identity_service.update_core(
            "siro",
            core,
            authorization=OwnerAuthorization.OWNER_EDIT,
            now=datetime.now(UTC),
            source_ids=("cli-owner-edit",),
        )
    conversation = ConversationEngine(OfflineDemoModel(), SQLiteConversationRepository(store))
    companion = CompanionCore(
        identities, MemoryService(SQLiteMemoryRepository(store)), conversation
    )

    async def answer(text: str) -> None:
        result = await companion.respond("cli", "siro", text)
        print(f"{core.name}: {result.text}")

    if arguments.once is not None:
        await answer(arguments.once)
        return 0
    print("SIRO offline demo: 輸入 /quit 結束。")
    while True:
        try:
            text = input("你: ").strip()
        except EOFError:
            break
        if text == "/quit":
            break
        if text:
            await answer(text)
    return 0


def _demo(arguments: argparse.Namespace) -> int:
    return asyncio.run(_run_demo(arguments))


def _doctor(arguments: argparse.Namespace) -> int:
    checks = collect_checks()
    payload = {
        "siro_version": __version__,
        "profile": "minimal",
        "checks": checks_as_dicts(checks),
    }
    if arguments.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"SIRO {__version__} doctor (minimal profile)")
        for check in checks:
            print(f"[{check.state.upper():11}] {check.name}: {check.detail} ({check.required_for})")
    minimal_ok = all(
        check.state == "available" for check in checks if check.required_for == "minimal"
    )
    return 0 if minimal_ok else 1


def _config_schema(_arguments: argparse.Namespace) -> int:
    print(json.dumps(SiroSettings.model_json_schema(), ensure_ascii=False, indent=2))
    return 0


def _validate_config(arguments: argparse.Namespace) -> int:
    settings = load_settings(Path(arguments.path))
    print(settings.model_dump_json(indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser without performing host checks."""

    parser = argparse.ArgumentParser(prog="siro", description="SIRO development CLI")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="inspect local capabilities")
    doctor_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    doctor_parser.set_defaults(handler=_doctor)

    schema_parser = subparsers.add_parser("config-schema", help="print settings JSON schema")
    schema_parser.set_defaults(handler=_config_schema)

    validate_parser = subparsers.add_parser("validate-config", help="validate a JSON config")
    validate_parser.add_argument("path", help="path to a JSON configuration")
    validate_parser.set_defaults(handler=_validate_config)

    demo_parser = subparsers.add_parser("demo", help="run the persistent offline text demo")
    demo_parser.add_argument("--data", default=".siro-demo", help="persistent data directory")
    demo_parser.add_argument("--name", default="SIRO", help="companion display name")
    demo_parser.add_argument("--persona", default="一位誠實、溫暖且會標明記憶來源的數位夥伴")
    demo_parser.add_argument(
        "--edit-persona",
        action="store_true",
        help="apply --name/--persona to an existing identity as the owner",
    )
    demo_parser.add_argument("--once", help="answer one message and exit")
    demo_parser.set_defaults(handler=_demo)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the SIRO CLI."""

    parser = build_parser()
    arguments = parser.parse_args(argv)
    return int(arguments.handler(arguments))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
