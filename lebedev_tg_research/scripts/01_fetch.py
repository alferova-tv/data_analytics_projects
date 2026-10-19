"""Выгрузка постов канала @temalebedev через Telegram API (Telethon).

Что делает:
1. Входит в аккаунт: спрашивает номер, код из Telegram и облачный пароль, если он включён.
2. Читает ТОЛЬКО канал @temalebedev. Список чатов и переписки не запрашиваются.
3. Сохраняет посты с 2024-09-01 в data/raw_api.parquet.
4. Завершает сессию (log_out): файл tg.session удаляется, вход в списке устройств пропадает.

Запуск в обычном терминале:
    cd lebedev_tg_research && .venv/bin/python scripts/01_fetch.py
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.tl.types import ReactionCustomEmoji, ReactionEmoji, ReactionPaid

CHANNEL = "temalebedev"
SINCE = datetime(2024, 9, 1, tzinfo=timezone.utc)

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
OUT = ROOT / "data" / "raw_api.parquet"
OUT.parent.mkdir(exist_ok=True)


def media_type(m) -> str:
    if m.poll: return "poll"
    if m.video_note: return "round"
    if m.voice: return "voice"
    if m.gif: return "gif"
    if m.video: return "video"
    if m.audio: return "audio"
    if m.sticker: return "sticker"
    if m.photo: return "photo"
    if m.document: return "document"
    if m.web_preview: return "link_preview"
    return "text"


def reactions(m) -> dict:
    out = {}
    if m.reactions:
        for r in m.reactions.results:
            if isinstance(r.reaction, ReactionEmoji):
                key = r.reaction.emoticon
            elif isinstance(r.reaction, ReactionPaid):
                key = "paid_star"
            elif isinstance(r.reaction, ReactionCustomEmoji):
                key = f"custom_{r.reaction.document_id}"
            else:
                key = type(r.reaction).__name__
            out[key] = out.get(key, 0) + r.count
    return out


client = TelegramClient(str(ROOT / "tg"), int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"])
client.start()
try:
    channel = client.get_entity(CHANNEL)
    assert getattr(channel, "broadcast", False) and channel.username.lower() == CHANNEL, "это не тот канал"
    print(f"Канал: {channel.title}")

    rows = []
    for m in client.iter_messages(channel):
        if m.date < SINCE:
            break
        if m.action:  # служебные сообщения (закреп, смена фото и т.п.)
            continue
        rows.append({
            "id": m.id,
            "date_utc": m.date,
            "text": m.message or "",
            "media": media_type(m),
            "grouped_id": m.grouped_id,
            "views": m.views,
            "forwards": m.forwards,
            "replies": m.replies.replies if m.replies else None,
            "comments_enabled": bool(m.replies and m.replies.comments),
            "reactions": json.dumps(reactions(m), ensure_ascii=False),
            "is_forward": m.fwd_from is not None,
            "edit_date_utc": m.edit_date,
            "n_links": sum(1 for e in (m.entities or []) if type(e).__name__ in ("MessageEntityUrl", "MessageEntityTextUrl")),
        })
        if len(rows) % 500 == 0:
            print(f"  {len(rows)} сообщений, дошли до {m.date:%Y-%m-%d}", flush=True)

    df = pd.DataFrame(rows)
    df.to_parquet(OUT, index=False)
    print(f"Сохранено {len(df)} сообщений за {df.date_utc.min():%Y-%m-%d} – {df.date_utc.max():%Y-%m-%d} в {OUT}")
finally:
    client.log_out()
    print("Сессия завершена, tg.session удалён.")
