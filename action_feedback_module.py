from __future__ import annotations

import time
from typing import Any, Dict


def now_ms() -> int:
    return int(time.time() * 1000)


class ActionFeedbackModule:
    """
    Action baslangic/sonuc eventlerinden kisa sesli geri bildirim uretir.

    IN:
      - executive.action_started
      - executive.action_result

    OUT:
      - voice.say
    """

    name = "action_feedback_module"

    def __init__(self, bus, rt, speak_on_start: bool = True, speak_on_result: bool = False):
        self.bus = bus
        self.rt = rt
        self.speak_on_start = bool(speak_on_start)
        self.speak_on_result = bool(speak_on_result)

        bus.subscribe("executive.action_started", self.on_action_started)
        bus.subscribe("executive.action_result", self.on_action_result)

    def tick(self):
        self.rt.beat(self.name)

    def _say(self, text: str):
        text = str(text or "").strip()
        if not text:
            return
        self.bus.publish(
            "voice.say",
            {
                "text": text,
                "lang": "tr",
                "ts_ms": now_ms(),
            },
        )

    def _start_text(self, action_type: str, action: Dict[str, Any]) -> str:
        params = dict(action.get("params", {}) or {})
        at = str(action_type or "").upper()

        if at == "GO_TO_LOCATION":
            location = str(params.get("location", "") or "")
            return f"{location.capitalize()} gidiyorum." if location else "Gidiyorum."

        if at == "FIND_OBJECT":
            obj = str(params.get("object", "") or "")
            return f"{obj.capitalize()} ariyorum." if obj else "Ariyorum."

        if at == "PICK_OBJECT":
            obj = str(params.get("object", "") or "")
            return f"{obj.capitalize()} aliyorum." if obj else "Aliyorum."

        if at == "BRING_OBJECT_TO_USER":
            obj = str(params.get("object", "") or "")
            return f"{obj.capitalize()} getiriyorum." if obj else "Getiriyorum."

        if at == "TURN_IN_PLACE":
            direction = str(params.get("direction", "") or "")
            return "Sağa dönüyorum." if direction == "right" else "Sola dönüyorum." if direction == "left" else "Dönüyorum."

        if at == "WALK_STEPS":
            steps = str(params.get("steps", "") or "")
            direction = str(params.get("direction", "forward") or "forward")
            if direction == "backward":
                return f"{steps} adım geri gidiyorum." if steps else "Geri gidiyorum."
            return f"{steps} adım ileri gidiyorum." if steps else "İleri gidiyorum."

        if at == "MOVE_LINEAR":
            direction = str(params.get("direction", "") or "")
            return "İleri gidiyorum." if direction == "forward" else "Geri gidiyorum." if direction == "backward" else "Hareket ediyorum."

        if at == "FOLLOW_USER":
            mode = str(params.get("mode", "follow") or "follow")
            if mode == "side":
                return "Yanında yürüyorum."
            if mode == "front":
                return "Önünde yürüyorum."
            return "Seni takip ediyorum."

        if at == "STOP":
            return "Duruyorum."

        if at == "SET_MODE":
            mode = str(params.get("mode", "") or "").strip().upper()
            return f"Modu {mode} yapıyorum." if mode else "Mod değiştiriyorum."

        if at == "RUN_SKILL":
            provider = str(params.get("provider", "") or "")
            return "Hava durumuna bakıyorum." if provider == "open_meteo" else "Bakıyorum."

        if at == "SAY":
            return ""

        return ""

    def _result_text(self, action_type: str, result: Dict[str, Any]) -> str:
        at = str(action_type or "").upper()
        status = str(result.get("status", "") or "").lower()
        output = dict(result.get("output", {}) or {})

        if status != "completed":
            return "Bir sorun oldu."

        if at == "GO_TO_LOCATION":
            location = str(output.get("location_reached", "") or "")
            return f"{location.capitalize()} vardim." if location else "Vardim."

        if at == "FIND_OBJECT":
            obj = str(output.get("object", "") or "")
            return f"{obj.capitalize()} buldum." if obj else "Buldum."

        if at == "PICK_OBJECT":
            obj = str(output.get("object", "") or "")
            return f"{obj.capitalize()} aldim." if obj else "Aldim."

        if at == "BRING_OBJECT_TO_USER":
            obj = str(output.get("object", "") or "")
            return f"{obj.capitalize()} getirdim." if obj else "Getirdim."

        if at == "TURN_IN_PLACE":
            return "Dönüş tamam."

        if at == "WALK_STEPS":
            return "Yürüyüş tamam."

        if at == "MOVE_LINEAR":
            return "Hareket tamam."

        if at == "FOLLOW_USER":
            return "Takibe başladım."

        if at == "STOP":
            return "Durdum."

        if at == "SET_MODE":
            mode = str(output.get("mode", "") or "").strip().upper()
            return f"Mod {mode} oldu." if mode else "Mod değişti."

        if at == "RUN_SKILL":
            return ""

        return ""

    def on_action_started(self, topic: str, msg: Any):
        if not self.speak_on_start:
            return

        payload = msg if isinstance(msg, dict) else {}
        action_type = str(payload.get("action_type", "") or "")
        text = self._start_text(action_type, payload)
        self._say(text)

    def on_action_result(self, topic: str, msg: Any):
        if not self.speak_on_result:
            return

        payload = msg if isinstance(msg, dict) else {}
        action_type = str(payload.get("action_type", "") or "")
        text = self._result_text(action_type, payload)
        self._say(text)
