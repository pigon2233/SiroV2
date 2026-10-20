"""Assign body collider groups to the VRoid clothing spring chains of a VRM 1.0 model.

VRoid exports hood, hood-string and sleeve chains without colliders, so they pass through the
body once the character moves. This rewrites only ``VRMC_springBone.springs[].colliderGroups``
in the GLB JSON chunk; meshes, textures and the binary chunk are copied unchanged.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

# Spring (by name prefix of its first joint) -> collider groups (by name).
ASSIGNMENTS = {
    "J_Sec_C_Hood": ["J_Bip_C_UpperChest", "J_Bip_C_Neck", "J_Bip_C_Head"],
    "J_Sec_L_HoodString": [
        "J_Bip_C_Spine",
        "J_Bip_C_UpperChest",
        "J_Bip_L_UpperArm",
        "J_Bip_R_UpperArm",
    ],
    "J_Sec_R_HoodString": [
        "J_Bip_C_Spine",
        "J_Bip_C_UpperChest",
        "J_Bip_L_UpperArm",
        "J_Bip_R_UpperArm",
    ],
    "J_Sec_L_TopsUpperArm": ["J_Bip_C_Spine", "J_Bip_C_UpperChest"],
    "J_Sec_R_TopsUpperArm": ["J_Bip_C_Spine", "J_Bip_C_UpperChest"],
    "J_Sec_L_TopsUpperLeg": [
        "J_Bip_L_UpperLeg",
        "J_Bip_R_UpperLeg",
        "J_Bip_L_Hand",
        "J_Bip_R_Hand",
    ],
    "J_Sec_R_TopsUpperLeg": [
        "J_Bip_L_UpperLeg",
        "J_Bip_R_UpperLeg",
        "J_Bip_L_Hand",
        "J_Bip_R_Hand",
    ],
}


def read_glb(path: Path) -> tuple[dict[str, object], bytes]:
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise SystemExit(f"not a binary glTF file: {path}")
    length, kind = struct.unpack_from("<II", data, 12)
    if kind != 0x4E4F534A:
        raise SystemExit("first chunk is not JSON")
    return json.loads(data[20 : 20 + length]), data[20 + length :]


def tune(document: dict[str, object]) -> list[str]:
    nodes = document["nodes"]
    springs = document["extensions"]["VRMC_springBone"]  # type: ignore[index]
    groups = {group["name"]: i for i, group in enumerate(springs["colliderGroups"])}
    changed = []
    for spring in springs["springs"]:
        first = nodes[spring["joints"][0]["node"]]["name"]  # type: ignore[index]
        for prefix, names in ASSIGNMENTS.items():
            if first.startswith(prefix):
                spring["colliderGroups"] = [groups[name] for name in names]
                changed.append(first)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    document, rest = read_glb(args.source)
    changed = tune(document)
    payload = json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode()
    payload += b" " * (-len(payload) % 4)
    total = 20 + len(payload) + len(rest)
    args.output.write_bytes(
        struct.pack("<4sII", b"glTF", 2, total)
        + struct.pack("<II", len(payload), 0x4E4F534A)
        + payload
        + rest
    )
    print(f"Assigned colliders to {len(changed)} spring chains: {', '.join(sorted(changed))}")


if __name__ == "__main__":
    main()
