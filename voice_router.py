# core/skills/voice_router.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class Routed:
    task: Optional[str] = None
    chat: Optional[str] = None


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    # türkçe i/İ gibi şeyler için kaba normalize
    s = s.replace("ı̇", "i").replace("i̇", "i")
    s = s.replace("’", "'")
    s = re.sub(r"\s+", " ", s)
    return s


def _extract_number(text: str) -> Optional[int]:
    # "90", "45" gibi sayıları yakala
    m = re.search(r"(-?\d+)", text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


class VoiceRouterCore:
    """
    Metni ikiye ayırır:
      - task: yürüyüş / dönme / dur / geri vb.
      - chat: genel sohbet / soru (örn: matematik)

    Not: Wake-word filtrelemesini HTTP katmanında da yapıyoruz.
    """

    def route(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        t = _norm(text)
        if not t:
            return None, None

        # Wakeword başta ise kırp
        if t.startswith("mamula "):
            t = t[len("mamula ") :].strip()
        elif t == "mamula":
            # "mamula" sadece ping, burada task/chat yok
            return None, None

        if not t:
            return None, None

        # --- TASK ROUTING ---

        # DUR
        if t in {"dur", "stop", "mamula dur"} or "dur" == t:
            return "stop", None

        # YÜRÜ / İLERİ
        # ör: "yürü", "yürü 10", "ileri yürü 3"
        if "yürü" in t or "ileri" in t:
            n = _extract_number(t)
            if n is None:
                n = 3
            if n < 0:
                # negatif gelirse geri say
                return f"walk {abs(n)} steps back", None
            return f"walk {n} steps forward", None

        # GERİ / GERİ YÜRÜ
        if "geri" in t and ("yürü" in t or "git" in t or t == "geri"):
            n = _extract_number(t)
            if n is None:
                n = 3
            return f"walk {n} steps back intent backturn", None

        # SAĞA DÖN
        if "sağa" in t and "dön" in t:
            deg = _extract_number(t)
            if deg is None:
                deg = 45
            return f"turn right {deg}", None

        # SOLA DÖN
        if "sola" in t and "dön" in t:
            deg = _extract_number(t)
            if deg is None:
                deg = 45
            return f"turn left {deg}", None

        # YANIMA GEL / GEL
        if ("yanıma" in t and "gel" in t) or t in {"gel", "yanıma gel"}:
            return "walk 1 steps forward intent come", None

        # ARKAMDA YÜRÜ / TAKİP ET
        if ("arkamda" in t and "yürü" in t) or "takip" in t:
            return "follow behind", None

        # UZAKLAŞ
        if "uzaklaş" in t or ("benden" in t and "uzak" in t):
            return "walk 1 steps back intent away", None

        # --- CHAT ROUTING ---
        # Komuta benzemiyorsa chat kabul et
        return None, t
