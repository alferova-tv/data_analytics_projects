"""Чистка выгрузки: data/raw_api.parquet -> data/posts.parquet.

raw_api.parquet не меняется. Шаги:
1. date_msc (время публикации по Москве); реакции: reactions_total (бесплатные), reactions_neg
   (отрицательные из них, список NEGATIVE), paid_stars (платные звёзды).
2. Альбомы (общий grouped_id) склеиваются в один пост. Метрики берутся с сообщения альбома,
   на котором висят реакции и комментарии, текст — с подписи.
3. Сервисные сообщения (m.action: закреп, смена фото и т.п.) отброшены ещё при выгрузке
   в 01_fetch.py; здесь проверяется, что их не осталось.
4. Флаг comments_paid: период, когда комментарии были платными (за звёзды).
   Посты с выключенными комментариями остаются, у них replies = NaN.
5. Тип рекламы ad_kind (None — не реклама). Рекламные посты получают content_type = "ad".
6. Тип содержания content_type: ad, own_products, video, reflection, other.
   Адреса ссылок берутся из data/links.parquet (01b_fetch_links.py): ссылки в тексте,
   ссылки под словами, превью и кнопки.

Запуск: .venv/bin/python scripts/02_clean.py
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw_api.parquet"
LINKS = ROOT / "data" / "links.parquet"
OUT = ROOT / "data" / "posts.parquet"

# Комментарии стали платными постом-объявлением и снова бесплатными другим постом.
# Первый пост уже с платными комментариями, второй — с бесплатными. Первый ищется по началу текста.
PAID_FROM = "Зай, молчание - золото!"
PAID_UNTIL = "Зая, я сделал каменты бесплатными. Веди себя хорошо!"

# Реклама. Автор помечает её хэштегом #нативнаяинтеграция (бывают опечатки: «интегрция»,
# «интгерация») и/или юридической маркировкой «Реклама. ООО … ИНН … erid …».
# Отдельный формат — авторский пост с рекламным блоком «Рекламная супер-ссылка (… erid …)»
# в конце; после окончания размещения блок заменяется на «Рекламная супер-ссылка была тут».
AD_HASHTAG = r"(?i)#нативн"
AD_LEGAL = r"(?i)\berid\W{0,3}[a-z0-9]{6,}|ИНН\W{0,3}\d{10}"  # ИНН с учётом регистра — иначе ловит «истинную»
AD_SUPERLINK = r"(?i)рекламная супер-ссылка"
# Иногда маркировка есть только в адресе ссылки под словом (…?erid=…), в тексте её нет.
AD_LINK_ERID = r"(?i)[?&]erid\W{0,2}[a-z0-9]{6,}"
# Реклама Альфа-Банка чаще всего промаркирована только в адресе ссылки (см. AD_LINK_ERID). Посты без маркировки
# узнаются по названию продукта банка и ссылке на сайт банка (alfa.me, alfabank.ru) или упоминанию @alfabank.
AD_ALFA = r"Альфа-(?:Банк|Инвест|Карт)|alfabank"
ALFA_URL = r"^(?:alfa\.me|alfabank\.ru)/"
NOT_AD = {9694}  # пост о рекламе («всю рекламу я всегда размещаю с хэштегом …»), сам не реклама
AD_MANUAL = {9331}  # розыгрыш «Cofix x Артемий Лебедев» без маркировки и хэштега

# Типы содержания (по наблюдению владелицы за каналом). Порядок проверки: реклама, свои продукты, видео, размышления.
# Шаблоны ниже применяются к адресу без https:// и www.
# Свои продукты: сайты Студии (artlebedev.ru с поддоменами store, magazinus, bibliotekus и т.д., короткие artl.ru),
# билеты на его выступления и туры с Инсайдерсами (Мадагаскар, Мексика, ЮАР).
# Слово lebedev в адресе само по себе не подходит, так как оно стоит в метках чужих рекламных ссылок
# (utm_medium=lebedev, start=tg_tg-traffic_lebedev).
OWN_URL = (r"(?i)^(?:[\w-]+\.)*artlebedev\.ru|^artl\.ru/|^insidersontour\.com|^t\.me/insiderstour_bot"
           r"|^lotusarenatickets\.com/lebedev|^stillstandup\.com/\S*artemii-lebedev")
OWN_TOURS = r"(?i)инсайдерс|insidersontour|приглашение для своих|мадагаскар"
# Видео с его участием: ссылка на видеохостинг. Обращение «Зай» не требуется, так как у него десятки форм
# («Заюсь», «Заюндель», «Зааая»), а видео-посты без обращения («Видос на вечер») тоже есть.
# Ссылка на канал YouTube (youtube.com/channel/…) видео не считается.
VIDEO_URL = (r"(?i)^(?:vkvideo\.ru|cloud\.mail\.ru|youtube\.com/(?:watch|shorts|live)|youtu\.be|rutube\.ru/video|dzen\.ru/video"
             r"|vk\.(?:com|ru)/(?:video|podcast)|vk\.com/\S*[?&]z=video)")
# Ссылки на собственные каналы (Макс, ВК, Telegram, Пикабу, TikTok). С 18 марта по 28 мая 2026 у 31 размышления
# в конце стоит подпись «Мой канал в Максе легко запомнить - https://max.ru/temalebedev» (например, id 10705),
# поэтому при проверке «без ссылок» такие ссылки не считаются.
OWN_CHANNEL_URL = r"(?i)^(?:max\.ru/|t\.me/|vk\.com/|pikabu\.ru/@|tiktok\.com/@)temalebedev\b"
# Тип, выбранный владелицей после просмотра поста. Пост 9575 «Еда как якорь воспоминаний» — размышление
# со ссылкой на его блог; остальные посты со ссылками на блог (tema.ru, tema.livejournal.com) остаются в other.
CONTENT_MANUAL = {9575: "reflection"}
TITLE = r"^[^\n]{1,100}\n\s*\n\S"                                      # первая строка, пустая строка, текст

# Отрицательные реакции — оценка поста. Грусть и испуг (😢 😭 😱 😨) относятся к содержанию, они не здесь;
# спорные (🤔 🤷 🍌 🥴 🗿 🤨 🙈 😐 💔) тоже считаются неотрицательными.
NEGATIVE = {"👎", "💩", "🤡", "🤮", "🥱", "😴", "🖕", "🤬", "😡"}

df = pd.read_parquet(RAW)
n_raw = len(df)

# 1. Новые столбцы
df["date_msc"] = df["date_utc"].dt.tz_convert("Europe/Moscow")
reactions = df["reactions"].map(json.loads)
df["paid_stars"] = reactions.map(lambda d: d.get("paid_star", 0))
df["reactions_total"] = reactions.map(lambda d: sum(v for k, v in d.items() if k != "paid_star"))
df["reactions_neg"] = reactions.map(lambda d: sum(v for k, v in d.items() if k in NEGATIVE))
assert reactions.map(lambda d: set(d) - {"paid_star"}).map(lambda k: not any(x.startswith("custom_") for x in k)).all(), \
    "есть кастомные эмодзи, их нужно разметить"
has_reactions = df["reactions_total"] + df["paid_stars"] > 0

# 2. Склейка альбомов
album = df[df["grouped_id"].notna()].copy()
album["album_size"] = album.groupby("grouped_id")["id"].transform("size")
album["album_has_video"] = album.groupby("grouped_id")["media"].transform(lambda m: (m == "video").any())
# Метрики висят на первом сообщении альбома, подпись обычно там же, но не всегда
# (в альбоме 9098–9103 подпись на 9101). Метрики берём с сообщения с реакциями, текст — с подписи.
assert has_reactions[album.index].groupby(album["grouped_id"]).sum().eq(1).all(), \
    "в альбоме не ровно одно сообщение с реакциями"
assert album.groupby("grouped_id")["text"].apply(lambda t: (t != "").sum()).eq(1).all(), \
    "в альбоме не ровно одна подпись"
main = album[has_reactions[album.index]].set_index("grouped_id")
caption = album[album["text"] != ""].set_index("grouped_id")
main["text"] = caption["text"]
main["n_links"] = caption["n_links"]
main = main.reset_index()
main["media"] = "album"

single = df[df["grouped_id"].isna()].copy()
single["album_size"] = 1
single["album_has_video"] = False
posts = pd.concat([single, main]).sort_values("id").reset_index(drop=True)
print(f"Сообщений {n_raw}, из них в альбомах {len(album)} ({album['grouped_id'].nunique()} альбомов) "
      f"-> постов {len(posts)}")

# 3. Сервисные сообщения: у каждого поста должны быть просмотры и содержимое
assert posts["views"].notna().all()
assert (posts["reactions_total"] > 0).all(), "есть посты без реакций"
empty = posts[(posts["text"] == "") & (posts["media"] == "text")]
print(f"Постов без текста и без распознанного медиа: {len(empty)} (id {empty['id'].tolist()}), оставлены: "
      "у них есть просмотры, реакции и комментарии")

# 4. Комментарии
off = posts[~posts["comments_enabled"]]
assert off["replies"].isna().all()
print(f"Комментарии выключены у {len(off)} постов (id {off['id'].tolist()}), replies = NaN")

paid_from = posts.loc[posts["text"].str.strip().str.startswith(PAID_FROM), "id"]
paid_until = posts.loc[posts["text"].str.strip() == PAID_UNTIL, "id"]
assert len(paid_from) == 1 and len(paid_until) == 1, "не нашлись посты-объявления о платных комментариях"
posts["comments_paid"] = (posts["id"] >= paid_from.iloc[0]) & (posts["id"] < paid_until.iloc[0])
paid = posts[posts["comments_paid"]]
print(f"Платные комментарии: {paid['date_msc'].min():%Y-%m-%d %H:%M} – {paid['date_msc'].max():%Y-%m-%d %H:%M} МСК, "
      f"{len(paid)} постов (id {paid_from.iloc[0]}–{paid['id'].max()})")

# Ссылки. В альбоме ссылки висят на сообщении с подписью, его id переводится в id поста.
links = pd.read_parquet(LINKS)
assert links["id"].isin(df["id"]).all()
post_of_group = main.set_index("grouped_id")["id"]
links["post_id"] = links["id"].map(df.set_index("id")["grouped_id"]).map(post_of_group).fillna(links["id"]).astype(int)
links["addr"] = links["url"].str.replace(r"(?i)^(?:https?://)?(?:www\.)?", "", regex=True)
links["own_channel"] = links["addr"].str.contains(OWN_CHANNEL_URL, regex=True)
in_text = links[links["source"].isin(["url", "text_url"])]   # ссылки из текста, их и считает n_links
n_found = in_text.groupby("post_id").size().reindex(posts["id"], fill_value=0).to_numpy()
assert (n_found == posts["n_links"]).all(), "число ссылок в links.parquet не совпадает с n_links"
print(f"Ссылки: {len(links)} адресов у {links['post_id'].nunique()} постов; у всех {(posts['n_links'] > 0).sum()} постов "
      f"с n_links > 0 найдено столько же ссылок в тексте, сколько в n_links")
link_posts = lambda pattern: posts["id"].isin(links.loc[links["addr"].str.contains(pattern, regex=True), "post_id"])

# 5. Реклама
superlink = posts["text"].str.contains(AD_SUPERLINK, regex=True)
native = (posts["text"].str.contains(AD_HASHTAG, regex=True) | posts["text"].str.contains(AD_LEGAL, regex=True)
          | link_posts(AD_LINK_ERID))
posts["ad_kind"] = None
posts.loc[native & ~superlink, "ad_kind"] = "native"        # весь пост рекламный
posts.loc[superlink, "ad_kind"] = "superlink"                # авторский пост с рекламным блоком
posts.loc[posts["id"].isin(AD_MANUAL), "ad_kind"] = "native"
alfa = posts["text"].str.contains(AD_ALFA, regex=True) & (link_posts(ALFA_URL) | posts["text"].str.contains("@alfabank"))
posts.loc[alfa & posts["ad_kind"].isna(), "ad_kind"] = "unmarked"   # Альфа-Банк без маркировки
posts.loc[posts["id"].isin(NOT_AD), "ad_kind"] = None
print(f"Реклама: {posts['ad_kind'].notna().sum()} постов, по типам: {posts['ad_kind'].value_counts().to_dict()}")

# 6. Тип содержания
n_other_links = in_text[~in_text["own_channel"]].groupby("post_id").size().reindex(posts["id"], fill_value=0).to_numpy()
own = link_posts(OWN_URL) | posts["text"].str.contains(OWN_TOURS, regex=True)
video = link_posts(VIDEO_URL)
# Пересланный пост написан не в канале, поэтому размышлением не считается и уходит в «прочее»
reflection = (posts["text"].str.contains(TITLE, regex=True) & (n_other_links == 0)
              & posts["media"].isin(["text", "photo"]) & ~posts["is_forward"])
posts["content_type"] = "other"
posts.loc[reflection, "content_type"] = "reflection"
posts.loc[video, "content_type"] = "video"
posts.loc[own, "content_type"] = "own_products"
posts.loc[posts["id"].isin(CONTENT_MANUAL), "content_type"] = posts["id"].map(CONTENT_MANUAL)
posts.loc[posts["ad_kind"].notna(), "content_type"] = "ad"
print(f"Типы содержания: {posts['content_type'].value_counts().to_dict()}")

posts.to_parquet(OUT, index=False)
print(f"Сохранено {len(posts)} постов в {OUT.relative_to(ROOT)}")
