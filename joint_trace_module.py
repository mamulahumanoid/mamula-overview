# core/modules/joint_trace_module.py
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional

from core.bus.event_bus import EventBus
from core.runtime.runtime import Runtime


def _now_ms() -> int:
    return int(time.time() * 1000)


def _jsonable(x: Any) -> Any:
    if x is None:
        return None
    if is_dataclass(x):
        try:
            return asdict(x)
        except Exception:
            return {"__dataclass__": x.__class__.__name__}
    if isinstance(x, (str, int, float, bool, list, dict)):
        return x
    return {"__type__": x.__class__.__name__, "__repr__": repr(x)[:500]}


class JointTraceModule:
    """Compact joint trace recorder (robot yokken en kritik debug aracı).

    Subscribes:
      - joints.frame  (JointFrame)

    Output:
      - ./logs/joint_trace_YYYYMMDD_HHMMSS.jsonl

    Downsampling:
      - every_n: record each N-th frame
      - every_ms: record if at least this many ms passed since last record
        (both apply with AND; if one is disabled, the other can still throttle)
    """

    name = "joint_trace"

    def __init__(
        self,
        bus: EventBus,
        rt: Runtime,
        log_dir: str = "./logs",
        every_n: int = 2,
        every_ms: int = 0,
        prefix: str = "joint_trace_",
        console: bool = False,
    ):
        self.bus = bus
        self.rt = rt

        self.log_dir = (log_dir or "./logs").strip()
        os.makedirs(self.log_dir, exist_ok=True)

        ts = time.strftime("%Y%m%d_%H%M%S")
        self.path = os.path.join(self.log_dir, f"{prefix}{ts}.jsonl")
        self._fh = open(self.path, "a", encoding="utf-8")

        self.every_n = max(1, int(every_n))
        self.every_ms = max(0, int(every_ms))
        self.console = bool(console)

        self._seq = 0
        self._frame_count = 0
        self._last_ms = 0

        bus.subscribe("joints.frame", self.on_frame)

        if self.console:
            print(f"[joint.trace] enabled ✅ -> {self.path}")

    def tick(self):
        self.rt.beat(self.name)

    def close(self):
        try:
            self._fh.flush()
            self._fh.close()
        except Exception:
            pass

    def _write(self, payload: Dict[str, Any]):
        rec = {
            "ts_ms": _now_ms(),
            "seq": self._seq,
            "payload": payload,
        }
        self._seq += 1
        self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._fh.flush()

    def on_frame(self, topic: str, msg: Any):
        self._frame_count += 1
        if (self._frame_count % self.every_n) != 0:
            return

        if self.every_ms > 0:
            now = _now_ms()
            if self._last_ms and (now - self._last_ms) < self.every_ms:
                return
            self._last_ms = now

        payload = _jsonable(msg)
        self._write(payload)
