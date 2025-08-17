import asyncio, os, re
from telethon import TelegramClient
import pandas as pd

import re
from datetime import datetime

FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

# Persian & English month maps (Gregorian + Jalali)
GREG_MONTHS = {
    # English
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
    # Common abbreviations
    "jan":1,"feb":2,"mar":3,"apr":4,"jun":6,"jul":7,"aug":8,"sep":9,"sept":9,"oct":10,"nov":11,"dec":12,
}
JALALI_MONTHS = {
    "فروردین":1,"اردیبهشت":2,"خرداد":3,"تیر":4,"مرداد":5,"شهریور":6,
    "مهر":7,"آبان":8,"آذر":9,"دی":10,"بهمن":11,"اسفند":12
}

def cleanup(s): 
    s = (s or "").replace("\u200c"," ").replace("\ufeff"," ")
    return re.sub(r"[ \t]+"," ", s).strip()

def norm_digits(s): 
    return (s or "").translate(FA_TO_EN)

# ---- bilingual patterns ----
PATTERNS = {
    # origin / from
    "origin": re.compile(
        r"(?:^|\n)\s*(?:[#\s]*(?:مبدا|مبدأ)|origin|from)\s*[:：]\s*([^\n]+)", re.I),
    # destination / to
    "destination": re.compile(
        r"(?:^|\n)\s*(?:[#\s]*مقصد|destination|to)\s*[:：]\s*([^\n]+)", re.I),
    # date
    "date": re.compile(
        r"(?:^|\n)\s*(?:تاریخ(?:\s*پرواز)?|date|flight\s*date|departure\s*date)\s*[:：]?\s*([^\n]+)", re.I),
    # time
    "time": re.compile(
        r"(?:^|\n)\s*(?:زمان(?:\s*پرواز)?|ساعت|time|departure\s*time|at)\s*[:：]?\s*([^\n]+)", re.I),
    # airline (very loose)
    "airline": re.compile(
        r"(?:^|\n)\s*(?:پرواز|airline)\s*[:：]\s*([^\n]+)", re.I),
}

HANDLE_RX = re.compile(r"@[\w\d_]+")
PHONE_RX  = re.compile(r"(?:\+?98|0)\s?-?\s?[\d۰-۹]{9,11}")
HASHTAG_RX = re.compile(r"#\S+")

def split_city_area(text):
    text = cleanup(text)
    m = re.search(r"(.+?)\s*[\(（]\s*([^)）]+)\s*[\)）]", text)
    return (cleanup(m.group(1)), cleanup(m.group(2))) if m else (text, "")

def parse_date_guess(s):
    """Return ISO YYYY-MM-DD if we can; else ''."""
    if not s: return ""
    t = norm_digits(cleanup(s))

    # e.g., 22 August / 22 Aug / 22-Aug
    m = re.search(r"\b(\d{1,2})[ \-/](\w+)", t, re.I)
    if m:
        d, mon = int(m.group(1)), m.group(2).lower()
        if mon in GREG_MONTHS:
            month = GREG_MONTHS[mon]
            # try current year (fallback)
            y = datetime.utcnow().year
            try: return datetime(y, month, d).date().isoformat()
            except: pass

    # Persian month: 31 مرداد 1403  (year optional)
    m = re.search(r"\b(\d{1,2})\s+(فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)(?:\s+(\d{4}))?", t)
    if m:
        d = int(m.group(1)); mon_name = m.group(2); jy = int(m.group(3)) if m.group(3) else None
        jm = JALALI_MONTHS[mon_name]
        # optional: convert Jalali → Gregorian (simple approx without external libs)
        try:
            # lightweight converter (works fine for typical current dates)
            from datetime import date
            # minimalist Jalali->Gregorian (algorithm by Kazimierz M. Borkowski) — inline to avoid deps
            def jalali_to_gregorian(jy, jm, jd):
                jy += 1595
                days = -355668 + (365 * jy) + (jy // 33) * 8 + ((jy % 33 + 3) // 4) + jd + \
                       (31 * (jm - 1) if jm <= 6 else 186 + (jm - 7) * 30)
                gy = 400 * (days // 146097); days %= 146097
                if days > 36524:
                    gy += 100 * ((days - 1) // 36524); days = (days - 1) % 36524
                    if days >= 365: days += 1
                gy += 4 * (days // 1461); days %= 1461
                if days > 365:
                    gy += (days - 1) // 365; days = (days - 1) % 365
                gd = days + 1
                kab = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
                sal_a = [0,31,29 if kab else 28,31,30,31,30,31,31,30,31,30,31]
                gm = 1
                while gm <= 12 and gd > sal_a[gm]:
                    gd -= sal_a[gm]; gm += 1
                return gy, gm, gd

            if not jy: jy = 1403  # sensible default if year omitted
            gy, gm, gd = jalali_to_gregorian(jy, jm, d)
            return date(gy, gm, gd).isoformat()
        except:
            return ""
    # bare numeric (DD/MM or MM/DD) — last resort
    m = re.search(r"\b(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{2,4}))?\b", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else datetime.utcnow().year
        # guess format: if a>12, treat as DD/MM
        mm, dd = (b, a) if a > 12 else (a, b)
        try: return datetime(y, mm, dd).date().isoformat()
        except: pass
    return ""

def extract_flight_fields(raw_text: str):
    t = cleanup(raw_text)
    t_d = norm_digits(t)
    out = {
        "type_tags": ";".join(HASHTAG_RX.findall(t)),
        "origin": "", "origin_area": "",
        "destination": "", "destination_area": "",
        "flight_date_text": "", "flight_time_text": "",
        "flight_date_iso": "",
        "airline": "",
        "contact_handles": ";".join(set(HANDLE_RX.findall(t))),
        "contact_phones": ";".join(set(norm_digits(p) for p in PHONE_RX.findall(t_d))),
        "raw_text": t.replace("\n"," "),
    }

    m = PATTERNS["origin"].search(t)
    if m:
        city, area = split_city_area(m.group(1)); out["origin"], out["origin_area"] = city, area

    m = PATTERNS["destination"].search(t)
    if m:
        city, area = split_city_area(m.group(1)); out["destination"], out["destination_area"] = city, area

    m = PATTERNS["date"].search(t)
    if m:
        out["flight_date_text"] = cleanup(m.group(1))
        out["flight_date_iso"] = parse_date_guess(out["flight_date_text"])

    m = PATTERNS["time"].search(t)
    if m:
        out["flight_time_text"] = cleanup(m.group(1))

    m = PATTERNS["airline"].search(t)
    if m:
        out["airline"] = cleanup(m.group(1))

    return out


API_ID   = int(os.getenv("TG_API_ID", "23104838"))      # put your number or set env var
API_HASH = os.getenv("TG_API_HASH", "51acd40e4cbf848489538dbe9047c4d6")
SESSION  = os.getenv("TG_SESSION", "tele_scraper")
TARGET   = os.getenv("TG_TARGET", "https://t.me/joinchat/mRng6VpbVNwzMDNh")  # paste your link

API_ID   = int(os.getenv("TG_API_ID", "1234567489"))      # put your number or set env var
API_HASH = os.getenv("TG_API_HASH", "hash")
SESSION  = os.getenv("TG_SESSION", "tele_scraper")
TARGET   = os.getenv("TG_TARGET", "https://t.me/joinchat/mRng6VpbVNwzMDNh")  # paste your link

async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    entity = await client.get_entity(TARGET)

    flights = []  # list of dicts

    async for m in client.iter_messages(entity, limit=1000):
        print(f"Processing message {m.id}")
        

        text = m.message or ""
        if not text.strip():
            continue

        # sender name
        sender = ""
        try:
            s = await m.get_sender()
            if s:
                sender = (getattr(s, "first_name", "") or "") + " " + (getattr(s, "last_name", "") or "")
                sender = sender.strip() or getattr(s, "username", "") or str(getattr(s, "id", ""))
        except:
            pass

        # extract flight fields
        row = extract_flight_fields(text)
        row["msg_id"]   = m.id
        row["msg_date"] = m.date.isoformat()
        row["sender"]   = sender

        # keep only rows that have at least origin+destination or a date
        if row["origin"] or row["destination"] or row["flight_date_text"]:
            flights.append(row)

    # Save to CSV
    if flights:
        df = pd.DataFrame(flights)
        df.to_csv("flights.csv", index=False, encoding="utf-8-sig")
        print(f"✅ Saved {len(df)} rows to flights.csv")
    else:
        print("No flight-style messages found.")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())