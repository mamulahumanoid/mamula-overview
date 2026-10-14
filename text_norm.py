from __future__ import annotations

import re
import unicodedata


def fold_tr(s: str) -> str:
    s = (s or "").strip()

    # unicode normalize
    s = unicodedata.normalize("NFKC", s)

    # Turkish dotted/dotless i düzelt
    s = s.replace("İ", "i").replace("I", "ı")

    # küçük harf
    s = s.lower()

    # farklı apostrof tipleri
    s = s.replace("’", "'").replace("`", "'").replace("´", "'")

    # noktalama sadeleştir
    s = re.sub(r"[“”\"()\[\]{}<>]", " ", s)

    # p i -> pi
    s = re.sub(r"\bp\s+i\b", "pi", s)

    # mamula varyasyonları
    s = re.sub(r"\bmamulam\b", "mamula", s)
    s = re.sub(r"\bmamula+m+\b", "mamula", s)

    # türkçe ekleri kabaca temizle
    s = re.sub(r"\b([a-zçğıöşü]+)'?(nin|nın|nun|nün)\b", r"\1", s)
    s = re.sub(r"\b([a-zçğıöşü]+)'?(yi|yı|yu|yü)\b", r"\1", s)
    s = re.sub(r"\b([a-zçğıöşü]+)'?(i|ı|u|ü)\b", r"\1", s)
    s = re.sub(r"\b([a-zçğıöşü]+)'?(ye|ya)\b", r"\1", s)
    s = re.sub(r"\b([a-zçğıöşü]+)'?(de|da|te|ta)\b", r"\1", s)
    s = re.sub(r"\b(?!sultan\b)([a-zçğıöşü]+)'?(den|dan|ten|tan)\b", r"\1", s)

    # çok geçen bozuk halleri düzelt
    s = re.sub(r"\bgeometriyi\b", "geometri", s)
    s = re.sub(r"\bfonksiyonu\b", "fonksiyon", s)
    s = re.sub(r"\bdenklemi\b", "denklem", s)
    s = re.sub(r"\bolasiligi\b", "olasılık", s)
    s = re.sub(r"\bistatistigi\b", "istatistik", s)
    s = re.sub(r"\bcografi\b", "coğrafi", s)
    s = re.sub(r"\bcografya\b", "coğrafya", s)

    # türkiye nin -> türkiye
    s = re.sub(r"\btürkiye nin\b", "türkiye", s)
    s = re.sub(r"\btürkiye'nin\b", "türkiye", s)

    # nil nehri'nin -> nil nehri
    s = re.sub(r"\bnehri'nin\b", "nehri", s)
    s = re.sub(r"\bnehri nin\b", "nehri", s)

    # gereksiz boşluk
    s = re.sub(r"[?!,;:]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def strip_wakeword_tr(s: str) -> str:
    t = fold_tr(s)
    t = re.sub(r"^\s*mamula\b", "", t).strip()
    return t


def looks_like_wakeword_only(s: str) -> bool:
    t = fold_tr(s)
    return bool(re.fullmatch(r"mamula", t))


def is_wakeword_prefixed(s: str) -> bool:
    t = fold_tr(s)
    return bool(re.match(r"^\s*mamula\b", t))


def normalize_knowledge_query(s: str) -> str:
    """
    API'ye gidecek sorguyu temizler.
    Amaç: 'nil nehri'nin önemi nedir' -> 'nil nehri'
          'türkiye'nin başkenti neresidir' -> 'türkiye başkenti'
          'pisagor teoremi nedir' -> 'pisagor teoremi'
    """
    t = strip_wakeword_tr(s)

    # soru kalıplarını sadeleştir
    t = re.sub(r"\bnedir\b", "", t)
    t = re.sub(r"\bkimdir\b", "", t)
    t = re.sub(r"\bnerededir\b", "", t)
    t = re.sub(r"\bneresidir\b", "", t)
    t = re.sub(r"\bne zaman\b", "", t)
    t = re.sub(r"\bneden önemlidir\b", "", t)
    t = re.sub(r"\bneden onemlidir\b", "", t)
    t = re.sub(r"\bönemi nedir\b", "", t)
    t = re.sub(r"\bonemi nedir\b", "", t)
    t = re.sub(r"\baçıklar mısın\b", "", t)
    t = re.sub(r"\baciklar misin\b", "", t)
    t = re.sub(r"\baçıkla\b", "", t)
    t = re.sub(r"\bacikla\b", "", t)

    # fazlalıklar
    t = re.sub(r"\börneğin\b", "", t)
    t = re.sub(r"\bornegin\b", "", t)
    t = re.sub(r"\blütfen\b", "", t)
    t = re.sub(r"\blutfen\b", "", t)

    t = re.sub(r"\s+", " ", t).strip()
    return t
