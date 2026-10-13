from pathlib import Path

import pytest

from siro.core.affect import AffectState, AffectSystem, Agency, Appraisal
from siro.persistence.affect import Preference, SQLiteAffectRepository
from siro.persistence.sqlite import SQLiteStore

pytestmark = pytest.mark.asyncio


async def test_affect_and_preferences_survive_repository_restart(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    await store.run_transaction(
        lambda connection: connection.execute(
            "INSERT INTO identities(identity_id, core_json, core_version, created_at) "
            "VALUES ('siro', '{}', 1, '2026-09-28T00:00:00+00:00')"
        )
    )
    first = SQLiteAffectRepository(store)
    state = AffectState("sad", -0.6, 0.3, 0.7, "goal loss")
    await first.record("siro", "browser", state, "event-1")
    await first.put_preference(
        Preference(
            "p1",
            "siro",
            "owner",
            "owner",
            "爵士樂",
            0.8,
            0.9,
            1.0,
            "music",
            "committed",
            ("event-2",),
            1,
        )
    )

    reopened = SQLiteAffectRepository(SQLiteStore(store.path))
    assert await reopened.state("siro", "browser") == state
    preferences = await reopened.preferences("siro", "owner")
    assert preferences[0].subject == "爵士樂"
    assert preferences[0].source_ids == ("event-2",)
    await reopened.put_preference(
        Preference(
            "ignored-on-update",
            "siro",
            "owner",
            "owner",
            "爵士樂",
            -0.4,
            0.6,
            1.0,
            "music",
            "committed",
            ("event-3",),
            1,
        )
    )
    corrected = (await reopened.preferences("siro", "owner"))[0]
    assert corrected.polarity == -0.4
    assert corrected.revision == 2
    assert await reopened.delete_preference(corrected.preference_id, "event-4")
    assert await reopened.preferences("siro", "owner") == []


async def test_complete_affect_dynamics_survive_restart(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    await store.run_transaction(
        lambda connection: connection.execute(
            "INSERT INTO identities(identity_id, core_json, core_version, created_at) "
            "VALUES ('siro', '{}', 1, '2026-09-28T00:00:00+00:00')"
        )
    )
    repository = SQLiteAffectRepository(store)
    result = AffectSystem().evaluate(
        "browser",
        Appraisal(
            event_id="event-5",
            novelty=0.8,
            goal_relevance=1.0,
            goal_conduciveness=-0.9,
            certainty=0.2,
            agency=Agency.OTHER,
            controllability=0.1,
            urgency=0.9,
            drive_changes={"safety": 0.2, "connection": 0.1},
        ),
    )
    await repository.record_result("siro", "browser", result, "event-5")

    reopened = SQLiteAffectRepository(SQLiteStore(store.path))
    mood, drives = await reopened.dynamics("siro", "browser")
    assert mood == result.mood
    assert drives == result.drives
    rows = await store.run_transaction(
        lambda connection: connection.execute(
            "SELECT COUNT(*) FROM emotion_activations"
        ).fetchone()[0]
    )
    assert rows == len(result.emotions)
