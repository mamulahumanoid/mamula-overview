"""Skill SDK — third-party plugins register into the robot skill catalog.

Registered rows extend ``robot_skill_catalog`` via ``register_extension_skills``;
handler callables are stored separately until executive wiring consumes them.

See ``core/docs/skill_sdk_plugin_stage9.md``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from core.modules.robot.robot_skill_catalog import register_extension_skills

SKILL_PLUGIN_SCHEMA_VERSION = "mamula.skill_plugin.v1"

_PLUGIN_HANDLERS: Dict[str, Callable[..., Any]] = {}


def _risk_level_to_tier(level: int) -> str:
    lv = int(level)
    if lv >= 4:
        return "high"
    if lv >= 3:
        return "medium"
    return "low"


def _cap_union(
    required_capabilities: Optional[Sequence[str]],
    required_sensors: Optional[Sequence[str]],
    required_actuators: Optional[Sequence[str]],
) -> List[str]:
    out: List[str] = []
    for seq in (required_capabilities, required_sensors, required_actuators):
        if not seq:
            continue
        for x in seq:
            t = str(x or "").strip()
            if t and t not in out:
                out.append(t)
    return out


def register_skill(
    *,
    name: str,
    risk_level: int = 2,
    required_sensors: Optional[Sequence[str]] = None,
    required_actuators: Optional[Sequence[str]] = None,
    handler: Optional[Callable[..., Any]] = None,
    preconditions: Optional[Sequence[str]] = None,
    postconditions: Optional[Sequence[str]] = None,
    required_capabilities: Optional[Sequence[str]] = None,
    timeout_ms: int = 60_000,
    recovery_policy: str = "abort",
    simulation_support: bool = True,
    hardware_support: bool = True,
    test_suite: Optional[str] = None,
    category: str = "plugin",
    description: str = "",
    params: Optional[Sequence[str]] = None,
    planner_action_types: Optional[Sequence[str]] = None,
    default_action_type: Optional[str] = None,
    tags: Optional[Sequence[str]] = None,
) -> None:
    """Register or replace a skill in the runtime catalog.

    Planner linkage requires ``planner_action_types`` or ``default_action_type``.
    Handler is optional metadata for future dispatch / tests.
    """
    nm = str(name or "").strip()
    if not nm:
        raise ValueError("register_skill: name is required")

    pts: Optional[List[str]] = None
    if planner_action_types:
        pts = [str(x).strip().upper() for x in planner_action_types if str(x).strip()]
    dat = str(default_action_type or "").strip().upper()
    if not pts and dat:
        pts = [dat]
    if not pts:
        raise ValueError(
            "register_skill: provide planner_action_types or default_action_type so the planner can map actions",
        )

    plugin_meta: Dict[str, Any] = {
        "schema_version": SKILL_PLUGIN_SCHEMA_VERSION,
        "risk_level": int(risk_level),
        "preconditions": [str(x) for x in (preconditions or []) if str(x).strip()],
        "postconditions": [str(x) for x in (postconditions or []) if str(x).strip()],
        "required_capabilities": [str(x) for x in (required_capabilities or []) if str(x).strip()],
        "required_sensors": [str(x) for x in (required_sensors or []) if str(x).strip()],
        "required_actuators": [str(x) for x in (required_actuators or []) if str(x).strip()],
        "required_capabilities_all": _cap_union(required_capabilities, required_sensors, required_actuators),
        "timeout_ms": int(timeout_ms),
        "recovery_policy": str(recovery_policy or "abort"),
        "simulation_support": bool(simulation_support),
        "hardware_support": bool(hardware_support),
        "test_suite": str(test_suite).strip() if test_suite else None,
    }

    row: Dict[str, Any] = {
        "name": nm,
        "params": [str(x) for x in (params or [])] if params is not None else [],
        "category": str(category or "plugin"),
        "description": str(description or ""),
        "tags": [str(x) for x in (tags or [])],
        "risk_tier": _risk_level_to_tier(risk_level),
        "planner_action_types": pts,
        "plugin": plugin_meta,
        "_skill_sdk": True,
    }

    # Hint flags for legacy filters (skills list / policy)
    caps = plugin_meta["required_capabilities_all"]
    if caps:
        row["required_capabilities"] = caps
    if plugin_meta["required_sensors"]:
        row["requires_vision"] = any(
            "camera" in s.lower() or "depth" in s.lower() or "vision" in s.lower()
            for s in plugin_meta["required_sensors"]
        )
    if plugin_meta["required_actuators"]:
        row["requires_manipulation"] = True

    register_extension_skills([row])
    if handler is not None:
        _PLUGIN_HANDLERS[nm] = handler
    elif nm in _PLUGIN_HANDLERS:
        del _PLUGIN_HANDLERS[nm]


def get_skill_handler(name: str) -> Optional[Callable[..., Any]]:
    return _PLUGIN_HANDLERS.get(str(name or "").strip())


def clear_skill_handlers() -> None:
    """Remove SDK handler bindings (tests). Catalog rows remain until cleared separately."""
    _PLUGIN_HANDLERS.clear()


__all__ = [
    "SKILL_PLUGIN_SCHEMA_VERSION",
    "clear_skill_handlers",
    "get_skill_handler",
    "register_skill",
]
