# TravMatch — Telegram Flight/Delivery Posts → Search API

Make Telegram flight/delivery posts **searchable**.  
Scrape a group/channel, parse **Persian + English** posts, store in a database, and expose a simple `/search` API for your website.

---

## Repository layout (what each file does)

- **`.env`** – your real secrets/settings (see `.env.example` below).
- **`extractor.py`** – parses raw Telegram text → fields (origin, destination, date/time, airline, phones, handles). *Bilingual (FA/EN).*  
- **`city_map.py`** – maps city names/aliases (FA/EN) → IATA airport/city codes (e.g., تهران/Tehran → `THR`/`IKA`). Add more spellings here when you see them.
- **`db.py`** – creates the SQLAlchemy DB engine and session from `DATABASE_URL` in `.env`.
- **`models.py`** – SQLAlchemy models: `AppUser`, `Post`, `Trip`.
- **`ingest_telethon.py`** – **ingestor worker**: logs in to Telegram, reads group messages, runs `extractor`, writes rows to DB (`post` + `trip`). Re-run periodically.
- **`api.py`** – **FastAPI** app exposing `/search` over the DB so your site can query structured results.
- **`alert_worker.py`** *(optional)* – sends Telegram DMs for saved searches/alerts (requires a bot and extra tables; you can ignore until later).
- **`main.py`** – quick local test that prints/writes **CSV** without using the DB (good sanity check).
- **`flights.csv`** – example CSV output from `main.py`.
- **`*.session`** – your Telegram login session file (created automatically on first login). **Do not commit this.**

Data flow:

```
Telegram Group/Channel
          │
          ▼
ingest_telethon.py  ──>  Database (Post, Trip)  ──>  api.py  →  /search (JSON for your website)
          ▲
 extractor.py + city_map.py

(optional) alert_worker.py  →  Telegram DM matches to saved searches
```

---

## Requirements

- Python **3.10+**
- **Postgres** (recommended) or SQLite for quick local tests
- Telegram **API ID** & **API HASH** from https://my.telegram.org

Install packages:
```bash
pip install -r requirements.txt
```

Suggested `requirements.txt`:
```
telethon
python-dotenv
sqlalchemy
psycopg2-binary
fastapi
uvicorn
pandas
aiogram
asyncpg
```

---

## 1) Configure environment

Create `.env` (or copy from `.env.example` and fill values):

```
# Database
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/travmatch

# Telegram (get from https://my.telegram.org → API Development Tools)
TG_API_ID=123456
TG_API_HASH=your_hash_here
TG_TARGET=https://t.me/joinchat/XXXXXXXX       # or @PublicUsername

# Session (choose ONE — StringSession is best for servers/other devices)
TG_SESSION=ingest_session                       # file-based session (interactive login once)
TG_SESSION_STRING=                              # paste a StringSession here if you bootstrap it (see step 3B)

# Alerts (optional; only for alert_worker.py)
BOT_TOKEN=123456:ABC-DEF...
```

> **Tip:** For headless servers and “run anywhere”, use `TG_SESSION_STRING` so no interactive login is needed.


---

## 2) Create the database tables

### Quick Python way
Create a tiny `create_tables.py` file:

```python
from db import engine
from models import Base
Base.metadata.create_all(engine)
print("Tables created.")
```

Run:
```bash
python create_tables.py
```

*(Later you can switch to a SQL migration that adds extensions/indexes; this is fine to start.)*


---

## 3) Login to Telegram (one-time)

### A) Interactive (file session)
Run a script that creates `TelegramClient(SESSION, API_ID, API_HASH)` (e.g., `main.py` or `ingest_telethon.py`).  
It will ask for your **phone number** and then a **code** sent by Telegram. A `.session` file will be created and reused.

### B) Non‑interactive (StringSession, recommended for other devices)
Create `bootstrap_session.py`:

```python
import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("Paste the line below into your .env as TG_SESSION_STRING=")
    print(client.session.save())
```

Run:
```bash
python bootstrap_session.py
```
Copy the printed line into `.env` as:
```
TG_SESSION_STRING=1A2B3C...   # very long string
```

`ingest_telethon.py` and `main.py` will automatically prefer `TG_SESSION_STRING` if present.


---

## 4) Sanity test without DB (optional)

```bash
python main.py
```
You should see recent messages printed or written to `flights.csv`.  
This confirms your credentials, session, and parser are OK.


---

## 5) Ingest messages into the database

```bash
python ingest_telethon.py
```
- Connects to `TG_TARGET`
- Parses each new message with `extractor.py` (Persian + English)
- Saves a row to `post` and a normalized row to `trip`

Re-run this periodically (cron / Task Scheduler) to stay in sync.


---

## 6) Start the search API

```bash
uvicorn api:app --reload --port 8000
```

Try in your browser:

- `http://localhost:8000/search?origin=THR&destination=YYZ`
- `http://localhost:8000/search?q=تورنتو&limit=20`
- Add `date_from=YYYY-MM-DD&date_to=YYYY-MM-DD` to filter by date window.

Example JSON:
```json
{
  "count": 12,
  "results": [
    {
      "message_id": 514980,
      "posted_at": "2025-08-17T04:48:30Z",
      "type": "مسافر",
      "origin": "تهران", "origin_code": "THR",
      "destination": "تورنتو", "destination_code": "YYZ",
      "date": "2025-08-22",
      "time": "09:15",
      "airline": "امارات",
      "contacts": ["@user", "0912xxxxxxx"],
      "snippet": "…"
    }
  ]
}
```


---

## 7) (Optional) Alerts worker

When you add “saved searches” and a bot token, run:
```bash
python alert_worker.py
```
Schedule every 10–15 minutes to DM new matches to users.


---

## Updating parser & cities

- **Parser missed something?** Edit regex in `extractor.py`.  
- **City code empty?** Add alias in `city_map.py` (`ALIASES` dict).  
- Re-run `ingest_telethon.py` after changes.


---

## Common issues & fixes

- **I can’t type my phone number in VS Code** → Run in the **Terminal** (VS Code Terminal, cmd, or PowerShell), not the “Output” tab.  
- **Zero results in API** → Try `q=` search first; if dates weren’t parsed, results still return but date may be text. Improve `extractor.py`.  
- **No DB rows** → Check `.env` `DATABASE_URL`, ensure tables exist, and confirm `ingest_telethon.py` logs messages.  
- **Other device setup is painful** → Use `TG_SESSION_STRING` (bootstrap once locally, paste into the server’s `.env`).


---

## Handy commands

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python create_tables.py
python bootstrap_session.py   # paste TG_SESSION_STRING into .env
python ingest_telethon.py
uvicorn api:app --reload --port 8000
```

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python create_tables.py
python bootstrap_session.py   # paste TG_SESSION_STRING into .env
python ingest_telethon.py
uvicorn api:app --reload --port 8000
```

---

## Security notes

- Only scrape groups/channels you **own or have permission to archive**.
- Keep `.env`, `*.session`, and any PII **out of version control**.
- Add rate limits and audit logs before public launch.
