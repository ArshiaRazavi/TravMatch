# ingest_telethon.py — read Telegram messages → parse → save to DB

import os, asyncio, json
from datetime import timezone, date
from telethon import TelegramClient
from telethon.sessions import StringSession

# load .env
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except Exception:
    pass

def req(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing {name}. Put it in your .env.")
    return v

API_ID      = int(req("TG_API_ID"))
API_HASH    = req("TG_API_HASH")
TARGET      = req("TG_TARGET")                 # @username or full t.me/joinchat/...
SESSION     = os.getenv("TG_SESSION", "ingest_session")
SESSION_STR = os.getenv("TG_SESSION_STRING")
LIMIT       = int(os.getenv("TG_LIMIT", "500"))  # how many messages per run
SEARCH      = os.getenv("TG_SEARCH")             # optional filter (e.g., "#مسافر")

def make_client():
    return TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH) if SESSION_STR \
           else TelegramClient(SESSION, API_ID, API_HASH)

STATE_FILE = "state.json"  # remembers last_id per chat so you only fetch new messages

from extractor import extract_flight_fields
from city_map import to_code
from db import SessionLocal
from models import AppUser, Post, Trip

def _load_state():
    try:
        return json.load(open(STATE_FILE, "r", encoding="utf-8"))
    except Exception:
        return {}

def _save_state(s):
    json.dump(s, open(STATE_FILE, "w", encoding="utf-8"))

async def main():
    client = make_client()
    await client.start()
    entity = await client.get_entity(TARGET)   # ← resolves your group/channel

    state = _load_state()
    last_id = int(state.get(str(entity.id), 0))

    db = SessionLocal()
    added = 0
    max_id = last_id

    try:
        # ==== THIS IS WHERE THE SCAN HAPPENS ====
        it = client.iter_messages(
            entity,
            limit=LIMIT,
            min_id=last_id,     # only newer than last run
            search=SEARCH       # optional: filter by keyword/hashtag
        )

        async for m in it:
            text = (m.message or "").strip()
            if not text:
                continue

            # upsert sender (AppUser)
            try:
                s = await m.get_sender()
                tg_id = getattr(s, "id", None)
                u = db.query(AppUser).filter_by(telegram_id=tg_id).one_or_none()
                if not u:
                    display = " ".join(filter(None, [getattr(s, "first_name", None),
                                                     getattr(s, "last_name", None)])) or None
                    u = AppUser(telegram_id=tg_id,
                                username=getattr(s, "username", None),
                                display_name=display)
                    db.add(u); db.flush()
            except Exception:
                u = None

            # skip duplicates
            if db.query(Post).filter_by(chat_id=entity.id, message_id=m.id).first():
                if m.id > max_id: max_id = m.id
                continue

            # parse with bilingual extractor
            fields = extract_flight_fields(text)

            post = Post(
                chat_id=entity.id,
                message_id=m.id,
                posted_at=m.date.astimezone(timezone.utc) if m.date else None,
                posted_by=(u.id if u else None),
                raw_text=fields["raw_text"],
                lang="fa" if any('\u0600' <= ch <= '\u06FF' for ch in fields["raw_text"]) else "en",
                type_tag=("مسافر" if "مسافر" in fields["type_tags"]
                         else ("قبول_بار" if "قبول" in fields["type_tags"] else None)),
                contact_handles=fields["contact_handles"].split(";") if fields["contact_handles"] else [],
                contact_phones=fields["contact_phones"].split(";") if fields["contact_phones"] else [],
            )
            db.add(post); db.flush()

            # normalize date
            iso = (fields.get("flight_date_iso") or "").strip()
            iso_date = None
            if len(iso) == 10:
                try:
                    y, mn, dd = map(int, iso.split("-"))
                    iso_date = date(y, mn, dd)
                except Exception:
                    pass

            trip = Trip(
                post_id=post.id,
                origin_city=fields["origin"],
                origin_area=fields["origin_area"],
                origin_code=to_code(fields["origin"]) or to_code(fields["origin_area"]),
                destination_city=fields["destination"],
                destination_area=fields["destination_area"],
                destination_code=to_code(fields["destination"]) or to_code(fields["destination_area"]),
                airline=fields["airline"],
                flight_date_text=fields["flight_date_text"],
                flight_time_text=fields["flight_time_text"],
                flight_date=iso_date,
            )
            db.add(trip)

            added += 1
            if m.id > max_id: max_id = m.id
            if added % 50 == 0:
                db.commit()
                print(f"Committed {added} posts... last_id={max_id}")

        db.commit()
        state[str(entity.id)] = max_id
        _save_state(state)
        print(f"✅ Done. Added {added} new posts. last_id={max_id}")

    finally:
        db.close()
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
