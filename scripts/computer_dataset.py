"""Inspect the recorded play data of one game (read-only).

  python scripts/computer_dataset.py undertale.exe            # stats + baseline accuracy
  python scripts/computer_dataset.py undertale.exe --sheet out.png   # plus random frames
Data directory: SIRO_DATA_DIR/computer-demos (override with --root).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from siro.services.computer_use.dataset import load_game
from siro.services.computer_use.demos import demos_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("process", help="program name, e.g. undertale.exe")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--sheet", type=Path, default=None, help="write a contact sheet PNG here")
    parser.add_argument("--val", type=float, default=0.2, help="validation share (by run)")
    args = parser.parse_args()
    data = load_game(args.root or demos_dir(), args.process)
    if not data.samples:
        print(f"no recorded data for {args.process} (set SIRO_COMPUTER_RECORD=1 and run tasks)")
        return 1
    train, val = data.split(args.val)
    print(json.dumps(data.stats(), ensure_ascii=False, indent=2))
    print(f"split by run: train {len(train)} samples / val {len(val)} samples")
    if args.sheet:
        print(f"contact sheet: {data.contact_sheet(args.sheet)} frames -> {args.sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
