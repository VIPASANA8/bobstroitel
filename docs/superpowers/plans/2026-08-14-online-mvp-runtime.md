# Poker8 Authoritative Table Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single global hand with recoverable per-table runtimes, FIFO seating, authenticated personalized WebSockets, server timers, and idempotent hand settlement.

**Architecture:** Every table is an independently locked state machine backed by a private serialized `GameState`, a monotonically increasing revision, and a persistent command journal. The server publishes viewer-specific snapshots, runs system players and deadlines, and settles stack deltas through the play ledger.

**Tech Stack:** Existing PokerEngine and bots, Python asyncio, FastAPI WebSocket, SQLAlchemy async, PostgreSQL JSONB, pytest, Starlette TestClient.

---

### Task 1: Make the engine explicitly 6-max and use a cryptographic shuffle

**Files:**
- Modify: `poker/deck.py`
- Modify: `poker/engine.py`
- Modify: `tests/test_multiway.py`
- Create: `tests/online/test_engine_contract.py`

- [ ] **Step 1: Write failing 6-max and shuffle-injection tests**

Create `tests/online/test_engine_contract.py`:

```python
import pytest

from poker.deck import Deck
from poker.engine import InvalidAction, PokerEngine


def _seats(count):
    return [
        {"id": f"p{seat}", "name": f"P{seat}", "seat": seat, "stack": 100.0, "is_bot": False}
        for seat in range(count)
    ]


def test_engine_rejects_a_seventh_player():
    with pytest.raises(InvalidAction, match="2 to 6"):
        PokerEngine().new_hand(_seats(7), button_seat=0)


def test_deck_can_restore_an_exact_remaining_order():
    deck = Deck.from_remaining(["As", "Kh", "2c"])
    assert deck.draw(2) == ["2c", "Kh"]
    assert deck.cards == ["As"]
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_engine_contract.py -q
```

Expected: the 7-player hand is accepted and `Deck.from_remaining` is missing.

- [ ] **Step 3: Implement the deck contract**

Change `poker/deck.py` to use `random.SystemRandom().shuffle(cards)` for a new deck and add:

```python
@classmethod
def from_remaining(cls, cards: list[str]) -> "Deck":
    deck = cls.__new__(cls)
    deck.cards = list(cards)
    return deck
```

Change the engine occupancy check to `2 <= len(occupied) <= 6`, remove the 7-player position map, and use the message `A Poker8 hand requires 2 to 6 players`.

Update legacy multiway fixtures that intentionally exercised seven players to use six seats and the 6-max positions `BTN, SB, BB, UTG, HJ, CO`. Keep the existing side-pot scenarios otherwise unchanged.

- [ ] **Step 4: Run engine tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_engine.py tests/test_multiway.py tests/online/test_engine_contract.py -q
```

Expected: all focused tests pass.

- [ ] **Step 5: Commit**

```powershell
git add poker/deck.py poker/engine.py tests/test_multiway.py tests/online/test_engine_contract.py
git commit -m "feat: harden six max engine shuffle"
```

### Task 2: Add lossless private game-state serialization

**Files:**
- Create: `online/serialization.py`
- Create: `tests/online/test_serialization.py`

- [ ] **Step 1: Write a failing round-trip test**

Create `tests/online/test_serialization.py`:

```python
from poker.engine import PokerEngine
from poker.models import ActionType
from online.serialization import deserialize_state, serialize_state


def test_private_snapshot_round_trip_continues_the_same_hand():
    engine = PokerEngine()
    seats = [
        {"id": "u1", "name": "One", "seat": 0, "stack": 100.0, "is_bot": False},
        {"id": "u2", "name": "Two", "seat": 1, "stack": 100.0, "is_bot": False},
    ]
    original = engine.new_hand(seats, button_seat=0)
    actor = original.acting_player
    restored = deserialize_state(serialize_state(original))

    assert restored.deck.cards == original.deck.cards
    assert restored.players["u1"].hole_cards == original.players["u1"].hole_cards
    assert restored.pending_actions == original.pending_actions

    engine.apply_action(original, actor, ActionType.CALL)
    engine.apply_action(restored, actor, ActionType.CALL)
    assert serialize_state(restored) == serialize_state(original)
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_serialization.py -q
```

Expected: import failure for `online.serialization`.

- [ ] **Step 3: Implement explicit serializers**

`serialize_state(state)` must return JSON-safe dictionaries for every `GameState`, `PlayerState`, and `Action` field, including:

```text
hand_id, street, pot, board, all private hole cards, seat_order,
button, acting_player, blind players, current_bet, min_raise_size,
last_aggressor, pending_actions, winner, winners, result text/details,
terminal, history, decision_reviews, difficulty, starting_stacks, remaining deck cards
```

`deserialize_state(payload)` must reconstruct the dataclasses, `Street` and `ActionType` enums, pending-action set, and `Deck.from_remaining(payload["deck_cards"])`. Do not use the public `GameState.to_dict` because it intentionally hides cards.

- [ ] **Step 4: Run serialization and engine suites**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_serialization.py tests/test_engine.py tests/test_multiway.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add online/serialization.py tests/online/test_serialization.py
git commit -m "feat: serialize recoverable poker hands"
```

### Task 3: Add runtime persistence and command journal tables

**Files:**
- Modify: `online/schema.py`
- Create: `migrations/versions/20260814_0002_table_runtime.py`
- Create: `tests/online/test_runtime_schema.py`

- [ ] **Step 1: Write failing metadata assertions**

Create `tests/online/test_runtime_schema.py`:

```python
from online.schema import game_commands, hand_actions, hand_players, hands, integrity_events, table_runtimes


def test_runtime_schema_has_recovery_and_idempotency_keys():
    assert table_runtimes.c.table_id.primary_key
    assert table_runtimes.c.revision.nullable is False
    assert {column.name for column in game_commands.primary_key.columns} == {"table_id", "command_id"}
    assert "private_state_json" in table_runtimes.c
    assert "public_payload_json" in integrity_events.c
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_runtime_schema.py -q
```

Expected: missing schema symbols.

- [ ] **Step 3: Add exact runtime tables**

Extend `online/schema.py` and migration `20260814_0002` with:

```text
table_runtimes(table_id PK/FK, revision BIGINT, phase CHECK waiting/active/result/countdown/paused,
  private_state_json JSON, action_deadline, result_clear_at, next_hand_at, paused_reason, updated_at)
game_commands(table_id PK/FK, command_id PK, user_id FK, expected_revision BIGINT,
  command_type, payload_json JSON, status CHECK accepted/rejected, result_json JSON, created_at)
hands(id PK, table_id FK, revision_started, button_seat, board_json, result_json,
  started_at, completed_at, terminal)
hand_players(hand_id PK/FK, participant_id PK, user_id nullable FK, system_player_id nullable FK,
  seat_no, position, start_stack_units, end_stack_units, hole_cards_json, shown, folded, net_units)
hand_actions(hand_id PK/FK, sequence PK, participant_id, street, action, amount_units,
  pot_before_units, pot_after_units, to_call_before_units, created_at)
integrity_events(id PK, tenant_id nullable FK, table_id nullable FK, hand_id nullable FK,
  user_id nullable FK, event_type, public_payload_json JSON, created_at)
```

Create indexes for incomplete hands, runtime deadlines, and integrity events by user/time.

- [ ] **Step 4: Run migration and schema tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_runtime_schema.py -q
$env:POKER8_DATABASE_URL='postgresql+psycopg://poker8:poker8@127.0.0.1:5432/poker8'
.\.venv\Scripts\alembic.exe upgrade head
```

Expected: test passes and PostgreSQL reaches revision `20260814_0002`.

- [ ] **Step 5: Commit**

```powershell
git add online/schema.py migrations/versions/20260814_0002_table_runtime.py tests/online/test_runtime_schema.py
git commit -m "feat: persist table runtime commands"
```

### Task 4: Implement FIFO seating, escrow, and system-player replacement

**Files:**
- Create: `online/seating.py`
- Test: `tests/online/test_seating.py`

- [ ] **Step 1: Write failing seating-state tests**

Create `tests/online/test_seating.py` with asynchronous tests covering these exact assertions:

```python
@pytest.mark.anyio
async def test_ready_appends_fifo_and_reserves_nothing(seating, ledger, user_a, table_id):
    request = await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    assert request.state == "waiting"
    assert await ledger.available_units(user_a) == 100_000


@pytest.mark.anyio
async def test_boundary_seats_first_request_and_replaces_system_player(seating, table_id, user_a, user_b):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.ready(user_b, table_id, seat_no=2, buy_in_units=4_000)
    result = await seating.process_boundary(table_id)
    assert result.seated_user_ids == [user_a]
    assert result.removed_system_player_ids


@pytest.mark.anyio
async def test_same_user_cannot_hold_two_network_seats(seating, user_a, table_id, second_table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    with pytest.raises(AlreadySeated):
        await seating.ready(user_a, second_table_id, seat_no=1, buy_in_units=4_000)
```

Use `@pytest.mark.anyio` on each async test.

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_seating.py -q
```

Expected: import failure for `online.seating`.

- [ ] **Step 3: Implement the seating service**

`SeatingService` must provide these concrete operations:

```text
ready(user_id, table_id, seat_no, buy_in_units)
cancel_ready(user_id, table_id)
process_boundary(table_id)
mark_disconnected(user_id, table_id, now)
reconnect(user_id, table_id)
request_observe(user_id, table_id)
request_leave(user_id, table_id)
add_on(user_id, table_id, amount_units)
expire_holds(table_id, now)
```

`ready` validates a 40–100 BB buy-in but does not reserve funds. `process_boundary` opens one database transaction, locks the table seats and waiting queue, revalidates the wallet, calls `reserve_buy_in(user_id, table_id, requested_buy_in_units, idempotency_key, session=session)`, calls `release_system_seat(system_player_id, table_id, idempotency_key, session=session)` when a human replaces a bot, and seats requests by `position_seq`. An unavailable requested chair falls back to the lowest free chair. A full table keeps the request waiting. If a waiting observer has no live connection, mark that request `expired`; if its wallet is no longer sufficient, mark it `cancelled` and continue to the next FIFO request instead of blocking the queue.

`request_observe` and `request_leave` mark the seat `leaving`; `process_boundary` returns its full escrow balance and clears it. Add-on executes only in a non-active phase and cannot raise the stack above 100 BB. When refilling an empty seat, select an unused system player matching the table's difficulty mix and call `fund_system_seat(system_player_id, table_id, 100 * big_blind_units, idempotency_key, session=session)` before seating it.

- [ ] **Step 4: Run seating and ledger tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_seating.py tests/online/test_ledger.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add online/seating.py tests/online/test_seating.py
git commit -m "feat: add boundary safe seat queue"
```

### Task 5: Implement the per-table command runtime

**Files:**
- Create: `online/runtime.py`
- Create: `online/events.py`
- Test: `tests/online/test_runtime.py`

- [ ] **Step 1: Write failing revision and duplicate-command tests**

Create `tests/online/test_runtime.py`:

```python
@pytest.mark.anyio
async def test_table_commands_are_serial_and_idempotent(runtime, human_turn):
    first = await runtime.action(
        table_id=human_turn.table_id,
        user_id=human_turn.user_id,
        command_id="cmd-1",
        expected_revision=human_turn.revision,
        action="call",
        amount_units=0,
    )
    duplicate = await runtime.action(
        table_id=human_turn.table_id,
        user_id=human_turn.user_id,
        command_id="cmd-1",
        expected_revision=human_turn.revision,
        action="call",
        amount_units=0,
    )
    assert duplicate == first
    assert runtime.engine_action_count(human_turn.table_id) == 1


@pytest.mark.anyio
async def test_stale_revision_returns_current_snapshot(runtime, human_turn):
    with pytest.raises(StaleRevision) as error:
        await runtime.action(human_turn.table_id, human_turn.user_id, "cmd-stale", 0, "fold", 0)
    assert error.value.current_revision == human_turn.revision


@pytest.mark.anyio
@pytest.mark.parametrize("difficulty", ["easy", "normal", "hard", "maximum"])
async def test_system_step_is_legal_at_every_difficulty(runtime, system_turn_factory, difficulty):
    turn = await system_turn_factory(difficulty)
    result = await runtime.system_step(turn.table_id)
    assert result.action in turn.legal_actions
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_runtime.py -q
```

Expected: import failure for `online.runtime`.

- [ ] **Step 3: Implement `TableRuntimeManager`**

The manager owns one `asyncio.Lock` per table and provides:

```text
load(table_id)
start_hand(table_id)
public_snapshot(table_id, viewer_user_id)
action(table_id, user_id, command_id, expected_revision, action, amount_units)
system_step(table_id)
timeout_current_actor(table_id, now)
finish_and_settle(table_id)
pause(table_id, reason)
restore_all()
```

Inside the table lock, `action` must:

1. return a stored result for an existing `(table_id, command_id)`;
2. reject mismatched `expected_revision` without mutating state;
3. map the authenticated user to exactly one participant;
4. validate that participant is the acting player;
5. convert `amount_units` from integer hundredths to the engine's chip amount and call `PokerEngine.apply_action`;
6. increment the revision once;
7. persist the private snapshot and command record in one transaction;
8. append a privacy-safe integrity event;
9. publish the new revision only after commit.

Capture `before = serialize_state(state)` before step 5. If persistence or ledger work fails after the in-memory mutation, restore `before`, set the table to `paused` with the failure reason, write an integrity event in a fresh transaction, and publish no new revision. A failed database commit must never leave memory ahead of durable state.

Route server-generated bot and timeout actions through the same command journal with deterministic IDs `system:{hand_id}:{revision}` and `timeout:{hand_id}:{revision}`. If a scheduler task fires twice or restarts after commit, the second call returns the stored result without applying another action.

`public_snapshot` calls `GameState.to_dict(viewer_player_id=participant_id)`, removes bot difficulty, and adds table phase, revision, legal actions for that viewer, deadlines, occupancy, and current user's queue/seat state. It never exposes another player's private cards or the private snapshot JSON.

`system_step` builds the bot decision input from that system participant's viewer-specific snapshot, public action history, and recency-weighted opponent model only. Do not pass the runtime object, `Deck`, remaining cards, other hole cards, Telegram identity, or integrity events into bot code.

- [ ] **Step 4: Run concurrent runtime tests**

Add a test using `asyncio.gather` to submit two different command IDs against one revision. Assert exactly one succeeds and the other receives `StaleRevision`.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_runtime.py -q
```

Expected: all runtime tests pass.

- [ ] **Step 5: Commit**

```powershell
git add online/runtime.py online/events.py tests/online/test_runtime.py
git commit -m "feat: serialize authoritative table commands"
```

### Task 6: Settle hands, history, wins, and bot opponent models

**Files:**
- Create: `online/history.py`
- Create: `online/opponent_models.py`
- Test: `tests/online/test_hand_settlement.py`
- Test: `tests/online/test_online_opponent_models.py`

- [ ] **Step 1: Write failing settlement tests**

Create tests proving:

```python
@pytest.mark.anyio
async def test_terminal_hand_posts_one_balanced_settlement(runtime, ledger, completed_hand):
    await runtime.finish_and_settle(completed_hand.table_id)
    again = await runtime.finish_and_settle(completed_hand.table_id)
    assert again.idempotency_key == f"settlement:{completed_hand.hand_id}"
    assert sum(await ledger.escrow_balances(completed_hand.table_id)) == completed_hand.starting_total_units


@pytest.mark.anyio
async def test_positive_net_counts_as_win_but_tie_does_not(history, completed_hand):
    await history.record(completed_hand.with_nets({"u1": 500, "u2": -500}))
    await history.record(completed_hand.with_nets({"u1": 0, "u2": 0}, hand_id="tie-hand"))
    assert (await history.profile("u1")).wins == 1
```

Also assert that an opponent's folded/mucked hole cards are absent from another user's hand-history response.

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_hand_settlement.py -q
```

Expected: missing online history implementation.

- [ ] **Step 3: Implement terminal settlement**

At terminal state, compute each participant's `end_stack_units - start_stack_units`. The deltas must sum to zero. Inside one database transaction, call `PlayLedger.settle_hand(hand_id, escrow_deltas, session=session)` with user and system-player escrow deltas and idempotency key `settlement:{hand_id}`, then persist the hand, participants, and public actions. Increment `hands_played`; increment `wins` only when `net_units > 0`. Apply the same progression rules and visible level thresholds to users and system players.

Expose `HistoryService.last_hands(user_id, limit=20)` with own hole cards and only showdown-shown opponent cards.

- [ ] **Step 4: Port the global recency-weighted opponent model**

Create `online/opponent_models.py` to calculate VPIP, PFR, 3-bet, fold-to-3-bet, postflop aggression, sample count, recency weight, confidence, and public traits from `hand_actions`. Use only public observed actions. Provide `model_for(user_id)` to `MultiwayBot`; do not pass hidden cards, Telegram ID, device, or integrity events.

Tests must show that two recent hands do not produce high confidence and that older samples receive less weight than recent samples.

- [ ] **Step 5: Run settlement and model tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_hand_settlement.py tests/online/test_online_opponent_models.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add online/history.py online/opponent_models.py tests/online/test_hand_settlement.py tests/online/test_online_opponent_models.py
git commit -m "feat: settle online hands and progression"
```

### Task 7: Add authenticated personalized WebSockets

**Files:**
- Create: `app/routers/realtime.py`
- Create: `tests/online/test_websocket.py`
- Modify: `app/online.py`

- [ ] **Step 1: Write failing WebSocket privacy and resync tests**

Create `tests/online/test_websocket.py` using `TestClient.websocket_connect`:

```python
def test_each_player_receives_only_their_hole_cards(two_logged_in_clients, active_table):
    client_a, client_b = two_logged_in_clients
    with client_a.websocket_connect(f"/ws/tables/{active_table.id}") as ws_a:
        snapshot_a = ws_a.receive_json()
    with client_b.websocket_connect(f"/ws/tables/{active_table.id}") as ws_b:
        snapshot_b = ws_b.receive_json()
    assert snapshot_a["state"]["players"][active_table.player_a]["hole_cards"] != ["??", "??"]
    assert snapshot_a["state"]["players"][active_table.player_b]["hole_cards"] == ["??", "??"]
    assert snapshot_b["state"]["players"][active_table.player_a]["hole_cards"] == ["??", "??"]


def test_stale_websocket_command_returns_resync(logged_in_client, active_table):
    with logged_in_client.websocket_connect(f"/ws/tables/{active_table.id}") as ws:
        ws.receive_json()
        ws.send_json({"type": "action", "command_id": "stale", "expected_revision": 0,
                      "action": "fold", "amount_units": 0})
        message = ws.receive_json()
        assert message["type"] == "snapshot"
        assert message["reason"] == "stale_revision"
```

Also open two sockets for the same seated user, close the first, and assert the seat remains connected; close the second and assert `disconnected_at` is set. Observer disconnects must only expire their waiting queue request and must never mutate a seat owned by another connection.

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_websocket.py -q
```

Expected: WebSocket route not found.

- [ ] **Step 3: Implement the connection hub and protocol**

The authenticated route `/ws/tables/{table_id}` accepts the HttpOnly session cookie, registers presence, and immediately sends:

```json
{"type":"snapshot","reason":"connected","revision":12,"state":{}}
```

Accepted client messages are:

```json
{"type":"action","command_id":"uuid","expected_revision":12,"action":"call","amount_units":0}
{"type":"resync","known_revision":11}
{"type":"ping","sent_at":123}
```

Server messages are `snapshot`, `state_changed`, `command_rejected`, `presence`, and `pong`. Every state message is rendered separately for each connected viewer. Never broadcast one player's personalized payload object to another socket.

- [ ] **Step 4: Run WebSocket tests and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_websocket.py tests/online/test_runtime.py -q
```

Expected: all tests pass.

```powershell
git add app/routers/realtime.py app/online.py tests/online/test_websocket.py
git commit -m "feat: stream private table state"
```

### Task 8: Implement action, disconnect, and seven-second hand timers

**Files:**
- Create: `online/scheduler.py`
- Create: `tests/online/test_scheduler.py`
- Modify: `online/runtime.py`

- [ ] **Step 1: Write failing fake-clock tests**

Create `tests/online/test_scheduler.py` with an injected `FakeClock` and assert:

```python
@pytest.mark.anyio
async def test_human_turn_deadline_is_thirty_seconds(scheduler, checking_turn):
    assert checking_turn.action_deadline == scheduler.now_plus(seconds=30)


@pytest.mark.anyio
async def test_timeout_checks_when_check_is_legal(scheduler, checking_turn):
    await scheduler.advance_to(checking_turn.action_deadline)
    assert scheduler.last_action == "check"


@pytest.mark.anyio
async def test_timeout_folds_when_facing_a_bet(scheduler, facing_bet_turn):
    await scheduler.advance_to(facing_bet_turn.action_deadline)
    assert scheduler.last_action == "fold"


@pytest.mark.anyio
async def test_repeated_timeout_callback_applies_once(scheduler, facing_bet_turn):
    await scheduler.fire_timeout(facing_bet_turn)
    await scheduler.fire_timeout(facing_bet_turn)
    assert scheduler.action_count == 1


@pytest.mark.anyio
async def test_result_clears_at_four_and_deals_at_seven(scheduler, terminal_table):
    await scheduler.advance(3.99)
    assert scheduler.phase == "result"
    await scheduler.advance(0.01)
    assert scheduler.phase == "countdown"
    assert scheduler.public_state_has_cards is False
    await scheduler.advance(3.0)
    assert scheduler.new_hand_count == 1


@pytest.mark.anyio
async def test_disconnected_seat_expires_after_hand_plus_sixty_seconds(scheduler, disconnected_player):
    await scheduler.finish_hand()
    await scheduler.advance(59.9)
    assert scheduler.seat_is_held
    await scheduler.advance(0.1)
    assert scheduler.seat_is_empty
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_scheduler.py -q
```

Expected: import failure for `online.scheduler`.

- [ ] **Step 3: Implement persistent deadlines**

`TableScheduler` scans and schedules persisted `action_deadline`, `result_clear_at`, `next_hand_at`, and seat `hold_until` values. It uses an injected UTC clock in tests and `asyncio` tasks in production. Every human action turn gets an authoritative 30-second deadline; client countdowns render that server timestamp and never decide the timeout locally.

On action timeout, call CHECK if `ActionType.CHECK` is legal; otherwise call FOLD. On terminal settlement, set phase `result`, `result_clear_at=now+4s`, and `next_hand_at=now+7s`. At clear time, publish a card/chip-free countdown snapshot. At next-hand time, process leaving seats, expired holds, and the FIFO queue, refill system players, then deal.

System-player actions are server scheduled with a bounded presentation delay; the browser no longer calls `/bot-step`.

- [ ] **Step 4: Run timer tests and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_scheduler.py -q
```

Expected: all fake-clock tests pass without real sleeping.

```powershell
git add online/scheduler.py online/runtime.py tests/online/test_scheduler.py
git commit -m "feat: run authoritative table deadlines"
```

### Task 9: Restore active hands after process restart

**Files:**
- Create: `tests/online/test_recovery.py`
- Modify: `online/runtime.py`
- Modify: `online/scheduler.py`
- Modify: `app/online.py`

- [ ] **Step 1: Write a failing restart test**

Create `tests/online/test_recovery.py`:

```python
@pytest.mark.anyio
async def test_restart_restores_exact_hand_and_grants_ten_second_grace(runtime_factory, active_hand):
    first = await runtime_factory()
    before = await first.private_snapshot(active_hand.table_id)
    await first.close()

    restored = await runtime_factory(now=active_hand.action_deadline_minus_five)
    after = await restored.private_snapshot(active_hand.table_id)
    public = await restored.public_snapshot(active_hand.table_id, active_hand.user_id)

    assert after["deck_cards"] == before["deck_cards"]
    assert after["players"] == before["players"]
    assert public["revision"] == active_hand.revision
    assert public["action_deadline"] >= restored.now_plus(seconds=10)
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_recovery.py -q
```

Expected: runtime factory does not restore persisted tables.

- [ ] **Step 3: Restore runtimes during application lifespan**

`TableRuntimeManager.restore_all()` must load every `active`, `result`, `countdown`, or `paused` runtime, deserialize its private snapshot, recreate per-table locks, and register deadlines. If the restored phase is active and the remaining action time is below 10 seconds, persist a new deadline of `now + 10 seconds` before accepting connections.

If deserialization, ledger reconciliation, or chip conservation fails, set phase `paused`, retain the private snapshot, write an integrity incident, and refuse new actions with `table_paused`.

Call `restore_all()` in `app/online.py` lifespan after migrations and before readiness becomes true. Then call `ensure_default_runtimes()` to create any missing catalogue runtimes, fill all six seats with unique stake-appropriate system players through the ledger, and start their first hands. Existing restored tables are never reseeded.

- [ ] **Step 4: Run the runtime release gate**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_recovery.py tests/online/test_runtime.py tests/online/test_scheduler.py tests/online/test_websocket.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add online/runtime.py online/scheduler.py app/online.py tests/online/test_recovery.py
git commit -m "feat: recover unfinished online hands"
```
