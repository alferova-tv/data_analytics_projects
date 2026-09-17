"""Общие функции проекта: загрузка панели, когорты, отток по продуктам.

Панель большая (13,6 млн строк), поэтому всё считаем в DuckDB поверх parquet,
а в pandas забираем только агрегаты.
"""

# аннотации вида `Path | str` иначе падают на Python 3.9, а системное ядро jupyter - 3.9
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

# 24 продуктовых флага в порядке из выгрузки
PRODUCTS = [
    "ind_ahor_fin_ult1", "ind_aval_fin_ult1", "ind_cco_fin_ult1", "ind_cder_fin_ult1",
    "ind_cno_fin_ult1", "ind_ctju_fin_ult1", "ind_ctma_fin_ult1", "ind_ctop_fin_ult1",
    "ind_ctpp_fin_ult1", "ind_deco_fin_ult1", "ind_deme_fin_ult1", "ind_dela_fin_ult1",
    "ind_ecue_fin_ult1", "ind_fond_fin_ult1", "ind_hip_fin_ult1", "ind_plan_fin_ult1",
    "ind_pres_fin_ult1", "ind_reca_fin_ult1", "ind_tjcr_fin_ult1", "ind_valo_fin_ult1",
    "ind_viv_fin_ult1", "ind_nomina_ult1", "ind_nom_pens_ult1", "ind_recibo_ult1",
]

# человеческие названия из словаря Kaggle
PRODUCT_NAMES = {
    "ind_ahor_fin_ult1": "накопительный счёт", "ind_aval_fin_ult1": "гарантии",
    "ind_cco_fin_ult1": "текущий счёт", "ind_cder_fin_ult1": "производный счёт",
    "ind_cno_fin_ult1": "зарплатный счёт", "ind_ctju_fin_ult1": "детский счёт",
    "ind_ctma_fin_ult1": "счёт Más particular", "ind_ctop_fin_ult1": "счёт particular",
    "ind_ctpp_fin_ult1": "счёт particular Plus", "ind_deco_fin_ult1": "короткий депозит",
    "ind_deme_fin_ult1": "средний депозит", "ind_dela_fin_ult1": "длинный депозит",
    "ind_ecue_fin_ult1": "онлайн-счёт", "ind_fond_fin_ult1": "паевые фонды",
    "ind_hip_fin_ult1": "ипотека", "ind_plan_fin_ult1": "пенсионный план",
    "ind_pres_fin_ult1": "кредит", "ind_reca_fin_ult1": "налоговые платежи",
    "ind_tjcr_fin_ult1": "кредитная карта", "ind_valo_fin_ult1": "ценные бумаги",
    "ind_viv_fin_ult1": "жилищный счёт", "ind_nomina_ult1": "зачисление зарплаты",
    "ind_nom_pens_ult1": "зачисление пенсии", "ind_recibo_ult1": "автоплатёж",
}

# границы окна, в котором когорты видны с первого месяца жизни (см. 01_data_quality)
COHORT_FIRST = "2015-07-01"
COHORT_LAST = "2016-04-01"
PANEL_LAST = "2016-05-01"  # последний снимок, отток по нему не определён


def flag_expr(col: str) -> str:
    """SQL-выражение, приводящее продуктовый флаг к 0/1.

    `ind_nomina_ult1` и `ind_nom_pens_ult1` приехали строками, т к содержат `NA`,
    поэтому каст делаем через TRY_CAST, а не напрямую.
    """
    return f"coalesce(TRY_CAST(trim(CAST({col} AS VARCHAR)) AS INT), 0)"


def n_prod_expr() -> str:
    """Число продуктов у клиента в строке."""
    return " + ".join(flag_expr(c) for c in PRODUCTS)


def build_panel(con: duckdb.DuckDBPyConnection, parquet_path: Path | str) -> None:
    """Готовит рабочие таблицы: `p` (компактная панель) и `fs` (профиль клиента).

    `p` - одна строка на клиента и месяц: число продуктов и нужные для разрезов поля.
    `fs` - по клиенту: первый месяц в панели, месяц подключения и сколько месяцев виден.
    Пустые строки приводим к NULL сразу, иначе `''` и NULL живут в данных вперемешку.
    """
    # иначе прогресс-бар DuckDB оставляет в выводе ноутбука виджет FloatProgress
    con.execute("SET enable_progress_bar = false")
    con.execute(f"CREATE OR REPLACE VIEW t AS SELECT * FROM read_parquet('{parquet_path}')")
    con.execute(f"""
        CREATE OR REPLACE TABLE p AS
        SELECT ncodpers,
               date_trunc('month', fecha_dato) AS m,
               date_trunc('month', fecha_alta) AS cohort,
               ({n_prod_expr()}) AS n_prod,
               nullif(trim(canal_entrada), '') AS canal,
               nullif(trim(segmento), '') AS segmento,
               nullif(trim(tiprel_1mes), '') AS rel,
               nullif(trim(indfall), '') AS indfall,
               TRY_CAST(trim(age) AS INT) AS age,
               TRY_CAST(trim(antiguedad) AS INT) AS antiguedad,
               renta
        FROM t
    """)
    con.execute("""
        CREATE OR REPLACE TABLE fs AS
        SELECT ncodpers, min(m) AS m1, max(m) AS m_last,
               min(cohort) AS cohort, count(*) AS месяцев
        FROM p GROUP BY 1
    """)


def cohort_members(con: duckdb.DuckDBPyConnection,
                   first: str = COHORT_FIRST, last: str = COHORT_LAST) -> None:
    """Строгое членство когорты: берём только тех, кто появился в панели в свой же месяц подключения.

    Без этого условия матрица даёт удержание выше 100%: в июле 2015 выгрузку расширили,
    и клиенты с более ранней `fecha_alta` наполняют свои когорты задним числом.
    """
    con.execute(f"""
        CREATE OR REPLACE TABLE mem AS
        SELECT ncodpers, cohort FROM fs
        WHERE m1 = cohort AND cohort BETWEEN DATE '{first}' AND DATE '{last}'
    """)


def retention_matrix(con: duckdb.DuckDBPyConnection, base: str = "cohort") -> pd.DataFrame:
    """Когортная матрица удержания в процентах.

    Активным считаем клиента, у которого в этом месяце есть хотя бы один продукт:
    четверть строк панели - клиенты без продуктов, присутствие в выгрузке ничего не значит.
    `base='cohort'` - процент от размера когорты, `base='k1'` - от второго месяца жизни
    (часть продуктов оформляется уже после первого снимка, см. 01_data_quality).
    """
    # колонка cohort есть и в mem, и в p, поэтому обращаемся к ней только через mem
    df = con.execute("""
        SELECT mem.cohort AS cohort, datediff('month', mem.cohort, p.m) AS k,
               count(DISTINCT p.ncodpers) AS присутствие,
               count(DISTINCT p.ncodpers) FILTER (WHERE p.n_prod >= 1) AS активные
        FROM mem JOIN p USING (ncodpers)
        WHERE p.m >= mem.cohort
        GROUP BY 1, 2
    """).fetchdf()
    pres = df.pivot(index="cohort", columns="k", values="присутствие")
    act = df.pivot(index="cohort", columns="k", values="активные")
    denom = pres[0] if base == "cohort" else act[1]
    return (100 * act.div(denom, axis=0)).round(1)


def product_transitions(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Уходы из продукта (1 → 0) и сколько из них - мигание (1 → 0 → 1).

    Считаем одним проходом: 24 пары lag/lead с одинаковым окном, поэтому сортировка
    по (клиент, месяц) выполняется один раз.
    """
    flags = ",\n ".join(f"{flag_expr(c)} AS {c}" for c in PRODUCTS)
    lags = ",\n ".join(f"lag({c}) OVER w AS l_{c}" for c in PRODUCTS)
    leads = ",\n ".join(f"lead({c}) OVER w AS n_{c}" for c in PRODUCTS)
    aggs = ",\n ".join(
        f"count(*) FILTER (WHERE l_{c} = 1 AND {c} = 0) AS {c}_уход, "
        f"count(*) FILTER (WHERE l_{c} = 1 AND {c} = 0 AND n_{c} = 1) AS {c}_мигание"
        for c in PRODUCTS
    )
    row = con.execute(f"""
        WITH b AS (SELECT ncodpers, fecha_dato, {flags} FROM t),
             w AS (SELECT *, {lags}, {leads} FROM b
                   WINDOW w AS (PARTITION BY ncodpers ORDER BY fecha_dato))
        SELECT {aggs} FROM w
    """).fetchdf().iloc[0]

    res = pd.DataFrame({
        "продукт": [PRODUCT_NAMES[c] for c in PRODUCTS],
        "колонка": PRODUCTS,
        "ушли": [int(row[f"{c}_уход"]) for c in PRODUCTS],
        "мигание": [int(row[f"{c}_мигание"]) for c in PRODUCTS],
    })
    res["мигание_проц"] = (100 * res["мигание"] / res["ушли"].replace(0, pd.NA)).round(1)
    res["чистый_отток"] = res["ушли"] - res["мигание"]
    return res.sort_values("ушли", ascending=False).reset_index(drop=True)
