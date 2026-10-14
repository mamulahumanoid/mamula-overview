from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional

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
    if isinstance(x, (str, int, float, bool)):
        return x
    if isinstance(x, list):
        return [_jsonable(v) for v in x]
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if hasattr(x, "__dict__"):
        try:
            return {str(k): _jsonable(v) for k, v in vars(x).items()}
        except Exception:
            pass
    return {"__type__": x.__class__.__name__, "__repr__": repr(x)[:500]}


class EpisodeWriterModule:
    """Collect task-centered episodes from live event bus traffic.

    Intent:
      - Convert runtime activity into task/episode JSON files.
      - Provide a stable unit for offline dataset building.
      - Stay non-invasive: it only subscribes and writes files.

    Opening rule:
      - voice.task starts a new episode.

    Closing rule:
      - motion.status success/failure-like states close the episode.
      - inactivity timeout also closes the episode.
    """

    name = "episode_writer"

    def __init__(
        self,
        bus: EventBus,
        rt: Runtime,
        out_dir: str = "./data/episodes/normalized",
        timeout_ms: int = 15000,
        prefix: str = "ep_",
    ):
        self.bus = bus
        self.rt = rt
        self.out_dir = (out_dir or "./data/episodes/normalized").strip()
        self.timeout_ms = max(1000, int(timeout_ms))
        self.prefix = prefix or "ep_"
        os.makedirs(self.out_dir, exist_ok=True)

        self.active: Optional[Dict[str, Any]] = None
        self._seq = 0

        bus.subscribe("voice.task", self.on_voice_task)
        bus.subscribe("planner.plan", self.on_plan)
        bus.subscribe("dispatch.cmd", self.on_dispatch)
        bus.subscribe("dispatch.motion_cmd", self.on_motion_cmd)
        bus.subscribe("motion.status", self.on_motion_status)
        bus.subscribe("joints.frame", self.on_joint_frame)
        bus.subscribe("reasoning.intent", self.on_reasoning_intent)
        bus.subscribe("task.event", self.on_task_event)
        bus.subscribe("status.report", self.on_status_report)

        print(f"[episode.writer] enabled -> {self.out_dir}")

    def tick(self):
        self.rt.beat(self.name)
        if not self.active:
            return
        now = _now_ms()
        last_activity = int(self.active.get("_meta", {}).get("last_activity_ms", now))
        if (now - last_activity) > self.timeout_ms:
            self._finalize(status="timeout", success=False, failure_reason="episode_timeout")

    def close(self):
        if self.active:
            self._finalize(status="closed", success=False, failure_reason="runtime_shutdown")

    def on_voice_task(self, topic: str, msg: Any):
        payload = _jsonable(msg)
        if self.active:
            self._finalize(status="interrupted", success=False, failure_reason="new_voice_task_started")

        text = self._pick(payload, "text", default="")
        lang = self._pick(payload, "lang", default="tr")
        confidence = float(self._pick(payload, "confidence", default=0.0) or 0.0)

        now = _now_ms()
        self._seq += 1
        episode_id = f"{self.prefix}{now}_{self._seq:06d}"
        session_id = self._infer_session_id()

        self.active = {
            "episode_id": episode_id,
            "session_id": session_id,
            "started_at_ms": now,
            "ended_at_ms": now,
            "duration_ms": 0,
            "source_files": {
                "session_log": "",
                "motion_trace": "",
                "joint_trace": "",
            },
            "instruction": {
                "text": text or "",
                "lang": lang or "tr",
                "confidence": confidence,
            },
            "context": {
                "active_identity": str(self._pick(payload, "speaker", default="")) or "",
                "world_state_before": {},
                "memory_hits": [],
                "attention_state": {},
                "navigation_state": {},
            },
            "decision_chain": {
                "goal": {},
                "task_plan": [],
                "planner_meta": {},
                "selected_actions": [],
            },
            "execution": {
                "dispatch_events": [],
                "motion_events": [],
                "joint_summary": {
                    "frame_count": 0,
                    "joint_names": [],
                    "last_positions": {},
                    "min": {},
                    "max": {},
                },
                "skills_called": [],
                "api_calls": [],
            },
            "outcome": {
                "status": "running",
                "success": False,
                "failure_reason": "",
                "recovery_used": False,
                "recovery_steps": [],
                "human_override": False,
            },
            "metrics": {
                "num_plan_steps": 0,
                "num_dispatches": 0,
                "num_motion_cmds": 0,
                "num_joint_frames": 0,
                "completion_latency_ms": 0,
                "clarification_count": 0,
            },
            "labels": {
                "task_type": self._infer_task_type(text),
                "behavior_type": "unknown",
                "motion_type": "unknown",
                "risk_level": "low",
            },
            "_meta": {
                "last_activity_ms": now,
                "raw_events": [{"topic": topic, "msg": payload}],
            },
        }

    def on_reasoning_intent(self, topic: str, msg: Any):
        if not self.active:
            return
        payload = _jsonable(msg)
        self._touch(topic, payload)
        self.active["decision_chain"]["goal"] = payload

    def on_plan(self, topic: str, msg: Any):
        if not self.active:
            return
        payload = _jsonable(msg)
        self._touch(topic, payload)
        steps = self._extract_steps(payload)
        self.active["decision_chain"]["planner_meta"] = payload
        self.active["decision_chain"]["task_plan"] = steps
        self.active["metrics"]["num_plan_steps"] = len(steps)
        if steps:
            self.active["labels"]["behavior_type"] = "planned"

    def on_dispatch(self, topic: str, msg: Any):
        if not self.active:
            return
        payload = _jsonable(msg)
        self._touch(topic, payload)
        self.active["execution"]["dispatch_events"].append(payload)
        self.active["metrics"]["num_dispatches"] += 1
        self.active["decision_chain"]["selected_actions"].append(payload)

    def on_motion_cmd(self, topic: str, msg: Any):
        if not self.active:
            return
        payload = _jsonable(msg)
        self._touch(topic, payload)
        self.active["execution"]["motion_events"].append({"kind": "motion_cmd", "payload": payload})
        self.active["metrics"]["num_motion_cmds"] += 1
        motion_type = self._infer_motion_type(payload)
        if motion_type != "unknown":
            self.active["labels"]["motion_type"] = motion_type

    def on_motion_status(self, topic: str, msg: Any):
        if not self.active:
            return
        payload = _jsonable(msg)
        self._touch(topic, payload)
        self.active["execution"]["motion_events"].append({"kind": "motion_status", "payload": payload})

        state = str(
            self._pick(payload, "state", default=self._pick(payload, "status", default=""))
        ).strip().lower()
        if state in {"completed", "done", "success", "succeeded"}:
            self._finalize(status=state, success=True)
        elif state in {"failed", "error", "aborted", "cancelled", "canceled"}:
            failure_reason = str(
                self._pick(
                    payload,
                    "failure_reason",
                    default=self._pick(payload, "reason", default=state),
                )
                or state
            )
            self._finalize(status=state, success=False, failure_reason=failure_reason)

    def on_joint_frame(self, topic: str, msg: Any):
        if not self.active:
            return
        payload = _jsonable(msg)
        self._touch(topic, payload, keep_raw=False)
        summary = self.active["execution"]["joint_summary"]
        summary["frame_count"] += 1
        self.active["metrics"]["num_joint_frames"] += 1

        positions = self._extract_joint_positions(payload)
        if not positions:
            return

        known_names = set(summary.get("joint_names", []))
        for name, value in positions.items():
            if name not in known_names:
                summary["joint_names"].append(name)
                known_names.add(name)
            summary["last_positions"][name] = value
            prev_min = summary["min"].get(name)
            prev_max = summary["max"].get(name)
            summary["min"][name] = value if prev_min is None else min(prev_min, value)
            summary["max"][name] = value if prev_max is None else max(prev_max, value)

    def on_task_event(self, topic: str, msg: Any):
        if not self.active:
            return
        payload = _jsonable(msg)
        self._touch(topic, payload)
        txt = json.dumps(payload, ensure_ascii=False).lower()
        if "recover" in txt or "retry" in txt:
            self.active["outcome"]["recovery_used"] = True
            self.active["outcome"]["recovery_steps"].append(payload)
        if "clarify" in txt:
            self.active["metrics"]["clarification_count"] += 1

    def on_status_report(self, topic: str, msg: Any):
        if not self.active:
            return
        payload = _jsonable(msg)
        self._touch(topic, payload)
        txt = json.dumps(payload, ensure_ascii=False).lower()
        if "human override" in txt or "manuel" in txt:
            self.active["outcome"]["human_override"] = True

    def _touch(self, topic: str, payload: Any, keep_raw: bool = True):
        if not self.active:
            return
        meta = self.active.setdefault("_meta", {})
        meta["last_activity_ms"] = _now_ms()
        if keep_raw:
            raw_events: List[Dict[str, Any]] = meta.setdefault("raw_events", [])
            if len(raw_events) < 200:
                raw_events.append({"topic": topic, "msg": payload})

    def _finalize(self, status: str, success: bool, failure_reason: str = ""):
        if not self.active:
            return
        now = _now_ms()
        self.active["ended_at_ms"] = now
        self.active["duration_ms"] = max(0, now - int(self.active.get("started_at_ms", now)))
        self.active["metrics"]["completion_latency_ms"] = self.active["duration_ms"]
        self.active["outcome"]["status"] = status
        self.active["outcome"]["success"] = bool(success)
        self.active["outcome"]["failure_reason"] = failure_reason or ""

        path = os.path.join(self.out_dir, f"{self.active['episode_id']}.json")
        serializable = dict(self.active)
        serializable.pop("_meta", None)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)

        print(f"[episode.writer] wrote -> {path}")
        self.active = None

    def _infer_session_id(self) -> str:
        return time.strftime("session_%Y%m%d_%H%M%S")

    def _infer_task_type(self, text: str) -> str:
        t = (text or "").strip().lower()
        if not t:
            return "unknown"
        if any(k in t for k in ["takip", "follow", "izle"]):
            return "follow"
        if any(k in t for k in ["ver", "handover", "uzat"]):
            return "handover"
        if any(k in t for k in ["dön", "turn"]):
            return "turn"
        if any(k in t for k in ["yürü", "walk", "ilerle"]):
            return "walk"
        if any(k in t for k in ["poz", "pose", "kol", "arm"]):
            return "pose"
        return "general"

    def _infer_motion_type(self, payload: Dict[str, Any]) -> str:
        text = json.dumps(payload, ensure_ascii=False).lower()
        if "turn" in text or "dön" in text:
            return "turn_in_place"
        if "walk" in text or "yürü" in text:
            return "walk"
        if "side_step" in text or "yan" in text:
            return "side_step"
        if "pose" in text or "set_pose" in text:
            return "set_pose"
        if "stand" in text:
            return "stand"
        return "unknown"

    def _extract_steps(self, payload: Any) -> List[Any]:
        if isinstance(payload, dict):
            for key in ("steps", "plan", "task_plan"):
                val = payload.get(key)
                if isinstance(val, list):
                    return val
        return []

    def _extract_joint_positions(self, payload: Any) -> Dict[str, float]:
        if not isinstance(payload, dict):
            return {}

        candidates: Dict[str, Any] = {}
        if isinstance(payload.get("positions"), dict):
            candidates = payload["positions"]
        elif isinstance(payload.get("joints"), dict):
            candidates = payload["joints"]
        elif isinstance(payload.get("payload"), dict):
            nested = payload["payload"]
            if isinstance(nested.get("positions"), dict):
                candidates = nested["positions"]

        out: Dict[str, float] = {}
        for name, value in candidates.items():
            try:
                out[str(name)] = float(value)
            except Exception:
                continue
        return out

    def _pick(self, payload: Any, key: str, default: Any = None) -> Any:
        if isinstance(payload, dict):
            if key in payload:
                return payload.get(key, default)
            meta = payload.get("meta")
            if isinstance(meta, dict) and key in meta:
                return meta.get(key, default)
        return default
