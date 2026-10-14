from __future__ import annotations

import time
from typing import Any, Dict, List


def now_ms() -> int:
    return int(time.time() * 1000)


class HandoverTaskAutonomyModule:
    """Task-level autonomy policy for handover.

    Inputs:
      - handover.social_policy_applied
      - handover.intent_updated
      - handover.reactive_escape_policy
      - action_router.action_ready / executive.action / executive.action_result

    Outputs:
      - handover.autonomy_policy_applied
      - handover.autonomy_escalated
      - handover.autonomy_result
    """

    name = "handover_task_autonomy_module"

    def __init__(self, bus, rt, *, history_limit: int = 12):
        self.bus = bus
        self.rt = rt
        self.history_limit = max(3, int(history_limit))
        self.last_social_policy: Dict[str, Any] = {}
        self.last_intent_prediction: Dict[str, Any] = {}
        self.last_reactive_policy: Dict[str, Any] = {}
        self.history: List[Dict[str, Any]] = []
        self.last_policy: Dict[str, Any] = {}
        self._action_transformer_subscription_tag = "action_patch_transformer:handover_task_autonomy"

        bus.subscribe("handover.social_policy_applied", self.on_social_policy)
        bus.subscribe("handover.intent_updated", self.on_intent)
        bus.subscribe("handover.reactive_escape_policy", self.on_reactive)
        bus.subscribe("action_router.action_ready", self.on_action_ready)
        bus.subscribe("executive.action", self.on_executive_action)
        bus.subscribe("executive.action_result", self.on_action_result)
        bus.subscribe("handover.autonomy_query", self.on_query)
        self._register_action_patch_transformer()

    def tick(self):
        self.rt.beat(self.name)

    def on_social_policy(self, topic: str, msg: Any):
        payload = dict(msg or {}) if isinstance(msg, dict) else {}
        self.last_social_policy = dict(payload.get("policy", {}) or {})

    def on_intent(self, topic: str, msg: Any):
        payload = dict(msg or {}) if isinstance(msg, dict) else {}
        self.last_intent_prediction = dict(payload.get("prediction", {}) or {})

    def on_reactive(self, topic: str, msg: Any):
        payload = dict(msg or {}) if isinstance(msg, dict) else {}
        self.last_reactive_policy = dict(payload.get("policy", {}) or {})

    def _recent_success_rate(self) -> float:
        if not self.history:
            return 0.5
        ok = sum(1 for item in self.history if item.get("status") == "completed")
        return round(ok / max(1, len(self.history)), 4)

    def _build_policy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        social = dict(params.get("handover_social_policy", {}) or self.last_social_policy or {})
        intent_score = float(params.get("intent_score", (self.last_intent_prediction or {}).get("intent_score", 0.0)) or 0.0)
        reactive = dict(self.last_reactive_policy or {})
        recent_success = self._recent_success_rate()
        recent_failures = sum(1 for item in self.history[-4:] if item.get("status") != "completed")
        queue_size = int(social.get("queue_size", 0) or 0)
        conflict = bool(social.get("conflict_detected", False))
        unsafe = reactive and not bool(reactive.get("safe", True))

        autonomy_mode = "autonomous"
        if conflict or queue_size > 1:
            autonomy_mode = "socially_aware"
        if recent_failures >= 2 or intent_score < 0.35:
            autonomy_mode = "assistive"
        if unsafe:
            autonomy_mode = "guarded"

        require_confirmation = bool(conflict or (recent_failures >= 3 and intent_score < 0.5))
        wait_for_disambiguation = bool(conflict)
        retry_budget = 0 if conflict else (2 if recent_success >= 0.65 else 1)
        prompt_strategy = "social_disambiguation" if conflict else ("preemptive_brief" if intent_score >= 0.72 else "minimal")
        policy = {
            "autonomy_mode": autonomy_mode,
            "recent_success_rate": recent_success,
            "recent_failures": recent_failures,
            "require_confirmation": require_confirmation,
            "wait_for_disambiguation": wait_for_disambiguation,
            "retry_budget": retry_budget,
            "prompt_strategy": prompt_strategy,
            "can_self_retry": bool(retry_budget > 0 and not require_confirmation),
            "policy_source": "heuristic_task_autonomy_v1",
            "ts_ms": now_ms(),
        }
        return policy

    def _publish(self, action: Dict[str, Any], policy: Dict[str, Any]):
        payload = {
            "action_id": str(action.get("action_id", "") or ""),
            "task_id": str(action.get("task_id", "") or ""),
            "node_id": str(action.get("node_id", "") or ""),
            "action_type": str(action.get("action_type", "") or ""),
            "policy": dict(policy),
            "ts_ms": now_ms(),
        }
        self.last_policy = dict(payload)
        self.bus.publish("handover.autonomy_policy_applied", payload)
        if policy.get("require_confirmation") or policy.get("wait_for_disambiguation"):
            self.bus.publish("handover.autonomy_escalated", payload)

    def on_action_ready(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        action = dict(payload.get("action", {}) or {})
        if str(action.get("action_type", "") or "").strip().upper() != "BRING_OBJECT_TO_USER":
            return
        params = action.setdefault("params", {})
        params["handover_autonomy_policy"] = self._build_policy(params)
        payload["action"] = action

    def on_executive_action(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        action = dict(payload.get("action", {}) or {})
        if str(action.get("action_type", "") or "").strip().upper() != "BRING_OBJECT_TO_USER":
            return
        policy = dict((action.get("params", {}) or {}).get("handover_autonomy_policy", {}) or {})
        if not policy:
            policy = self._build_policy(action.get("params", {}) or {})
        self._publish(action, policy)

    def transform_action_patch(self, msg: Any) -> Dict[str, Any] | None:
        payload = msg if isinstance(msg, dict) else {}
        action = dict(payload.get("action", {}) or {})
        if str(action.get("action_type", "") or "").strip().upper() != "BRING_OBJECT_TO_USER":
            return None
        params = dict(action.get("params", {}) or {})
        policy = dict(params.get("handover_autonomy_policy", {}) or {})
        if not policy:
            policy = self._build_policy(params)
        event_payload = {
            "action_id": str(action.get("action_id", "") or ""),
            "task_id": str(action.get("task_id", "") or ""),
            "node_id": str(action.get("node_id", "") or ""),
            "action_type": str(action.get("action_type", "") or ""),
            "policy": dict(policy),
            "ts_ms": now_ms(),
        }
        self.last_policy = dict(event_payload)
        events = [{"topic": "handover.autonomy_policy_applied", "payload": dict(event_payload)}]
        if policy.get("require_confirmation") or policy.get("wait_for_disambiguation"):
            events.append({"topic": "handover.autonomy_escalated", "payload": dict(event_payload)})
        return {
            "stage": "handover_task_autonomy",
            "reason": "handover_autonomy_policy",
            "params": {"handover_autonomy_policy": dict(policy)},
            "status_events": events,
        }

    def _register_action_patch_transformer(self) -> None:
        register = getattr(self.bus, "register_action_transformer", None)
        if callable(register):
            try:
                register(
                    f"{self.__class__.__module__}.{self.__class__.__name__}",
                    self.transform_action_patch,
                    stage="handover_task_autonomy",
                    priority=733,
                    subscription_tag=self._action_transformer_subscription_tag,
                    kind="action_patch",
                )
            except TypeError:
                pass
        tag_subscription = getattr(self.bus, "tag_subscription", None)
        if callable(tag_subscription):
            tag_subscription("executive.action", self.on_executive_action, self._action_transformer_subscription_tag)

    def on_action_result(self, topic: str, msg: Any):
        payload = dict(msg or {}) if isinstance(msg, dict) else {}
        if str(payload.get("action_type", "") or "").strip().upper() != "BRING_OBJECT_TO_USER":
            return
        entry = {
            "status": str(payload.get("status", "") or ""),
            "reason": str(payload.get("reason", "") or ""),
            "ts_ms": now_ms(),
        }
        self.history.append(entry)
        self.history = self.history[-self.history_limit:]
        self.bus.publish("handover.autonomy_result", {
            "last_policy": dict(self.last_policy or {}),
            "history_size": len(self.history),
            "last_outcome": entry,
            "ts_ms": now_ms(),
        })

    def on_query(self, topic: str, msg: Any):
        self.bus.publish("handover.autonomy_result", {
            "last_policy": dict(self.last_policy or {}),
            "history": list(self.history),
            "ts_ms": now_ms(),
        })
