from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


def now_ms() -> int:
    return int(time.time() * 1000)


class HandoverSocialIntelligenceModule:
    """Multi-human social coordination for handover.

    Inputs:
      - vision.person_tracks / transport.video.person_tracks / perception.state
      - vision.hand_targets
      - handover.target_selected
      - action_router.action_ready / executive.action

    Outputs:
      - handover.social_policy_applied
      - handover.social_queue_updated
      - handover.social_target_locked
      - handover.social_conflict_detected
      - handover.social_result
    """

    name = "handover_social_intelligence_module"

    def __init__(
        self,
        bus,
        rt,
        *,
        conflict_score_gap: float = 0.12,
        conflict_azimuth_gap_deg: float = 14.0,
        social_clearance_m: float = 0.35,
    ):
        self.bus = bus
        self.rt = rt
        self.conflict_score_gap = float(conflict_score_gap)
        self.conflict_azimuth_gap_deg = float(conflict_azimuth_gap_deg)
        self.social_clearance_m = float(social_clearance_m)
        self.track_index: Dict[str, Dict[str, Any]] = {}
        self.hand_targets: List[Dict[str, Any]] = []
        self.current_target: Dict[str, Any] = {}
        self.last_policy: Dict[str, Any] = {}
        self._action_transformer_subscription_tag = "action_patch_transformer:handover_social_intelligence"

        bus.subscribe("vision.person_tracks", self.on_tracks)
        bus.subscribe("transport.video.person_tracks", self.on_tracks)
        bus.subscribe("perception.state", self.on_perception_state)
        bus.subscribe("vision.hand_targets", self.on_hand_targets)
        bus.subscribe("handover.target_selected", self.on_target_selected)
        bus.subscribe("action_router.action_ready", self.on_action_ready)
        bus.subscribe("executive.action", self.on_executive_action)
        bus.subscribe("handover.social_query", self.on_query)
        self._register_action_patch_transformer()

    def tick(self):
        self.rt.beat(self.name)

    def on_target_selected(self, topic: str, msg: Any):
        self.current_target = dict(msg or {}) if isinstance(msg, dict) else {}

    def _normalize_tracks(self, msg: Any) -> List[Dict[str, Any]]:
        raw = []
        if isinstance(msg, list):
            raw = msg
        elif isinstance(msg, dict):
            raw = msg.get("tracks", []) or msg.get("persons", []) or msg.get("person_tracks", []) or []
        out: List[Dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            track_id = str(item.get("track_id", "") or item.get("person_track_id", "") or "")
            if not track_id:
                continue
            t = dict(item)
            t["track_id"] = track_id
            out.append(t)
        return out

    def on_tracks(self, topic: str, msg: Any):
        tracks = self._normalize_tracks(msg)
        if tracks:
            self.track_index = {t["track_id"]: t for t in tracks}

    def on_perception_state(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        tracks = payload.get("person_tracks") or payload.get("tracks")
        if tracks:
            self.on_tracks(topic, tracks)

    def on_hand_targets(self, topic: str, msg: Any):
        raw = []
        if isinstance(msg, list):
            raw = msg
        elif isinstance(msg, dict):
            raw = msg.get("hands", []) or msg.get("hand_targets", []) or []
        self.hand_targets = [dict(x) for x in raw if isinstance(x, dict)]

    def _hand_readiness(self, track_id: str) -> float:
        best = 0.0
        for hand in self.hand_targets:
            hand_track_id = str(hand.get("track_id", "") or hand.get("person_track_id", "") or "")
            if hand_track_id not in ("", track_id):
                continue
            score = float(hand.get("confidence", 0.0) or 0.0) * 0.45
            if hand.get("extended") is True:
                score += 0.25
            score += min(0.20, float(hand.get("extension_score", 0.0) or 0.0) * 0.20)
            dist_to_object = hand.get("distance_to_object_m")
            if isinstance(dist_to_object, (int, float)):
                score += max(0.0, 0.20 - min(float(dist_to_object), 0.20))
            best = max(best, score)
        return round(min(1.0, best), 4)

    def _candidate_score(self, track: Dict[str, Any], preferred_track_id: str) -> float:
        track_id = str(track.get("track_id", "") or "")
        distance_m = float(track.get("distance_m", 2.5) or 2.5)
        body_orientation = float(track.get("body_orientation_score", 0.0) or 0.0)
        approach_velocity = abs(float(track.get("approach_velocity_mps", track.get("estimated_speed_mps", 0.0)) or 0.0))
        hand_score = self._hand_readiness(track_id)
        score = 0.0
        if track_id and track_id == preferred_track_id:
            score += 0.28
        if track.get("is_primary") is True:
            score += 0.10
        score += max(0.0, 0.22 - min(distance_m, 2.2) * 0.08)
        score += min(0.14, body_orientation * 0.14)
        score += min(0.16, approach_velocity * 0.16)
        score += hand_score
        return round(min(1.0, score), 4)

    def _queue_candidates(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        preferred_track_id = str((self.current_target or {}).get("track_id", "") or params.get("target_track_id", "") or "")
        candidates: List[Dict[str, Any]] = []
        for track_id, track in self.track_index.items():
            cand = dict(track)
            cand["social_score"] = self._candidate_score(track, preferred_track_id)
            cand["hand_readiness"] = self._hand_readiness(track_id)
            candidates.append(cand)
        candidates.sort(key=lambda x: (-float(x.get("social_score", 0.0) or 0.0), float(x.get("distance_m", 9.9) or 9.9)))
        return candidates

    def _build_policy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        preferred_track_id = str((self.current_target or {}).get("track_id", "") or params.get("target_track_id", "") or "")
        candidates = self._queue_candidates(params)
        queue = [
            {
                "track_id": str(c.get("track_id", "") or ""),
                "distance_m": round(float(c.get("distance_m", 9.9) or 9.9), 4),
                "azimuth_deg": (round(float(c.get("azimuth_deg", 0.0) or 0.0), 4) if isinstance(c.get("azimuth_deg"), (int, float)) else None),
                "social_score": float(c.get("social_score", 0.0) or 0.0),
                "hand_readiness": float(c.get("hand_readiness", 0.0) or 0.0),
            }
            for c in candidates[:5]
        ]
        selected = candidates[0] if candidates else {}
        if preferred_track_id:
            preferred = next((c for c in candidates if str(c.get("track_id", "") or "") == preferred_track_id), None)
            if preferred is not None and float(preferred.get("social_score", 0.0) or 0.0) + 0.08 >= float(selected.get("social_score", 0.0) or 0.0):
                selected = preferred
        selected_track_id = str((selected or {}).get("track_id", "") or preferred_track_id or "")
        selected_has_azimuth = isinstance((selected or {}).get("azimuth_deg"), (int, float))
        selected_azimuth = float((selected or {}).get("azimuth_deg", 0.0) or 0.0)
        selected_distance = float((selected or {}).get("distance_m", 9.9) or 9.9)
        conflict = False
        conflict_with: Optional[str] = None
        if len(candidates) >= 2:
            a, b = candidates[0], candidates[1]
            score_gap = abs(float(a.get("social_score", 0.0) or 0.0) - float(b.get("social_score", 0.0) or 0.0))
            a_has_az = isinstance(a.get("azimuth_deg"), (int, float))
            b_has_az = isinstance(b.get("azimuth_deg"), (int, float))
            az_gap = abs(float(a.get("azimuth_deg", 0.0) or 0.0) - float(b.get("azimuth_deg", 0.0) or 0.0)) if a_has_az and b_has_az else 999.0
            dist_gap = abs(float(a.get("distance_m", 9.9) or 9.9) - float(b.get("distance_m", 9.9) or 9.9))
            if score_gap <= self.conflict_score_gap and az_gap <= self.conflict_azimuth_gap_deg and dist_gap <= self.social_clearance_m:
                conflict = True
                conflict_with = str(b.get("track_id", "") or "")
        social_spacing_ok = True
        for cand in candidates:
            if str(cand.get("track_id", "") or "") == selected_track_id:
                continue
            cand_has_az = isinstance(cand.get("azimuth_deg"), (int, float))
            az_gap = abs(float(cand.get("azimuth_deg", 0.0) or 0.0) - selected_azimuth) if cand_has_az and selected_has_azimuth else 999.0
            dist_gap = abs(float(cand.get("distance_m", 9.9) or 9.9) - selected_distance)
            if az_gap <= 10.0 and dist_gap < self.social_clearance_m:
                social_spacing_ok = False
                break
        recipient_locked = bool(selected_track_id) and not conflict
        policy = {
            "selected_track_id": selected_track_id,
            "selected_face_id": str((selected or {}).get("face_id", "") or ""),
            "selected_speaker_id": str((selected or {}).get("speaker_id", "") or ""),
            "queue": queue,
            "queue_size": len(queue),
            "queue_head_track_id": selected_track_id,
            "social_spacing_ok": social_spacing_ok,
            "recipient_locked": recipient_locked,
            "conflict_detected": conflict,
            "conflict_with_track_id": conflict_with or "",
            "disambiguation_required": conflict,
            "social_safe": bool(recipient_locked and social_spacing_ok),
            "retargeted": bool(selected_track_id and preferred_track_id and selected_track_id != preferred_track_id),
            "courtesy_mode": "turn_taking" if len(queue) > 1 else "direct",
            "queue_policy": "priority_ready_then_target",
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
        self.bus.publish("handover.social_policy_applied", payload)
        self.bus.publish("handover.social_queue_updated", payload)
        if policy.get("conflict_detected"):
            self.bus.publish("handover.social_conflict_detected", payload)
        if policy.get("recipient_locked"):
            self.bus.publish("handover.social_target_locked", payload)

    def on_action_ready(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        action = dict(payload.get("action", {}) or {})
        if str(action.get("action_type", "") or "").strip().upper() != "BRING_OBJECT_TO_USER":
            return
        params = action.setdefault("params", {})
        policy = self._build_policy(params)
        params["handover_social_policy"] = dict(policy)
        if policy.get("selected_track_id"):
            params["target_track_id"] = str(policy.get("selected_track_id", "") or "")
            params["target_face_id"] = str(policy.get("selected_face_id", "") or "")
            params["target_speaker_id"] = str(policy.get("selected_speaker_id", "") or "")
        payload["action"] = action

    def on_executive_action(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        action = dict(payload.get("action", {}) or {})
        if str(action.get("action_type", "") or "").strip().upper() != "BRING_OBJECT_TO_USER":
            return
        policy = dict((action.get("params", {}) or {}).get("handover_social_policy", {}) or {})
        if not policy:
            policy = self._build_policy(action.get("params", {}) or {})
        self._publish(action, policy)

    def transform_action_patch(self, msg: Any) -> Dict[str, Any] | None:
        payload = msg if isinstance(msg, dict) else {}
        action = dict(payload.get("action", {}) or {})
        if str(action.get("action_type", "") or "").strip().upper() != "BRING_OBJECT_TO_USER":
            return None
        params = dict(action.get("params", {}) or {})
        policy = dict(params.get("handover_social_policy", {}) or {})
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
        patch_params: Dict[str, Any] = {"handover_social_policy": dict(policy)}
        if policy.get("selected_track_id"):
            patch_params["target_track_id"] = str(policy.get("selected_track_id", "") or "")
            patch_params["target_face_id"] = str(policy.get("selected_face_id", "") or "")
            patch_params["target_speaker_id"] = str(policy.get("selected_speaker_id", "") or "")
        events = [
            {"topic": "handover.social_policy_applied", "payload": dict(event_payload)},
            {"topic": "handover.social_queue_updated", "payload": dict(event_payload)},
        ]
        if policy.get("conflict_detected"):
            events.append({"topic": "handover.social_conflict_detected", "payload": dict(event_payload)})
        if policy.get("recipient_locked"):
            events.append({"topic": "handover.social_target_locked", "payload": dict(event_payload)})
        return {
            "stage": "handover_social_intelligence",
            "reason": "handover_social_policy",
            "params": patch_params,
            "status_events": events,
        }

    def _register_action_patch_transformer(self) -> None:
        register = getattr(self.bus, "register_action_transformer", None)
        if callable(register):
            try:
                register(
                    f"{self.__class__.__module__}.{self.__class__.__name__}",
                    self.transform_action_patch,
                    stage="handover_social_intelligence",
                    priority=731,
                    subscription_tag=self._action_transformer_subscription_tag,
                    kind="action_patch",
                )
            except TypeError:
                pass
        tag_subscription = getattr(self.bus, "tag_subscription", None)
        if callable(tag_subscription):
            tag_subscription("executive.action", self.on_executive_action, self._action_transformer_subscription_tag)

    def on_query(self, topic: str, msg: Any):
        self.bus.publish("handover.social_result", {
            "current_target": dict(self.current_target or {}),
            "last_policy": dict(self.last_policy or {}),
            "track_count": len(self.track_index),
            "ts_ms": now_ms(),
        })
