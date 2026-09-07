# Рефералы и profit share — состояние работы

Файл для продолжения с нуля, если сессия прервалась. Модель и решения —
в [referrals-and-profit-share.md](referrals-and-profit-share.md), здесь только
статус, проверки и следующий шаг.

Ветка: `claude/referral-system-profit-share-9a5a9b`
(worktree `C:\project\poker\.claude\worktrees\poker-stop-server-md-9779a2`).
Коммит фазы 1: `3e8ef9f` — «feat(referrals): реферальная программа Cube и доля
партнёра». В `main` **не влито и на прод не выкачено**.

## Что уже сделано (фаза 1, Cube)

| Область | Файлы |
|---|---|
| Привязка, коды, внутренние аккаунты | `cash/referrals.py` |
| Расчёт: сутки, carryover, hold, реверс, доля партнёра | `cash/settlement.py` |
| Таблицы + `users.internal` + новые kind проводок | `online/schema.py`, `cash/ledger.py` |
| Миграция `20260907_0030` | `migrations/versions/20260907_0030_referrals.py` |
| Вход по ссылке | `online/auth.py` (`start_param`), `app/routers/telegram.py` |
| API игрока | `app/routers/cash.py` → `GET /api/cash/referral` |
| Админка: отчёты, доля, расходы Cube, реверс | `cash/admin.py`, `app/routers/cash_admin.py` |
| Запуск раз в час | `cash/watchdog.py` (`_housekeeping`), `app/online.py` |
| Настройки | `online/config.py`: `POKER8_REFERRAL_HOLD_DAYS=7`, `POKER8_PARTNER_PERIOD=month`, `POKER8_INTERNAL_TELEGRAM_IDS` |
| Тесты | `tests/cash/test_referral_math.py` (17, без БД), `tests/cash/test_referrals.py` (26, postgres) |

## Что проверено, а что нет

Прошло:

```bash
python -m pytest -q
```

973 passed, 3 skipped, 234 deselected (2026-09-07). Сюда входят 17 тестов
арифметики начислений и все прежние тесты проекта.

**Не проверено:** `tests/cash/test_referrals.py` — 26 тестов на БД (привязка,
идемпотентность расчёта, hold и релиз, реверс, carryover партнёра, сходимость
ledger). Они помечены `postgres` и по умолчанию отключены (`pytest.ini`), а
поднять сервис в той сессии не вышло: движок Docker Desktop не запустился,
`com.docker.service` требует прав администратора. SQL всех запросов при этом
прогнан вручную на SQLite (проводки там недоступны — `CashLedger` работает
только на PostgreSQL).

**Это и есть первый шаг для продолжения.** Запустить Docker Desktop, затем:

```bash
docker compose -f compose.yaml up -d postgres_test
```

```bash
POKER8_CASH_TEST_DATABASE_URL=postgresql+psycopg://poker8:poker8@localhost:5433/poker8_test python -m pytest tests/cash/test_referrals.py -m postgres -q
```

И миграция на копии боевой базы: `tools/cash_backup_restore_check.py`.

## Порядок выката

1. Прогнать postgres-тесты выше — они закрывают все денежные пути.
2. `git push origin HEAD:main`.
3. `ssh newvps "cd /opt/poker8 && sh deploy/poker8-update.sh donbass.win"` —
   миграция применяется при старте контейнера, ждём `ready:200`.
4. Задать долю партнёра (без неё расчёты партнёра просто не создаются):
   `POST /api/cash-admin/partner/share` с `effective_from`, `share_bps`,
   `reason` и заголовком `Idempotency-Key`.
5. Заполнить `POKER8_INTERNAL_TELEGRAM_IDS` (владельцы, партнёр, служебные) —
   иначе они смогут участвовать в реферальной программе как обычные игроки.
6. Проверить `GET /api/cash-admin/referrals` и `GET /api/cash-admin/partner`.

## Что осталось за фазой 1

* **Poker RevShare (фаза 2).** Не начат сознательно: на кэш-столах нет
  реального оборота. Требует: движок отдаёт разбивку рейка по игрокам, новая
  колонка `hand_players.rake_micros`, заполняемая в `cash/game.py::_settle`,
  и вторая ветка расчёта с `source='poker'` (в схеме уже разрешён). Метод
  атрибуции — contributed rake, точная формула в модели, раздел «Poker
  RevShare — вторая фаза». Важно: **задним числом разбивку не восстановить**,
  колонку надо завести до того, как пойдёт реальный оборот.
* **Активация по Poker.** `_activate` в `cash/settlement.py` берёт первый
  раунд Cube; когда откроются кэш-столы, туда добавляется первая кэш-раздача
  (одно `LEAST`, комментарий на месте).
* **UI.** Реферального экрана нет, только API `GET /api/cash/referral`
  (код, ссылка, приглашённые, начислено/выплачено, текущий carryover).
* **Реверс после релиза.** Возврат возможен только пока начисление `pending`.
  После релиза — ручная корректировка баланса оператором.
* **Реверс задним числом после расчёта партнёра.** Если начисление отменено
  уже после того, как период партнёра закрыт, доля посчитана со старым
  расходом; исправляется строкой `cube_adjustments`.
* **Бонусы.** Их в проекте нет. Когда появятся (депозитные, кэшбэк, рейкбэк,
  промокоды, задания) — совокупный эффект надо считать вместе с RevShare, см.
  раздел «Почему антифрод здесь скромный».
