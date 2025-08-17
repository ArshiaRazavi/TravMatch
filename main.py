# main.py — sanity check: read recent messages, parse, write flights.csv

import os, asyncio, csv
from datetime import timezone
from telethon import TelegramClient
from telethon.sessions import StringSession
from extractor import extract_flight_fields

# (optional) load .env if you use python-dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

API_ID   = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
TARGET   = os.getenv("TG_TARGET")  # @username or full t.me/joinchat/...
SESSION  = os.getenv("TG_SESSION", "local_session")
SESSION_STR = os.getenv("TG_SESSION_STRING")  # if set, no interactive login needed

OUT_CSV = "flights.csv"
LIMIT   = 200  # how many recent messages to scan

async def run():
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH) if SESSION_STR \
             else TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()  # first time (file session) will ask for phone + code
    entity = await client.get_entity(TARGET)

    rows = []
    async for m in client.iter_messages(entity, limit=LIMIT):
        text = (m.message or "").strip()
        if not text:
            continue

        # parse with bilingual extractor
        fields = extract_flight_fields(text)

        # keep only "flight-like" posts (tune as you like)
        if fields["origin"] or fields["destination"] or fields["flight_date_text"]:
            rows.append({
                "message_id": m.id,
                "date_utc": m.date.astimezone(timezone.utc).isoformat() if m.date else "",
                **fields
            })

    # write CSV
    if rows:
        write_header = not os.path.exists(OUT_CSV)
        with open(OUT_CSV, "a", newline="", encoding="utf-8-sig") as f:
            cols = [
                "message_id","date_utc","type_tags",
                "origin","origin_area","destination","destination_area",
                "flight_date_text","flight_time_text","flight_date_iso",
                "airline","contact_handles","contact_phones","raw_text"
            ]
            w = csv.DictWriter(f, fieldnames=cols)
            if write_header: w.writeheader()
            w.writerows(rows)
        print(f"✅ Parsed {len(rows)} flight-like posts → {OUT_CSV}")
    else:
        print("No flight-like posts found in recent messages.")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(run())
