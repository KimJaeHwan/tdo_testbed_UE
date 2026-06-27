#!/usr/bin/env python3
"""Shared path resolution for the low-pcode engine repo.

The UE testbed is intended to live next to the engine repo during local
development, but CI or Windows worktrees may put it elsewhere.  Keep that
choice outside the analysis code by resolving it once from environment and
well-known sibling locations.
"""
from __future__ import annotations

import os
from pathlib import Path


def resolve_engine_root(repo_root: Path) -> Path:
    env = os.environ.get("TDO_ENGINE_ROOT")
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.extend(
        [
            repo_root.parent / "lowpcode_data_origin",
            repo_root.parent / "trace_data_origin_lowpcode",
            repo_root.parent / "11_tracing_Data_Origin_lowpcode" / "trace_data_origin_lowpcode",
            Path("D:/01_gitproject/11_tracing_Data_Origin_lowpcode/trace_data_origin_lowpcode"),
        ]
    )
    for candidate in candidates:
        root = candidate.expanduser()
        if (root / "analysis" / "interprocedural_summary.py").exists():
            return root
    searched = "\n  - ".join(str(c) for c in candidates)
    raise RuntimeError(
        "Could not find trace_data_origin_lowpcode engine root. "
        "Set TDO_ENGINE_ROOT to the lowpcode_data_origin/trace_data_origin_lowpcode path.\n"
        f"Searched:\n  - {searched}"
    )


def add_engine_to_syspath(repo_root: Path) -> Path:
    import sys

    engine_root = resolve_engine_root(repo_root)
    sys.path.insert(0, str(engine_root))
    return engine_root


def ensure_engine_python(repo_root: Path) -> None:
    """Re-exec with the engine venv when the caller used system Python.

    The analysis engine owns dependencies such as networkx.  Keeping this in
    the testbed runner avoids duplicating requirements or asking every caller
    to remember the engine venv path.
    """
    import sys

    if os.environ.get("TDO_NO_VENV_REEXEC") == "1":
        return
    engine_root = resolve_engine_root(repo_root)
    if os.name == "nt":
        venv_python = engine_root / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = engine_root / ".venv" / "bin" / "python"
    if not venv_python.exists():
        return
    current = Path(sys.executable).absolute()
    target = venv_python.absolute()
    if current == target:
        return
    os.environ["TDO_NO_VENV_REEXEC"] = "1"
    os.execv(str(target), [str(target), *sys.argv])
