"""Shadow-only bridge from legacy planner events to Agent Runtime v1."""

from __future__ import annotations

import hashlib
import re
import time
from typing import Any, Callable, Mapping

from core.agent_runtime import (
    AgentBudgets,
    AgentRunState,
    AgentRuntime,
    ContextSnapshot,
    GoalContract,
    Observation,
    PlanRevision,
    PlanStep,
    ReplanAuthorization,
    VerificationDecision,
    VerificationStatus,
)
from core.contract.message_envelope_v1 import payload_only

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _system_clock_ms() -> int:
    return int(time.time() * 1000)


def _payload(msg: Any) -> dict[str, Any]:
    if not isinstance(msg, Mapping):
        return {}
    unwrapped = payload_only(dict(msg))
    return dict(unwrapped) if unwrapped else dict(msg)


def _safe_id(value: str, prefix: str) -> str:
    normalized = str(value or "").strip()
    if _SAFE_ID.fullmatch(normalized):
        return normalized
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}-{digest}"


class AgentRuntimeBridgeModule:
    """Mirror explicitly opted-in sandbox plans without controlling execution."""

    name = "agent_runtime_bridge"

    def __init__(
        self,
        bus: Any,
        rt: Any,
        *,
        agent_runtime: AgentRuntime,
        clock_ms: Callable[[], int] = _system_clock_ms,
    ) -> None:
        self.bus = bus
        self.rt = rt
        self.agent_runtime = agent_runtime
        self._clock_ms = clock_ms
        self._run_by_task: dict[str, str] = {}
        bus.subscribe("planner.goal", self.on_goal)
        bus.subscribe("planner.task_plan", self.on_plan)
        bus.subscribe("exec.done", self.on_legacy_exec_done)
        bus.subscribe("exec.timeout", self.on_legacy_exec_done)
        bus.subscribe("agent.runtime.action_request", self.on_action_request)
        bus.subscribe("agent.runtime.observation", self.on_observation)
        bus.subscribe("agent.runtime.verification_decision", self.on_verification_decision)
        bus.subscribe("planner.recovery_request", self.on_recovery_request)
        bus.subscribe("agent.runtime.replan_candidate", self.on_replan_candidate)

    def tick(self) -> None:
        try:
            self.rt.beat(self.name)
        except Exception:
            return

    def on_goal(self, _topic: str, msg: Any) -> None:
        data = _payload(msg)
        if not self._sandbox_opted_in(data):
            return
        task_id = str(data.get("task_id") or "").strip()
        session_id = str(data.get("session_id") or "").strip()
        goal = data.get("goal")
        goal = dict(goal) if isinstance(goal, Mapping) else {}
        if not task_id or not session_id or not goal or task_id in self._run_by_task:
            self._emit_rejected(task_id, "sandbox_goal_incomplete_or_duplicate")
            return
        goal_text = str(goal.get("description") or goal.get("goal_type") or "").strip()
        if not goal_text:
            self._emit_rejected(task_id, "goal_description_missing")
            return
        now = int(self._clock_ms())
        run = self.agent_runtime.create_run(
            goal=GoalContract(
                goal_id=_safe_id(str(goal.get("goal_id") or task_id), "goal"),
                description=goal_text,
                success_criteria=("bound observation satisfies the planned sandbox goal",),
                required_evidence_sources=("agent.runtime.observation",),
            ),
            budgets=AgentBudgets(16, 16, 3, 2, 8_192, 120_000),
            session_id=_safe_id(session_id, "session"),
            actor="legacy_event_bridge",
            mode="sandbox",
            risk=str(goal.get("risk") or "unknown"),
        )
        context_data = data.get("context")
        context_data = dict(context_data) if isinstance(context_data, Mapping) else {"goal": goal}
        context = ContextSnapshot(
            context_id=f"context-{run.run_id[:24]}",
            run_id=run.run_id,
            source="planner.goal",
            source_version="legacy-shadow-v1",
            captured_at_ms=now,
            freshness_ms=30_000,
            confidence=1.0,
            data=context_data,
        )
        state = self.agent_runtime.attach_context(run.run_id, context)
        self._run_by_task[task_id] = run.run_id
        self._emit_state(task_id, state, "goal_mirrored")

    def on_plan(self, _topic: str, msg: Any) -> None:
        data = _payload(msg)
        task_id = str(data.get("task_id") or "").strip()
        run_id = self._run_by_task.get(task_id)
        if not run_id:
            return
        if data.get("preview_only") is True:
            self._emit_rejected(task_id, "preview_plan_not_executable")
            return
        raw_steps = [dict(item) for item in list(data.get("steps") or []) if isinstance(item, Mapping)]
        if not raw_steps:
            self._emit_rejected(task_id, "plan_has_no_observable_steps")
            return
        run = self.agent_runtime.get(run_id)
        if run.state != AgentRunState.CONTEXT_READY:
            self._emit_rejected(task_id, f"plan_state_invalid:{run.state.value}")
            return
        steps = tuple(
            PlanStep(
                step_id=_safe_id(str(step.get("step_id") or f"step-{index}"), "step"),
                operation=str(step.get("title") or step.get("action_type") or step.get("cmd_type") or "sandbox_step"),
                expected_observation_sources=("agent.runtime.observation",),
                preconditions=tuple(str(item) for item in list(step.get("preconditions") or [])),
                rollback=str(step.get("rollback") or ""),
            )
            for index, step in enumerate(raw_steps, start=1)
        )
        plan = PlanRevision(
            plan_id=f"plan-{run_id[:20]}-1",
            run_id=run_id,
            revision=1,
            parent_plan_id="",
            created_at_ms=int(self._clock_ms()),
            steps=steps,
            reason="legacy planner.task_plan shadow mirror",
        )
        state = self.agent_runtime.set_plan(run_id, plan)
        self._emit_state(task_id, state, "plan_mirrored")

    def on_legacy_exec_done(self, topic: str, msg: Any) -> None:
        data = _payload(msg)
        task_id = str(data.get("task_id") or "").strip()
        run_id = self._run_by_task.get(task_id)
        if not run_id:
            return
        run = self.agent_runtime.get(run_id)
        self.bus.publish(
            "agent.runtime.legacy_result_ignored",
            {
                "task_id": task_id,
                "agent_run_id": run_id,
                "source_topic": topic,
                "state": run.state.value,
                "reason": "legacy_result_lacks_bound_action_observation_and_verification",
                "done": False,
            },
        )

    def on_action_request(self, _topic: str, msg: Any) -> None:
        data = _payload(msg)
        task_id = str(data.get("task_id") or "").strip()
        run_id = self._run_by_task.get(task_id)
        if not run_id:
            return
        if str(data.get("kind") or "") != "skill":
            self._emit_rejected(task_id, "shadow_bridge_accepts_sandbox_skill_requests_only")
            return
        try:
            state = self.agent_runtime.request_action(
                run_id,
                step_id=str(data.get("step_id") or ""),
                kind="skill",
                target=str(data.get("target") or ""),
            )
        except (RuntimeError, ValueError) as exc:
            self._emit_rejected(task_id, f"action_request_rejected:{exc}")
            return
        assert state.current_action is not None
        self.bus.publish(
            "agent.runtime.authorization_required",
            {
                "task_id": task_id,
                "agent_run_id": run_id,
                "action_attempt_id": state.current_action.attempt_id,
                "kind": state.current_action.kind,
                "target": state.current_action.target,
                "state": state.state.value,
                "execution_started": False,
            },
        )
        self._emit_state(task_id, state, "action_requested_authorization_required")

    def on_observation(self, _topic: str, msg: Any) -> None:
        data = _payload(msg)
        task_id = str(data.get("task_id") or "").strip()
        run_id = self._run_by_task.get(task_id)
        if not run_id:
            return
        run = self.agent_runtime.get(run_id)
        if run.plan is None or run.current_action is None:
            self._emit_rejected(task_id, "observation_has_no_bound_action")
            return
        try:
            observation = Observation(
                observation_id=_safe_id(str(data.get("observation_id") or ""), "observation"),
                run_id=run_id,
                plan_id=run.plan.plan_id,
                action_attempt_id=str(data.get("action_attempt_id") or ""),
                source="agent.runtime.observation",
                source_version=str(data.get("source_version") or "1"),
                observed_at_ms=int(data.get("observed_at_ms") or self._clock_ms()),
                received_at_ms=int(self._clock_ms()),
                confidence=float(data.get("confidence", 0.0) or 0.0),
                payload=dict(data.get("payload") or {}) if isinstance(data.get("payload"), Mapping) else {},
            )
            state = self.agent_runtime.attach_observation(run_id, observation)
        except (RuntimeError, TypeError, ValueError) as exc:
            self._emit_rejected(task_id, f"observation_rejected:{exc}")
            return
        self.bus.publish(
            "agent.runtime.verification_required",
            {
                "task_id": task_id,
                "agent_run_id": run_id,
                "observation_id": observation.observation_id,
                "observation_digest": observation.digest,
                "state": state.state.value,
            },
        )
        self._emit_state(task_id, state, "observation_bound_verification_required")

    def on_verification_decision(self, _topic: str, msg: Any) -> None:
        data = _payload(msg)
        task_id = str(data.get("task_id") or "").strip()
        run_id = self._run_by_task.get(task_id)
        raw = data.get("decision")
        raw = dict(raw) if isinstance(raw, Mapping) else {}
        if not run_id or not raw:
            return
        try:
            decision = VerificationDecision(
                verification_id=str(raw["verification_id"]),
                run_id=str(raw["run_id"]),
                goal_digest=str(raw["goal_digest"]),
                plan_id=str(raw["plan_id"]),
                action_attempt_id=str(raw["action_attempt_id"]),
                observation_id=str(raw["observation_id"]),
                observation_digest=str(raw["observation_digest"]),
                status=VerificationStatus(str(raw["status"])),
                reason=str(raw["reason"]),
                verified_at_ms=int(raw["verified_at_ms"]),
                verifier=str(raw["verifier"]),
                signature=str(raw["signature"]),
            )
            state = self.agent_runtime.apply_verification(run_id, decision)
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            self._emit_rejected(task_id, f"verification_rejected:{exc}")
            return
        self._emit_state(task_id, state, "signed_verification_applied")

    def on_recovery_request(self, _topic: str, msg: Any) -> None:
        data = _payload(msg)
        task_id = str(data.get("task_id") or "").strip()
        run_id = self._run_by_task.get(task_id)
        if not run_id:
            return
        run = self.agent_runtime.get(run_id)
        self.bus.publish(
            "agent.runtime.replan_review_required",
            {
                "task_id": task_id,
                "agent_run_id": run_id,
                "state": run.state.value,
                "reason": str(data.get("reason") or "legacy_recovery_request"),
                "automatic_replan_applied": False,
            },
        )

    def on_replan_candidate(self, _topic: str, msg: Any) -> None:
        """Apply only an exact reviewed plan carrying a trusted signature."""

        data = _payload(msg)
        task_id = str(data.get("task_id") or "").strip()
        run_id = self._run_by_task.get(task_id)
        raw_authorization = data.get("authorization")
        raw_authorization = dict(raw_authorization) if isinstance(raw_authorization, Mapping) else {}
        raw_steps = [dict(item) for item in list(data.get("steps") or []) if isinstance(item, Mapping)]
        if not run_id or not raw_authorization or not raw_steps:
            self._emit_rejected(task_id, "signed_replan_candidate_incomplete")
            return
        run = self.agent_runtime.get(run_id)
        if run.plan is None or run.state != AgentRunState.REPLAN_REQUIRED:
            self._emit_rejected(task_id, f"replan_state_invalid:{run.state.value}")
            return
        try:
            plan = PlanRevision(
                plan_id=str(data["plan_id"]),
                run_id=run_id,
                revision=int(data["revision"]),
                parent_plan_id=str(data["parent_plan_id"]),
                created_at_ms=int(data["created_at_ms"]),
                steps=tuple(
                    PlanStep(
                        step_id=str(step["step_id"]),
                        operation=str(step["operation"]),
                        expected_observation_sources=tuple(step["expected_observation_sources"]),
                        preconditions=tuple(step.get("preconditions") or ()),
                        rollback=str(step.get("rollback") or ""),
                    )
                    for step in raw_steps
                ),
                reason=str(data["reason"]),
            )
            authorization = ReplanAuthorization(
                authorization_id=str(raw_authorization["authorization_id"]),
                run_id=str(raw_authorization["run_id"]),
                current_plan_id=str(raw_authorization["current_plan_id"]),
                candidate_plan_id=str(raw_authorization["candidate_plan_id"]),
                candidate_plan_digest=str(raw_authorization["candidate_plan_digest"]),
                review_id=str(raw_authorization["review_id"]),
                review_digest=str(raw_authorization["review_digest"]),
                actor=str(raw_authorization["actor"]),
                session_id=str(raw_authorization["session_id"]),
                issued_at_ms=int(raw_authorization["issued_at_ms"]),
                expires_at_ms=int(raw_authorization["expires_at_ms"]),
                issuer=str(raw_authorization["issuer"]),
                signature=str(raw_authorization["signature"]),
            )
            state = self.agent_runtime.set_authorized_replan(
                run_id,
                plan,
                authorization=authorization,
                tokens_used=int(data.get("tokens_used") or 0),
            )
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            self._emit_rejected(task_id, f"replan_rejected:{exc}")
            return
        self._emit_state(task_id, state, "signed_reviewed_replan_applied")

    def run_id_for_task(self, task_id: str) -> str:
        return self._run_by_task.get(str(task_id), "")

    @staticmethod
    def _sandbox_opted_in(data: Mapping[str, Any]) -> bool:
        return data.get("agent_runtime_shadow") is True and str(data.get("execution_mode") or "") == "sandbox"

    def _emit_state(self, task_id: str, run: Any, reason: str) -> None:
        self.bus.publish(
            "agent.runtime.shadow_state",
            {
                "task_id": task_id,
                "agent_run_id": run.run_id,
                "state": run.state.value,
                "terminal": run.terminal_state,
                "reason": reason,
                "trace_head": str(run.trace[-1]["event_hash"]) if run.trace else "",
            },
        )

    def _emit_rejected(self, task_id: str, reason: str) -> None:
        self.bus.publish(
            "agent.runtime.shadow_rejected",
            {"task_id": task_id, "reason": reason, "done": False},
        )


__all__ = ["AgentRuntimeBridgeModule"]
