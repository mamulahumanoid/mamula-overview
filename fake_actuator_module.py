
from __future__ import annotations

import time
from typing import Any, Dict, Set


def now_ms() -> int:
    return int(time.time() * 1000)


class FakeActuatorModule:
    """
    Deterministic fake actuator for pre-hardware motion testing.
    Consumes exec.cmd_safe and emits joints.frame + exec.done/timeout.
    """
    name = "fake_actuator"

    def __init__(self, bus, rt):
        self.bus = bus
        self.rt = rt
        self.pose = {"x_m": 0.0, "y_m": 0.0, "z_m": 0.0, "heading_deg": 0.0}
        self.last_command: Dict[str, Any] | None = None
        self._consumed_fail_once: Set[str] = set()
        bus.subscribe("exec.cmd_safe", self.on_exec_cmd_safe)
        bus.subscribe("robot.command", self.on_robot_command)

    def tick(self):
        self.rt.beat(self.name)

    def _as_dict(self, msg: Any) -> Dict[str, Any]:
        if isinstance(msg, dict):
            return dict(msg)
        out: Dict[str, Any] = {}
        for attr in ("meta", "plan_id", "step_id", "cmd_type", "params", "priority", "cancel_previous"):
            if hasattr(msg, attr):
                val = getattr(msg, attr)
                if hasattr(val, "to_dict"):
                    try:
                        val = val.to_dict()
                    except Exception:
                        pass
                out[attr] = val
        return out

    def _emit_joint_frame(self, *, velocity_mps: float = 0.0, turn_rate_dps: float = 0.0):
        self.bus.publish("joints.frame", {
            "positions": {"waist_yaw": self.pose["heading_deg"] / 180.0},
            "x_m": self.pose["x_m"],
            "y_m": self.pose["y_m"],
            "z_m": self.pose["z_m"],
            "heading_deg": self.pose["heading_deg"],
            "velocity_mps": velocity_mps,
            "turn_rate_dps": turn_rate_dps,
            "balance_state": "stable",
            "posture": "standing",
            "ts_ms": now_ms(),
        })

    def _result(self, command: Dict[str, Any], status: str, reason: str = "", output: Dict[str, Any] | None = None):
        meta = command.get("meta") or {}
        cmd_id = ""
        if isinstance(meta, dict):
            cmd_id = str(meta.get("id", "") or "")
        if not cmd_id:
            cmd_id = str(command.get("step_id", "") or f"cmd_{now_ms()}")
        payload = {
            "cmd_id": cmd_id,
            "status": status,
            "reason": reason,
            "cmd_type": str(command.get("cmd_type", "") or ""),
            "output": output or {},
            "ts_ms": now_ms(),
        }
        topic = "exec.timeout" if status == "timed_out" else "exec.done"
        self.bus.publish(topic, payload)

    def _consume_once_flag(self, payload: Dict[str, Any], flag_name: str, discriminator: str = "") -> bool:
        params = dict(payload.get("params", {}) or {})
        if not bool(params.get(flag_name, False)):
            return False
        meta = dict(payload.get("meta", {}) or {})
        key = "|".join([
            flag_name,
            str(meta.get("correlation_id", "") or payload.get("step_id", "") or ""),
            str(payload.get("cmd_type", "") or ""),
            discriminator or str(params.get("object", "") or params.get("location", "") or ""),
        ])
        if key in self._consumed_fail_once:
            return False
        self._consumed_fail_once.add(key)
        return True

    def _should_timeout_once(self, payload: Dict[str, Any]) -> bool:
        return self._consume_once_flag(payload, "force_timeout_once")

    def on_robot_command(self, topic: str, msg: Any):
        payload = self._as_dict(msg)
        if payload:
            self.bus.publish("exec.cmd_safe", payload)

    def on_exec_cmd_safe(self, topic: str, msg: Any):
        payload = self._as_dict(msg)
        if not payload:
            return
        self.last_command = payload
        cmd_type = str(payload.get("cmd_type", "") or "").upper()
        params = dict(payload.get("params", {}) or {})
        self.bus.publish("exec.started", {"cmd_type": cmd_type, "step_id": payload.get("step_id", ""), "ts_ms": now_ms()})

        if cmd_type == "TIMEOUT" or self._should_timeout_once(payload):
            self._result(payload, "timed_out", "simulated_timeout")
            return

        if cmd_type == "PICK_OBJECT" and self._consume_once_flag(payload, "force_pick_fail_once"):
            self._emit_joint_frame(velocity_mps=0.0, turn_rate_dps=0.0)
            self._result(payload, "failed", "grasp_failed", output={"object": params.get("object", ""), "object_grasped": False, "selected_grasp_candidate": params.get("selected_grasp_candidate", ""), "reach_arm": params.get("reach_arm", "right")})
            return

        if cmd_type in {"MOVE_LINEAR", "WALK_STEPS", "GO_TO_LOCATION"}:
            distance = float(params.get("distance_m", 0.25) or 0.25)
            if cmd_type == "WALK_STEPS":
                distance = float(params.get("steps", 1) or 1) * 0.25
            local_motion_plan = dict(params.get("local_motion_plan", {}) or {})
            selected_approach = dict(params.get("selected_approach", {}) or {})
            waypoints = list(params.get("waypoints", []) or local_motion_plan.get("waypoints", []) or [])
            approach_offset = dict(params.get("approach_offset_m", {}) or selected_approach.get("approach_offset_m", {}) or {})
            if waypoints:
                last_wp = dict(waypoints[-1] or {})
                self.pose["x_m"] = float(last_wp.get("x_m", self.pose["x_m"] + distance) or (self.pose["x_m"] + distance))
                self.pose["y_m"] = float(last_wp.get("y_m", self.pose["y_m"]) or self.pose["y_m"])
            else:
                self.pose["x_m"] += distance
                self.pose["y_m"] += float(approach_offset.get("y_m", 0.0) or 0.0)
            self.pose["heading_deg"] += float(params.get("approach_heading_deg", selected_approach.get("approach_heading_deg", 0.0)) or 0.0)
            requires_slowdown = bool(params.get("requires_slowdown", local_motion_plan.get("requires_slowdown", False)))
            velocity = 0.18 if requires_slowdown else 0.35
            self._emit_joint_frame(velocity_mps=velocity, turn_rate_dps=0.0)
            self._result(payload, "completed", output={"pose": dict(self.pose), "velocity_mps": velocity, "location_reached": params.get("location", ""), "approach_offset_m": approach_offset, "corridor_strategy": params.get("corridor_strategy", ""), "local_motion_strategy": params.get("local_motion_strategy", ""), "corridor_clearance_m": params.get("corridor_clearance_m", 0.0), "obstacle_risk_band": params.get("obstacle_risk_band", "low"), "preferred_approach_side": params.get("preferred_approach_side", "center"), "local_motion_plan": local_motion_plan, "selected_approach": selected_approach, "waypoints": waypoints, "path_type": params.get("path_type", local_motion_plan.get("path_type", "straight")), "approach_heading_deg": params.get("approach_heading_deg", local_motion_plan.get("approach_heading_deg", 0.0)), "requires_slowdown": requires_slowdown})
            return

        if cmd_type in {"TURN", "TURN_IN_PLACE"}:
            heading = float(params.get("heading_delta_deg", params.get("degrees", 45.0)) or 45.0)
            self.pose["heading_deg"] += heading
            self._emit_joint_frame(velocity_mps=0.0, turn_rate_dps=60.0)
            self._result(payload, "completed", output={"pose": dict(self.pose), "heading_delta_deg": heading})
            return

        if cmd_type in {"SET_POSE", "STAND", "HOLD_POSTURE"}:
            self._emit_joint_frame(velocity_mps=0.0, turn_rate_dps=0.0)
            self._result(payload, "completed", output={"pose": dict(self.pose), "posture": str(params.get("posture", "neutral") or "neutral"), "duration_ms": int(params.get("duration_ms", 0) or 0)})
            return

        if cmd_type in {"REACH_ARM", "GRASP_PREP", "HANDOVER_PREP", "PICK_OBJECT", "BRING_OBJECT_TO_USER"}:
            arm = str(params.get("reach_arm", params.get("arm", "right")) or "right").lower()
            arm_prefix = "left" if arm.startswith("l") else "right"
            handover_side = str(params.get("handover_side", "") or ("left" if arm_prefix == "left" else "right"))
            joint_positions = {
                f"{arm_prefix}_shoulder_pitch": 0.35,
                f"{arm_prefix}_elbow_pitch": 0.65,
                f"{arm_prefix}_wrist_roll": -0.10 if arm_prefix == "left" else 0.10,
            }
            if cmd_type in {"HANDOVER_PREP", "BRING_OBJECT_TO_USER"}:
                height_offset = float(params.get("handover_height_offset_m", 0.0) or 0.0)
                joint_positions[f"{arm_prefix}_shoulder_pitch"] = 0.15 + max(-0.18, min(0.12, height_offset))
                joint_positions[f"{arm_prefix}_shoulder_roll"] = 0.18 if handover_side == "left" else (-0.18 if handover_side == "right" else 0.0)
            self.bus.publish("joints.frame", {
                "positions": joint_positions,
                "x_m": self.pose["x_m"],
                "y_m": self.pose["y_m"],
                "z_m": self.pose["z_m"],
                "heading_deg": self.pose["heading_deg"],
                "velocity_mps": 0.0,
                "turn_rate_dps": 0.0,
                "balance_state": "stable",
                "posture": "standing",
                "ts_ms": now_ms(),
            })
            output = {"pose": dict(self.pose), "joint_positions": joint_positions, "reach_arm": arm_prefix, "corridor_strategy": params.get("corridor_strategy", ""), "local_motion_strategy": params.get("local_motion_strategy", ""), "corridor_clearance_m": params.get("corridor_clearance_m", 0.0), "obstacle_risk_band": params.get("obstacle_risk_band", "low"), "selected_approach": dict(params.get("selected_approach", {}) or {}), "local_motion_plan": dict(params.get("local_motion_plan", {}) or {})}
            if params.get("selected_grasp_candidate"):
                output["selected_grasp_candidate"] = params.get("selected_grasp_candidate")
            if cmd_type in {"HANDOVER_PREP", "BRING_OBJECT_TO_USER"}:
                output["handover_side"] = handover_side
                output["human_posture"] = params.get("human_posture", "standing")
                output["human_pose_band"] = params.get("human_pose_band", "open")
                output["handover_height_offset_m"] = params.get("handover_height_offset_m", 0.0)
                output["handover_confirm_required"] = params.get("handover_confirm_required", False)
            if cmd_type == "PICK_OBJECT":
                output.update({"object": params.get("object", ""), "object_grasped": True, "target_object": params.get("target_object", {})})
            if cmd_type == "BRING_OBJECT_TO_USER":
                output.update({"object": params.get("object", ""), "object_delivered": True, "target_user": params.get("target_user", {})})
            self._result(payload, "completed", output=output)
            return

        self._emit_joint_frame(velocity_mps=0.0, turn_rate_dps=0.0)
        self._result(payload, "completed", output={"pose": dict(self.pose)})
