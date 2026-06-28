#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PREFIXES = ("_case_TV2", "_dfb_", "_TraceRunAll", "_tv2_")


def normalize_symbol(value: str) -> str:
    if value.startswith(PREFIXES):
        return value[1:]
    return value


def normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {normalize_symbol(key): normalize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    if isinstance(value, str):
        return normalize_symbol(value)
    return value


def normalize_file(path: Path) -> Path:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data = normalize_value(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    name = path.name
    if name.startswith(PREFIXES):
        new_path = path.with_name(name[1:])
        if new_path != path:
            path.replace(new_path)
            return new_path
    return path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: normalize_macho_lowpcode.py <low_pcode_dir>", file=sys.stderr)
        return 2
    root = Path(argv[1])
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 1

    count = 0
    for path in sorted(root.glob("*_low_pcode.json")):
        normalize_file(path)
        count += 1
    manifest = root / "low_pcode_extraction_manifest.json"
    if manifest.exists():
        normalize_file(manifest)
    print(f"[normalized] Mach-O low-pcode symbols/files: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
