from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CASE_SCOPE_SCHEMA_VERSION = 2
FUNCTION_POINTER_SCOPE_WINDOW = 0x20


@dataclass(frozen=True)
class FunctionEntry:
    path: Path
    function_name: str
    function_entry: str
    call_names: tuple[str, ...]
    referenced_data_addresses: tuple[int, ...]
    function_pointer_targets: tuple[tuple[int, str, str], ...]
    has_computed_call: bool
    source_or_sink: bool
    file_hash: str
    size_bytes: int


@dataclass(frozen=True)
class ScopedCase:
    original_path: Path
    target_path: Path
    scope_dir: Path
    scope_hash: str
    root_file_hash: str | None
    scope_files: tuple[Path, ...]
    missing_internal_calls: tuple[str, ...]
    enabled: bool
    reason: str
    source_file_count: int
    source_bytes: int

    @property
    def manifest(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "reason": self.reason,
            "scope_dir": str(self.scope_dir),
            "scope_hash": self.scope_hash,
            "root_file_hash": self.root_file_hash,
            "scope_files": [str(path) for path in self.scope_files],
            "missing_internal_calls": list(self.missing_internal_calls),
            "source_file_count": self.source_file_count,
            "source_bytes": self.source_bytes,
        }


class CaseScopePlanner:
    """Build a deterministic per-case low-pcode closure without changing engine semantics.

    Engine11 currently composes every ``*_low_pcode.json`` in the target directory.
    Large UE DebugGame directories are therefore expensive even when one case only
    calls a small subset. This planner materializes a directory containing the
    target case and its transitive internal callees. It uses Ghidra call target
    metadata only to select already-extracted JSON files, not as dataflow truth.
    """

    def __init__(
        self,
        sample_dir: Path,
        output_root: Path,
        variant_label: str,
        policy: str = "auto",
        file_threshold: int = 32,
        byte_threshold: int = 128 * 1024 * 1024,
    ):
        if policy not in {"auto", "always", "never"}:
            raise ValueError(f"unknown case scope policy: {policy}")
        self.sample_dir = sample_dir
        self.output_root = output_root
        self.variant_label = variant_label
        self.policy = policy
        self.file_threshold = file_threshold
        self.byte_threshold = byte_threshold
        self._entries: dict[Path, FunctionEntry] | None = None
        self._name_index: dict[str, set[Path]] | None = None
        self._entry_index: dict[str, set[Path]] | None = None
        self._source_file_count: int | None = None
        self._source_bytes: int | None = None

    def materialize(self, case_path: Path) -> ScopedCase:
        self._ensure_index()
        assert self._entries is not None

        source_file_count = self._source_file_count or 0
        source_bytes = self._source_bytes or 0
        if not self._should_scope(source_file_count, source_bytes):
            entry = self._entries.get(case_path)
            return ScopedCase(
                original_path=case_path,
                target_path=case_path,
                scope_dir=case_path.parent,
                scope_hash=self._directory_hash(case_path.name),
                root_file_hash=entry.file_hash if entry is not None else None,
                scope_files=tuple(sorted(self._entries)),
                missing_internal_calls=(),
                enabled=False,
                reason=self._policy_reason(source_file_count, source_bytes, scoped=False),
                source_file_count=source_file_count,
                source_bytes=source_bytes,
            )

        closure, missing = self._closure_for(case_path)
        entry = self._entries.get(case_path)
        scope_hash = self._scope_hash(closure, case_path.name)
        scope_dir = (
            self.output_root
            / "case_scopes"
            / _safe_label(self.variant_label)
            / f"{case_path.stem}_{scope_hash[:12]}"
        )
        scope_dir.mkdir(parents=True, exist_ok=True)
        for source in sorted(closure):
            target = scope_dir / source.name
            if target.exists() or target.is_symlink():
                continue
            _link_or_copy(source, target)
        manifest_path = scope_dir / "case_scope_manifest.json"
        scoped = ScopedCase(
            original_path=case_path,
            target_path=scope_dir / case_path.name,
            scope_dir=scope_dir,
            scope_hash=scope_hash,
            root_file_hash=entry.file_hash if entry is not None else None,
            scope_files=tuple(sorted(closure)),
            missing_internal_calls=tuple(sorted(missing)),
            enabled=True,
            reason=self._policy_reason(source_file_count, source_bytes, scoped=True),
            source_file_count=source_file_count,
            source_bytes=source_bytes,
        )
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": CASE_SCOPE_SCHEMA_VERSION,
                    "target": str(case_path),
                    **scoped.manifest,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return scoped

    def _should_scope(self, source_file_count: int, source_bytes: int) -> bool:
        if self.policy == "always":
            return True
        if self.policy == "never":
            return False
        return source_file_count > self.file_threshold or source_bytes > self.byte_threshold

    def _policy_reason(self, source_file_count: int, source_bytes: int, scoped: bool) -> str:
        if self.policy == "always":
            return "case_scope_policy_always" if scoped else "case_scope_policy_always_not_applied"
        if self.policy == "never":
            return "case_scope_policy_never"
        if scoped:
            return f"auto_threshold:file_count={source_file_count},bytes={source_bytes}"
        return f"auto_below_threshold:file_count={source_file_count},bytes={source_bytes}"

    def _ensure_index(self) -> None:
        if self._entries is not None:
            return
        entries: dict[Path, FunctionEntry] = {}
        name_index: dict[str, set[Path]] = {}
        entry_index: dict[str, set[Path]] = {}
        total_size = 0
        for path in sorted(self.sample_dir.rglob("*_low_pcode.json")):
            entry = self._load_entry(path)
            entries[path] = entry
            total_size += entry.size_bytes
            for alias in self._aliases_for(entry):
                name_index.setdefault(alias, set()).add(path)
            if entry.function_entry:
                entry_index.setdefault(entry.function_entry, set()).add(path)
        self._entries = entries
        self._name_index = name_index
        self._entry_index = entry_index
        self._source_file_count = len(entries)
        self._source_bytes = total_size

    def _load_entry(self, path: Path) -> FunctionEntry:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        function_name = str(data.get("function_name") or _function_name_from_path(path))
        function_entry = _normalize_address(data.get("start_address"))
        call_names: set[str] = set()
        referenced_data_addresses: set[int] = set()
        function_pointer_targets: set[tuple[int, str, str]] = set()
        has_computed_call = False
        functions_by_entry = (data.get("indices") or {}).get("functions_by_entry") or {}
        names_by_entry = {
            _normalize_address(entry): str(info.get("name") or "")
            for entry, info in functions_by_entry.items()
            if isinstance(info, dict) and info.get("name")
        }
        for instr in data.get("instructions") or []:
            if not isinstance(instr, dict):
                continue
            flow_type = str(instr.get("flow_type") or "").upper()
            if "COMPUTED" in flow_type and "CALL" in flow_type:
                has_computed_call = True
            for target in instr.get("call_targets") or []:
                if not isinstance(target, dict):
                    continue
                for key in ("function_name", "thunk_target_name"):
                    value = target.get(key)
                    if value:
                        call_names.add(str(value))
                proto = target.get("external_prototype") or {}
                if isinstance(proto, dict):
                    for key in ("normalized_name", "name"):
                        value = proto.get(key)
                        if value:
                            call_names.add(str(value))
            for ref in instr.get("refs_from") or []:
                if not isinstance(ref, dict):
                    continue
                if ref.get("is_flow") or ref.get("is_call") or ref.get("is_jump"):
                    continue
                name = names_by_entry.get(_normalize_address(ref.get("to")))
                if name:
                    call_names.add(name)
                ref_address = _parse_address(ref.get("to"))
                if ref_address is not None:
                    referenced_data_addresses.add(ref_address)
        indices = data.get("indices") or {}
        data_refs_by_from = (data.get("indices") or {}).get("data_refs_by_from") or {}
        for refs in data_refs_by_from.values():
            for ref in refs or []:
                if not isinstance(ref, dict):
                    continue
                if ref.get("is_flow") or ref.get("is_call") or ref.get("is_jump"):
                    continue
                name = names_by_entry.get(_normalize_address(ref.get("to")))
                if name:
                    call_names.add(name)
                ref_address = _parse_address(ref.get("to"))
                if ref_address is not None:
                    referenced_data_addresses.add(ref_address)
        self._collect_function_pointer_targets(indices, function_pointer_targets)
        size_bytes = path.stat().st_size
        return FunctionEntry(
            path=path,
            function_name=function_name,
            function_entry=function_entry,
            call_names=tuple(sorted(call_names)),
            referenced_data_addresses=tuple(sorted(referenced_data_addresses)),
            function_pointer_targets=tuple(sorted(function_pointer_targets)),
            has_computed_call=has_computed_call,
            source_or_sink=function_name.startswith("dfb_source_") or function_name.startswith("dfb_sink_"),
            file_hash=_sha256_file(path),
            size_bytes=size_bytes,
        )

    def _collect_function_pointer_targets(self, indices: dict[str, Any], targets: set[tuple[int, str, str]]) -> None:
        for values in (indices.get("address_taken_functions_by_entry") or {}).values():
            for value in values or []:
                self._add_function_pointer_target(value, targets)
        for value in (indices.get("function_pointers_by_data_address") or {}).values():
            self._add_function_pointer_target(value, targets)

    def _add_function_pointer_target(self, value: Any, targets: set[tuple[int, str, str]]) -> None:
        if not isinstance(value, dict):
            return
        data_address = _parse_address(value.get("data_address"))
        if data_address is None:
            return
        name = str(value.get("target_name") or "")
        entry = _normalize_address(value.get("target_entry"))
        if name or entry:
            targets.add((data_address, name, entry))

    def _aliases_for(self, entry: FunctionEntry) -> set[str]:
        aliases = {entry.function_name, _function_name_from_path(entry.path)}
        if entry.function_name.startswith("_"):
            aliases.add(entry.function_name[1:])
        return {alias for alias in aliases if alias}

    def _closure_for(self, case_path: Path) -> tuple[set[Path], set[str]]:
        self._ensure_index()
        assert self._entries is not None
        assert self._name_index is not None
        assert self._entry_index is not None

        closure: set[Path] = {case_path}
        missing: set[str] = set()
        stack = [case_path]

        # Boundary helpers are small and make source/sink indexing stable across
        # direct-call and inlined-boundary variants.
        for path, entry in self._entries.items():
            if entry.source_or_sink:
                closure.add(path)

        if self._can_use_case_family_scope(case_path):
            for path in self._family_helper_paths(case_path):
                if path not in closure:
                    closure.add(path)
                    stack.append(path)

        while stack:
            current = stack.pop()
            entry = self._entries.get(current)
            if entry is None:
                continue
            if entry.has_computed_call:
                for _, name, target_entry in self._nearby_function_pointer_targets(closure):
                    for candidate in self._target_paths(name, target_entry):
                        if candidate in closure:
                            continue
                        closure.add(candidate)
                        stack.append(candidate)
            for call_name in entry.call_names:
                candidates = self._name_index.get(call_name)
                if not candidates:
                    missing.add(call_name)
                    continue
                for candidate in sorted(candidates):
                    if candidate in closure:
                        continue
                    closure.add(candidate)
                    stack.append(candidate)
        return closure, missing

    def _nearby_function_pointer_targets(self, closure: set[Path]) -> set[tuple[int, str, str]]:
        self._ensure_index()
        assert self._entries is not None
        reference_addresses: set[int] = set()
        targets: set[tuple[int, str, str]] = set()
        for path in closure:
            entry = self._entries.get(path)
            if entry is None:
                continue
            reference_addresses.update(entry.referenced_data_addresses)
            targets.update(entry.function_pointer_targets)
        if not reference_addresses:
            return set()
        selected: set[tuple[int, str, str]] = set()
        for target in targets:
            data_address = target[0]
            if any(abs(data_address - ref_address) <= FUNCTION_POINTER_SCOPE_WINDOW for ref_address in reference_addresses):
                selected.add(target)
        return selected

    def _target_paths(self, name: str, target_entry: str) -> set[Path]:
        self._ensure_index()
        assert self._name_index is not None
        assert self._entry_index is not None
        candidates: set[Path] = set()
        if target_entry:
            candidates.update(self._entry_index.get(target_entry, set()))
        if name and not candidates:
            candidates.update(self._name_index.get(name, set()))
        return candidates

    def _family_helper_paths(self, case_path: Path) -> set[Path]:
        self._ensure_index()
        assert self._entries is not None
        root_entry = self._entries.get(case_path)
        tokens = _case_family_tokens(case_path.name)
        if root_entry is not None:
            tokens.update(_case_family_tokens(root_entry.function_name))
        if not tokens:
            return set()
        family_paths: set[Path] = set()
        lowered_tokens = {token.lower() for token in tokens}
        for path, entry in self._entries.items():
            haystacks = {
                path.name.lower(),
                entry.function_name.lower(),
                _function_name_from_path(path).lower(),
            }
            if any(token in item for token in lowered_tokens for item in haystacks):
                family_paths.add(path)
        return family_paths

    def _can_use_case_family_scope(self, case_path: Path) -> bool:
        parts = {part.lower() for part in case_path.parts}
        return "cpp_like" in parts

    def _scope_hash(self, closure: set[Path], target_name: str) -> str:
        self._ensure_index()
        assert self._entries is not None
        payload = {
            "schema_version": CASE_SCOPE_SCHEMA_VERSION,
            "target": target_name,
            "files": [
                {
                    "name": path.name,
                    "function_name": self._entries[path].function_name,
                    "sha256": self._entries[path].file_hash,
                }
                for path in sorted(closure)
            ],
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _directory_hash(self, target_name: str) -> str:
        self._ensure_index()
        assert self._entries is not None
        return self._scope_hash(set(self._entries), target_name)


def _function_name_from_path(path: Path) -> str:
    name = path.name
    if name.endswith("_low_pcode.json"):
        return name[: -len("_low_pcode.json")]
    return path.stem


def _normalize_address(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("L", "")
    if not text:
        return ""
    try:
        return f"{int(text, 16):08x}"
    except ValueError:
        return text.lower()


def _parse_address(value: Any) -> int | None:
    normalized = _normalize_address(value)
    if not normalized:
        return None
    try:
        return int(normalized, 16)
    except ValueError:
        return None


def _case_family_tokens(text: str) -> set[str]:
    return {
        match.group(0)
        for match in re.finditer(r"[A-Z][A-Z0-9]{1,15}\d{3,}", text, flags=re.IGNORECASE)
    }


def _safe_label(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _link_or_copy(source: Path, target: Path) -> None:
    try:
        os.symlink(source, target)
    except (AttributeError, NotImplementedError, OSError):
        shutil.copy2(source, target)
