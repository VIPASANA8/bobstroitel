from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.schemas import (
    PlayerActionRequest, BotSeatRequest, HumanSeatRequest,
    ProfileCreateRequest, ProfileRenameRequest, ProfileTopUpRequest, SavedTableRequest, BotCooldownRequest,
)
from poker.engine import PokerEngine, InvalidAction
from bots.difficulty import DIFFICULTIES
from bots.multiway import MultiwayBot
from analysis.hand_analyzer import HandAnalyzer
from solver.mccfr import LocalMCCFRSolver
from persistence import TrainingStore


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"

app = FastAPI(title="Покерный тренажёр 7-max", version="0.10.3")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

engine = PokerEngine()
solver = LocalMCCFRSolver(engine=engine)
analyzer = HandAnalyzer()
store = TrainingStore(DATA_DIR / "poker_trainer.sqlite3")
bot = MultiwayBot(engine=engine, opponent_model_provider=store.bot_opponent_model)

GAMES = {}
SOLVER_CACHE = {}
ACTIVE_HAND_ID = None
NEXT_BUTTON_SEAT = 0


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


def active_state():
    return GAMES.get(ACTIVE_HAND_ID) if ACTIVE_HAND_ID else None


def table_is_locked() -> bool:
    state = active_state()
    return bool(state and not state.terminal)


def ensure_unlocked(message="Состав стола можно менять после завершения текущей раздачи"):
    if table_is_locked():
        raise HTTPException(status_code=409, detail=message)


def viewed_profile_id(state=None):
    if state and state.acting_player:
        p = state.players.get(state.acting_player)
        if p and not p.is_bot and p.profile_id:
            return p.profile_id
    return store.active_profile_id()


@app.get("/api/difficulties")
def difficulties():
    return [profile.public_dict() for profile in DIFFICULTIES.values()]


@app.get("/api/table")
def table():
    state = active_state()
    returned_bots = []
    ejected_bots = []
    if not table_is_locked():
        # Heal stale tables on load/migration too. A bot with < 1 BB has busted
        # and must leave the room immediately; the chair becomes free.
        ejected_bots = store.eject_busted_bots(engine.BIG_BLIND)
        returned_bots = store.return_ready_bots()
    seats = store.get_table()
    profile_id = viewed_profile_id(state)
    cooldowns = store.bot_cooldowns()
    return {
        "seats": seats,
        "locked": table_is_locked(),
        "active_hand_id": state.hand_id if state and not state.terminal else None,
        "profile": store.profile(profile_id),
        "profiles": store.list_profiles(),
        "active_profile_id": store.active_profile_id(),
        "saved_tables": store.list_saved_tables(),
        "current_saved_table_id": store.current_table_id(),
        "max_players": 7,
        "max_bots": 6,
        "human_count": sum(1 for row in seats if row["active"] and row["occupant_type"] == "human"),
        "bot_count": sum(1 for row in seats if row["active"] and row["occupant_type"] == "bot"),
        "spectator_only": not any(row["active"] and row["occupant_type"] == "human" for row in seats),
        "mode": "hot-seat",
        "bot_bust_cooldown_minutes": store.bot_cooldown_minutes(),
        "bot_cooldowns": cooldowns,
        "returned_bots": returned_bots,
        "ejected_bots": ejected_bots,
    }


@app.post("/api/table/seats/{seat}/bot")
def add_or_update_bot(seat: int, req: BotSeatRequest):
    ensure_unlocked()
    try:
        row = store.add_bot(seat, req.name, req.difficulty)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"seat": row, "table": store.get_table()}


@app.post("/api/table/seats/{seat}/human")
def add_human(seat: int, req: HumanSeatRequest):
    ensure_unlocked()
    try:
        row = store.set_human_seat(seat, req.profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"seat": row, "table": store.get_table()}


@app.delete("/api/table/seats/{seat}")
def clear_seat(seat: int):
    ensure_unlocked()
    try:
        store.clear_seat(seat)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "table": store.get_table()}


# v0.8 compatibility
@app.delete("/api/table/seats/{seat}/bot")
def remove_bot_compat(seat: int):
    return clear_seat(seat)


@app.get("/api/profiles")
def profiles():
    return {"active_profile_id": store.active_profile_id(), "profiles": store.list_profiles()}


@app.post("/api/profiles")
def create_profile(req: ProfileCreateRequest):
    ensure_unlocked("Профиль можно создавать после завершения текущей раздачи")
    try:
        created = store.create_profile(req.name)
        profile = store.select_profile(created["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"profile": profile, "profiles": store.list_profiles(), "table": store.get_table()}


@app.post("/api/profiles/{profile_id}/activate")
def activate_profile(profile_id: str):
    # This is only the profile selected in the stats panel; seated profiles stay seated.
    try:
        profile = store.select_profile(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"profile": profile, "profiles": store.list_profiles(), "table": store.get_table()}


@app.patch("/api/profiles/{profile_id}")
def rename_profile(profile_id: str, req: ProfileRenameRequest):
    ensure_unlocked("Профиль можно переименовать после завершения текущей раздачи")
    try:
        profile = store.rename_profile(profile_id, req.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"profile": profile, "profiles": store.list_profiles(), "table": store.get_table()}


@app.post("/api/profiles/{profile_id}/top-up")
def top_up_profile(profile_id: str, req: ProfileTopUpRequest):
    ensure_unlocked("Пополнять баланс можно только между раздачами")
    try:
        current = store.get_profile_record(profile_id)
        new_balance = round(float(current["balance"]) + float(req.amount), 2)
        store.set_profile_balance(profile_id, new_balance)
        profile = store.profile(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "ok": True,
        "added": round(float(req.amount), 2),
        "profile": profile,
        "table": store.get_table(),
    }


@app.get("/api/profiles/{profile_id}/model")
def profile_model(profile_id: str):
    try:
        return store.profile(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/profile")
def player_profile():
    return store.profile()


@app.get("/api/profile/training-samples")
def player_training_samples(limit: int = 200, profile_id: str | None = None):
    pid = profile_id or store.active_profile_id()
    return {"profile": store.get_profile_record(pid), "samples": store.training_samples(pid, limit)}


@app.get("/api/history")
def persistent_history(limit: int = 20, profile_id: str | None = None):
    return store.recent_hands(limit, profile_id)


# ------------------------------------------------------------------
# Saved local tables
# ------------------------------------------------------------------
@app.get("/api/tables")
def saved_tables():
    return {"tables": store.list_saved_tables(), "current_table_id": store.current_table_id()}


@app.post("/api/tables")
def save_table(req: SavedTableRequest):
    ensure_unlocked("Стол можно сохранять после завершения текущей раздачи")
    try:
        saved = store.save_current_table(req.name, button_seat=NEXT_BUTTON_SEAT)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"saved_table": saved, "tables": store.list_saved_tables()}


@app.put("/api/tables/{table_id}")
def update_saved_table(table_id: str, req: SavedTableRequest):
    ensure_unlocked("Стол можно сохранять после завершения текущей раздачи")
    try:
        saved = store.save_current_table(req.name, table_id=table_id, button_seat=NEXT_BUTTON_SEAT)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"saved_table": saved, "tables": store.list_saved_tables()}


@app.post("/api/tables/{table_id}/load")
def load_saved_table(table_id: str):
    global ACTIVE_HAND_ID, NEXT_BUTTON_SEAT
    ensure_unlocked("Сохранённый стол можно открыть после завершения текущей раздачи")
    try:
        result = store.load_saved_table(table_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    ACTIVE_HAND_ID = None
    saved = result["saved_table"]
    NEXT_BUTTON_SEAT = int(saved.get("button_seat", 0))
    return {**result, "profiles": store.list_profiles()}


@app.delete("/api/tables/{table_id}")
def delete_saved_table(table_id: str):
    ensure_unlocked("Сохранённый стол можно удалить после завершения текущей раздачи")
    try:
        store.delete_saved_table(table_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ok": True, "tables": store.list_saved_tables()}


@app.post("/api/bankroll/reset")
def reset_bankroll():
    global ACTIVE_HAND_ID, NEXT_BUTTON_SEAT
    ensure_unlocked("Нельзя сбрасывать баланс во время раздачи")
    ACTIVE_HAND_ID = None
    NEXT_BUTTON_SEAT = 0
    GAMES.clear()
    SOLVER_CACHE.clear()
    return {"ok": True, "table": store.reset_balances(), "profile": store.profile()}

@app.post("/api/table/rebuy-busted-bots")
def rebuy_busted_bots():
    raise HTTPException(
        status_code=410,
        detail="Мгновенный авторебай отключён. Выбитый бот покидает рум и возвращается после тайм-аута.",
    )


@app.post("/api/table/bot-cooldown")
def set_bot_cooldown(req: BotCooldownRequest):
    ensure_unlocked("Тайм-аут ботов можно менять только между раздачами")
    try:
        minutes = store.set_bot_cooldown_minutes(req.minutes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "ok": True,
        "minutes": minutes,
        "bot_cooldowns": store.bot_cooldowns(),
        "saved_tables": store.list_saved_tables(),
    }


def state_fingerprint(state, player_id: str):
    p = state.players[player_id]
    return "|".join([
        state.hand_id, player_id, state.street.value, str(len(state.history)), state.acting_player or "none",
        f"{state.pot:.2f}", f"{state.current_bet:.2f}", ",".join(state.board), f"{p.stack:.2f}",
    ])


def result_has_exact_action(result, action, amount):
    for row in result.get("actions", []):
        if row.get("action") != action.value:
            continue
        if action.value in {"fold", "check", "call", "all_in"}:
            return True
        if abs(float(row.get("amount", 0.0)) - float(amount)) < 0.011:
            return True
    return False


def clear_solver_cache_for_hand(hand_id: str):
    for key in [k for k in SOLVER_CACHE if k.startswith(hand_id + "|")]:
        SOLVER_CACHE.pop(key, None)


def acting_human(state):
    if state.terminal or not state.acting_player:
        return None
    p = state.players.get(state.acting_player)
    return p if p and not p.is_bot else None


def public_payload(state):
    human = acting_human(state)
    humans = [p for p in state.players.values() if not p.is_bot]

    # With one local human their hole cards stay visible for the whole hand,
    # including while bots are thinking. Previously viewer_id became None on a
    # bot turn and the UI hid the user's own cards.
    # In multi-human hot-seat mode privacy still follows the acting human; while
    # bots act we show the profile selected locally in the stats/profile panel.
    viewer = None
    if len(humans) == 1:
        viewer = humans[0]
    elif human is not None:
        viewer = human
    else:
        active_pid = store.active_profile_id()
        viewer = next((p for p in humans if p.profile_id == active_pid), None)
    viewer_id = viewer.id if viewer else None

    legal, min_raise_to, to_call = [], None, 0.0
    if human:
        legal = [x.value for x in engine.legal_actions(state, human.id)]
        min_raise_to = engine.min_raise_to(state, human.id)
        to_call = engine.to_call(state, human.id)

    payload = state.to_dict(viewer_player_id=viewer_id)
    payload["human_legal_actions"] = legal
    payload["human_to_call"] = round(to_call, 2)
    payload["human_min_raise_to"] = round(min_raise_to, 2) if min_raise_to is not None else None
    payload["acting_human_player_id"] = human.id if human else None
    payload["acting_human_profile_id"] = human.profile_id if human else None
    payload["acting_human_name"] = human.name if human else None
    payload["viewer_player_id"] = viewer_id
    payload["persistent_hole_cards"] = len(humans) == 1
    # Old UI aliases retained while v0.9 frontend migrates.
    payload["hero_legal_actions"] = legal
    payload["hero_to_call"] = round(to_call, 2)
    payload["hero_min_raise_to"] = round(min_raise_to, 2) if min_raise_to is not None else None

    review = None
    if human:
        review = next((r for r in reversed(state.decision_reviews) if r.get("profile_id") == human.profile_id), None)
    elif state.decision_reviews:
        review = state.decision_reviews[-1]
    payload["last_review"] = review
    payload["review_count"] = len(state.decision_reviews)

    profile_id = human.profile_id if human and human.profile_id else store.active_profile_id()
    payload["training_profile"] = store.profile(profile_id)
    payload["active_profile_id"] = store.active_profile_id()
    payload["persistent_bankroll"] = True
    payload["table_locked"] = not state.terminal
    payload["player_count"] = len(state.seat_order)
    payload["solver_available"] = bool(human and len(state.live_ids()) == 2)
    payload["solver_name"] = "CFR-lite (heads-up)"
    payload["hot_seat"] = True
    payload["spectator_only"] = not state_has_human(state)
    payload["human_count"] = sum(1 for p in state.players.values() if not p.is_bot)
    payload["bot_count"] = sum(1 for p in state.players.values() if p.is_bot)
    return payload


def autoplay_bots(state):
    safety = 0
    while not state.terminal and state.acting_player and state.players[state.acting_player].is_bot:
        safety += 1
        if safety > 150:
            raise RuntimeError("Защитная остановка автодействий ботов")
        pid = state.acting_player
        decision = bot.decide(state, pid)
        engine.apply_action(state, pid, decision.action, decision.amount)


def state_has_human(state) -> bool:
    return any(not p.is_bot for p in state.players.values())


def step_bot_once(state):
    """Сделать ровно одно действие бота. Используется режимом наблюдения."""
    if state.terminal:
        return None
    pid = state.acting_player
    if not pid or pid not in state.players or not state.players[pid].is_bot:
        raise InvalidAction("Сейчас ход не бота")
    decision = bot.decide(state, pid)
    engine.apply_action(state, pid, decision.action, decision.amount)
    return decision


def next_active_button_seat(current_seat: int, seats: list[dict]) -> int:
    active_numbers = sorted(int(row["seat"]) for row in seats if row["active"])
    if not active_numbers:
        return 0
    for seat in active_numbers:
        if seat > current_seat:
            return seat
    return active_numbers[0]


def persist_current_saved_table_rotation():
    table_id = store.current_table_id()
    if not table_id:
        return
    row = next((x for x in store.list_saved_tables() if x["id"] == table_id), None)
    if row:
        store.save_current_table(row["name"], table_id=table_id, button_seat=NEXT_BUTTON_SEAT)


def persist_and_process_terminal(state):
    """Persist result, then remove busted bots without reserving their chairs."""
    store.save_state(state)
    busted = []
    if state.terminal:
        busted = store.eject_busted_bots(engine.BIG_BLIND)
        persist_current_saved_table_rotation()
    return busted


@app.post("/api/game/active/abort")
def abort_active_hand():
    global ACTIVE_HAND_ID, NEXT_BUTTON_SEAT
    state = active_state()
    if not state or state.terminal:
        ACTIVE_HAND_ID = None
        return {"ok": True, "aborted": False, "table": store.get_table()}
    hand_id = state.hand_id
    if state.button in state.players:
        NEXT_BUTTON_SEAT = int(state.players[state.button].seat)
    store.discard_incomplete_hand(hand_id)
    clear_solver_cache_for_hand(hand_id)
    GAMES.pop(hand_id, None)
    ACTIVE_HAND_ID = None
    return {"ok": True, "aborted": True, "hand_id": hand_id, "table": store.get_table(), "profile": store.profile()}


@app.post("/api/game/new")
def new_game():
    global ACTIVE_HAND_ID, NEXT_BUTTON_SEAT
    # Between hands, ready bots may re-enter on any free seat. A chair is never reserved.
    store.eject_busted_bots(engine.BIG_BLIND)
    store.return_ready_bots()
    seats = store.active_seats()
    if len(seats) < 2:
        raise HTTPException(status_code=409, detail="Посадите за стол хотя бы двух игроков или ботов")
    if any(float(row["balance"]) < engine.BIG_BLIND for row in seats):
        raise HTTPException(status_code=409, detail="У одного из игроков меньше 1 ББ. Сбросьте баланс или измените состав стола.")
    previous = active_state()
    if previous and not previous.terminal:
        raise HTTPException(status_code=409, detail="Сначала завершите текущую раздачу")

    active_numbers = [int(row["seat"]) for row in seats]
    if NEXT_BUTTON_SEAT not in active_numbers:
        NEXT_BUTTON_SEAT = active_numbers[0]
    try:
        state = engine.new_hand(seats, button_seat=NEXT_BUTTON_SEAT)
    except InvalidAction as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    NEXT_BUTTON_SEAT = next_active_button_seat(NEXT_BUTTON_SEAT, seats)
    GAMES[state.hand_id] = state
    ACTIVE_HAND_ID = state.hand_id
    # v0.10: любое действие бота выполняется отдельным /bot-step.
    # Так клиент успевает показать «размышление», ставку и анимацию даже
    # на смешанном столе с людьми. Никакого мгновенного autoplay на сервере.
    busted = persist_and_process_terminal(state) if state.terminal else []
    if not state.terminal:
        store.save_state(state)
    payload = public_payload(state)
    payload["busted_bots"] = busted
    return payload


@app.get("/api/game/{hand_id}")
def get_game(hand_id: str):
    state = GAMES.get(hand_id)
    if not state:
        raise HTTPException(status_code=404, detail="Раздача не найдена")
    return public_payload(state)


@app.post("/api/game/{hand_id}/bot-step")
def bot_step(hand_id: str):
    """Сделать ровно одно действие текущего бота на любом типе стола."""
    state = GAMES.get(hand_id)
    if not state:
        raise HTTPException(status_code=404, detail="Раздача не найдена")
    if state.terminal:
        return public_payload(state)
    try:
        decision = step_bot_once(state)
        busted = persist_and_process_terminal(state) if state.terminal else []
        if not state.terminal:
            store.save_state(state)
        clear_solver_cache_for_hand(hand_id)
    except (InvalidAction, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    payload = public_payload(state)
    payload["busted_bots"] = busted if 'busted' in locals() else []
    if decision is not None:
        payload["last_bot_decision"] = {
            "action": decision.action.value,
            "amount": round(float(decision.amount or 0.0), 2),
            "reason": getattr(decision, "reason", ""),
        }
    return payload


@app.get("/api/game/{hand_id}/solver")
def solve_current_spot(hand_id: str):
    state = GAMES.get(hand_id)
    if not state:
        raise HTTPException(status_code=404, detail="Раздача не найдена")
    human = acting_human(state)
    if not human:
        raise HTTPException(status_code=400, detail="Сейчас нет решения человека для анализа")
    if len(state.live_ids()) != 2:
        raise HTTPException(status_code=400, detail="CFR-lite этой версии доступен в heads-up спотах")
    key = state_fingerprint(state, human.id)
    if key not in SOLVER_CACHE:
        SOLVER_CACHE[key] = solver.solve(state, human.id, iterations=520)
    return SOLVER_CACHE[key]


@app.post("/api/game/{hand_id}/action")
def player_action(hand_id: str, req: PlayerActionRequest):
    state = GAMES.get(hand_id)
    if not state:
        raise HTTPException(status_code=404, detail="Раздача не найдена")
    human = acting_human(state)
    if not human:
        raise HTTPException(status_code=400, detail="Сейчас ход не человека")

    try:
        review = None
        if req.action not in engine.legal_actions(state, human.id):
            raise InvalidAction("Это действие сейчас недоступно")
        if len(state.live_ids()) == 2:
            key = state_fingerprint(state, human.id)
            cached = SOLVER_CACHE.get(key)
            if cached is not None and result_has_exact_action(cached, req.action, req.amount):
                result = cached
            else:
                result = solver.solve(state, human.id, iterations=520, extra_action=req.action, extra_amount=req.amount)
            review = solver.review_action(result, req.action, req.amount, street=state.street, board=list(state.board))
            review["action_seq"] = len(state.history)
            review["player_id"] = human.id
            review["profile_id"] = human.profile_id
            review["player_name"] = human.name

        engine.apply_action(state, human.id, req.action, req.amount)
        if review is not None:
            state.decision_reviews.append(review)
        # Следующий бот (если он ходит) будет вызван клиентом отдельным шагом
        # после человеческой паузы. Это сохраняет естественный темп игры.
        busted = persist_and_process_terminal(state) if state.terminal else []
        if not state.terminal:
            store.save_state(state)
        clear_solver_cache_for_hand(hand_id)
    except (InvalidAction, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    payload = public_payload(state)
    payload["busted_bots"] = busted if 'busted' in locals() else []
    return payload



@app.post("/api/game/{hand_id}/timeout-fold")
def timeout_fold_action(hand_id: str):
    state = GAMES.get(hand_id)
    if not state:
        raise HTTPException(status_code=404, detail="Раздача не найдена")
    human = acting_human(state)
    if not human:
        raise HTTPException(status_code=400, detail="Сейчас ход не человека")
    try:
        engine.timeout_fold(state, human.id)
        busted = persist_and_process_terminal(state) if state.terminal else []
        if not state.terminal:
            store.save_state(state)
        clear_solver_cache_for_hand(hand_id)
    except (InvalidAction, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    payload = public_payload(state)
    payload["busted_bots"] = busted if 'busted' in locals() else []
    payload["timed_out"] = True
    return payload

@app.get("/api/game/{hand_id}/analysis")
def analysis(hand_id: str):
    state = GAMES.get(hand_id)
    if not state:
        raise HTTPException(status_code=404, detail="Раздача не найдена")
    humans = [p for p in state.players.values() if not p.is_bot and p.profile_id]
    return {
        "hand_id": state.hand_id,
        "players": len(state.seat_order),
        "board": state.board,
        "result": state.result_text,
        "side_pots": state.result_details,
        "reviews": state.decision_reviews,
        "human_profiles": [store.profile(p.profile_id) for p in humans],
        "models": {p.profile_id: store.get_profile_model(p.profile_id) for p in humans},
    }
