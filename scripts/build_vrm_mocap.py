"""Retarget motion-capture clips onto SIRO's VRM skeleton and add them to the activity pack.

Hand-keyed clips (``build_vrm_motions.py``) read as stiff, so the everyday gestures come from
real motion capture instead. Sources are fetched on demand into a cache outside the repository,
pinned by sha256; only the retargeted ``.vrma`` clips are committed.

- Bandai Namco Research Motion Dataset (CC BY-NC 4.0, non-commercial use only):
  wave, bow and bye.
- Mixamo animations shipped with the three.js examples (``Xbot.glb``, three.js r169): idle,
  nod and head shake.
- Think and a surprised start: authored arm and torso layers over the captured idle.

Run after ``build_vrm_motions.py`` (which rewrites pack.json): this replaces the authored
entries it supersedes and appends the rest, marking each with its source and licence.

Retargeting works on world rotations. Each source joint gets a T-pose calibration rotation: the
torso is upright, arms point straight out and legs straight down, matching VRM 1.0 normalized
bones; elbow and knee twist comes from the hinge axis measured in the motion itself, and the
remaining twist offsets of the rig are zeroed on average. Then ``vrm_world = source_world @
calibration.T`` per frame, converted to parent-relative rotations.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import struct
import urllib.request
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "assets" / "companion" / "siro-vrm" / "0.1.0"
CACHE = Path.home() / ".cache" / "siro" / "mocap"
FPS = 30

BANDAI = (
    "https://raw.githubusercontent.com/BandaiNamcoResearchInc/"
    "Bandai-Namco-Research-Motiondataset/master/dataset"
)
BANDAI_LICENSE = "CC BY-NC 4.0 (Bandai Namco Research Motion Dataset); non-commercial use only"
BANDAI_CREDIT = "Bandai Namco Research Inc., Bandai-Namco-Research-Motiondataset"
MIXAMO_LICENSE = "Mixamo animation as distributed in the three.js examples (MIT repository)"
MIXAMO_CREDIT = "Mixamo (Adobe), via three.js examples/models/gltf/Xbot.glb r169"
SOURCES = {
    "Xbot.glb": (
        "https://raw.githubusercontent.com/mrdoob/three.js/r169/examples/models/gltf/Xbot.glb",
        "002f8d269de68e5dce3d25195caf390d1aa359bbfaae3fcf4c8dc78ec36c3ba5",
    ),
    "dataset-2_wave-right-hand_normal_001.bvh": (
        f"{BANDAI}/Bandai-Namco-Research-Motiondataset-2/data/"
        "dataset-2_wave-right-hand_normal_001.bvh",
        "d0e1907bcaa25c6ee0596a9e652b226c532e9af4c01eb860a4bd7487ab2c7c15",
    ),
    "dataset-1_bow_normal_001.bvh": (
        f"{BANDAI}/Bandai-Namco-Research-Motiondataset-1/data/dataset-1_bow_normal_001.bvh",
        "4e390b9c92caf7bb92b49bb0b5df72cf6e9f48900656b55a100a77b6bab0946b",
    ),
    "dataset-1_bye_normal_001.bvh": (
        f"{BANDAI}/Bandai-Namco-Research-Motiondataset-1/data/dataset-1_bye_normal_001.bvh",
        "cf821ed70f42832e9b519103ffb5e0a0f458ab46582340071b8867a633e8ee4d",
    ),
}

Quats = dict[str, np.ndarray]  # VRM bone -> (frames, 4) xyzw, parent-relative
Clip = tuple[Quats, np.ndarray]  # rotations, hips world position (frames, 3) in metres

UP, LEFT, FORWARD = np.array([0.0, 1, 0]), np.array([1.0, 0, 0]), np.array([0.0, 0, 1])


def load_motions() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "build_vrm_motions", ROOT / "scripts" / "build_vrm_motions.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.overlap = module.delay  # kept for the authored layers over captured motion
    module.delay = lambda bone: 0.0  # captured motion already has its own overlap
    return module


def fetch(name: str, cache: Path) -> Path:
    url, digest = SOURCES[name]
    path = cache / name
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as response:
            path.write_bytes(response.read())
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != digest:
        raise SystemExit(f"{path}: sha256 {actual} does not match the pinned {digest}")
    return path


# --- rotation helpers (row-stacked numpy, quaternions xyzw) ---------------------------------


def unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v)


def axis_angle(axis: np.ndarray, angle: float) -> np.ndarray:
    a = unit(axis)
    k = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(angle) * k + (1 - np.cos(angle)) * k @ k


def min_rotation(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a, b = unit(a), unit(b)
    v, c = np.cross(a, b), float(np.dot(a, b))
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1 + c)


def two_vector(
    p_local: np.ndarray, s_local: np.ndarray, p_world: np.ndarray, s_world: np.ndarray
) -> np.ndarray:
    def frame(p: np.ndarray, s: np.ndarray) -> np.ndarray:
        x = unit(p)
        z = unit(np.cross(x, s))
        return np.stack([x, np.cross(z, x), z], axis=1)

    return frame(p_world, s_world) @ frame(p_local, s_local).T


def to_quat(m: np.ndarray) -> np.ndarray:
    w = np.sqrt(np.maximum(0, 1 + m[..., 0, 0] + m[..., 1, 1] + m[..., 2, 2])) / 2
    x = np.sqrt(np.maximum(0, 1 + m[..., 0, 0] - m[..., 1, 1] - m[..., 2, 2])) / 2
    y = np.sqrt(np.maximum(0, 1 - m[..., 0, 0] + m[..., 1, 1] - m[..., 2, 2])) / 2
    z = np.sqrt(np.maximum(0, 1 - m[..., 0, 0] - m[..., 1, 1] + m[..., 2, 2])) / 2
    x = np.copysign(x, m[..., 2, 1] - m[..., 1, 2])
    y = np.copysign(y, m[..., 0, 2] - m[..., 2, 0])
    z = np.copysign(z, m[..., 1, 0] - m[..., 0, 1])
    q = np.stack([x, y, z, w], axis=-1)
    return q / np.linalg.norm(q, axis=-1, keepdims=True)


def to_matrix(q: np.ndarray) -> np.ndarray:
    x, y, z, w = np.moveaxis(q, -1, 0)
    return np.stack(
        [
            np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], -1),
            np.stack([2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], -1),
            np.stack([2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)], -1),
        ],
        -2,
    )


def qmul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ax, ay, az, aw = np.moveaxis(a, -1, 0)
    bx, by, bz, bw = np.moveaxis(b, -1, 0)
    return np.stack(
        [
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz,
        ],
        -1,
    )


def qinv(q: np.ndarray) -> np.ndarray:
    return q * np.array([-1, -1, -1, 1])


def slerp(a: np.ndarray, b: np.ndarray, t: np.ndarray) -> np.ndarray:
    b = np.where((a * b).sum(-1, keepdims=True) < 0, -b, b)
    q = a + (b - a) * t[..., None]  # nlerp: the blends are short and between close poses
    return q / np.linalg.norm(q, axis=-1, keepdims=True)


def arc(a: np.ndarray, b: np.ndarray, t: np.ndarray) -> np.ndarray:
    """True slerp at constant angular speed, for wide swings; ``t`` may overshoot past 1."""

    b = np.where((a * b).sum(-1, keepdims=True) < 0, -b, b)
    theta = np.arccos(np.clip((a * b).sum(-1), -1, 1))
    s = np.sin(theta)
    near = s < 1e-6
    s = np.where(near, 1, s)
    wa = np.where(near, 1 - t, np.sin((1 - t) * theta) / s)
    wb = np.where(near, t, np.sin(t * theta) / s)
    q = wa[..., None] * a + wb[..., None] * b
    return q / np.linalg.norm(q, axis=-1, keepdims=True)


def parent_relative(world: dict[str, np.ndarray], skeleton: dict[str, Any]) -> Quats:
    local = {}
    for bone, w in world.items():
        parent = skeleton[bone]["parent"]
        while parent and parent not in world:
            parent = skeleton[parent]["parent"]
        rel = w if parent is None else np.swapaxes(world[parent], -1, -2) @ w
        local[bone] = to_quat(rel)
    return local


# --- BVH (Bandai Namco rig) -----------------------------------------------------------------

BVH_BONES = {
    "hips": "Hips",
    "spine": "Spine",
    "chest": "Chest",
    "neck": "Neck",
    "head": "Head",
    "leftShoulder": "Shoulder_L",
    "leftUpperArm": "UpperArm_L",
    "leftLowerArm": "LowerArm_L",
    "leftHand": "Hand_L",
    "rightShoulder": "Shoulder_R",
    "rightUpperArm": "UpperArm_R",
    "rightLowerArm": "LowerArm_R",
    "rightHand": "Hand_R",
    "leftUpperLeg": "UpperLeg_L",
    "leftLowerLeg": "LowerLeg_L",
    "leftFoot": "Foot_L",
    "leftToes": "Toes_L",
    "rightUpperLeg": "UpperLeg_R",
    "rightLowerLeg": "LowerLeg_R",
    "rightFoot": "Foot_R",
    "rightToes": "Toes_R",
}
BVH_CHILD = {
    "Hips": "Spine",
    "Spine": "Chest",
    "Chest": "Neck",
    "Neck": "Head",
    "Shoulder_L": "UpperArm_L",
    "UpperArm_L": "LowerArm_L",
    "LowerArm_L": "Hand_L",
    "Shoulder_R": "UpperArm_R",
    "UpperArm_R": "LowerArm_R",
    "LowerArm_R": "Hand_R",
    "UpperLeg_L": "LowerLeg_L",
    "LowerLeg_L": "Foot_L",
    "Foot_L": "Toes_L",
    "UpperLeg_R": "LowerLeg_R",
    "LowerLeg_R": "Foot_R",
    "Foot_R": "Toes_R",
}
# VRM normalized T-pose direction of each source bone.
BVH_TARGET = {
    "Spine": UP,
    "Neck": UP,
    "Head": UP,
    "Shoulder_L": LEFT,
    "UpperArm_L": LEFT,
    "LowerArm_L": LEFT,
    "Hand_L": LEFT,
    "Shoulder_R": -LEFT,
    "UpperArm_R": -LEFT,
    "LowerArm_R": -LEFT,
    "Hand_R": -LEFT,
    "UpperLeg_L": -UP,
    "LowerLeg_L": -UP,
    "UpperLeg_R": -UP,
    "LowerLeg_R": -UP,
    "Toes_L": FORWARD,
    "Toes_R": FORWARD,
}
# (upper, lower, end, hinge axis in the T-pose): forearms flex forward, shins flex back.
HINGES = [
    ("UpperArm_L", "LowerArm_L", "Hand_L", -UP),
    ("UpperArm_R", "LowerArm_R", "Hand_R", UP),
    ("UpperLeg_L", "LowerLeg_L", "Foot_L", LEFT),
    ("UpperLeg_R", "LowerLeg_R", "Foot_R", LEFT),
]
TWIST_FROM_MOTION = {
    "Spine",
    "Neck",
    "Head",
    "Shoulder_L",
    "Shoulder_R",
    "Hand_L",
    "Hand_R",
    "Foot_L",
    "Foot_R",
    "Toes_L",
    "Toes_R",
}


def parse_bvh(path: Path) -> tuple[list[dict[str, Any]], np.ndarray]:
    head, motion = path.read_text(encoding="utf-8").split("MOTION", 1)
    tokens = re.findall(r"\S+", head)
    joints: list[dict[str, Any]] = []
    stack: list[int] = []
    pending: dict[str, Any] | None = None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in ("ROOT", "JOINT"):
            pending = {"name": tokens[i + 1], "parent": stack[-1] if stack else -1}
            i += 2
        elif token == "End":  # end sites carry no channels
            depth, i = 0, i + 2
            while True:
                depth += {"{": 1, "}": -1}.get(tokens[i], 0)
                i += 1
                if depth == 0:
                    break
        elif token == "{":
            assert pending is not None
            joints.append(pending)
            stack.append(len(joints) - 1)
            i += 1
        elif token == "}":
            stack.pop()
            i += 1
        elif token == "OFFSET":
            joints[stack[-1]]["offset"] = np.array([float(x) for x in tokens[i + 1 : i + 4]])
            i += 4
        elif token == "CHANNELS":
            count = int(tokens[i + 1])
            joints[stack[-1]]["channels"] = tokens[i + 2 : i + 2 + count]
            i += 2 + count
        else:
            i += 1
    lines = motion.strip().splitlines()
    frames = int(lines[0].split()[1])
    data = np.array([[float(x) for x in line.split()] for line in lines[2 : 2 + frames]])
    return joints, data


def axis_matrix(axis: str, degrees: np.ndarray) -> np.ndarray:
    r = np.radians(degrees)
    c, s, one, zero = np.cos(r), np.sin(r), np.ones_like(r), np.zeros_like(r)
    rows = {
        "X": [[one, zero, zero], [zero, c, -s], [zero, s, c]],
        "Y": [[c, zero, s], [zero, one, zero], [-s, zero, c]],
        "Z": [[c, -s, zero], [s, c, zero], [zero, zero, one]],
    }[axis]
    return np.moveaxis(np.array(rows), [0, 1], [-2, -1])


def bvh_fk(joints: list[dict[str, Any]], data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    frames = len(data)
    rot = np.zeros((frames, len(joints), 3, 3))
    pos = np.zeros((frames, len(joints), 3))
    column = 0
    for j, joint in enumerate(joints):
        local = np.broadcast_to(np.eye(3), (frames, 3, 3)).copy()
        move = np.broadcast_to(joint["offset"], (frames, 3)).copy()
        for channel in joint["channels"]:
            values = data[:, column]
            column += 1
            if channel.endswith("position"):
                move[:, "XYZ".index(channel[0])] = values
            else:
                local = local @ axis_matrix(channel[0], values)
        p = joint["parent"]
        rot[:, j] = local if p < 0 else rot[:, p] @ local
        pos[:, j] = move if p < 0 else pos[:, p] + np.einsum("fij,fj->fi", rot[:, p], move)
    return rot, pos


def calibrate(
    joints: list[dict[str, Any]], rot: np.ndarray, pos: np.ndarray, foot: np.ndarray
) -> dict[str, np.ndarray]:
    index = {joint["name"]: i for i, joint in enumerate(joints)}
    offset = {joint["name"]: joint["offset"] for joint in joints}
    target = dict(BVH_TARGET, Foot_L=foot, Foot_R=foot * [-1, 1, 1])

    def bone_dir(name: str) -> np.ndarray:
        child = BVH_CHILD.get(name)
        if child:
            return offset[child]
        return offset[BVH_CHILD[joints[joints[index[name]]["parent"]]["name"]]]

    hinge_local, hinge_world = {}, {}
    for upper, lower, end, axis in HINGES:
        bend = np.cross(
            pos[:, index[lower]] - pos[:, index[upper]], pos[:, index[end]] - pos[:, index[lower]]
        )
        for name in (upper, lower):
            hinge_local[name] = unit(np.einsum("fji,fj->fi", rot[:, index[name]], bend).sum(0))
            hinge_world[name] = axis

    rest = {
        joints[0]["name"]: np.eye(3),
        "Hips": two_vector(offset["Spine"], offset["UpperLeg_L"] - offset["UpperLeg_R"], UP, LEFT),
        "Chest": two_vector(offset["Neck"], offset["Shoulder_L"] - offset["Shoulder_R"], UP, LEFT),
    }
    for joint in joints:
        name = joint["name"]
        if name in rest:
            continue
        parent_name = joints[joint["parent"]]["name"]
        parent = rest[parent_name]
        aim = unit(target[name])
        r = min_rotation(parent @ unit(bone_dir(name)), aim) @ parent
        if name in hinge_local:
            have = r @ hinge_local[name]
            have, want = (unit(v - aim * np.dot(v, aim)) for v in (have, hinge_world[name]))
            twist = np.arctan2(np.dot(np.cross(have, want), aim), np.dot(have, want))
            r = axis_angle(aim, twist) @ r
        elif name in TWIST_FROM_MOTION:
            rel = parent @ np.swapaxes(rot[:, index[parent_name]], -1, -2) @ rot[:, index[name]]
            q = to_quat(rel @ r.T)
            angle = 2 * np.arctan2(q[:, :3] @ aim, q[:, 3])
            r = axis_angle(aim, np.arctan2(np.sin(angle).mean(), np.cos(angle).mean())) @ r
        rest[name] = r
    return rest


def load_bvh(path: Path, skeleton: dict[str, Any]) -> Clip:
    joints, data = parse_bvh(path)
    rot, pos = bvh_fk(joints, data)
    index = {joint["name"]: i for i, joint in enumerate(joints)}
    foot = np.array(skeleton["leftToes"]["world"]) - np.array(skeleton["leftFoot"]["world"])
    rest = calibrate(joints, rot, pos, foot)
    world = {vrm: rot[:, index[src]] @ rest[src].T for vrm, src in BVH_BONES.items()}
    world["upperChest"] = world["chest"]
    forward = world["hips"][:, :, 2]  # face +Z on average
    yaw = -np.arctan2(forward[:, 0].mean(), forward[:, 2].mean())
    turn = axis_angle(UP, yaw)
    world = {bone: turn @ w for bone, w in world.items()}
    hips = pos[:, index["Hips"]] @ turn.T
    standing = np.median(hips[:, 1])
    return parent_relative(world, skeleton), hips / standing * skeleton["hips"]["world"][1]


# --- glTF (Mixamo rig, T-pose rest with identity rotations) ---------------------------------

MIXAMO_BONES = {
    "hips": "Hips",
    "spine": "Spine",
    "chest": "Spine1",
    "upperChest": "Spine2",
    "neck": "Neck",
    "head": "Head",
    "leftShoulder": "LeftShoulder",
    "leftUpperArm": "LeftArm",
    "leftLowerArm": "LeftForeArm",
    "leftHand": "LeftHand",
    "rightShoulder": "RightShoulder",
    "rightUpperArm": "RightArm",
    "rightLowerArm": "RightForeArm",
    "rightHand": "RightHand",
    "leftUpperLeg": "LeftUpLeg",
    "leftLowerLeg": "LeftLeg",
    "leftFoot": "LeftFoot",
    "leftToes": "LeftToeBase",
    "rightUpperLeg": "RightUpLeg",
    "rightLowerLeg": "RightLeg",
    "rightFoot": "RightFoot",
    "rightToes": "RightToeBase",
}


def load_mixamo(path: Path, animation: str, skeleton: dict[str, Any]) -> Clip:
    data = path.read_bytes()
    length = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20 : 20 + length])
    binary = data[28 + length :]

    def accessor(i: int) -> np.ndarray:
        a = doc["accessors"][i]
        view = doc["bufferViews"][a["bufferView"]]
        width = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[a["type"]]
        start = view.get("byteOffset", 0) + a.get("byteOffset", 0)
        values = np.frombuffer(binary, "<f4", a["count"] * width, start)
        return values.reshape(a["count"], width) if width > 1 else values

    nodes = doc["nodes"]
    name_of = [node["name"].removeprefix("mixamorig:") for node in nodes]
    index = {name: i for i, name in enumerate(name_of)}
    parent = {c: i for i, node in enumerate(nodes) for c in node.get("children", [])}
    anim = next(a for a in doc["animations"] if a["name"] == animation)
    duration = max(float(accessor(s["input"]).max()) for s in anim["samplers"])
    times = np.arange(round(duration * FPS) + 1) / FPS
    local: dict[str, np.ndarray] = {}
    hips = np.zeros((len(times), 3))
    for channel in anim["channels"]:
        sampler = anim["samplers"][channel["sampler"]]
        node = name_of[channel["target"]["node"]]
        keys, values = accessor(sampler["input"]), accessor(sampler["output"])
        k0 = np.clip(np.searchsorted(keys, times, side="right") - 1, 0, len(keys) - 1)
        k1 = np.minimum(k0 + 1, len(keys) - 1)
        u = np.clip((times - keys[k0]) / np.where(k1 > k0, keys[k1] - keys[k0], 1), 0, 1)
        if channel["target"]["path"] == "rotation":
            local[node] = to_matrix(slerp(values[k0], values[k1], u))
        elif channel["target"]["path"] == "translation" and node == "Hips":
            hips = values[k0] + (values[k1] - values[k0]) * u[:, None]
    identity = np.broadcast_to(np.eye(3), (len(times), 3, 3))

    def world(name: str) -> np.ndarray:
        m = local.get(name, identity)
        i = parent.get(index[name])
        while i is not None and nodes[i]["name"].startswith("mixamorig:"):
            m = local.get(name_of[i], identity) @ m
            i = parent.get(i)
        return m

    rotations = parent_relative({vrm: world(src) for vrm, src in MIXAMO_BONES.items()}, skeleton)
    rest_height = nodes[index["Hips"]]["translation"][1]
    return rotations, hips / rest_height * skeleton["hips"]["world"][1]


# --- clip editing ---------------------------------------------------------------------------


def narrow_stance(rotations: Quats, target: float = 0.01, leg: float = 0.85) -> Quats:
    """Swing wide-set thighs in about the hip; the feet keep their world orientation."""

    out = dict(rotations)
    hips = to_matrix(out["hips"])
    for side, sign in (("left", 1), ("right", -1)):
        thigh, shin, foot = (out[f"{side}{b}"] for b in ("UpperLeg", "LowerLeg", "Foot"))
        w = hips @ to_matrix(thigh)
        reach = 0.44 * (w @ -UP) + 0.41 * (w @ to_matrix(shin) @ -UP)
        excess = sign * reach[:, 0].mean() - target
        if excess <= 0:
            continue
        half = -sign * np.arctan2(excess, leg) / 2
        swung = qmul(np.array([0, 0, np.sin(half), np.cos(half)]), thigh)
        out[f"{side}Foot"] = qmul(qinv(shin), qmul(qinv(swung), qmul(thigh, qmul(shin, foot))))
        out[f"{side}UpperLeg"] = swung
    return out


def open_arms(rotations: Quats, degrees: float) -> Quats:
    """Lift the upper arms away from the body so a slim source rig clears SIRO's jacket."""

    out = dict(rotations)
    half = np.radians(degrees) / 2
    for side, sign in (("left", 1), ("right", -1)):
        lift = np.array([0, 0, sign * np.sin(half), np.cos(half)])
        out[f"{side}UpperArm"] = qmul(lift, out[f"{side}UpperArm"])
    return out


def mirror(clip: Clip) -> Clip:
    rotations, hips = clip
    flipped = {}
    for bone, q in rotations.items():
        other = bone.replace("left", "@").replace("right", "left").replace("@", "right")
        flipped[other] = q * np.array([1, -1, -1, 1])
    return flipped, hips * np.array([-1, 1, 1])


def join(a: Clip, b: Clip, blend: int = 10) -> Clip:
    """``a`` then ``b``, cross-fading ``blend`` frames where they meet."""

    t = (np.arange(blend) + 1) / (blend + 1)
    rotations = {}
    for bone in a[0]:
        qa, qb = a[0][bone], b[0][bone]
        seam = slerp(qa[-blend:], qb[:blend], t)
        rotations[bone] = np.concatenate([qa[:-blend], seam, qb[blend:]])
    ha, hb = a[1], b[1]
    seam_h = ha[-blend:] * (1 - t[:, None]) + hb[:blend] * t[:, None]
    return rotations, np.concatenate([ha[:-blend], seam_h, hb[blend:]])


def cut(clip: Clip, start: int, end: int | None = None) -> Clip:
    return {b: q[start:end] for b, q in clip[0].items()}, clip[1][start:end]


def close_loop(clip: Clip, blend: int = 12) -> Clip:
    rotations, hips = clip
    t = np.arange(blend) / blend
    out = {}
    for bone, q in rotations.items():
        q = q.copy()
        q[-blend:] = slerp(q[-blend:], np.repeat(q[:1], blend, 0), t)
        q[-1] = q[0]
        out[bone] = q
    hips = hips.copy()
    hips[-blend:] = hips[-blend:] * (1 - t[:, None]) + hips[0] * t[:, None]
    hips[-1] = hips[0]
    return out, hips


def in_place(clip: Clip) -> Clip:
    hips = clip[1].copy()
    hips[:, [0, 2]] -= hips[:, [0, 2]].mean(0)
    return clip[0], hips


# --- authored layers over the captured idle -------------------------------------------------
#
# None of the sources capture thinking or a surprised start, so those are authored poses laid
# over the captured idle: the arms swing to the pose outright, the torso and head add only the
# pose's offset from the stand, and the body underneath keeps breathing and shifting its weight.

Weight = Callable[[np.ndarray], np.ndarray]
Shapes = dict[str, np.ndarray]  # side -> (frames, 3): curl, spread, override weight


def in_out(u: np.ndarray) -> np.ndarray:
    return np.where(u < 0.5, 4 * u**3, 1 - (-2 * u + 2) ** 3 / 2)


def out_back(u: np.ndarray, overshoot: float) -> np.ndarray:
    v = u - 1
    return 1 + (overshoot + 1) * v**3 + overshoot * v**2


def envelope(rise: tuple[float, float], fall: tuple[float, float], overshoot: float = 0) -> Weight:
    """0 -> 1 over ``rise`` (seconds), back to 0 over ``fall``; overshoot makes the arrival land."""

    def weight(t: np.ndarray) -> np.ndarray:
        up = np.clip((t - rise[0]) / (rise[1] - rise[0]), 0, 1)
        down = np.clip((t - fall[0]) / (fall[1] - fall[0]), 0, 1)
        return (out_back(up, overshoot) if overshoot else in_out(up)) * (1 - in_out(down))

    return weight


def idle_tail(loop: Clip, seconds: float) -> Clip:
    """The idle loop leading up to its first frame, so a layered clip hands back seamlessly."""

    rotations, hips = loop
    index = np.arange(-round(seconds * FPS), 1) % (len(hips) - 1)
    return {bone: q[index] for bone, q in rotations.items()}, hips[index]


def layer(
    motions: ModuleType,
    base: Clip,
    target: dict[str, list[tuple[str, object]]],
    weight: Weight,
    absolute: tuple[str, ...] = (),
    additive: tuple[str, ...] = (),
    trail: bool = True,
) -> Clip:
    """Blend ``absolute`` bones to the target pose and add the target's offset from the stand
    pose to ``additive`` ones (build those targets with ``on_stand``); each bone trails its
    parent by the authored overlap delay (``trail=False`` keeps a fast beat, like a clap,
    in sync along the arm)."""

    rotations, hips = base
    t = np.arange(len(hips)) / FPS
    out = dict(rotations)
    for bone in (*absolute, *additive):
        stand = motions.STAND.get(bone, [])
        goal = np.broadcast_to(np.array(motions.compose(target.get(bone, stand))), out[bone].shape)
        w = weight(t - motions.overlap(bone)) if trail else weight(t)
        if bone in absolute:
            out[bone] = arc(out[bone], goal, w)
        else:
            identity = np.broadcast_to(np.array([0.0, 0, 0, 1]), goal.shape)
            offset = qmul(goal, qinv(np.array(motions.compose(stand))))
            out[bone] = qmul(arc(identity, offset, w), out[bone])
    return out, hips


def on_stand(motions: ModuleType, **extra: list[tuple[str, object]]) -> dict[str, Any]:
    """A target whose offset from the stand pose is exactly ``extra``."""

    return motions.add(motions.STAND, **extra)


def held_shape(curl: float, spread: float, weight: np.ndarray) -> np.ndarray:
    lag = lagged(np.clip(weight, 0, 1), loop=False)
    return np.stack([np.full_like(lag, curl), np.full_like(lag, spread), lag], -1)


RIGHT_ARM = ("rightShoulder", "rightUpperArm", "rightLowerArm", "rightHand")
LEFT_ARM = ("leftShoulder", "leftUpperArm", "leftLowerArm", "leftHand")
TORSO = ("hips", "spine", "chest", "neck", "head")


def think(motions: ModuleType, idle: Clip) -> tuple[Clip, Shapes]:
    """Chin in hand, the other arm folded under the elbow, head tilting further as she thinks."""

    clip = idle_tail(idle, 4.2)
    pose = motions.THINK
    deeper = on_stand(motions, neck=[("z", 7)], head=[("x", 3), ("z", 3)])
    clip = layer(motions, clip, pose, envelope((0.0, 0.9), (3.2, 3.95)), additive=TORSO)
    clip = layer(motions, clip, deeper, envelope((1.0, 2.6), (2.9, 3.6)), additive=("neck", "head"))
    clip = layer(motions, clip, pose, envelope((0.1, 0.85), (3.3, 3.95), 0.6), RIGHT_ARM)
    support = envelope((0.22, 0.95), (3.2, 3.9))
    clip = layer(motions, clip, pose, support, LEFT_ARM)
    t = np.arange(len(clip[1])) / FPS
    hand = envelope((0.3, 0.85), (3.3, 3.7))(t)  # a loose fist under the chin, not an open hand
    return clip, {"right": held_shape(1.6, 0.3, hand), "left": held_shape(1.1, 0.6, support(t))}


FLINCH = {"spine": [("x", -4)], "chest": [("x", -4)], "neck": [("x", -5)], "head": [("x", -4)]}
SURPRISE = {
    "leftShoulder": [("z", 7)],
    "rightShoulder": [("z", -7)],
    # A gasp: the right hand flies up to the mouth, the left lands across the chest.
    "rightUpperArm": [("x", 30), ("z", 90), ("x", -46)],
    "rightLowerArm": [("y", 146), ("z", -18)],
    "rightHand": [("z", 0), ("x", -10)],
    "leftUpperArm": [("x", 55), ("z", -70), ("x", -14)],
    "leftLowerArm": [("y", -112)],
    "leftHand": [("z", 0)],
}


def surprise(motions: ModuleType, idle: Clip) -> tuple[Clip, Shapes]:
    """A startle: a quick flinch back with a gasp, a beat of held breath, then relaxing."""

    clip = idle_tail(idle, 1.9)
    flinch = on_stand(motions, **FLINCH)
    clip = layer(motions, clip, flinch, envelope((0.0, 0.18), (0.8, 1.55), 1.8), additive=TORSO)
    arms = envelope((0.03, 0.24), (0.85, 1.6), 1.4)
    clip = layer(motions, clip, SURPRISE, arms, (*LEFT_ARM, *RIGHT_ARM))
    w = arms(np.arange(len(clip[1])) / FPS)
    return clip, {"right": held_shape(0.6, 1.6, w), "left": held_shape(0.7, 1.0, w)}


# --- pack -----------------------------------------------------------------------------------

MOCAP = {
    "idle": ("Mixamo idle, mirrored and joined into a 5 s weight-shifting loop.", True),
    "nod": ("Mixamo agree: a few natural nods; returns to the stand pose.", False),
    "shake": ("Mixamo head shake (no); returns to the stand pose.", False),
    "wave": ("Captured right-hand wave, trimmed to two sweeps; returns to the stand pose.", False),
    "bow": ("Captured polite bow with hands together; returns to the stand pose.", False),
    "bye": ("Captured small hand-by-the-face hello/bye; returns to the stand pose.", False),
    "think": (
        "Chin in hand over the captured idle, head tilting further; returns to the idle.",
        False,
    ),
    "attention": (
        "Startle over the captured idle: flinch back, a hand to the mouth, held breath, relax.",
        False,
    ),
    "sit_loop": (
        "Seated on an edge with the captured idle's breathing and sway in the upper body,"
        " an idle foot swing; loops until stand_up.",
        True,
    ),
    "idle_happy": (
        "Happy idle: livelier sway, chest up, hands behind the back, small bounce.",
        True,
    ),
    "idle_sad": ("Sad idle: slower, head and shoulders down, hands together low in front.", True),
    "idle_angry": ("Angry idle: arms folded, chin down, an impatient foot tap.", True),
    "idle_relaxed": ("Relaxed idle: slower and looser, shoulders down, head at a tilt.", True),
    "clap": ("Three quick claps in front of the chest with a happy lift.", False),
    "sigh": ("A breath in, shoulders up, then a long breath out that lets everything drop.", False),
    "stretch": ("Both arms up overhead, leaning back; needs headroom above the head.", False),
    "yawn": ("Head back, shoulders up, right hand over the mouth.", False),
}
MOODS = {"idle_happy", "idle_sad", "idle_angry", "idle_relaxed"}
LAYERED = {"think", "attention", "sit_loop", *MOODS, "clap", "sigh", "stretch", "yawn"}
SEATED = {"sit_loop"}


def build_clips(
    cache: Path, skeleton: dict[str, Any], motions: ModuleType
) -> dict[str, tuple[Clip, Shapes | None]]:
    xbot = fetch("Xbot.glb", cache)

    def mixamo(name: str) -> Clip:
        rotations, hips = load_mixamo(xbot, name, skeleton)
        return in_place((open_arms(narrow_stance(rotations), 4), hips))

    def bvh(name: str) -> Clip:
        return in_place(load_bvh(fetch(f"{name}.bvh", cache), skeleton))

    captured = mixamo("idle")
    idle = close_loop(join(captured, mirror(captured)))
    wave = bvh("dataset-2_wave-right-hand_normal_001")
    clips = {
        "idle": idle,
        "nod": mixamo("agree"),
        "shake": mixamo("headShake"),
        # raise and one and a half sweeps, then the matching sweep before the arm comes down
        "wave": join(cut(wave, 0, 65), cut(wave, 136)),
        "bow": bvh("dataset-1_bow_normal_001"),
        "bye": bvh("dataset-1_bye_normal_001"),
    }
    out: dict[str, tuple[Clip, Shapes | None]] = {name: (c, None) for name, c in clips.items()}
    out["think"] = think(motions, idle)
    out["attention"] = surprise(motions, idle)
    out["sit_loop"] = (seated(motions, idle, skeleton), None)
    out["idle_happy"] = mood_happy(motions, idle)
    out["idle_sad"] = mood_sad(motions, idle, offset_pose(xbot, "sad_pose", skeleton))
    out["idle_angry"] = mood_angry(motions, idle)
    out["idle_relaxed"] = mood_relaxed(motions, idle)
    out["clap"] = clap(motions, idle)
    out["sigh"] = sigh(motions, idle)
    out["stretch"] = stretch(motions, idle)
    out["yawn"] = yawn(motions, idle)
    return out


UPPER_BODY = ("spine", "chest", "upperChest", "neck", "head", "leftShoulder", "rightShoulder")


def seated(
    motions: ModuleType, idle: Clip, skeleton: dict[str, Any], strength: float = 0.8
) -> Clip:
    """The authored seated loop with the captured idle's breathing and sway in the upper body.

    Two idle cycles long; the authored loop is stretched to match so both stay seamless.
    """

    period = len(idle[1]) - 1
    index = np.arange(2 * period + 1) % period
    duration = 2 * period / FPS
    samples = [motions.sit_loop(i / FPS * 8.0 / duration) for i in range(len(index))]
    fingers = (*motions.FINGERS, "Thumb")
    # fingers are left to the hand layer, which keeps them drifting
    bones = {b for p, _h in samples for b in p if not any(f in b for f in fingers)}
    out = {b: np.array([motions.compose(p.get(b, [])) for p, _h in samples]) for b in bones}
    identity = np.broadcast_to(np.array([0.0, 0, 0, 1]), (len(index), 4))
    for bone in UPPER_BODY:
        q = idle[0][bone]
        q = np.where((q * q[:1]).sum(-1, keepdims=True) < 0, -q, q)
        mean = q.mean(0) / np.linalg.norm(q.mean(0))
        sway = arc(identity, qmul(q[index], qinv(mean)), np.full(len(index), strength))
        out[bone] = qmul(sway, out.get(bone, identity))
    hips = np.array([h for _p, h in samples]) + np.array(skeleton["hips"]["world"])
    return out, hips


# --- moods: emotion-specific idle loops and small one-shots ----------------------------------
#
# Each mood loop is the captured idle re-timed and re-scaled (slower and smaller when sad,
# quicker and bigger when happy), with an authored arm pose and torso offset on top. They are
# drop-in replacements for the idle loop. Rhythmic extras use whole cycles per loop.


def retime(loop: Clip, factor: float) -> Clip:
    """The loop played ``factor`` times slower, resampled; it stays seamless."""

    rotations, hips = loop
    period = len(hips) - 1
    frames = round(period * factor)
    src = np.arange(frames + 1) * period / frames
    i0 = np.minimum(np.floor(src).astype(int), period - 1)
    u = src - i0
    out = {bone: slerp(q[i0], q[i0 + 1], u) for bone, q in rotations.items()}
    return out, hips[i0] + (hips[i0 + 1] - hips[i0]) * u[:, None]


def rescale(loop: Clip, amount: float) -> Clip:
    """Scale every bone's motion about its average pose: below 1 calmer, above 1 livelier."""

    rotations, hips = loop
    out = {}
    for bone, q in rotations.items():
        q = np.where((q * q[:1]).sum(-1, keepdims=True) < 0, -q, q)
        mean = np.broadcast_to(q.mean(0) / np.linalg.norm(q.mean(0)), q.shape)
        out[bone] = arc(mean, q, np.full(len(q), amount))
    centre = hips.mean(0)
    return out, centre + (hips - centre) * amount


def offset_pose(xbot: Path, name: str, skeleton: dict[str, Any]) -> Quats:
    """A Mixamo additive pose clip as per-bone offsets: its last frame against its first."""

    rotations, _hips = load_mixamo(xbot, name, skeleton)
    return {bone: qmul(q[-1], qinv(q[0])) for bone, q in rotations.items()}


def add_offsets(clip: Clip, offsets: Quats, bones: tuple[str, ...], amount: float) -> Clip:
    rotations, hips = clip
    out = dict(rotations)
    identity = np.array([0.0, 0, 0, 1])
    for bone in bones:
        scaled = arc(identity[None], offsets[bone][None], np.array([amount]))[0]
        out[bone] = qmul(np.broadcast_to(scaled, out[bone].shape), out[bone])
    return out, hips


def wobble(clip: Clip, bone: str, axis: str, degrees: np.ndarray) -> Clip:
    """Add a per-frame rotation about one axis (parent frame) to a bone."""

    rotations, hips = clip
    half = np.radians(degrees) / 2
    q = np.zeros((len(half), 4))
    q[:, "xyz".index(axis)] = np.sin(half)
    q[:, 3] = np.cos(half)
    return {**rotations, bone: qmul(q, rotations[bone])}, hips


def cycles(clip: Clip, count: int, phase: float = 0.0) -> np.ndarray:
    """A sine with a whole number of cycles over the loop, one value per frame."""

    frames = len(clip[1])
    return np.sin(2 * np.pi * count * np.arange(frames) / (frames - 1) + phase)


def always(_t: np.ndarray) -> np.ndarray:
    return np.ones_like(_t)


HANDS_BEHIND = {
    "leftUpperArm": [("x", 95), ("z", -80), ("x", 14)],
    "rightUpperArm": [("x", 95), ("z", 80), ("x", 14)],
    "leftLowerArm": [("y", -70)],
    "rightLowerArm": [("y", 70)],
    "leftHand": [("z", 0)],
    "rightHand": [("z", 0)],
}
HANDS_FRONT = {
    "leftUpperArm": [("x", 45), ("z", -80), ("x", -2)],
    "rightUpperArm": [("x", 45), ("z", 80), ("x", -2)],
    "leftLowerArm": [("y", -64)],
    "rightLowerArm": [("y", 64)],
    "leftHand": [("z", 10)],
    "rightHand": [("z", -10)],
}
ARMS_FOLDED = {
    "leftUpperArm": [("x", 70), ("z", -68), ("x", -28)],
    "rightUpperArm": [("x", 70), ("z", 68), ("x", -22)],
    "leftLowerArm": [("y", -118)],
    "rightLowerArm": [("y", 112)],
    "leftHand": [("z", 0)],
    "rightHand": [("z", 0)],
}
ARMS = (*LEFT_ARM, *RIGHT_ARM)  # with the shoulders, which the arm poses are measured from
SLUMP = ("spine", "chest", "upperChest", "neck", "head")


def mood_happy(motions: ModuleType, idle: Clip) -> tuple[Clip, Shapes]:
    """Quicker and bigger than the idle, chest up, hands behind the back, a small bounce."""

    clip = rescale(retime(idle, 0.85), 1.3)
    lift = on_stand(motions, spine=[("x", -2)], chest=[("x", -2)], head=[("x", -2)])
    clip = layer(motions, clip, lift, always, additive=("spine", "chest", "head"))
    clip = layer(motions, clip, HANDS_BEHIND, always, ARMS)
    clip = wobble(clip, "neck", "z", 4 * cycles(clip, 1))  # head sways side to side
    bounce = (1 - cycles(clip, 4, np.pi / 2)) / 2  # 0..1, four soft bounces per loop
    for side in ("left", "right"):
        clip = wobble(clip, f"{side}UpperLeg", "x", -4 * bounce)
        clip = wobble(clip, f"{side}LowerLeg", "x", 8 * bounce)
        clip = wobble(clip, f"{side}Foot", "x", -4 * bounce)
    rotations, hips = clip
    hips = hips.copy()
    hips[:, 1] -= 0.008 * bounce
    w = np.ones(len(hips))
    return (rotations, hips), {"left": held_shape(1.1, 0.6, w), "right": held_shape(1.1, 0.6, w)}


def mood_sad(motions: ModuleType, idle: Clip, slump: Quats) -> tuple[Clip, Shapes]:
    """Slower and smaller, head and shoulders down, hands held together low in front."""

    clip = rescale(retime(idle, 1.3), 0.6)
    clip = add_offsets(clip, slump, SLUMP, 0.3)
    clip = layer(motions, clip, HANDS_FRONT, always, ARMS)
    droop = on_stand(motions, leftShoulder=[("z", -3)], rightShoulder=[("z", 3)])
    clip = layer(motions, clip, droop, always, additive=("leftShoulder", "rightShoulder"))
    clip = wobble(clip, "chest", "x", -1.5 * cycles(clip, 1))  # one slow, deep breath per loop
    w = np.ones(len(clip[1]))
    return clip, {"left": held_shape(0.9, 0.3, w), "right": held_shape(0.9, 0.3, w)}


def mood_angry(motions: ModuleType, idle: Clip) -> tuple[Clip, Shapes]:
    """Arms folded, chin down, sharper shifts and an impatient tap of the left foot."""

    clip = rescale(retime(idle, 0.9), 1.1)
    chin = on_stand(motions, neck=[("x", 3)], head=[("x", 4)], spine=[("x", -1)])
    clip = layer(motions, clip, chin, always, additive=("neck", "head", "spine"))
    clip = layer(motions, clip, ARMS_FOLDED, always, ARMS)
    frames = len(clip[1])
    phase = np.arange(frames) / (frames - 1)
    taps = sum(np.exp(-(((phase - c) / 0.025) ** 2)) for c in (0.55, 0.64, 0.73))
    clip = wobble(clip, "leftFoot", "x", -10 * taps)  # toes lift and drop three times
    w = np.ones(frames)
    return clip, {"left": held_shape(1.5, 0.3, w), "right": held_shape(1.5, 0.3, w)}


def mood_relaxed(motions: ModuleType, idle: Clip) -> tuple[Clip, None]:
    """Slower, a little looser, shoulders down and the head resting at a tilt."""

    clip = rescale(retime(idle, 1.35), 1.15)
    loose = {
        "neck": [("z", 3)],
        "head": [("x", -1), ("z", 2)],
        "leftShoulder": [("z", -2)],
        "rightShoulder": [("z", 2)],
    }
    clip = layer(motions, clip, on_stand(motions, **loose), always, additive=tuple(loose))
    clip = wobble(clip, "head", "z", 2 * cycles(clip, 1, 1.0))
    return clip, None


CLAP_OPEN = {
    "leftUpperArm": [("x", 26), ("z", -72), ("x", -28)],
    "rightUpperArm": [("x", 26), ("z", 72), ("x", -28)],
    "leftLowerArm": [("x", -65), ("y", -95)],
    "rightLowerArm": [("x", -65), ("y", 95)],
    "leftHand": [("z", 0)],
    "rightHand": [("z", 0)],
}
CLAP_SHUT = {
    **CLAP_OPEN,
    "leftUpperArm": [("x", 40), ("z", -72), ("x", -28)],
    "rightUpperArm": [("x", 40), ("z", 72), ("x", -28)],
}
STRETCH = {
    "leftShoulder": [("z", 10)],
    "rightShoulder": [("z", -10)],
    "leftUpperArm": [("z", 72), ("x", -10)],
    "rightUpperArm": [("z", -72), ("x", -10)],
    "leftLowerArm": [("y", -50)],
    "rightLowerArm": [("y", 50)],
    "leftHand": [("z", 0)],
    "rightHand": [("z", 0)],
}
YAWN = {
    "rightShoulder": [("z", -5)],
    "rightUpperArm": [("x", 30), ("z", 90), ("x", -50)],
    "rightLowerArm": [("y", 150), ("z", -18)],
    "rightHand": [("z", 0), ("x", -10)],
}


def pulses(centres: tuple[float, ...], width: float) -> Weight:
    def weight(t: np.ndarray) -> np.ndarray:
        return np.minimum(1, sum(np.exp(-(((t - c) / width) ** 2)) for c in centres))

    return weight


def clap(motions: ModuleType, idle: Clip) -> tuple[Clip, Shapes]:
    """Hands up in front of the chest, three quick claps, a happy lift; back to the idle."""

    clip = idle_tail(idle, 2.2)
    lift = on_stand(motions, chest=[("x", -2)], head=[("x", -3)])
    clip = layer(motions, clip, lift, envelope((0.0, 0.3), (1.6, 2.0)), additive=("chest", "head"))
    ready = envelope((0.05, 0.4), (1.5, 1.95), 0.5)
    clip = layer(motions, clip, CLAP_OPEN, ready, ARMS)
    beats = pulses((0.6, 0.9, 1.2), 0.055)
    clip = layer(motions, clip, CLAP_SHUT, beats, ARMS, trail=False)
    w = ready(np.arange(len(clip[1])) / FPS)
    return clip, {"left": held_shape(0.4, 0.5, w), "right": held_shape(0.4, 0.5, w)}


def sigh(motions: ModuleType, idle: Clip) -> tuple[Clip, None]:
    """A breath in with the shoulders rising, then a long breath out that lets everything drop."""

    clip = idle_tail(idle, 3.0)
    inhale = on_stand(
        motions,
        leftShoulder=[("z", 5)],
        rightShoulder=[("z", -5)],
        chest=[("x", -3)],
        head=[("x", -3)],
    )
    exhale = on_stand(
        motions,
        leftShoulder=[("z", -3)],
        rightShoulder=[("z", 3)],
        spine=[("x", 4)],
        chest=[("x", 3)],
        neck=[("x", 4)],
        head=[("x", 6)],
    )
    bones = ("leftShoulder", "rightShoulder", "spine", "chest", "neck", "head")
    clip = layer(motions, clip, inhale, envelope((0.1, 1.0), (1.0, 1.6)), additive=bones)
    clip = layer(motions, clip, exhale, envelope((1.0, 1.8), (2.1, 2.75)), additive=bones)
    return clip, None


def stretch(motions: ModuleType, idle: Clip) -> tuple[Clip, Shapes]:
    """Both arms up overhead, leaning back with the face up, held a moment; back to the idle.
    The hands go well above the head, so the desktop framing needs headroom for it."""

    clip = idle_tail(idle, 3.6)
    arms = envelope((0.2, 1.1), (2.2, 3.25))
    back = on_stand(motions, spine=[("x", -5)], chest=[("x", -3)], head=[("x", -8)])
    clip = layer(motions, clip, back, arms, additive=("spine", "chest", "head"))
    clip = layer(motions, clip, STRETCH, arms, ARMS)
    w = arms(np.arange(len(clip[1])) / FPS)
    return clip, {"left": held_shape(0.3, 2.5, w), "right": held_shape(0.3, 2.5, w)}


def yawn(motions: ModuleType, idle: Clip) -> tuple[Clip, Shapes]:
    """Head tipping back with the shoulders up, the right hand covering the mouth.
    The face (mouth open, eyes shut) is the renderer's part."""

    clip = idle_tail(idle, 3.2)
    tip = on_stand(
        motions,
        neck=[("x", -3)],
        head=[("x", -8)],
        leftShoulder=[("z", 5)],
        rightShoulder=[("z", -5)],
    )
    bones = ("neck", "head", "leftShoulder", "rightShoulder")
    clip = layer(motions, clip, tip, envelope((0.2, 1.0), (2.2, 2.95)), additive=bones)
    hand = envelope((0.5, 1.1), (2.3, 2.95))
    clip = layer(motions, clip, YAWN, hand, tuple(YAWN))
    return clip, {"right": held_shape(0.7, 0.6, hand(np.arange(len(clip[1])) / FPS))}


# ---- Hands: none of the sources capture fingers, so they get their own layer ----

# Hand shapes as (curl, spread) for build_vrm_motions.hands(): relaxed and slightly cupped,
# open with the fingers fanned (a raised, waving hand), and flat with the fingers together.
RELAXED, OPEN, FLAT = (1.0, 1.0), (0.3, 3.5), (0.35, -0.4)
FINGER_LAG = 0.12  # seconds; fingers settle a beat after the arm


def smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - edge0) / (edge1 - edge0), 0, 1)
    return t * t * (3 - 2 * t)


def world_rotations(rotations: Quats, skeleton: dict[str, Any], bone: str) -> np.ndarray:
    chain = []
    while bone:
        chain.append(bone)
        bone = skeleton[bone]["parent"]
    frames = len(next(iter(rotations.values())))
    world = np.broadcast_to(np.eye(3), (frames, 3, 3))
    for name in reversed(chain):
        if name in rotations:
            world = world @ to_matrix(rotations[name])
    return world


def lagged(weight: np.ndarray, loop: bool) -> np.ndarray:
    """One-pole low-pass, so the hand shape trails the arm instead of snapping with it."""

    alpha = 1 - np.exp(-1 / (FPS * FINGER_LAG))
    out = np.empty_like(weight)
    value = weight[-1] if loop else weight[0]
    for i, w in enumerate(weight):
        value += (w - value) * alpha
        out[i] = value
    return out


def hand_weights(clip: Clip, skeleton: dict[str, Any], loop: bool) -> dict[str, np.ndarray]:
    """Per side, per frame: how open (hand raised) and how flat (bowing) the hand should be."""

    rotations, _hips = clip
    lean = world_rotations(rotations, skeleton, "upperChest")[:, 1, 1]  # cos of forward tilt
    flat = smoothstep(np.cos(np.radians(10)), np.cos(np.radians(30)), lean)
    out = {}
    for side, out_axis in (("left", 1.0), ("right", -1.0)):
        upper = world_rotations(rotations, skeleton, f"{side}UpperArm")
        lower = world_rotations(rotations, skeleton, f"{side}LowerArm")
        axis = np.array([out_axis, 0, 0])
        rise = 0.26 * (upper @ axis)[:, 1] + 0.24 * (lower @ axis)[:, 1]  # wrist above shoulder
        raised = smoothstep(-0.32, -0.02, rise)
        out[side] = np.stack([lagged(raised, loop), lagged(flat, loop)], -1)
    return out


def auto_shape(raised: float, flat: float) -> tuple[float, float, float]:
    """(curl, spread, drift amount) from how raised and how flat the hand should be."""

    curl = RELAXED[0] + (OPEN[0] - RELAXED[0]) * raised
    spread = RELAXED[1] + (OPEN[1] - RELAXED[1]) * raised
    curl += (FLAT[0] - curl) * flat * (1 - raised)
    spread += (FLAT[1] - spread) * flat * (1 - raised)
    return curl, spread, 1 - 0.6 * max(raised, flat)


def finger_pose(
    motions: ModuleType, side: str, curl: float, spread: float, calm: float, t: float, period: float
) -> dict[str, list[tuple[str, object]]]:
    """The hand shape, plus a slow, small curl drift per finger so hands never freeze."""

    shape = motions.hands(curl, spread)
    # the thumb stays tucked alongside the palm; a fully opened thumb splays out like a claw
    shape.update({b: r for b, r in motions.hands(max(curl, 0.75), spread).items() if "Thumb" in b})
    phase = 0.0 if side == "left" else 1.7
    out: dict[str, list[tuple[str, object]]] = {}
    for bone, rotations in shape.items():
        if not bone.startswith(side):
            continue
        finger = next((i for i, f in enumerate((*motions.FINGERS, "Thumb")) if f in bone), 0)
        # whole cycles per clip keep loops seamless; amplitude fades on open/flat hands
        cycles = max(1, round(period / (3.5 + 0.9 * finger)))
        drift = np.sin(2 * np.pi * cycles * t / period + phase + 1.3 * finger)
        drift_deg = (2.5 + 0.8 * finger) * drift * calm
        sign = -1 if side == "left" else 1
        bent = [
            (axis, value + sign * drift_deg if axis == "z" else value) for axis, value in rotations
        ]
        out[bone] = bent  # type: ignore[assignment]
    return out


def encode(
    motions: ModuleType,
    skeleton: dict[str, Any],
    clip: Clip,
    loop: bool,
    shapes: Shapes | None = None,
) -> bytes:
    """``shapes`` overrides the automatic hand shape where a layered gesture holds its own."""

    rotations, hips = clip
    rest = np.array(skeleton["hips"]["world"])
    frames = len(hips)
    period = (frames - 1) / FPS
    weights = hand_weights(clip, skeleton, loop)

    def sample(t: float) -> tuple[dict[str, list[tuple[str, object]]], tuple[float, ...]]:
        f = min(frames - 1, round(t * FPS))
        pose: dict[str, list[tuple[str, object]]] = {}
        for side, w in weights.items():
            curl, spread, calm = auto_shape(float(w[f, 0]), float(w[f, 1]))
            if shapes and side in shapes:
                held_curl, held_spread, k = (float(x) for x in shapes[side][f])
                curl, spread = curl + (held_curl - curl) * k, spread + (held_spread - spread) * k
                calm += (0.5 - calm) * k
            pose.update(finger_pose(motions, side, curl, spread, calm, t, period))
        for bone, q in rotations.items():
            pose[bone] = [("q", tuple(float(x) for x in q[f]))]
        return pose, tuple(float(x) for x in hips[f] - rest)

    return bytes(motions.build_vrma(skeleton, sample, (frames - 1) / FPS, loop))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=PACK)
    parser.add_argument("--cache", type=Path, default=CACHE)
    args = parser.parse_args()
    skeleton = json.loads((args.out / "skeleton.json").read_text(encoding="utf-8"))
    motions = load_motions()
    pack = json.loads((args.out / "pack.json").read_text(encoding="utf-8"))
    entries = {entry["activity"]: entry for entry in pack["activities"]}
    for name, (clip, shapes) in build_clips(args.cache, skeleton, motions).items():
        description, loop = MOCAP[name]
        data = encode(motions, skeleton, clip, loop, shapes)
        (args.out / f"{name}.vrma").write_bytes(data)
        bandai = name in {"wave", "bow", "bye"}
        entries[name] = {
            "activity": name,
            "file": f"{name}.vrma",
            "sha256": hashlib.sha256(data).hexdigest(),
            "duration": (len(clip[1]) - 1) / FPS,
            "loop": loop,
            "description": description,
            "entry_pose": "seated" if name in SEATED else "stand",
            "exit_pose": "seated" if name in SEATED else "stand",
            "root_motion": "none (hips height only; desktop window owns travel)",
            "ground_contact": "seat_edge_and_feet" if name in SEATED else "feet",
            "interrupt": "any_frame",
            "crossfade_seconds": 0.3,
            "source": "mocap_layered" if name in LAYERED else "mocap",
            "license": BANDAI_LICENSE if bandai else MIXAMO_LICENSE,
            "attribution": BANDAI_CREDIT if bandai else MIXAMO_CREDIT,
        }
    pack["activities"] = list(entries.values())
    pack["mocap_source"] = "scripts/build_vrm_mocap.py"
    (args.out / "pack.json").write_text(
        json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(MOCAP)} motion-capture activities to {args.out}")


if __name__ == "__main__":
    main()
