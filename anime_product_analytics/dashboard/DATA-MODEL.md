# Data Model

> Managed by tableau-dashboard-plugin (tableau-data). See CONTRACT.md before hand-editing.

## Acquisition

- tier: csv (provided in data/)
- Each CSV under `data/` is one data source (CONTRACT.md §3.2). Documented field names below must match the CSV headers exactly so **Replace Data Source** can swap in live data later.
- Обе таблицы выгружает `src/export_tableau.py` основного проекта. Разрез: TV-сериалы, `status == 'Finished Airing'`, `start_year >= 2020`, `started >= 1000`.
- Связь между источниками - по `mal_id` (relationship), иначе фильтр по `start_year` не подействует на кривую удержания.

## Data source: `tableau_episode_retention.csv`

- rows profiled: 200
- Всего 8 208 строк: 684 сериала ровно на 12 серий × 12 серий. Гранулярность - сериал × серия.

| Field | Type | Role | Sample values | Description |
|-------|------|------|---------------|-------------|
| mal_id | integer | Dimension | 32455, 35252, 35335 | ID тайтла на MyAnimeList, ключ связи с `tableau_titles.csv`. Не агрегировать. |
| episode | integer | Dimension | 1 | Номер серии, 1–12. Ось X кривой удержания, использовать как дискретное измерение. |
| retention | real | Measure | 0.9082, 0.9058, 0.8685 | Доля стартовавших зрителей, дошедших до этой серии (0–1). На графике - `MEDIAN`, формат в %. 36 пустых значений у 23 сериалов на сериях 5–11; серии 1–3 и 12 заполнены у всех 684. |
| title | string | Dimension | Gekidol: Actidol Project, Hatena☆Illusion, Musashino! | Название сериала на MAL (романизация). Для tooltip. |
| segment | string | Dimension | Остальные, Нишевые любимчики, Надёжный просмотр | Сегмент тайтла по связке «смотрят / привязываются»: Флагманы, Надёжный просмотр, Нишевые любимчики, Остальные. Цвет линий на кривой. |
| source | string | Dimension | Original, Light novel, Game | Первоисточник (манга, ранобэ, оригинал и т д). Дублируется из `tableau_titles.csv`. |
| title_type | string | Dimension | Дебют, Продолжение | Дебют или Продолжение (≥ 50% стартовавших пришли из предыдущего сезона). Дублируется из `tableau_titles.csv`. |

## Data source: `tableau_titles.csv`

- rows profiled: 200
- Всего 1 101 строка, одна строка - один сериал. Основной источник для KPI, scatter и разреза по первоисточникам.

| Field | Type | Role | Sample values | Description |
|-------|------|------|---------------|-------------|
| mal_id | integer | Dimension | 58985, 60425, 41380 | ID тайтла на MyAnimeList, первичный ключ. `COUNTD([mal_id])` - KPI «сериалов в разрезе». Не агрегировать как число. |
| title | string | Dimension | 0-saiji Start Dash Monogatari, 0-saiji Start Dash Monogatari Season 2, 100-man no Inochi no Ue ni Ore wa Tatteiru | Название сериала на MAL (романизация). Подпись точек на scatter и tooltip. |
| start_year | integer | Dimension | 2024, 2025, 2020 | Год выхода первой серии, 2020–2025. Фильтр дашборда, не суммировать. |
| source | string | Dimension | Manga, Web manga, Original | Первоисточник, 14 значений. Ось Y графика «первоисточник × удержание» и фильтр. У мелких категорий (`Book` - 1 сериал, `Web novel` - 2, `Music` - 6) медиана шумная, рядом нужен счётчик сериалов. |
| main_genre | string | Dimension | Adventure, Action, Comedy | Первый жанр из списка жанров MAL, «Не указан» если пусто. На дашборде пока не используется, годится для tooltip. |
| episodes | integer | Dimension | 12, 13, 24 | Число серий в сезоне. Сериалы ровно на 12 серий - те самые 684 из файла удержания. |
| members | integer | Measure | 12263, 4376, 324016 | Сколько пользователей MAL добавили тайтл в список в любом статусе, включая «plan to watch». Общая известность, знаменатель `favorites_rate`. |
| started | integer | Measure | 6660, 2257, 267488 | Сколько реально начали смотреть: `watching + completed + dropped + on_hold`. Размер точки на scatter, порог разреза ≥ 1000. |
| audience_quartile | string | Dimension | Q1 малые, Q4 крупные, Q3 | Квартиль по `started`: Q1 малые, Q2, Q3, Q4 крупные, примерно по 275 сериалов. Посчитан по всем 1 101 и при фильтрации не пересчитывается. Переключатель на графике первоисточников. |
| conversion_to_start | real | Measure | 0.5426, 0.5142, 0.8254 | `started / total` - доля тех, кто дошёл до просмотра из всех добавивших. Ось X scatter, формат в %. |
| completion_rate | real | Measure | 0.2262, 0.3249, 0.6478 | `completed / total` - доля досмотревших до конца от всех добавивших. Ось Y scatter, формат в %. |
| favorites_rate | real | Measure | 0.002, 0.0023, 0.0022 | `favorites / members` - доля добавивших в избранное, прокси привязанности к тайтлу. Входит в сегментацию. |
| ep3_retention | real | Measure | 0.6425, 0.7967, 0.9 | Доля стартовавших, дошедших до 3-й серии. KPI считаем как `MEDIAN` = 84,2% по 1 097 сериалам (у 4 пусто). Это не 84,4% с кривой - там только сериалы ровно на 12 серий. |
| score_combined | real | Measure | 0.1035, 0.1493, 0.6379 | Средний перцентиль по трём метрикам (`conversion_to_start`, `completion_rate`, `favorites_rate`), 0–1. Основа сегментации, для сортировки списков лучших тайтлов. |
| segment | string | Dimension | Остальные, Надёжный просмотр, Нишевые любимчики | Сегмент по перцентилям: Флагманы 165, Надёжный просмотр 188, Нишевые любимчики 203, Остальные 545. Цвет на scatter и кривой, палитра одинаковая на обоих листах. |
| title_type | string | Dimension | Дебют, Продолжение | Дебют 814 / Продолжение 287. Продолжение - если ≥ 50% стартовавших досмотрели предыдущий сезон. Фильтр и KPI «доля продолжений» = 26%. |
