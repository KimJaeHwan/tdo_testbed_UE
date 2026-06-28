from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import HarnessConfig


@dataclass(frozen=True)
class PrepareStep:
    label: str
    command: tuple[str, ...]
    cwd: Path
    env: dict[str, str]
    outputs: tuple[Path, ...] = ()
    optional: bool = False


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
    TIER0_ARCHES = {
        "x86": "x86",
        "x64": "x86_64",
        "armv7": "armv7",
        "aarch64": "aarch64",
    }

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

        variants: list[Variant] = []
        cpp_expected = self.root / "cpp_like" / "expected" / "tv2_cpp_like.expected.json"
        for profile, opt in [("P0", "O0"), ("P1", "O2")]:
            for build_arch, arch in self.TIER0_ARCHES.items():
                sample_dir = self.root / "cpp_like" / "samples" / "low_pcode" / build_arch
                if profile != "P0":
                    sample_dir = self.root / "cpp_like" / "samples" / "low_pcode" / f"{profile}_{build_arch}"
                variants.append(
                    Variant(
                        suite="10_tdo_testbed_UE",
                        label=f"tv2-tier0-{profile}-{build_arch}",
                        sample_dir=sample_dir,
                        expected_path=cpp_expected,
                        case_glob="case_TV2C*_low_pcode.json",
                        arch=arch,
                        compiler="ndk-clang",
                        opt=opt,
                        build_config=profile,
                        pdb=False,
                        unreal_version=None,
                        binary_path=self.root / "cpp_like" / "build" / profile / build_arch / "libtv2_cpp_like.so",
                        source_kind="local-tier0",
                    )
                )

        project = self.root / "unreal_playground" / "TraceUnrealPlayground"
        expected = self.root / "unreal_playground" / "expected" / "tv2_unreal.expected.json"
        variants.extend(
            [
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
                    unreal_version="5.8.0",
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
                    unreal_version="5.8.0",
                    source_kind="local-samples",
                ),
            ]
        )
        return variants

    def prepare_steps(
        self,
        mode: str,
        profile: str,
        arches: list[str],
        include_ue_build: bool = False,
    ) -> list[PrepareStep]:
        if mode != "local-samples":
            return []
        env = self._tool_env()
        steps = [
            PrepareStep(
                label=f"tier0-build-{profile}",
                command=("bash", str(self.root / "build.sh"), "tier0", profile),
                cwd=self.root,
                env=env,
                outputs=tuple(
                    self.root / "cpp_like" / "build" / profile / arch / "libtv2_cpp_like.so"
                    for arch in arches
                ),
            )
        ]
        for arch in arches:
            sample_dir = self.root / "cpp_like" / "samples" / "low_pcode" / arch
            if profile != "P0":
                sample_dir = self.root / "cpp_like" / "samples" / "low_pcode" / f"{profile}_{arch}"
            steps.append(
                PrepareStep(
                    label=f"tier0-extract-{profile}-{arch}",
                    command=("bash", str(self.root / "cpp_like" / "scripts" / "extract_lowpcode.sh"), arch, profile),
                    cwd=self.root,
                    env=env,
                    outputs=(sample_dir,),
                )
            )
        if include_ue_build:
            steps.append(
                PrepareStep(
                    label=f"ue-build-{profile}",
                    command=("bash", str(self.root / "build.sh"), "ue", profile),
                    cwd=self.root,
                    env=env,
                    outputs=(self.root / "unreal_playground" / "TraceUnrealPlayground" / "Binaries",),
                )
            )
        return steps

    def _tool_env(self) -> dict[str, str]:
        values = {
            "ANDROID_NDK_HOME": self._path_value("tools", "android_ndk"),
            "UE_ROOT": self._path_value("tools", "unreal_engine_root"),
            "GHIDRA_DIR": self._path_value("tools", "ghidra_home"),
            "GHIDRA_JAVA_HOME": self._path_value("tools", "ghidra_java_home"),
            "TDO_ENGINE_ROOT": self._path_value("repos", "engine_11"),
            "TDO_DUMPER_DIR": str(self.config.path("repos", "engine_11") / "scripts"),
            "PYTHON_BIN": self._path_value("tools", "python"),
        }
        return {key: value for key, value in values.items() if value}

    def _path_value(self, section: str, key: str) -> str:
        raw = self.config.value(section, key, "")
        if raw is None or str(raw).strip() == "":
            return ""
        return str(Path(str(raw)).expanduser())


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


def selected_prepare_steps(
    config: HarnessConfig,
    suites: set[str],
    mode: str,
    profile: str,
    arches: list[str],
    include_ue_build: bool = False,
) -> list[PrepareStep]:
    steps: list[PrepareStep] = []
    if "10" in suites:
        steps.extend(Suite10UEAdapter(config).prepare_steps(mode, profile, arches, include_ue_build))
    return steps
