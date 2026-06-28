from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "None"}:
        return None
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value.startswith("[") and value.endswith("]"):
        return [_parse_scalar(item.strip()) for item in value[1:-1].split(",") if item.strip()]
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def _load_simple_yaml(path: Path) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        line = raw_line.split(" #", 1)[0].rstrip()
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(value)
    return root


def _load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").lstrip()
    if text.startswith("{"):
        return json.loads(text)
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"config root must be a mapping: {path}")
        return loaded
    except ModuleNotFoundError:
        return _load_simple_yaml(path)


def _deep_update(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_update(merged[key], value)
        else:
            merged[key] = value
    return merged


@dataclass(frozen=True)
class HarnessConfig:
    data: dict[str, Any] = field(default_factory=dict)
    root: Path = ROOT

    @classmethod
    def defaults(cls, root: Path = ROOT) -> "HarnessConfig":
        base = {
            "repos": {
                "testbed_09": str(root.parent / "tdo_testbed"),
                "testbed_10_ue": str(root),
                "engine_11": str(root.parent / "lowpcode_data_origin"),
            },
            "tools": {
                "python": "",
                "ghidra_home": "/opt/homebrew/Cellar/ghidra/12.0.4/libexec",
                "ghidra_java_home": "/Applications/Android Studio.app/Contents/jbr/Contents/Home",
                "android_ndk": "/Users/test2000/Library/Android/sdk/ndk/30.0.14904198",
                "unreal_engine_root": "/Users/Shared/Epic Games/UE_5.8",
                "release_artifacts": str(root / "dist" / "release_0.3.0"),
            },
            "output": {
                "root": str(root / "output" / "harness"),
                "memory": str(root / "output" / "harness" / "memory"),
            },
            "models": {
                "cheap": "",
                "strong": "",
                "adversary_panel": [],
            },
            "budgets": {
                "per_run_max_calls": 0,
                "per_run_max_tokens": 0,
            },
            "defaults": {
                "mode": "release-artifacts",
                "summary_first": True,
                "changed_only_prepare": True,
                "case_scope": "auto",
                "case_scope_file_threshold": 32,
                "case_scope_byte_threshold": 134217728,
            },
        }
        return cls(base, root)

    @classmethod
    def load(cls, path: Path | None, root: Path = ROOT) -> "HarnessConfig":
        default = cls.defaults(root)
        if path is None or not path.exists():
            return default
        return cls(_deep_update(default.data, _load_mapping(path)), root)

    def path(self, section: str, key: str) -> Path:
        return Path(str(self.data.get(section, {}).get(key, ""))).expanduser()

    def value(self, section: str, key: str, default: Any = None) -> Any:
        return self.data.get(section, {}).get(key, default)
