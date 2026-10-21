#!/usr/bin/env python3
"""Opt-in real local embedding evaluation; synthetic data, temporary database only.

Run with PYTHONPATH=src. Writes new JSON output only, never a private database.
Token comparison is against sending the entire 30-memory corpus, not lexical
recall (which may use fewer tokens by finding nothing). No answer-quality claim.
"""

# ruff: noqa: RUF001 -- Deliberate Traditional Chinese synthetic fixtures.

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import statistics
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import httpx

from siro.adapters.models.ollama_embeddings import OllamaEmbedder
from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.context import END, START, render_context
from siro.core.identity import IdentityService, ImmutableCore
from siro.core.memory import Memory, MemoryService, assemble_prompt
from siro.core.memory_retrieval import HybridMemoryRetriever
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.memory_vectors import SQLiteMemoryVectors
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository
from siro.ports.embeddings import EmbeddingProfile

MODEL = "qwen3-embedding:0.6b"
DIGEST = "ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d"
TOKEN_CASE = 1  # Case 2: allergy; report a successful-source token sample explicitly.
# Fixed before real inference. Independent topics and Chinese paraphrases plus paths.
CASES = (
    ("我喝咖啡會心悸，平常改喝無咖啡因的麥茶。", "想買飲料給我，要避開哪一類成分？"),
    ("我對花生過敏，聚餐點餐要先確認有沒有花生。", "請提醒我用餐的過敏原是什麼？"),
    ("我的工作日鬧鐘固定早上七點半響。", "週一早晨我通常幾點被叫醒？"),
    ("專案的備份資料夾是 E:/siro-backups。", "備份應該放哪個路徑？"),
    ("我週三晚上會到游泳池練習自由式。", "一星期哪天晚上我要去練游泳？"),
    ("我家貓咪叫小橘，牠愛吃鮪魚口味的罐頭。", "家裡那隻貓的名字和喜歡的食物？"),
    ("我希望收到的回覆使用繁體中文，內容簡短。", "你回答時該用什麼語言和篇幅？"),
    ("我搭火車旅行喜歡坐靠窗的位置。", "訂鐵路車票時我偏好哪種座位？"),
    ("我的筆電充電器收在書桌左邊第二個抽屜。", "電腦沒電了，電源供應器放哪裡？"),
    ("每個月五號需要繳交房租。", "每月哪一天要付租金？"),
    ("我討厭香菜，吃麵時不要加。", "幫我點麵時哪種配料要拿掉？"),
    ("下次修繕要先處理浴室水龍頭漏水。", "家裡維修的優先項目是什麼？"),
    ("我偏好深色介面，晚上看螢幕比較舒服。", "設定軟體外觀時，我喜歡亮色還是暗色？"),
    ("我學日文時每天背十個單字。", "我每天的外語詞彙練習量是多少？"),
    ("我的單車胎壓使用七十 psi。", "腳踏車輪胎要打到多少氣壓？"),
    ("我的工作會議通常排在星期二下午兩點。", "例行開會是在何時？"),
    ("我把護照放在臥室衣櫃上層的藍色盒子。", "出國證件收在哪個地方？"),
    ("我在專注工作時會把手機調成靜音。", "我做事不想被電話打斷時會怎麼設定？"),
    ("我喜歡聽沒有歌詞的鋼琴音樂幫助閱讀。", "看書時適合放哪種背景音樂給我？"),
    ("測試設定檔位於 config/memory-test.toml。", "config/memory-test.toml 是拿來做什麼的？"),
)
DISTRACTORS = (
    "我朋友喝咖啡會加牛奶。",
    "同事週三晚上去健身房。",
    "客廳抽屜放的是遙控器。",
    "測試環境租金報表的日期欄位是整數。",
    "我妹妹喜歡香菜。",
    "白天戶外螢幕可能需要提高亮度。",
    "鄰居的貓叫豆豆。",
    "上次一次性的會議是週四上午九點。",
    "舊備份路徑 D:/archive 已停用。",
    "朋友的單車建議胎壓是九十 psi。",
)
NEGATIVES = (
    "我的血型是什麼？",
    "我家的門鎖密碼是多少？",
    "我的銀行帳號是什麼？",
    "我最喜歡哪一位歌手？",
)
# Frozen after the first development-set diagnosis, before running the 0.5 floor.
# These are a small holdout, not a representative production benchmark.
HOLDOUT_POSITIVE = (
    (0, "你還記得我為什麼不喝提神飲料嗎？"),
    (2, "明天要上班，鬧鐘該設幾點？"),
    (3, "資料副本平時儲存在哪個目錄？"),
    (5, "小橘的罐頭該挑什麼口味？"),
    (6, "請依照我喜歡的語文和長度來回覆。"),
    (8, "我找不到筆記型電腦的電源線，它收在哪裡？"),
    (9, "我每月要在幾號交房屋租金？"),
    (14, "我的自行車要充氣到多少 psi？"),
    (17, "工作要集中精神時，我的手機怎麼設定？"),
    (19, "記憶測試的 toml 檔案完整路徑是什麼？"),
)
HOLDOUT_NEGATIVE = (
    "我的生日是幾月幾號？",
    "我的鞋子穿幾號？",
    "我開的汽車型號是什麼？",
    "我在哪一間公司任職？",
    "我的住家完整地址是什麼？",
    "我的身分證字號是多少？",
    "我的電話號碼是多少？",
    "我的兄弟姊妹從事什麼職業？",
    "我上次出國去了哪個國家？",
    "我最喜歡什麼顏色？",
)


class CountedEmbedder:
    def __init__(self, adapter: OllamaEmbedder) -> None:
        self.adapter = adapter
        self.document_inputs = 0
        self.query_inputs = 0
        self.last_query_vector: tuple[float, ...] = ()

    @property
    def profile(self) -> EmbeddingProfile:
        return self.adapter.profile

    async def embed(self, texts: tuple[str, ...], *, query: bool) -> tuple[tuple[float, ...], ...]:
        if query:
            self.query_inputs += len(texts)
        else:
            self.document_inputs += len(texts)
        result = await self.adapter.embed(texts, query=query)
        if query:
            self.last_query_vector = result[0]
        return result


async def token_count(prompt: str) -> int:
    async with httpx.AsyncClient(trust_env=False, timeout=120) as client:
        result = await client.post(
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": "qwen3:4b-instruct",
                "stream": False,
                "think": False,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": CASES[TOKEN_CASE][1]},
                ],
                "options": {"num_predict": 1, "temperature": 0, "seed": 42, "num_ctx": 32768},
            },
        )
        if result.status_code != 200:
            raise RuntimeError(
                f"synthetic token measurement failed: {result.status_code} {result.text[:500]}"
            )
        count = result.json()["prompt_eval_count"]
        if not isinstance(count, int) or count <= 0:
            raise ValueError("provider did not report actual prompt token count")
        return count


async def evaluate(measure_tokens: bool) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="siro-mem04-") as directory:
        store = SQLiteStore(Path(directory) / "synthetic.sqlite")
        await store.initialize()
        identities = SQLiteIdentityRepository(store)
        identity = await IdentityService(identities).create(
            "siro",
            ImmutableCore(
                name="SIRO",
                baseline_identity="synthetic evaluation",
                core_values=("honesty",),
                creator_relationship="owner",
            ),
            now=datetime.now(UTC),
        )
        repo = SQLiteMemoryRepository(store)
        lexical = MemoryService(repo)
        memories = []
        for index, text in enumerate([c[0] for c in CASES] + list(DISTRACTORS)):
            now = datetime.now(UTC)
            event_id = uuid5(NAMESPACE_URL, f"siro:mem04:synthetic:event:{index}")
            event = UserTextEvent(
                event_id=event_id,
                type="conversation.user_text.v1",
                source="synthetic",
                occurred_at=now,
                received_at=now,
                trace_id="mem04-synthetic",
                session_id="synthetic",
                turn_id=str(index),
                sequence=index + 1,
                priority=Priority.INTERACTIVE,
                privacy=Privacy.LOCAL_ONLY,
                payload=UserTextPayload(text=text, language="zh-TW"),
            )
            memory = Memory(
                uuid5(NAMESPACE_URL, f"siro:mem04:synthetic:memory:{index}"),
                "siro",
                text,
                (event_id,),
                now,
            )
            await lexical.remember(memory, event)
            memories.append(memory)
        embedder = CountedEmbedder(OllamaEmbedder(EmbeddingProfile(MODEL, DIGEST)))
        hybrid = MemoryService(
            repo, retriever=HybridMemoryRetriever(SQLiteMemoryVectors(store), embedder)
        )
        rows = []
        latencies: list[float] = []
        selected_first = []
        for index, (_, query) in enumerate(CASES):
            old = await lexical.recall_context("siro", query)
            before = time.perf_counter()
            found = await hybrid.recall_context("siro", query)
            elapsed = time.perf_counter() - before
            latencies.append(elapsed)
            if index == TOKEN_CASE:
                selected_first = found
            target = memories[index].memory_id
            docs = await SQLiteMemoryVectors(store).documents(
                "siro", "owner", Privacy.LOCAL_ONLY, embedder.profile, 1000
            )
            similarities = {
                d.memory.memory_id: sum(
                    a * b for a, b in zip(embedder.last_query_vector, d.vector, strict=True)
                )
                for d in docs
                if d.vector is not None
            }
            rows.append(
                {
                    "case": index + 1,
                    "query": query,
                    "lexical_ids": [str(m.memory_id) for m in old],
                    "hybrid_ids": [str(m.memory_id) for m in found],
                    "lexical_hit5": any(m.memory_id == target for m in old),
                    "hybrid_hit5": any(m.memory_id == target for m in found),
                    "hybrid_hit1": bool(found and found[0].memory_id == target),
                    "seconds": elapsed,
                    "max_similarity": max(similarities.values()),
                    "target_similarity": similarities[target],
                }
            )
        docs_after_first_pass = embedder.document_inputs
        before = time.perf_counter()
        restarted = MemoryService(
            repo,
            retriever=HybridMemoryRetriever(SQLiteMemoryVectors(SQLiteStore(store.path)), embedder),
        )
        warm = await restarted.recall_context("siro", CASES[TOKEN_CASE][1])
        warm_seconds = time.perf_counter() - before
        negatives = []
        for query in NEGATIVES:
            found = await hybrid.recall_context("siro", query)
            negative_similarities = [
                sum(a * b for a, b in zip(embedder.last_query_vector, d.vector, strict=True))
                for d in docs
                if d.vector is not None
            ]
            negatives.append(
                {
                    "query": query,
                    "retrieved_ids": [str(m.memory_id) for m in found],
                    "empty": not found,
                    "max_similarity": max(negative_similarities),
                }
            )
        holdout_positive = []
        for target_index, query in HOLDOUT_POSITIVE:
            found = await hybrid.recall_context("siro", query)
            holdout_positive.append(
                {
                    "query": query,
                    "target_index": target_index,
                    "hit5": memories[target_index] in found,
                    "retrieved_ids": [str(m.memory_id) for m in found],
                }
            )
        holdout_negative = []
        for query in HOLDOUT_NEGATIVE:
            found = await hybrid.recall_context("siro", query)
            holdout_negative.append(
                {
                    "query": query,
                    "empty": not found,
                    "retrieved_ids": [str(m.memory_id) for m in found],
                }
            )
        prompts = {}
        for name, selected in (
            ("full_corpus", memories),
            ("hybrid", selected_first),
            ("lexical", await lexical.recall_context("siro", CASES[TOKEN_CASE][1])),
        ):
            snapshot = await lexical.context_snapshot(
                "siro", selected, route_privacy=Privacy.LOCAL_ONLY
            )
            context = render_context(
                "synthetic", "siro", selected, snapshot, route_privacy=Privacy.LOCAL_ONLY
            )
            if name == "full_corpus":
                # Production renderer intentionally caps five. The naive baseline
                # explicitly includes all thirty bodies and the same source metadata.
                data = json.loads(context.split(START, 1)[1].split(END, 1)[0])
                data["memories"] = []
                for start in range(0, len(selected), 5):
                    part = render_context(
                        "synthetic", "siro", selected[start : start + 5], snapshot
                    )
                    data["memories"].extend(
                        json.loads(part.split(START, 1)[1].split(END, 1)[0])["memories"]
                    )
                context = START + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + END
            prompt = assemble_prompt(
                identity, "", selected, (), context_evidence=context, native_dialogue=True
            )
            try:
                tokens = await token_count(prompt) if measure_tokens else None
                error = None
            except (RuntimeError, httpx.HTTPError) as exc:
                tokens, error = None, str(exc)
            prompts[name] = {
                "memory_count": len(selected),
                "context_utf8_bytes": len(context.encode()),
                "prompt_tokens": tokens,
                "measurement_error": error,
            }
        return {
            "synthetic_only": True,
            "model": MODEL,
            "digest": DIGEST,
            "dimensions": 1024,
            "minimum_similarity": 0.5,
            "fixture_sha256": hashlib.sha256(
                json.dumps(
                    [CASES, DISTRACTORS, NEGATIVES, HOLDOUT_POSITIVE, HOLDOUT_NEGATIVE],
                    ensure_ascii=False,
                ).encode()
            ).hexdigest(),
            "corpus_size": len(memories),
            "positive_cases": len(CASES),
            "lexical_hit5": sum(bool(r["lexical_hit5"]) for r in rows),
            "hybrid_hit5": sum(bool(r["hybrid_hit5"]) for r in rows),
            "hybrid_hit1": sum(bool(r["hybrid_hit1"]) for r in rows),
            "cold_first_seconds": rows[0]["seconds"],
            "warm_median_seconds": statistics.median(latencies[1:]),
            "restart_warm_seconds": warm_seconds,
            "document_inputs_first_pass": docs_after_first_pass,
            "document_inputs_after_restart_and_negatives": embedder.document_inputs,
            "restart_same_ranking": warm == selected_first,
            "negative_empty": sum(bool(r["empty"]) for r in negatives),
            "negative_cases": negatives,
            "holdout_positive_hit5": sum(bool(r["hit5"]) for r in holdout_positive),
            "holdout_negative_empty": sum(bool(r["empty"]) for r in holdout_negative),
            "holdout_positive_cases": holdout_positive,
            "holdout_negative_cases": holdout_negative,
            "token_comparison": prompts,
            "token_measurement_case": TOKEN_CASE + 1,
            "token_comparison_target_recalled": memories[TOKEN_CASE] in selected_first,
            "cases": rows,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--measure-tokens", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; preserve prior evidence")
    result = asyncio.run(evaluate(args.measure_tokens))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(
        json.dumps(
            {k: v for k, v in result.items() if not k.endswith("cases") or isinstance(v, int)},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
