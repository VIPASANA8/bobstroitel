# Индекс проекта Poker8 / Poker Trainer

> Карта репозитория `D:\project\poker`. Обновлена 2026-08-16.
> Python-проект: локальный тренажёр No-Limit Texas Hold'em (v0.11), развившийся
> в сетевой продукт **Poker8 Online MVP** — Telegram Mini App с 6-max столами на
> виртуальном PLAY-балансе, авторитетным сервером раздач и WebSocket-транспортом.

## Обзор

Стек: **FastAPI + Starlette + Uvicorn**, **SQLAlchemy 2 (async) + Alembic**,
PostgreSQL (прод) / SQLite+aiosqlite (dev), WebSockets, Pydantic 2. Тесты — pytest
(+ Playwright для e2e). Фронтенд — статический HTML/CSS/JS без сборщика. Сборка и
деплой — Docker Compose.

Границы продукта Online MVP: нет депозитов, выводов, KYC, USDT/TRC20, блокчейна и
real-money API. Только виртуальный баланс (юниты); при входе начисляется welcome
100 000 юнитов из «крана» (faucet).

## Корень

| Файл | Назначение |
|------|-----------|
| `README.md` | История версий v0.9–v0.11 + инструкция запуска Online MVP |
| `requirements.txt` | Зависимости (FastAPI 0.116, SQLAlchemy 2, Alembic, psycopg, websockets, playwright) |
| `alembic.ini` | Конфигурация миграций |
| `compose.yaml` / `compose.server.yaml` | Docker Compose (dev-Postgres / прод-стек app+postgres) |
| `Dockerfile`, `.dockerignore` | Образ приложения (python:3.12-slim) |
| `.env.example` | Пример переменных окружения (`POKER8_*`) |
| `pytest.ini` | Конфигурация тестов |
| `servers.md` | ⚠️ Секретные доступы к VPS (не коммитить) |
| `UI_COMPONENTS.md`, `V012_LAYOUT.md`, `V013_PIXEL_PASS.md`, `V014_MOBILE_FILL.md` | Документация UI-итераций |

## Ядро покера — `poker/`

Движок и правила игры (не зависят от сети).

| Модуль | Размер | Назначение |
|--------|--------|-----------|
| `engine.py` | 20 KB | Основной игровой движок: раздача, очередность, main/side pots, all-in, showdown |
| `evaluator.py` | 5 KB | Оценка комбинаций рук |
| `models.py` | 6 KB | Доменные модели (карта, игрок, стол, состояние раздачи) |
| `equity.py` | 1 KB | Расчёт эквити |
| `deck.py` | 0.5 KB | Колода и тасование |

## Онлайн-слой — `online/`

Сетевой рантайм Poker8: авторитетный сервер, БД, транспорт.

| Модуль | Размер | Назначение |
|--------|--------|-----------|
| `runtime.py` | 30 KB | Рантайм столов: жизненный цикл раздач, ревизии, тики; исключения `StaleRevision`, `TablePaused` |
| `seating.py` | 20 KB | FIFO-рассадка, очередь, ready/leave/observe/reconnect/add-on, `SeatingError` |
| `ledger.py` | 18 KB | Двухзаписный учёт виртуального баланса (счета/транзакции/проводки), faucet, идемпотентность |
| `schema.py` | 13 KB | SQLAlchemy-модели БД (см. раздел «Схема БД») |
| `auth.py` | 9 KB | Аутентификация: Telegram `initData`, guest, dev; сессии-cookie |
| `catalogue.py` | 5 KB | Каталог/лобби столов, quick-play, сид дефолтных столов |
| `serialization.py` | 5 KB | Сериализация состояния стола для клиента |
| `scheduler.py` | 4 KB | Планировщик тиков/дедлайнов |
| `coordinator.py` | 3 KB | Координатор автозапуска столов (`POKER8_COORDINATOR_ENABLED`) |
| `config.py` | 3 KB | `Settings.from_mapping()` — чтение окружения `POKER8_*` |
| `opponent_models.py` | 3 KB | Модели поведения оппонентов |
| `chat.py` | 3 KB | Чат за столом, rate-limit |
| `history.py` | 6 KB | История раздач |
| `logging.py`, `events.py`, `amounts.py`, `asyncio_runner.py`, `database.py` | — | Логи, события, суммы, async-раннер, `create_database()` |

## Веб-приложение — `app/`

FastAPI-приложение и HTTP/WS-роутеры.

| Файл | Назначение |
|------|-----------|
| `main.py` | Точка входа `app.main:app` |
| `online.py` | `create_app()`: lifespan, DI в `app.state`, монтирование роутеров и `/static` |
| `legacy.py` (26 KB) | Legacy-эндпоинты локального тренажёра v0.11 |
| `dependencies.py` | `get_current_user`, `AuthenticatedUser` |
| `schemas.py` | Pydantic-схемы API |
| `production.py` | Прод-обвязка |

### REST API (роутеры `app/routers/`)

Все `/api/*`-ручки (кроме `/health` и `/api/config`) требуют сессию-cookie
`poker8_session`.

| Метод и путь | Роутер | Назначение |
|--------------|--------|-----------|
| `POST /api/auth/telegram` | auth | Логин по Telegram `initData` |
| `POST /api/auth/guest` | auth | Гостевой вход (только при `open_access`) |
| `POST /api/auth/dev/{tg_id}` | auth | Dev-логин (только `environment=development`) |
| `POST /api/auth/logout` | auth | Выход, отзыв сессии |
| `GET /api/config` | config | Публичный конфиг тенанта/брендинга |
| `GET /api/lobby/tables` | lobby | Список столов (пагинация) |
| `POST /api/lobby/quick-play` | lobby | Быстрый подбор стола |
| `GET /api/tables/{id}` | tables | Снапшот стола + `viewer_state` |
| `POST /api/tables/{id}/ready` | tables | Встать в очередь на место (buy-in) |
| `POST /api/tables/{id}/ready/cancel` | tables | Отменить готовность |
| `POST /api/tables/{id}/observe` | tables | Перейти в наблюдатели |
| `POST /api/tables/{id}/leave` | tables | Покинуть стол |
| `POST /api/tables/{id}/reconnect` | tables | Переподключение к месту |
| `POST /api/tables/{id}/add-on` | tables | Докупка фишек |
| `GET/POST /api/tables/{id}/chat` | chat | Чтение/отправка сообщений (лимит 300 симв.) |
| `GET /api/profile` | profiles | Профиль, баланс, уровень |
| `GET /api/profile/play-journal` | profiles | Журнал операций баланса |
| `GET /api/profile/hands` | profiles | История последних раздач |
| `POST /api/profile/play-top-up` | profiles | Пополнение виртуального баланса |
| `GET /health/live` | health | Liveness |
| `GET /health/ready` | health | Readiness (БД, ревизия миграции, паузы рантайма) |
| `GET /` | online.py | Лобби (`static/lobby.html`) |
| `GET /table` | online.py | Стол (`static/index.html`) |
| `GET /static/*` | online.py | Статические ассеты |

### WebSocket-протокол — `WS /ws/tables/{table_id}`

Аутентификация по cookie; без сессии — закрытие с кодом `4401`.

Клиент → сервер (JSON `type`): `ping`, `resync`, `action`
(`{command_id, expected_revision, action, amount_units}`), `disconnect`.
Сервер → клиент: `snapshot` (reason: `connected`/`resync`/`state_changed`/
`stale_revision`), `pong`, `presence`, `command_rejected`
(`unknown_message`/`table_paused`/…). После каждого валидного `action` сервер
рассылает свежий снапшот всем зрителям стола. Рассинхрон ревизии → снапшот с
reason `stale_revision`.

## Схема БД — `online/schema.py` (Alembic до `20260814_0004`)

Мультитенантная модель с денежным леджером в стиле двойной записи.

- **Тенанты и пользователи:** `tenants`, `tenant_bots`, `users`,
  `user_tenant_visits`, `auth_sessions` (хэш токена, TTL, отзыв).
- **Виртуальные деньги:** `play_accounts` (owner: user/system/table; kind:
  wallet/escrow/faucet), `play_transactions` (faucet_grant/buy_in/add_on/
  settlement/return, идемпотентный ключ), `play_entries` (проводки, сумма ≠ 0).
- **Столы и рассадка:** `poker_tables` (SB/BB, min/max buy-in, `max_seats = 6`),
  `table_seats` (seat 0–5, состояние empty/seated/held/leaving, частичные
  unique-индексы на активные места), `seat_queue` (FIFO, `position_seq`).
- **Рантайм и команды:** `table_runtimes` (revision, phase waiting/active/result/
  countdown/paused, приватный/публичный JSON-стейт, дедлайны), `game_commands`
  (идемпотентность по `command_id`, accepted/rejected).
- **История раздач:** `hands`, `hand_players` (карманные карты, net), `hand_actions`
  (по улицам, pot до/после), `system_players` (боты: easy/normal/hard/maximum),
  `chat_messages`, `integrity_events` (аудит честности).

## Боты — `bots/`

| Модуль | Назначение |
|--------|-----------|
| `base.py` | Базовый интерфейс бота |
| `strategic.py` (9 KB) | Стратегический бот |
| `multiway.py` (10 KB) | Логика multiway-споты |
| `heuristic.py` | Эвристический бот |
| `cfr_bot.py` | Бот на основе CFR-решателя |
| `difficulty.py` | Уровни сложности (easy/normal/hard/maximum) |

## Солвер и диапазоны

- **`solver/`** — `mccfr.py` (16 KB, Monte-Carlo CFR), `action_abstraction.py`.
- **`ranges/`** — `model.py` (10 KB, модель диапазонов рук).
- **`analysis/`** — `hand_analyzer.py` (пост-хенд анализ, CFR-lite споты).

## Хранение и миграции

- **`persistence/`** — `store.py` (57 KB) + `__init__.py`: слой персистентности локального тренажёра.
- **`migrations/`** — Alembic; версии `0001_online_foundation` → `0002_table_runtime` → `0003_seat_queue_seat` → `0004_chat_and_branding`.
- **`data/`** — SQLite-базы: `poker_trainer.sqlite3` (тренажёр), `poker8_online_dev.sqlite3` (онлайн dev).

## Фронтенд — `static/`

- Точки входа: `index.html` (стол), `lobby.html`, `profile.html`.
- Ядро: `app.js` (88 KB), `style.css` (134 KB), `component-ui.{css,js}`, `mobile.css`, `network.css`.
- Онлайн-клиент: `online-table.js`, `online-transport.js`, `auth-client.js`, `lobby.js`, `profile.js`.
- Итеративные патчи UI: `v015`–`v038`; крупнейший — `v038-poker8-v2-cinematic-table.js` (65 KB).
- `assets/` — фоны стола (`neon-room-*.webp`, `poker8-v2-table-mobile.webp`).

## Инструменты — `tools/project_mcp/`

MCP-сервер управления состоянием проекта: `server.py`, `project_state.py` (32 KB),
`install.ps1`. Пишет только в `docs/project/{status,decisions}.md` (решение P8-DEC-0001).

## Документация — `docs/`

- **`project/`** — `status.md` (план online-mvp-foundation, задача 1, completed), `decisions.md` (append-only).
- **`runbooks/`** — `online-mvp.md` (деплой/бэкап/release-gate), `add-partner-bot.md`.
- **`superpowers/`** — планы (`plans/`) и спецификации (`specs/`): продуктовое видение, online-network MVP (foundation/runtime/client), project-navigator MCP, визуальные референсы poker8-v2, мобильные доработки.

## Тесты — `tests/`

- **Корень:** движок, эвалюатор, multiway, солвер, диапазоны, персистентность, профили, регрессии (`test_v101_regressions.py`).
- **`online/`** (~30 файлов): auth, catalogue, chat, config, coordinator, ledger, runtime, seating, scheduler, schema, websocket, recovery, hand_settlement, postgres-интеграция, наблюдаемость.
- **`e2e/`** — Playwright мобильного онлайн-флоу. **`load/`** — нагрузка (100 соединений / 20 столов). **`project_mcp/`** — тесты MCP-сервера.

---

## Деплой и VPS

### Docker Compose (прод/стейджинг) — `compose.server.yaml`

Два сервиса: `app` (билд из `Dockerfile`, uvicorn на `0.0.0.0:8000`,
`restart: unless-stopped`, healthcheck `/health/live`) и `postgres:16-alpine`
(том `poker8_pgdata`). При старте контейнер выполняет `alembic upgrade head`
и запускает сервер.

```bash
# на сервере, в каталоге проекта
export POSTGRES_PASSWORD=...           # обязателен
export POKER8_DEFAULT_BOT_TOKEN=...    # обязателен в прод
export POKER8_TENANTS_JSON='[...]'     # обязателен: hosts/бренд/token_env
docker compose -f compose.server.yaml up -d --build
docker compose -f compose.server.yaml logs -f app
```

`compose.yaml` — только dev-Postgres (порт 5432) и эфемерный `postgres_test`
(порт 5433, tmpfs) для тестов.

### Переменные окружения (`POKER8_*`, читаются в `online/config.py`)

| Переменная | Назначение |
|-----------|-----------|
| `POKER8_ENV` | `development` / `staging` / `test` / `production` |
| `POKER8_DATABASE_URL` | DSN БД (обязателен в проде); dev по умолчанию — SQLite |
| `POKER8_DEFAULT_BOT_TOKEN` | Telegram bot-токен (обязателен в проде) |
| `POKER8_TENANTS_JSON` | Список тенантов: `slug`, `hosts`, `name`, `branding`, `token_env` |
| `POKER8_DEFAULT_TENANT` | Слаг тенанта по умолчанию (`poker8`) |
| `POKER8_COORDINATOR_ENABLED` | Автозапуск столов (в prod/test = вкл) |
| `POKER8_OPEN_ACCESS` | Гостевой доступ для IP-стейджинга (в проде принудительно выкл) |
| `POKER8_DEV_PROFILES` | Dev-профили `id:имя` через запятую |

Прод требует PostgreSQL, точную привязку host→tenant и Telegram-`initData`;
токены ботов никогда не уходят в браузер. Для временного IP-стейджинга —
`POKER8_ENV=staging` + `POKER8_OPEN_ACCESS=1` (гостевые ники `Guest-XXXXXX`),
затем обязательно вернуть `0`.

### Бэкап / восстановление

```bash
pg_dump "$POKER8_DATABASE_URL" --format=custom --file=poker8-backup.dump
pg_restore --dbname=postgresql://poker8:poker8@127.0.0.1:5432/poker8_restore poker8-backup.dump
```

Перед возвратом трафика проверить `/health/ready`, паузы рантаймов и
`integrity_events`.

### Целевой VPS

Доступы к серверу описаны в `servers.md` (помечен как секрет — **не коммитить,
не пересылать**): хост `64.188.67.9` / `share.play2go.cloud`, Ubuntu 26.04,
`root`, SSH-алиас `autorek`. Там уже развёрнут через `docker compose` другой
стек (`autorek` — Telegram-бот `@autoreklamaMAINbot`, каталог `/root/autorek`,
Postgres + Redis, без публичных портов/nginx/TLS). Для Poker8 Online на этом
же сервере учитывать: продукт слушает `:8000` и требует публичного HTTPS-домена
(reverse-proxy/TLS) для Telegram Mini App, тогда как autorek работает без
входящих портов — конфликтов по портам нет, но веб-фронт Poker8 нужно вынести
за nginx с сертификатом. Реальные пароли/ключи держать только в `servers.md` и
`.env` на сервере.

## Карта потока (из README)

```text
Profiles / Saved rooms → Table seats → Poker Engine → Bot manager → Persistence → Browser UI
```
