from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import HarnessConfig


@dataclass(frozen=True)
class Variant:
    suite: str
    label: str
    sample_dir: Path
    expected_path: Path
    case_glob: str
    arch: str
    compiler: str
    opt: str
    build_config: str | None = None
    pdb: bool = False
    unreal_version: str | None = None
    binary_path: Path | None = None
    source_kind: str = "existing-lowpcode"

    def variant_dict(self) -> dict:
        return {
            "arch": self.arch,
            "compiler": self.compiler,
            "opt": self.opt,
            "build_config": self.build_config,
            "pdb": self.pdb,
            "unreal_version": self.unreal_version,
            "source_kind": self.source_kind,
        }


class Suite10UEAdapter:
    def __init__(self, config: HarnessConfig):
        self.config = config
        self.root = config.path("repos", "testbed_10_ue")

    def variants(self, mode: str) -> list[Variant]:
        if mode == "release-artifacts":
            release = self.config.path("tools", "release_artifacts")
            expected = release / "extracted" / "expected" / "tv2_unreal.expected.json"
            if not expected.exists():
                expected = self.root / "unreal_playground" / "expected" / "tv2_unreal.expected.json"
            return [
                Variant(
                    suite="10_tdo_testbed_UE",
                    label="ue-win64-development-release",
                    sample_dir=release / "low_pcode" / "ue_win64_dev",
                    expected_path=expected,
                    case_glob="case_TV2*_low_pcode.json",
                    arch="x86_64",
                    compiler="msvc",
                    opt="O2",
                    build_config="Development",
                    pdb=True,
                    unreal_version="5.1.1",
                    binary_path=release / "extracted" / "ue-win64" / "UnrealEditor-TraceUnrealPlayground.dll",
                    source_kind="release-artifact",
                ),
                Variant(
                    suite="10_tdo_testbed_UE",
                    label="ue-win64-debuggame-release",
                    sample_dir=release / "low_pcode" / "ue_win64_debuggame",
                    expected_path=expected,
                    case_glob="case_TV2*_low_pcode.json",
                    arch="x86_64",
                    compiler="msvc",
                    opt="Od",
                    build_config="DebugGame",
                    pdb=True,
                    unreal_version="5.1.1",
                    binary_path=release
                    / "extracted"
                    / "ue-win64"
                    / "UnrealEditor-TraceUnrealPlayground-Win64-DebugGame.dll",
                    source_kind="release-artifact",
                ),
            ]

        project = self.root / "unreal_playground" / "TraceUnrealPlayground"
        expected = self.root / "unreal_playground" / "expected" / "tv2_unreal.expected.json"
        return [
            Variant(
                suite="10_tdo_testbed_UE",
                label="ue-local-development",
                sample_dir=project / "samples" / "low_pcode",
                expected_path=expected,
                case_glob="case_TV2*_low_pcode.json",
                arch="x86_64",
                compiler="local",
                opt="O2",
                build_config="Development",
                pdb=False,
                unreal_version="5.1.1",
                source_kind="local-samples",
            ),
            Variant(
                suite="10_tdo_testbed_UE",
                label="ue-local-debuggame",
                sample_dir=project / "samples" / "low_pcode_P0",
                expected_path=expected,
                case_glob="case_TV2*_low_pcode.json",
                arch="x86_64",
                compiler="local",
                opt="Od",
                build_config="DebugGame",
                pdb=False,
                unreal_version="5.1.1",
                source_kind="local-samples",
            ),
        ]


class Suite09Adapter:
    ARCH_NAMES = {
        "PE_x64": "x86_64",
        "PE_x86": "x86",
        "linux_amd64": "x86_64",
        "linux_386": "x86",
        "linux_arm64": "aarch64",
        "linux_arm_v7": "armv7",
    }

    def __init__(self, config: HarnessConfig):
        self.config = config
        self.testbed = config.path("repos", "testbed_09")
        self.engine = config.path("repos", "engine_11")

    def variants(self, mode: str) -> list[Variant]:
        sample_root = self.engine / "samples" / "low_pcode"
        expected = self.testbed / "expected"
        variants: list[Variant] = []
        for root in sorted(path for path in sample_root.iterdir() if path.is_dir()):
            if not list(root.rglob("case_DFB*_low_pcode.json")):
                continue
            arch = self.ARCH_NAMES.get(root.name, root.name)
            variants.append(
                Variant(
                    suite="09_tdo_testbed",
                    label=f"dfb-{root.name}",
                    sample_dir=root,
                    expected_path=expected,
                    case_glob="case_DFB*_low_pcode.json",
                    arch=arch,
                    compiler="mixed",
                    opt="mixed",
                    source_kind="engine-samples",
                )
            )
        return variants


def selected_variants(config: HarnessConfig, suites: set[str], mode: str) -> list[Variant]:
    variants: list[Variant] = []
    if "09" in suites:
        variants.extend(Suite09Adapter(config).variants(mode))
    if "10" in suites:
        variants.extend(Suite10UEAdapter(config).variants(mode))
    return variants

