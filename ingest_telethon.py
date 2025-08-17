from telethon.sessions import StringSession

API_ID   = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
SESSION  = os.getenv("TG_SESSION", "ingest_session")
SESSION_STR = os.getenv("TG_SESSION_STRING")
TARGET   = os.getenv("TG_TARGET")

# ...
if SESSION_STR:
    client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
else:
    client = TelegramClient(SESSION, API_ID, API_HASH)
