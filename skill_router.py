# core/skills/skill_router.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.contract.actions import normalize_step

from core.skills.text_norm import fold_tr
from core.skills.weather_skill import try_parse_weather
from core.skills.date_skill import try_parse_date
from core.skills.geography_skill import try_parse_geography
from core.skills.history_skill import try_parse_history
from core.skills.physics_skill import try_parse_physics
from core.skills.chemistry_skill import try_parse_chemistry
from core.skills.biology_skill import try_parse_biology
from core.skills.sociology_skill import try_parse_sociology
from core.skills.math_skill import try_parse_math
from core.skills.math_knowledge_skill import try_parse_math_knowledge
from core.skills.general_knowledge_skill import try_parse_general_knowledge
from core.skills.knowledge_skill import try_parse_knowledge


def _normalize_steps(out: Any) -> Optional[List[Dict[str, Any]]]:
    if out is None:
        return None

    if isinstance(out, list):
        return [normalize_step(s) for s in out if s is not None]

    return [normalize_step(out)]


def _run_parser(fn, text: str) -> Optional[List[Dict[str, Any]]]:
    try:
        out = fn(text)
        return _normalize_steps(out)
    except Exception as e:
        print(f"[skill_router] parser error in {getattr(fn, '__name__', 'unknown')}: {e}")
        return None


def route_text_to_steps(text: str) -> Optional[List[Dict[str, Any]]]:
    """
    Router stratejisi:

    1) Önce HAM metin ile dene
       - apostrof
       - büyük/küçük harf
       - Türkçe karakter
       - doğal cümle yapısı korunur

    2) Sonra fold edilmiş metin ile tekrar dene
       - ASCII'de kalmış varyasyonlar
       - sesli yazım / STT sapmaları
       - 'turkiye', 'istanbul', 'vestfalya' benzeri durumlar

    Sıra önemli:
    - hava / tarih
    - coğrafya / tarih / fen
    - matematik işlem
    - matematik bilgi
    """
    raw = (text or "").strip()
    if not raw:
        return None

    folded = fold_tr(raw)

    parsers = (
        try_parse_weather,
        try_parse_date,
        try_parse_geography,
        try_parse_history,
        try_parse_physics,
        try_parse_chemistry,
        try_parse_biology,
        try_parse_sociology,
        try_parse_math,
        try_parse_math_knowledge,
        try_parse_knowledge,
        try_parse_general_knowledge,
    )

    # 1) Önce ham metin
    for fn in parsers:
        steps = _run_parser(fn, raw)
        if steps:
            print(f"[skill_router] matched raw -> {getattr(fn, '__name__', 'unknown')}")
            return steps

    # 2) Sonra fold edilmiş metin
    if folded != raw:
        for fn in parsers:
            steps = _run_parser(fn, folded)
            if steps:
                print(f"[skill_router] matched folded -> {getattr(fn, '__name__', 'unknown')}")
                return steps

    return None