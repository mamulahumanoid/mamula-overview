from __future__ import annotations

import time
from typing import Any, Dict, Optional


def now_ms() -> int:
    return int(time.time() * 1000)


class FollowRecoveryModule:
    """Manage follow-user continuity and emergency interruption.

    Responsibilities:
      - Track whether FOLLOW_USER is active and remember the last mode.
      - On follow.user_lost, issue an immediate STOP and mark recovery pending.
      - On follow.user_acquired, resume FOLLOW_USER with the remembered mode.
      - On STOP goals or STOP action results, clear pending follow recovery state.

    This keeps follow behaviour stateful without coupling perception directly
    into the planner/executive layers.
    """

    name = "follow_recovery_module"

    def __init__(self, bus, rt):
        self.bus = bus
        self.rt = rt
        self.follow_active: bool = False
        self.follow_mode: str = "follow"
        self.pending_resume: bool = False
        self.user_visible: bool = True
        self.last_transition: Dict[str, Any] = {"state": "idle", "ts_ms": now_ms()}

        bus.subscribe("executive.action_result", self.on_action_result)
        bus.subscribe("planner.goal", self.on_goal)
        bus.subscribe("follow.user_lost", self.on_user_lost)
        bus.subscribe("follow.user_acquired", self.on_user_acquired)
        bus.subscribe("follow.query", self.on_query)

    def tick(self):
        self.rt.beat(self.name)

    def _publish_stop(self, reason: str):
        action = {
            "action_id": f"follow-stop-{now_ms()}",
            "task_id": "follow-recovery",
            "node_id": "follow-stop",
            "kind": "safety",
            "action_type": "STOP",
            "title": "STOP",
            "params": {},
            "constraints": {},
            "preconditions": [],
            "success_conditions": [],
            "failure_conditions": [],
            "timeout_ms": 3000,
            "retry_limit": 0,
            "updated_ts_ms": now_ms(),
        }
        self.bus.publish(
            "executive.action",
            {
                "task_id": "follow-recovery",
                "goal_type": "STOP",
                "action": action,
                "reason": reason,
                "ts_ms": now_ms(),
            },
        )

    def _publish_resume_follow(self):
        action = {
            "action_id": f"follow-resume-{now_ms()}",
            "task_id": "follow-recovery",
            "node_id": "follow-resume",
            "kind": "follow",
            "action_type": "FOLLOW_USER",
            "title": "FOLLOW_USER",
            "params": {"mode": self.follow_mode},
            "constraints": {},
            "preconditions": [],
            "success_conditions": [],
            "failure_conditions": [],
            "timeout_ms": 5000,
            "retry_limit": 0,
            "updated_ts_ms": now_ms(),
        }
        self.bus.publish(
            "executive.action",
            {
                "task_id": "follow-recovery",
                "goal_type": "FOLLOW_USER",
                "action": action,
                "reason": "user_reacquired",
                "ts_ms": now_ms(),
            },
        )

    def _set_transition(self, state: str, **extra: Any):
        self.last_transition = {"state": state, "ts_ms": now_ms(), **extra}

    def on_goal(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        goal = dict(payload.get("goal", {}) or {})
        goal_type = str(goal.get("goal_type", "") or "").strip().upper()
        if goal_type == "STOP":
            self.follow_active = False
            self.pending_resume = False
            self._set_transition("stopped_by_goal")

    def on_action_result(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        action_type = str(payload.get("action_type", "") or "").strip().upper()
        status = str(payload.get("status", "") or "").strip().lower()
        output = dict(payload.get("output", {}) or {})

        if action_type == "FOLLOW_USER" and status == "completed":
            mode = str(output.get("mode", self.follow_mode) or self.follow_mode).strip().lower() or "follow"
            self.follow_mode = mode
            self.follow_active = True
            self.pending_resume = False
            self.user_visible = True
            self._set_transition("following", mode=mode)
            return

        if action_type == "STOP" and status == "completed":
            self.follow_active = False
            self._set_transition("stopped")
            return

    def on_user_lost(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        if not self.follow_active:
            return
        self.user_visible = False
        self.pending_resume = True
        self.follow_active = False
        self._set_transition("user_lost", detail=str(payload.get("detail", "") or ""), mode=self.follow_mode)
        self.bus.publish("voice.say", {"text": "Kullanıcıyı kaybettim, duruyorum.", "lang": "tr", "ts_ms": now_ms()})
        self._publish_stop(reason="follow_user_lost")

    def on_user_acquired(self, topic: str, msg: Any):
        if not self.pending_resume:
            return
        self.user_visible = True
        self.pending_resume = False
        self._set_transition("user_reacquired", mode=self.follow_mode)
        self.bus.publish("voice.say", {"text": "Kullanıcıyı tekrar gördüm, takibe devam ediyorum.", "lang": "tr", "ts_ms": now_ms()})
        self._publish_resume_follow()

    def on_query(self, topic: str, msg: Any):
        self.bus.publish(
            "follow.result",
            {
                "follow_active": self.follow_active,
                "follow_mode": self.follow_mode,
                "pending_resume": self.pending_resume,
                "user_visible": self.user_visible,
                "last_transition": dict(self.last_transition),
                "ts_ms": now_ms(),
            },
        )
