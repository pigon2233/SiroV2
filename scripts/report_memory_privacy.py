# ruff: noqa: RUF001  # User-facing Chinese text uses full-width punctuation.
"""Count active memories by privacy level and category. Read-only: never writes the database.

A memory's privacy comes from its source events, the same rule the prompt uses: a
cloud_allowed prompt only includes memories whose every source is cloud_allowed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

# Passwords, identity and money stay local_only whatever else the text mentions.
SENSITIVE = re.compile(
    r"(?:密碼|密码|帳號|账号|帳戶|账户|驗證碼|验证码|身分證|身份证|護照|护照|本名|真名|全名|"
    r"地址|住址|住在|電話|电话|手機號|手机号|生日|出生|"
    r"信用卡|銀行|银行|卡號|卡号|存款|薪水|薪資|薪资|收入|財務|财务|貸款|贷款|欠款|債|债|"
    r"股票|投資|投资|保險|保险|稅|税|私鑰|私钥|api[\s_-]?key|token|secret)",
    re.IGNORECASE,
)
CATEGORIES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "name",
        "稱呼",
        re.compile(r"(?:叫我|稱呼|称呼|暱稱|昵称|綽號|绰号|小名|名字|叫做|叫她|叫他)"),
    ),
    (
        "preference",
        "喜好",
        re.compile(
            r"(?:喜歡|喜欢|討厭|讨厌|愛吃|爱吃|愛喝|爱喝|愛看|爱看|愛玩|爱玩|最愛|最爱|"
            r"偏好|興趣|兴趣|口味|不吃|不喝|習慣|习惯|傾向|倾向|想玩|想看|想吃|想喝)"
        ),
    ),
    (
        "routine",
        "作息",
        re.compile(
            r"(?:起床|睡覺|睡觉|就寢|就寝|午睡|熬夜|早睡|晚睡|上班|下班|上課|上课|下課|下课|"
            r"作息|通勤|早餐|午餐|晚餐|每天|每週|每周|週末|周末)"
        ),
    ),
)
LABELS = {"sensitive": "敏感（永遠 local_only）", "other": "其他"} | {
    key: label for key, label, _pattern in CATEGORIES
}
PROMOTABLE = tuple(key for key, _label, _pattern in CATEGORIES)
LEVELS = ("local_only", "trusted_lan", "cloud_allowed", "unknown", "no_source")


def categorize(text: str) -> str:
    if SENSITIVE.search(text):
        return "sensitive"
    for key, _label, pattern in CATEGORIES:
        if pattern.search(text):
            return key
    return "other"


def level(privacies: list[str | None]) -> str:
    """The route a memory can reach: the strictest of its sources."""
    if not privacies:
        return "no_source"
    if any(item not in ("local_only", "trusted_lan", "cloud_allowed") for item in privacies):
        return "unknown"
    if all(item == "cloud_allowed" for item in privacies):
        return "cloud_allowed"
    if all(item in ("trusted_lan", "cloud_allowed") for item in privacies):
        return "trusted_lan"
    return "local_only"


@dataclass(frozen=True, slots=True)
class MemoryRow:
    memory_id: str
    identity_id: str
    person_id: str
    kind: str
    text: str
    confidence: float
    valid_from: str | None
    valid_to: str | None
    revision: int
    level: str
    category: str
    linked: bool
    revoked: bool
    link_reasons: tuple[str, ...] = ()


def default_database() -> Path:
    return Path(os.environ.get("SIRO_DATA_DIR", ".siro-data")) / "siro.db"


def read_memories(connection: sqlite3.Connection) -> list[MemoryRow]:
    """Active committed memories with their source privacy. Works on a read-only connection."""
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "SELECT * FROM memories WHERE deleted_at IS NULL AND status = 'committed' "
        "ORDER BY valid_from, memory_id"
    ).fetchall()
    result: list[MemoryRow] = []
    for row in rows:
        memory_id = row["memory_id"]
        sources = connection.execute(
            "SELECT json_extract(e.envelope_json, '$.privacy') AS privacy, "
            "r.source_event_id AS revoked FROM memory_sources s "
            "LEFT JOIN events e ON e.event_id = s.source_event_id "
            "LEFT JOIN memory_source_revocations r ON r.source_event_id = s.source_event_id "
            "WHERE s.memory_id = ?",
            (memory_id,),
        ).fetchall()
        reasons: list[str] = []
        if (
            connection.execute(
                "SELECT 1 FROM memory_derivations WHERE parent_memory_id = ? "
                "OR child_memory_id = ? LIMIT 1",
                (memory_id, memory_id),
            ).fetchone()
            is not None
        ):
            reasons.append("derivation")
        if (
            connection.execute(
                "SELECT 1 FROM semantic_facts WHERE memory_id = ? LIMIT 1", (memory_id,)
            ).fetchone()
            is not None
        ):
            reasons.append("semantic_fact")
        result.append(
            MemoryRow(
                memory_id=memory_id,
                identity_id=row["identity_id"],
                person_id=row["person_id"],
                kind=row["kind"],
                text=row["text"],
                confidence=float(row["confidence"]),
                valid_from=row["valid_from"],
                valid_to=row["valid_to"],
                revision=int(row["revision"]),
                level=level([source["privacy"] for source in sources]),
                category=categorize(row["text"]),
                linked=bool(reasons),
                revoked=any(source["revoked"] is not None for source in sources),
                link_reasons=tuple(reasons),
            )
        )
    return result


def open_read_only(database: Path) -> sqlite3.Connection:
    path = database.resolve(strict=True)
    if not path.is_file():
        raise ValueError("database must be a file")
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
    connection.execute("PRAGMA query_only=ON")
    return connection


SKIP_LABELS = {
    "derivation": "有衍生記憶（memory_derivations）",
    "semantic_fact": "有語意事實（semantic_facts）",
    "revoked": "來源已撤銷",
}


def skipped(memories: list[MemoryRow]) -> list[MemoryRow]:
    """Everyday memories that are not cloud_allowed but promotion leaves alone."""
    return [
        item
        for item in memories
        if item.category in PROMOTABLE
        and item.level != "cloud_allowed"
        and (item.linked or item.revoked)
    ]


def skip_reasons(item: MemoryRow) -> tuple[str, ...]:
    return item.link_reasons + (("revoked",) if item.revoked else ())


def _short(text: str, width: int = 60) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= width else flat[: width - 1] + "…"


def report(database: Path, *, examples: int = 3) -> dict[str, object]:
    if not 0 <= examples <= 20:
        raise ValueError("examples must be between 0 and 20")
    with closing(open_read_only(database)) as connection:
        memories = read_memories(connection)
    levels = Counter(item.level for item in memories)
    table: dict[str, dict[str, object]] = {}
    for item in memories:
        cell = table.setdefault(f"{item.level}/{item.category}", {"count": 0, "examples": []})
        cell["count"] = int(str(cell["count"])) + 1
        shown = cell["examples"]
        assert isinstance(shown, list)
        if len(shown) < examples:
            shown.append(f"[{item.kind}] {_short(item.text)}")
    promotable = [
        item
        for item in memories
        if item.level != "cloud_allowed"
        and item.category in PROMOTABLE
        and not item.linked
        and not item.revoked
    ]
    return {
        "read_only": True,
        "total": len(memories),
        "by_level": {name: levels.get(name, 0) for name in LEVELS},
        "by_kind": dict(Counter(item.kind for item in memories)),
        "by_level_and_category": table,
        "promotable": dict(Counter(item.category for item in promotable)),
        "linked_skipped": sum(
            1 for item in memories if item.linked and item.category in PROMOTABLE
        ),
        "skipped": [
            {
                "memory_id": item.memory_id,
                "category": item.category,
                "level": item.level,
                "reasons": list(skip_reasons(item)),
                "text": _short(item.text),
            }
            for item in skipped(memories)
        ],
    }


def render(result: dict[str, object]) -> str:
    lines = [f"有效記憶共 {result['total']} 筆（唯讀統計，沒有修改資料庫）", "", "依隱私等級："]
    by_level = result["by_level"]
    assert isinstance(by_level, dict)
    lines.extend(f"  {name}: {count}" for name, count in by_level.items())
    lines += ["", "依等級與類別（附範例）："]
    table = result["by_level_and_category"]
    assert isinstance(table, dict)
    for key in sorted(table):
        cell = table[key]
        level_name, category = key.split("/", 1)
        lines.append(f"  {level_name} · {LABELS[category]}: {cell['count']}")
        lines.extend(f"      - {example}" for example in cell["examples"])
    promotable = result["promotable"]
    assert isinstance(promotable, dict)
    lines += ["", "可以用 promote_memory_privacy.py 逐類確認改成 cloud_allowed 的："]
    for key in PROMOTABLE:
        lines.append(f"  {LABELS[key]}: {promotable.get(key, 0)}")
    lines.append(f"  有衍生記憶或語意事實、這次不處理的: {result['linked_skipped']}")
    skipped_rows = result["skipped"]
    assert isinstance(skipped_rows, list)
    if skipped_rows:
        lines += ["", "不會被升級的稱呼／喜好／作息記憶與原因："]
        for row in skipped_rows:
            reasons = "、".join(SKIP_LABELS[reason] for reason in row["reasons"])
            lines.append(
                f"  - {row['memory_id']} {LABELS[row['category']]} [{row['level']}] "
                f"{row['text']}（{reasons}）"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, default=None, help="default $SIRO_DATA_DIR/siro.db"
    )
    parser.add_argument("--examples", type=int, default=3, help="0..20 examples per cell")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = parser.parse_args(argv)
    try:
        result = report(args.database or default_database(), examples=args.examples)
    except (OSError, ValueError, sqlite3.Error) as error:
        print(f"讀不到記憶資料庫：{error}")
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
