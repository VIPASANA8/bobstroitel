# Рефералы и profit share — состояние работы

Файл для продолжения с нуля, если сессия прервалась. Модель и решения —
в [referrals-and-profit-share.md](referrals-and-profit-share.md), здесь только
статус, проверки и следующий шаг.

Ветка: `claude/referral-system-profit-share-9a5a9b`
(worktree `C:\project\poker\.claude\worktrees\poker-stop-server-md-9779a2`).
В `main` **не влито и на прод не выкачено**.

Обновлено: 2026-09-07, после добавления Poker RevShare.

## Что сделано

Cube-ветка и Poker-ветка целиком:

| Область | Файлы |
|---|---|
| Привязка, коды, внутренние аккаунты | `cash/referrals.py` |
| Расчёт: сутки, carryover, hold, реверс, доля партнёра, обе ветки дохода | `cash/settlement.py` |
| Атрибуция рейка по игрокам | `poker/engine.py` (`_charge_rake`), `poker/models.py`, `online/serialization.py`, `cash/game.py` (`_settle`) |
| Таблицы + `users.internal` + `hand_players.rake_micros` + новые kind проводок | `online/schema.py`, `cash/ledger.py` |
| Миграции `20260907_0030`, `20260907_0031` | `migrations/versions/` |
| Вход по ссылке | `online/auth.py` (`start_param`), `app/routers/telegram.py` |
| API игрока | `app/routers/cash.py` → `GET /api/cash/referral` |
| Админка: отчёты, доля, расходы Cube, реверс | `cash/admin.py`, `app/routers/cash_admin.py` |
| Запуск раз в час | `cash/watchdog.py` (`_housekeeping`), `app/online.py` |
| Настройки | `online/config.py`: `POKER8_REFERRAL_HOLD_DAYS=7`, `POKER8_PARTNER_PERIOD=month`, `POKER8_INTERNAL_TELEGRAM_IDS` |

## Что проверено, а что нет

Прошло:

```bash
python -m pytest -q
```

**985 passed, 3 skipped** (2026-09-07). Сюда входят:

* `tests/cash/test_referral_math.py` — 17 тестов арифметики начислений
  (сценарии п.23 ТЗ, которым не нужна БД);
* `tests/cash/test_rake_attribution.py` — 12 тестов разбивки рейка по игрокам,
  включая сайд-поты, потолок в 3 больших блайнда, остатки от деления и
  сходимость суммы с `state.rake`;
* весь прежний набор тестов проекта — движок и escrow не сломаны.

**Не проверено:** `tests/cash/test_referrals.py` — 30 тестов на БД (привязка,
идемпотентность, hold и релиз, реверс, разделение Poker/Cube, carryover
партнёра, сходимость ledger). Они помечены `postgres` и по умолчанию отключены
(`pytest.ini`), а поднять сервис не вышло: движок Docker Desktop не запустился,
`com.docker.service` требует прав администратора. SQL всех запросов при этом
прогнан вручную на SQLite (проводки там недоступны — `CashLedger` работает
только на PostgreSQL).

**Это первый шаг для продолжения.** Запустить Docker Desktop, затем:

```bash
docker compose -f compose.yaml up -d postgres_test
```

```bash
POKER8_CASH_TEST_DATABASE_URL=postgresql+psycopg://poker8:poker8@localhost:5433/poker8_test python -m pytest tests/cash -m postgres -q
```

И миграции на копии боевой базы: `tools/cash_backup_restore_check.py`.

## Порядок выката

1. Прогнать postgres-тесты выше — они закрывают все денежные пути.
2. `git push origin HEAD:main`.
3. `ssh newvps "cd /opt/poker8 && sh deploy/poker8-update.sh donbass.win"` —
   миграции применяются при старте контейнера, ждём `ready:200`.
4. Задать долю партнёра (без неё расчёты партнёра просто не создаются):
   `POST /api/cash-admin/partner/share` с `effective_from`, `share_bps`,
   `reason` и заголовком `Idempotency-Key`.
5. Заполнить `POKER8_INTERNAL_TELEGRAM_IDS` (владельцы, партнёр, служебные) —
   иначе они смогут участвовать в реферальной программе как обычные игроки.
6. Проверить `GET /api/cash-admin/referrals` и `GET /api/cash-admin/partner`.

## Что осталось

* **UI.** Реферального экрана нет, только API `GET /api/cash/referral`
  (код, ссылка, приглашённые, начислено/выплачено, текущий carryover).
* **Старые раздачи.** `hand_players.rake_micros` заполняется только для
  раздач после миграции `20260907_0031`; по более ранним (там `NULL`) Poker
  RevShare не начисляется. Восстановить их нельзя — разбивка сайд-потов не
  сохранялась.
* **Реверс после релиза.** Возврат возможен только пока начисление `pending`.
  После релиза — ручная корректировка баланса оператором.
* **Реверс задним числом после расчёта партнёра.** Если начисление отменено
  уже после того, как период партнёра закрыт, доля посчитана со старым
  расходом; исправляется строкой `cube_adjustments`.
* **Бонусы.** Их в проекте нет. Когда появятся (депозитные, кэшбэк, рейкбэк,
  промокоды, задания) — совокупный эффект надо считать вместе с RevShare, см.
  «Почему антифрод здесь скромный» в модели.
* **Нагрузка.** Расчёт читает по строке на раунд и на игрока в раздаче за
  сутки (`ponytail:`-пометки в `cash/settlement.py`); при росте объёма это
  сворачивается в `GROUP BY` на стороне БД.
