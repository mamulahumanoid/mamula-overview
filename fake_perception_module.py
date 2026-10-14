from __future__ import annotations

import time
from copy import deepcopy
from typing import Any, Dict, List

from core.modules.perception_scenario_engine import PerceptionScenarioEngine


def now_ms() -> int:
    return int(time.time() * 1000)


class FakePerceptionModule:
    """Scenario-aware deterministic perception generator for pre-hardware work.

    This module preserves the earlier simple behaviour while adding a richer
    scenario engine so the stack can graduate into simulation before a real
    perception backend exists.
    """

    name = "fake_perception"

    def __init__(self, bus, rt, *, include_default_user: bool = True, include_default_objects: bool = True):
        self.bus = bus
        self.rt = rt
        self.engine = PerceptionScenarioEngine(seed=7)
        self._last = None

        baseline_state, baseline_zone_objects = self._build_baseline(include_default_user=include_default_user, include_default_objects=include_default_objects)
        self.engine.set_baseline(baseline_state, baseline_zone_objects, current_zone="table_zone")

        bus.subscribe("perception.inject", self.on_inject)
        bus.subscribe("perception.query", self.on_query)
        bus.subscribe("perception.reobserve", self.on_reobserve)
        bus.subscribe("task.choice", self.on_task_choice)
        bus.subscribe("executive.action_result", self.on_action_result)
        bus.subscribe("exec.done", self.on_exec_done)

        bus.subscribe("perception.scenario.load", self.on_scenario_load)
        bus.subscribe("perception.scenario.start", self.on_scenario_start)
        bus.subscribe("perception.scenario.step", self.on_scenario_step)
        bus.subscribe("perception.scenario.advance", self.on_scenario_step)
        bus.subscribe("perception.scenario.patch", self.on_scenario_patch)
        bus.subscribe("perception.scenario.reset", self.on_scenario_reset)
        bus.subscribe("perception.scenario.query", self.on_scenario_query)

        self._emit("init")

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def tick(self):
        self.rt.beat(self.name)

    # ------------------------------------------------------------------
    # event handlers
    # ------------------------------------------------------------------
    def on_inject(self, topic: str, msg: Any):
        payload = self._as_dict(msg)
        result = self.engine.apply_external_inject(payload)
        self._emit(str(payload.get("reason", "inject") or "inject"))
        self.bus.publish("perception.scenario.changed", {"reason": "inject", "result": result, "state": self.state, "ts_ms": now_ms()})

    def on_query(self, topic: str, msg: Any):
        self.bus.publish("perception.result", deepcopy(self.state))

    def on_reobserve(self, topic: str, msg: Any):
        payload = self._as_dict(msg)
        result = self.engine.reobserve(payload)
        if bool(result.get("changed", False)):
            self._emit("reobserve")
        self.bus.publish("perception.reobserve.result", {**result, "state": deepcopy(self.state)})

    def on_task_choice(self, topic: str, msg: Any):
        payload = self._as_dict(msg)
        result = self.engine.task_choice(payload)
        if bool(result.get("changed", False)):
            self._emit("task_choice")

    def on_exec_done(self, topic: str, msg: Any):
        payload = self._as_dict(msg)
        result = self.engine.exec_done(payload)
        if bool(result.get("changed", False)):
            self._emit(f"zone:{result.get('location', '')}")

    def on_action_result(self, topic: str, msg: Any):
        payload = self._as_dict(msg)
        result = self.engine.action_result(payload)
        if bool(result.get("changed", False)):
            self._emit(str(payload.get("action_type", "action_result") or "action_result").lower())
        elif str(payload.get("action_type", "") or "").upper() in {"BRING_OBJECT_TO_USER", "HANDOVER"} and self._as_dict(payload.get("output")).get("object_delivered"):
            self._emit("handover_complete")

    def on_scenario_load(self, topic: str, msg: Any):
        payload = self._as_dict(msg)
        result = self.engine.load_manifest(payload)
        self._emit("scenario_loaded")
        self.bus.publish("perception.scenario.result", {**result, "state": deepcopy(self.state), "scenario_status": self.engine.scenario_status()})

    def on_scenario_start(self, topic: str, msg: Any):
        payload = self._as_dict(msg)
        result = self.engine.start_scenario(payload)
        if bool(result.get("started", False)):
            self._emit(f"scenario_start:{result.get('scenario_id', '')}")
            step_result = self._as_dict(result.get("step_result"))
            for event in list(step_result.get("events", []) or []):
                self._publish_scenario_event(event)
        self.bus.publish("perception.scenario.result", {**result, "state": deepcopy(self.state), "scenario_status": self.engine.scenario_status()})

    def on_scenario_step(self, topic: str, msg: Any):
        payload = self._as_dict(msg)
        result = self.engine.advance_scenario(payload)
        if bool(result.get("advanced", False)):
            self._emit(f"scenario_step:{result.get('step_id', '')}")
            for event in list(result.get("events", []) or []):
                self._publish_scenario_event(event)
        self.bus.publish("perception.scenario.result", {**result, "state": deepcopy(self.state), "scenario_status": self.engine.scenario_status()})

    def on_scenario_patch(self, topic: str, msg: Any):
        payload = self._as_dict(msg)
        result = self.engine.apply_patch(payload)
        self._emit(str(payload.get("reason", "scenario_patch") or "scenario_patch"))
        self.bus.publish("perception.scenario.result", {**result, "state": deepcopy(self.state), "scenario_status": self.engine.scenario_status()})

    def on_scenario_reset(self, topic: str, msg: Any):
        payload = self._as_dict(msg)
        preserve = bool(payload.get("preserve_loaded_scenarios", True))
        self.engine.reset_scene(preserve_loaded_scenarios=preserve)
        if payload.get("scenario_id"):
            self.engine.active_scenario_id = str(payload.get("scenario_id") or "")
        self._emit("scenario_reset")
        self.bus.publish("perception.scenario.result", {"reset": True, "state": deepcopy(self.state), "scenario_status": self.engine.scenario_status(), "ts_ms": now_ms()})

    def on_scenario_query(self, topic: str, msg: Any):
        self.bus.publish("perception.scenario.result", {"state": deepcopy(self.state), "scenario_status": self.engine.scenario_status(), "ts_ms": now_ms()})

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @property
    def state(self) -> Dict[str, Any]:
        return self.engine.visible_state()

    @property
    def zone_objects(self) -> Dict[str, List[Dict[str, Any]]]:
        return deepcopy(self.engine.zone_objects)

    @property
    def current_zone(self) -> str:
        return str(self.engine.current_zone or "table_zone")

    def _as_dict(self, msg: Any) -> Dict[str, Any]:
        return dict(msg or {}) if isinstance(msg, dict) else {}

    def _emit(self, reason: str):
        payload = deepcopy(self.state)
        if payload != self._last:
            self.bus.publish("perception.state", payload)
            self.bus.publish("perception.changed", {"reason": reason, "state": payload, "ts_ms": now_ms()})
            self._last = deepcopy(payload)

    def _publish_scenario_event(self, event: Any):
        payload = self._as_dict(event)
        event_topic = str(payload.get("topic", "") or "").strip()
        if not event_topic:
            return
        event_msg = deepcopy(self._as_dict(payload.get("msg")))
        event_msg.setdefault("ts_ms", now_ms())
        self.bus.publish(event_topic, event_msg)

    def _build_baseline(self, *, include_default_user: bool, include_default_objects: bool) -> tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]]]:
        zone_objects: Dict[str, List[Dict[str, Any]]] = {
            "table_zone": [],
            "shelf_zone": [
                {
                    "id": "obj_cup_hidden_1",
                    "label": "cup",
                    "x_m": 0.35,
                    "y_m": -0.22,
                    "z_m": 1.05,
                    "height_m": 1.05,
                    "width_m": 0.09,
                    "depth_m": 0.08,
                    "yaw_deg": -8.0,
                    "confidence": 0.81,
                    "uncertainty": 0.28,
                    "zone": "shelf_zone",
                    "grasp_candidates": [{"id": "side_grasp", "score": 0.78}, {"id": "top_grasp", "score": 0.59}],
                    "visibility": "visible",
                    "occluded": False,
                }
            ],
        }
        state: Dict[str, Any] = {
            "objects": [],
            "humans": [],
            "obstacles": [],
            "zones": [
                {"id": "home_base", "label": "home_base"},
                {"id": "table_zone", "label": "table"},
                {"id": "shelf_zone", "label": "shelf"},
            ],
            "ts_ms": now_ms(),
            "source": self.name,
            "current_zone": "table_zone",
            "person_visible": bool(include_default_user),
            "speaker_present": bool(include_default_user),
            "approach_safe": True,
        }
        if include_default_objects:
            state["objects"] = [
                {
                    "id": "obj_cup_1",
                    "label": "cup",
                    "x_m": 0.55,
                    "y_m": 0.15,
                    "z_m": 0.75,
                    "height_m": 0.75,
                    "width_m": 0.09,
                    "depth_m": 0.08,
                    "yaw_deg": 12.0,
                    "confidence": 0.94,
                    "uncertainty": 0.08,
                    "zone": "table_zone",
                    "grasp_candidates": [{"id": "side_grasp", "score": 0.81}, {"id": "top_grasp", "score": 0.63}],
                },
                {
                    "id": "obj_bottle_1",
                    "label": "water_bottle",
                    "x_m": 0.62,
                    "y_m": -0.10,
                    "z_m": 0.75,
                    "height_m": 0.75,
                    "width_m": 0.07,
                    "depth_m": 0.07,
                    "yaw_deg": -6.0,
                    "confidence": 0.91,
                    "uncertainty": 0.12,
                    "zone": "table_zone",
                    "grasp_candidates": [{"id": "front_grasp", "score": 0.84}, {"id": "side_grasp", "score": 0.68}],
                },
            ]
        if include_default_user:
            state["humans"] = [
                {
                    "id": "user_1",
                    "label": "operator",
                    "x_m": 1.20,
                    "y_m": 0.0,
                    "z_m": 0.0,
                    "confidence": 0.97,
                    "preferred_handover_side": "right",
                    "posture": "standing",
                }
            ]
        return state, zone_objects


class SimPerceptionSeedModule(FakePerceptionModule):
    """Deterministic perception seed for hardware-facing stacks.

    Same behaviour as :class:`FakePerceptionModule`; distinct registry name so
    production maturity / operator manifests do not list ``fake_*`` modules.
    """

    name = "sim_perception_seed"
