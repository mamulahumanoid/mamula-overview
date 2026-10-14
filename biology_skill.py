from __future__ import annotations

import re
from typing import Any, Dict, Optional

from core.contract.actions import normalize_step


def _say(text: str) -> Dict[str, Any]:
    return normalize_step(
        {
            "type": "CMD",
            "cmd_type": "SAY",
            "params": {"text": text},
        }
    )


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def try_parse_biology(text: str) -> Optional[Dict[str, Any]]:
    t = (text or "").strip()
    if not t:
        return None

    low = _norm(t)

    if re.search(r"\bdna\b", low) and re.search(r"\bnedir\b", low):
        return _say("DNA, canlıların kalıtsal bilgisini taşıyan deoksiribonükleik asittir.")

    if re.search(r"\brna\b", low) and re.search(r"\bnedir\b", low):
        return _say("RNA, genetik bilginin taşınması ve protein sentezinde görev alan ribonükleik asittir.")

    if re.search(r"\bmitokondri\b", low) and re.search(r"\bgörevi\b|\bnedir\b", low):
        return _say("Mitokondri, hücrede enerji üretiminden sorumlu organeldir.")

    return None