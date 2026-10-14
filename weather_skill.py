# core/skills/weather_skill.py
from __future__ import annotations

import calendar
import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from core.contract.actions import normalize_step
from core.skills.text_norm import fold_tr

# -------------------------------
# Intent detection
# -------------------------------
_WEATHER_RE = re.compile(
    r"\b("
    r"hava\s*durumu|hava\s*nas[ıi]l|ya[ğg]mur|s[ıi]cakl[ıi]k|r[üu]zgar|nem|"
    r"forecast|weather"
    r")\b",
    flags=re.IGNORECASE,
)

# ``tahmin`` alone is a general Turkish word ("guess/prediction"), not a
# weather intent.  Accept it only when the same utterance also carries a
# concrete weather or forecast-time anchor.
_TR_WEATHER_FORECAST_RE = re.compile(
    r"(?:\b(?:hava|ya[ğg]mur|s[ıi]cakl[ıi]k|r[üu]zgar|nem|bugün|bugun|yar[ıi]n|hafta)\b"
    r".{0,50}\btahmin\b|\btahmin\b.{0,50}"
    r"\b(?:hava|ya[ğg]mur|s[ıi]cakl[ıi]k|r[üu]zgar|nem|bugün|bugun|yar[ıi]n|hafta)\b)",
    flags=re.IGNORECASE,
)

_CITY_CLEAN_RE = re.compile(r"[^\wğüşöçıİĞÜŞÖÇ\s\'-]+", flags=re.UNICODE)

# -------------------------------
# Period / time parsing
# -------------------------------
# api_skill_module.py target_period: "morning|noon|afternoon|evening|night"
_PERIOD_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("morning", re.compile(r"\b(sabah|erken\s+sabah|günün\s+ilk\s+saatleri)\b", re.I)),
    ("noon", re.compile(r"\b(öğle|ogle|öğlen|oglen)\b", re.I)),
    ("afternoon", re.compile(r"\b(öğleden\s+sonra|ogleden\s+sonra|ikindi)\b", re.I)),
    ("evening", re.compile(r"\b(akşam|aksam|akşamüstü|aksamustu|akşam\s+üstü|aksam\s+ustu)\b", re.I)),
    ("night", re.compile(r"\b(gece|bu\s+gece|geceleyin|gece\s+yarısı)\b", re.I)),
]

_TOMORROW_RE = re.compile(r"\b(yarın|yarin)\b", re.IGNORECASE)
_TODAY_RE = re.compile(r"\b(bugün|bugun)\b", re.IGNORECASE)
_THIS_RE = re.compile(r"\b(bu)\b", re.IGNORECASE)

_NEXT_RE = re.compile(r"\b(önümüzdeki|gelecek)\b", re.IGNORECASE)
_NEXT_WEEK_RE = re.compile(r"\b(haftaya|gelecek\s+hafta|önümüzdeki\s+hafta)\b", re.IGNORECASE)

# Relative day phrases
_DAYS_AFTER_RE = re.compile(r"\b(\d{1,2})\s*(gün|gun)\s+sonra\b", re.IGNORECASE)

# Day of month: "ayın 3'ünde", "ayın 15inde"
_DAY_OF_MONTH_RE = re.compile(r"\b(ayın|ayin)\s+(\d{1,2})\s*(\'?(inde|ında|unda|ünde|de|da))?\b", re.IGNORECASE)

_HOURLY_RE = re.compile(r"\b(saat\s*saat|saatlik|saat\s+kaçta|saat\s+kaç)\b", re.IGNORECASE)
_WEEKLY_RE = re.compile(r"\b(haftalık|haftalik)\b", re.IGNORECASE)
_DAYS_RE = re.compile(r"\b(\d{1,2})\s*(gün|gun)\b", re.IGNORECASE)
_DETAILED_RE = re.compile(r"\b(detaylı|detayli|ayrıntı|ayrinti)\b", re.IGNORECASE)

_FIELD_HINTS = {
    "temperature": re.compile(r"\b(sıcaklık|sicaklik|derece)\b", re.IGNORECASE),
    "wind": re.compile(r"\b(rüzgar|ruzgar|rüzgâr|ruzgâr)\b", re.IGNORECASE),
    "humidity": re.compile(r"\b(nem)\b", re.IGNORECASE),
    "precip": re.compile(r"\b(yağış|yagis|yağmur|yagmur|kar)\b", re.IGNORECASE),
}

# "Ankara'da", "Paris'te"
_LOC_SUFFIX_RE = re.compile(r"\'?(d[ae]|t[ae])\b", re.IGNORECASE)

# ✅ "İstanbul'un", "Ankara'nın" gibi iyelik ekleri
_POSSESSIVE_SUFFIX_RE = re.compile(
    r"(?:\'?\s*)(?:n)?(?:un|ün|ın|in|nun|nün|nın|nin)\b",
    re.IGNORECASE,
)

# ✅ Tarih/offset sayılarının konuma karışmasını engelle (2, 3'ünde, 10uncu gibi)
_NUM_SUFFIX_CLEAN_RE = re.compile(
    r"\b\d{1,2}\s*\'?\s*(inde|ında|unda|ünde|in|ın|un|ün|inci|ıncı|uncu|üncü|nci|ncı|ncu|ncü)?\b",
    re.IGNORECASE,
)

_MULTI_SPACE_RE = re.compile(r"\s+")

# ✅ Ülke / çok genel ifade (Open-Meteo bazen "America, Limburg" gibi alakasız eşleştirebiliyor)
_VAGUE_LOCATION_RE = re.compile(
    r"^\s*(amerika|abd|a\.?b\.?d\.?|usa|u\.?s\.?a\.?|united\s+states|türkiye|turkiye|"
    r"ingiltere|fransa|almanya|ispanya|italya|avrupa)\s*$",
    re.IGNORECASE,
)

# -------------------------------
# Weekday mapping
# -------------------------------
# date.weekday(): Monday=0 ... Sunday=6
_WEEKDAY_MAP = {
    # TR
    "pazartesi": 0,
    "salı": 1,
    "sali": 1,
    "çarşamba": 2,
    "carsamba": 2,
    "çarsamba": 2,
    "perşembe": 3,
    "persembe": 3,
    "cuma": 4,
    "cumartesi": 5,
    "pazar": 6,
    # short
    "pzt": 0,
    "sal": 1,
    "çar": 2,
    "car": 2,
    "per": 3,
    "cum": 4,
    "cts": 5,
    "pazr": 6,
    # EN
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_WEEKDAY_RE = re.compile(
    r"\b("
    r"pazartesi|salı|sali|çarşamba|carsamba|çarsamba|perşembe|persembe|cuma|cumartesi|pazar|"
    r"pzt|sal|çar|car|per|cum|cts|pazr|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r")\b",
    re.IGNORECASE,
)

# core/skills/weather_skill.py

_STRIP_WORDS_RE = re.compile(
    r"\b("
    r"mamula|lütfen|lutfen|"
    r"hava|durumu|nasıl|nasil|"
    r"bugün|bugun|yarın|yarin|bu|"
    r"haftaya|gelecek|önümüzdeki|hafta|"
    r"sabah|öğle|ogle|öğlen|oglen|öğleden\s+sonra|ogleden\s+sonra|ikindi|"
    r"akşam|aksam|akşamüstü|aksamustu|gece|"
    r"detaylı|detayli|ayrıntı|ayrinti|"
    r"saat\s*saat|saatlik|"
    r"haftalık|haftalik|"
    r"gün|gun|günü|gunu|sonra|"
    r"ayın|ayin|"
    r"tahmin|forecast|weather|"
    r"amerika|abd|a\.?b\.?d\.?|usa|u\.?s\.?a\.?|united\s+states|"
    r"pazartesi|salı|sali|çarşamba|carsamba|çarsamba|perşembe|persembe|cuma|cumartesi|pazar|"
    r"pzt|sal|çar|car|per|cum|cts|pazr|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r")\b",
    re.IGNORECASE,
)


def _norm(t: str) -> str:
    t = (t or "").strip()
    t = _MULTI_SPACE_RE.sub(" ", t)
    return t


def _weekday_offset(text_folded: str) -> Optional[int]:
    """
    "pazar", "pazartesi" gibi gün adlarını bulur ve bugüne göre offset döner.
    Eğer "haftaya/gelecek hafta" varsa, mutlaka next week'e atar.
    """
    m = _WEEKDAY_RE.search(text_folded)
    if not m:
        return None

    w = (m.group(1) or "").lower().strip()
    target = _WEEKDAY_MAP.get(w)
    if target is None:
        return None

    today_wd = date.today().weekday()  # Mon=0..Sun=6
    base = (int(target) - int(today_wd)) % 7  # 0..6

    force_next_week = bool(_NEXT_WEEK_RE.search(text_folded)) or bool(_NEXT_RE.search(text_folded) and "hafta" in text_folded)
    if force_next_week:
        if base == 0:
            return 7
        return base + 7

    if _NEXT_RE.search(text_folded) and base == 0:
        base = 7

    return int(base)


def _offset_from_day_of_month(day: int) -> Optional[int]:
    """
    "ayın 3'ünde" -> bir sonraki uygun tarih için offset döner.
    Bugün ayın 3'ü ise offset 0.
    Eğer bu ayda geçtiyse, bir sonraki aya bakar (geçerli gün bulana kadar).
    """
    try:
        day = int(day)
    except Exception:
        return None
    if day < 1 or day > 31:
        return None

    today = date.today()
    y, m = today.year, today.month

    for step in range(0, 13):
        mm = m + step
        yy = y + (mm - 1) // 12
        mm = (mm - 1) % 12 + 1
        last = calendar.monthrange(yy, mm)[1]
        if day > last:
            continue

        candidate = date(yy, mm, day)
        if candidate < today:
            continue
        return (candidate - today).days

    return None


def _parse_explicit_day_offset(text_folded: str) -> Optional[int]:
    """
    Öncelik sırası:
      - "N gün sonra"
      - "ayın N'inde"
      - "haftaya" (tek başına) -> 7
    """
    m = _DAYS_AFTER_RE.search(text_folded)
    if m:
        try:
            n = int(m.group(1))
            if 0 <= n <= 60:
                return n
        except Exception:
            pass

    m = _DAY_OF_MONTH_RE.search(text_folded)
    if m:
        try:
            day = int(m.group(2))
        except Exception:
            day = None
        if day is not None:
            off = _offset_from_day_of_month(day)
            if off is not None:
                return int(off)

    if _NEXT_WEEK_RE.search(text_folded) and not _WEEKDAY_RE.search(text_folded):
        return 7

    return None


def _detect_period_and_day(text_folded: str) -> Tuple[Optional[str], int]:
    """
    Returns:
      target_period: "morning|noon|afternoon|evening|night" or None
      day_offset: 0 today, 1 tomorrow, N weekday/explicit offset...
    """
    explicit = _parse_explicit_day_offset(text_folded)
    if explicit is not None:
        day_offset = int(explicit)
    else:
        wd = _weekday_offset(text_folded)
        if wd is not None:
            day_offset = int(wd)
        else:
            if _TOMORROW_RE.search(text_folded):
                day_offset = 1
            elif _TODAY_RE.search(text_folded) or _THIS_RE.search(text_folded):
                day_offset = 0
            else:
                day_offset = 0

    target_period: Optional[str] = None
    for key, pat in _PERIOD_PATTERNS:
        if pat.search(text_folded):
            target_period = key
            break

    return target_period, day_offset


def _detect_mode_days_hours(text_folded: str, *, target_period: Optional[str], day_offset: int) -> Tuple[str, int, int, bool]:
    """
    mode: current|daily|hourly
    days: forecast_days (1..14)
    hours: hourly list length (3..24)
    want_tomorrow: True => api tarafında yarın satırı gelsin
    """
    hourly = bool(_HOURLY_RE.search(text_folded)) or (target_period is not None)

    days = 1
    m = _DAYS_RE.search(text_folded)
    if m:
        try:
            days = int(m.group(1))
        except Exception:
            days = 1

    if _WEEKLY_RE.search(text_folded) and days < 7:
        days = 7

    want_tomorrow = bool(_TOMORROW_RE.search(text_folded))

    if day_offset >= 1:
        days = max(days, day_offset + 1)

    if want_tomorrow and days < 2:
        days = 2

    days = max(1, min(14, days))

    if hourly:
        mode = "hourly"
    elif days >= 2 or _WEEKLY_RE.search(text_folded) or want_tomorrow or day_offset >= 1:
        mode = "daily"
    else:
        mode = "current"

    hours = 6
    hours = max(3, min(24, int(hours)))

    return mode, days, hours, want_tomorrow


def _detect_fields(text_folded: str) -> List[str]:
    hits: List[str] = []
    for k, rx in _FIELD_HINTS.items():
        if rx.search(text_folded):
            hits.append(k)

    if not hits:
        return ["temperature", "wind", "humidity", "precip"]

    if "temperature" not in hits:
        hits.insert(0, "temperature")

    out: List[str] = []
    for x in hits:
        if x not in out:
            out.append(x)
    return out


def _extract_city(text: str) -> str:
    """
    Dünya geneli şehir/konum çıkarımı (Open-Meteo geocoding'e verilecek query).
    """
    t = fold_tr((text or "").strip())
    if not t:
        return "Istanbul"
    low = t

    cand = ""
    m = re.search(r"\bhava\s*durumu\s+(.+)$", low, flags=re.IGNORECASE)
    if m:
        cand = m.group(1).strip()
    else:
        m2 = re.search(r"^(.+?)\s+hava\s*durumu\b", low, flags=re.IGNORECASE)
        if m2:
            cand = m2.group(1).strip()
        else:
            m3 = re.search(r"^(.+?)\s+hava\s+nas[ıi]l\b", low, flags=re.IGNORECASE)
            if m3:
                cand = m3.group(1).strip()
            else:
                cand = low

    cand = cand.strip()
    cand = re.sub(r"\bmamula\b", "", cand, flags=re.IGNORECASE).strip()

    # ✅ önce iyelik eklerini kırp (istanbul'un -> istanbul)
    cand = _POSSESSIVE_SUFFIX_RE.sub("", cand).strip()

    # "Paris'te" / "Ankara'da"
    cand = _LOC_SUFFIX_RE.sub("", cand).strip()

    # ✅ "2 gün sonra" / "ayın 3'ünde" gibi parçaların sayısı konuma karışmasın
    cand = _NUM_SUFFIX_CLEAN_RE.sub(" ", cand)

    cand = _STRIP_WORDS_RE.sub(" ", cand)
    cand = _CITY_CLEAN_RE.sub("", cand)
    cand = _norm(cand)

    # ✅ baş/sonda kalan tek sayı tokenları temizle
    toks = [x for x in cand.split() if x]
    toks = [x for x in toks if not re.fullmatch(r"\d{1,2}", x)]
    cand = " ".join(toks).strip()

    if not cand:
        tokens = [x for x in re.split(r"\s+", _CITY_CLEAN_RE.sub("", low)) if x]
        if tokens:
            return tokens[-1].title()
        return "Istanbul"

    return cand.title()


def _make_key(city: str, mode: str, days: int, fields: List[str], detailed: bool, *, target_period: Optional[str], day_offset: int, hours: int) -> str:
    fld = "-".join(fields) if fields else "all"
    det = "1" if detailed else "0"
    per = target_period or "none"
    return f"weather:{city.strip().lower()}:{mode}:{days}:{fld}:{det}:{per}:{day_offset}:{hours}"


def try_parse_weather(text: str) -> Optional[Dict[str, Any]]:
    """
    Weather v2 parser:
      - Dünya geneli konum (Open-Meteo geocoding)
      - current / daily / hourly
      - bugün/yarın + sabah/akşam/gece + gün adı ("pazar sabah")
      - "2 gün sonra", "haftaya salı", "ayın 3'ünde"
      - TTS odaklı params ile api_skill_module.py'ye zengin bilgi taşır
    """
    raw = (text or "").strip()
    t = fold_tr(raw)
    if not t or not (_WEATHER_RE.search(t) or _TR_WEATHER_FORECAST_RE.search(t)):
        return None

    detailed = bool(_DETAILED_RE.search(t))

    target_period, day_offset = _detect_period_and_day(t)
    mode, days, hours, want_tomorrow = _detect_mode_days_hours(t, target_period=target_period, day_offset=day_offset)
    fields = _detect_fields(t)

    city = _extract_city(raw) or "Istanbul"

    # ✅ "amerika/abd/usa/türkiye/avrupa" gibi çok genel ifade ise yanlış eşleşme yerine şehir iste
    if _VAGUE_LOCATION_RE.match(city.strip().lower()):
        return normalize_step(
            {"type": "CMD", "cmd_type": "SAY", "params": {"text": "Hangi şehir için hava durumunu istiyorsun? (örn: New York, Los Angeles, Berlin)"}}
        )

    key = _make_key(city, mode, days, fields, detailed, target_period=target_period, day_offset=day_offset, hours=hours)

    params: Dict[str, Any] = {
        "provider": "open_meteo",
        "query": city.strip().lower(),
        "key": key,
        "ttl_sec": 1800,
        "lang": "tr",
        "mode": mode,                 # current|daily|hourly
        "days": days,                 # forecast_days
        "fields": fields,             # temperature/wind/humidity/precip
        "detailed": detailed,
        "want_tomorrow": bool(want_tomorrow),
    }

    if day_offset:
        params["day_offset"] = int(day_offset)

    if target_period is not None:
        params["mode"] = "hourly"
        params["target_period"] = target_period
        params["day_offset"] = int(day_offset)
        params["hours"] = int(hours)

    if _HOURLY_RE.search(t) and "target_period" not in params:
        params["mode"] = "hourly"
        params["hours"] = int(hours)
        params["day_offset"] = int(day_offset)

    return normalize_step(
        {
            "type": "CMD",
            "cmd_type": "FETCH_API",
            "params": params,
            "priority": 0,
            "cancel_previous": False,
            "note": "",
        }
    )
