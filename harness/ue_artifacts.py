from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UEBuildArtifact:
    profile: str
    build_config: str
    platform: str
    arch: str
    binary_path: Path
    sample_dir: Path
    label: str
    opt: str


def discover_local_ue_artifact(repo_root: Path, profile: str) -> UEBuildArtifact:
    """Discover the local UE module binary for a harness profile.

    The harness still treats the binary only as an extraction input and artifact
    identity. It does not infer source/sink semantics from UE naming or ABI.
    """

    project = repo_root / "unreal_playground" / "TraceUnrealPlayground"
    binaries = project / "Binaries"
    normalized = profile.upper()
    if normalized == "P0":
        candidates = [
            binaries / "Mac" / "libUnrealEditor-TraceUnrealPlayground-Mac-DebugGame.dylib",
            binaries / "Win64" / "UnrealEditor-TraceUnrealPlayground-Win64-DebugGame.dll",
        ]
        return _first_existing(
            candidates,
            fallback=candidates[0],
            profile=normalized,
            build_config="DebugGame",
            sample_dir=project / "samples" / "low_pcode_P0",
            label="ue-local-debuggame",
            opt="Od",
        )
    if normalized == "P1":
        candidates = [
            binaries / "Mac" / "libUnrealEditor-TraceUnrealPlayground.dylib",
            binaries / "Win64" / "UnrealEditor-TraceUnrealPlayground.dll",
        ]
        return _first_existing(
            candidates,
            fallback=candidates[0],
            profile=normalized,
            build_config="Development",
            sample_dir=project / "samples" / "low_pcode",
            label="ue-local-development",
            opt="O2",
        )
    raise ValueError(f"unknown UE profile: {profile}")


def _first_existing(
    candidates: list[Path],
    fallback: Path,
    profile: str,
    build_config: str,
    sample_dir: Path,
    label: str,
    opt: str,
) -> UEBuildArtifact:
    binary = next((path for path in candidates if path.exists()), fallback)
    parts = set(binary.parts)
    platform = "Mac" if "Mac" in parts else "Win64" if "Win64" in parts else "unknown"
    arch = "aarch64" if platform == "Mac" else "x86_64" if platform == "Win64" else "unknown"
    return UEBuildArtifact(
        profile=profile,
        build_config=build_config,
        platform=platform,
        arch=arch,
        binary_path=binary,
        sample_dir=sample_dir,
        label=label,
        opt=opt,
    )
