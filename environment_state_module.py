from __future__ import annotations

import time
from typing import Any, Dict


def now_ms() -> int:
    return int(time.time() * 1000)


class EnvironmentStateModule:
    """
    Dünya durumu:
    - obje nerede
    - lokasyonlar neler
    - obje taşındı mı

    IN:
      - environment.query_object
      - environment.move_object
      - environment.query_snapshot

    OUT:
      - environment.object_info
      - environment.object_not_found
      - environment.object_moved
      - environment.snapshot
    """

    name = "environment_state_module"

    def __init__(self, bus, rt):
        self.bus = bus
        self.rt = rt

        self.objects: Dict[str, Dict[str, Any]] = {
            "su": {
                "id": "obj_su",
                "location": "mutfak",
                "movable": True,
            },
            "kumanda": {
                "id": "obj_kumanda",
                "location": "salon",
                "movable": True,
            },
            "kitap": {
                "id": "obj_kitap",
                "location": "oda",
                "movable": True,
            },
            "ilac": {
                "id": "obj_ilac",
                "location": "masa",
                "movable": True,
            },
        }

        self.locations: Dict[str, Dict[str, Any]] = {
            "home_base": {},
            "mutfak": {},
            "salon": {},
            "oda": {},
            "koridor": {},
            "masa": {},
            "banyo": {},
            "yatak odasi": {},
        }

        bus.subscribe("environment.query_object", self.on_query_object)
        bus.subscribe("environment.move_object", self.on_move_object)
        bus.subscribe("environment.query_snapshot", self.on_query_snapshot)

    def tick(self):
        self.rt.beat(self.name)

    def _norm(self, value: str) -> str:
        return str(value or "").strip().lower()

    def on_query_object(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        obj = self._norm(payload.get("object", ""))

        if not obj or obj not in self.objects:
            self.bus.publish(
                "environment.object_not_found",
                {
                    "object": obj,
                    "ts_ms": now_ms(),
                },
            )
            return

        data = self.objects[obj]

        self.bus.publish(
            "environment.object_info",
            {
                "object": obj,
                "object_id": data["id"],
                "location": data["location"],
                "movable": bool(data.get("movable", True)),
                "ts_ms": now_ms(),
            },
        )

    def on_move_object(self, topic: str, msg: Any):
        payload = msg if isinstance(msg, dict) else {}
        obj = self._norm(payload.get("object", ""))
        location = self._norm(payload.get("location", ""))

        if not obj or obj not in self.objects:
            return
        if not location or location not in self.locations:
            return

        self.objects[obj]["location"] = location

        self.bus.publish(
            "environment.object_moved",
            {
                "object": obj,
                "object_id": self.objects[obj]["id"],
                "location": location,
                "ts_ms": now_ms(),
            },
        )

    def on_query_snapshot(self, topic: str, msg: Any):
        self.bus.publish(
            "environment.snapshot",
            {
                "objects": {k: dict(v) for k, v in self.objects.items()},
                "locations": {k: dict(v) for k, v in self.locations.items()},
                "ts_ms": now_ms(),
            },
        )
