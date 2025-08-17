import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("✅ Logged in. Copy the line below into your .env as TG_SESSION_STRING=")
    print(client.session.save())
