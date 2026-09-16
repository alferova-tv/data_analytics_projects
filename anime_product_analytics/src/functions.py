import re
import numpy as np
import pandas as pd

def fancy_info(df, null_color="#8e44ad", null_text_color="white"):

    """
    Аналог df.info(), но с расширенным понятием null и подсветкой проблемных полей.

    В отличие от df.info(), null-подобными считаются не только NaN/None,
    но и пустые коллекции ([], (), {}), пустая строка "" и строка "[]".

    Параметры
    ----------
    df : pd.DataFrame
        Датафрейм, структуру которого нужно посмотреть.
    null_color : str, default "#8e44ad"
        Цвет фона для строк, где есть null-подобные значения (null_percent > 0).
    null_text_color : str, default "white"
        Цвет текста в подсвеченных строках.

    Возвращает
    -------
    pandas.io.formats.style.Styler
        Таблица со столбцами column, dtype, non_null_count, null_percent.
    """
    def is_null_value(x):
        if isinstance(x, (list, tuple, set, dict)):
            return len(x) == 0
        if pd.isna(x):
            return True
        if isinstance(x, str) and x.strip() in ("", "[]"):
            return True
        return False

    null_mask = df.apply(lambda col: col.map(is_null_value))
    null_count = null_mask.sum()
    null_percent = (null_count / len(df) * 100).round(2)

    info_df = pd.DataFrame({
        "column": df.columns,
        "dtype": df.dtypes.astype(str).values,
        "non_null_count": (len(df) - null_count).values,
        "null_percent": null_percent.values,
    })

    def highlight(row):
        style = f"background-color: {null_color}; color: {null_text_color}"
        return [style if row["null_percent"] > 0 else "" for _ in row]

    return info_df.style.apply(highlight, axis=1).format({"null_percent": "{:.2f}"})

"""
Детектор аномалий для табличных данных MAL (details / stats).

Проверяем три вещи:

1. Какие данные содержит столбец. id, rank, percentage, year, score и counter имеют разные
   допустимые диапазоны. Проверять счётчик и идентификатор одним правилом
   бессмысленно. Например в id значение 255 встречается ровно один раз, потому что
   так устроены id, а не потому что это заглушка.

2. Спайк частоты. Настоящая заглушка / переполнение — это локальный пик
   частоты там, где соседние значения пусты.
   Значение 255 в скошенном счётчике пиком не является: соседи 250, 251, 260
   встречаются примерно с той же частотой, это просто хвост распределения.

3. Согласованность между столбцами. Сумма компонент должна давать total, 
   сумма процентов — 100, взвешенное среднее голосов — score. 
   Расхождение здесь гарантированно означает битые данные,
   а не особенность распределения.

IQR намеренно не используется как признак аномалии: на лог-нормальных
счётчиках правило Тьюки даже с k=3 объявляет выбросом 12-16% наблюдений,
то есть описывает форму распределения, а не ошибки. Вместо него в отчёте
есть справочная колонка tail (max / p99).

Использование
-------------
    from functions import detect_anomaly, check_consistency

    detect_anomaly(details)                 # Styler для ноутбука
    detect_anomaly(stats)
    check_consistency(details, stats)       # кросс-проверки

    # если роль определилась неверно
    detect_anomaly(df, roles={'episodes': 'count'})

    # сырой датафрейм вместо Styler — для дальнейшей обработки
    rep = detect_anomaly(details, return_raw=True)
    rep[rep.severity == 'hard']
"""

# Битовые пределы и "круглые" заглушки. Используются только как проверка
# максимума в столбце, а не как список запрещённых значений.
CLIP_LIMITS = {
    255, 256, 511, 512, 1023, 1024, 4095, 4096,
    32767, 32768, 65535, 65536, 131071,
    2147483647, 2147483648, 4294967295,
    9999, 99999, 999999, 9999999,
}


# --------------------------------------------------------------------------
# роли столбцов
# --------------------------------------------------------------------------

def infer_role(name: str) -> str:
    """Определяет роль по имени. Роль задаёт набор проверок."""
    n = name.lower()
    if n == 'id' or n.endswith('_id') or n.startswith('id_'):
        return 'id'
    if 'percent' in n or n.endswith('_pct'):
        return 'percentage'
    if n in ('rank', 'ranking', 'popularity'):
        return 'rank'
    if 'year' in n:
        return 'year'
    if n == 'score' or re.fullmatch(r'score_\d+', n):
        return 'score'
    return 'count'


ROLE_RANGE = {
    'id':          (1, None),
    'rank':        (1, None),
    'percentage':  (0, 100),
    'score':       (0, 10),
    'year':        (1900, 2100),
    'count':       (0, None),
}


# --------------------------------------------------------------------------
# спайк-тест: поиск локальных пиков частоты
# --------------------------------------------------------------------------

def spike_candidates(s: pd.Series, min_count=5, half=8, ratio_thr=10.0,
                     sparse_thr=0.5, min_unique=20):
    """
    Ищет значения, частота которых резко выше локального фона.

    Возвращает список (значение, count, ratio), отсортированный по ratio.

    Ограничения по построению:
      * только целочисленные значения (у дробных понятие "соседнего
        значения" не определено);
      * кандидат должен встречаться не реже min_count раз — единичное
        значение не отличить от шума;
      * кандидат должен быть выше Q1 и не совпадать с минимумом колонки:
        мода в нуле у скошенного счётчика (favorites = 0 у тысяч тайтлов) —
        это норма, а не заглушка;
      * фон считается медианой частот соседей в окне +/- half, окно
        обрезается наблюдаемым диапазоном столбца;
      * колонка должна иметь не менее min_unique уникальных значений:
        у низкокардинальных полей понятие локального фона не работает,
        их проще смотреть обычным value_counts();
      * окрестность должна быть разреженной: не менее sparse_thr соседних
        значений вообще не встречаются в данных. Это отличает заглушку от локальной моды.
    """
    s = s.dropna()
    if s.empty:
        return []
    arr = s.to_numpy(dtype='float64')
    if not np.all(arr == np.floor(arr)):
        return []

    if s.nunique() < min_unique:
        return []

    vc = s.astype('int64').value_counts()
    cnt = {int(k): int(v) for k, v in vc.items()}
    lo, hi = min(cnt), max(cnt)
    q1 = float(s.quantile(0.25))

    out = []
    for v, c in cnt.items():
        if c < min_count or v <= q1 or v == lo:
            continue
        nb = [cnt.get(u, 0)
              for u in range(max(v - half, lo), min(v + half, hi) + 1)
              if u != v]
        if len(nb) < 4:
            continue
        sparsity = sum(1 for x in nb if x == 0) / len(nb)
        if sparsity < sparse_thr:
            continue                      # плотная окрестность => это мода
        bg = float(np.median(nb))
        ratio = c / max(bg, 1.0)
        if ratio >= ratio_thr:
            out.append((v, c, round(ratio, 1)))

    out.sort(key=lambda t: -t[2])
    return out


def clip_suspect(s: pd.Series):
    """
    Максимум колонки лежит ровно на битовом пределе и повторяется —
    признак переполнения или обрезки значений при парсинге.
    """
    s = s.dropna()
    if s.empty:
        return None
    mx = s.max()
    if float(mx) != np.floor(float(mx)):
        return None
    mx = int(mx)
    c = int((s == mx).sum())
    if mx in CLIP_LIMITS and c > 1:
        return mx, c
    return None


# --------------------------------------------------------------------------
# основной отчёт по колонкам
# --------------------------------------------------------------------------

def detect_anomaly(df, color='#8e44ad', text_color='white',
                   min_count=5, half=8, ratio_thr=10.0,
                   sparse_thr=0.5, min_unique=20,
                   roles=None, return_raw=False):
    """
    Построчный отчёт по числовым столбцам датафрейма.

    Параметры
    ----------
    df : pd.DataFrame
    color, text_color : str
        Оформление строк, где найдены проблемы (severity != 'ok').
    min_count, half, ratio_thr : см. spike_candidates
    roles : dict | None
        Ручное переопределение ролей: {'episodes': 'count', ...}
    return_raw : bool
        True — вернуть обычный DataFrame вместо Styler.

    Колонки отчёта
    --------------
    role         определённая роль столбца
    null_%       доля пропусков (все остальные проценты считаются от
                 непропусков, чтобы базы не разъезжались)
    tail         max / p99 — насколько длинный правый хвост. Просто чтобы быть в курсе,
                 большое значение у счётчика — норма, а не ошибка.
    severity     ok / soft / hard
    issues       что именно найдено
    examples     конкретные значения с частотой и spike-ratio
    """
    roles = roles or {}
    n = len(df)
    rows = []

    for col in df.select_dtypes(include='number').columns:
        raw = df[col]
        s = raw.dropna()
        role = roles.get(col, infer_role(col))
        lo_ok, hi_ok = ROLE_RANGE[role]

        null_pct = round(raw.isna().mean() * 100, 2) if n else 0.0
        if s.empty:
            rows.append((col, role, str(raw.dtype), null_pct, None, None,
                         0, None, 'ok', 'пусто', ''))
            continue

        issues, examples = [], []
        severity = 'ok'

        # 1. выход за допустимый диапазон роли
        bad = pd.Series(False, index=s.index)
        if lo_ok is not None:
            bad |= s < lo_ok
        if hi_ok is not None:
            bad |= s > hi_ok
        n_bad = int(bad.sum())
        if n_bad:
            severity = 'hard'
            issues.append(f'range:{n_bad}')
            examples += [f'{_num(v)}x{c}' for v, c
                         in s[bad].value_counts().head(3).items()]

        # 2. клиппинг на битовом пределе
        clip = clip_suspect(s)
        if clip:
            severity = 'hard'
            issues.append(f'clip:{clip[0]}')
            examples.append(f'max={clip[0]}x{clip[1]}')

        # 3. спайки частоты (только для счётчиков и оценок)
        if role in ('count', 'score'):
            sp = spike_candidates(s, min_count, half, ratio_thr,
                                  sparse_thr, min_unique)
            if sp:
                severity = 'hard' if severity == 'hard' else 'soft'
                issues.append(f'spike:{len(sp)}')
                examples += [f'{v}x{c} (r={r})' for v, c, r in sp[:3]]

        # 4. для id и rank — проверка на неуникальность значений
        n_uniq = int(s.nunique())
        if role in ('id', 'rank') and n_uniq < len(s):
            severity = 'hard'
            issues.append(f'not_unique:{len(s) - n_uniq}')

        p99 = float(s.quantile(0.99))
        tail = round(float(s.max()) / p99, 1) if p99 > 0 else None

        rows.append((col, role, str(raw.dtype), null_pct,
                     _num(s.min()), _num(s.max()), n_uniq, tail,
                     severity, '; '.join(issues) or 'ok',
                     ', '.join(examples[:4])))

    out = pd.DataFrame(rows, columns=[
        'column', 'role', 'dtype', 'null_%', 'min', 'max', 'n_unique',
        'tail', 'severity', 'issues', 'examples'])

    if return_raw:
        return out

    def paint(row):
        if row['severity'] == 'hard':
            style = f'background-color: {color}; color: {text_color}'
        elif row['severity'] == 'soft':
            style = f'background-color: {color}44'
        else:
            style = ''
        return [style] * len(row)

    return out.style.apply(paint, axis=1).format({'null_%': '{:.2f}'})


def _num(v):
    v = float(v)
    return int(v) if v.is_integer() else round(v, 2)


# --------------------------------------------------------------------------
# согласованность между колонками и таблицами
# --------------------------------------------------------------------------

def check_consistency(details, stats, key='mal_id', tol=1.0, max_examples=5):
    """
    Кросс-проверки details и stats. Здесь находки однозначны: если сумма
    компонент не равна total, данные битые независимо от распределения.

    Возвращает DataFrame: check, n_checked, n_bad, bad_%, worst_error,
    examples (значения key).
    """
    d = details.set_index(key)
    st = stats.set_index(key)
    idx = d.index.intersection(st.index)
    d, st = d.loc[idx], st.loc[idx]

    comp = [c for c in ('watching', 'completed', 'on_hold',
                        'dropped', 'plan_to_watch') if c in st.columns]
    vote_cols = [f'score_{i}_votes' for i in range(1, 11)
                 if f'score_{i}_votes' in st.columns]
    pct_cols = [f'score_{i}_percentage' for i in range(1, 11)
                if f'score_{i}_percentage' in st.columns]

    res = []

    def add(name, err, applicable=None, thr=tol):
        """err — Series абсолютных ошибок; applicable — где проверка имеет смысл."""
        err = pd.Series(err, index=idx).astype('float64')
        ok_mask = pd.Series(True, index=idx) if applicable is None else applicable
        ok_mask = ok_mask & err.notna()
        e = err[ok_mask]
        bad = e > thr
        ex = ', '.join(str(i) for i in e[bad].sort_values(
            ascending=False).head(max_examples).index)
        res.append((name, int(ok_mask.sum()), int(bad.sum()),
                    round(bad.mean() * 100, 3) if len(e) else 0.0,
                    round(float(e.max()), 3) if len(e) else None, ex))

    # 1. компоненты списков складываются в total
    if comp and 'total' in st.columns:
        add('sum(components) == stats.total',
            (st[comp].sum(axis=1) - st['total']).abs(), thr=0)

    # 2. total в stats совпадает с members в details
    if 'total' in st.columns and 'members' in d.columns:
        add('stats.total == details.members',
            (st['total'] - d['members']).abs(), thr=0)

    # 3. сумма голосов совпадает со scored_by
    if vote_cols and 'scored_by' in d.columns:
        add('sum(score_votes) == details.scored_by',
            (st[vote_cols].sum(axis=1) - d['scored_by']).abs(), thr=0)

    # 4. проценты складываются в 100 (там, где голоса вообще есть)
    if pct_cols:
        has_votes = (st[vote_cols].sum(axis=1) > 0) if vote_cols else None
        add('sum(score_percentage) == 100',
            (st[pct_cols].sum(axis=1) - 100).abs(), applicable=has_votes)

    # 5. каждый процент восстанавливается из голосов
    if vote_cols and pct_cols and len(vote_cols) == len(pct_cols):
        tot = st[vote_cols].sum(axis=1).replace(0, np.nan)
        err = pd.concat(
            [(st[p] - st[v] / tot * 100).abs()
             for v, p in zip(vote_cols, pct_cols)], axis=1).max(axis=1)
        add('percentage == votes / sum(votes)', err)

    # 6. score восстанавливается как взвешенное среднее голосов
    if vote_cols and 'score' in d.columns:
        tot = st[vote_cols].sum(axis=1).replace(0, np.nan)
        wmean = sum(int(re.search(r'\d+', v).group()) * st[v]
                    for v in vote_cols) / tot
        add('weighted mean(votes) == details.score',
            (wmean - d['score']).abs(), thr=0.01)

    # 7. На MAL нельзя оценить тайтл, не добавив его в список
    if 'scored_by' in d.columns and 'members' in d.columns:
        add('scored_by <= members',
            (d['scored_by'] - d['members']).clip(lower=0), thr=0)

    # 8. в избранном не может быть больше людей, чем в списках
    if 'favorites' in d.columns and 'members' in d.columns:
        add('favorites <= members',
            (d['favorites'] - d['members']).clip(lower=0), thr=0)

    # 9. completed не больше total
    if 'completed' in st.columns and 'total' in st.columns:
        add('completed <= total',
            (st['completed'] - st['total']).clip(lower=0), thr=0)

    return pd.DataFrame(res, columns=[
        'check', 'n_checked', 'n_bad', 'bad_%', 'worst_error', 'examples'])