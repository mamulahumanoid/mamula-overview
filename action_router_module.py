from __future__ import annotations

import time
from typing import Any, Dict

from core.services.voice_command_risk import aggregate_command_risk
from core.control.motion_planner import (
    build_executive_action_from_motion_request,
    motion_via_executive_enabled,
)
from core.contract.actions import ActionSpec, make_action
from core.contract.commands import CommandIssued
from core.contract.lifecycle_readiness_v1 import (
    CAPABILITY_MOTION_ALL,
    CAPABILITY_VISUAL_PICK,
    CAPABILITY_WALKING,
    capability_snapshot,
    infer_camera_present,
)
from core.contract.message_envelope_v1 import payload_only
from core.contract.types import Meta
from core.modules.robot.approval_by_exception_policy_module import build_approval_policy_baseline
from core.utils.failure_snapshot import write_failure_snapshot
from core.utils.locale_resolution import resolve_voice_lang


def now_ms() -> int:
    return int(time.time() * 1000)


_ACTION_ALIASES = {
    "say": "speech",
    "speak": "speech",
    "tts": "speech",
    "voice": "speech",
    "voice.say": "speech",
    "speech": "speech",
    "memorywrite": "memory_write",
    "write_memory": "memory_write",
    "mem_write": "memory_write",
    "memory_write": "memory_write",
    "memoryquery": "memory_query",
    "query_memory": "memory_query",
    "read_memory": "memory_query",
    "mem_query": "memory_query",
    "memory_query": "memory_query",
    "move": "motion",
    "walk": "motion",
    "turn": "motion",
    "motion": "motion",
    "sweep": "sweep_floor",
    "clean": "clean_zone",
    "cleaning": "clean_zone",
    "wipe": "wipe_surface",
    "surface_wipe": "wipe_surface",
    "wipe_table": "wipe_surface",
    "wipe_counter": "wipe_surface",
    "clean_table": "wipe_surface",
    "clean_counter": "wipe_surface",
    "attach_tool": "attach_tool",
    "detach_tool": "detach_tool",
    "putaway": "place_object",
    "put_away": "place_object",
    "place": "place_object",
    "sort": "place_object",
    "prepare_tray": "prepare_tray",
    "tray_service": "serve_table",
    "serve": "serve_table",
    "serve_table": "serve_table",
    "table_service": "serve_table",
    "kitchen_prep": "prepare_tray",
    "clear_table": "clear_table",
    "clear_dishes": "clear_table",
    "bus_table": "clear_table",
    "reset_table": "reset_table",
    "table_reset": "reset_table",
    "collect_laundry": "collect_laundry",
    "laundry_collect": "collect_laundry",
    "gather_laundry": "collect_laundry",
    "dropoff_laundry": "dropoff_laundry",
    "laundry_dropoff": "dropoff_laundry",
    "laundry_sort": "dropoff_laundry",
    "laundry_putaway": "dropoff_laundry",
    "load_washer": "load_washer",
    "washer_load": "load_washer",
    "add_detergent": "add_detergent",
    "detergent": "add_detergent",
    "start_washer": "start_washer",
    "run_washer": "start_washer",
    "power_on_tool": "power_on_tool",
    "power_off_tool": "power_off_tool",
    "load_dishwasher": "load_dishwasher",
    "dishwasher_load": "load_dishwasher",
    "add_dishwasher_detergent": "add_dishwasher_detergent",
    "dishwasher_detergent": "add_dishwasher_detergent",
    "start_dishwasher": "start_dishwasher",
    "run_dishwasher": "start_dishwasher",
    "power_on_device": "power_on_device",
    "power_off_device": "power_off_device",
    "turn_on_tv": "power_on_device",
    "power_on_tv": "power_on_device",
    "open_appliance_door": "open_appliance_door",
    "close_appliance_door": "close_appliance_door",
    "open_balcony_door": "open_balcony_door",
    "close_balcony_door": "close_balcony_door",
    "open_door": "open_door",
    "close_door": "close_door",
    "open_curtain": "open_curtain",
    "close_curtain": "close_curtain",
    "open_blind": "open_blind",
    "close_blind": "close_blind",
    "open_shutter": "open_shutter",
    "close_shutter": "close_shutter",
    "open_awning": "open_awning",
    "close_awning": "close_awning",
    "open_garage_door": "open_garage_door",
    "close_garage_door": "close_garage_door",
    "open_sliding_door": "open_sliding_door",
    "close_sliding_door": "close_sliding_door",
    "open_vent": "open_vent",
    "close_vent": "close_vent",
    "open_display_shutter": "open_display_shutter",
    "close_display_shutter": "close_display_shutter",
    "open_curtain_track": "open_curtain_track",
    "close_curtain_track": "close_curtain_track",
    "open_window": "open_window",
    "close_window": "close_window",
    "open_drawer": "open_drawer",
    "close_drawer": "close_drawer",
    "open_cabinet": "open_cabinet",
    "close_cabinet": "close_cabinet",
    "open_detergent_drawer": "open_detergent_drawer",
    "close_detergent_drawer": "close_detergent_drawer",
    "open_dishwasher_detergent_compartment": "open_dishwasher_detergent_compartment",
    "close_dishwasher_detergent_compartment": "close_dishwasher_detergent_compartment",
    "run_domestic_routine": "run_domestic_routine",
    "domestic_routine": "run_domestic_routine",
    "dock_robot": "dock_robot",
    "dock": "dock_robot",
    "start_charging": "start_charging",
    "charge": "start_charging",
    "stop_charging": "stop_charging",
    "tv_on": "power_on_device",
    "turn_off_tv": "power_off_device",
    "power_off_tv": "power_off_device",
    "tv_off": "power_off_device",
    "turn_on_vacuum": "power_on_tool",
    "turn_off_vacuum": "power_off_tool",
    "vacuum": "sweep_floor",
    "vacuum_floor": "sweep_floor",
    "run_weekly_household_plan": "run_weekly_household_plan",
    "weekly_household_plan": "run_weekly_household_plan",
    "weekly_plan": "run_weekly_household_plan",
    "run_restock_planner": "run_restock_planner",
    "restock": "run_restock_planner",
    "shopping": "run_restock_planner",
    "shopping_restock": "run_restock_planner",
    "take_out_trash": "take_out_trash",
    "trash": "take_out_trash",
    "sort_recycling": "sort_recycling",
    "recycling": "sort_recycling",
    "run_garbage_recycling_workflow": "run_garbage_recycling_workflow",
    "garbage_recycling": "run_garbage_recycling_workflow",
    "run_household_mission_dashboard": "run_household_mission_dashboard",
    "mission_dashboard": "run_household_mission_dashboard",
    "dashboard": "run_household_mission_dashboard",
    "accept_home_delivery": "accept_home_delivery",
    "delivery_acceptance": "accept_home_delivery",
    "run_home_entry_delivery_workflow": "run_home_entry_delivery_workflow",
    "home_entry_delivery": "run_home_entry_delivery_workflow",
    "run_storage_putaway_mapping": "run_storage_putaway_mapping",
    "storage_putaway_mapping": "run_storage_putaway_mapping",
    "cabinet_putaway_mapping": "run_storage_putaway_mapping",
    "run_adaptive_routine_optimizer": "run_adaptive_routine_optimizer",
    "adaptive_routine_optimizer": "run_adaptive_routine_optimizer",
    "optimize_routine": "run_adaptive_routine_optimizer",
    "run_delivery_item_classification": "run_delivery_item_classification",
    "delivery_item_classification": "run_delivery_item_classification",
    "invoice_receipt_memory": "run_delivery_item_classification",
    "run_fridge_pantry_inventory_mapping": "run_fridge_pantry_inventory_mapping",
    "fridge_inventory_mapping": "run_fridge_pantry_inventory_mapping",
    "pantry_inventory_mapping": "run_fridge_pantry_inventory_mapping",
    "run_cross_room_storage_graph": "run_cross_room_storage_graph",
    "cross_room_storage_graph": "run_cross_room_storage_graph",
    "semantic_storage_graph": "run_cross_room_storage_graph",
    "run_invoice_expense_memory": "run_invoice_expense_memory",
    "invoice_expense_memory": "run_invoice_expense_memory",
    "expense_category_memory": "run_invoice_expense_memory",
    "run_freshness_expiry_tracking": "run_freshness_expiry_tracking",
    "freshness_expiry_tracking": "run_freshness_expiry_tracking",
    "expiry_tracking": "run_freshness_expiry_tracking",
    "run_procurement_to_storage_closed_loop": "run_procurement_to_storage_closed_loop",
    "procurement_storage_closed_loop": "run_procurement_to_storage_closed_loop",
    "procurement_closed_loop": "run_procurement_to_storage_closed_loop",
    "run_meal_recipe_readiness": "run_meal_recipe_readiness",
    "meal_recipe_readiness": "run_meal_recipe_readiness",
    "recipe_readiness": "run_meal_recipe_readiness",
    "run_fridge_spoilage_monitor": "run_fridge_spoilage_monitor",
    "fridge_spoilage_monitor": "run_fridge_spoilage_monitor",
    "spoilage_monitor": "run_fridge_spoilage_monitor",
    "run_kitchen_to_table_closed_loop": "run_kitchen_to_table_closed_loop",
    "kitchen_to_table_closed_loop": "run_kitchen_to_table_closed_loop",
    "kitchen_to_table": "run_kitchen_to_table_closed_loop",
    "run_meal_prep_primitives": "run_meal_prep_primitives",
    "meal_prep_primitives": "run_meal_prep_primitives",
    "prep_primitives": "run_meal_prep_primitives",
    "unload_dishwasher": "unload_dishwasher",
    "dishwasher_unload": "unload_dishwasher",
    "run_dish_loading_unloading_closed_loop": "run_dish_loading_unloading_closed_loop",
    "dish_loading_unloading_closed_loop": "run_dish_loading_unloading_closed_loop",
    "dish_closed_loop": "run_dish_loading_unloading_closed_loop",
    "run_household_semantic_task_graph": "run_household_semantic_task_graph",
    "household_semantic_task_graph": "run_household_semantic_task_graph",
    "semantic_task_graph": "run_household_semantic_task_graph",
    "run_mini_household_mission_chain": "run_mini_household_mission_chain",
    "mini_household_mission_chain": "run_mini_household_mission_chain",
    "open_cold_storage": "open_cold_storage",
    "close_cold_storage": "close_cold_storage",
    "run_cold_chain_handling": "run_cold_chain_handling",
    "cold_chain": "run_cold_chain_handling",
    "run_meal_plating_policy": "run_meal_plating_policy",
    "meal_plating_policy": "run_meal_plating_policy",
    "plating": "run_meal_plating_policy",
    "run_household_autonomy_scorecard": "run_household_autonomy_scorecard",
    "autonomy_scorecard": "run_household_autonomy_scorecard",
    "scorecard": "run_household_autonomy_scorecard",
}


_EXECUTIVE_ACTION_TYPES = {
    "say",
    "go_to_location",
    "find_object",
    "pick_object",
    "bring_object_to_user",
    "turn_in_place",
    "walk_steps",
    "move_linear",
    "follow_user",
    "handover",
    "stop",
    "set_mode",
    "run_skill",
    "fetch_object",
    "deliver_object",
    "find_pick_and_bring",
    "attach_tool",
    "detach_tool",
    "sweep_floor",
    "clean_zone",
    "wipe_surface",
    "place_object",
    "put_away_object",
    "prepare_tray",
    "serve_table",
    "clear_table",
    "reset_table",
    "collect_laundry",
    "dropoff_laundry",
    "load_washer",
    "add_detergent",
    "start_washer",
    "load_dishwasher",
    "add_dishwasher_detergent",
    "start_dishwasher",
    "power_on_tool",
    "power_off_tool",
    "power_on_device",
    "power_off_device",
    "open_appliance_door",
    "close_appliance_door",
    "open_balcony_door",
    "close_balcony_door",
    "open_door",
    "close_door",
    "open_curtain",
    "close_curtain",
    "open_blind",
    "close_blind",
    "open_shutter",
    "close_shutter",
    "open_awning",
    "close_awning",
    "open_garage_door",
    "close_garage_door",
    "open_sliding_door",
    "close_sliding_door",
    "open_vent",
    "close_vent",
    "open_display_shutter",
    "close_display_shutter",
    "open_curtain_track",
    "close_curtain_track",
    "open_window",
    "close_window",
    "open_drawer",
    "close_drawer",
    "open_cabinet",
    "close_cabinet",
    "open_detergent_drawer",
    "close_detergent_drawer",
    "open_dishwasher_detergent_compartment",
    "close_dishwasher_detergent_compartment",
    "run_domestic_routine",
    "dock_robot",
    "start_charging",
    "stop_charging",
    "run_weekly_household_plan",
    "run_restock_planner",
    "take_out_trash",
    "sort_recycling",
    "run_garbage_recycling_workflow",
    "run_household_mission_dashboard",
    "accept_home_delivery",
    "run_home_entry_delivery_workflow",
    "run_storage_putaway_mapping",
    "run_adaptive_routine_optimizer",
    "run_delivery_item_classification",
    "run_fridge_pantry_inventory_mapping",
    "run_cross_room_storage_graph",
    "run_invoice_expense_memory",
    "run_freshness_expiry_tracking",
    "run_procurement_to_storage_closed_loop",
    "run_meal_recipe_readiness",
    "run_fridge_spoilage_monitor",
    "run_kitchen_to_table_closed_loop",
    "run_meal_prep_primitives",
    "unload_dishwasher",
    "run_dish_loading_unloading_closed_loop",
    "run_household_semantic_task_graph",
    "run_mini_household_mission_chain",
    "open_cold_storage",
    "close_cold_storage",
    "run_cold_chain_handling",
    "run_meal_plating_policy",
    "run_household_autonomy_scorecard",
}

_LIFECYCLE_NON_MOTION_ACTION_TYPES = frozenset(
    {
        "say",
        "speech",
        "set_mode",
        "stop",
        "memory_write",
        "memory_query",
    }
)

_LIFECYCLE_LOCOMOTION_ACTION_TYPES = frozenset(
    {
        "go_to_location",
        "walk_steps",
        "move_linear",
        "turn_in_place",
        "follow_user",
        "dock_robot",
        "sweep_floor",
        "clean_zone",
    }
)

_LIFECYCLE_VISUAL_PICK_ACTION_TYPES = frozenset(
    {
        "pick_object",
        "find_object",
        "find_pick_and_bring",
        "fetch_object",
        "deliver_object",
        "bring_object_to_user",
    }
)


class ActionRouterModule:
    """
    Canonical action bridge.

    Supported inputs:
      - behavior.node_ready   -> ActionSpec -> executive.action
      - action.request        -> legacy / canonical actions -> execution topics
      - action_router.query

    Behavior:
      - SpeechAction / speech => voice.say
      - MemoryWriteAction     => memory.write
      - MemoryQueryAction     => memory.query
      - MotionAction          => executive.action (skill_planner) when MAMULA_MOTION_VIA_EXECUTIVE=1,
                                else legacy exec.cmd → exec.cmd_safe
      - ActionSpec envelope   => executive.action

    Also emits lifecycle + normalized action.result events so higher layers can
    observe routing and execution using a single contract.
    """

    name = "action_router_module"

    def __init__(self, bus, rt):
        self.bus = bus
        self.rt = rt
        self.last_action: Dict[str, Any] | None = None
        self._pending_by_action_id: Dict[str, Dict[str, Any]] = {}
        self._pending_by_cmd_id: Dict[str, Dict[str, Any]] = {}
        self._voice_task_risk_by_task_id: Dict[str, Dict[str, Any]] = {}
        self._voice_task_risk_by_session: Dict[str, Dict[str, Any]] = {}
        self._last_hardware_telemetry: Dict[str, Any] = {}
        self._last_robot_diagnostics: Dict[str, Any] = {}
        self._last_watchdog_status: Dict[str, Any] = {}
        self._last_operator_policy: Dict[str, Any] = build_approval_policy_baseline()
        self._last_lifecycle_status: Dict[str, Any] | None = None

        bus.subscribe_payload("behavior.node_ready", self.on_behavior_node_ready)
        bus.subscribe_payload("action.request", self.on_action_request)
        bus.subscribe_payload("action_router.query", self.on_query)
        bus.subscribe_payload("voice.task", self.on_voice_task)
        bus.subscribe_payload("hardware.telemetry", self.on_hardware_telemetry)
        bus.subscribe_payload("robot.diagnostics.status", self.on_robot_diagnostics_status)
        bus.subscribe_payload("hardware.watchdog_status", self.on_hardware_watchdog_status)
        bus.subscribe_payload("operator.supervision.policy.result", self.on_operator_policy_result)
        bus.subscribe_payload("lifecycle.status", self.on_lifecycle_status)

        bus.subscribe_payload("memory.result", self.on_memory_result)
        bus.subscribe_payload("memory.query.result", self.on_memory_result)
        bus.subscribe_payload("exec.done", self.on_exec_done)
        bus.subscribe_payload("exec.timeout", self.on_exec_timeout)
        bus.subscribe_payload("executive.action_started", self.on_executive_action_started)
        bus.subscribe_payload("executive.action_result", self.on_executive_action_result)

    def tick(self):
        self.rt.beat(self.name)

    def _msg_to_dict(self, msg: Any) -> Dict[str, Any]:
        if isinstance(msg, dict):
            payload = payload_only(msg)
            return dict(payload) if payload else dict(msg)
        if hasattr(msg, "to_dict"):
            try:
                raw = msg.to_dict()
                if isinstance(raw, dict):
                    return dict(raw)
            except Exception:
                pass
        return {}

    def _normalize_action_type(self, payload: Dict[str, Any]) -> str:
        raw = str(payload.get("action_type", "") or "").strip()
        raw_fold = raw.lower().replace("-", "_").replace(" ", "_")
        if raw_fold in _ACTION_ALIASES:
            return _ACTION_ALIASES[raw_fold]
        if raw_fold in _EXECUTIVE_ACTION_TYPES:
            return raw_fold
        if not raw_fold and payload.get("name"):
            return "motion"
        return raw_fold

    def _meta_from(self, payload: Dict[str, Any], default_source: str = "action_router") -> Dict[str, Any]:
        raw = payload.get("meta") or {}
        if hasattr(raw, "to_dict"):
            raw = raw.to_dict()
        elif not isinstance(raw, dict):
            raw = {
                "id": str(getattr(raw, "id", "") or ""),
                "ts_ms": int(getattr(raw, "ts_ms", now_ms()) or now_ms()),
                "seq": int(getattr(raw, "seq", 0) or 0),
                "source": str(getattr(raw, "source", default_source) or default_source),
                "correlation_id": str(getattr(raw, "correlation_id", "") or ""),
                "session_id": str(getattr(raw, "session_id", "") or ""),
                "turn_id": str(getattr(raw, "turn_id", "") or ""),
                "trace_id": str(getattr(raw, "trace_id", "") or ""),
                "parent_id": str(getattr(raw, "parent_id", "") or ""),
                "extra": dict(getattr(raw, "extra", {}) or {}),
            }
        meta = dict(raw or {})
        meta.setdefault("id", f"meta_{now_ms()}")
        meta.setdefault("ts_ms", now_ms())
        meta.setdefault("seq", 0)
        meta.setdefault("source", default_source)
        meta.setdefault("correlation_id", str(payload.get("task_id", "") or payload.get("action_id", "") or ""))
        meta.setdefault("session_id", "")
        meta.setdefault("turn_id", "")
        meta.setdefault("trace_id", meta.get("turn_id", "") or meta.get("correlation_id", "") or "")
        meta.setdefault("parent_id", "")
        extra = meta.get("extra")
        meta["extra"] = dict(extra or {}) if isinstance(extra, dict) else {}
        return meta

    def _remember_voice_task_risk(self, msg: Any):
        text = ""
        if isinstance(msg, dict):
            text = str(msg.get("text", "") or "").strip()
            raw_meta = msg.get("meta", {}) or {}
            if hasattr(raw_meta, "to_dict"):
                raw_meta = raw_meta.to_dict()
        else:
            text = str(getattr(msg, "text", "") or "").strip()
            raw_meta = getattr(msg, "meta", None)
            if hasattr(raw_meta, "to_dict"):
                raw_meta = raw_meta.to_dict()
            elif raw_meta is not None:
                raw_meta = {
                    "id": str(getattr(raw_meta, "id", "") or ""),
                    "source": str(getattr(raw_meta, "source", "") or ""),
                    "correlation_id": str(getattr(raw_meta, "correlation_id", "") or ""),
                    "session_id": str(getattr(raw_meta, "session_id", "") or ""),
                    "extra": dict(getattr(raw_meta, "extra", {}) or {}),
                }
        meta = dict(raw_meta or {}) if isinstance(raw_meta, dict) else {}
        extra = dict(meta.get("extra", {}) or {}) if isinstance(meta.get("extra"), dict) else {}
        source = str(meta.get("source", "") or "")
        explicit_level = int(extra.get("aggregate_command_risk_level", extra.get("command_risk_level", 0)) or 0)
        guard_checked = bool(extra.get("physical_risk_gate_checked", False))
        if not guard_checked and source != "http_voice_router":
            return
        risk = aggregate_command_risk([text]) if text else {}
        aggregate_level = int(extra.get("aggregate_command_risk_level", risk.get("max_level", 0)) or 0)
        context = {
            "aggregate_command_risk_level": aggregate_level,
            "aggregate_command_risk_label": str(extra.get("aggregate_command_risk_label", risk.get("max_label", "")) or ""),
            "command_risk_level": int(extra.get("command_risk_level", explicit_level) or explicit_level),
            "command_risk_label": str(extra.get("command_risk_label", "") or ""),
            "wake_required": bool(extra.get("wake_required", aggregate_level >= 3)),
            "wake_gate_passed": bool(extra.get("wake_gate_passed", False)),
            "approval_required": bool(extra.get("approval_required", False)),
            "approval_confirmed": bool(extra.get("approval_confirmed", False)),
            "user_confirmation_required": bool(extra.get("user_confirmation_required", aggregate_level >= 4)),
            "physical_risk_gate_checked": bool(extra.get("physical_risk_gate_checked", guard_checked)),
            "operator_policy_required": bool(extra.get("operator_policy_required", aggregate_level >= 3)),
            "telemetry_fresh_required": bool(extra.get("telemetry_fresh_required", aggregate_level >= 3)),
            "safety_ready_required": bool(extra.get("safety_ready_required", aggregate_level >= 3)),
            "source": source,
            "text": text,
            "ts_ms": int(meta.get("ts_ms", now_ms()) or now_ms()),
        }
        task_id = str(meta.get("correlation_id", "") or meta.get("id", "") or "")
        session_id = str(meta.get("session_id", "") or "")
        if task_id:
            self._voice_task_risk_by_task_id[task_id] = context
        if session_id:
            self._voice_task_risk_by_session[session_id] = context

    def _risk_context_for_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        meta = self._meta_from(payload)
        extra = dict(meta.get("extra", {}) or {}) if isinstance(meta.get("extra"), dict) else {}
        explicit_level = int(extra.get("aggregate_command_risk_level", extra.get("command_risk_level", 0)) or 0)
        if explicit_level > 0 or bool(extra.get("physical_risk_gate_checked", False)):
            return {
                "aggregate_command_risk_level": explicit_level,
                "aggregate_command_risk_label": str(extra.get("aggregate_command_risk_label", "") or ""),
                "command_risk_level": int(extra.get("command_risk_level", explicit_level) or explicit_level),
                "command_risk_label": str(extra.get("command_risk_label", "") or ""),
                "wake_required": bool(extra.get("wake_required", explicit_level >= 3)),
                "wake_gate_passed": bool(extra.get("wake_gate_passed", False)),
                "approval_required": bool(extra.get("approval_required", False)),
                "approval_confirmed": bool(extra.get("approval_confirmed", False)),
                "user_confirmation_required": bool(extra.get("user_confirmation_required", explicit_level >= 4)),
                "physical_risk_gate_checked": bool(extra.get("physical_risk_gate_checked", False)),
                "operator_policy_required": bool(extra.get("operator_policy_required", explicit_level >= 3)),
                "telemetry_fresh_required": bool(extra.get("telemetry_fresh_required", explicit_level >= 3)),
                "safety_ready_required": bool(extra.get("safety_ready_required", explicit_level >= 3)),
                "source": str(meta.get("source", "") or ""),
                "ts_ms": int(meta.get("ts_ms", now_ms()) or now_ms()),
            }
        task_id = str(payload.get("task_id", "") or meta.get("correlation_id", "") or "")
        session_id = str(meta.get("session_id", "") or "")
        if task_id:
            item = self._voice_task_risk_by_task_id.get(task_id)
            if item:
                return dict(item)
        if session_id:
            item = self._voice_task_risk_by_session.get(session_id)
            if item:
                return dict(item)
        return {}

    def _telemetry_gate_snapshot(self) -> Dict[str, Any]:
        telemetry = dict(self._last_hardware_telemetry or {})
        diagnostics = dict(self._last_robot_diagnostics or {})
        sensor_health = dict(diagnostics.get("sensor_health", {}) or {})
        telemetry_age_ms = -1
        raw_age = sensor_health.get("telemetry_age_ms", None)
        try:
            if raw_age is not None:
                telemetry_age_ms = int(raw_age)
        except (TypeError, ValueError):
            telemetry_age_ms = -1
        if telemetry_age_ms < 0 and telemetry:
            try:
                telemetry_age_ms = max(0, now_ms() - int(telemetry.get("ts_ms", now_ms()) or now_ms()))
            except Exception:
                telemetry_age_ms = -1
        telemetry_stale = bool(sensor_health.get("telemetry_stale", False))
        contacts_ready = bool(telemetry.get("contacts"))
        imu_ready = bool(telemetry.get("imu"))
        harness_ready = bool(telemetry.get("harness_ready", False))
        estop_active = bool(telemetry.get("estop_active", False))
        watchdog_healthy = bool(self._last_watchdog_status.get("healthy", True)) if self._last_watchdog_status else True
        telemetry_fresh = bool(telemetry) and not telemetry_stale and telemetry_age_ms >= 0
        safety_ready = bool(telemetry) and telemetry_fresh and not estop_active and harness_ready and contacts_ready and imu_ready and watchdog_healthy
        return {
            "telemetry_fresh": telemetry_fresh,
            "telemetry_stale": telemetry_stale,
            "telemetry_age_ms": telemetry_age_ms,
            "safety_ready": safety_ready,
            "estop_active": estop_active,
            "harness_ready": harness_ready,
            "contact_ready": contacts_ready,
            "imu_ready": imu_ready,
            "watchdog_healthy": watchdog_healthy,
        }

    def on_lifecycle_status(self, topic: str, msg: Any):
        self._last_lifecycle_status = dict(msg) if isinstance(msg, dict) else {}

    def _capability_gate_snapshot(self) -> Dict[str, Any]:
        if self._last_lifecycle_status:
            return dict(self._last_lifecycle_status)
        telemetry = dict(self._last_hardware_telemetry or {})
        diagnostics = dict(self._last_robot_diagnostics or {})
        sensor_health = dict(diagnostics.get("sensor_health", {}) or {})
        telemetry_stale = bool(sensor_health.get("telemetry_stale"))
        imu_present = bool(telemetry.get("imu"))
        camera_present = infer_camera_present(telemetry)
        return capability_snapshot(
            imu_present=imu_present,
            camera_present=camera_present,
            telemetry_stale=telemetry_stale,
        )

    def _walking_lifecycle_gate_applies(self) -> bool:
        return bool(self._last_hardware_telemetry)

    @staticmethod
    def _motion_cmd_requires_walking(name_upper: str) -> bool:
        tokens = ("WALK", "STEP", "GAIT", "TURN", "LOCOMOT", "MOVE_LINEAR", "GO_TO", "FOLLOW", "DOCK")
        return any(tok in name_upper for tok in tokens)

    def _lifecycle_capability_failure(self, action_dict: Dict[str, Any]) -> Dict[str, Any]:
        action_type = str(action_dict.get("action_type", "") or "").strip().lower()
        snap = self._capability_gate_snapshot()
        caps = dict(snap.get("capabilities") or {})
        telemetry = self._telemetry_gate_snapshot()
        if not caps.get(CAPABILITY_MOTION_ALL):
            if action_type in _LIFECYCLE_NON_MOTION_ACTION_TYPES:
                return {}
            return {
                "reason": "lifecycle_motion_disabled",
                "chat": "Telemetri bayat veya hareket kapisi kapali; bu eylemi baslatmiyorum.",
                "telemetry": telemetry,
                "lifecycle": snap,
            }
        if action_type in _LIFECYCLE_LOCOMOTION_ACTION_TYPES:
            if self._walking_lifecycle_gate_applies() and not caps.get(CAPABILITY_WALKING):
                return {
                    "reason": "lifecycle_walking_disabled",
                    "chat": "IMU/locomotion hazir olmadigi icin bu eylemi baslatmiyorum.",
                    "telemetry": telemetry,
                    "lifecycle": snap,
                }
        if action_type in _LIFECYCLE_VISUAL_PICK_ACTION_TYPES and not caps.get(CAPABILITY_VISUAL_PICK):
            return {
                "reason": "lifecycle_visual_pick_disabled",
                "chat": "Kamera/gorus akisi olmadan bu gorsel sec-im eylemini baslatmiyorum.",
                "telemetry": telemetry,
                "lifecycle": snap,
            }
        return {}

    def _physical_command_gate_failure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action_type = str(payload.get("action_type", "") or "").strip().upper()
        risk_context = self._risk_context_for_payload(payload)
        level = int(risk_context.get("aggregate_command_risk_level", 0) or 0)
        if level < 3 or not bool(risk_context.get("physical_risk_gate_checked", False)):
            return {}
        if bool(risk_context.get("wake_required", True)) and not bool(risk_context.get("wake_gate_passed", False)):
            return {
                "reason": "wake_gate_missing",
                "chat": "Bu fiziksel komut icin wake onayi gormeden eyleme gecmiyorum.",
                "risk_context": risk_context,
            }
        telemetry = self._telemetry_gate_snapshot()
        if bool(risk_context.get("telemetry_fresh_required", True)) and not bool(telemetry.get("telemetry_fresh", False)):
            return {
                "reason": "telemetry_not_fresh",
                "chat": "Bu fiziksel komutu başlatmadan önce taze telemetri görmem gerekiyor.",
                "risk_context": risk_context,
                "telemetry": telemetry,
            }
        if bool(risk_context.get("safety_ready_required", True)) and not bool(telemetry.get("safety_ready", False)):
            return {
                "reason": "safety_not_ready",
                "chat": "Safety hazir olmadigi icin bu fiziksel komutu baslatmiyorum.",
                "risk_context": risk_context,
                "telemetry": telemetry,
            }
        policy = dict(self._last_operator_policy or build_approval_policy_baseline())
        if bool(risk_context.get("operator_policy_required", True)) and not bool(policy.get("enabled", True)):
            return {
                "reason": "operator_policy_disabled",
                "chat": "Operator policy kapali oldugu icin bu fiziksel komutu baslatmiyorum.",
                "risk_context": risk_context,
                "telemetry": telemetry,
                "policy": policy,
            }
        auto_actions = {
            str(item or "").strip().upper()
            for item in list(policy.get("auto_approve_actions", []) or [])
            if str(item).strip()
        }
        approval_required = bool(risk_context.get("approval_required", False))
        if not approval_required and action_type:
            approval_required = action_type not in auto_actions
        if int(level) >= 4:
            approval_required = True
        if approval_required and not bool(risk_context.get("approval_confirmed", False)):
            return {
                "reason": "user_confirmation_required",
                "chat": "Bu fiziksel komut icin kullanici onayi eksik oldugu icin eylemi baslatmiyorum.",
                "risk_context": risk_context,
                "telemetry": telemetry,
                "policy": policy,
            }
        return {}

    def _chat_only_risk_gate_failure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from core.brain.chat_risk_gate import (
            chat_only_risk_gate_enabled,
            is_chat_only_blocked_action,
            payload_chat_only_gated,
        )

        if not chat_only_risk_gate_enabled():
            return {}
        if not payload_chat_only_gated(payload):
            return {}
        action_type = str(payload.get("action_type", "") or "").strip().lower()
        if not is_chat_only_blocked_action(action_type):
            return {}
        return {
            "reason": "chat_only_motion_blocked",
            "chat": "Sohbet modundayken fiziksel eylem baslatmiyorum; gorev icin net bir komut ver.",
            "chat_risk_gate": {
                "execution_mode": "chat_only",
                "preview_only": True,
                "blocked_action_type": action_type,
            },
        }

    def _publish_risk_block(self, payload: Dict[str, Any], failure: Dict[str, Any]):
        reason = str(failure.get("reason", "command_risk_gate_blocked") or "command_risk_gate_blocked")
        chat = str(failure.get("chat", "") or "Bu fiziksel komutu simdilik baslatmiyorum.")
        action_id = str(payload.get("action_id", "") or "")
        task_id = str(payload.get("task_id", "") or "")
        node_id = str(payload.get("node_id", "") or "")
        action_type = str(payload.get("action_type", "") or "")
        blocked = {
            "action_id": action_id,
            "task_id": task_id,
            "node_id": node_id,
            "action_type": action_type,
            "reason": reason,
            "risk_context": dict(failure.get("risk_context") or {}),
            "telemetry": dict(failure.get("telemetry") or {}),
            "policy": dict(failure.get("policy") or {}),
            "lifecycle": dict(failure.get("lifecycle") or {}),
            "ts_ms": now_ms(),
        }
        self.bus.publish("action_router.risk_blocked", blocked)
        write_failure_snapshot(
            source="action_router.risk_blocked",
            reason=reason,
            detail=blocked,
            ts_ms=int(blocked["ts_ms"]),
        )
        self.bus.publish("voice.say", {"text": chat, "lang": "tr", "ts_ms": now_ms()})
        self._publish_lifecycle(payload, "failed", "executive.action", {"reason": reason, "detail": reason, "success": False})
        self.bus.publish(
            "behavior.node_result",
            {
                "node_id": node_id,
                "status": "failed",
                "reason": reason,
                "params": {
                    "runtime_command_risk_gate": dict(failure),
                },
                "output": {
                    "gate_blocked": True,
                    "gate_reason": reason,
                },
                "ts_ms": now_ms(),
            },
        )

    def _ensure_action_identity(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(payload)
        action_type = self._normalize_action_type(payload)
        if action_type:
            payload["action_type"] = action_type
        payload.setdefault("action_id", f"action_{now_ms()}")
        payload.setdefault("task_id", str(payload.get("task_id", "") or payload["action_id"]))
        payload["meta"] = self._meta_from(payload)
        meta_dict = payload["meta"]
        params = dict(payload.get("params") or {})
        tid = str(meta_dict.get("trace_id") or "")
        if tid and "trace_id" not in params:
            params["trace_id"] = tid
        tub = str(meta_dict.get("turn_id") or "")
        if tub and "turn_id" not in params:
            params["turn_id"] = tub
        sid = str(meta_dict.get("session_id") or "")
        if sid and "session_id" not in params:
            params["session_id"] = sid
        payload["params"] = params
        return payload

    def _pending_entry(self, payload: Dict[str, Any], route_topic: str) -> Dict[str, Any]:
        meta = self._meta_from(payload)
        return {
            "action_id": str(payload.get("action_id", "") or ""),
            "task_id": str(payload.get("task_id", "") or ""),
            "action_type": str(payload.get("action_type", "") or ""),
            "route_topic": route_topic,
            "meta": meta,
            "params": dict(payload.get("params", {}) or {}),
        }

    def _register_pending(self, payload: Dict[str, Any], route_topic: str, *, cmd_id: str = "") -> Dict[str, Any]:
        entry = self._pending_entry(payload, route_topic)
        action_id = entry["action_id"]
        if action_id:
            self._pending_by_action_id[action_id] = entry
        if cmd_id:
            self._pending_by_cmd_id[cmd_id] = entry
        return entry

    def _clear_pending(self, action_id: str = "", cmd_id: str = ""):
        entry = None
        if cmd_id:
            entry = self._pending_by_cmd_id.pop(cmd_id, None)
            if entry and not action_id:
                action_id = str(entry.get("action_id", "") or "")
        if action_id:
            entry = self._pending_by_action_id.pop(action_id, None) or entry
        return entry

    def _build_action_from_node(self, payload: Dict[str, Any]) -> ActionSpec:
        node = payload.get("node", {}) or {}
        task_id = str(payload.get("task_id", "") or node.get("task_id", "") or "")
        node_id = str(node.get("node_id", "") or "")
        kind = str(node.get("kind", "") or "generic")
        action_type = str(node.get("action_type", "") or "UNKNOWN")
        title = str(node.get("title", "") or action_type)

        return make_action(
            task_id=task_id,
            node_id=node_id,
            kind=kind,
            action_type=action_type,
            title=title,
            params=dict(node.get("params", {}) or {}),
            constraints={},
            preconditions=list(node.get("preconditions", []) or []),
            success_conditions=list(node.get("success_conditions", []) or []),
            failure_conditions=list(node.get("failure_conditions", []) or []),
            timeout_ms=int(node.get("timeout_ms", 10_000) or 10_000),
            retry_limit=int(node.get("retry_limit", 0) or 0),
        )

    def _publish_lifecycle(self, payload: Dict[str, Any], stage: str, route_topic: str, detail: Dict[str, Any] | None = None):
        meta = self._meta_from(payload)
        action_id = str(payload.get("action_id", "") or "")
        task_id = str(payload.get("task_id", "") or "")
        action_type = str(payload.get("action_type", "") or "")
        event = {
            "action_id": action_id,
            "task_id": task_id,
            "action_type": action_type,
            "stage": stage,
            "route_topic": route_topic,
            "ts_ms": now_ms(),
            "meta": meta,
            "correlation_id": str(meta.get("correlation_id", "") or task_id or action_id),
        }
        if detail:
            event.update(detail)
        self.bus.publish("action.lifecycle", event)
        if stage == "routed":
            self.bus.publish("action.routed", event)
        if stage in {"completed", "failed"}:
            self.bus.publish("action.result", event)

    def _publish_behavior_action(self, action_dict: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        action_dict = self._ensure_action_identity(action_dict)
        lf = self._lifecycle_capability_failure(action_dict)
        if lf:
            self._publish_risk_block(action_dict, lf)
            return False
        failure = self._physical_command_gate_failure(action_dict)
        if failure:
            self._publish_risk_block(action_dict, failure)
            return False
        self.last_action = action_dict
        self._register_pending(action_dict, "executive.action")
        envelope = {
            "graph_id": payload.get("graph_id", ""),
            "task_id": payload.get("task_id", "") or action_dict.get("task_id", ""),
            "goal_type": payload.get("goal_type", ""),
            "action": action_dict,
            "ts_ms": now_ms(),
        }
        self.bus.publish("action_router.action_ready", envelope)
        target_topic = "executive.action"
        has_subscribers = getattr(self.bus, "has_subscribers", None)
        if callable(has_subscribers) and has_subscribers("executive.action.request"):
            target_topic = "executive.action.request"
        self.bus.publish(target_topic, envelope)
        return True

    def _is_behavior_action(self, payload: Dict[str, Any], action_type: str) -> bool:
        if {"node_id", "kind", "title"}.issubset(payload.keys()):
            return True
        return action_type in _EXECUTIVE_ACTION_TYPES

    def _normalize_action_result(self, payload: Dict[str, Any], *, action_id: str, task_id: str, action_type: str, route_topic: str, success: bool, detail: str, stage: str) -> Dict[str, Any]:
        base = {
            "action_id": action_id,
            "task_id": task_id,
            "action_type": action_type,
            "success": success,
            "detail": detail,
            "stage": stage,
            "route_topic": route_topic,
            "ts_ms": now_ms(),
        }
        base["meta"] = self._meta_from(payload)
        base["correlation_id"] = str(base["meta"].get("correlation_id", "") or task_id or action_id)
        return base

    def on_behavior_node_ready(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        action = self._build_action_from_node(payload)
        action.updated_ts_ms = now_ms()
        self._publish_behavior_action(action.to_dict(), payload)

    def on_voice_task(self, topic: str, msg: Any):
        self._remember_voice_task_risk(msg)

    def on_hardware_telemetry(self, topic: str, msg: Any):
        self._last_hardware_telemetry = dict(msg or {}) if isinstance(msg, dict) else {}

    def on_robot_diagnostics_status(self, topic: str, msg: Any):
        self._last_robot_diagnostics = dict(msg or {}) if isinstance(msg, dict) else {}

    def on_hardware_watchdog_status(self, topic: str, msg: Any):
        self._last_watchdog_status = dict(msg or {}) if isinstance(msg, dict) else {}

    def on_operator_policy_result(self, topic: str, msg: Any):
        payload = dict(msg or {}) if isinstance(msg, dict) else {}
        policy = dict(payload.get("policy") or {})
        if policy:
            self._last_operator_policy = policy

    def _route_speech(self, payload: Dict[str, Any]):
        params = dict(payload.get("params", {}) or {})
        text = str(payload.get("text", "") or params.get("text", "") or "").strip()
        if not text:
            self._publish_lifecycle(payload, "failed", "voice.say", {"reason": "text_missing", "detail": "text_missing", "success": False})
            return
        meta = self._meta_from(payload)
        extra = meta.get("extra") if isinstance(meta.get("extra"), dict) else {}
        lg = resolve_voice_lang(
            explicit=payload.get("lang") or params.get("lang"),
            context_lang=extra.get("locale"),
        )
        out = {
            "text": text,
            "lang": lg,
            "voice": str(payload.get("voice", "") or params.get("voice", "") or ""),
            "interrupt": bool(payload.get("interrupt", False) or params.get("interrupt", False)),
            "session_id": str(meta.get("session_id", "") or ""),
            "meta": meta,
        }
        self.bus.publish("voice.say", out)
        self._publish_lifecycle(payload, "completed", "voice.say", {"success": True, "detail": text, "text": text})

    def _route_memory_write(self, payload: Dict[str, Any]):
        params = dict(payload.get("params", {}) or {})
        out = {
            "scope": str(payload.get("scope", "") or params.get("scope", "") or "semantic"),
            "key": str(payload.get("key", "") or params.get("key", "") or ""),
            "value": payload.get("value", params.get("value")),
            "ttl_ms": int(payload.get("ttl_ms", params.get("ttl_ms", 0)) or 0),
            "reply_topic": str(payload.get("reply_topic", params.get("reply_topic", "memory.result")) or "memory.result"),
            "meta": self._meta_from(payload),
            "task_id": str(payload.get("task_id", "") or ""),
            "action_id": str(payload.get("action_id", "") or ""),
            "correlation_id": str(self._meta_from(payload).get("correlation_id", "") or payload.get("task_id", "") or payload.get("action_id", "") or ""),
        }
        if not out["key"]:
            self._publish_lifecycle(payload, "failed", "memory.write", {"reason": "key_missing", "detail": "key_missing", "success": False})
            return
        self._register_pending(payload, "memory.write")
        self.bus.publish("memory.write", out)
        self._publish_lifecycle(payload, "routed", "memory.write", {"success": True, "key": out["key"], "detail": f"memory.write:{out['key']}"})

    def _route_memory_query(self, payload: Dict[str, Any]):
        params = dict(payload.get("params", {}) or {})
        out = {
            "scope": str(payload.get("scope", "") or params.get("scope", "") or "semantic"),
            "key": str(payload.get("key", "") or params.get("key", "") or ""),
            "query": str(payload.get("query", "") or params.get("query", "") or ""),
            "limit": int(payload.get("limit", params.get("limit", 5)) or 5),
            "reply_topic": str(payload.get("reply_topic", params.get("reply_topic", "memory.query.result")) or "memory.query.result"),
            "meta": self._meta_from(payload),
            "task_id": str(payload.get("task_id", "") or ""),
            "action_id": str(payload.get("action_id", "") or ""),
            "correlation_id": str(self._meta_from(payload).get("correlation_id", "") or payload.get("task_id", "") or payload.get("action_id", "") or ""),
        }
        if not out["key"] and not out["query"]:
            self._publish_lifecycle(payload, "failed", "memory.query", {"reason": "query_missing", "detail": "query_missing", "success": False})
            return
        self._register_pending(payload, "memory.query")
        self.bus.publish("memory.query", out)
        self._publish_lifecycle(payload, "routed", "memory.query", {"success": True, "key": out["key"], "query": out["query"], "detail": f"memory.query:{out['key'] or out['query']}"})

    def _route_motion(self, payload: Dict[str, Any]):
        route_topic = "executive.action" if motion_via_executive_enabled() else "exec.cmd"
        caps = dict(self._capability_gate_snapshot().get("capabilities") or {})
        if not caps.get(CAPABILITY_MOTION_ALL):
            self._publish_lifecycle(
                payload,
                "failed",
                route_topic,
                {
                    "reason": "lifecycle_motion_disabled",
                    "detail": "lifecycle_motion_disabled",
                    "success": False,
                },
            )
            self.bus.publish(
                "voice.say",
                {"text": "Telemetri bayat; hareket komutunu gondermiyorum.", "lang": "tr", "ts_ms": now_ms()},
            )
            return
        params = dict(payload.get("params", {}) or {})
        name = str(payload.get("name", "") or params.get("name", "") or "").strip()
        nu = name.upper()
        if (
            self._walking_lifecycle_gate_applies()
            and self._motion_cmd_requires_walking(nu)
            and not caps.get(CAPABILITY_WALKING)
        ):
            self._publish_lifecycle(
                payload,
                "failed",
                route_topic,
                {
                    "reason": "lifecycle_walking_disabled",
                    "detail": "lifecycle_walking_disabled",
                    "success": False,
                },
            )
            self.bus.publish(
                "voice.say",
                {"text": "IMU hazir olmadigi icin bu hareketi gondermiyorum.", "lang": "tr", "ts_ms": now_ms()},
            )
            return
        if not name:
            self._publish_lifecycle(
                payload,
                "failed",
                route_topic,
                {"reason": "motion_name_missing", "detail": "motion_name_missing", "success": False},
            )
            return

        if motion_via_executive_enabled():
            executive = build_executive_action_from_motion_request(payload)
            if executive:
                if self._route_motion_executive(payload, executive):
                    return
            else:
                self._publish_lifecycle(
                    payload,
                    "failed",
                    "executive.action",
                    {"reason": "unknown_motion_name", "detail": name, "success": False},
                )
                return

        self._route_motion_legacy_exec_cmd(payload, name=name, params=params)

    def _route_motion_executive(self, payload: Dict[str, Any], executive: Dict[str, Any]) -> bool:
        action_type = str(executive.get("action_type", "") or "")
        merged = dict(payload)
        merged.update(executive)
        merged["action_type"] = action_type.lower()
        if not self._publish_behavior_action(executive, {"task_id": executive.get("task_id", "")}):
            return False
        self._publish_lifecycle(
            merged,
            "routed",
            "executive.action",
            {
                "success": True,
                "detail": action_type,
                "executive_action_type": action_type,
                "planner_layer": "skill_motion_planner",
            },
        )
        self.bus.publish(
            "skill.motion.planned",
            {
                "action_id": executive.get("action_id", ""),
                "task_id": executive.get("task_id", ""),
                "executive_action_type": action_type,
                "motion_name": str(payload.get("name", "") or ""),
                "planner_origin": str(
                    ((executive.get("meta") or {}).get("extra") or {}).get("planner_origin", "")
                ),
                "ts_ms": now_ms(),
            },
        )
        return True

    def _route_motion_legacy_exec_cmd(self, payload: Dict[str, Any], *, name: str, params: Dict[str, Any]) -> None:
        meta_dict = self._meta_from(payload)
        cmd = CommandIssued(
            meta=Meta(**meta_dict),
            plan_id=str(payload.get("task_id", "") or ""),
            step_id=str(payload.get("action_id", "") or f"step_{now_ms()}"),
            cmd_type=name.upper(),
            params=params,
            priority=int(payload.get("priority", 0) or 0),
            cancel_previous=False,
        )
        cmd_id = str(meta_dict.get("id", "") or "")
        self._register_pending(payload, "exec.cmd", cmd_id=cmd_id)
        self.bus.publish("exec.cmd", cmd)
        self._publish_lifecycle(payload, "routed", "exec.cmd", {"success": True, "cmd_type": name.upper(), "detail": name.upper()})

    def on_action_request(self, topic: str, msg: Any):
        payload = self._msg_to_dict(msg)
        if not payload:
            return

        payload = self._ensure_action_identity(payload)
        self.last_action = dict(payload)
        action_type = str(payload.get("action_type", "") or "").strip().lower()
        self._publish_lifecycle(payload, "requested", topic, {"success": True, "detail": "requested"})

        chat_only_failure = self._chat_only_risk_gate_failure(payload)
        if chat_only_failure:
            self._publish_risk_block(payload, chat_only_failure)
            return

        if self._is_behavior_action(payload, action_type) and action_type not in {"speech", "memory_write", "memory_query", "motion", "attention", "task_control"}:
            if self._publish_behavior_action(dict(payload), {"task_id": payload.get("task_id", "")}):
                self._publish_lifecycle(payload, "routed", "executive.action", {"success": True, "detail": "executive.action"})
            return

        if action_type == "speech":
            self._route_speech(payload)
            return
        if action_type == "memory_write":
            self._route_memory_write(payload)
            return
        if action_type == "memory_query":
            self._route_memory_query(payload)
            return
        if action_type == "motion":
            self._route_motion(payload)
            return

        self._publish_lifecycle(payload, "failed", "", {"reason": f"unsupported_action_type:{action_type}", "detail": f"unsupported_action_type:{action_type}", "success": False})

    def on_memory_result(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        action_id = str(payload.get("action_id", "") or "")
        task_id = str(payload.get("task_id", "") or "")
        meta = self._meta_from(payload)
        if not action_id:
            corr = str(payload.get("correlation_id", "") or meta.get("correlation_id", "") or task_id)
            for candidate in self._pending_by_action_id.values():
                if str(candidate.get("task_id", "") or "") == task_id or str((candidate.get("meta") or {}).get("correlation_id", "") or "") == corr:
                    action_id = str(candidate.get("action_id", "") or "")
                    break
        entry = self._pending_by_action_id.get(action_id, {})
        action_type = str(entry.get("action_type", payload.get("action_type", "") or "") or "")
        if action_type not in {"memory_write", "memory_query"}:
            return
        task_id = str(task_id or entry.get("task_id", "") or "")
        ok = bool(payload.get("ok", False))
        found = payload.get("found", None)
        detail = str(payload.get("error", "") or payload.get("query", "") or payload.get("key", "") or payload.get("op", "memory"))
        result = self._normalize_action_result(payload, action_id=action_id, task_id=task_id, action_type=action_type, route_topic=str(entry.get("route_topic", topic) or topic), success=ok and (found is not False or action_type == "memory_write"), detail=detail, stage="completed" if ok else "failed")
        if found is not None:
            result["found"] = found
        result["ok"] = ok
        result["payload"] = payload
        self._clear_pending(action_id=action_id)
        self.bus.publish("action.lifecycle", dict(result))
        self.bus.publish("action.result", result)

    def on_exec_done(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        cmd_id = str(payload.get("cmd_id", "") or "")
        entry = self._clear_pending(cmd_id=cmd_id)
        if not entry:
            return
        state = str(payload.get("state", "") or "").upper()
        ok = bool(payload.get("ok", state == "COMPLETED"))
        result = self._normalize_action_result(payload, action_id=str(entry.get("action_id", "") or ""), task_id=str(entry.get("task_id", "") or ""), action_type=str(entry.get("action_type", "") or "motion"), route_topic=str(entry.get("route_topic", topic) or topic), success=ok, detail=str(payload.get("reason", "") or state or "exec_done"), stage="completed" if ok else "failed")
        result["cmd_id"] = cmd_id
        self.bus.publish("action.lifecycle", dict(result))
        self.bus.publish("action.result", result)

    def on_exec_timeout(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        cmd_id = str(payload.get("cmd_id", "") or "")
        entry = self._clear_pending(cmd_id=cmd_id)
        if not entry:
            return
        result = self._normalize_action_result(payload, action_id=str(entry.get("action_id", "") or ""), task_id=str(entry.get("task_id", "") or ""), action_type=str(entry.get("action_type", "") or "motion"), route_topic=str(entry.get("route_topic", topic) or topic), success=False, detail=str(payload.get("reason", "") or "timeout"), stage="failed")
        result["cmd_id"] = cmd_id
        self.bus.publish("action.lifecycle", dict(result))
        self.bus.publish("action.result", result)

    def on_executive_action_started(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        action_id = str(payload.get("action_id", "") or "")
        entry = self._pending_by_action_id.get(action_id, {})
        merged = dict(entry)
        merged.update(payload)
        if entry:
            merged["meta"] = entry.get("meta", {})
        self._publish_lifecycle(merged, "started", "executive.action", {"success": True, "detail": "started"})

    def on_executive_action_result(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        action_id = str(payload.get("action_id", "") or "")
        entry = self._clear_pending(action_id=action_id)
        merged = dict(entry or {})
        merged.update(payload)
        status = str(merged.get("status", "") or "").lower()
        success = status == "completed"
        detail = str(merged.get("reason", "") or status or "executive_result")
        route_topic = str((entry or {}).get("route_topic", "executive.action") or "executive.action")
        result = self._normalize_action_result(merged, action_id=action_id, task_id=str(merged.get("task_id", "") or (entry or {}).get("task_id", "") or ""), action_type=str(merged.get("action_type", "") or (entry or {}).get("action_type", "") or ""), route_topic=route_topic, success=success, detail=detail, stage="completed" if success else "failed")
        result["status"] = status
        result["output"] = dict(merged.get("output", {}) or {})
        self.bus.publish("action.lifecycle", dict(result))
        self.bus.publish("action.result", result)

    def on_query(self, topic: str, msg: Any):
        self.bus.publish(
            "action_router.result",
            {
                "last_action": self.last_action,
                "pending_action_count": len(self._pending_by_action_id),
                "ts_ms": now_ms(),
            },
        )
