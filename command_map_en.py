# core/skills/command_map_en.py
"""İngilizce deterministik komutlar → ``ParsedCommand`` (``command_map_tr`` ile aynı çıktı şeması).

İç ``room_id`` / cihaz kimlikleri Türkçe parser ile uyumlu kalır (ör. ``salon``, ``mutfak``).
"""

from __future__ import annotations

import re
from typing import Optional

from core.skills.command_map_tr import ParsedCommand

_NUM_WORDS_EN = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}


def _norm(t: str) -> str:
    t = (t or "").strip()
    t = re.sub(r"\s+", " ", t)
    return t


def _parse_int_token_en(tok: str) -> Optional[int]:
    tok = _norm(tok).lower()
    if not tok:
        return None
    if re.fullmatch(r"\d{1,3}", tok):
        try:
            return int(tok)
        except Exception:
            return None
    if tok in _NUM_WORDS_EN:
        return int(_NUM_WORDS_EN[tok])
    return None


def _extract_steps_en(text: str) -> Optional[int]:
    t = _norm(text).lower()

    m = re.search(r"\b(\d{1,3})\s*steps?\b", t)
    if m:
        return int(m.group(1))

    m = re.search(r"\b([a-z]+(?:\s+[a-z]+)?)\s+steps?\b", t)
    if m:
        v = _parse_int_token_en(m.group(1).split()[-1])
        if v is not None:
            return v
        v = _parse_int_token_en(m.group(1))
        if v is not None:
            return v

    m = re.search(r"\b(?:walk|go|move)\s+(\d{1,3})\b", t)
    if m:
        return int(m.group(1))

    m = re.search(r"\b(\d{1,3})\s+(?:steps?\s+)?(?:forward|backward|back)\b", t)
    if m:
        return int(m.group(1))

    return None


def _dir_left_right_en(t: str) -> Optional[str]:
    s = _norm(t).lower()
    if re.search(r"\b(right|clockwise|starboard)\b", s):
        return "right"
    if re.search(r"\b(left|counter\s*clockwise|anticlockwise|port)\b", s):
        return "left"
    return None


def _extract_angle_deg_en(t: str) -> Optional[float]:
    s = _norm(t).lower()
    m = re.search(r"\b(\d{1,3}(?:\.\d+)?)\s*(?:degrees?|deg)\b", s)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    m = re.search(r"\b(\d{1,3}(?:\.\d+)?)\s*°\b", s)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    return None


def _turn_profile_and_angle_default_en(t: str) -> tuple[str, float]:
    s = _norm(t).lower()
    soft = bool(re.search(r"\b(slowly|softly|slightly|gentle|a little bit)\b", s))
    sharp = bool(re.search(r"\b(sharply|quickly|fast|hard)\b", s))
    if sharp:
        return "sharp", 135.0
    if soft:
        return "soft", 25.0
    return "normal", 90.0


def _extract_room_hint_en(t: str) -> str:
    text = _norm(t).lower()
    room_patterns = {
        "yatak odasi": [r"\b(bedroom|bed\s+room)\b"],
        "cocuk odasi": [r"\b(kids?\s+room|children'?s?\s+room|child\s+room)\b"],
        "salon": [r"\b(living\s+room|lounge)\b"],
        "mutfak": [r"\b(kitchen)\b"],
        "oda": [r"\b(room)\b"],
        "banyo": [r"\b(bathroom)\b"],
        "koridor": [r"\b(corridor|hallway|hall)\b"],
        "balkon": [r"\b(balcony)\b"],
        "garaj": [r"\b(garage)\b"],
        "teras": [r"\b(terrace|patio)\b"],
        "ofis": [r"\b(office)\b"],
        "vitrin": [r"\b(display|shop\s+window|storefront)\b"],
    }
    for room, patterns in room_patterns.items():
        if any(re.search(pat, text) for pat in patterns):
            return room
    return ""


def parse_command_en(text: str) -> Optional[ParsedCommand]:
    """İngilizce komutları ``ParsedCommand``'e çevirir (``parse_command`` ile aynı ``cmd_type`` uzayı)."""
    raw = _norm(text)
    t = raw.lower()
    if not t:
        return None

    if re.search(r"\b(stop|halt|cancel|abort)\b", t):
        return ParsedCommand(cmd_type="STOP", params={}, priority=10, cancel_previous=True)

    if re.search(r"\b(autonomous|autonomy|automatic)\s+mode\b", t) or re.search(
        r"\b(enable|turn on)\s+autonom", t
    ):
        return ParsedCommand(cmd_type="SET_MODE", params={"mode": "AUTO"}, priority=5, cancel_previous=False)
    if re.search(r"\bmanual\s+mode\b", t) or re.search(r"\b(disable|turn off)\s+autonom", t):
        return ParsedCommand(cmd_type="SET_MODE", params={"mode": "MANUAL"}, priority=5, cancel_previous=False)

    if re.search(r"\b(recall\b|what\s+did\s+i\s+say|read\s+(?:my\s+)?memory|memory\s+query)\b", t):
        q = re.sub(
            r"^.*\b(recall|what\s+did\s+i\s+say|read\s+(?:my\s+)?memory|memory\s+query)\b\s*",
            "",
            raw,
            flags=re.IGNORECASE,
        ).strip()
        if not q:
            q = "last"
        return ParsedCommand(cmd_type="MEMORY_QUERY", params={"q": q, "limit": 6, "say": True}, priority=1)

    if re.search(r"\bweather\b", t) or re.search(r"\btemperature\b", t):
        city = re.sub(r"^.*\b(?:weather|temperature)\b\s*(?:in|for)?\s*", "", raw, flags=re.IGNORECASE).strip()
        if not city:
            city = "Istanbul"
        city = re.sub(r"^[?.:!,\s]+", "", city).strip() or "Istanbul"
        return ParsedCommand(
            cmd_type="FETCH_API",
            params={"provider": "wttr", "query": city, "key": f"weather:{city}", "ttl_sec": 7200},
            priority=0,
        )

    if re.search(r"\b(wikipedia|look\s+up|search\s+for|research)\b", t):
        q = re.sub(
            r"^.*\b(wikipedia|look\s+up|search\s+for|research)\b\s*",
            "",
            raw,
            flags=re.IGNORECASE,
        ).strip()
        if q:
            return ParsedCommand(
                cmd_type="FETCH_API", params={"provider": "wikipedia", "query": q, "key": f"wiki:{q}"}, priority=0
            )

    has_window = bool(re.search(r"\bwindow\b", t))
    if has_window and re.search(r"\bopen\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"window_id": f"{room_id}_pencere" if room_id else "pencere", "window_kind": "casement"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="OPEN_WINDOW", params=params, priority=0, cancel_previous=False)
    if has_window and re.search(r"\b(close|shut)\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"window_id": f"{room_id}_pencere" if room_id else "pencere", "window_kind": "casement"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="CLOSE_WINDOW", params=params, priority=0, cancel_previous=False)

    has_balcony_door = bool(re.search(r"\bbalcony\b", t) and re.search(r"\bdoor\b", t))
    if has_balcony_door and re.search(r"\bopen\b", t):
        return ParsedCommand(
            cmd_type="OPEN_BALCONY_DOOR",
            params={"door_id": "balkon_kapisi", "door_kind": "balcony_door", "room_id": "balkon"},
            priority=0,
            cancel_previous=False,
        )
    if has_balcony_door and re.search(r"\b(close|shut)\b", t):
        return ParsedCommand(
            cmd_type="CLOSE_BALCONY_DOOR",
            params={"door_id": "balkon_kapisi", "door_kind": "balcony_door", "room_id": "balkon"},
            priority=0,
            cancel_previous=False,
        )

    has_drawer = bool(re.search(r"\bdrawer\b", t))
    if has_drawer and re.search(r"\bopen\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"drawer_id": f"{room_id}_cekmece" if room_id else "cekmece", "drawer_kind": "generic"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="OPEN_DRAWER", params=params, priority=0, cancel_previous=False)
    if has_drawer and re.search(r"\b(close|shut)\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"drawer_id": f"{room_id}_cekmece" if room_id else "cekmece", "drawer_kind": "generic"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="CLOSE_DRAWER", params=params, priority=0, cancel_previous=False)

    has_cabinet = bool(re.search(r"\b(cabinet|closet|cupboard)\b", t))
    if has_cabinet and re.search(r"\bopen\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"cabinet_id": f"{room_id}_dolap" if room_id else "dolap", "cabinet_kind": "generic"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="OPEN_CABINET", params=params, priority=0, cancel_previous=False)
    if has_cabinet and re.search(r"\b(close|shut)\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"cabinet_id": f"{room_id}_dolap" if room_id else "dolap", "cabinet_kind": "generic"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="CLOSE_CABINET", params=params, priority=0, cancel_previous=False)

    has_garage_door = bool(re.search(r"\bgarage\b", t) and re.search(r"\bdoor\b", t))
    if has_garage_door and re.search(r"\bopen\b", t):
        return ParsedCommand(
            cmd_type="OPEN_GARAGE_DOOR",
            params={"door_id": "garaj_kapisi", "room_id": "garaj", "door_kind": "garage_door"},
            priority=0,
            cancel_previous=False,
        )
    if has_garage_door and re.search(r"\b(close|shut)\b", t):
        return ParsedCommand(
            cmd_type="CLOSE_GARAGE_DOOR",
            params={"door_id": "garaj_kapisi", "room_id": "garaj", "door_kind": "garage_door"},
            priority=0,
            cancel_previous=False,
        )

    has_sliding_door = bool(re.search(r"\bsliding\b", t) and re.search(r"\bdoor\b", t))
    if has_sliding_door and re.search(r"\bopen\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"door_id": f"{room_id}_surgulu_kapi" if room_id else "surgulu_kapi", "door_kind": "sliding_door"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="OPEN_SLIDING_DOOR", params=params, priority=0, cancel_previous=False)
    if has_sliding_door and re.search(r"\b(close|shut)\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"door_id": f"{room_id}_surgulu_kapi" if room_id else "surgulu_kapi", "door_kind": "sliding_door"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="CLOSE_SLIDING_DOOR", params=params, priority=0, cancel_previous=False)

    has_door = bool(re.search(r"\bdoor\b", t))
    if has_door and not has_balcony_door and not has_garage_door and not has_sliding_door and re.search(
        r"\bopen\b", t
    ):
        room_id = _extract_room_hint_en(t)
        params = {"door_id": f"{room_id}_kapi" if room_id else "kapi", "door_kind": "generic"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="OPEN_DOOR", params=params, priority=0, cancel_previous=False)
    if has_door and not has_balcony_door and not has_garage_door and not has_sliding_door and re.search(
        r"\b(close|shut)\b", t
    ):
        room_id = _extract_room_hint_en(t)
        params = {"door_id": f"{room_id}_kapi" if room_id else "kapi", "door_kind": "generic"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="CLOSE_DOOR", params=params, priority=0, cancel_previous=False)

    has_cold_storage = bool(re.search(r"\b(fridge|refrigerator|freezer)\b", t))
    if has_cold_storage and re.search(r"\bopen\b", t):
        storage_kind = "freezer" if re.search(r"\bfreezer\b", t) else "fridge"
        return ParsedCommand(cmd_type="OPEN_COLD_STORAGE", params={"storage_kind": storage_kind}, priority=0, cancel_previous=False)
    if has_cold_storage and re.search(r"\b(close|shut)\b", t):
        storage_kind = "freezer" if re.search(r"\bfreezer\b", t) else "fridge"
        return ParsedCommand(cmd_type="CLOSE_COLD_STORAGE", params={"storage_kind": storage_kind}, priority=0, cancel_previous=False)

    has_curtain = bool(re.search(r"\bcurtain\b", t)) and not bool(re.search(r"\b(track|rail)\b", t))
    if has_curtain and re.search(r"\b(open|raise|draw)\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"curtain_id": f"{room_id}_perde" if room_id else "perde", "curtain_kind": "curtain"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="OPEN_CURTAIN", params=params, priority=0, cancel_previous=False)
    if has_curtain and re.search(r"\b(close|shut|lower)\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"curtain_id": f"{room_id}_perde" if room_id else "perde", "curtain_kind": "curtain"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="CLOSE_CURTAIN", params=params, priority=0, cancel_previous=False)

    has_blind = bool(re.search(r"\b(blind|roller\s+blind|venetian)\b", t))
    if has_blind and re.search(r"\b(open|raise)\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"blind_id": f"{room_id}_stor" if room_id else "stor", "blind_kind": "roller_blind"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="OPEN_BLIND", params=params, priority=0, cancel_previous=False)
    if has_blind and re.search(r"\b(close|shut|lower)\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"blind_id": f"{room_id}_stor" if room_id else "stor", "blind_kind": "roller_blind"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="CLOSE_BLIND", params=params, priority=0, cancel_previous=False)

    has_shutter = bool(re.search(r"\b(shutter|rolling\s+shutter)\b", t)) and not bool(re.search(r"\bdisplay\b", t))
    if has_shutter and re.search(r"\bopen\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"shutter_id": f"{room_id}_panjur" if room_id else "panjur", "shutter_kind": "roller_shutter"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="OPEN_SHUTTER", params=params, priority=0, cancel_previous=False)
    if has_shutter and re.search(r"\b(close|shut)\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"shutter_id": f"{room_id}_panjur" if room_id else "panjur", "shutter_kind": "roller_shutter"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="CLOSE_SHUTTER", params=params, priority=0, cancel_previous=False)

    has_awning = bool(re.search(r"\b(awning|sunshade|marquee)\b", t))
    if has_awning and re.search(r"\b(open|extend|unroll)\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"awning_id": f"{room_id}_tente" if room_id else "tente", "awning_kind": "awning"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="OPEN_AWNING", params=params, priority=0, cancel_previous=False)
    if has_awning and re.search(r"\b(close|retract|roll up)\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"awning_id": f"{room_id}_tente" if room_id else "tente", "awning_kind": "awning"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="CLOSE_AWNING", params=params, priority=0, cancel_previous=False)

    has_vent = bool(re.search(r"\bvent\b", t))
    if has_vent and re.search(r"\bopen\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"vent_id": f"{room_id}_menfez" if room_id else "menfez", "vent_kind": "climate_vent"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="OPEN_VENT", params=params, priority=0, cancel_previous=False)
    if has_vent and re.search(r"\b(close|shut)\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"vent_id": f"{room_id}_menfez" if room_id else "menfez", "vent_kind": "climate_vent"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="CLOSE_VENT", params=params, priority=0, cancel_previous=False)

    has_display_shutter = bool(re.search(r"\bdisplay\b", t)) and bool(re.search(r"\b(shutter)\b", t))
    if has_display_shutter and re.search(r"\bopen\b", t):
        return ParsedCommand(
            cmd_type="OPEN_DISPLAY_SHUTTER",
            params={"shutter_id": "vitrin_kepenk", "room_id": "vitrin", "shutter_kind": "display_shutter"},
            priority=0,
            cancel_previous=False,
        )
    if has_display_shutter and re.search(r"\b(close|shut)\b", t):
        return ParsedCommand(
            cmd_type="CLOSE_DISPLAY_SHUTTER",
            params={"shutter_id": "vitrin_kepenk", "room_id": "vitrin", "shutter_kind": "display_shutter"},
            priority=0,
            cancel_previous=False,
        )

    has_curtain_track = bool(re.search(r"\bcurtain\b", t)) and bool(re.search(r"\b(track|rail)\b", t))
    if has_curtain_track and re.search(r"\bopen\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"track_id": f"{room_id}_perde_rayi" if room_id else "perde_rayi", "track_kind": "motorized_curtain_track"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="OPEN_CURTAIN_TRACK", params=params, priority=0, cancel_previous=False)
    if has_curtain_track and re.search(r"\b(close|shut)\b", t):
        room_id = _extract_room_hint_en(t)
        params = {"track_id": f"{room_id}_perde_rayi" if room_id else "perde_rayi", "track_kind": "motorized_curtain_track"}
        if room_id:
            params["room_id"] = room_id
        return ParsedCommand(cmd_type="CLOSE_CURTAIN_TRACK", params=params, priority=0, cancel_previous=False)

    if re.search(r"\b(next to me|beside me|walk with me|stay with me)\b", t) and re.search(
        r"\b(walk|come|stay)\b", t
    ):
        return ParsedCommand(cmd_type="FOLLOW_USER", params={"mode": "side"}, priority=0, cancel_previous=False)
    if re.search(r"\b(ahead of me|in front of me)\b", t) and re.search(r"\b(walk|go|stop)\b", t):
        return ParsedCommand(cmd_type="FOLLOW_USER", params={"mode": "front"}, priority=0, cancel_previous=False)
    if re.search(r"\b(follow me|come after me|trail me)\b", t):
        return ParsedCommand(cmd_type="FOLLOW_USER", params={"mode": "follow"}, priority=0, cancel_previous=False)

    if re.search(
        r"\b(walk|go|move|step)\b.*\b(forward|ahead|onward)\b", t
    ) or re.search(r"\b(forward|ahead)\b.*\b(walk|go|move)\b", t):
        steps = _extract_steps_en(t) or 1
        direction = "backward" if re.search(r"\b(backward|back)\b", t) else "forward"
        return ParsedCommand(
            cmd_type="WALK",
            params={"direction": direction, "steps": int(steps)},
            priority=0,
            cancel_previous=False,
        )

    if re.search(r"\b(walk|step)\b", t) and not re.search(r"\b(turn|backward|back\s+up|door|window)\b", t):
        steps = _extract_steps_en(t) or 1
        return ParsedCommand(
            cmd_type="WALK",
            params={"direction": "forward", "steps": int(steps)},
            priority=0,
            cancel_previous=False,
        )

    if re.search(r"\b(backward|back up|move back|walk back|go back)\b", t) and not re.search(
        r"\bturn\b", t
    ):
        steps = _extract_steps_en(t) or 1
        return ParsedCommand(
            cmd_type="WALK",
            params={"direction": "backward", "steps": int(steps)},
            priority=0,
            cancel_previous=False,
        )

    if re.search(r"\b(look|glance|peek)\b", t):
        d = _dir_left_right_en(t)
        if d:
            return ParsedCommand(
                cmd_type="TURN",
                params={"direction": d, "angle_deg": 30.0, "profile": "normal", "intent": "look"},
                priority=0,
                cancel_previous=False,
            )

    if re.search(r"\b(turn|rotate|spin|pivot)\b", t):
        d = _dir_left_right_en(t)
        if not d and re.search(r"\b(u\s*turn|turn\s+around|about\s*face)\b", t):
            return ParsedCommand(
                cmd_type="TURN",
                params={"direction": "right", "angle_deg": 180.0, "profile": "normal"},
                priority=0,
                cancel_previous=False,
            )
        if not d and re.search(r"\b180\b", t):
            d = "right"
        if not d:
            return None
        explicit_angle = _extract_angle_deg_en(t)
        if explicit_angle is not None:
            angle = float(explicit_angle)
            profile, _ = _turn_profile_and_angle_default_en(t)
        else:
            profile, angle = _turn_profile_and_angle_default_en(t)
        return ParsedCommand(
            cmd_type="TURN",
            params={"direction": d, "angle_deg": float(angle), "profile": profile},
            priority=0,
            cancel_previous=False,
        )

    return None


__all__ = ["parse_command_en"]
