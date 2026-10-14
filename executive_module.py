# core/modules/executive_module.py
from __future__ import annotations

import time
import threading
from typing import Any, Dict, Optional

from core.contract.message_envelope_v1 import payload_only

# --- robust imports (repo yapısına göre otomatik bulur) ---
try:
    from core.contract.commands import CommandIssued
except Exception:
    try:
        from core.contract.events import CommandIssued  # type: ignore
    except Exception:
        CommandIssued = None  # type: ignore

try:
    from core.contract.meta import Meta
except Exception:
    try:
        from core.contract.types import Meta
    except Exception:
        try:
            from core.contract.commands import Meta  # type: ignore
        except Exception:
            Meta = None  # type: ignore


def _ms() -> int:
    return int(time.time() * 1000)


def _meta_from_any(meta_any: Any):
    """
    Meta(dict|object) -> Meta object (best-effort)
    """
    if Meta is None:
        return meta_any  # no-op

    if meta_any is None:
        return Meta(id=f"meta-{_ms()}", ts_ms=_ms(), seq=0, source="executive", correlation_id="", session_id="", turn_id="", trace_id="", parent_id="", extra={})

    if isinstance(meta_any, Meta):
        return meta_any

    if isinstance(meta_any, dict):
        d = dict(meta_any)
        # normalize fields
        d.setdefault("id", f"meta-{_ms()}")
        d.setdefault("ts_ms", _ms())
        d.setdefault("seq", 0)
        d.setdefault("source", "executive")
        d.setdefault("correlation_id", d.get("correlation_id", "") or "")
        d.setdefault("extra", {})
        if not isinstance(d.get("extra"), dict):
            d["extra"] = {}

        # Some Meta definitions may not accept unknown keys; filter.
        allowed = {"id", "ts_ms", "seq", "source", "correlation_id", "session_id", "turn_id", "trace_id", "parent_id", "extra"}
        kwargs = {k: d[k] for k in allowed if k in d}
        try:
            return Meta(**kwargs)
        except Exception:
            # fallback: try positional-ish by attribute setting
            try:
                m = Meta(  # type: ignore
                    id=kwargs.get("id", f"meta-{_ms()}"),
                    ts_ms=int(kwargs.get("ts_ms", _ms())),
                    seq=int(kwargs.get("seq", 0)),
                    source=str(kwargs.get("source", "executive")),
                    correlation_id=str(kwargs.get("correlation_id", "")),
                    session_id=str(kwargs.get("session_id", "")),
                    turn_id=str(kwargs.get("turn_id", "")),
                    trace_id=str(kwargs.get("trace_id", "")),
                    parent_id=str(kwargs.get("parent_id", "")),
                    extra=dict(kwargs.get("extra", {}) or {}),
                )
                return m
            except Exception:
                return meta_any

    # object-ish
    try:
        return Meta(
            id=str(getattr(meta_any, "id", "") or f"meta-{_ms()}"),
            ts_ms=int(getattr(meta_any, "ts_ms", _ms()) or _ms()),
            seq=int(getattr(meta_any, "seq", 0) or 0),
            source=str(getattr(meta_any, "source", "executive") or "executive"),
            correlation_id=str(getattr(meta_any, "correlation_id", "") or ""),
            session_id=str(getattr(meta_any, "session_id", "") or ""),
            turn_id=str(getattr(meta_any, "turn_id", "") or ""),
            trace_id=str(getattr(meta_any, "trace_id", "") or ""),
            parent_id=str(getattr(meta_any, "parent_id", "") or ""),
            extra=dict(getattr(meta_any, "extra", {}) or {}),
        )
    except Exception:
        return meta_any


def _cmd_from_any(msg: Any) -> Optional["CommandIssued"]:
    """
    CommandIssued|dict -> CommandIssued
    """
    if CommandIssued is None:
        return None

    if isinstance(msg, CommandIssued):
        return msg

    if not isinstance(msg, dict):
        return None

    payload = payload_only(msg)
    if payload:
        value = payload.get("value")
        if CommandIssued is not None and isinstance(value, CommandIssued):
            return value
        msg = payload

    meta_obj = _meta_from_any(msg.get("meta"))
    plan_id = str(msg.get("plan_id", "") or "")
    step_id = str(msg.get("step_id", "") or "")
    cmd_type = str(msg.get("cmd_type", "") or "").upper().strip() or "SAY"
    params = msg.get("params") or {}
    if not isinstance(params, dict):
        params = {"text": str(params)}
    priority = int(msg.get("priority", 0) or 0)
    cancel_previous = bool(msg.get("cancel_previous", False))

    try:
        return CommandIssued(
            meta=meta_obj,
            plan_id=plan_id,
            step_id=step_id,
            cmd_type=cmd_type,
            params=params,
            priority=priority,
            cancel_previous=cancel_previous,
        )
    except Exception:
        # If CommandIssued signature differs, best-effort:
        try:
            return CommandIssued(meta_obj, plan_id, step_id, cmd_type, params, priority, cancel_previous)  # type: ignore
        except Exception:
            return None


class ExecutiveModule:
    """
    exec.cmd_safe -> dispatch.motion_cmd OR dispatch.skill_cmd

    completion sources:
      - motion: motion.status (COMPLETED/CANCELED/ERROR)
      - skill : exec.done    (state COMPLETED/ERROR)

    NOTE:
      - SAY motion değildir. SAY -> voice.say hattına gider ve exec.done ile hemen biter.
      - ✅ exec.cmd_safe artık dict gelebilir (ReflexSafety JSON-safe yayınlıyor)
        burada dict -> CommandIssued normalize ediyoruz.
    """

    name = "executive"

    def __init__(self, bus, runtime, timeout_ms: int = 6500, retry_max: int = 1, **kwargs):
        self.bus = bus
        self.runtime = runtime
        self.timeout_ms = int(timeout_ms)
        self.retry_max = int(retry_max)

        self._pending_lock = threading.Lock()
        self._pending: Dict[str, Dict[str, Any]] = {}  # cmd_id -> state

        self.bus.subscribe("exec.cmd_safe", self.on_cmd_safe)
        self.bus.subscribe("motion.status", self.on_motion_status)
        self.bus.subscribe("exec.done", self.on_exec_done)

    def _beat(self):
        try:
            self.runtime.heartbeat(self.name)
        except Exception:
            try:
                self.runtime.beat(self.name)
            except Exception:
                pass

    def tick(self):
        self._beat()

    def _is_motion_type(self, t: str) -> bool:
        t = (t or "").upper().strip()
        return t in ("STOP", "WALK", "TURN", "TURN_IN_PLACE", "SET_POSE")

    def _route_topic(self, cmd: "CommandIssued") -> str:
        t = (cmd.cmd_type or "").upper().strip()
        return "dispatch.motion_cmd" if self._is_motion_type(t) else "dispatch.skill_cmd"

    def on_cmd_safe(self, topic: str, msg: Any):
        self._beat()

        cmd = _cmd_from_any(msg) if not (CommandIssued is not None and isinstance(msg, CommandIssued)) else msg
        if cmd is None:
            return

        cmd_type = (cmd.cmd_type or "").upper().strip()

        cmd_id = str(getattr(getattr(cmd, "meta", None), "id", "") or "") or f"cmd-unknown-{_ms()}"
        corr = str(getattr(getattr(cmd, "meta", None), "correlation_id", "") or "") or cmd_id

        # ---- SAY direkt voice hattına ----
        if cmd_type == "SAY":
            params = cmd.params if isinstance(cmd.params, dict) else {}
            text = str(params.get("text", "") or "")
            lang = str(params.get("lang", "tr") or "tr")
            if text:
                self.bus.publish("voice.say", {"text": text, "lang": lang})
            self.bus.publish("exec.done", {"cmd_id": cmd_id, "state": "COMPLETED", "ok": True})
            return

        route = self._route_topic(cmd)
        is_motion = (route == "dispatch.motion_cmd")

        with self._pending_lock:
            self._pending[cmd_id] = {
                "cmd": cmd,
                "cmd_id": cmd_id,
                "corr": corr,
                "route": route,
                "is_motion": is_motion,
                "start_ms": _ms(),
                "retry_count": int((cmd.params or {}).get("retry_count", 0) or 0)
                if isinstance(cmd.params, dict)
                else 0,
                "done": False,
            }

        # publish downstream (MotionModule expects CommandIssued)
        self.bus.publish(route, cmd)

        # watchdog thread for this cmd_id
        th = threading.Thread(target=self._watchdog, args=(cmd_id,), daemon=True)
        th.start()

    def _watchdog(self, cmd_id: str):
        while True:
            time.sleep(0.05)
            self._beat()

            with self._pending_lock:
                st = self._pending.get(cmd_id)
                if not st:
                    return
                if st.get("done"):
                    self._pending.pop(cmd_id, None)
                    return

                start_ms = int(st.get("start_ms", _ms()))
                if (_ms() - start_ms) < self.timeout_ms:
                    continue

                cmd: "CommandIssued" = st["cmd"]
                retry_count = int(st.get("retry_count", 0))
                is_motion = bool(st.get("is_motion", False))

                if retry_count < self.retry_max:
                    retry_count += 1
                    st["retry_count"] = retry_count
                    st["start_ms"] = _ms()

                    try:
                        if cmd.params is None:
                            cmd.params = {}
                        if isinstance(cmd.params, dict):
                            cmd.params["retry"] = True
                            cmd.params["retry_count"] = retry_count
                    except Exception:
                        pass

                    # motion timeout ise STOP bas
                    if is_motion and CommandIssued is not None and Meta is not None:
                        try:
                            extra = dict(getattr(getattr(cmd, "meta", None), "extra", {}) or {})
                            stop_cmd = CommandIssued(
                                meta=Meta(
                                    id=f"exec-stop-{_ms()}-0",
                                    ts_ms=_ms(),
                                    seq=0,
                                    source=self.name,
                                    correlation_id=cmd_id,
                                    extra={"session_id": extra.get("session_id", "")},
                                ),
                                plan_id=f"preempt-{cmd_id}",
                                step_id="stop",
                                cmd_type="STOP",
                                params={"reason": "executive_stop"},
                                priority=100,
                                cancel_previous=True,
                            )
                            self.bus.publish("dispatch.motion_cmd", stop_cmd)
                        except Exception:
                            pass

                    # retry publish
                    self.bus.publish(st["route"], cmd)
                    continue

                # retry exhausted
                self.bus.publish("exec.timeout", {"cmd_id": cmd_id, "corr": st.get("corr", ""), "route": st.get("route", ""), "retry_count": retry_count, "ts_ms": _ms()})
                self.bus.publish("exec.done", {"cmd_id": cmd_id, "state": "ERROR", "ok": False, "reason": "timeout"})
                st["done"] = True
                self._pending.pop(cmd_id, None)
                return

    def on_motion_status(self, topic: str, msg: Any):
        self._beat()
        try:
            cmd_id = str(getattr(msg, "cmd_id", "") or "")
            state = str(getattr(msg, "state", "") or "").upper().strip()
        except Exception:
            return

        if not cmd_id:
            return

        if state in ("COMPLETED", "CANCELED", "ERROR", "FAILED"):
            with self._pending_lock:
                st = self._pending.get(cmd_id)
                if not st:
                    return
                if not st.get("is_motion", False):
                    return
                st["done"] = True
                self._pending.pop(cmd_id, None)

    def on_exec_done(self, topic: str, msg: Any):
        self._beat()
        if not isinstance(msg, dict):
            return
        cmd_id = str(msg.get("cmd_id", "") or "")
        state = str(msg.get("state", "") or "").upper().strip()
        if not cmd_id:
            return
        if state not in ("COMPLETED", "ERROR"):
            return

        with self._pending_lock:
            st = self._pending.get(cmd_id)
            if not st:
                return
            if st.get("is_motion", False):
                return
            st["done"] = True
            self._pending.pop(cmd_id, None)
