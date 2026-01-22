import os
import re
import time
import sqlite3
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional


# ====== CONFIG ======
FEEDS = [
    "https://www.melhoresdestinos.com.br/feed/rss",
    "https://www.tudodeviagem.com/category/promocao-de-passagens/feed/",
]

KEYWORDS_ANY = [
    "passagens", "promo", "promoção", "voos", "aéreas", "aereo", "aéreo", "baratas", "oferta"
]

# ⚠️ NÃO vamos mais exigir Fortaleza explicitamente
KEYWORDS_ORIGIN = []

# Destinos de interesse (mantemos)
KEYWORDS_DEST = [
    "eua", "estados unidos",
    "orlando", "miami", "boston",
    "nova york", "los angeles",
    "internacional"
]


POLL_INTERVAL_SEC = 900  # 15 min

DB_PATH = "rss_seen.db"

# Horário do digest (Fortaleza = UTC-3)
FORTALEZA_TZ = timezone(timedelta(hours=-3))
DIGEST_HOUR = 20   # 20:00
DIGEST_MINUTE = 0  # 20:00


# ====== TELEGRAM ======
def telegram_send(text: str) -> None:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        raise RuntimeError("Faltou TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID.")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()


# ====== DB ======
def db_init() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen (
            id TEXT PRIMARY KEY,
            first_seen_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS digest_items (
            entry_id TEXT PRIMARY KEY,
            date_key TEXT NOT NULL,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            source TEXT NOT NULL,
            added_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS digest_sent (
            date_key TEXT PRIMARY KEY,
            sent_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def already_seen(conn: sqlite3.Connection, entry_id: str) -> bool:
    cur = conn.execute("SELECT 1 FROM seen WHERE id = ?", (entry_id,))
    return cur.fetchone() is not None


def mark_seen(conn: sqlite3.Connection, entry_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO seen (id, first_seen_at) VALUES (?, ?)",
        (entry_id, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def add_digest_item(conn: sqlite3.Connection, date_key: str, entry_id: str, title: str, link: str, source: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO digest_items (entry_id, date_key, title, link, source, added_at) VALUES (?, ?, ?, ?, ?, ?)",
        (entry_id, date_key, title, link, source, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def digest_already_sent(conn: sqlite3.Connection, date_key: str) -> bool:
    cur = conn.execute("SELECT 1 FROM digest_sent WHERE date_key = ?", (date_key,))
    return cur.fetchone() is not None


def mark_digest_sent(conn: sqlite3.Connection, date_key: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO digest_sent (date_key, sent_at) VALUES (?, ?)",
        (date_key, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def get_digest_items(conn: sqlite3.Connection, date_key: str) -> List[Dict[str, str]]:
    cur = conn.execute(
        "SELECT title, link, source FROM digest_items WHERE date_key = ? ORDER BY added_at ASC",
        (date_key,),
    )
    rows = cur.fetchall()
    return [{"title": r[0], "link": r[1], "source": r[2]} for r in rows]


# ====== FILTRO ======
def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def matches(text: str, keywords: List[str]) -> bool:
    t = normalize(text)
    return any(k.lower() in t for k in keywords)


def relevant(entry):
    title = entry.get("title", "")
    summary = entry.get("summary", "") or entry.get("description", "")
    text = f"{title}\n{summary}"

    if not matches(text, KEYWORDS_ANY):
        return False

    if KEYWORDS_DEST and not matches(text, KEYWORDS_DEST):
        return False

    return True



# ====== LOOP ======
def today_key_fortaleza() -> str:
    return datetime.now(FORTALEZA_TZ).date().isoformat()


def should_send_digest_now(conn: sqlite3.Connection) -> bool:
    now = datetime.now(FORTALEZA_TZ)
    key = now.date().isoformat()

    # Só dispara depois do horário definido
    if (now.hour, now.minute) < (DIGEST_HOUR, DIGEST_MINUTE):
        return False

    # E só 1 vez por dia
    if digest_already_sent(conn, key):
        return False

    return True


def fetch_and_store(conn: sqlite3.Connection) -> int:
    """
    Busca entradas, marca como seen e (se relevante) adiciona ao digest do dia.
    Retorna quantas entradas relevantes foram adicionadas ao digest (novas).
    """
    date_key = today_key_fortaleza()
    added = 0

    for feed_url in FEEDS:
        d = feedparser.parse(feed_url)
        entries = getattr(d, "entries", []) or []  

        for e in entries[:40]:
            entry_id = e.get("id") or e.get("link") or (e.get("title", "") + feed_url)
            if already_seen(conn, entry_id):
                continue

            mark_seen(conn, entry_id)

            if relevant(e):
                title = e.get("title", "Promoção")
                link = e.get("link", "")
                source = feed_url.split("/")[2]
                add_digest_item(conn, date_key, entry_id, title, link, source)
            added += 1

    



    return added


def send_digest(conn: sqlite3.Connection) -> None:
    date_key = today_key_fortaleza()
    items = get_digest_items(conn, date_key)

    if not items:
        msg = f"📬 <b>Resumo de promoções</b> ({date_key})\n\nNenhuma promoção relevante encontrada hoje."
        telegram_send(msg)
        mark_digest_sent(conn, date_key)
        return

    lines = [f"📬 <b>Resumo de promoções</b> ({date_key})", f"Total: {len(items)}\n"]

    # Limita para não estourar tamanho de mensagem do Telegram
    max_items = 20
    for i, it in enumerate(items[:max_items], start=1):
        lines.append(f"{i}) {it['title']}\n{it['link']}\n<i>Fonte: {it['source']}</i>\n")

    if len(items) > max_items:
        lines.append(f"… e mais {len(items) - max_items} itens (aumente o limite se quiser).")

    telegram_send("\n".join(lines))
    mark_digest_sent(conn, date_key)


def main():
    conn = db_init()
    telegram_send("✅ RSS Digest Bot ligado! Vou checar feeds e enviar 1 resumo diário no horário configurado.")

    while True:
        try:
            added = fetch_and_store(conn)
            print(f"[OK] checagem concluída. novos itens pro digest: {added}")

            if should_send_digest_now(conn):
                print("[OK] horário do digest atingido. enviando resumo…")
                send_digest(conn)
                print("[OK] digest enviado.")
        except Exception as ex:
            print("[ERRO] na checagem:", ex)

        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
