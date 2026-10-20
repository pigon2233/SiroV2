#!/usr/bin/env python3
"""Real local relevance evaluation, synthetic-only and no database/service changes.

Exit 0 means measurement finished, not a quality certificate. Old MEM04 cases are
known regression data. New contrast fixtures are frozen before first inference.
All classifier input/output usage is included separately from final-chat context.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import statistics
import tempfile
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from evaluate_memory_retrieval import (
    CASES,
    DIGEST,
    DISTRACTORS,
    HOLDOUT_NEGATIVE,
    HOLDOUT_POSITIVE,
    MODEL,
    NEGATIVES,
    CountedEmbedder,
    token_count,
)

from siro.adapters.models.ollama_embeddings import OllamaEmbedder
from siro.adapters.models.ollama_memory_relevance import PROMPT_VERSION, OllamaMemoryRelevance
from siro.contracts.events import Priority, Privacy, UserTextEvent, UserTextPayload
from siro.core.context import END, START, render_context
from siro.core.identity import IdentityService, IdentityState, ImmutableCore
from siro.core.memory import Memory, MemoryService, assemble_prompt
from siro.core.memory_retrieval import HybridMemoryRetriever
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.memory_vectors import SQLiteMemoryVectors
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository
from siro.ports.embeddings import EmbeddingProfile, RetrievalUnavailable
from siro.ports.memory_relevance import RelevanceCandidate

CHAT_MODEL = "qwen3:4b-instruct"
CHAT_DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
ROOT = Path(__file__).resolve().parents[1]


async def run(contrast_only: bool, token_probe_only: bool = False) -> dict[str, object]:
    fixture = ROOT / "tests/fixtures/memory_relevance.json"
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    judge = OllamaMemoryRelevance(CHAT_MODEL, CHAT_DIGEST)
    if token_probe_only:
        return {
            "synthetic_only": True,
            "model": CHAT_MODEL,
            "digest": CHAT_DIGEST,
            "prompt_version": PROMPT_VERSION,
            "token_probe": await retrieval(judge, True),
        }
    contrast = []
    for case in cases:
        before = time.perf_counter()
        candidates = tuple(
            RelevanceCandidate(
                "synthetic:" + hashlib.sha256(t.encode()).hexdigest(),
                t,
                ("conversation.user_text.v1",),
            )
            for t in case["texts"]
        )
        try:
            selected = list(await judge.select(case["query"], candidates))
            error = None
        except RetrievalUnavailable as exc:
            selected, error = [], str(exc)
        contrast.append(
            {
                "id": case["id"],
                "expected": case["selected"],
                "selected": selected,
                "passed": error is None and set(selected) == set(case["selected"]),
                "error": error,
                "seconds": time.perf_counter() - before,
            }
        )
        print(json.dumps(contrast[-1]), flush=True)
    result: dict[str, object] = {
        "synthetic_only": True,
        "model": CHAT_MODEL,
        "digest": CHAT_DIGEST,
        "prompt_version": PROMPT_VERSION,
        "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "contrast_passed": sum(bool(r["passed"]) for r in contrast),
        "contrast_total": len(contrast),
        "contrast": contrast,
        "contrast_usage": asdict(judge.usage),
    }
    if not contrast_only:
        result["retrieval_regression"] = await retrieval(judge)
    result["total_classifier_usage"] = asdict(judge.usage)
    return result


async def retrieval(judge: OllamaMemoryRelevance, probe_only: bool = False) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="siro-mem04b-") as directory:
        store = SQLiteStore(Path(directory) / "synthetic.sqlite")
        await store.initialize()
        identities = SQLiteIdentityRepository(store)
        identity = await IdentityService(identities).create(
            "siro",
            ImmutableCore(
                name="SIRO",
                baseline_identity="synthetic",
                core_values=("honesty",),
                creator_relationship="owner",
            ),
            now=datetime.now(UTC),
        )
        repo = SQLiteMemoryRepository(store)
        memories = []
        for index, text in enumerate([c[0] for c in CASES] + list(DISTRACTORS)):
            now = datetime.now(UTC)
            event_id = uuid5(NAMESPACE_URL, f"siro:mem04b:event:{index}")
            event = UserTextEvent(
                event_id=event_id,
                type="conversation.user_text.v1",
                source="synthetic",
                occurred_at=now,
                received_at=now,
                trace_id="synthetic",
                session_id="synthetic",
                turn_id=str(index),
                sequence=index + 1,
                priority=Priority.INTERACTIVE,
                privacy=Privacy.LOCAL_ONLY,
                payload=UserTextPayload(text=text, language="zh-TW"),
            )
            memory = Memory(
                uuid5(NAMESPACE_URL, f"siro:mem04b:memory:{index}"), "siro", text, (event_id,), now
            )
            await repo.add(memory, event)
            memories.append(memory)
        embedder = CountedEmbedder(OllamaEmbedder(EmbeddingProfile(MODEL, DIGEST)))
        service = MemoryService(
            repo,
            retriever=HybridMemoryRetriever(
                SQLiteMemoryVectors(store),
                embedder,
                relevance=judge,
            ),
        )
        if probe_only:
            return await token_probe(service, identity, memories, judge, embedder)
        queries: list[tuple[str, int | None, str]] = [
            ("development", i, q) for i, (_, q) in enumerate(CASES)
        ]
        queries += [("development_absent", None, q) for q in NEGATIVES]
        queries += [("former_holdout", i, q) for i, q in HOLDOUT_POSITIVE]
        queries += [("former_holdout_absent", None, q) for q in HOLDOUT_NEGATIVE]
        rows = []
        latencies: list[float] = []
        for group, target_index, query in queries:
            before_usage = judge.usage
            before = time.perf_counter()
            try:
                found = await service.recall_context("siro", query)
                error = None
            except RetrievalUnavailable as exc:
                found, error = [], str(exc)
            after = judge.usage
            elapsed = time.perf_counter() - before
            latencies.append(elapsed)
            rows.append(
                {
                    "group": group,
                    "query": query,
                    "target_index": target_index,
                    "selected_indices": [memories.index(m) for m in found],
                    "exact_source_set": error is None
                    and (not found if target_index is None else found == [memories[target_index]]),
                    "passed": error is None
                    and (not found if target_index is None else memories[target_index] in found),
                    "error": error,
                    "seconds": elapsed,
                    "classifier_input_tokens": after.input_tokens - before_usage.input_tokens,
                    "classifier_output_tokens": after.output_tokens - before_usage.output_tokens,
                }
            )
            print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
        before_usage = judge.usage
        before = time.perf_counter()
        await service.recall_context("siro", CASES[1][1])
        warm_seconds = time.perf_counter() - before
        return {
            "cases": rows,
            "groups": {
                group: {
                    "passed": sum(bool(r["passed"]) for r in rows if r["group"] == group),
                    "total": sum(r["group"] == group for r in rows),
                    "exact_source_set": sum(
                        bool(r["exact_source_set"]) for r in rows if r["group"] == group
                    ),
                }
                for group in (
                    "development",
                    "development_absent",
                    "former_holdout",
                    "former_holdout_absent",
                )
            },
            "median_seconds": statistics.median(latencies),
            "repeat_seconds": warm_seconds,
            "repeat_classifier_inputs": judge.usage.input_tokens - before_usage.input_tokens,
            "repeat_classifier_outputs": judge.usage.output_tokens - before_usage.output_tokens,
            "document_embedding_inputs": embedder.document_inputs,
        }


async def token_probe(
    service: MemoryService,
    identity: IdentityState,
    memories: list[Memory],
    judge: OllamaMemoryRelevance,
    embedder: CountedEmbedder,
) -> dict[str, object]:
    # Same fixed successful-source question as MEM04. Counts include classifier
    # work, not just the final chat prompt; different embedding tokenizer excluded.
    before = judge.usage
    started = time.perf_counter()
    found = await service.recall_context("siro", CASES[1][1])
    cold_seconds = time.perf_counter() - started
    after = judge.usage
    packets = {}
    for name, selected in (("full_corpus", memories), ("filtered", found)):
        snapshot = await service.context_snapshot(
            "siro", selected, route_privacy=Privacy.LOCAL_ONLY
        )
        context = render_context("synthetic", "siro", selected, snapshot)
        if name == "full_corpus":
            data = json.loads(context[len(START) : -len(END)])
            data["memories"] = []
            for start in range(0, len(selected), 5):
                part = render_context("synthetic", "siro", selected[start : start + 5], snapshot)
                data["memories"].extend(json.loads(part[len(START) : -len(END)])["memories"])
            context = START + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + END
        prompt = assemble_prompt(
            identity, "", selected, (), context_evidence=context, native_dialogue=True
        )
        packets[name] = await token_count(prompt)
    started = time.perf_counter()
    await service.recall_context("siro", CASES[1][1])
    warm_seconds = time.perf_counter() - started
    return {
        "case": 2,
        "target_recalled": memories[1] in found,
        "selected_indices": [memories.index(m) for m in found],
        "classifier_input_tokens": after.input_tokens - before.input_tokens,
        "classifier_output_tokens": after.output_tokens - before.output_tokens,
        "classifier_unmeasured_calls": after.unmeasured_calls - before.unmeasured_calls,
        "chat_prompt_tokens": packets,
        "generative_model_tokens_filtered": packets["filtered"]
        + after.input_tokens
        - before.input_tokens
        + after.output_tokens
        - before.output_tokens,
        "generative_model_tokens_full_corpus": packets["full_corpus"],
        "cold_recall_seconds": cold_seconds,
        "warm_recall_seconds": warm_seconds,
        "warm_classifier_input_tokens": judge.usage.input_tokens - after.input_tokens,
        "warm_classifier_output_tokens": judge.usage.output_tokens - after.output_tokens,
        "embedding_document_inputs": embedder.document_inputs,
        "embedding_query_inputs": embedder.query_inputs,
        "limitations": (
            "Single synthetic case. Generative token sum excludes embedding tokens "
            "and final answer output; chat probes generate one unscored token each."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--contrast-only", action="store_true")
    mode.add_argument("--token-probe-only", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("preserve previous evidence: output must be new")
    result = asyncio.run(run(args.contrast_only, args.token_probe_only))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
