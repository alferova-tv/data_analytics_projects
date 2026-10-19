# Графики для письма. Числа не пересчитываются, а взяты из выводов lebedev_tg_research.ipynb (источник указан у каждого графика).
import matplotlib.pyplot as plt
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

OUT = Path(__file__).parent
CYAN, ORANGE, LIGHTBLUE, NAVY, GREY2 = "#2FA8E0", "#EE6C2B", "#86A8D8", "#4A6A9B", "#A8A8A8"
GREY = "#C9C3DA"
plt.rcParams.update({
    "font.family": ["PT Serif", "Charter", "DejaVu Serif"], "font.size": 12,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.titlelocation": "left", "axes.titlesize": 13, "axes.titleweight": "bold",
    "xtick.bottom": False, "ytick.left": False, "savefig.dpi": 200, "savefig.bbox": "tight",
})

def num(v, fmt):
    # округление половины вверх, как в тексте ноутбука (14,85 → 14,9)
    digits = int(fmt[3]) if fmt.startswith("{:.") else 1
    return str(Decimal(str(v)).quantize(Decimal(1).scaleb(-digits), ROUND_HALF_UP)).replace(".", ",")

def hbars(ax, labels, values, colors, fmt="{:.1f}"):
    y = range(len(labels))[::-1]
    ax.barh(list(y), values, color=colors, height=0.6)
    ax.set_yticks(list(y), labels)
    ax.set_xticks([])
    for yi, v in zip(y, values):
        ax.text(v + max(values) * 0.02, yi, num(v, fmt), va="center")
    ax.set_xlim(0, max(values) * 1.18)

# 1. Реакции по типу поста — медианы из cmp-content (все посты окна)
fig, ax = plt.subplots(figsize=(7, 3.2))
hbars(ax, ["Размышления", "Прочие посты", "Реклама", "Свои продукты", "Видео"],
      [14.85, 12.50, 7.50, 6.16, 4.70], [CYAN, GREY2, ORANGE, LIGHTBLUE, NAVY])
ax.set_title("Реакций на 1000 просмотров, медиана")
fig.savefig(OUT / "1_reactions_by_type.png"); plt.close(fig)

# 2. Платные комментарии — медианы из paid-table
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.2))
periods = ["Комментарии\nбесплатные\nокт 2024 – мар 2025", "Комментарии\nплатные\nмар – окт 2025", "Комментарии\nснова бесплатные\nокт 2025 – сен 2026"]
for ax, vals, title, fmt in [(a1, [1.17, 0.18, 0.99], "Комментариев на 1000 просмотров", "{:.2f}"),
                             (a2, [12.9, 13.1, 11.8], "Реакций на 1000 просмотров", "{:.1f}")]:
    bars = ax.bar(range(3), vals, color=[CYAN, ORANGE, LIGHTBLUE], width=0.6)
    ax.set_xticks(range(3), periods, fontsize=10)
    ax.set_yticks([]); ax.spines["left"].set_visible(False)
    for i, v in enumerate(vals):
        ax.text(i, v + max(vals) * 0.03, num(v, fmt), ha="center")
    ax.set_ylim(0, max(vals) * 1.2); ax.set_title(title)
fig.tight_layout(); fig.savefig(OUT / "2_paid_comments.png"); plt.close(fig)

# 3. Комментарии у размышлений: вопрос в тексте (cmp-text-md) и время публикации (cmp-slot, все размышления)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 2.6))
hbars(a1, ["С вопросом", "Без вопроса"], [1.52, 1.13], [CYAN, ORANGE], "{:.2f}")
a1.set_title("Вопрос в тексте")
hbars(a2, ["19:05", "15:05", "11:05"], [1.39, 1.19, 1.15], [CYAN, ORANGE, LIGHTBLUE], "{:.2f}")
a2.set_title("Время публикации")
fig.suptitle("Комментариев на 1000 просмотров у размышлений, медиана", x=0.01, ha="left", fontsize=13)
fig.tight_layout(); fig.savefig(OUT / "3_comments.png"); plt.close(fig)

# 4. Падение охвата — медиана просмотров по кварталам, все посты окна.
# Посчитано вне ноутбука по data/posts.parquet; перед отправкой письма добавить расчёт в ноутбук.
quarters = ["IV кв.\n2024", "I кв.\n2025", "II кв.\n2025", "III кв.\n2025", "IV кв.\n2025", "I кв.\n2026", "II кв.\n2026", "III кв.\n2026"]
views_k = [228.6, 227.2, 201.5, 188.1, 159.4, 163.2, 105.9, 81.1]
fig, ax = plt.subplots(figsize=(9, 3.4))
ax.plot(range(8), views_k, color=CYAN, lw=2.5, marker="o", ms=7)
for i, v in enumerate(views_k):
    ax.text(i, v + 10, num(v, "{:.0f}"), ha="center")
ax.set_xticks(range(8), quarters, fontsize=10)
ax.set_yticks([]); ax.spines["left"].set_visible(False)
ax.set_ylim(0, 270); ax.set_title("Просмотров на пост, тысяч, медиана")
fig.savefig(OUT / "4_views_by_quarter.png"); plt.close(fig)

# 5. 15:05 и длина текста — отличие 15:05 от 11:05 у размышлений, B / A − 1 из cmp-slot
# (все размышления и внутри корзин длины). Длинные не показаны: в 15:05 их 20, меньше порога 30.
groups = ["Все размышления", "Короткие\n(до 414 символов)", "Средние\n(415–720 символов)"]
diffs = [-11, -6, -3]
fig, ax = plt.subplots(figsize=(8, 3.0))
y = list(range(3))[::-1]
ax.barh(y, diffs, color=[ORANGE, CYAN, LIGHTBLUE], height=0.55)
ax.set_yticks(y, groups)
ax.axvline(0, color="black", lw=1)
for yi, v in zip(y, diffs):
    ax.text(v - 0.3, yi, f"−{abs(v)}%", va="center", ha="right")
ax.set_xlim(-14, 1); ax.set_xticks([])
ax.spines["bottom"].set_visible(False)
ax.set_title("На сколько в 15:05 меньше реакций, чем в 11:05")
fig.savefig(OUT / "5_slot_by_length.png"); plt.close(fig)

# 6. Отрицательные реакции по типу поста — медианы из cmp-content
fig, ax = plt.subplots(figsize=(7, 3.2))
hbars(ax, ["Размышления", "Прочие посты", "Реклама", "Свои продукты", "Видео"],
      [0.38, 0.70, 1.83, 0.53, 0.40], [CYAN, GREY2, ORANGE, LIGHTBLUE, NAVY], "{:.2f}")
ax.set_title("Отрицательных реакций на 1000 просмотров, медиана")
fig.savefig(OUT / "6_negative_by_type.png"); plt.close(fig)

# 7. Альтернатива графикам 1 и 6: реакции и отрицательные реакции по типу поста на одной диаграмме.
# Медианы и число постов из cmp-content; площадь круга — число постов.
types = [("Размышления", 14.85, 0.38, 1430, CYAN), ("Прочие посты", 12.50, 0.70, 220, GREY2),
         ("Реклама", 7.50, 1.83, 209, ORANGE), ("Свои продукты", 6.16, 0.53, 45, LIGHTBLUE),
         ("Видео", 4.70, 0.40, 375, NAVY)]
OFFSETS = {"Размышления": (0, 42, "center"), "Прочие посты": (-16, 16, "right"), "Реклама": (0, 26, "center"),
           "Свои продукты": (12, 0, "left"), "Видео": (-20, 0, "right")}
fig, ax = plt.subplots(figsize=(8, 4.2))
for name, r, n, size, color in types:
    ax.scatter(r, n, s=size * 0.9, color=color, alpha=0.9, edgecolor="white", lw=1.5, zorder=3)
    dx, dy, ha = OFFSETS[name]
    ax.annotate(f"{name}\n{num(r, '{:.1f}')} и {num(n, '{:.2f}')}", (r, n), xytext=(dx, dy),
                textcoords="offset points", ha=ha, va="center", fontsize=10)
ax.set_xlim(0, 17.5); ax.set_ylim(0, 2.4)
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.1f}".replace(".", ","))
ax.spines["left"].set_visible(True)
ax.tick_params(left=True, bottom=True)
ax.set_xlabel("Реакций на 1000 просмотров")
ax.set_ylabel("Отрицательных реакций\nна 1000 просмотров")
ax.set_title("Реакции и отрицательные реакции по типу поста, медианы")
ax.text(1, -0.2, "Площадь круга — число постов", transform=ax.transAxes, ha="right", fontsize=9, color="#777777")
fig.savefig(OUT / "7_types_scatter.png"); plt.close(fig)

# 8. Альтернатива графику 3: точки вместо столбиков, медианы комментариев у размышлений.
fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 2.4), sharex=True)
for ax, labels, vals, colors, title in [
        (a1, ["С вопросом", "Без вопроса"], [1.52, 1.13], [CYAN, ORANGE], "Вопрос в тексте"),
        (a2, ["19:05", "15:05", "11:05"], [1.39, 1.19, 1.15], [CYAN, ORANGE, LIGHTBLUE], "Время публикации")]:
    y = list(range(len(labels)))[::-1]
    ax.hlines(y, 1.0, 1.65, color="#EEEEEE", lw=1.5, zorder=1)
    ax.scatter(vals, y, s=160, color=colors, zorder=3)
    for yi, v in zip(y, vals):
        ax.text(v + 0.03, yi, num(v, "{:.2f}"), va="center")
    ax.set_yticks(y, labels); ax.set_xticks([]); ax.set_xlim(1.0, 1.65)
    ax.set_ylim(-0.6, len(labels) - 0.4); ax.set_title(title)
    ax.spines["bottom"].set_visible(False)
fig.suptitle("Комментариев на 1000 просмотров у размышлений, медиана", x=0.01, ha="left", fontsize=13)
fig.tight_layout(); fig.savefig(OUT / "8_comments_dots.png"); plt.close(fig)
