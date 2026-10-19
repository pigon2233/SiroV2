"""Retarget motion-capture clips onto SIRO's VRM skeleton and add them to the activity pack.

Hand-keyed clips (``build_vrm_motions.py``) read as stiff, so the everyday gestures come from
real motion capture instead. Sources are fetched on demand into a cache outside the repository,
pinned by sha256; only the retargeted ``.vrma`` clips are committed.

- Bandai Namco Research Motion Dataset (CC BY-NC 4.0, non-commercial use only):
  wave, bow and bye.
- Mixamo animations shipped with the three.js examples (``Xbot.glb``, three.js r169): idle,
  nod and head shake.

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


# --- pack -----------------------------------------------------------------------------------

MOCAP = {
    "idle": ("Mixamo idle, mirrored and joined into a 5 s weight-shifting loop.", True),
    "nod": ("Mixamo agree: a few natural nods; returns to the stand pose.", False),
    "shake": ("Mixamo head shake (no); returns to the stand pose.", False),
    "wave": ("Captured right-hand wave, trimmed to two sweeps; returns to the stand pose.", False),
    "bow": ("Captured polite bow with hands together; returns to the stand pose.", False),
    "bye": ("Captured small hand-by-the-face hello/bye; returns to the stand pose.", False),
}


def build_clips(cache: Path, skeleton: dict[str, Any]) -> dict[str, Clip]:
    xbot = fetch("Xbot.glb", cache)

    def mixamo(name: str) -> Clip:
        rotations, hips = load_mixamo(xbot, name, skeleton)
        return in_place((open_arms(narrow_stance(rotations), 4), hips))

    def bvh(name: str) -> Clip:
        return in_place(load_bvh(fetch(f"{name}.bvh", cache), skeleton))

    idle = mixamo("idle")
    wave = bvh("dataset-2_wave-right-hand_normal_001")
    return {
        "idle": close_loop(join(idle, mirror(idle))),
        "nod": mixamo("agree"),
        "shake": mixamo("headShake"),
        # raise and one and a half sweeps, then the matching sweep before the arm comes down
        "wave": join(cut(wave, 0, 65), cut(wave, 136)),
        "bow": bvh("dataset-1_bow_normal_001"),
        "bye": bvh("dataset-1_bye_normal_001"),
    }


def encode(motions: ModuleType, skeleton: dict[str, Any], clip: Clip, loop: bool) -> bytes:
    rotations, hips = clip
    fingers = motions.hands()
    rest = np.array(skeleton["hips"]["world"])
    frames = len(hips)

    def sample(t: float) -> tuple[dict[str, list[tuple[str, object]]], tuple[float, ...]]:
        f = min(frames - 1, round(t * FPS))
        pose: dict[str, list[tuple[str, object]]] = {b: list(r) for b, r in fingers.items()}
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
    for name, clip in build_clips(args.cache, skeleton).items():
        description, loop = MOCAP[name]
        data = encode(motions, skeleton, clip, loop)
        (args.out / f"{name}.vrma").write_bytes(data)
        bandai = name in {"wave", "bow", "bye"}
        entries[name] = {
            "activity": name,
            "file": f"{name}.vrma",
            "sha256": hashlib.sha256(data).hexdigest(),
            "duration": (len(clip[1]) - 1) / FPS,
            "loop": loop,
            "description": description,
            "entry_pose": "stand",
            "exit_pose": "stand",
            "root_motion": "none (hips height only; desktop window owns travel)",
            "ground_contact": "feet",
            "interrupt": "any_frame",
            "crossfade_seconds": 0.3,
            "source": "mocap",
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
