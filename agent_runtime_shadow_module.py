"""Feature-flagged, sandbox-only bootstrap owner for Agent Runtime v1."""

from __future__ import annotations

import os
import time
from typing import Any

from core.agent_runtime import (
    AgentRuntime,
    ReplanAuthorizationPolicy,
    SkillAuthorizationPolicy,
    TrustedAgentVerifier,
    TrustedReplanAuthorizer,
    TrustedSkillAuthorizer,
)
from core.modules.agent_runtime_bridge_module import AgentRuntimeBridgeModule


def _clock_ms() -> int:
    return int(time.time() * 1000)


def _secret_from_env(name: str) -> bytes:
    raw = str(os.getenv(name, "") or "").strip()
    try:
        value = bytes.fromhex(raw)
    except ValueError as exc:
        raise ValueError(f"{name.lower()}_must_be_hex") from exc
    if len(value) < 32:
        raise ValueError(f"{name.lower()}_requires_32_bytes")
    return value


def _skill_targets_from_env() -> frozenset[str]:
    values = frozenset(
        item.strip()
        for item in str(os.getenv("MAMULA_AGENT_RUNTIME_SKILL_TARGETS", "") or "").split(",")
        if item.strip()
    )
    if not values:
        raise ValueError("mamula_agent_runtime_skill_targets_required")
    if "*" in values:
        raise ValueError("mamula_agent_runtime_wildcard_skill_target_forbidden")
    return values


class AgentRuntimeShadowModule:
    """Own trusted runtime dependencies without granting execution authority."""

    name = "agent_runtime_shadow"

    def __init__(self, bus: Any, rt: Any) -> None:
        verifier_secret = _secret_from_env("MAMULA_AGENT_VERIFIER_SECRET_HEX")
        skill_secret = _secret_from_env("MAMULA_AGENT_SKILL_AUTH_SECRET_HEX")
        replan_secret = _secret_from_env("MAMULA_AGENT_REPLAN_AUTH_SECRET_HEX")
        skill_targets = _skill_targets_from_env()
        self.agent_runtime = AgentRuntime(
            verifier=TrustedAgentVerifier(secret=verifier_secret, clock_ms=_clock_ms),
            skill_authorizer=TrustedSkillAuthorizer(
                secret=skill_secret,
                policy=SkillAuthorizationPolicy(
                    allowed_actors=frozenset({"legacy_event_bridge"}),
                    allowed_targets=skill_targets,
                    allowed_scopes=frozenset({"skill.execute"}),
                    ttl_ms=30_000,
                    max_attempts=1,
                ),
                clock_ms=_clock_ms,
            ),
            replan_authorizer=TrustedReplanAuthorizer(
                secret=replan_secret,
                policy=ReplanAuthorizationPolicy(
                    allowed_actors=frozenset({"legacy_event_bridge"}),
                    max_plan_steps=16,
                    ttl_ms=30_000,
                ),
                clock_ms=_clock_ms,
            ),
            clock_ms=_clock_ms,
        )
        self.bridge = AgentRuntimeBridgeModule(bus, rt, agent_runtime=self.agent_runtime, clock_ms=_clock_ms)

    def tick(self) -> None:
        self.bridge.tick()


__all__ = ["AgentRuntimeShadowModule"]
