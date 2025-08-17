# extractor.py
# Bilingual (FA/EN) extractor for flight/delivery posts
# - No external deps
# - Returns a dict ready for CSV/DB

from __future__ import annotations
import re
from datetime import datetime, date
from typing import Dict, Tuple

# ---------- Utilities ----------

FA_TO_EN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

GREG_MONTHS = {
    # English long
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
    # English short
    "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"sept":9,"oct":10,"nov":11,"dec":12,
}

PERSIAN_GREG_MONTHS = {
    "ژانویه":1, "فوریه":2, "مارس":3, "آوریل":4, "مه":5, "ژوئن":6,
    "ژوئیه":7, "جولای":7, "اوت":8, "آگوست":8, "سپتامبر":9,
    "اکتبر":10, "نوامبر":11, "دسامبر":12
}

JALALI_MONTHS = {
    "فروردین":1,"اردیبهشت":2,"خرداد":3,"تیر":4,"مرداد":5,"شهریور":6,
    "مهر":7,"آبان":8,"آذر":9,"دی":10,"بهمن":11,"اسفند":12
}

AIRLINE_WORDS = r"(?:امارات|قطر|ترکیش|لوفتانزا|ایران\s?ایر|قشم|ماهان|عمان|اروپا|Austrian|Turkish|Qatar|Emirates|Lufthansa|Oman|Iran\s?Air|Mahan)"

HANDLE_RX   = re.compile(r"@[\w\d_]+")
HASHTAG_RX  = re.compile(r"#\S+")
PHONE_RX    = re.compile(r"(?:\+?\d[\d\s\-()]{8,16}\d)")  # generic intl (Iran +98, CA +1, etc.)

def cleanup(s: str) -> str:
    if not s: return ""
    s = s.replace("\u200c", " ")  # ZWNJ
    s = s.replace("\ufeff", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

def norm_digits(s: str) -> str:
    return (s or "").translate(FA_TO_EN_DIGITS)

def contains_persian(text: str) -> bool:
    return any('\u0600' <= ch <= '\u06FF' for ch in text or "")

def split_city_area(text: str) -> Tuple[str, str]:
    """Return (city, area) if parentheses exist; otherwise (text, '')."""
    t = cleanup(text)
    m = re.search(r"(.+?)\s*[\(（]\s*([^)）]+)\s*[\)）]", t)
    return (cleanup(m.group(1)), cleanup(m.group(2))) if m else (t, "")

# ---------- Date / time parsing ----------

def jalali_to_gregorian(jy: int, jm: int, jd: int) -> Tuple[int, int, int]:
    """Minimal Jalali→Gregorian (Borkowski). Works fine for modern dates."""
    jy += 1595
    days = -355668 + 365 * jy + (jy // 33) * 8 + ((jy % 33 + 3) // 4) + jd + (31 * (jm - 1) if jm <= 6 else 186 + (jm - 7) * 30)
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        gy += 100 * ((days - 1) // 36524)
        days = (days - 1) % 36524
        if days >= 365: days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    kab = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    month_days = [0,31,29 if kab else 28,31,30,31,30,31,31,30,31,30,31]
    gm = 1
    while gm <= 12 and gd > month_days[gm]:
        gd -= month_days[gm]; gm += 1
    return gy, gm, gd

def parse_date_guess(s: str) -> str:
    """
    Try to parse many formats to ISO YYYY-MM-DD.
    Returns '' if unsure.
    """
    if not s: return ""
    t = norm_digits(cleanup(s))

    # English month formats: 22 August / Aug 22 / 22-Aug
    m = re.search(r"\b(\d{1,2})[ \-\/](\w+)\b", t, re.I)
    if m:
        d, mon = int(m.group(1)), m.group(2).lower()
        if mon in GREG_MONTHS:
            y = datetime.utcnow().year
            try: return date(y, GREG_MONTHS[mon], d).isoformat()
            except: pass

    m = re.search(r"\b(\w+)[ \-](\d{1,2})\b", t, re.I)
    if m:
        mon, d = m.group(1).lower(), int(m.group(2))
        if mon in GREG_MONTHS:
            y = datetime.utcnow().year
            try: return date(y, GREG_MONTHS[mon], d).isoformat()
            except: pass

    # Persian month: 31 مرداد 1403 (year optional)
    m = re.search(r"\b(\d{1,2})\s+(فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)(?:\s+(\d{3,4}))?\b", t)
    if m:
        d = int(m.group(1)); mon_name = m.group(2); jm = JALALI_MONTHS[mon_name]
        jy = int(m.group(3)) if m.group(3) else 1403  # sensible default
        try:
            gy, gm, gd = jalali_to_gregorian(jy, jm, d)
            return date(gy, gm, gd).isoformat()
        except:
            pass

    # Persian month: "5 سپتامبر [1403|2025]" (year optional → assume current gregorian)
    m = re.search(r"\b(\d{1,2})\s+(ژانویه|فوریه|مارس|آوریل|مه|ژوئن|ژوئیه|جولای|اوت|آگوست|سپتامبر|اکتبر|نوامبر|دسامبر)(?:\s+(\d{3,4}))?\b", t)
    if m:
        d = int(m.group(1)); mon = m.group(2)
        y = int(m.group(3)) if m.group(3) else datetime.utcnow().year
        try: return date(y, PERSIAN_GREG_MONTHS[mon], d).isoformat()
        except: pass

    # Persian month first: "سپتامبر 5 [2025]"
    m = re.search(r"\b(ژانویه|فوریه|مارس|آوریل|مه|ژوئن|ژوئیه|جولای|اوت|آگوست|سپتامبر|اکتبر|نوامبر|دسامبر)\s+(\d{1,2})(?:\s+(\d{3,4}))?\b", t)
    if m:
        mon = m.group(1); d = int(m.group(2))
        y = int(m.group(3)) if m.group(3) else datetime.utcnow().year
        try: return date(y, PERSIAN_GREG_MONTHS[mon], d).isoformat()
        except: pass


    # Numeric DD/MM(/YY) or MM/DD(/YY) → guess by a>12
    m = re.search(r"\b(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{2,4}))?\b", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else datetime.utcnow().year
        mm, dd = (b, a) if a > 12 else (a, b)
        try: return date(y, mm, dd).isoformat()
        except: pass

    return ""

def parse_time_guess(s: str) -> str:
    """
    Try HH:MM (24h) or 9 pm / 9:30pm → 'HH:MM'
    Returns '' if not found.
    """
    if not s: return ""
    t = norm_digits(cleanup(s)).lower()

    # 24h HH:MM
    m = re.search(r"\b([01]?\d|2[0-3])[:٫\.]([0-5]\d)\b", t)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"

    # 12h like 9 pm, 9:30pm
    m = re.search(r"\b(\d{1,2})(?::([0-5]\d))?\s*(am|pm|a\.m\.|p\.m\.)\b", t)
    if m:
        h = int(m.group(1))
        mn = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3)
        if "p" in ampm and h != 12: h += 12
        if "a" in ampm and h == 12: h = 0
        return f"{h:02d}:{mn:02d}"

    # Persian words for morning/evening (approx): 9 صبح / 7 عصر
    m = re.search(r"\b(\d{1,2})(?::([0-5]\d))?\s*(صبح|عصر|شب|AM|PM)\b", t, re.I)
    if m:
        h = int(m.group(1)); mn = int(m.group(2)) if m.group(2) else 0
        tag = m.group(3)
        if tag in ["عصر","شب","PM","pm"] and h != 12: h += 12
        if tag in ["صبح","AM","am"] and h == 12: h = 0
        return f"{h:02d}:{mn:02d}"

    return ""

# ---------- Core patterns ----------

PAT = {
    # Labeled fields (both FA/EN)
    "origin": re.compile(r"(?:^|\n)\s*(?:[#\s]*(?:مبدا|مبدأ)|origin|from)\s*[:：]\s*([^\n]+)", re.I),
    "destination": re.compile(r"(?:^|\n)\s*(?:[#\s]*مقصد|destination|to)\s*[:：]\s*([^\n]+)", re.I),
    "date": re.compile(r"(?:^|\n)\s*(?:تاریخ(?:\s*پرواز)?|date|flight\s*date|departure\s*date)\s*[:：]?\s*([^\n]+)", re.I),
    "time": re.compile(r"(?:^|\n)\s*(?:زمان(?:\s*پرواز)?|ساعت|time|departure\s*time|at)\s*[:：]?\s*([^\n]+)", re.I),
    "airline": re.compile(r"(?:^|\n)\s*(?:پرواز|airline)\s*[:：]\s*([^\n]+)", re.I),
    # From → To inline (EN): "from Tehran to Toronto"
    "from_to_en": re.compile(r"\bfrom\s+(.+?)\s+to\s+(.+?)(?:[\s\.,;]|$)", re.I),
    # From → To inline (FA): "از تهران به تورنتو"
    "from_to_fa": re.compile(r"\bاز\s+(.+?)\s+به\s+(.+?)(?:[\s\.,؛]|$)"),
    # Hashtags to help classify type
    "tags": HASHTAG_RX,
}

def _extract_contacts(text: str) -> Tuple[str, str, str]:
    handles = set(HANDLE_RX.findall(text))
    phones  = set(norm_digits(p) for p in PHONE_RX.findall(text))
    tags    = set(HASHTAG_RX.findall(text))
    return ";".join(sorted(handles)), ";".join(sorted(phones)), ";".join(sorted(tags))

# ---------- Public API ----------

def extract_flight_fields(raw_text: str) -> Dict[str, str]:
    """
    Input: raw Telegram message text
    Output: dict with keys:
      type_tags, origin, origin_area, destination, destination_area,
      flight_date_text, flight_time_text, flight_date_iso, airline,
      contact_handles, contact_phones, raw_text
    """
    t = cleanup(raw_text)
    t_digits = norm_digits(t)

    out = {
        "type_tags": "",
        "origin": "", "origin_area": "",
        "destination": "", "destination_area": "",
        "flight_date_text": "", "flight_time_text": "",
        "flight_date_iso": "",
        "airline": "",
        "contact_handles": "", "contact_phones": "",
        "raw_text": t.replace("\n", " "),
    }

    # contacts + tags
    handles, phones, tags = _extract_contacts(t_digits)
    out["contact_handles"], out["contact_phones"], out["type_tags"] = handles, phones, tags

    # 1) labeled fields first
    m = PAT["origin"].search(t)
    if m:
        city, area = split_city_area(m.group(1)); out["origin"], out["origin_area"] = city, area

    m = PAT["destination"].search(t)
    if m:
        city, area = split_city_area(m.group(1)); out["destination"], out["destination_area"] = city, area

    m = PAT["date"].search(t)
    if m:
        out["flight_date_text"] = cleanup(m.group(1))
        out["flight_date_iso"]  = parse_date_guess(out["flight_date_text"])

    m = PAT["time"].search(t)
    if m:
        out["flight_time_text"] = parse_time_guess(m.group(1)) or cleanup(m.group(1))

    m = PAT["airline"].search(t)
    if m:
        # If line contains known airline word, keep that; else keep the line text
        line = cleanup(m.group(1))
        known = re.search(AIRLINE_WORDS, line, re.I)
        out["airline"] = cleanup(known.group(0)) if known else line

    # 2) if origin/destination still empty, try inline "from X to Y" (EN/FA)
    if not out["origin"] or not out["destination"]:
        m = PAT["from_to_en"].search(t)
        if m:
            oc, da = split_city_area(m.group(1)); out["origin"], out["origin_area"] = oc, da
            dc, aa = split_city_area(m.group(2)); out["destination"], out["destination_area"] = dc, aa

    if not out["origin"] or not out["destination"]:
        m = PAT["from_to_fa"].search(t)
        if m:
            oc, da = split_city_area(m.group(1)); out["origin"], out["origin_area"] = oc, da
            dc, aa = split_city_area(m.group(2)); out["destination"], out["destination_area"] = dc, aa

    return out

# ---------- Local test ----------
if __name__ == "__main__":
    samples = [
        """#مسافر
        مبدا: تهران (نیلوفران)
        مقصد: تورنتو (نورث یورک)
        تاریخ پرواز: 31 مرداد 1403
        ساعت: 09:15
        پرواز: امارات
        تماس: @user ۰۹۱۲۳۴۵۶۷۸۹
        """,
        """Traveler available #مسافر
        from Tehran to Toronto
        Flight date: 22 Aug
        Time: 9:30 pm
        Airline: Qatar
        Contact: @john +1 (587) 555-1212
        """,
        """از مشهد به کلگری، 5 سپتامبر، ساعت 7 عصر
        تماس: @ali""",
    ]
    for s in samples:
        print("----")
        print(extract_flight_fields(s))
