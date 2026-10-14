from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


def now_ms() -> int:
    return int(time.time() * 1000)


class HumanHandoverPerceptionModule:
    """Select a concrete human target for object delivery using visual tracks + grounding.

    Inputs:
      - vision.person_tracks / transport.video.person_tracks / perception.state
      - audio_visual_grounding.resolved / current_speaker
      - follow.visual_lock
      - executive.action / executive.action_result
      - handover.query

    Outputs:
      - handover.target_selected
      - handover.completed / handover.target_lost
      - handover.result
    """

    name = "human_handover_perception_module"

    def __init__(self, bus, rt, *, target_ttl_ms: int = 5000):
        self.bus = bus
        self.rt = rt
        self.target_ttl_ms = int(max(500, target_ttl_ms))

        self.track_index: Dict[str, Dict[str, Any]] = {}
        self.current_grounding: Dict[str, Any] = {}
        self.follow_lock: Dict[str, Any] = {}
        self.current_target: Dict[str, Any] = {}
        self.last_selected_ts_ms = 0
        self.last_completed: Dict[str, Any] = {}
        self._action_transformer_subscription_tag = "action_patch_transformer:human_handover_perception"

        bus.subscribe("vision.person_tracks", self.on_tracks)
        bus.subscribe("transport.video.person_tracks", self.on_tracks)
        bus.subscribe("perception.state", self.on_perception_state)
        bus.subscribe("audio_visual_grounding.resolved", self.on_grounding)
        bus.subscribe("audio_visual_grounding.current_speaker", self.on_grounding)
        bus.subscribe("follow.visual_lock", self.on_follow_lock)
        bus.subscribe("action_router.action_ready", self.on_action_ready)
        bus.subscribe("executive.action", self.on_executive_action)
        bus.subscribe("executive.action_result", self.on_action_result)
        bus.subscribe("handover.query", self.on_query)
        self._register_action_patch_transformer()

    def tick(self):
        self.rt.beat(self.name)
        if self.current_target and (now_ms() - self.last_selected_ts_ms) > self.target_ttl_ms:
            self.current_target = {}

    def _normalize_tracks(self, msg: Any) -> List[Dict[str, Any]]:
        raw = []
        if isinstance(msg, list):
            raw = msg
        elif isinstance(msg, dict):
            raw = msg.get("tracks", []) or msg.get("persons", []) or []
        tracks: List[Dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            track = dict(item)
            track_id = str(track.get("track_id", "") or track.get("person_track_id", "") or "")
            if not track_id:
                continue
            track["track_id"] = track_id
            track["face_id"] = str(track.get("face_id", "") or "")
            track["speaker_id"] = str(track.get("speaker_id", "") or "")
            tracks.append(track)
        return tracks

    def on_tracks(self, topic: str, msg: Any):
        tracks = self._normalize_tracks(msg)
        if tracks:
            self.track_index = {t["track_id"]: t for t in tracks}

    def on_perception_state(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        tracks = payload.get("person_tracks") or payload.get("tracks")
        if tracks:
            self.on_tracks(topic, tracks)

    def on_grounding(self, topic: str, msg: Any):
        self.current_grounding = dict(msg or {}) if isinstance(msg, dict) else {}

    def on_follow_lock(self, topic: str, msg: Any):
        self.follow_lock = dict(msg or {}) if isinstance(msg, dict) else {}

    def _score_track(self, track: Dict[str, Any]) -> float:
        score = 0.0
        track_id = str(track.get("track_id", "") or "")
        face_id = str(track.get("face_id", "") or "")
        speaker_id = str(track.get("speaker_id", "") or "")
        if track_id and track_id == str(self.current_grounding.get("person_track_id", "") or self.current_grounding.get("track_id", "") or ""):
            score += 1.0
        if face_id and face_id == str(self.current_grounding.get("grounded_face_id", "") or self.current_grounding.get("face_id", "") or ""):
            score += 0.9
        if speaker_id and speaker_id == str(self.current_grounding.get("speaker_id", "") or ""):
            score += 0.7
        if track_id and track_id == str(self.follow_lock.get("track_id", "") or ""):
            score += 0.55
        if track.get("is_speaking") is True:
            score += 0.45
        if track.get("is_primary") is True:
            score += 0.20
        dist = track.get("distance_m")
        if isinstance(dist, (int, float)):
            score += max(0.0, 0.35 - min(float(dist), 3.5) * 0.08)
        bbox = track.get("bbox") or {}
        if isinstance(bbox, dict):
            w = float(bbox.get("w", 0.0) or 0.0)
            h = float(bbox.get("h", 0.0) or 0.0)
            score += min(0.25, max(0.0, w * h))
        return score

    def _fallback_target(self) -> Dict[str, Any]:
        if self.current_grounding:
            return {
                "track_id": str(self.current_grounding.get("person_track_id", "") or self.current_grounding.get("track_id", "") or ""),
                "face_id": str(self.current_grounding.get("grounded_face_id", "") or self.current_grounding.get("face_id", "") or ""),
                "speaker_id": str(self.current_grounding.get("speaker_id", "") or ""),
                "confidence": float(self.current_grounding.get("grounding_confidence", self.current_grounding.get("confidence", 0.0)) or 0.0),
                "source": "grounding_only",
                "target_kind": "human",
                "ts_ms": now_ms(),
            }
        if self.follow_lock:
            return {
                "track_id": str(self.follow_lock.get("track_id", "") or ""),
                "face_id": str(self.follow_lock.get("face_id", "") or ""),
                "speaker_id": str(self.follow_lock.get("speaker_id", "") or ""),
                "confidence": float(self.follow_lock.get("confidence", 0.0) or 0.0),
                "source": "follow_lock_only",
                "target_kind": "human",
                "ts_ms": now_ms(),
            }
        return {
            "track_id": "",
            "face_id": "",
            "speaker_id": str(self.current_grounding.get("speaker_id", "") or "user"),
            "confidence": 0.1,
            "source": "generic_user",
            "target_kind": "human",
            "ts_ms": now_ms(),
        }

    def _select_target(self) -> Dict[str, Any]:
        candidates = list(self.track_index.values())
        if not candidates:
            return self._fallback_target()
        best = max(candidates, key=self._score_track)
        score = self._score_track(best)
        return {
            "track_id": str(best.get("track_id", "") or ""),
            "face_id": str(best.get("face_id", "") or ""),
            "speaker_id": str(best.get("speaker_id", "") or self.current_grounding.get("speaker_id", "") or ""),
            "distance_m": best.get("distance_m"),
            "azimuth_deg": best.get("azimuth_deg", self.current_grounding.get("estimated_azimuth_deg")),
            "bbox": dict(best.get("bbox", {}) or {}),
            "source": "visual_track_fusion",
            "confidence": round(score, 4),
            "target_kind": "human",
            "ts_ms": now_ms(),
        }


    def on_action_ready(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        action = dict(payload.get("action", {}) or {})
        if str(action.get("action_type", "") or "").strip().upper() != "BRING_OBJECT_TO_USER":
            return
        target = self._select_target()
        action_params = action.setdefault("params", {})
        action_params["target_track_id"] = str(target.get("track_id", "") or "")
        action_params["target_face_id"] = str(target.get("face_id", "") or "")
        action_params["target_speaker_id"] = str(target.get("speaker_id", "") or "")
        payload["action"] = action

    def on_executive_action(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        action = dict(payload.get("action", {}) or {})
        if str(action.get("action_type", "") or "").strip().upper() != "BRING_OBJECT_TO_USER":
            return
        params = dict(action.get("params", {}) or {})
        target = {}
        if any(str(params.get(k, "") or "") for k in ("target_track_id", "target_face_id", "target_speaker_id")):
            target = {
                "track_id": str(params.get("target_track_id", "") or ""),
                "face_id": str(params.get("target_face_id", "") or ""),
                "speaker_id": str(params.get("target_speaker_id", "") or ""),
                "source": "action_params",
                "target_kind": "human",
                "ts_ms": now_ms(),
            }
            track = dict(self.track_index.get(str(target.get("track_id", "") or ""), {}) or {})
            if track:
                target.update({
                    "distance_m": track.get("distance_m"),
                    "azimuth_deg": track.get("azimuth_deg"),
                    "bbox": dict(track.get("bbox", {}) or {}),
                    "confidence": round(self._score_track(track), 4),
                })
            else:
                target["confidence"] = 0.5
        if not target:
            target = self._select_target()
        target["action_id"] = str(action.get("action_id", "") or "")
        target["task_id"] = str(action.get("task_id", "") or payload.get("task_id", "") or "")
        target["object"] = str((action.get("params", {}) or {}).get("object", "") or "")
        self.current_target = dict(target)
        self.last_selected_ts_ms = now_ms()
        self.bus.publish("handover.target_selected", dict(target))

    def transform_action_patch(self, msg: Any) -> Dict[str, Any] | None:
        payload = msg if isinstance(msg, dict) else {}
        action = dict(payload.get("action", {}) or {})
        if str(action.get("action_type", "") or "").strip().upper() != "BRING_OBJECT_TO_USER":
            return None
        params = dict(action.get("params", {}) or {})
        target = {}
        if any(str(params.get(k, "") or "") for k in ("target_track_id", "target_face_id", "target_speaker_id")):
            target = {
                "track_id": str(params.get("target_track_id", "") or ""),
                "face_id": str(params.get("target_face_id", "") or ""),
                "speaker_id": str(params.get("target_speaker_id", "") or ""),
                "source": "action_params",
                "target_kind": "human",
                "ts_ms": now_ms(),
            }
            track = dict(self.track_index.get(str(target.get("track_id", "") or ""), {}) or {})
            if track:
                target.update({
                    "distance_m": track.get("distance_m"),
                    "azimuth_deg": track.get("azimuth_deg"),
                    "bbox": dict(track.get("bbox", {}) or {}),
                    "confidence": round(self._score_track(track), 4),
                })
            else:
                target["confidence"] = 0.5
        if not target:
            target = self._select_target()
        target["action_id"] = str(action.get("action_id", "") or "")
        target["task_id"] = str(action.get("task_id", "") or payload.get("task_id", "") or "")
        target["object"] = str(params.get("object", "") or "")
        self.current_target = dict(target)
        self.last_selected_ts_ms = now_ms()
        return {
            "stage": "human_handover_perception",
            "reason": "handover_target_selected",
            "params": {
                "target_track_id": str(target.get("track_id", "") or ""),
                "target_face_id": str(target.get("face_id", "") or ""),
                "target_speaker_id": str(target.get("speaker_id", "") or ""),
            },
            "status_topic": "handover.target_selected",
            "status_payload": dict(target),
        }

    def _register_action_patch_transformer(self) -> None:
        register = getattr(self.bus, "register_action_transformer", None)
        if callable(register):
            try:
                register(
                    f"{self.__class__.__module__}.{self.__class__.__name__}",
                    self.transform_action_patch,
                    stage="human_handover_perception",
                    priority=730,
                    subscription_tag=self._action_transformer_subscription_tag,
                    kind="action_patch",
                )
            except TypeError:
                pass
        tag_subscription = getattr(self.bus, "tag_subscription", None)
        if callable(tag_subscription):
            tag_subscription("executive.action", self.on_executive_action, self._action_transformer_subscription_tag)

    def on_action_result(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        action_type = str(payload.get("action_type", "") or "").strip().upper()
        if action_type != "BRING_OBJECT_TO_USER":
            return
        status = str(payload.get("status", "") or "").strip().lower()
        reason = str(payload.get("reason", "") or "")
        if status == "completed":
            completed = dict(self.current_target or {})
            completed.update({
                "object": str((payload.get("output", {}) or {}).get("object", "") or completed.get("object", "")),
                "delivered_to": completed.get("track_id") or completed.get("face_id") or completed.get("speaker_id") or "user",
                "location": (payload.get("output", {}) or {}).get("location"),
                "ts_ms": now_ms(),
            })
            self.last_completed = completed
            self.bus.publish("handover.completed", completed)
        elif reason in ("user_not_found", "delivery_failed"):
            self.bus.publish("handover.target_lost", {"reason": reason, **dict(self.current_target or {}), "ts_ms": now_ms()})

    def on_query(self, topic: str, msg: Any):
        self.bus.publish(
            "handover.result",
            {
                "current_target": dict(self.current_target or {}),
                "last_completed": dict(self.last_completed or {}),
                "track_count": len(self.track_index),
                "grounding": dict(self.current_grounding or {}),
                "follow_lock": dict(self.follow_lock or {}),
                "ts_ms": now_ms(),
            },
        )
