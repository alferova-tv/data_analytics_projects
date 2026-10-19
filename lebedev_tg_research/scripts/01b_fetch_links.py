"""Дозагрузка адресов ссылок для постов из data/raw_api.parquet.

01_fetch.py сохранил только число ссылок (n_links). Если ссылка спрятана под словом,
её адреса нет в тексте поста. Этот скрипт по тем же id забирает адреса всех ссылок:
- url        — адрес, написанный в тексте;
- text_url   — ссылка, спрятанная под словом;
- preview    — адрес превью страницы под постом;
- button     — кнопка-ссылка под постом.

Что делает:
1. Входит в аккаунт: спрашивает номер, код из Telegram и облачный пароль, если он включён.
2. Читает ТОЛЬКО канал @temalebedev и только сообщения с id из raw_api.parquet.
3. Сохраняет data/links.parquet: одна строка — одна ссылка (id, source, url). raw_api.parquet не меняется.
4. Завершает сессию (log_out): файл tg.session удаляется, вход в списке устройств пропадает.

Запуск в обычном терминале:
    cd lebedev_tg_research && .venv/bin/python scripts/01b_fetch_links.py
"""
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl

CHANNEL = "temalebedev"
BATCH = 100  # столько сообщений Telegram отдаёт за один запрос по id

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
RAW = ROOT / "data" / "raw_api.parquet"
OUT = ROOT / "data" / "links.parquet"


def links(m) -> list[tuple[str, str]]:
    out = []
    # get_entities_text сам пересчитывает смещения (Telegram считает их в UTF-16)
    for e, text in m.get_entities_text():
        if isinstance(e, MessageEntityTextUrl):
            out.append(("text_url", e.url))
        elif isinstance(e, MessageEntityUrl):
            out.append(("url", text))
    if m.web_preview and getattr(m.web_preview, "url", None):
        out.append(("preview", m.web_preview.url))
    for row in (m.buttons or []):
        for b in row:
            if b.url:  # у кнопок другого типа url = None
                out.append(("button", b.url))
    return out


ids = pd.read_parquet(RAW, columns=["id"])["id"].tolist()

client = TelegramClient(str(ROOT / "tg"), int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"])
client.start()
try:
    channel = client.get_entity(CHANNEL)
    assert getattr(channel, "broadcast", False) and channel.username.lower() == CHANNEL, "это не тот канал"
    print(f"Канал: {channel.title}, сообщений для проверки: {len(ids)}")

    rows, missing = [], []
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        for msg_id, m in zip(chunk, client.get_messages(channel, ids=chunk)):
            if m is None:  # сообщение удалено после выгрузки
                missing.append(msg_id)
                continue
            rows += [{"id": m.id, "source": s, "url": u} for s, u in links(m)]
        print(f"  {min(i + BATCH, len(ids))} / {len(ids)}", flush=True)

    df = pd.DataFrame(rows, columns=["id", "source", "url"])
    df.to_parquet(OUT, index=False)
    print(f"Сохранено {len(df)} ссылок из {df['id'].nunique()} сообщений в {OUT}")
    print(f"По типам: {df['source'].value_counts().to_dict()}")
    if missing:
        print(f"Удалены после выгрузки: {len(missing)} сообщений (id {missing[:20]}{' …' if len(missing) > 20 else ''})")
finally:
    client.log_out()
    print("Сессия завершена, tg.session удалён.")
