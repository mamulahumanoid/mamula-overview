from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from core.contract.commands import CommandIssued
from core.contract.types import Meta


def _ms() -> int:
    return int(time.time() * 1000)


class AutonomyLoopModule:
    """A minimal autonomy loop.

    Goals:
      - In AUTO mode, periodically triggers a knowledge refresh via FETCH_API.

    Modes:
      - MANUAL: do nothing
      - ASSIST: (reserved) could do light background tasks
      - AUTO: generate goals periodically

    Control:
      - env AUTONOMY_MODE=MANUAL|ASSIST|AUTO
      - topic autonomy.set_mode {mode}
      - cmd_type SET_MODE params {mode}
    """

    name = "autonomy_loop"

    def __init__(self, bus, rt, period_sec: float = 120.0, default_provider: str = "wttr", default_query: str = "Istanbul"):
        self.bus = bus
        self.rt = rt

        self.period_sec = max(5.0, float(period_sec))
        self.default_provider = str(default_provider)
        self.default_query = str(default_query)

        self.mode = str(os.getenv("AUTONOMY_MODE", "MANUAL")).strip().upper() or "MANUAL"
        self._t_last = 0.0

        bus.subscribe("autonomy.set_mode", self.on_set_mode)
        bus.subscribe("dispatch.cmd", self.on_cmd)  # backward compatibility
        bus.subscribe("dispatch.skill_cmd", self.on_cmd)

    def tick(self):
        try:
            self.rt.beat(self.name)
        except Exception:
            pass

        if self.mode != "AUTO":
            return

        t = time.time()
        if (t - self._t_last) < self.period_sec:
            return
        self._t_last = t

        # Generate a simple background skill command on the canonical skill channel.
        cmd = self._mk_cmd_fetch_api(provider=self.default_provider, query=self.default_query, key=f"auto:{self.default_provider}:{self.default_query}")
        self.bus.publish("dispatch.skill_cmd", cmd)

    def on_set_mode(self, topic: str, msg: Any):
        if isinstance(msg, dict):
            m = str(msg.get("mode") or "").strip().upper()
        else:
            m = str(msg or "").strip().upper()
        if m in ("MANUAL", "ASSIST", "AUTO"):
            self.mode = m
            self.bus.publish("voice.say", {"text": f"Otonomi modu: {m}", "lang": "tr"})

    def on_cmd(self, topic: str, msg: Any):
        if not isinstance(msg, CommandIssued):
            return
        if (msg.cmd_type or "").upper().strip() != "SET_MODE":
            return
        m = str((msg.params or {}).get("mode") or "").strip().upper()
        if m in ("MANUAL", "ASSIST", "AUTO"):
            self.mode = m
            self.bus.publish("voice.say", {"text": f"Otonomi modu: {m}", "lang": "tr"})

    def _mk_cmd_fetch_api(self, provider: str, query: str, key: str = "") -> CommandIssued:
        now = _ms()
        meta = Meta(
            id=f"cmd-{now}-auto",
            ts_ms=now,
            seq=0,
            source=self.name,
            correlation_id=f"auto-{now}",
            extra={},
        )
        return CommandIssued(
            meta=meta,
            plan_id=f"plan-auto-{now}",
            step_id="auto",
            cmd_type="FETCH_API",
            params={"provider": provider, "query": query, "key": key, "ttl_sec": 3600},
            priority=0,
            cancel_previous=False,
        )
