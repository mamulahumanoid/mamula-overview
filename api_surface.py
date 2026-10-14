"""Machine-readable public/internal API surface registry.

External developers can use this module to check whether a Python import path is
intended as stable public API, beta API, experimental surface, or internal
implementation detail.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Sequence

API_SURFACE_SCHEMA_VERSION = "mamula.api_surface.v1"

STABLE = "stable"
BETA = "beta"
EXPERIMENTAL = "experimental"
INTERNAL = "internal"


@dataclass(frozen=True)
class ApiSurfaceEntry:
    pattern: str
    stability: str
    audience: str
    compatibility: str
    description: str


API_SURFACE: tuple[ApiSurfaceEntry, ...] = (
    ApiSurfaceEntry(
        pattern="core.contract.*",
        stability=STABLE,
        audience="external integrations, adapters, tests",
        compatibility="Backwards-compatible changes with deprecation when practical.",
        description="Versioned message, topic, safety, lifecycle, and data contracts.",
    ),
    ApiSurfaceEntry(
        pattern="core.bus.*",
        stability=STABLE,
        audience="external integrations, tests, lightweight runtimes",
        compatibility="Backwards-compatible changes with deprecation when practical.",
        description="EventBus and topic registry primitives used to connect modules.",
    ),
    ApiSurfaceEntry(
        pattern="core.skills.sdk",
        stability=STABLE,
        audience="third-party skill/plugin authors",
        compatibility="Backwards-compatible changes with deprecation when practical.",
        description="Skill plugin registration SDK.",
    ),
    ApiSurfaceEntry(
        pattern="core.skills",
        stability=STABLE,
        audience="third-party skill/plugin authors",
        compatibility="Convenience re-export of the skill SDK only.",
        description="Stable import shortcut for skill SDK registration helpers.",
    ),
    ApiSurfaceEntry(
        pattern="core.version",
        stability=STABLE,
        audience="external integrations, release tooling, operators",
        compatibility="Backwards-compatible version metadata.",
        description="Public runtime version helpers and semantic-version validation.",
    ),
    ApiSurfaceEntry(
        pattern="core.runtime.paths",
        stability=BETA,
        audience="operators and deployment tooling",
        compatibility="May evolve with release-note notice; avoid deep runtime internals.",
        description="Runtime directory resolution for logs, DBs, telemetry, and cache roots.",
    ),
    ApiSurfaceEntry(
        pattern="core.services.*",
        stability=BETA,
        audience="adapter authors",
        compatibility="Framework-independent service contracts may still be refined.",
        description="Business logic layer intended to stay free of Flask/vendor SDK imports.",
    ),
    ApiSurfaceEntry(
        pattern="core.api.*",
        stability=BETA,
        audience="HTTP adapter maintainers",
        compatibility="Route-level behavior may change before 1.0.",
        description="API route modules and request/response boundary helpers.",
    ),
    ApiSurfaceEntry(
        pattern="core.adapters.*",
        stability=BETA,
        audience="adapter maintainers",
        compatibility="Adapter details may change when external systems change.",
        description="HTTP, ops, hardware, LLM, and external-world adapters.",
    ),
    ApiSurfaceEntry(
        pattern="core.control.*",
        stability=EXPERIMENTAL,
        audience="control-stack contributors",
        compatibility="Subject to change as native control and safety contracts mature.",
        description="Motion planning, safety filtering, and command arbitration internals.",
    ),
    ApiSurfaceEntry(
        pattern="core.controllers.*",
        stability=EXPERIMENTAL,
        audience="control-stack contributors",
        compatibility="Subject to change as humanoid controllers mature.",
        description="Controller implementations and controller manager internals.",
    ),
    ApiSurfaceEntry(
        pattern="core.estimation.*",
        stability=EXPERIMENTAL,
        audience="state-estimation contributors",
        compatibility="Subject to change as estimators mature.",
        description="State, body, joint, balance, and contact estimator implementations.",
    ),
    ApiSurfaceEntry(
        pattern="core.state.*",
        stability=EXPERIMENTAL,
        audience="robot-state contributors",
        compatibility="Subject to change until contracts graduate into core.contract.",
        description="Internal state containers and control-state helpers.",
    ),
    ApiSurfaceEntry(
        pattern="core.hardware.*",
        stability=EXPERIMENTAL,
        audience="hardware/HIL contributors",
        compatibility="Subject to change with HAL and real-robot bridge work.",
        description="Hardware abstraction, drivers, transport, and telemetry helpers.",
    ),
    ApiSurfaceEntry(
        pattern="core.skills.*",
        stability=EXPERIMENTAL,
        audience="built-in skill contributors",
        compatibility="Built-in skills may change; use core.skills.sdk for plugins.",
        description="Built-in skill implementations and routers.",
    ),
    ApiSurfaceEntry(
        pattern="core.modules.*",
        stability=INTERNAL,
        audience="runtime maintainers",
        compatibility="No external compatibility promise.",
        description="Runtime module implementations and profile-specific behavior.",
    ),
    ApiSurfaceEntry(
        pattern="core.brain.*",
        stability=INTERNAL,
        audience="cognition/runtime maintainers",
        compatibility="No external compatibility promise.",
        description="Reasoning, planning, policy, and conversation internals.",
    ),
    ApiSurfaceEntry(
        pattern="core.ai.*",
        stability=INTERNAL,
        audience="AI runtime maintainers",
        compatibility="No external compatibility promise.",
        description="LLM orchestration, embodied context, memory prompt, and chat internals.",
    ),
    ApiSurfaceEntry(
        pattern="core.learning.*",
        stability=INTERNAL,
        audience="learning-stack maintainers",
        compatibility="No external compatibility promise; artifacts follow MODEL_AND_DATA_POLICY.md.",
        description="Training, model governance, active learning, and promotion internals.",
    ),
    ApiSurfaceEntry(
        pattern="core.memory.*",
        stability=INTERNAL,
        audience="memory-stack maintainers",
        compatibility="No external compatibility promise; privacy policy applies.",
        description="Memory stores, DB schemas, and retention implementation details.",
    ),
    ApiSurfaceEntry(
        pattern="core.reasoning.*",
        stability=INTERNAL,
        audience="reasoning-stack maintainers",
        compatibility="No external compatibility promise.",
        description="Reasoning helpers and experimental behavior layers.",
    ),
    ApiSurfaceEntry(
        pattern="core.training.*",
        stability=INTERNAL,
        audience="training-stack maintainers",
        compatibility="No external compatibility promise.",
        description="Training layout and rollout internals.",
    ),
    ApiSurfaceEntry(
        pattern="core.tools.*",
        stability=INTERNAL,
        audience="operator tooling maintainers",
        compatibility="Python imports are internal; CLI commands are the public surface.",
        description="CLI and maintenance tools. Prefer the documented mamula commands.",
    ),
)

DEFAULT_ENTRY = ApiSurfaceEntry(
    pattern="core.*",
    stability=INTERNAL,
    audience="core maintainers",
    compatibility="No external compatibility promise unless listed in API_SURFACE.",
    description="Unlisted core package path.",
)

PUBLIC_STABILITIES = frozenset({STABLE, BETA})


def _pattern_matches(pattern: str, module_name: str) -> bool:
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        return module_name == prefix or module_name.startswith(prefix + ".")
    return module_name == pattern


def _specificity(pattern: str) -> tuple[int, int]:
    exact_bonus = 1 if not pattern.endswith(".*") else 0
    return (exact_bonus, len(pattern.rstrip("*")))


def classify_module(module_name: str) -> ApiSurfaceEntry:
    """Return the most specific API-surface entry for ``module_name``."""
    name = str(module_name or "").strip()
    matches = [entry for entry in API_SURFACE if _pattern_matches(entry.pattern, name)]
    if not matches:
        return DEFAULT_ENTRY
    return max(matches, key=lambda entry: _specificity(entry.pattern))


def is_public_module(module_name: str) -> bool:
    return classify_module(module_name).stability in PUBLIC_STABILITIES


def public_api_entries() -> tuple[ApiSurfaceEntry, ...]:
    return tuple(entry for entry in API_SURFACE if entry.stability in PUBLIC_STABILITIES)


def build_api_surface_report() -> dict[str, object]:
    return {
        "schema": API_SURFACE_SCHEMA_VERSION,
        "public_stabilities": sorted(PUBLIC_STABILITIES),
        "entries": [asdict(entry) for entry in API_SURFACE],
    }


def _print_table(entries: Sequence[ApiSurfaceEntry]) -> None:
    print("Pattern | Stability | Audience")
    print("--- | --- | ---")
    for entry in entries:
        print(f"{entry.pattern} | {entry.stability} | {entry.audience}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print MAMULA public/internal Python API surface")
    parser.add_argument("module", nargs="?", help="classify one module path, e.g. core.contract.message_envelope_v1")
    parser.add_argument("--json", action="store_true", help="print machine-readable API surface report")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.module:
        entry = classify_module(args.module)
        payload = {"module": args.module, "entry": asdict(entry), "public": is_public_module(args.module)}
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"{args.module}: {entry.stability} ({entry.pattern})")
            print(entry.description)
        return 0
    if args.json:
        print(json.dumps(build_api_surface_report(), indent=2, sort_keys=True))
    else:
        _print_table(API_SURFACE)
    return 0


__all__ = [
    "API_SURFACE",
    "API_SURFACE_SCHEMA_VERSION",
    "BETA",
    "EXPERIMENTAL",
    "INTERNAL",
    "PUBLIC_STABILITIES",
    "STABLE",
    "ApiSurfaceEntry",
    "build_api_surface_report",
    "classify_module",
    "is_public_module",
    "main",
    "public_api_entries",
]


if __name__ == "__main__":
    raise SystemExit(main())
