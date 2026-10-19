"""Build the SIRO VRM activity pack (.vrma clips + pack.json) from authored keyframes.

The keyframes below are the editable source. Each pose maps a VRM humanoid bone to a list of
``(axis, degrees)`` rotations on the normalized bone, applied in order in the parent frame.
VRM 1.0 normalized bones have an identity rest (T-pose) and the model faces +Z, with +X on
the character's left, so: arm down is ``("z", -70)`` for the left arm and ``+70`` for the
right; leg forward and nod down are ``("x", -deg)`` and ``("x", +deg)`` respectively.

Output: ``assets/companion/siro-vrm/<version>/`` with one ``.vrma`` per activity and a
``siro.visual.pack.v0`` manifest. The rest skeleton comes from ``skeleton.json`` in that folder
(bone positions only, measured from the owner model with three-vrm).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
PACK = ROOT / "assets" / "companion" / "siro-vrm" / VERSION
FPS = 30

# ("x" | "y" | "z", degrees), or ("q", quaternion) for an already blended rotation.
Rotations = list[tuple[str, object]]
Pose = dict[str, Rotations]
Quat = tuple[float, float, float, float]


def axis_quat(axis: str, degrees: float) -> Quat:
    half = math.radians(degrees) / 2
    s, c = math.sin(half), math.cos(half)
    return {"x": (s, 0.0, 0.0, c), "y": (0.0, s, 0.0, c), "z": (0.0, 0.0, s, c)}[axis]


def mul(a: Quat, b: Quat) -> Quat:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def compose(rotations: Rotations) -> Quat:
    q: Quat = (0.0, 0.0, 0.0, 1.0)
    for axis, value in rotations:
        q = mul(value if axis == "q" else axis_quat(axis, value), q)  # type: ignore[arg-type]
    return q


def slerp(a: Quat, b: Quat, t: float) -> Quat:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    if dot < 0:
        b, dot = (-b[0], -b[1], -b[2], -b[3]), -dot
    if dot > 0.9995:
        q = tuple(x + (y - x) * t for x, y in zip(a, b, strict=True))
    else:
        theta = math.acos(dot)
        wa, wb = math.sin((1 - t) * theta) / math.sin(theta), math.sin(t * theta) / math.sin(theta)
        q = tuple(wa * x + wb * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in q))
    return (q[0] / norm, q[1] / norm, q[2] / norm, q[3] / norm)


def smooth(t: float) -> float:
    return t * t * (3 - 2 * t)


def ease_in_out(t: float) -> float:
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_back(t: float, overshoot: float = 1.4) -> float:
    """Arrives slightly past the key and settles back: reads as weight, not a robot stop."""

    u = t - 1
    return 1 + (overshoot + 1) * u**3 + overshoot * u**2


EASES: dict[str, Callable[[float], float]] = {
    "smooth": smooth,
    "in_out": ease_in_out,
    "back": ease_out_back,
    "linear": lambda t: t,
}


def wave(t: float, period: float, phase: float = 0.0) -> float:
    return math.sin(2 * math.pi * t / period + phase)


def mirror(rotations: Rotations) -> Rotations:
    """Left-to-right copy: y and z rotations flip sign across the sagittal plane."""

    return [(axis, value if axis in {"x", "q"} else -value) for axis, value in rotations]  # type: ignore[operator]


FINGERS = ("Index", "Middle", "Ring", "Little")


def hands(curl: float = 1.0, spread: float = 1.0) -> Pose:
    """Relaxed, slightly cupped hands; flat VRoid fingers are the main source of stiffness."""

    out: Pose = {}
    for i, finger in enumerate(FINGERS):
        base = (12 + 6 * i) * curl
        for j, joint in enumerate(("Proximal", "Intermediate", "Distal")):
            amount = base * (1.25, 1.1, 0.7)[j]
            rotations: Rotations = [("z", -amount)]
            if j == 0:
                rotations.append(("y", (4 - 3 * i) * spread))
            out[f"left{finger}{joint}"] = rotations
            out[f"right{finger}{joint}"] = mirror(rotations)
    for joint, (y, z) in {
        "Metacarpal": (-12, -4),
        "Proximal": (-10, -6),
        "Distal": (-8, -10),
    }.items():
        out[f"leftThumb{joint}"] = [("y", y * curl), ("z", z * curl)]
        out[f"rightThumb{joint}"] = mirror(out[f"leftThumb{joint}"])
    return out


# Relaxed contrapposto: weight on the right leg, left knee eased, shoulders countering the hips.
STAND: Pose = {
    **hands(),
    "hips": [("z", 2.0), ("y", -3.0)],
    "spine": [("z", -1.5), ("y", 1.5)],
    "chest": [("z", -1.0)],
    "neck": [("z", 1.5)],
    "leftUpperLeg": [("x", -3.0), ("z", 1.0)],
    "leftLowerLeg": [("x", 7.0)],
    "leftFoot": [("x", -3.0)],
    "rightUpperLeg": [("x", 1.0), ("z", 1.5)],
    "leftShoulder": [("z", 1.0)],
    "rightShoulder": [("z", -2.0)],
    "leftUpperArm": [("z", -68), ("x", 5)],
    "rightUpperArm": [("z", 71), ("x", -2)],
    "leftLowerArm": [("y", -16), ("z", 0)],
    "rightLowerArm": [("y", 11), ("z", 0)],
    "leftHand": [("z", -8), ("x", 6)],
    "rightHand": [("z", 6), ("x", 4)],
}


def pose(**changes: Rotations) -> Pose:
    merged = {bone: list(rotations) for bone, rotations in STAND.items()}
    merged.update(changes)
    return merged


def add(base: Pose, **extra: Rotations) -> Pose:
    """Layer extra rotations on top of a pose (applied after the base rotation)."""

    out = {bone: list(rotations) for bone, rotations in base.items()}
    for bone, rotations in extra.items():
        out[bone] = out.get(bone, []) + list(rotations)
    return out


def blend(a: Pose, b: Pose, t: float) -> Pose:
    return {
        bone: [("q", slerp(compose(a.get(bone, [])), compose(b.get(bone, [])), t))]
        for bone in {*a, *b}
    }


Offset = tuple[float, float, float]
Frame = tuple[Pose, Offset]
Sampler = Callable[[float], Frame]


def keyframes(
    times: list[float],
    poses: list[Pose],
    hips: list[Offset] | None = None,
    eases: list[str] | None = None,
    life: Callable[[float], Pose] | None = None,
) -> Sampler:
    """Eased segments between authored keys; ``hips`` are offsets from rest in metres.

    ``life`` layers a small continuous motion (breathing) over the whole clip so held keys
    never freeze.
    """

    offsets = hips or [(0.0, 0.0, 0.0)] * len(times)
    curves = eases or ["in_out"] * (len(times) - 1)

    def sample(t: float) -> Frame:
        segment = len(times) - 2
        for i in range(len(times) - 1):
            if t <= times[i + 1]:
                segment = i
                break
        span = times[segment + 1] - times[segment]
        raw = min(1.0, max(0.0, (t - times[segment]) / span))
        u = EASES[curves[segment]](raw)
        h = tuple(
            a + (b - a) * u for a, b in zip(offsets[segment], offsets[segment + 1], strict=True)
        )
        p = blend(poses[segment], poses[segment + 1], u)
        if life is not None:
            for bone, rotations in life(t).items():
                p[bone] = p.get(bone, []) + rotations
        return p, h  # type: ignore[return-value]

    return sample


def breathing(t: float, period: float = 4.0, depth: float = 1.0) -> Pose:
    b = wave(t, period)
    return {
        "spine": [("x", 0.8 * b * depth)],
        "chest": [("x", 0.9 * b * depth)],
        "leftShoulder": [("z", 0.8 * b * depth)],
        "rightShoulder": [("z", -0.8 * b * depth)],
        "neck": [("x", -0.5 * b * depth)],
    }


def idle(t: float) -> Frame:
    # 8 s loop; every term is a harmonic of 8 s so the loop is seamless, but the mix of
    # periods (8, 4, 8/3, 8/5) keeps it from reading as one mechanical sway.
    sway = wave(t, 8)
    p = add(
        STAND,
        hips=[("z", 1.6 * sway), ("y", 1.5 * wave(t, 8, 1.2))],
        spine=[("z", -1.2 * sway), ("y", -1.0 * wave(t, 8, 1.2))],
        chest=[("y", 0.8 * wave(t, 8 / 3, 0.4))],
        neck=[
            ("y", 3.5 * wave(t, 8, 2.2) + 1.2 * wave(t, 8 / 5, 0.7)),
            ("x", 1.2 * wave(t, 8 / 3, 1.9)),
        ],
        head=[("z", 1.5 * wave(t, 8, 3.1)), ("x", 0.8 * wave(t, 8 / 5, 2.5))],
        leftUpperLeg=[("x", -1.5 * sway)],
        leftLowerLeg=[("x", 3.0 * max(0.0, sway))],
        leftUpperArm=[("z", 1.2 * wave(t, 4, 0.6)), ("x", 1.5 * wave(t, 8, 2.0))],
        rightUpperArm=[("z", -1.0 * wave(t, 4, 0.9)), ("x", -1.2 * wave(t, 8, 2.6))],
        leftLowerArm=[("y", -2.0 * wave(t, 8 / 3, 0.2))],
        rightLowerArm=[("y", 1.5 * wave(t, 8 / 3, 1.4))],
        leftHand=[("z", -2.0 * wave(t, 8 / 3, 0.8))],
        rightHand=[("z", 2.0 * wave(t, 8 / 3, 2.1))],
    )
    for bone, rotations in breathing(t).items():
        p[bone] = p[bone] + rotations if bone in p else rotations
    return p, (0.012 * sway, 0.002 * wave(t, 4), 0.0)


def walk(t: float) -> Frame:
    # 1 s cycle; phase 0 = left heel strike. Knee flexes ~12 deg in stance and ~55 deg in swing.
    def leg(phase: float) -> tuple[float, float, float]:
        ph = phase % 1.0
        thigh = -22 * math.cos(2 * math.pi * ph)  # forward at strike, back at toe-off
        if ph < 0.6:  # stance
            knee = 12 * math.sin(math.pi * ph / 0.6) + 3
            foot = -10 * (1 - ph / 0.15) if ph < 0.15 else 14 * max(0.0, (ph - 0.45) / 0.15)
        else:  # swing
            knee = 55 * math.sin(math.pi * (ph - 0.6) / 0.4) + 3
            foot = -6 * math.sin(math.pi * (ph - 0.6) / 0.4)
        return thigh, knee, foot

    lt, lk, lf = leg(t)
    rt, rk, rf = leg(t + 0.5)
    s = wave(t, 1.0)
    p = pose(
        **hands(curl=0.9),
        hips=[("y", 6 * s), ("z", -3 * wave(t, 1.0, math.pi / 2))],
        spine=[("x", 4), ("y", -4 * s)],
        chest=[("y", -3 * s)],
        neck=[("y", 0.8 * s), ("x", -2)],
        head=[("z", 1.5 * wave(t, 1.0, math.pi / 2))],
        leftUpperLeg=[("x", lt)],
        rightUpperLeg=[("x", rt)],
        leftLowerLeg=[("x", lk)],
        rightLowerLeg=[("x", rk)],
        leftFoot=[("x", lf)],
        rightFoot=[("x", rf)],
        leftUpperArm=[("z", -72), ("x", -18 * math.cos(2 * math.pi * (t + 0.5)))],
        rightUpperArm=[("z", 72), ("x", -18 * math.cos(2 * math.pi * t))],
        leftLowerArm=[("y", -18 - 14 * max(0.0, -math.cos(2 * math.pi * t))), ("z", 0)],
        rightLowerArm=[("y", 18 + 14 * max(0.0, math.cos(2 * math.pi * t))), ("z", 0)],
    )
    bob = 0.022 * (0.5 - 0.5 * math.cos(4 * math.pi * t)) - 0.022
    return p, (0.012 * wave(t, 1.0, math.pi / 2), bob, 0.0)


SIT: Pose = pose(
    **hands(curl=1.2),
    hips=[("x", 0)],
    spine=[("x", 8), ("z", 0)],
    chest=[("x", 2)],
    neck=[("x", 4), ("z", 3)],
    leftUpperLeg=[("x", -86), ("z", -5)],
    rightUpperLeg=[("x", -88), ("z", 3)],
    leftLowerLeg=[("x", 80)],
    rightLowerLeg=[("x", 88)],
    leftFoot=[("x", 8)],
    rightFoot=[("x", 2)],
    leftShoulder=[("z", -2)],
    rightShoulder=[("z", 2)],
    # Hands resting on the thighs (solved numerically against the measured skeleton).
    leftUpperArm=[("z", -77), ("x", -27)],
    rightUpperArm=[("z", 75), ("x", -29)],
    leftLowerArm=[("y", -17), ("z", -38)],
    rightLowerArm=[("y", 13), ("z", 41)],
    leftHand=[("z", -4), ("x", 10)],
    rightHand=[("z", 4), ("x", 10)],
)
# Seat height puts the thighs level with the feet resting on the floor.
SIT_DROP = -0.40
# Hips settle back onto the seat edge behind the heels.
SIT_BACK = -0.12
# Leaning forward over the knees is what lets a person sit down and stand up.
LEAN = add(blend(STAND, SIT, 0.7), spine=[("x", 22)], chest=[("x", 6)], neck=[("x", -14)])
# Hip drop that keeps the feet on the floor with LEAN's bent knees (thigh and shin lengths).
LEAN_DROP = -0.18


def sit_loop(t: float) -> Frame:
    p = add(
        SIT,
        neck=[("y", 5 * wave(t, 8, 0.5)), ("x", 1.5 * wave(t, 8 / 3, 1.0))],
        head=[("z", 2 * wave(t, 8, 2.0))],
        # idle foot swing, out of phase between the legs
        leftLowerLeg=[("x", 6 * wave(t, 8 / 3))],
        rightLowerLeg=[("x", 5 * wave(t, 8 / 3, 2.4))],
    )
    for bone, rotations in breathing(t).items():
        p[bone] = p[bone] + rotations
    return p, (0.0, SIT_DROP + 0.002 * wave(t, 4), SIT_BACK)


WAVE_UP = pose(
    **hands(curl=0.25, spread=2.0),
    rightUpperArm=[("z", -10), ("x", -14)],
    rightLowerArm=[("y", 4), ("z", -88)],
    rightHand=[("z", 0), ("x", -6)],
    rightShoulder=[("z", -6)],
    spine=[("z", 3), ("y", 4)],
    chest=[("z", 2)],
    neck=[("z", -6), ("y", -4)],
    hips=[("z", -1.5), ("y", 3)],
)
WAVE_READY = blend(STAND, WAVE_UP, 0.15)


def wave_frame(t: float) -> Frame:
    if t < 0.15:  # small anticipation dip
        return blend(STAND, WAVE_READY, smooth(t / 0.15)), (0.0, -0.004 * smooth(t / 0.15), 0.0)
    if t < 0.6:
        return blend(WAVE_READY, WAVE_UP, ease_out_back((t - 0.15) / 0.45, 1.2)), (0.0, -0.004, 0.0)
    if t < 2.0:
        # forearm and wrist swing out of phase so the hand flicks instead of pivoting rigidly
        ph = 2 * math.pi * (t - 0.6) / 0.62
        fade = min(1.0, (t - 0.6) / 0.15) * min(1.0, (2.0 - t) / 0.2)
        p = add(
            WAVE_UP,
            rightLowerArm=[("z", 20 * math.sin(ph) * fade)],
            rightHand=[("z", 16 * math.sin(ph - 1.0) * fade)],
            neck=[("z", 1.5 * math.sin(ph) * fade)],
        )
        return p, (0.0, -0.004, 0.0)
    u = ease_in_out(min(1.0, (t - 2.0) / 0.55))
    return blend(WAVE_UP, STAND, u), (0.0, -0.004 * (1 - u), 0.0)


THINK = pose(
    **hands(curl=1.1),
    neck=[("x", -5), ("z", 8)],
    head=[("x", -3)],
    spine=[("y", -5), ("z", -2)],
    hips=[("z", 3), ("y", -5)],
    leftUpperLeg=[("x", -5), ("z", 2)],
    leftLowerLeg=[("x", 10)],
    # Hand raised to the cheek; angles solved numerically against the measured skeleton.
    rightUpperArm=[("x", 30), ("z", 90), ("x", -38)],
    rightLowerArm=[("y", 138), ("z", -18)],
    rightHand=[("z", 0), ("x", -10)],
    # the free arm folds across the waist to support the raised elbow
    leftUpperArm=[("z", -74), ("x", -22)],
    leftLowerArm=[("y", -70), ("z", -10)],
)


def think_life(t: float) -> Pose:
    return breathing(t) | {
        "head": [("z", 2 * wave(t, 1.5))],
        "rightHand": [("x", 4 * wave(t, 0.9))],
    }


ATTENTION = pose(
    **hands(curl=0.8),
    spine=[("x", -3)],
    chest=[("x", -3)],
    neck=[("x", -4)],
    head=[("x", -2)],
    hips=[("z", 0.5), ("y", -1)],
    leftUpperLeg=[("x", -1), ("z", 1)],
    leftLowerLeg=[("x", 3)],
    leftShoulder=[("z", 2.5)],
    rightShoulder=[("z", -3.5)],
)
NOD_UP = add(STAND, neck=[("x", -4)], head=[("x", -2)])
NOD_DOWN = add(STAND, neck=[("x", 14)], head=[("x", 5)], spine=[("x", 2.5)], chest=[("x", 1.5)])
NOD_REBOUND = add(STAND, neck=[("x", -2)])


ACTIVITIES: dict[str, dict[str, object]] = {
    "idle": {"duration": 8.0, "loop": True, "sample": idle},
    "attention": {
        "duration": 0.7,
        "loop": False,
        "sample": keyframes([0, 0.7], [STAND, ATTENTION], eases=["back"], life=breathing),
    },
    "nod": {
        "duration": 0.9,
        "loop": False,
        "sample": keyframes(
            [0, 0.12, 0.38, 0.62, 0.9],
            [STAND, NOD_UP, NOD_DOWN, NOD_REBOUND, STAND],
            eases=["in_out", "in_out", "in_out", "smooth"],
        ),
    },
    "wave": {"duration": 2.6, "loop": False, "sample": wave_frame},
    "think": {
        "duration": 3.4,
        "loop": False,
        "sample": keyframes(
            [0, 0.7, 2.7, 3.4],
            [STAND, THINK, THINK, STAND],
            eases=["back", "linear", "in_out"],
            life=think_life,
        ),
    },
    "walk": {"duration": 1.0, "loop": True, "sample": walk},
    "sit_down": {
        "duration": 1.4,
        "loop": False,
        "sample": keyframes(
            [0, 0.55, 1.4],
            [STAND, LEAN, SIT],
            [(0, 0, 0), (0, LEAN_DROP, SIT_BACK * 0.3), (0, SIT_DROP, SIT_BACK)],
            eases=["in_out", "back"],
        ),
    },
    "sit_loop": {"duration": 8.0, "loop": True, "sample": sit_loop},
    "stand_up": {
        "duration": 1.3,
        "loop": False,
        "sample": keyframes(
            [0, 0.5, 1.3],
            [SIT, LEAN, STAND],
            [(0, SIT_DROP, SIT_BACK), (0, LEAN_DROP, SIT_BACK * 0.3), (0, 0, 0)],
            eases=["in_out", "back"],
        ),
    },
}

DESCRIPTIONS = {
    "idle": "Contrapposto breathing with layered sway, weight shift and head drift; 8 s loop.",
    "attention": "Perks up toward the viewer with a small overshoot; holds the last frame.",
    "nod": "Anticipation, nod, rebound, settle; returns to the stand pose.",
    "wave": "Right-hand wave with anticipation and a wrist flick; returns to the stand pose.",
    "think": "Hand to cheek, free arm across the waist, head tilt; returns to the stand pose.",
    "walk": "In-place gait: heel strike, toe-off, hip roll; the window moves, not the clip.",
    "sit_down": "Leans over the knees and settles onto an edge, feet on the floor.",
    "sit_loop": "Seated breathing, head drift and an idle foot swing; loops until stand_up.",
    "stand_up": "Leans forward and rises back to the stand pose.",
}

# Overlapping action: children trail their parents by these delays (seconds), so a motion
# rolls up the spine and out along the arm instead of every joint moving in lockstep.
DELAYS = {
    "chest": 0.03,
    "upperChest": 0.05,
    "neck": 0.08,
    "head": 0.12,
    "Shoulder": 0.04,
    "UpperArm": 0.07,
    "LowerArm": 0.12,
    "Hand": 0.17,
    "Proximal": 0.2,
    "Intermediate": 0.22,
    "Distal": 0.24,
    "Metacarpal": 0.2,
}


def delay(bone: str) -> float:
    for key, value in DELAYS.items():
        if bone == key or bone.endswith(key):
            return value
    return 0.0


def build_vrma(
    skeleton: dict[str, dict[str, object]], sample: Sampler, duration: float, loop: bool
) -> bytes:
    bones = list(skeleton)
    index = {bone: i for i, bone in enumerate(bones)}
    world = {bone: skeleton[bone]["world"] for bone in bones}
    nodes: list[dict[str, object]] = []
    for bone in bones:
        parent = skeleton[bone]["parent"]
        base = world[parent] if parent else [0.0, 0.0, 0.0]
        node: dict[str, object] = {
            "name": bone,
            "translation": [w - b for w, b in zip(world[bone], base, strict=True)],
        }
        children = [index[c] for c in bones if skeleton[c]["parent"] == bone]
        if children:
            node["children"] = children
        nodes.append(node)
    frames = round(duration * FPS)
    # A loop's last frame equals its first; one-shots end exactly on their final pose.
    times = [i / FPS for i in range(frames + 1)]

    def at(t: float, lag: float) -> float:
        if loop:
            return (t - lag) % duration
        # One-shots keep their first and last frames exact; the lag peaks mid-clip.
        return min(duration, max(0.0, t - lag * math.sin(math.pi * min(1.0, t / duration))))

    samples = [sample(at(t, 0.0)) for t in times]
    animated = sorted({bone for p, _h in samples for bone in p} & set(bones))
    cache: dict[float, Pose] = {}

    def rotation(bone: str, t: float) -> Quat:
        key = round(at(t, delay(bone)), 6)
        if key not in cache:
            cache[key] = sample(key)[0]
        return compose(cache[key].get(bone, []))

    blob = bytearray()
    accessors: list[dict[str, object]] = []
    views: list[dict[str, object]] = []

    def add(values: list[float], kind: str, count: int, bounds: bool = False) -> int:
        offset = len(blob)
        blob.extend(struct.pack(f"<{len(values)}f", *values))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(values) * 4})
        accessor: dict[str, object] = {
            "bufferView": len(views) - 1,
            "componentType": 5126,
            "count": count,
            "type": kind,
        }
        if bounds:
            accessor["min"], accessor["max"] = [min(values)], [max(values)]
        accessors.append(accessor)
        return len(accessors) - 1

    time_accessor = add(times, "SCALAR", len(times), bounds=True)
    samplers: list[dict[str, object]] = []
    channels: list[dict[str, object]] = []
    for bone in animated:
        values: list[float] = []
        previous: Quat | None = None
        for t in times:
            q = rotation(bone, t)
            if previous and sum(a * b for a, b in zip(q, previous, strict=True)) < 0:
                q = (-q[0], -q[1], -q[2], -q[3])  # keep the shortest path between keys
            values.extend(q)
            previous = q
        samplers.append({"input": time_accessor, "output": add(values, "VEC4", len(times))})
        channels.append(
            {"sampler": len(samplers) - 1, "target": {"node": index[bone], "path": "rotation"}}
        )
    hips_rest = world["hips"]
    hips_values = [
        v
        for _p, h in samples
        for v in (hips_rest[0] + h[0], hips_rest[1] + h[1], hips_rest[2] + h[2])
    ]
    samplers.append({"input": time_accessor, "output": add(hips_values, "VEC3", len(times))})
    channels.append(
        {"sampler": len(samplers) - 1, "target": {"node": index["hips"], "path": "translation"}}
    )

    document = {
        "asset": {"version": "2.0", "generator": "SIRO scripts/build_vrm_motions.py"},
        "extensionsUsed": ["VRMC_vrm_animation"],
        "extensions": {
            "VRMC_vrm_animation": {
                "specVersion": "1.0",
                "humanoid": {"humanBones": {bone: {"node": index[bone]} for bone in bones}},
            }
        },
        "scene": 0,
        "scenes": [{"nodes": [index["hips"]]}],
        "nodes": nodes,
        "animations": [{"name": "siro", "samplers": samplers, "channels": channels}],
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(blob)}],
    }
    payload = json.dumps(document, separators=(",", ":")).encode()
    payload += b" " * (-len(payload) % 4)
    blob.extend(b"\0" * (-len(blob) % 4))
    total = 12 + 8 + len(payload) + 8 + len(blob)
    return (
        struct.pack("<4sII", b"glTF", 2, total)
        + struct.pack("<II", len(payload), 0x4E4F534A)
        + payload
        + struct.pack("<II", len(blob), 0x004E4942)
        + bytes(blob)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=PACK)
    args = parser.parse_args()
    skeleton = json.loads((args.out / "skeleton.json").read_text(encoding="utf-8"))
    activities = []
    for name, spec in ACTIVITIES.items():
        duration, loop = float(spec["duration"]), bool(spec["loop"])  # type: ignore[arg-type]
        data = build_vrma(skeleton, spec["sample"], duration, loop)  # type: ignore[arg-type]
        path = args.out / f"{name}.vrma"
        path.write_bytes(data)
        seated = name in {"sit_loop"} or name == "sit_down"
        activities.append(
            {
                "activity": name,
                "file": path.name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "duration": duration,
                "loop": loop,
                "description": DESCRIPTIONS[name],
                "entry_pose": "seated" if name in {"sit_loop", "stand_up"} else "stand",
                "exit_pose": "seated"
                if seated
                else ("hold_last_frame" if name == "attention" else "stand"),
                "root_motion": "none (hips height only; desktop window owns travel)",
                "ground_contact": "seat_edge_and_feet"
                if name.startswith("sit") or name == "stand_up"
                else "feet",
                "interrupt": "any_frame"
                if loop or name in {"attention", "nod", "think"}
                else "after_complete",
                "crossfade_seconds": 0.3,
            }
        )
    pack = {
        "schema": "siro.visual.pack.v0",
        "status": "AUTHORED_PREVIEW_ONLY_PENDING_P01",
        "pack_id": "siro.vrm.activities",
        "version": VERSION,
        "identity": "siro (owner VRoid model; no identity or memory changes)",
        "authorship": "Claude original keyframes (scripts/build_vrm_motions.py), 2026-10-19",
        "license": "Original project-authored numeric data for SIRO; follows repository licensing.",
        "format": "VRM Animation 1.0 (.vrma), loaded with @pixiv/three-vrm-animation 3.1.0",
        "editable_source": "scripts/build_vrm_motions.py",
        "skeleton": "skeleton.json",
        "fps": FPS,
        "write_mask": (
            "humanoid bones listed per clip; expressions, lookAt, blink and spring bones"
            " are never written"
        ),
        "activities": activities,
    }
    (args.out / "pack.json").write_text(
        json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(activities)} activities to {args.out}")


if __name__ == "__main__":
    main()
