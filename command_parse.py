"""Ses görevi metni için dil bilinçli deterministik komut ayrıştırma."""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.skills.command_map_en import parse_command_en
from core.skills.command_map_tr import ParsedCommand, parse_command
from core.utils.locale_resolution import normalize_locale_base, runtime_default_locale

__all__ = ["parse_voice_command", "ParsedCommand", "voice_task_lang_from_plan_meta"]


def voice_task_lang_from_plan_meta(msg: Any) -> Optional[str]:
    """
    Plan olayından yalnızca **açıkça iletilen** ses görevi dili.

    ``meta.extra.task_lang`` veya ``meta.extra.lang`` (STT / router'ın ``TaskReceived.lang`` ile uyumlu).
    İkisi de yoksa ``None`` — ``parse_voice_command(text, None)`` çalışma zamanı varsayılanına
    (genelde ``tr``) düşer; Türkçe kararlılığı bozmaz.
    """
    ex: Dict[str, Any] = {}
    try:
        m = getattr(msg, "meta", None)
        if m is not None:
            ex = dict(getattr(m, "extra", {}) or {})
    except Exception:
        ex = {}
    if not ex and isinstance(msg, dict):
        ex = dict(((msg.get("meta") or {}).get("extra") or {}))
    raw = ex.get("task_lang") or ex.get("lang")
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def parse_voice_command(text: str, lang: Optional[str] = None) -> Optional[ParsedCommand]:
    """
    Önce kullanıcı yerel ayarına göre sırayla dener; eşleşme yoksa yedek dil.

    - ``tr``: Türkçe parser, sonra İngilizce (ör. "stop", "go forward").
    - Diğer tüm kodlar: İngilizce, sonra Türkçe (aynı evde iki dil karışık kullanım).
    """
    base = normalize_locale_base(lang, fallback=runtime_default_locale())
    primary_tr = base == "tr"
    first = parse_command if primary_tr else parse_command_en
    second = parse_command_en if primary_tr else parse_command

    r = first(text)
    if r is not None:
        return r
    return second(text)
