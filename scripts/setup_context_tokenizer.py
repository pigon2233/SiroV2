"""Provision only public, pinned tokenizer assets; no inference or credentials."""

from __future__ import annotations

import argparse
import hashlib
import json
from importlib.resources import files
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory",
        type=Path,
        default=Path(__file__).parents[1] / ".siro-data/tokenizers/gpt-oss-20b",
    )
    args = parser.parse_args()
    profile = json.loads(files("siro.services.agent").joinpath("gpt_oss_profile.json").read_text())
    args.directory.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=90) as client:
        for filename, digest in profile["files"].items():
            path = args.directory / filename
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                continue
            response = client.get(
                f"https://huggingface.co/{profile['repository']}/resolve/"
                f"{profile['revision']}/{filename}"
            )
            response.raise_for_status()
            if hashlib.sha256(response.content).hexdigest() != digest:
                raise ValueError("downloaded tokenizer digest mismatch")
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_bytes(response.content)
            temporary.replace(path)
    print(f"Verified pinned tokenizer assets: {args.directory}")


if __name__ == "__main__":
    main()
