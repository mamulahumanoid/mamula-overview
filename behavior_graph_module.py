from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from core.contract.behavior import BehaviorGraph, BehaviorNode, GoalSpec, make_graph, make_node


def now_ms() -> int:
    return int(time.time() * 1000)


class BehaviorGraphModule:
    name = "behavior_graph_module"

    def __init__(self, bus, rt):
        self.bus = bus
        self.rt = rt
        self.active_graph: Optional[BehaviorGraph] = None
        self.active_index: int = -1
        bus.subscribe("planner.task_plan", self.on_task_plan)
        bus.subscribe("behavior.start", self.on_behavior_start)
        bus.subscribe("behavior.node_result", self.on_node_result)
        bus.subscribe("behavior.query", self.on_query)

    def tick(self):
        self.rt.beat(self.name)

    def _goal_from_payload(self, payload: Dict[str, Any]) -> GoalSpec:
        g = payload.get("goal", {}) or {}
        return GoalSpec(goal_id=str(g.get("goal_id", "")), goal_type=str(g.get("goal_type", "")), raw_text=str(g.get("raw_text", "")), user_id=str(g.get("user_id", "default_user")), params=dict(g.get("params", {}) or {}), constraints=dict(g.get("constraints", {}) or {}), ts_ms=int(g.get("ts_ms", now_ms()) or now_ms()))

    def _nodes_from_steps(self, task_id: str, steps: List[Dict[str, Any]]) -> List[BehaviorNode]:
        out=[]
        for idx, step in enumerate(steps):
            out.append(make_node(task_id=task_id, kind=str(step.get("kind", "generic") or "generic"), title=str(step.get("title", "") or step.get("action_type", f"step-{idx}")), action_type=str(step.get("action_type", "") or "UNKNOWN"), params=dict(step.get("params", {}) or {}), preconditions=list(step.get("preconditions", []) or []), success_conditions=list(step.get("success_conditions", []) or []), failure_conditions=list(step.get("failure_conditions", []) or []), retry_limit=int(step.get("retry_limit", 0) or 0), timeout_ms=int(step.get("timeout_ms", 10000) or 10000), order_index=idx, parent_node_id=None))
        return out

    def _create_graph(self, payload: Dict[str, Any]) -> BehaviorGraph:
        goal=self._goal_from_payload(payload)
        task_id=str(payload.get("task_id", "") or f"task-{goal.goal_id}")
        steps=list(payload.get("steps", []) or [])
        return make_graph(task_id=task_id, goal=goal, nodes=self._nodes_from_steps(task_id, steps), metadata={"last_node_output": {}, "goal_params": dict(goal.params or {})})

    def _publish_graph_created(self):
        if self.active_graph:
            self.bus.publish("behavior.graph_created", {"graph": self.active_graph.to_dict(), "ts_ms": now_ms()})

    def _publish_task_status(self, status: str):
        if self.active_graph:
            self.bus.publish("task.status", {"task_id": self.active_graph.task_id, "status": status, "goal_type": self.active_graph.goal_type, "ts_ms": now_ms()})

    def _publish_current_node(self):
        if not self.active_graph or not (0 <= self.active_index < len(self.active_graph.nodes)):
            return
        node=self.active_graph.nodes[self.active_index]
        node.status="running"
        self.active_graph.updated_ts_ms=now_ms()
        self.bus.publish("behavior.node_ready", {"graph_id": self.active_graph.graph_id, "task_id": self.active_graph.task_id, "goal_type": self.active_graph.goal_type, "node": node.to_dict(), "ts_ms": now_ms()})

    def _guided_retry_allowed(self, runtime_policy: Dict[str, Any]) -> bool:
        recommended = str(runtime_policy.get("recommended_action", "") or "").strip().lower()
        if recommended in {"operator_review", "replan_with_clarification", "guarded_replan", "halt_and_replan"}:
            return False
        return True

    def _apply_retry_guidance(self, node: BehaviorNode, runtime_policy: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        merged_params = dict(node.params or {})
        merged_params.update(dict(params or {}))
        merged_policy = dict(merged_params.get("runtime_recovery_policy", {}) or {})
        merged_policy.update(runtime_policy)
        merged_params["runtime_recovery_policy"] = merged_policy
        guidance = dict(merged_policy.get("execution_guidance", {}) or {})
        if not guidance:
            node.params = merged_params
            return {}
        if bool(guidance.get("requires_slowdown", False)):
            merged_params["requires_slowdown"] = True
        clearance = float(guidance.get("corridor_clearance_m", 0.0) or 0.0)
        if clearance > float(merged_params.get("corridor_clearance_m", 0.0) or 0.0):
            merged_params["corridor_clearance_m"] = clearance
        strategy = str(guidance.get("local_motion_strategy", "") or "").strip()
        if strategy:
            merged_params["local_motion_strategy"] = strategy
        retry_variant = str(guidance.get("retry_variant", "") or "").strip()
        if retry_variant:
            merged_params["retry_variant"] = retry_variant
        recovery_mode = str(guidance.get("recovery_mode", "") or "").strip()
        if recovery_mode:
            merged_params["recovery_mode"] = recovery_mode
        pre_retry_action = str(guidance.get("pre_retry_action", "") or "").strip()
        if pre_retry_action:
            merged_params["pre_retry_action"] = pre_retry_action
        if bool(guidance.get("perception_confirmation_required", False)):
            merged_params["perception_confirmation_required"] = True
        node.params = merged_params
        return guidance

    def _complete_graph(self):
        if self.active_graph:
            self.active_graph.status="completed"
            self.active_graph.updated_ts_ms=now_ms()
            self.bus.publish("behavior.completed", {"graph": self.active_graph.to_dict(), "ts_ms": now_ms()})
            self._publish_task_status("completed")

    def _fail_graph(self, reason: str, node: Optional[BehaviorNode]=None):
        if self.active_graph:
            self.active_graph.status="failed"
            self.active_graph.updated_ts_ms=now_ms()
            self.bus.publish("behavior.failed", {"graph": self.active_graph.to_dict(), "reason": reason, "node": node.to_dict() if node else None, "ts_ms": now_ms()})
            self._publish_task_status("failed")

    def on_task_plan(self, topic: str, msg: Any):
        payload=msg if isinstance(msg, dict) else {}
        graph=self._create_graph(payload)
        if not graph.nodes:
            self.bus.publish("behavior.failed", {"reason": "no_nodes_generated_from_task_plan", "task_plan": payload, "ts_ms": now_ms()})
            return
        self.active_graph=graph
        self.active_index=-1
        self._publish_graph_created()
        self.on_behavior_start("behavior.start", {})

    def on_behavior_start(self, topic: str, msg: Any):
        if not self.active_graph:
            return
        self.active_graph.status="running"
        self.active_graph.updated_ts_ms=now_ms()
        self.active_index=0
        self.bus.publish("behavior.started", {"graph_id": self.active_graph.graph_id, "task_id": self.active_graph.task_id, "goal_type": self.active_graph.goal_type, "ts_ms": now_ms()})
        self._publish_task_status("running")
        self._publish_current_node()

    def on_node_result(self, topic: str, msg: Any):
        if not self.active_graph or not (0 <= self.active_index < len(self.active_graph.nodes)):
            return
        payload=msg if isinstance(msg, dict) else {}
        current=self.active_graph.nodes[self.active_index]
        node_id=str(payload.get("node_id", "") or "")
        if node_id and node_id != current.node_id:
            return
        status=str(payload.get("status", "") or "").lower()
        reason=str(payload.get("reason", "") or "")
        output=dict(payload.get("output", {}) or {})
        params=dict(payload.get("params", {}) or {})
        if status == "completed":
            current.status="completed"
            self.active_graph.metadata["last_node_output"]=output
            self.active_index += 1
            if self.active_index >= len(self.active_graph.nodes):
                self._complete_graph()
            else:
                self._publish_current_node()
            return
        if status == "failed":
            runtime_policy=dict(params.get("runtime_recovery_policy", {}) or {})
            retry_budget=int(runtime_policy.get("retry_budget", current.retry_limit) or 0)
            key=f"retry_count:{current.node_id}"
            retry_count=int(self.active_graph.metadata.get(key, 0) or 0)
            if retry_count < retry_budget and self._guided_retry_allowed(runtime_policy):
                retry_count += 1
                self.active_graph.metadata[key]=retry_count
                current.status="pending"
                guidance = self._apply_retry_guidance(current, runtime_policy, params)
                self.bus.publish("behavior.retrying", {"node_id": current.node_id, "task_id": self.active_graph.task_id, "retry_count": retry_count, "retry_budget": retry_budget, "reason": reason or "node_failed", "runtime_failure_family": str(params.get("runtime_failure_family", "") or ""), "recommended_action": str(runtime_policy.get("recommended_action", "") or ""), "execution_guidance": guidance, "ts_ms": now_ms()})
                self._publish_current_node()
                return
            current.status="failed"
            self.bus.publish("behavior.escalated", {"node_id": current.node_id, "task_id": self.active_graph.task_id, "reason": reason or "node_failed", "runtime_failure_family": str(params.get("runtime_failure_family", "") or ""), "runtime_recovery_policy": runtime_policy, "execution_guidance": dict(runtime_policy.get("execution_guidance", {}) or {}), "ts_ms": now_ms()})
            self._fail_graph(reason or "node_failed", current)

    def on_query(self, topic: str, msg: Any):
        self.bus.publish("behavior.result", {"graph": self.active_graph.to_dict() if self.active_graph else None, "active_index": self.active_index, "ts_ms": now_ms()})
