# Design Tokens

> Authored by `tableau-brand` (step 4). The single source of truth for palette,
> type, and spacing consumed by `tableau-mock` (the HTML demo) and `tableau-build`
> (the `.twb`).

## Source

- **Brand source**: `branding/branding.md` - собран из `DASHBOARD-REQUEST.md` и ответов аналитика 16.09.2026 (палитра сегментов, размер холста). Демо-пример `scaffold/branding/EXAMPLE-branding.md` не использовался.
- **Logo / icons**: none provided - логотипа нет по требованию запроса, папки `branding/icons/` нет.

## Typography

- **Font family**: Tableau Book
- **Dashboard title**: 28px, Tableau Bold, `#1c2833`
- **Chart title**: 15px, Tableau Medium, `#1c2833`   *(a Text object, not the worksheet's built-in header - see Constraints)*
- **Filter / section labels**: 12px, Tableau Medium, `#5d6d7e`
- **Worksheet default**: 12px
- **Tooltip**: 12px

Весь текст на русском. Семейство Tableau ставится вместе с Tableau Desktop, так что на Tableau Public отрисуется одинаково. Перед публикацией стоит глазами проверить кириллицу в Desktop; если глифов не хватит, меняем `Font family` на `Arial` во всех строках этого раздела.

## Colors

### Backgrounds
- **Dashboard background**: `#f6f7f9`
- **Top banner / title area**: `#f5f7f9`
- **Chart card background**: `#ffffff`
- **Separator line**: `#eef1f4`

### Accent colors (KPI top border bars)
- Accent 1 (сериалов в разрезе): `#1f5c8b`
- Accent 2 (медианный ep3_retention): `#2e75b6`
- Accent 3 (доля продолжений): `#41a5a5`
- Accent 4 (резерв): `#6f8faf`

### Chart series colors

`#1f5c8b`, `#2e75b6`, `#41a5a5`, `#b6bfc9`, `#1c2833`

**`segment`**

| Member | Token | Hex |
|--------|-------|-----|
| Флагманы | Blue 800 | `#1f5c8b` |
| Надёжный просмотр | Blue 600 | `#2e75b6` |
| Нишевые любимчики | Teal 500 | `#41a5a5` |
| Остальные | Grey 300 | `#b6bfc9` |
| Все сериалы | Ink 900 | `#1c2833` |

Порядок строк = порядок обхода домена: сегменты сортируются Флагманы → Надёжный просмотр → Нишевые любимчики → Остальные, в конце - справочная линия «Все сериалы» на кривой удержания. «Остальные» намеренно серые: это 545 из 1 101 тайтлов, они фон, а не сигнал. Палитра одна и та же на кривой и на scatter.

Бары на графике «первоисточник × удержание» красим одним цветом `#2e75b6` - сравниваем длину, а не категории.

### Text
- Dark (titles): `#1c2833`
- Medium (labels): `#5d6d7e`

## Logo

- **File**: none provided
- **Placement**: логотипа нет, шапку занимает только Text object с заголовком дашборда.

## Dashboard Sizing

- **Sizing mode**: Range
- **Minimum width**: 1200
- **Minimum height**: 900
- **Maximum**: Flex (no max)

## Icons

Папки `branding/icons/` нет - `tableau-mock` рисует простые inline-SVG по типу графика (линия, scatter, бар).

## Spacing

| Element | Property | Value |
|---------|----------|-------|
| Chart card | padding | 8px |
| Section | spacing | 11px |
| Container | margin | 4px |
| KPI accent bar | height | 3px |
| KPI cards | margin-right | 16px |
| Sheet zone | inner padding | 8px |
| Separator line | margin left/right | 10px |

## Fallback Decisions

| Token / decision | Fallback value used | Why it was needed |
|------------------|---------------------|-------------------|
| Font family и размеры шрифтов | Tableau Book / Bold 28px / Medium 15px / Medium 12px / 12px | В запросе про шрифты ничего не было, взяли родное семейство Tableau |
| Dashboard background | `#f6f7f9` | Фон не задан |
| Top banner / title area | `#f5f7f9` | Фон шапки не задан |
| Chart card background | `#ffffff` | Фон карточек не задан |
| Separator line | `#eef1f4` | Цвет разделителя не задан |
| Accent 4 | `#6f8faf` | KPI всего три, четвёртый акцент оставлен про запас из дефолтной палитры |
| Text dark / medium | `#1c2833` / `#5d6d7e` | Цвета текста не заданы |
| Spacing (padding 8, spacing 11, margin 4, accent bar 3, KPI margin 16) | дефолты Tableau | Отступы в запросе не обсуждались |
| Sizing mode Range, Maximum Flex | Range, без максимума | Задан только размер холста, режим не обсуждался |

Из брендинга аналитика пришли: цвета сегментов, минимальные ширина/высота холста, отсутствие логотипа, русский язык подписей.

## Constraints

- **Sheet headers are hidden; the visible header is a Text object.** У каждого листа снят `Show Header`, видимый заголовок - отдельный Text object в контейнере шапки.
- **Collapsible filter panel via a Show/Hide button** (не Dynamic Zone Visibility).
- **Tiled layout by default** - плавающие элементы только для оверлеев вроде панели фильтров.
- **Insight-style titles** - заголовок формулирует вывод, а не название метрики: «60% потерь - в первых трёх сериях», а не «Удержание по сериям».
- Никаких скруглённых углов на `2024.2-2025.x`, `border-style: none`, белые карточки на светло-сером фоне.
- Максимум 5 цветов серий, один цветовой язык на весь дашборд.
