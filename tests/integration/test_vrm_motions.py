from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parents[2]
PACK = ROOT / "assets/companion/siro-vrm/0.1.0"


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def glb(data: bytes) -> tuple[Any, bytes]:
    length, kind = struct.unpack_from("<II", data, 12)
    assert data[:4] == b"glTF" and kind == 0x4E4F534A
    return json.loads(data[20 : 20 + length]), data[28 + length :]


def test_pack_matches_committed_clips_and_rebuilds_identically(tmp_path: Path) -> None:
    pack = json.loads((PACK / "pack.json").read_text(encoding="utf-8"))
    (tmp_path / "skeleton.json").write_bytes((PACK / "skeleton.json").read_bytes())
    motions = load("build_vrm_motions")
    for activity in pack["activities"]:
        data = (PACK / activity["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == activity["sha256"]
        if str(activity.get("source", "")).startswith("mocap"):
            continue  # rebuilt from fetched captures by build_vrm_mocap.py
        spec = motions.ACTIVITIES[activity["activity"]]
        rebuilt = motions.build_vrma(
            json.loads((tmp_path / "skeleton.json").read_text()),
            spec["sample"],
            spec["duration"],
            spec["loop"],
        )
        assert rebuilt == data, f"{activity['file']} is stale; rerun scripts/build_vrm_motions.py"


def test_clips_are_vrm_animation_with_hips_root_and_seamless_loops() -> None:
    pack = json.loads((PACK / "pack.json").read_text(encoding="utf-8"))
    names = {a["activity"] for a in pack["activities"]}
    assert {"idle", "nod", "wave", "think", "walk", "sit_down", "sit_loop", "stand_up"} <= names
    assert {"bow", "bye", "shake"} <= names
    for activity in pack["activities"]:
        document, blob = glb((PACK / activity["file"]).read_bytes())
        bones = document["extensions"]["VRMC_vrm_animation"]["humanoid"]["humanBones"]
        assert document["scenes"][0]["nodes"] == [bones["hips"]["node"]]
        animation = document["animations"][0]
        paths = {(c["target"]["node"], c["target"]["path"]) for c in animation["channels"]}
        assert (bones["hips"]["node"], "translation") in paths
        # Only humanoid bones are written: never expressions, lookAt or spring joints.
        assert {node for node, _path in paths} <= {b["node"] for b in bones.values()}
        times = document["accessors"][0]
        assert abs(times["max"][0] - activity["duration"]) < 1e-6
        if activity["loop"]:
            for sampler in animation["samplers"]:
                accessor = document["accessors"][sampler["output"]]
                view = document["bufferViews"][accessor["bufferView"]]
                width = 4 if accessor["type"] == "VEC4" else 3
                values = struct.unpack_from(
                    f"<{accessor['count'] * width}f", blob, view["byteOffset"]
                )
                assert values[:width] == values[-width:]


def test_mocap_clips_credit_their_source_and_rebuild_when_cached() -> None:
    pack = json.loads((PACK / "pack.json").read_text(encoding="utf-8"))
    entries = pack["activities"]
    captured = {a["activity"]: a for a in entries if str(a.get("source")).startswith("mocap")}
    assert set(captured) == {
        "idle",
        "nod",
        "shake",
        "wave",
        "bow",
        "bye",
        "think",
        "attention",
        "sit_loop",
    }
    for entry in captured.values():
        assert entry["license"] and entry["attribution"]
    assert "non-commercial" in captured["wave"]["license"]
    assert captured["sit_loop"]["entry_pose"] == captured["sit_loop"]["exit_pose"] == "seated"
    mocap = load("build_vrm_mocap")
    if not all((mocap.CACHE / name).exists() for name in mocap.SOURCES):
        pytest.skip("motion-capture sources not cached; run scripts/build_vrm_mocap.py")
    skeleton = json.loads((PACK / "skeleton.json").read_text(encoding="utf-8"))
    motions = mocap.load_motions()
    for name, (clip, shapes) in mocap.build_clips(mocap.CACHE, skeleton, motions).items():
        data = mocap.encode(motions, skeleton, clip, mocap.MOCAP[name][1], shapes)
        assert hashlib.sha256(data).hexdigest() == captured[name]["sha256"], name


def rotation_keys(name: str) -> dict[str, list[tuple[float, ...]]]:
    document, blob = glb((PACK / f"{name}.vrma").read_bytes())
    nodes = document["nodes"]
    animation = document["animations"][0]
    out = {}
    for channel in animation["channels"]:
        if channel["target"]["path"] != "rotation":
            continue
        accessor = document["accessors"][animation["samplers"][channel["sampler"]]["output"]]
        view = document["bufferViews"][accessor["bufferView"]]
        values = struct.unpack_from(f"<{accessor['count'] * 4}f", blob, view["byteOffset"])
        out[nodes[channel["target"]["node"]]["name"]] = [
            values[i : i + 4] for i in range(0, len(values), 4)
        ]
    return out


def test_layered_gestures_hand_back_to_the_idle_loop_exactly() -> None:
    idle = rotation_keys("idle")
    fingers = ("Thumb", "Index", "Middle", "Ring", "Little")
    for name in ("think", "attention"):
        clip = rotation_keys(name)
        body = [bone for bone in idle if not any(f in bone for f in fingers)]
        assert set(body) <= set(clip)
        for bone in body:
            last, first = clip[bone][-1], idle[bone][0]
            dot = abs(sum(a * b for a, b in zip(last, first, strict=True)))
            assert dot > 1 - 1e-6, f"{name} ends off the idle loop at {bone}"
        # and the pose really leaves the idle in between: the right hand comes up to the face
        middle = clip["rightLowerArm"][len(clip["rightLowerArm"]) // 2]
        dot = abs(sum(a * b for a, b in zip(middle, idle["rightLowerArm"][0], strict=True)))
        assert dot < 0.7, f"{name} never raises the right forearm"


def test_spring_tuning_assigns_body_colliders_to_clothing_chains() -> None:
    springs = load("tune_vrm_springs")
    names = [
        "J_Bip_C_Spine",
        "J_Bip_C_UpperChest",
        "J_Bip_C_Neck",
        "J_Bip_C_Head",
        "J_Bip_L_UpperArm",
        "J_Bip_R_UpperArm",
        "J_Bip_L_UpperLeg",
        "J_Bip_R_UpperLeg",
        "J_Bip_L_Hand",
        "J_Bip_R_Hand",
    ]
    document: dict[str, object] = {
        "nodes": [
            {"name": "J_Sec_C_Hood_01"},
            {"name": "J_Sec_L_TopsUpperArmInside_01"},
            {"name": "J_Sec_Hair1_01"},
        ],
        "extensions": {
            "VRMC_springBone": {
                "colliderGroups": [{"name": n, "colliders": []} for n in names],
                "springs": [
                    {"joints": [{"node": 0}]},
                    {"joints": [{"node": 1}]},
                    {"joints": [{"node": 2}], "colliderGroups": [3]},
                ],
            }
        },
    }
    changed = springs.tune(document)
    result = document["extensions"]["VRMC_springBone"]["springs"]  # type: ignore[index]
    assert changed == ["J_Sec_C_Hood_01", "J_Sec_L_TopsUpperArmInside_01"]
    assert result[0]["colliderGroups"] == [1, 2, 3]
    assert result[1]["colliderGroups"] == [0, 1]
    assert result[2]["colliderGroups"] == [3]
