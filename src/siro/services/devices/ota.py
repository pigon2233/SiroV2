"""Server side of node OTA: a signed-by-hash manifest for the firmware image the node may pull.

Nothing here pushes to a device or flashes anything. The node asks for the manifest, compares the
version, downloads the image and verifies `sha256` before switching partitions (firmware side).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path

_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass(frozen=True)
class OtaManifest:
    version: str
    size: int
    sha256: str
    filename: str

    def as_json(self) -> dict[str, object]:
        return asdict(self)


def parse_version(value: str) -> tuple[int, int, int]:
    if not _VERSION.fullmatch(value):
        raise ValueError("firmware version must look like 1.2.3")
    major, minor, patch = (int(part) for part in value.split("."))
    return major, minor, patch


def build_manifest(image: Path, version: str) -> OtaManifest:
    parse_version(version)
    data = image.read_bytes()
    if not data:
        raise ValueError("firmware image is empty")
    return OtaManifest(version, len(data), hashlib.sha256(data).hexdigest(), image.name)


def update_available(current: str, manifest: OtaManifest) -> bool:
    """Only strictly newer images are offered; a downgrade must be an explicit decision."""

    return parse_version(manifest.version) > parse_version(current)
