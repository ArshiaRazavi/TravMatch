# ingest_telethon.py
import os, asyncio
from datetime import timezone
from telethon import TelegramClient
from extractor import extract_flight_fields
from city_map import to_code
from db import SessionLocal
from models import AppUser, Post, Trip

API_ID   = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
SESSION  = os.getenv("TG_SESSION", "ingest_session")
TARGET   = os.getenv("TG_TARGET")

async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    entity = await client.get_entity(TARGET)

    db = SessionLocal()
    try:
        async for m in client.iter_messages(entity, limit=500):
            text = (m.message or "").strip()
            if not text: continue

            # upsert user
            sender = await m.get_sender()
            u = db.query(AppUser).filter_by(telegram_id=getattr(sender, "id", None)).one_or_none()
            if not u:
                u = AppUser(
                    telegram_id=getattr(sender, "id", None),
                    username=getattr(sender, "username", None),
                    display_name=(" ".join(filter(None, [getattr(sender, "first_name", None), getattr(sender, "last_name", None)])) or None),
                )
                db.add(u); db.flush()

            # upsert post
            p = db.query(Post).filter_by(chat_id=entity.id, message_id=m.id).one_or_none()
            if p: 
                continue
            fields = extract_flight_fields(text)

            p = Post(
                chat_id=entity.id,
                message_id=m.id,
                posted_at=m.date.astimezone(timezone.utc),
                posted_by=u.id,
                raw_text=fields["raw_text"],
                lang="fa" if any('\u0600' <= ch <= '\u06FF' for ch in fields["raw_text"]) else "en",
                type_tag=("مسافر" if "مسافر" in fields["type_tags"] else ("قبول_بار" if "قبول" in fields["type_tags"] else None)),
                contact_handles=fields["contact_handles"].split(";") if fields["contact_handles"] else [],
                contact_phones=fields["contact_phones"].split(";") if fields["contact_phones"] else []
            )
            db.add(p); db.flush()

            # trip
            trip = Trip(
                post_id=p.id,
                origin_city=fields["origin"],
                origin_area=fields["origin_area"],
                origin_code=to_code(fields["origin"]) or to_code(fields["origin_area"]),
                destination_city=fields["destination"],
                destination_area=fields["destination_area"],
                destination_code=to_code(fields["destination"]) or to_code(fields["destination_area"]),
                airline=fields["airline"],
                flight_date_text=fields["flight_date_text"],
                flight_time_text=fields["flight_time_text"],
                flight_date=(None if not fields.get("flight_date_iso") else fields["flight_date_iso"])
            )
            db.add(trip)

            if m.id % 50 == 0:
                db.commit()
        db.commit()
    finally:
        db.close()
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
