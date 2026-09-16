"""Выгрузка метрик для дашборда в Tableau Public.

Повторяет расчёты из notebooks/02_EDA&metrics.ipynb (разрез: TV, Finished Airing,
start_year >= 2020, started >= 1000) и сохраняет плоские csv в data/processed/.

Запуск из корня проекта:
    .venv/bin/python src/export_tableau.py
"""
import ast
import re
from collections import defaultdict
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW = PROJECT_ROOT / 'data' / 'raw'
OUT = PROJECT_ROOT / 'data' / 'processed'

KEY_METRICS = ['conversion_to_start', 'completion_rate', 'favorites_rate']
STARTED_STATUSES = ['watching', 'completed', 'dropped', 'on_hold']
SEGMENT_NAMES = {
    'флагманы': 'Флагманы',
    'надёжный просмотр': 'Надёжный просмотр',
    'нишевые': 'Нишевые любимчики',
    'остальные': 'Остальные',
}


def to_list(s):
    """'["Action", "Comedy"]' -> ['Action', 'Comedy'], пропуск/битая строка -> []"""
    if pd.isna(s):
        return []
    try:
        val = ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return []
    return list(val) if isinstance(val, (list, tuple)) else [val]


def safe_div(a, b):
    return a / b.replace(0, np.nan)


def load_anime():
    details = pd.read_csv(RAW / 'details.csv')
    stats = pd.read_csv(RAW / 'stats.csv')
    details['start_date'] = pd.to_datetime(details['start_date'], errors='coerce')
    details['start_year'] = details['start_date'].dt.year
    anime = details.merge(stats, on='mal_id')
    anime['genres_list'] = anime['genres'].map(to_list)
    return anime


def build_winners(anime):
    finished = anime[anime['status'] == 'Finished Airing'].copy()
    finished['started'] = finished[STARTED_STATUSES].sum(axis=1)
    finished['conversion_to_start'] = safe_div(finished['started'], finished['total'])
    finished['completion_rate'] = safe_div(finished['completed'], finished['total'])
    finished['favorites_rate'] = safe_div(finished['favorites'], finished['members'])

    winners = finished[(finished['type'] == 'TV')
                       & (finished['start_year'] >= 2020)
                       & (finished['started'] >= 1000)].copy()

    for m in KEY_METRICS:
        winners[f'{m}_pct'] = winners[m].rank(pct=True)
    winners['score_combined'] = winners[[f'{m}_pct' for m in KEY_METRICS]].mean(axis=1)
    winners['watch_pct'] = winners[['conversion_to_start_pct', 'completion_rate_pct']].mean(axis=1)
    winners['attach_pct'] = winners['favorites_rate_pct']

    hi = 2 / 3
    watch = winners['watch_pct'] >= hi
    attach = winners['attach_pct'] >= hi
    winners['segment'] = np.select(
        [watch & attach, watch & ~attach, attach & ~watch],
        ['флагманы', 'надёжный просмотр', 'нишевые'],
        default='остальные',
    )
    return winners


def episode_survival(con, winners):
    """Доля стартовавших, дошедших до серии k, по каждому тайтлу разреза."""
    con.register('winner_ids', winners[['mal_id']])
    depth = con.sql(f"""
        SELECT anime_id, episodes_watched AS eps, count(*) AS n
        FROM ratings_clean
        WHERE anime_id IN (SELECT mal_id FROM winner_ids)
          AND status IN ({', '.join(f"'{s}'" for s in STARTED_STATUSES)})
        GROUP BY 1, 2
    """).df().dropna(subset=['eps'])
    depth['eps'] = depth['eps'].astype(int)

    starters = depth.groupby('anime_id')['n'].sum()
    return pd.DataFrame([
        (g.set_index('eps')['n'].sort_index()[::-1].cumsum()[::-1] / starters[aid]).rename(aid)
        for aid, g in depth.groupby('anime_id')
    ]).sort_index(axis=1)


def norm(t):
    return re.sub(r'\s+', ' ', re.sub(r'[^0-9a-z∬ ]+', ' ', str(t).lower())).strip()


def sequel_ids(con, anime, winners):
    """Продолжения из разреза: предшественник по префиксу названия, from_prequel >= 0.5."""
    tv = anime[anime['type'] == 'TV'][['mal_id', 'title', 'start_date']].dropna(subset=['start_date']).copy()
    tv['key'] = tv['title'].map(norm)
    index = defaultdict(list)
    for r in tv.itertuples():
        index[r.key].append((r.mal_id, r.start_date))

    rows = []
    for r in tv.itertuples():
        words = r.key.split()
        for L in range(len(words), 0, -1):
            cands = [c for c in index[' '.join(words[:L])] if c[0] != r.mal_id and c[1] < r.start_date]
            if cands:
                rows.append({'prequel_id': max(cands, key=lambda c: c[1])[0], 'sequel_id': r.mal_id})
                break
    pairs = pd.DataFrame(rows)
    pairs = pairs[pairs['sequel_id'].isin(winners['mal_id'])]
    con.register('pairs', pairs)

    statuses = ', '.join(f"'{s}'" for s in STARTED_STATUSES)
    carry = con.sql(f"""
        WITH u AS (
            SELECT username, anime_id, status FROM ratings_clean
            WHERE anime_id IN (SELECT prequel_id FROM pairs UNION SELECT sequel_id FROM pairs)
              AND status IN ({statuses})
        ),
        base AS (
            SELECT anime_id AS sequel_id, count(*) AS started_total FROM u
            WHERE anime_id IN (SELECT sequel_id FROM pairs) GROUP BY 1
        )
        SELECT p.prequel_id, p.sequel_id, count(s.username) AS started_sequel, any_value(b.started_total) AS started_total
        FROM pairs p
        JOIN u AS pr ON pr.anime_id = p.prequel_id AND pr.status = 'completed'
        LEFT JOIN u AS s ON s.anime_id = p.sequel_id AND s.username = pr.username
        JOIN base b ON b.sequel_id = p.sequel_id
        GROUP BY 1, 2
    """).df()
    carry['from_prequel'] = carry['started_sequel'] / carry['started_total']
    return set(carry.loc[carry['from_prequel'] >= 0.5, 'sequel_id'])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    anime = load_anime()
    winners = build_winners(anime)

    con = duckdb.connect()
    con.execute('SET enable_progress_bar=false')
    con.sql(f"CREATE VIEW ratings AS SELECT * FROM read_parquet('{(RAW / 'ratings.parquet').as_posix()}')")
    con.register('anime_meta', anime[['mal_id']])
    con.sql("""
        CREATE VIEW ratings_clean AS
        SELECT r.username, r.anime_id, r.status,
               CASE WHEN r.num_watched_episodes <= 3000 THEN r.num_watched_episodes END AS episodes_watched
        FROM ratings r
        JOIN anime_meta a ON r.anime_id = a.mal_id
        WHERE r.status <> 'unknown' AND r.status <> ''
    """)

    surv = episode_survival(con, winners)
    winners['ep3_retention'] = surv[3].reindex(winners['mal_id']).values
    winners['is_sequel'] = winners['mal_id'].isin(sequel_ids(con, anime, winners))

    titles = winners.copy()   # winners уже содержит все поля details/stats
    titles['main_genre'] = titles['genres_list'].map(lambda g: g[0] if g else 'Не указан')
    titles['audience_quartile'] = pd.qcut(titles['started'], 4, labels=['Q1 малые', 'Q2', 'Q3', 'Q4 крупные'])
    titles['segment'] = titles['segment'].map(SEGMENT_NAMES)
    titles['title_type'] = np.where(titles['is_sequel'], 'Продолжение', 'Дебют')
    for col in ['start_year', 'episodes', 'members', 'started']:   # в details это float из-за пропусков, Tableau покажет «2024.0»
        titles[col] = titles[col].astype('Int64')

    cols = ['mal_id', 'title', 'start_year', 'source', 'main_genre', 'episodes', 'members', 'started',
            'audience_quartile', 'conversion_to_start', 'completion_rate', 'favorites_rate',
            'ep3_retention', 'score_combined', 'segment', 'title_type']
    titles[cols].round(4).to_csv(OUT / 'tableau_titles.csv', index=False)

    # кривая удержания: только сериалы ровно на 12 серий, длинный формат для line chart
    twelve = titles.loc[titles['episodes'] == 12, ['mal_id', 'title', 'segment', 'source', 'title_type']]
    curve = (surv.loc[surv.index.intersection(twelve['mal_id']), list(range(1, 13))]
                 .rename_axis('mal_id').reset_index()
                 .melt(id_vars='mal_id', var_name='episode', value_name='retention')
                 .merge(twelve, on='mal_id'))
    curve.round(4).to_csv(OUT / 'tableau_episode_retention.csv', index=False)

    print(f'tableau_titles.csv: {len(titles)} тайтлов')
    print(titles['segment'].value_counts().to_string())
    print(f'tableau_episode_retention.csv: {curve["mal_id"].nunique()} тайтлов x 12 серий')


if __name__ == '__main__':
    main()
