from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, FrozenSet, List, Optional

from core.runtime.module_spec import ModuleSpec

# stub | experimental | sim_ready | hil_ready | hardware_ready | production
MaturityName = str
SafetyName = str  # non_motion | low_risk | high_risk | critical

_LEGACY_MATURITY_ALIASES = {
    "sim": "sim_ready",
    "hil": "hil_ready",
    "bench": "hil_ready",
    "supervised": "hil_ready",
}

_MOTION_HARDWARE_MODULE_NAMES = frozenset(
    {
        "hardware_bridge",
        "motor_driver_backend",
        "hardware_protocol_bridge",
        "hardware_safety_watchdog",
        "native_command_frame_hardware_bridge",
        "vendor_servo_protocol",
        "servo_coordinator",
    }
)


def normalize_maturity_name(raw: str | None) -> MaturityName:
    key = str(raw or "").strip().lower()
    if not key:
        return "experimental"
    return _LEGACY_MATURITY_ALIASES.get(key, key)


def _shadow_commands_enabled() -> bool:
    return os.environ.get("MAMULA_HARDWARE_SHADOW_COMMANDS", "").strip().lower() in {"1", "true", "yes", "on"}


def _skip_production_maturity_gate() -> bool:
    env_val = os.environ.get("HUMANOID_SKIP_PRODUCTION_MATURITY", "").strip().lower()
    if env_val:
        return env_val in {"1", "true", "yes", "on"}
    try:
        from core.config.mamula_config import get_config

        return get_config().get_bool("safety.skip_production_maturity", False)
    except Exception:
        return False


SAFETY_PIPELINE_IMPORT_PATH = "core.safety.safety_pipeline.SafetyPipelineModule"
MOTION_COMMAND_GATEWAY_PATH = (
    "core.modules.control.motion_command_gateway_module.MotionCommandGatewayModule"
)
SAFE_COMMAND_ACTION_ROUTER_PATH = (
    "core.modules.control.safe_command_action_router_module.SafeCommandActionRouterModule"
)
MOTION_NATIVE_GOAL_BRIDGE_PATH = (
    "core.modules.control.motion_native_goal_bridge_module.MotionNativeGoalBridgeModule"
)
ACTUATOR_BUNDLE_SAFETY_FILTER_PATH = (
    "core.modules.control.actuator_bundle_safety_filter_module.ActuatorBundleSafetyFilterModule"
)
SAFETY_SUPERVISOR_PATH = "core.safety.safety_supervisor_module.SafetySupervisorModule"
HARDWARE_ROLLOUT_GATE_PATH = "core.safety.hardware_rollout_gate_module.HardwareRolloutGateModule"
CONTROL_AUDIT_RECORDER_PATH = "core.observability.control_audit_recorder_module.ControlAuditRecorderModule"
ACTION_TRANSFORMATION_PIPELINE_PATH = (
    "core.modules.execution.action_transformation_pipeline_module.ActionTransformationPipelineModule"
)
TRUSTED_RECOVERY_AUTHORIZER_PATH = (
    "core.modules.control.trusted_recovery_authorizer_module.TrustedRecoveryAuthorizerModule"
)
RECOVERY_REQUESTER_MODULE_NAMES = frozenset(
    {
        "fall_recovery",
        "locomotion_supervisor",
        "manipulation_autonomy_retry_recovery",
    }
)


def profile_requires_safety_pipeline(resolved: str) -> bool:
    """Stacks that must include :class:`SafetyPipelineModule` (``exec.cmd`` gate)."""
    r = (resolved or "").strip().lower()
    if r == "production":
        return True
    if "supervised" in r:
        return True
    try:
        from core.runtime.profiles.registry import profile_registry

        pspec = profile_registry().get(resolved)
        if pspec is not None and (pspec.category or "").strip().lower() == "hardware":
            return True
    except Exception:
        pass
    return False


def _spec_index(specs: List[ModuleSpec], name: str) -> int:
    for i, s in enumerate(specs):
        if s.name == name:
            return i
    return -1


def insert_safety_supervisor_if_required(specs: List[ModuleSpec], resolved: str) -> List[ModuleSpec]:
    if _spec_index(specs, "safety_supervisor") >= 0:
        return list(specs)
    names = {s.name for s in specs}
    need = (
        profile_requires_safety_pipeline(resolved)
        or "fake_actuator" in names
        or bool(names & {"hardware_bridge", "motor_driver_backend", "servo_coordinator", "task_graph"})
    )
    if not need:
        return list(specs)
    out = list(specs)
    out.insert(
        0,
        ModuleSpec(
            "safety_supervisor",
            SAFETY_SUPERVISOR_PATH,
            {
                "profile_name": resolved,
                "module_names": tuple(s.name for s in specs),
            },
        ),
    )
    return out


def insert_hardware_rollout_gate_if_required(specs: List[ModuleSpec], resolved: str) -> List[ModuleSpec]:
    if _spec_index(specs, "hardware_rollout_gate") >= 0:
        return list(specs)
    names = {s.name for s in specs}
    need = (
        profile_requires_safety_pipeline(resolved)
        or "fake_actuator" in names
        or bool(names & {"hardware_bridge", "motor_driver_backend", "servo_coordinator", "task_graph"})
    )
    if not need:
        return list(specs)
    out = list(specs)
    sup = _spec_index(out, "safety_supervisor")
    if sup >= 0:
        out.insert(sup + 1, ModuleSpec("hardware_rollout_gate", HARDWARE_ROLLOUT_GATE_PATH, {}))
    else:
        out.insert(0, ModuleSpec("hardware_rollout_gate", HARDWARE_ROLLOUT_GATE_PATH, {}))
    return out


def insert_control_audit_recorder_if_required(specs: List[ModuleSpec], resolved: str) -> List[ModuleSpec]:
    if _spec_index(specs, "control_audit_recorder") >= 0:
        return list(specs)
    if str(os.environ.get("MAMULA_DISABLE_CONTROL_AUDIT", "")).strip().lower() in {"1", "true", "yes"}:
        return list(specs)
    names = {s.name for s in specs}
    need = (
        profile_requires_safety_pipeline(resolved)
        or "fake_actuator" in names
        or bool(names & {"hardware_bridge", "motor_driver_backend", "motion_command_gateway", "safety_supervisor"})
    )
    if not need:
        return list(specs)
    out = list(specs)
    anchor = _spec_index(out, "hardware_rollout_gate")
    if anchor < 0:
        anchor = _spec_index(out, "safety_supervisor")
    spec = ModuleSpec("control_audit_recorder", CONTROL_AUDIT_RECORDER_PATH, {})
    if anchor >= 0:
        out.insert(anchor + 1, spec)
    else:
        out.insert(0, spec)
    return out


def insert_safety_pipeline_if_required(specs: List[ModuleSpec], resolved: str) -> List[ModuleSpec]:
    if _spec_index(specs, "safety_pipeline") >= 0:
        return list(specs)
    names = {s.name for s in specs}
    motion_hw = bool(names & {"hardware_bridge", "motor_driver_backend"})
    need = profile_requires_safety_pipeline(resolved) or ("fake_actuator" in names) or motion_hw
    if not need:
        return list(specs)
    pipe = ModuleSpec("safety_pipeline", SAFETY_PIPELINE_IMPORT_PATH, {})
    out = list(specs)
    ar = _spec_index(out, "action_router")
    if ar >= 0:
        out.insert(ar, pipe)
        return out
    eb = _spec_index(out, "executive_bridge")
    if eb >= 0:
        out.insert(eb, pipe)
        return out
    out.insert(0, pipe)
    return out


# Modules that enrich ``executive.action`` / ``executive.action.authorized`` params must
# initialize before ``executive_bridge`` so in-proc bus subscribers run first.
EXECUTIVE_GATE_MODULES_BEFORE_BRIDGE: tuple[str, ...] = (
    "approval_by_exception_policy",
    "operator_supervised_pick_and_bring",
    "integrated_task_bringup",
    "manipulation_autonomy_retry_recovery",
    "supported_handover_hil",
    "supervised_multi_attempt_delivery",
    "recovery_after_failed_handover",
    "supported_sort_and_putaway",
    "supervised_tidy_zone",
    "supervised_room_sweep",
    "supervised_table_counter_cleaning",
    "clutter_pickup_semantics",
    "battery_charging_and_docking_orchestration",
    "fridge_pantry_inventory_mapping",
    "cabinet_drawer_shelf_putaway_mapping",
    "cross_room_semantic_storage_graph",
    "freshness_expiry_tracking",
    "short_horizon_footstep_planner",
    "receding_horizon_foothold_mpc",
    "stair_ledge_negotiation",
    "end_to_end_household_autonomy_scorecard",
    "kitchen_prep_semantics",
    "meal_ingredient_and_recipe_readiness_memory",
    "meal_plating_and_serving_presentation_policy",
    "meal_prep_manipulation_primitives",
    "kitchen_to_table_closed_loop",
    "supported_tray_and_table_service",
    "appliance_door_drawer_action_primitives",
    "detergent_compartment_affordance_pose_targeting",
)


def ensure_modules_before_executive_bridge(
    specs: List[ModuleSpec],
    module_names: tuple[str, ...] = EXECUTIVE_GATE_MODULES_BEFORE_BRIDGE,
) -> List[ModuleSpec]:
    out = list(specs)
    bridge_idx = _spec_index(out, "executive_bridge")
    if bridge_idx < 0:
        bridge_idx = _spec_index(out, "hardware_bridge")
    if bridge_idx < 0:
        return out
    to_move: List[ModuleSpec] = []
    for name in module_names:
        idx = _spec_index(out, name)
        if idx >= 0 and idx > bridge_idx:
            to_move.append(out[idx])
    if not to_move:
        return out
    for spec in reversed(to_move):
        idx = _spec_index(out, spec.name)
        if idx >= 0:
            out.pop(idx)
    bridge_idx = _spec_index(out, "executive_bridge")
    if bridge_idx < 0:
        bridge_idx = _spec_index(out, "hardware_bridge")
    if bridge_idx < 0:
        return out
    for i, spec in enumerate(to_move):
        out.insert(bridge_idx + i, spec)
    return out


def insert_motion_control_stack_if_required(specs: List[ModuleSpec], resolved: str) -> List[ModuleSpec]:
    """Insert exec.cmd_safe → authorized motion → native goal safety stack."""
    specs = insert_action_transformation_pipeline_if_required(specs, resolved)
    specs = insert_trusted_recovery_authorizer_if_required(specs, resolved)
    names = {s.name for s in specs}
    motion_hw = bool(names & {"hardware_bridge", "motor_driver_backend", "servo_coordinator"})
    need = profile_requires_safety_pipeline(resolved) or ("fake_actuator" in names) or motion_hw
    if not need:
        return ensure_modules_before_executive_bridge(list(specs))
    out = list(specs)
    if _spec_index(out, "safe_command_action_router") < 0:
        router = ModuleSpec(
            "safe_command_action_router",
            SAFE_COMMAND_ACTION_ROUTER_PATH,
            {},
            module_maturity="hil_ready",
            safety_class="critical",
            realtime_safe=False,
            hardware_allowed=False,
        )
        sp = _spec_index(out, "safety_pipeline")
        if sp >= 0:
            out.insert(sp + 1, router)
        else:
            out.insert(0, router)
    if _spec_index(out, "motion_command_gateway") < 0:
        gateway_spec = ModuleSpec(
            "motion_command_gateway",
            MOTION_COMMAND_GATEWAY_PATH,
            {},
            module_maturity="hil_ready",
            safety_class="critical",
            realtime_safe=False,
            hardware_allowed=False,
        )
        fss = _spec_index(out, "first_supported_steps")
        eb = _spec_index(out, "executive_bridge")
        if fss >= 0:
            out.insert(fss + 1, gateway_spec)
        elif eb >= 0:
            out.insert(eb, gateway_spec)
        else:
            out.insert(0, gateway_spec)
    if _spec_index(out, "motion_native_goal_bridge") < 0:
        native_goal_bridge = ModuleSpec(
            "motion_native_goal_bridge",
            MOTION_NATIVE_GOAL_BRIDGE_PATH,
            {},
            module_maturity="hil_ready",
            safety_class="critical",
            realtime_safe=False,
            hardware_allowed=False,
        )
        gateway_index = _spec_index(out, "motion_command_gateway")
        eb = _spec_index(out, "executive_bridge")
        hb = _spec_index(out, "hardware_bridge")
        if gateway_index >= 0:
            out.insert(gateway_index + 1, native_goal_bridge)
        elif eb >= 0:
            out.insert(eb, native_goal_bridge)
        elif hb >= 0:
            out.insert(hb, native_goal_bridge)
        else:
            out.insert(0, native_goal_bridge)
    if _spec_index(out, "actuator_bundle_safety_filter") < 0 and "servo_coordinator" in names:
        flt = ModuleSpec("actuator_bundle_safety_filter", ACTUATOR_BUNDLE_SAFETY_FILTER_PATH, {})
        sc = _spec_index(out, "servo_coordinator")
        out.insert(sc, flt)
    return ensure_modules_before_executive_bridge(out)


def insert_trusted_recovery_authorizer_if_required(specs: List[ModuleSpec], resolved: str) -> List[ModuleSpec]:
    if _spec_index(specs, "trusted_recovery_authorizer") >= 0:
        return list(specs)
    names = {s.name for s in specs}
    need = (
        profile_requires_safety_pipeline(resolved)
        or bool(names & RECOVERY_REQUESTER_MODULE_NAMES)
        or bool(names & {"motion_command_gateway", "executive_bridge", "hardware_bridge", "motor_driver_backend"})
    )
    if not need:
        return list(specs)
    authorizer = ModuleSpec(
        "trusted_recovery_authorizer",
        TRUSTED_RECOVERY_AUTHORIZER_PATH,
        {},
        module_maturity="hil_ready",
        safety_class="critical",
        realtime_safe=False,
        hardware_allowed=False,
    )
    out = list(specs)
    for anchor in ("motion_command_gateway", "executive_bridge", "hardware_bridge"):
        idx = _spec_index(out, anchor)
        if idx >= 0:
            out.insert(idx, authorizer)
            return out
    for anchor in ("fall_recovery", "locomotion_supervisor", "manipulation_autonomy_retry_recovery"):
        idx = _spec_index(out, anchor)
        if idx >= 0:
            out.insert(idx, authorizer)
            return out
    out.append(authorizer)
    return out


def insert_action_transformation_pipeline_if_required(specs: List[ModuleSpec], resolved: str) -> List[ModuleSpec]:
    if _spec_index(specs, "action_transformation_pipeline") >= 0:
        return list(specs)
    names = {s.name for s in specs}
    need = (
        profile_requires_safety_pipeline(resolved)
        or "action_router" in names
        or "executive_bridge" in names
        or bool(names & {"hardware_bridge", "motor_driver_backend", "servo_coordinator"})
    )
    if not need:
        return list(specs)
    pipe = ModuleSpec(
        "action_transformation_pipeline",
        ACTION_TRANSFORMATION_PIPELINE_PATH,
        {},
        module_maturity="hil_ready",
        safety_class="high_risk",
        realtime_safe=False,
        hardware_allowed=False,
    )
    out = list(specs)
    for anchor in ("motion_command_gateway", "executive_bridge", "hardware_bridge"):
        idx = _spec_index(out, anchor)
        if idx >= 0:
            out.insert(idx, pipe)
            return out
    out.append(pipe)
    return out


def validate_safety_pipeline_gate(specs: List[ModuleSpec], resolved: str) -> None:
    names = {s.name for s in specs}
    if "safety_pipeline" in names:
        return
    if profile_requires_safety_pipeline(resolved) or "fake_actuator" in names:
        raise RuntimeError(
            f"profile {resolved!r} requires module 'safety_pipeline' in the stack "
            "(exec.cmd must pass through SafetyPipelineModule before exec.cmd_safe)."
        )


def validate_hardware_protocol_gate(specs: List[ModuleSpec], resolved: str) -> None:
    if not profile_requires_safety_pipeline(resolved):
        return
    names = {s.name for s in specs}
    uses_native_motion = bool(names & {"motor_driver_backend", "hardware_bridge"})
    if not uses_native_motion:
        return
    if "hardware_protocol_bridge" not in names:
        raise RuntimeError(
            f"profile {resolved!r} includes motor_driver_backend or hardware_bridge but not "
            "hardware_protocol_bridge (hardware_command_protocol bus path required)."
        )


@dataclass(frozen=True)
class ModuleMaturityResolved:
    module_maturity: MaturityName
    safety_class: SafetyName
    realtime_safe: bool
    hardware_allowed: bool
    tags: FrozenSet[str]


def _merge_meta(base: ModuleMaturityResolved, spec: ModuleSpec) -> ModuleMaturityResolved:
    m = normalize_maturity_name(spec.module_maturity or base.module_maturity)
    s = spec.safety_class or base.safety_class
    rt = base.realtime_safe if spec.realtime_safe is None else bool(spec.realtime_safe)
    hw = base.hardware_allowed if spec.hardware_allowed is None else bool(spec.hardware_allowed)
    return ModuleMaturityResolved(
        module_maturity=m,
        safety_class=str(s).strip().lower(),
        realtime_safe=rt,
        hardware_allowed=hw,
        tags=base.tags,
    )


def _heuristic_base(spec: ModuleSpec) -> ModuleMaturityResolved:
    path = (spec.import_path or "").lower()
    name = (spec.name or "").lower()

    tags: set[str] = set()
    if "fake_actuator" in path or name.startswith("fake_"):
        tags.add("fake_actuator")
    if "isaac_sim_bridge" in path:
        tags.add("offline_stub_bridge")
    if "roadmap_stack_stubs" in path or "_stub" in path or "stub_module" in path or name.endswith("_stub"):
        tags.add("roadmap_or_generated_stub")
    if "placeholder" in path:
        tags.add("placeholder_perception")

    if tags & {"fake_actuator"}:
        return ModuleMaturityResolved("stub", "high_risk", False, True, frozenset(tags))
    if tags & {"offline_stub_bridge"}:
        return ModuleMaturityResolved("sim_ready", "low_risk", False, False, frozenset(tags))
    if tags & {"roadmap_or_generated_stub"}:
        return ModuleMaturityResolved("stub", "non_motion", False, False, frozenset(tags))

    if name in {
        "object_pose_estimation",
        "scene_understanding",
        "vision_perception",
        "vision_web_identity",
    }:
        tags.add("placeholder_perception")
        return ModuleMaturityResolved("sim_ready", "low_risk", False, False, frozenset(tags))

    if name in {
        "hardware_bridge",
        "motor_driver_backend",
        "hardware_protocol_bridge",
        "native_command_frame_hardware_bridge",
        "vendor_servo_protocol",
        "servo_coordinator",
    } or "real_robot_bridge_module" in path:
        return ModuleMaturityResolved("hardware_ready", "high_risk", False, True, frozenset(tags))

    if name in {"safety_pipeline", "reflex"}:
        return ModuleMaturityResolved("hil_ready", "critical", False, False, frozenset(tags))
    if name == "hardware_safety_watchdog":
        return ModuleMaturityResolved("hil_ready", "critical", False, True, frozenset(tags))

    if name in {"action_router", "task_graph", "task_primitive", "executive_bridge"}:
        return ModuleMaturityResolved("sim_ready", "low_risk", False, False, frozenset(tags))

    if any(k in path for k in ("locomotion", "balance", "fall_recovery", "capture_step", "whole_body")):
        return ModuleMaturityResolved("experimental", "high_risk", False, False, frozenset(tags))

    if any(k in path for k in ("voice", "stt", "tts")):
        return ModuleMaturityResolved("experimental", "non_motion", False, False, frozenset(tags))

    return ModuleMaturityResolved("experimental", "non_motion", False, False, frozenset(tags))


@lru_cache(maxsize=1)
def _registry_overrides() -> dict[str, ModuleMaturityResolved]:
    o: dict[str, ModuleMaturityResolved] = {
        "memory": ModuleMaturityResolved("production", "non_motion", True, False, frozenset()),
        "reasoning": ModuleMaturityResolved("experimental", "non_motion", False, False, frozenset({"llm_planner"})),
        "slam_map_stub": ModuleMaturityResolved("stub", "non_motion", False, False, frozenset({"roadmap_stub"})),
        "navigation_pose_bridge": ModuleMaturityResolved("stub", "non_motion", False, False, frozenset({"roadmap_stub"})),
        "dynamic_obstacle_layer": ModuleMaturityResolved("stub", "non_motion", False, False, frozenset({"roadmap_stub"})),
        "learning_signal_stub": ModuleMaturityResolved("stub", "non_motion", False, False, frozenset({"roadmap_stub"})),
        "multimodal_context_stub": ModuleMaturityResolved("stub", "non_motion", False, False, frozenset({"roadmap_stub"})),
        "multimodal_observation_bridge": ModuleMaturityResolved("experimental", "non_motion", False, False, frozenset({"structured_grounding", "non_executable"})),
        "safety_proximity_stub": ModuleMaturityResolved("stub", "low_risk", False, False, frozenset({"roadmap_stub"})),
        "fleet_coordination_stub": ModuleMaturityResolved("stub", "non_motion", False, False, frozenset({"roadmap_stub"})),
    }
    return o


def resolve_module_maturity(spec: ModuleSpec) -> ModuleMaturityResolved:
    base = _registry_overrides().get(spec.name) or _heuristic_base(spec)
    merged = _merge_meta(base, spec)
    from core.runtime.module_readiness_registry import apply_domain_override

    return apply_domain_override(spec.name, merged)


def stack_requires_hardware_shadow(specs: List[ModuleSpec]) -> bool:
    for spec in specs:
        meta = resolve_module_maturity(spec)
        if meta.hardware_allowed:
            return True
        if meta.safety_class in {"high_risk", "critical"}:
            return True
        path = (spec.import_path or "").lower()
        if "motor_driver_backend_module" in path or "real_robot_bridge_module" in path:
            return True
    return False


def profile_requires_production_maturity_gate(
    resolved: str,
    *,
    requested_profile: Optional[str] = None,
    specs: Optional[List[ModuleSpec]] = None,
) -> bool:
    res = (resolved or "").strip().lower()
    req = (requested_profile or "").strip().lower()

    if res == "production":
        return True

    if res == "embodied_operator_supervised_pick_and_bring":
        return True

    if req:
        try:
            from core.runtime.profiles.operator_profiles import OPERATOR_PROFILE_CANONICAL, operator_surface_meta

            canon = OPERATOR_PROFILE_CANONICAL.get(req)
            if canon:
                meta = operator_surface_meta().get(canon) or {}
                if str(meta.get("safety_level") or "").strip().lower() == "production_supervised":
                    return True
        except Exception:
            pass

    if "production" in res or "production" in req:
        return True

    try:
        from core.runtime.profiles.registry import profile_registry

        pspec = profile_registry().get(resolved)
        if pspec is not None and (pspec.category or "").strip().lower() == "hardware":
            return True
    except Exception:
        pass

    if specs:
        names = {s.name for s in specs}
        if names & {"hardware_bridge", "motor_driver_backend"}:
            return True

    return False


def _production_maturity_error(spec: ModuleSpec, meta: ModuleMaturityResolved) -> str | None:
    """Field-motion gate: strict on hardware paths; software/manipulation may stay sim_ready."""
    if meta.module_maturity == "stub":
        return f"stub module in production stack: {spec.name!r} ({spec.import_path})"
    if spec.name in _MOTION_HARDWARE_MODULE_NAMES:
        allowed = {"hardware_ready", "production"}
        if spec.name == "hardware_safety_watchdog":
            allowed = allowed | {"hil_ready"}
        if meta.module_maturity not in allowed:
            return (
                f"hardware path module requires {sorted(allowed)!r} maturity, "
                f"got {meta.module_maturity!r}: {spec.name!r} ({spec.import_path})"
            )
    elif meta.hardware_allowed and meta.module_maturity in {"experimental", "sim_ready"}:
        return (
            f"motion-capable module {meta.module_maturity!r} blocked on production stack: "
            f"{spec.name!r} ({spec.import_path})"
        )
    return None


def _production_readiness_axis_error(spec: ModuleSpec, meta: ModuleMaturityResolved) -> str | None:
    from core.runtime.module_readiness_registry import readiness_axes_for_module

    software, evidence = readiness_axes_for_module(spec.name, meta)
    if software == "draft":
        return (
            f"draft software maturity blocked on production stack: {spec.name!r} "
            f"({spec.import_path}); software={software!r} evidence={evidence!r}"
        )

    if spec.name in _MOTION_HARDWARE_MODULE_NAMES:
        allowed = {"robot", "soak"}
        if spec.name == "hardware_safety_watchdog":
            allowed = allowed | {"hil"}
        if evidence not in allowed:
            return (
                f"hardware path module requires deployment evidence {sorted(allowed)!r}, "
                f"got software={software!r} evidence={evidence!r}: {spec.name!r} ({spec.import_path})"
            )

    if meta.safety_class == "critical" and evidence not in {"hil", "robot", "soak"}:
        return (
            f"critical module requires HIL or better deployment evidence, "
            f"got software={software!r} evidence={evidence!r}: {spec.name!r} ({spec.import_path})"
        )

    return None


def validate_production_profile_stack(specs: List[ModuleSpec], rt: Any) -> None:
    """Hard gate for production-class profiles — realistic maturity/evidence only."""
    if _skip_production_maturity_gate():
        return

    errors: List[str] = []

    for spec in specs:
        meta = resolve_module_maturity(spec)
        if spec.name.startswith("fake_"):
            errors.append(
                f"fake-prefixed module name blocked in production-maturity stack "
                f"(use sim/plant/harness naming): {spec.name!r} ({spec.import_path})"
            )
            continue
        if meta.module_maturity == "stub":
            errors.append(f"stub module in production stack: {spec.name!r} ({spec.import_path})")
        mat_err = _production_maturity_error(spec, meta)
        if mat_err:
            errors.append(mat_err)
        axis_err = _production_readiness_axis_error(spec, meta)
        if axis_err:
            errors.append(axis_err)
        if "offline_stub_bridge" in meta.tags:
            errors.append(f"offline / stub sim bridge blocked in production: {spec.name!r} ({spec.import_path})")
        if "placeholder_perception" in meta.tags:
            errors.append(f"placeholder perception module blocked in production: {spec.name!r} ({spec.import_path})")

    if stack_requires_hardware_shadow(specs) and not _shadow_commands_enabled():
        errors.append(
            "production stack includes motion/hardware modules but MAMULA_HARDWARE_SHADOW_COMMANDS is not enabled "
            "(shadow command logging / suppressed send required before field bring-up)."
        )

    names = {s.name for s in specs}
    if "safety_supervisor" not in names:
        errors.append(
            "production stack must include module 'safety_supervisor' "
            "(authoritative BOOT→ACTIVE safety state machine)"
        )
    if "safety_pipeline" not in names:
        errors.append(
            "production stack must include module 'safety_pipeline' (exec.cmd → exec.cmd_safe central gate)"
        )
    if names & {"hardware_bridge", "motor_driver_backend"} and "hardware_safety_watchdog" not in names:
        errors.append(
            "production stack includes hardware_bridge or motor_driver_backend but not "
            "hardware_safety_watchdog (software safety watchdog module required)."
        )

    cfg = getattr(rt, "cfg", None)
    if cfg is not None and not bool(getattr(cfg, "watchdog_enabled", True)):
        errors.append("RuntimeConfig.watchdog_enabled is False — blocked for production profile.")

    if errors:
        raise RuntimeError("production maturity gate failed:\n- " + "\n- ".join(errors))


def maturity_dict(meta: ModuleMaturityResolved) -> dict[str, Any]:
    return {
        "MODULE_MATURITY": meta.module_maturity,
        "SAFETY_CLASS": meta.safety_class,
        "REALTIME_SAFE": meta.realtime_safe,
        "HARDWARE_ALLOWED": meta.hardware_allowed,
        "tags": sorted(meta.tags),
    }
