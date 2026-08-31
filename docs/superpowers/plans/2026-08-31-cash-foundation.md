# CASH foundation — первый пакет реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. В текущем проекте выполнять последовательно через executing-plans; делегирование без отдельного разрешения не включать.

**Goal:** Добавить внутренний CASH_USDT-журнал с точным масштабом 1 USDT = 10 игровых единиц, атомарными проводками и PostgreSQL-проверками повторов, конкуренции и отката.

**Architecture:** Три новые таблицы в общей PostgreSQL-базе и небольшой модуль `cash/`. Существующие PLAY-кошельки, API, столы и пользовательские балансы не меняются. Кассовые и игровые сервисы следующих пакетов будут вызывать журнал внутри своих транзакций; сам журнал не подтверждает блокчейн-платежи и не отправляет деньги.

**Tech Stack:** Уже установленные Python, SQLAlchemy, Alembic, psycopg и pytest; новых зависимостей нет.

---

## Границы и безопасность выполнения

Спецификация: [cash-c2c-design](../specs/2026-08-31-cash-c2c-design.md).

Реализация первого пакета выполнена 2026-09-01 в ветке `codex/cash-foundation`. Кодовые блоки синхронизированы с реализацией; дополнительные проверки входят в перечисленные тестовые файлы. Фактические результаты и ограничения: [отчёт приёмки](../../cash-foundation-verification.md).

Результат пакета — проверенный внутренний журнал, а не готовый C2C, REAL CASH или вывод. Не создаются HTTP-эндпоинты пополнения, provider credentials, blockchain transactions, админ-бот или денежные столы. Не включаются приём денег и игровые CASH-режимы.

Счёт `clearing` — бухгалтерская сторона подтверждённого внешнего события; отрицательное значение такого счёта не означает кредит пользователю из faucet. Приведённые тестовые проводки имитируют внешние события. Ни один публичный клиент не может вызывать низкоуровневый `post` или создавать такой счёт. Контроль подлинности события, разрешения оператора и состояния заявки добавляются до подключения API в следующих пакетах.

При начале реализации проверить актуальные AGENTS.md, рабочую ветку и Alembic head. План составлен при head `20260831_0013`; если head изменился, сначала перебазировать номер/родителя новой миграции и EXPECTED_MIGRATION_REVISION, не создавать вторую голову. Изолированную ветку/рабочее дерево подготовить по using-git-worktrees. Не затрагивать пользовательские изображения и другие посторонние изменения.

Все команды ниже выполняются из `C:/project/poker` либо соответствующего изолированного рабочего дерева. Только `postgres_test` из существующего compose.yaml используется для денежных интеграционных тестов. Фикстура проверяет loopback, порт 5433 и имя `poker8_test`, создаёт собственную случайную схему и удаляет только её.

```powershell
docker compose up -d postgres_test
$env:POKER8_CASH_TEST_DATABASE_URL = 'postgresql+psycopg://poker8:poker8@localhost:5433/poker8_test'
```

Значения выше — уже существующие локальные тестовые настройки compose.yaml. Не подставлять production URL, не менять POKER8_DATABASE_URL и не запускать миграции на живой базе. Если локальный Docker/PostgreSQL недоступен, денежные проверки остаются невыполненными; их нельзя заменить успешным SQLite-прогоном или считать пропуск прохождением.

## Структура изменений

| Файл относительно корня | Назначение |
|---|---|
| `cash/__init__.py` | Пустой пакет, без побочных действий при импорте |
| `cash/amounts.py` | Точное преобразование строк USDT/CASH и целых micro-USDT |
| `cash/ledger.py` | Один внутренний примитив публикации сбалансированной операции |
| `online/schema.py` | Три CASH-таблицы в существующем metadata |
| `migrations/versions/20260831_0014_cash_foundation.py` | Независимая от текущего runtime-кода миграция |
| `app/online.py` | Только ожидаемая ревизия схемы; без подключения cash-сервисов |
| `tests/cash/conftest.py` | Изолированная PostgreSQL-схема и тестовые счета |
| `tests/cash/test_amounts.py` | Курс, точность и отбрасывание недопустимых входов |
| `tests/cash/test_migration.py` | Обновление исторической схемы и запрет уничтожения данных при downgrade |
| `tests/cash/test_cash_ledger.py` | Идемпотентность, нехватка средств, rollback и конкуренция |

Определения CASH-таблиц остаются в общем online/schema.py: проект уже использует его metadata. Так не появится циклическая регистрация моделей или вторая схема SQLAlchemy. Отдельные cash_accounts и cash_entries не объединяются с PLAY-таблицами.

## Task 1: Точные суммы и согласованный курс

**Files:** Create `cash/__init__.py`, `cash/amounts.py`, `tests/cash/test_amounts.py`.

- [x] **Step 1: Добавить тесты до реализации.**

```python
# tests/cash/test_amounts.py
import pytest

from cash.amounts import (
    MAX_MICROS, micros_to_units, micros_to_usdt,
    units_to_micros, usdt_to_micros,
)


def test_usdt_and_cash_are_two_denominations_of_the_same_amount():
    assert usdt_to_micros("1") == units_to_micros("10") == 1_000_000
    assert micros_to_units(usdt_to_micros("10.01")) == "100.1"
    assert micros_to_usdt(units_to_micros("100")) == "10"
    assert micros_to_units(usdt_to_micros("0.000001")) == "0.00001"
    assert micros_to_usdt(usdt_to_micros("0")) == "0"


@pytest.mark.parametrize("value", [
    "-1", "NaN", "Infinity", "1e2", "1,00", " 1", "1 ",
    "0.0000001", "", ".1", "+1", 1.1, 1, True, None,
    "9223372036854.775808",
])
def test_usdt_parser_rejects_ambiguous_or_inexact_input(value):
    with pytest.raises(ValueError):
        usdt_to_micros(value)


def test_cash_unit_precision_and_bigint_boundary():
    with pytest.raises(ValueError):
        units_to_micros("0.000001")
    assert usdt_to_micros(micros_to_usdt(MAX_MICROS)) == MAX_MICROS
    assert units_to_micros(micros_to_units(MAX_MICROS)) == MAX_MICROS
    for value in (-1, True, 1.5, MAX_MICROS + 1):
        with pytest.raises(ValueError):
            micros_to_usdt(value)
```

- [x] **Step 2: Проверить ожидаемое падение.**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/cash/test_amounts.py -q
```

Ожидается ошибка импорта cash.amounts: модуля ещё нет.

- [x] **Step 3: Создать пустой cash/__init__.py и реализацию преобразования.**

```python
# cash/amounts.py
import re

MAX_MICROS = 2**63 - 1
MICROS_PER_USDT = 1_000_000
MICROS_PER_CASH_UNIT = 100_000


def _parse(value: str, digits: int) -> int:
    if not isinstance(value, str) or len(value) > 32:
        raise ValueError("amount must be a plain decimal string")
    match = re.fullmatch(r"([0-9]+)(?:\.([0-9]{1," + str(digits) + r"}))?", value)
    if match is None:
        raise ValueError("invalid amount or excess precision")
    whole, fraction = match.groups()
    result = int(whole) * 10**digits + int((fraction or "").ljust(digits, "0"))
    if result > MAX_MICROS:
        raise ValueError("amount exceeds supported range")
    return result


def _format(value: int, digits: int) -> str:
    if type(value) is not int or not 0 <= value <= MAX_MICROS:
        raise ValueError("micros must be a nonnegative signed-bigint value")
    whole, fraction = divmod(value, 10**digits)
    if not fraction:
        return str(whole)
    return f"{whole}.{fraction:0{digits}d}".rstrip("0")


def usdt_to_micros(value: str) -> int:
    return _parse(value, 6)


def units_to_micros(value: str) -> int:
    return _parse(value, 5)


def micros_to_usdt(value: int) -> str:
    return _format(value, 6)


def micros_to_units(value: int) -> str:
    return _format(value, 5)
```

Курс не меняет минимальную фишку и блайнды автоматически. Модуль допускает нулевое представление баланса; положительность конкретного платежа проверяется его командой. Денежные float и bool не принимаются.

- [x] **Step 4: Повторить тестовую команду; все cases должны пройти.**
- [x] **Step 5: Зафиксировать только файлы этого шага.**

```powershell
git add -- cash/__init__.py cash/amounts.py tests/cash/test_amounts.py
git commit -m "feat: define exact cash denomination conversions"
```

## Task 2: CASH-таблицы и миграция без изменения PLAY

**Files:** Modify `online/schema.py`, `app/online.py`; create migration, `tests/cash/conftest.py`, `tests/cash/test_migration.py`.

- [x] **Step 1: Добавить PostgreSQL-фикстуру и миграционный тест.**

```python
# tests/cash/conftest.py
import asyncio
import os
import re
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from online.schema import (
    cash_accounts, metadata, play_accounts, tenants, users,
)


@pytest.fixture
def anyio_backend():
    return "asyncio", {"loop_factory": asyncio.SelectorEventLoop}


@pytest.fixture
async def cash_db(request, anyio_backend):
    raw_url = os.environ.get("POKER8_CASH_TEST_DATABASE_URL")
    if not raw_url:
        pytest.fail("Set POKER8_CASH_TEST_DATABASE_URL to the local postgres_test service")
    url = make_url(raw_url)
    if not (
        url.drivername == "postgresql+psycopg"
        and url.host in {"localhost", "127.0.0.1", "::1"}
        and url.port == 5433 and url.database == "poker8_test"
        and not url.query  # libpq query parameters can override host/port.
    ):
        pytest.fail("Refusing a database outside the local postgres_test target")
    schema = "cash_test_" + uuid4().hex
    schema_state = getattr(request, "param", "current")
    engine = create_async_engine(
        url, poolclass=NullPool,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        if schema_state == "empty":
            yield factory
            return
        async with engine.begin() as conn:
            selected = [tenants, users, play_accounts] if schema_state == "historical" else None
            await conn.run_sync(lambda sync: metadata.create_all(sync, tables=selected))
            await conn.execute(tenants.insert().values(id="tenant", slug="cash-test", name="Test"))
            await conn.execute(users.insert(), [
                {"id": "alice", "telegram_user_id": 1, "display_name": "Alice", "acquisition_tenant_id": "tenant"},
                {"id": "bob", "telegram_user_id": 2, "display_name": "Bob", "acquisition_tenant_id": "tenant"},
            ])
            await conn.execute(play_accounts.insert().values(
                id="play-sentinel", owner_kind="user", owner_id="alice",
                account_kind="wallet", balance_units=12345,
            ))
            if schema_state == "current":
                await conn.execute(cash_accounts.insert(), [
                    {"id": "external", "kind": "clearing", "user_id": None, "reference_id": "mock"},
                    {"id": "alice-wallet", "kind": "available", "user_id": "alice", "reference_id": "alice"},
                    {"id": "bob-wallet", "kind": "available", "user_id": "bob", "reference_id": "bob"},
                    {"id": "alice-seat", "kind": "escrow", "user_id": "alice", "reference_id": "occupancy-1"},
                    {"id": "alice-withdraw", "kind": "withdrawal", "user_id": "alice", "reference_id": "withdrawal-1"},
                ])
        yield factory
    finally:
        if not re.fullmatch(r"cash_test_[0-9a-f]{32}", schema):
            raise RuntimeError("unsafe test schema cleanup target")
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            await engine.dispose()
```

```python
# tests/cash/test_migration.py
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from online.schema import metadata

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]


def migrate(conn, direction):
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "migrations"))
    module = ScriptDirectory.from_config(config).get_revision("20260831_0014").module
    with Operations.context(MigrationContext.configure(conn)):
        getattr(module, direction)()


@pytest.mark.parametrize("cash_db", ["historical"], indirect=True)
async def test_upgrade_preserves_play_and_downgrade_refuses_cash_rows(cash_db):
    async with cash_db() as session:
        async with session.begin():
            conn = await session.connection()
            await conn.run_sync(lambda sync: migrate(sync, "upgrade"))
            names = await conn.run_sync(lambda sync: set(sa.inspect(sync).get_table_names()))
            assert {"cash_accounts", "cash_transactions", "cash_entries"} <= names
            assert await session.scalar(sa.text("SELECT balance_units FROM play_accounts WHERE id='play-sentinel'")) == 12345
            assert await session.scalar(sa.text("SELECT count(*) FROM cash_accounts")) == 0
            await conn.run_sync(assert_cash_schema_matches_metadata)
            await conn.run_sync(lambda sync: migrate(sync, "downgrade"))
            names = await conn.run_sync(lambda sync: set(sa.inspect(sync).get_table_names()))
            assert "cash_accounts" not in names
            await conn.run_sync(lambda sync: migrate(sync, "upgrade"))
            # A fresh install may already contain these tables because historical
            # migration 0001 uses current metadata; this upgrade must tolerate it.
            await conn.run_sync(lambda sync: migrate(sync, "upgrade"))
            await session.execute(sa.text("""
                INSERT INTO cash_accounts (id, kind, reference_id)
                VALUES ('probe', 'clearing', 'mock-probe')
            """))
            with pytest.raises(RuntimeError, match="cash data"):
                await conn.run_sync(lambda sync: migrate(sync, "downgrade"))
            assert await session.scalar(sa.text("SELECT count(*) FROM cash_accounts")) == 1


def assert_cash_schema_matches_metadata(conn):
    context = MigrationContext.configure(conn, opts={
        "include_object": lambda obj, name, type_, reflected, compare_to:
            type_ != "table" or name.startswith("cash_"),
        "compare_server_default": True,
    })
    assert compare_metadata(context, metadata) == []


@pytest.mark.parametrize("cash_db", ["empty"], indirect=True)
async def test_all_upgrades_on_empty_schema_keep_cash_disabled(cash_db):
    def upgrade_all(conn):
        scripts = ScriptDirectory(str(Path(__file__).resolve().parents[2] / "migrations"))
        with Operations.context(MigrationContext.configure(conn)):
            for revision in reversed(list(scripts.walk_revisions())):
                revision.module.upgrade()
        assert_cash_schema_matches_metadata(conn)

    async with cash_db() as session:
        async with session.begin():
            conn = await session.connection()
            await conn.run_sync(upgrade_all)
            for name in ("cash_accounts", "cash_transactions", "cash_entries"):
                assert await session.scalar(sa.text(f'SELECT count(*) FROM "{name}"')) == 0


async def test_downgrade_blocks_writers_before_checking_for_cash_data(cash_db):
    async with cash_db() as migration_session:
        async with migration_session.begin():
            conn = await migration_session.connection()
            with pytest.raises(RuntimeError, match="cash data"):
                await conn.run_sync(lambda sync: migrate(sync, "downgrade"))
            # Keep the migration transaction open: a concurrent first deposit
            # must not slip between its empty check and its table drops.
            with pytest.raises(sa.exc.OperationalError) as blocked:
                async with cash_db() as writer:
                    async with writer.begin():
                        await writer.execute(sa.text("SET LOCAL lock_timeout = '200ms'"))
                        await writer.execute(sa.text("""
                            INSERT INTO cash_accounts (id, kind, reference_id)
                            VALUES ('concurrent', 'clearing', 'concurrent')
                        """))
            assert blocked.value.orig.sqlstate == "55P03"
```

- [x] **Step 2: Выполнить тест до реализации.**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/cash/test_migration.py -m postgres -q
```

Ожидается ошибка импорта cash_accounts. После реализации ожидается PASS, без skips.

- [x] **Step 3: Добавить таблицы в конец online/schema.py.**

```python
cash_accounts = Table(
    "cash_accounts", metadata,
    Column("id", String(64), primary_key=True),
    Column("kind", String(32), nullable=False),
    Column("user_id", String(64), ForeignKey("users.id")),
    Column("reference_id", String(100), nullable=False),
    Column("balance_micros", BIGINT, nullable=False, server_default=text("0")),
    Column("created_at", timestamp, **created_at),
    UniqueConstraint("kind", "reference_id", name="uq_cash_account_reference"),
    CheckConstraint("kind IN ('available', 'escrow', 'withdrawal', 'clearing')", name="ck_cash_account_kind"),
    CheckConstraint("(kind = 'clearing' AND user_id IS NULL) OR (kind <> 'clearing' AND user_id IS NOT NULL)", name="ck_cash_account_owner"),
    CheckConstraint("kind = 'clearing' OR balance_micros >= 0", name="ck_cash_nonnegative"),
)

cash_transactions = Table(
    "cash_transactions", metadata,
    Column("id", String(32), primary_key=True),
    Column("scope", String(64), nullable=False),
    Column("idempotency_key", String(200), nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("reference_id", String(100), nullable=False),
    Column("actor", String(100), nullable=False),
    Column("created_at", timestamp, **created_at),
    UniqueConstraint("scope", "idempotency_key", name="uq_cash_transaction_key"),
    CheckConstraint("kind IN ('deposit', 'reserve', 'release', 'settlement', 'payout', 'adjustment')", name="ck_cash_transaction_kind"),
)

cash_entries = Table(
    "cash_entries", metadata,
    Column("transaction_id", String(32), ForeignKey("cash_transactions.id"), primary_key=True),
    Column("account_id", String(64), ForeignKey("cash_accounts.id"), primary_key=True),
    Column("amount_micros", BIGINT, nullable=False),
    Column("created_at", timestamp, **created_at),
    CheckConstraint("amount_micros <> 0", name="ck_cash_nonzero_entry"),
)
Index("ix_cash_entries_account", cash_entries.c.account_id)
```

Все CASH-таблицы фиксированно относятся к CASH_USDT: нет параметра валюты, которым можно подменить актив. FK записи журнала допускает только cash_accounts. Идентификаторы реальных счетов будет создавать серверный кассовый workflow; постоянные короткие ID здесь принадлежат только тестовым fixtures. Счета создаются с нулём; пополнение отражается проводкой.

- [x] **Step 4: Создать замороженную миграцию. Не импортировать текущие runtime-модели из миграции.**

```python
# migrations/versions/20260831_0014_cash_foundation.py
"""Add cash accounting tables without enabling cash operations."""
from alembic import op
import sqlalchemy as sa

revision = "20260831_0014"
down_revision = "20260831_0013"
branch_labels = None
depends_on = None


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "cash_accounts" not in tables:
        op.create_table(
            "cash_accounts",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("kind", sa.String(32), nullable=False),
            sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id")),
            sa.Column("reference_id", sa.String(100), nullable=False),
            sa.Column("balance_micros", sa.BIGINT(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("kind", "reference_id", name="uq_cash_account_reference"),
            sa.CheckConstraint("kind IN ('available', 'escrow', 'withdrawal', 'clearing')", name="ck_cash_account_kind"),
            sa.CheckConstraint("(kind = 'clearing' AND user_id IS NULL) OR (kind <> 'clearing' AND user_id IS NOT NULL)", name="ck_cash_account_owner"),
            sa.CheckConstraint("kind = 'clearing' OR balance_micros >= 0", name="ck_cash_nonnegative"),
        )
    if "cash_transactions" not in tables:
        op.create_table(
            "cash_transactions",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("scope", sa.String(64), nullable=False),
            sa.Column("idempotency_key", sa.String(200), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("kind", sa.String(32), nullable=False),
            sa.Column("reference_id", sa.String(100), nullable=False),
            sa.Column("actor", sa.String(100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("scope", "idempotency_key", name="uq_cash_transaction_key"),
            sa.CheckConstraint("kind IN ('deposit', 'reserve', 'release', 'settlement', 'payout', 'adjustment')", name="ck_cash_transaction_kind"),
        )
    if "cash_entries" not in tables:
        op.create_table(
            "cash_entries",
            sa.Column("transaction_id", sa.String(32), sa.ForeignKey("cash_transactions.id"), primary_key=True),
            sa.Column("account_id", sa.String(64), sa.ForeignKey("cash_accounts.id"), primary_key=True),
            sa.Column("amount_micros", sa.BIGINT(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint("amount_micros <> 0", name="ck_cash_nonzero_entry"),
        )
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("cash_entries")}
    if "ix_cash_entries_account" not in indexes:
        op.create_index("ix_cash_entries_account", "cash_entries", ["account_id"])


def downgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    # Keep the emptiness check and drops atomic against concurrent first writes.
    # Follow posting order: claim transaction, lock accounts, insert entries.
    lock_order = ("cash_transactions", "cash_accounts", "cash_entries")
    existing = [name for name in lock_order if name in tables]
    if bind.dialect.name == "postgresql" and existing:
        targets = ", ".join(f'"{name}"' for name in existing)
        bind.execute(sa.text(f"LOCK TABLE {targets} IN ACCESS EXCLUSIVE MODE"))
    names = ("cash_entries", "cash_transactions", "cash_accounts")
    for name in names:
        if name in tables and op.get_bind().execute(sa.text(f'SELECT 1 FROM "{name}" LIMIT 1')).first():
            raise RuntimeError("Refusing to delete cash data; disable the feature and keep its journal")
    for name in names:
        if name in tables:
            op.drop_table(name)
```

- [x] **Step 5: В app/online.py заменить только ожидаемую ревизию.**

```python
EXPECTED_MIGRATION_REVISION = "20260831_0014"
```

`create_app` продолжает создавать только PLAY runtime и сервисы. CashLedger не присваивается app.state, не передаётся в SeatingService и не подключается к авторизации.

- [x] **Step 6: Проверить миграцию и существующую защиту cash-off.**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/cash/test_migration.py -m postgres -q
.\.venv\Scripts\python.exe -m pytest tests/test_migration_head.py tests/online/test_no_cash_runtime.py tests/online/test_ledger.py -q
```

Ожидается PASS. Тест cash-off не удалять: новые внутренние таблицы не означают доступность денежных API или столов. Тест исторической миграции начинается с таблиц users/tenants/play_accounts, без CASH, поэтому проверяет настоящий путь upgrade, а не только текущий create_all.

- [x] **Step 7: Зафиксировать только изменения пакета схемы.**

```powershell
git add -- online/schema.py app/online.py migrations/versions/20260831_0014_cash_foundation.py tests/cash/conftest.py tests/cash/test_migration.py
git commit -m "feat: add isolated cash ledger schema"
```

## Task 3: Атомарная публикация и защита от повторов

**Files:** Create `cash/ledger.py`, `tests/cash/test_cash_ledger.py`.

Примитив получает уже существующие cash-account ID и уже проверенную сервером причину операции. Он не открывает кошелёк по произвольному пользовательскому запросу, не одобряет депозит/вывод и не завершает транзакцию вызывающего workflow. Начальная структура account/reference должна создаваться кассой; полноценные команды депозитов и выводов не входят в этот пакет.

- [x] **Step 1: Добавить проверки до реализации.**

```python
# tests/cash/test_cash_ledger.py
import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from cash.amounts import MAX_MICROS, micros_to_units
from cash.ledger import CashLedger, IdempotencyConflict, InsufficientCash
from online.ledger import PlayLedger
from online.schema import cash_accounts, cash_entries, cash_transactions

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]
ledger = CashLedger()


async def submit(factory, key, postings, *, kind="reserve", ref="test-ref", actor="system:test", gate=None):
    async with factory() as session:
        async with session.begin():
            if gate is not None:
                await session.connection()
                await gate.wait()
            return await ledger.post(
                session, scope="test", key=key, kind=kind,
                reference_id=ref, actor=actor, postings=postings,
            )


async def fund(factory, amount=10_000_000, key="deposit"):
    return await submit(
        factory, key, {"external": -amount, "alice-wallet": amount},
        kind="deposit", ref="mock-deposit",
    )


async def balances(factory):
    async with factory() as session:
        result = await session.execute(select(cash_accounts.c.id, cash_accounts.c.balance_micros))
        return dict(result.all())


async def transaction_count(factory):
    async with factory() as session:
        return await session.scalar(select(func.count()).select_from(cash_transactions))


async def assert_reconciled(factory):
    async with factory() as session:
        rows = (await session.execute(
            select(
                cash_accounts.c.id, cash_accounts.c.balance_micros,
                func.coalesce(func.sum(cash_entries.c.amount_micros), 0),
            )
            .outerjoin(cash_entries, cash_entries.c.account_id == cash_accounts.c.id)
            .group_by(cash_accounts.c.id, cash_accounts.c.balance_micros)
        )).all()
        assert all(balance == entry_sum for _, balance, entry_sum in rows)
        totals = (await session.execute(
            select(cash_transactions.c.id, func.sum(cash_entries.c.amount_micros), func.count(cash_entries.c.account_id))
            .outerjoin(cash_entries, cash_entries.c.transaction_id == cash_transactions.c.id)
            .group_by(cash_transactions.c.id)
        )).all()
        assert all(total == 0 and count >= 2 for _, total, count in totals)


async def test_cash_starts_at_zero_and_play_grants_do_not_change_it(cash_db):
    assert (await balances(cash_db))["alice-wallet"] == 0
    await PlayLedger(cash_db).grant("alice", 1_000, "play-only")
    assert await PlayLedger(cash_db).available_units("alice") == 13_345
    assert (await balances(cash_db))["alice-wallet"] == 0
    assert await transaction_count(cash_db) == 0


async def test_deposit_replay_preserves_amount_and_detects_changed_recipient(cash_db):
    first = await fund(cash_db, 10_010_000)
    replay = await submit(
        cash_db, "deposit", {"alice-wallet": 10_010_000, "external": -10_010_000},
        kind="deposit", ref="mock-deposit",
    )
    assert first.transaction_id == replay.transaction_id
    assert first.created and not replay.created
    assert micros_to_units((await balances(cash_db))["alice-wallet"]) == "100.1"
    with pytest.raises(IdempotencyConflict):
        await submit(cash_db, "deposit", {"bob-wallet": 10_010_000, "external": -10_010_000}, kind="deposit", ref="mock-deposit")
    with pytest.raises(IdempotencyConflict):
        await fund(cash_db, 11_000_000)
    with pytest.raises(IdempotencyConflict):
        await submit(cash_db, "deposit", {"alice-wallet": 10_010_000, "external": -10_010_000}, kind="deposit", ref="mock-deposit", actor="different-actor")
    assert await transaction_count(cash_db) == 1
    await assert_reconciled(cash_db)


@pytest.mark.parametrize("postings", [
    {"external": -1, "alice-wallet": 2},
    {"external": 0, "alice-wallet": 0},
    {"external": -1, "alice-wallet": True},
    {"external": -1.0, "alice-wallet": 1.0},
    {"external": -(MAX_MICROS + 1), "alice-wallet": MAX_MICROS + 1},
])
async def test_invalid_postings_do_not_write_anything(cash_db, postings):
    with pytest.raises(ValueError):
        await submit(cash_db, "invalid", postings)
    assert await transaction_count(cash_db) == 0
    assert all(value == 0 for value in (await balances(cash_db)).values())


async def test_missing_account_does_not_leave_an_operation(cash_db):
    with pytest.raises(ValueError, match="unknown cash account"):
        await submit(cash_db, "missing", {"external": -1, "missing": 1})
    assert await transaction_count(cash_db) == 0


async def test_reserve_and_idempotent_release(cash_db):
    await fund(cash_db)
    await submit(cash_db, "reserve", {"alice-wallet": -7_000_000, "alice-withdraw": 7_000_000})
    before = await balances(cash_db)
    assert before["alice-wallet"] == 3_000_000 and before["alice-withdraw"] == 7_000_000
    first = await submit(cash_db, "release", {"alice-withdraw": -7_000_000, "alice-wallet": 7_000_000}, kind="release")
    replay = await submit(cash_db, "release", {"alice-withdraw": -7_000_000, "alice-wallet": 7_000_000}, kind="release")
    assert first.created and not replay.created
    assert (await balances(cash_db))["alice-wallet"] == 10_000_000
    assert (await balances(cash_db))["alice-withdraw"] == 0
    assert await transaction_count(cash_db) == 3
    await assert_reconciled(cash_db)


async def test_outer_rollback_removes_claim_entries_and_projection(cash_db):
    with pytest.raises(RuntimeError, match="workflow rollback"):
        async with cash_db() as session:
            async with session.begin():
                await ledger.post(session, scope="test", key="rollback", kind="deposit", reference_id="mock-deposit", actor="system:test", postings={"external": -100, "alice-wallet": 100})
                raise RuntimeError("workflow rollback")
    assert await transaction_count(cash_db) == 0
    assert (await balances(cash_db))["alice-wallet"] == 0
    assert (await fund(cash_db, 100, key="rollback")).created
    await assert_reconciled(cash_db)


async def test_failed_operation_can_be_retried_in_same_outer_transaction(cash_db):
    async with cash_db() as session:
        async with session.begin():
            command = dict(scope="test", key="reserve", kind="reserve", reference_id="seat", actor="system:test", postings={"alice-wallet": -100, "alice-seat": 100})
            with pytest.raises(InsufficientCash):
                await ledger.post(session, **command)
            assert await session.scalar(select(func.count()).select_from(cash_transactions)) == 0
            await ledger.post(session, scope="test", key="deposit", kind="deposit", reference_id="mock", actor="system:test", postings={"external": -100, "alice-wallet": 100})
            assert (await ledger.post(session, **command)).created
    assert (await balances(cash_db))["alice-seat"] == 100
    await assert_reconciled(cash_db)


async def test_concurrent_duplicate_callbacks_credit_once(cash_db):
    gate = asyncio.Barrier(8)
    tasks = [asyncio.create_task(submit(
        cash_db, "same-event", {"external": -10_000_000, "alice-wallet": 10_000_000},
        kind="deposit", gate=gate,
    )) for _ in range(8)]
    results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=15)
    assert sum(result.created for result in results) == 1
    assert len({result.transaction_id for result in results}) == 1
    assert (await balances(cash_db))["alice-wallet"] == 10_000_000
    assert await transaction_count(cash_db) == 1
    await assert_reconciled(cash_db)


async def test_buyin_and_withdrawal_cannot_spend_the_same_money(cash_db):
    await fund(cash_db)
    gate = asyncio.Barrier(2)
    tasks = [
        asyncio.create_task(submit(cash_db, "buyin", {"alice-wallet": -8_000_000, "alice-seat": 8_000_000}, gate=gate)),
        asyncio.create_task(submit(cash_db, "withdraw", {"alice-wallet": -8_000_000, "alice-withdraw": 8_000_000}, gate=gate)),
    ]
    results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=15)
    assert sum(isinstance(result, InsufficientCash) for result in results) == 1
    assert sum(not isinstance(result, BaseException) for result in results) == 1
    result = await balances(cash_db)
    assert result["alice-wallet"] == 2_000_000
    assert result["alice-seat"] + result["alice-withdraw"] == 8_000_000
    assert await transaction_count(cash_db) == 2
    await assert_reconciled(cash_db)


async def test_concurrent_distinct_deposits_do_not_lose_an_update(cash_db):
    await asyncio.wait_for(asyncio.gather(fund(cash_db, key="one"), fund(cash_db, key="two")), timeout=15)
    assert (await balances(cash_db))["alice-wallet"] == 20_000_000
    assert await transaction_count(cash_db) == 2
    await assert_reconciled(cash_db)


async def test_balance_overflow_rolls_back_the_whole_operation(cash_db):
    await fund(cash_db, MAX_MICROS)
    with pytest.raises(ValueError, match="range"):
        await fund(cash_db, 1, key="overflow")
    assert (await balances(cash_db))["alice-wallet"] == MAX_MICROS
    assert await transaction_count(cash_db) == 1
    await assert_reconciled(cash_db)


async def test_post_requires_caller_transaction(cash_db):
    async with cash_db() as session:
        with pytest.raises(ValueError, match="caller's transaction"):
            await ledger.post(
                session, scope="test", key="no-transaction", kind="deposit",
                reference_id="mock", actor="system:test",
                postings={"external": -100, "alice-wallet": 100},
            )
    assert await transaction_count(cash_db) == 0


async def test_post_refuses_sqlite_even_inside_transaction():
    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with async_sessionmaker(engine)() as session:
            async with session.begin():
                with pytest.raises(ValueError, match="PostgreSQL row locks"):
                    await ledger.post(
                        session, scope="test", key="sqlite", kind="deposit",
                        reference_id="mock", actor="system:test",
                        postings={"external": -100, "alice-wallet": 100},
                    )
    finally:
        await engine.dispose()


@pytest.mark.parametrize("changed", [
    {"kind": "adjustment"}, {"reference_id": "different-event"},
])
async def test_retry_is_bound_to_operation_kind_and_reference(cash_db, changed):
    command = dict(
        scope="test", key="event", kind="deposit", reference_id="mock",
        actor="system:test", postings={"external": -100, "alice-wallet": 100},
    )
    async with cash_db() as session:
        async with session.begin():
            await ledger.post(session, **command)
            with pytest.raises(IdempotencyConflict):
                await ledger.post(session, **(command | changed))
    assert await transaction_count(cash_db) == 1
    assert (await balances(cash_db))["alice-wallet"] == 100
    await assert_reconciled(cash_db)


async def test_same_key_in_distinct_scopes_is_independent(cash_db):
    async with cash_db() as session:
        async with session.begin():
            for scope in ("provider-a", "provider-b"):
                receipt = await ledger.post(
                    session, scope=scope, key="event", kind="deposit",
                    reference_id="mock", actor="system:test",
                    postings={"external": -100, "alice-wallet": 100},
                )
                assert receipt.created
    assert await transaction_count(cash_db) == 2
    assert (await balances(cash_db))["alice-wallet"] == 200
    await assert_reconciled(cash_db)
```

- [x] **Step 2: Выполнить тест до реализации.**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/cash/test_cash_ledger.py -m postgres -q
```

Ожидается ошибка импорта cash.ledger.

- [x] **Step 3: Создать денежный примитив.**

```python
# cash/ledger.py
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from cash.amounts import MAX_MICROS
from online.schema import cash_accounts, cash_entries, cash_transactions


class InsufficientCash(ValueError):
    pass


class IdempotencyConflict(ValueError):
    pass


@dataclass(frozen=True)
class CashReceipt:
    transaction_id: str
    created: bool


def _identifier(value: str, limit: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("invalid cash operation identifier")


class CashLedger:
    ASSET = "CASH_USDT"
    KINDS = {"deposit", "reserve", "release", "settlement", "payout", "adjustment"}

    async def post(
        self, session: AsyncSession, *, scope: str, key: str, kind: str,
        reference_id: str, actor: str, postings: Mapping[str, int],
    ) -> CashReceipt:
        """Post inside the caller's READ COMMITTED transaction.

        The caller authenticates the reason and owns commit/rollback. A receipt
        is provisional until that commit; external effects must wait for it.
        Pass all affected accounts in one call where possible. If an outer
        workflow deadlocks, retry that entire transaction with the same key.
        """
        if session.get_bind().dialect.name != "postgresql":
            raise ValueError("cash posting requires PostgreSQL row locks")
        if not session.in_transaction():
            raise ValueError("cash posting requires the caller's transaction")
        for value, limit in ((scope, 64), (key, 200), (reference_id, 100), (actor, 100)):
            _identifier(value, limit)
        if not isinstance(kind, str) or kind not in self.KINDS:
            raise ValueError("invalid cash operation kind")
        if not isinstance(postings, Mapping) or len(postings) < 2:
            raise ValueError("cash postings must contain at least two accounts")
        amounts = dict(postings)
        for account_id, amount in amounts.items():
            _identifier(account_id, 64)
            if type(amount) is not int or amount == 0 or abs(amount) > MAX_MICROS:
                raise ValueError("cash postings require nonzero signed integer micros in range")
        if sum(amounts.values()) != 0:
            raise ValueError("cash postings must balance to zero")
        payload = json.dumps(
            {"kind": kind, "reference_id": reference_id, "actor": actor, "postings": sorted(amounts.items())},
            sort_keys=True, separators=(",", ":"),
        )
        fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        # A failed operation must not poison a caller that catches the error.
        # The outer transaction still owns commit/rollback of its workflow.
        async with session.begin_nested():
            transaction_id = uuid4().hex
            claimed = await session.scalar(
                insert(cash_transactions).values(
                    id=transaction_id, scope=scope, idempotency_key=key,
                    request_hash=fingerprint, kind=kind,
                    reference_id=reference_id, actor=actor,
                )
                .on_conflict_do_nothing(index_elements=["scope", "idempotency_key"])
                .returning(cash_transactions.c.id)
            )
            if claimed is None:
                existing = (await session.execute(
                    select(cash_transactions.c.id, cash_transactions.c.request_hash).where(
                        cash_transactions.c.scope == scope,
                        cash_transactions.c.idempotency_key == key,
                    )
                )).mappings().one()
                if existing["request_hash"] != fingerprint:
                    raise IdempotencyConflict("same cash key with different content")
                return CashReceipt(existing["id"], False)

            ids = sorted(amounts)
            accounts = (await session.execute(
                select(cash_accounts)
                .where(cash_accounts.c.id.in_(ids))
                .order_by(cash_accounts.c.id)
                .with_for_update()
            )).mappings().all()
            if len(accounts) != len(ids):
                raise ValueError("unknown cash account")
            updated = {}
            for account in accounts:
                balance = int(account["balance_micros"]) + amounts[account["id"]]
                if not -MAX_MICROS <= balance <= MAX_MICROS:
                    raise ValueError("cash balance exceeds supported range")
                if account["kind"] != "clearing" and balance < 0:
                    raise InsufficientCash("insufficient available or reserved cash")
                updated[account["id"]] = balance

            await session.execute(cash_entries.insert(), [
                {"transaction_id": transaction_id, "account_id": account_id, "amount_micros": amounts[account_id]}
                for account_id in ids
            ])
            for account_id in ids:
                await session.execute(
                    update(cash_accounts).where(cash_accounts.c.id == account_id)
                    .values(balance_micros=updated[account_id])
                )
            return CashReceipt(transaction_id, True)
```

Требуется стандартная изоляция READ COMMITTED. Блокировки берутся в стабильном порядке. Claim уникального ключа и все изменения находятся в одной транзакции; конкурирующий повтор ждёт её исхода. Все проверки балансов выполняются после блокировок. `created=False` означает повтор уже опубликованной в транзакции операции: вызывающий workflow не должен второй раз менять стек или статус бизнес-объекта.

Одна денежная бизнес-операция должна по возможности передавать все счета одним post. Если будущий workflow удерживает блокировки нескольких post или других таблиц, порядок блокировок проверяется для всей транзакции; локальная сортировка внутри post не доказывает отсутствие любых deadlock. Повтор после SQLSTATE 40001/40P01 относится ко всей откатившейся бизнес-транзакции с тем же ключом, а не к повторной отправке внешнего перевода.

Запись считается внешне завершённой только после commit вызывающего workflow. Нельзя отправлять уведомление «успешно» или делать внешний payout на основании receipt до commit. Вызовы сети не выполняются внутри удерживаемых денежных блокировок.

Здесь нет функций UPDATE/DELETE для cash_entries и cash_transactions: исправления идут новой проводкой. Эта гарантия относится к штатному приложению, не к администратору БД. До live-подключения обязателен отдельный проверенный режим прав БД: прикладной роли запрещаются UPDATE/DELETE опубликованного журнала; привилегированные миграции и обслуживание используют другую роль. Пакет не заявляет защиту от владельца базы или скомпрометированного сервисного SQL-доступа.

- [x] **Step 4: Выполнить денежные тесты на PostgreSQL.**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/cash/test_cash_ledger.py -m postgres -q
```

Ожидается PASS без skips. Нехватка средств должна быть доменной ошибкой InsufficientCash, не необработанным конфликтом уникальности, deadlock или отрицательным балансом. Тесты проверяют и общий баланс каждой операции, и соответствие каждой проекции сумме проводок.

- [x] **Step 5: Зафиксировать денежный примитив и проверки.**

```powershell
git add -- cash/ledger.py tests/cash/test_cash_ledger.py
git commit -m "feat: post cash entries atomically with content-bound retries"
```

## Task 4: Приёмка пакета и граница следующей работы

**Files:** Review все изменённые файлы и соответствие исходной спецификации. Новые runtime-функции на этом шаге не добавлять.

- [x] **Step 1: Проверить всю локальную регрессию и cash-off.**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Ожидается PASS. Существующий pytest.ini по умолчанию исключает PostgreSQL и e2e: этот результат сам по себе не означает денежную приёмку.

- [x] **Step 2: Отдельно проверить обязательные денежные сценарии.**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/cash -m postgres -q
.\.venv\Scripts\python.exe -m pytest tests/cash/test_amounts.py -q
.\.venv\Scripts\python.exe -m alembic heads
git diff --check
git status --short
```

Ожидается PASS без пропуска PostgreSQL-проверок, одна миграционная голова и отсутствие неожиданных файлов. Пустой git diff после commit не заменяет просмотр самих commit-ов. Если есть unrelated failure, воспроизвести его на исходной базе ветки и отдельно указать пользователю; не приписывать пакету непроверенное прохождение всей регрессии.

- [x] **Step 3: Проверить код без добавления функций вне пакета.**

Проверка покрывает: совпадение миграции и metadata, точность курса, отсутствие float/auto-rounding, все пути после конфликтов и rollback, стабильный порядок блокировок, неизменность PLAY, отсутствие публичного пути создания cash, отсутствие ключей и сетевых платёжных запросов. Использовать requesting-code-review только в рамках разрешённого процесса; автоматическое делегирование не подразумевается.

- [x] **Step 4: Передать фактический результат.**

В отчёте указать применённые миграции только тестовых схем, команды и результаты, известные ограничения. Не писать «C2C работает»: адаптер ещё не подключён. Не писать «вывод работает»: здесь протестирован бухгалтерский резерв, не отправка денег. Если PostgreSQL не был доступен, пакет не считать принятым.

После принятия этого пакета следующий самостоятельный план описывает режим CASH_USDT у стола, подтверждённую идентичность и исключение системных игроков. Затем идёт точная игровая арифметика и восстановление; после них полный C2C mock-цикл, операторский API/бот и клиент. Фиатный P2P остаётся после C2C-приёмки. В этом плане ни один из следующих пакетов не считается реализованным.
