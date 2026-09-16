# Branding Specification - «Во что вкладывать контент-бюджет»

Собрано из `DASHBOARD-REQUEST.md` (нейтральная палитра, без логотипов, русский язык,
Tableau Public) плюс решения аналитика от 16.09.2026: сине-бирюзовая палитра сегментов,
холст Range 1200×900.

## Color Palette

- Primary: #2e75b6 (синий)
- Secondary: #41a5a5 (бирюзовый)
- Accent colors: #1f5c8b, #b6bfc9
- Background: #F6F7F9
- Card background: #FFFFFF
- Text dark: #1C2833
- Text medium: #5D6D7E

### Цвета сегментов (общие для кривой удержания и scatter)

| Сегмент | Hex |
|---------|-----|
| Флагманы | #1f5c8b |
| Надёжный просмотр | #2e75b6 |
| Нишевые любимчики | #41a5a5 |
| Остальные | #b6bfc9 |
| Все сериалы (жирная линия на кривой) | #1c2833 |

«Остальные» - 545 из 1 101 тайтлов, поэтому серый: они не должны перетягивать внимание.

## Fonts

- Primary font: Tableau Book (семейство Tableau, ставится вместе с Tableau Desktop)
- Title weight: Tableau Bold
- Body weight: Tableau Light

Все подписи на русском. Перед публикацией проверить кириллицу в Tableau Desktop -
если в семействе Tableau окажутся не все глифы, заменить на Arial во всём токен-файле.

## Padding & Spacing

- Card padding: 8px
- Section spacing: 11px
- Container margin: 4px
- KPI accent bar height: 3px

## Logo & Icons

Логотипа нет и не нужно - сервис вымышленный, дашборд идёт в портфолио.
Папки `branding/icons/` нет, иконки заголовков `tableau-mock` рисует сам.

## Dashboard Sizing

- Mode: Range
- Minimum width: 1200
- Minimum height: 900
- Maximum: Flexible

## Fallback Disclosure

Всё, что не перечислено выше, берётся из дефолтов Tableau и должно быть перечислено
в разделе `## Fallback Decisions` файла `DESIGN-TOKENS.md`.
