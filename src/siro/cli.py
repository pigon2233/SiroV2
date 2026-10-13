"""Command-line entry point for SIRO development and diagnostics."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import stat
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType

from siro import __version__
from siro.config import SiroSettings, load_settings
from siro.core.releases import ReleaseManager
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
    return asyncio.run(
        _run_demo(arguments), loop_factory=getattr(arguments, "_data_loop_factory", None)
    )


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


def _verify_patch(arguments: argparse.Namespace) -> int:
    from pydantic import ValidationError

    from siro.core.evolution import PatchProposal, VerificationReport
    from siro.services.tools.patch_verification import verify_isolated_patch

    limit = 4 * 1024 * 1024
    try:
        descriptor = os.open(arguments.proposal, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
                raise ValueError("invalid proposal input")
            data = stream.read(limit + 1)
            if len(data) > limit:
                raise ValueError("proposal input too large")
        proposal = PatchProposal.model_validate_json(data)
    except (OSError, ValueError, ValidationError):
        print(json.dumps({"status": "rejected_input"}))
        return 2
    active: asyncio.Task[VerificationReport] | None = None
    interrupted = False

    def interrupt(_signum: int, _frame: FrameType | None) -> None:
        nonlocal interrupted
        interrupted = True
        if active is not None and not active.done():
            active.get_loop().call_soon_threadsafe(active.cancel)

    async def run() -> VerificationReport:
        nonlocal active
        active = asyncio.current_task()
        if interrupted:
            raise asyncio.CancelledError
        return await verify_isolated_patch(
            Path(arguments.project_root), proposal, profile=arguments.profile
        )

    previous = signal.getsignal(signal.SIGINT)
    try:
        # Repeated Ctrl-C cancels the same owner instead of aborting its cleanup.
        signal.signal(signal.SIGINT, interrupt)
        report = asyncio.run(run())
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    finally:
        signal.signal(signal.SIGINT, previous)
    if interrupted:
        return 130
    print(json.dumps(asdict(report), default=str, ensure_ascii=False))
    return 0 if report.status == "passed" else 1


def _release_manager(arguments: argparse.Namespace) -> ReleaseManager:
    from siro.persistence.sqlite import load_migrations

    key = os.environ.get(arguments.key_env)
    if not key:
        raise ValueError(f"required environment variable is missing: {arguments.key_env}")
    database = Path(arguments.database) if arguments.database else None
    return ReleaseManager(
        Path(arguments.release_root),
        key.encode(),
        current_schema=len(load_migrations()),
        database=database,
    )


def _release_stage(arguments: argparse.Namespace) -> int:
    from siro.core.releases import ReleaseManifest

    manager = _release_manager(arguments)
    manifest = ReleaseManifest.model_validate_json(
        Path(arguments.manifest).read_text(encoding="utf-8")
    )
    check = tuple(json.loads(arguments.healthcheck))
    if not check or not all(isinstance(item, str) for item in check):
        raise ValueError("healthcheck must be a JSON argv array of strings")
    result = manager.stage_and_activate(Path(arguments.bundle), manifest, check)
    print(json.dumps({"status": result.status, "active_version": result.active_version}))
    return 0 if result.status == "activated" else 1


def _release_rollback(arguments: argparse.Namespace) -> int:
    result = _release_manager(arguments).rollback()
    print(json.dumps({"status": result.status, "active_version": result.active_version}))
    return 0 if result.status == "rolled_back" else 1


async def _backup_data(arguments: argparse.Namespace) -> int:
    from siro.persistence.sqlite import SQLiteStore

    store = SQLiteStore(Path(arguments.data) / "siro.db")
    await store.initialize()
    if arguments.config:
        from siro.operations import create_backup_bundle

        await create_backup_bundle(
            store, Path(arguments.destination), config=Path(arguments.config)
        )
    else:
        await store.backup_to(Path(arguments.destination))
    print(json.dumps({"status": "backed_up", "destination": arguments.destination}))
    return 0


async def _restore_data(arguments: argparse.Namespace) -> int:
    from siro.persistence.sqlite import SQLiteStore

    store = SQLiteStore(Path(arguments.data) / "siro.db")
    if arguments.config:
        from siro.operations import restore_backup_bundle

        await restore_backup_bundle(store, Path(arguments.source), config=Path(arguments.config))
    else:
        await store.restore_from(Path(arguments.source))
    status = await store.integrity_check()
    if status != "ok":
        raise RuntimeError(f"restored database failed integrity check: {status}")
    print(json.dumps({"status": "restored", "data": arguments.data}))
    return 0


def _backup(arguments: argparse.Namespace) -> int:
    return asyncio.run(
        _backup_data(arguments), loop_factory=getattr(arguments, "_data_loop_factory", None)
    )


def _restore(arguments: argparse.Namespace) -> int:
    return asyncio.run(
        _restore_data(arguments), loop_factory=getattr(arguments, "_data_loop_factory", None)
    )


def _install(arguments: argparse.Namespace) -> int:
    from siro.operations import enable_user_service, install_user_service

    result = install_user_service(
        Path(arguments.project_root),
        unit_dir=Path(arguments.unit_dir).expanduser(),
        config_dir=Path(arguments.config_dir).expanduser(),
        data_dir=Path(arguments.data_dir).expanduser(),
        log_dir=Path(arguments.log_dir).expanduser(),
        port=arguments.port,
    )
    if arguments.enable:
        enable_user_service()
    print(
        json.dumps(
            {
                "status": "enabled" if arguments.enable else "installed",
                "unit": str(result.unit),
                "timer": str(result.timer),
                "config": str(result.config),
            }
        )
    )
    return 0


def _prune_logs(arguments: argparse.Namespace) -> int:
    from siro.operations import prune_logs

    removed = prune_logs(Path(arguments.directory), days=arguments.days)
    print(json.dumps({"status": "pruned", "removed": len(removed)}))
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

    patch_parser = subparsers.add_parser(
        "verify-patch", help="verify a candidate in the supported Linux isolation profile"
    )
    patch_parser.add_argument("proposal", help="bounded PatchProposal JSON file")
    patch_parser.add_argument("--project-root", required=True)
    patch_parser.add_argument(
        "--profile", choices=("python-unittest-single",), default="python-unittest-single"
    )
    patch_parser.set_defaults(handler=_verify_patch)

    release_parser = subparsers.add_parser(
        "release", help="stage or roll back signed local releases"
    )
    release_parser.add_argument("--release-root", required=True)
    release_parser.add_argument("--key-env", default="SIRO_RELEASE_SIGNING_KEY")
    release_parser.add_argument("--database")
    release_subparsers = release_parser.add_subparsers(dest="release_command", required=True)
    stage_parser = release_subparsers.add_parser("stage")
    stage_parser.add_argument("--bundle", required=True)
    stage_parser.add_argument("--manifest", required=True)
    stage_parser.add_argument("--healthcheck", required=True, help="JSON argv array")
    stage_parser.set_defaults(handler=_release_stage)
    rollback_parser = release_subparsers.add_parser("rollback")
    rollback_parser.set_defaults(handler=_release_rollback)

    backup_parser = subparsers.add_parser("backup", help="create a consistent SQLite data backup")
    backup_parser.add_argument("--data", required=True)
    backup_parser.add_argument("--config", help="include validated settings in a ZIP bundle")
    backup_parser.add_argument("destination")
    backup_parser.set_defaults(handler=_backup)
    restore_parser = subparsers.add_parser(
        "restore", help="restore a SQLite backup into a data directory"
    )
    restore_parser.add_argument("--data", required=True)
    restore_parser.add_argument("--config", help="restore settings from a ZIP bundle here")
    restore_parser.add_argument("source")
    restore_parser.set_defaults(handler=_restore)
    install_parser = subparsers.add_parser("install", help="install the local user service")
    install_parser.add_argument("--project-root", default=str(Path.cwd()))
    install_parser.add_argument(
        "--unit-dir", default="~/.config/systemd/user", help="systemd user unit directory"
    )
    install_parser.add_argument("--config-dir", default="~/.config/siro")
    install_parser.add_argument("--data-dir", default="~/.local/share/siro")
    install_parser.add_argument("--log-dir", default="~/.local/state/siro/log")
    install_parser.add_argument("--port", type=int, default=8000, choices=range(1024, 65536))
    install_parser.add_argument("--enable", action="store_true")
    install_parser.set_defaults(handler=_install)
    prune_parser = subparsers.add_parser("prune-logs", help="remove expired rotated logs")
    prune_parser.add_argument("--directory", required=True)
    prune_parser.add_argument("--days", type=int, default=14)
    prune_parser.set_defaults(handler=_prune_logs)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the SIRO CLI."""

    parser = build_parser()
    arguments = parser.parse_args(argv)
    from siro.adapters.data_ownership import (
        DataOwnerBusyError,
        DataOwnerUnavailableError,
        exclusive_data_owner,
    )

    database = None
    if arguments.command in {"demo", "backup", "restore"}:
        database = Path(arguments.data) / "siro.db"
    elif arguments.command == "release" and arguments.database:
        database = Path(arguments.database)
    if database is not None:
        try:
            write_target = None
            temporary_write_target = None
            if arguments.command == "backup":
                write_target = Path(arguments.destination)
                inputs = [database]
                outputs = [write_target]
                if arguments.config:
                    inputs.append(Path(arguments.config))
                    temporary_write_target = write_target.with_suffix(write_target.suffix + ".tmp")
                    outputs.append(temporary_write_target)
                if any(
                    output.resolve() == path.resolve() for output in outputs for path in inputs
                ) or (
                    temporary_write_target is not None
                    and temporary_write_target.resolve() == write_target.resolve()
                ):
                    print(json.dumps({"status": "invalid_backup_destination"}))
                    return 1
            elif arguments.command == "restore" and arguments.config:
                write_target = Path(arguments.config)
                temporary_write_target = write_target.with_suffix(write_target.suffix + ".tmp")
                restore_inputs = {database.resolve(), Path(arguments.source).resolve()}
                if (
                    write_target.resolve() in restore_inputs
                    or temporary_write_target.resolve() in restore_inputs
                    or temporary_write_target.resolve() == write_target.resolve()
                ):
                    print(json.dumps({"status": "invalid_restore_configuration"}))
                    return 1
            with exclusive_data_owner(
                database,
                write_target=write_target,
                temporary_write_target=temporary_write_target,
            ) as owner:
                arguments._data_loop_factory = owner.loop_factory
                return int(arguments.handler(arguments))
        except DataOwnerBusyError:
            print(json.dumps({"status": "data_in_use"}))
            return 1
        except DataOwnerUnavailableError:
            print(json.dumps({"status": "data_owner_unavailable"}))
            return 1
    return int(arguments.handler(arguments))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
