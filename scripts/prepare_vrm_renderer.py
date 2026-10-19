"""Build the local VRM renderer and (optionally) register an owner VRM model.

The renderer source lives in ``renderers/vrm``. Dependencies are installed from the
committed lockfile and copied into a Git-ignored output directory, so the gateway can
serve the renderer offline without any CDN. A model is copied into a Git-ignored
``config/body-assets`` directory together with a ``BodyAssetManifest`` v1 record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from siro.adapters.body.assets import BodyAssetManifest, load_verified_manifest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "renderers" / "vrm"
VENDOR = {
    "three.module.js": "three/build/three.module.js",
    "jsm/loaders/GLTFLoader.js": "three/examples/jsm/loaders/GLTFLoader.js",
    "jsm/utils/BufferGeometryUtils.js": "three/examples/jsm/utils/BufferGeometryUtils.js",
    "three-vrm.module.js": "@pixiv/three-vrm/lib/three-vrm.module.js",
    "LICENSE-three.txt": "three/LICENSE",
    "LICENSE-three-vrm.txt": "@pixiv/three-vrm/LICENSE",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vrm_spec_version(path: Path) -> str:
    """Return the VRM spec version of a GLB file, or raise if it is not a VRM."""

    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        raise ValueError(f"not a binary glTF file: {path}")
    length, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != 0x4E4F534A:
        raise ValueError(f"first glTF chunk is not JSON: {path}")
    document = json.loads(data[20 : 20 + length])
    extensions = document.get("extensions", {})
    if "VRMC_vrm" in extensions:
        return str(extensions["VRMC_vrm"].get("specVersion", "1.0"))
    if "VRM" in extensions:
        return "0.x"
    raise ValueError(f"glTF file has no VRM extension: {path}")


def build_renderer(output: Path, *, force: bool) -> bool:
    """Build into ``output``; an existing build is reused unless ``force`` is set."""

    if (output / "index.html").is_file() and not force:
        return False
    # Windows ships npm as npm.cmd, which CreateProcess cannot find by bare name.
    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("npm was not found; install Node.js LTS to build the VRM renderer")
    if output.exists():
        shutil.rmtree(output)
    subprocess.run(
        [npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=SOURCE, check=True
    )
    output.mkdir(parents=True)
    shutil.copy2(SOURCE / "index.html", output / "index.html")
    shutil.copytree(SOURCE / "src", output / "src")
    for target, source in VENDOR.items():
        destination = output / "vendor" / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / "node_modules" / source, destination)
    lock = json.loads((SOURCE / "package-lock.json").read_text(encoding="utf-8"))
    files = sorted(p for p in output.rglob("*") if p.is_file())
    record = {
        "renderer": "siro-vrm",
        "packages": {
            name.removeprefix("node_modules/"): meta["version"]
            for name, meta in lock["packages"].items()
            if name in {"node_modules/three", "node_modules/@pixiv/three-vrm"}
        },
        "files": [{"path": p.relative_to(output).as_posix(), "sha256": sha256(p)} for p in files],
    }
    (output / "build-manifest.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    return True


def register_model(
    model: Path,
    asset_dir: Path,
    *,
    source_url: str,
    license_url: str,
    license_name: str,
    accepted_by: str,
    force: bool,
) -> Path:
    spec = vrm_spec_version(model)
    if asset_dir.exists() and any(asset_dir.iterdir()) and not force:
        raise SystemExit(f"{asset_dir} is not empty; pass --force to replace the model")
    asset_dir.mkdir(parents=True, exist_ok=True)
    target = asset_dir / "model.vrm"
    shutil.copy2(model, target)
    manifest = BodyAssetManifest.model_validate(
        {
            "schema_version": 1,
            "asset_id": "vrm.siro-owner-model",
            "source_url": source_url,
            "license_name": license_name,
            "license_url": license_url,
            "accepted_by": accepted_by,
            "accepted_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "files": [{"path": "model.vrm", "sha256": sha256(target)}],
        }
    )
    path = asset_dir / "asset-manifest.json"
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    load_verified_manifest(path)
    print(f"Registered VRM {spec} model: {target}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "models" / "vrm-renderer")
    parser.add_argument("--model", type=Path, help="owner VRM file to register")
    parser.add_argument(
        "--asset-dir", type=Path, default=ROOT / "config" / "body-assets" / "siro-vrm"
    )
    parser.add_argument("--source-url", default="https://vroid.com/en/studio")
    parser.add_argument("--license-url", help="terms the owner accepted for the model source")
    parser.add_argument("--license-name", default="VRoid Studio terms of use (owner-created model)")
    parser.add_argument("--accepted-by", default="owner")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    built = build_renderer(args.out.resolve(), force=args.force)
    print(f"{'Built' if built else 'Reusing'} VRM renderer: {args.out.resolve()}")
    manifest = args.asset_dir.resolve() / "asset-manifest.json"
    if args.model is not None:
        if not args.license_url:
            raise SystemExit("--license-url is required when registering a model")
        manifest = register_model(
            args.model.resolve(),
            args.asset_dir.resolve(),
            source_url=args.source_url,
            license_url=args.license_url,
            license_name=args.license_name,
            accepted_by=args.accepted_by,
            force=args.force,
        )
    print("Start the gateway with:")
    print(f'  SIRO_VRM_DIST="{args.out.resolve()}" \\')
    print(f'  SIRO_VRM_MODEL_MANIFEST="{manifest}" uv run siro-gateway')


if __name__ == "__main__":
    main()
