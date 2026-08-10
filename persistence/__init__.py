import json

from persistence.store import TrainingStore as _TrainingStore


class TrainingStore(_TrainingStore):
    """Poker8 v2 policy: no more than six active seats at one table.

    The underlying storage still keeps seven physical seat rows for backward
    compatibility with old databases and saved data. Poker8 v2 simply limits
    the live composition to six participants.
    """

    MAX_PLAYERS = 6

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._normalize_six_max_table()

    def _normalize_six_max_table(self):
        table = self.get_table()
        active = [row for row in table if row.get("active")]
        if len(active) <= self.MAX_PLAYERS:
            return

        # Preserve the lowest physical seats first. In the legacy packaged
        # table this removes the sixth bot while retaining the local player.
        remove = sorted(active, key=lambda row: int(row["seat"]), reverse=True)[: len(active) - self.MAX_PLAYERS]
        now = self._now()
        with self._lock, self._connect() as con:
            for row in remove:
                seat = int(row["seat"])
                con.execute(
                    """UPDATE table_seats SET player_id=?,name='Свободно',is_bot=0,difficulty='normal',active=0,
                       occupant_type='empty',profile_id=NULL,updated_at=? WHERE seat=?""",
                    (f"empty_{seat}", now, seat),
                )
        self._autosave_current_table()

    def _ensure_six_max_capacity(self, seat: int):
        table = self.get_table()
        current = next((row for row in table if int(row["seat"]) == int(seat)), None)
        active_count = sum(1 for row in table if row.get("active"))
        if current and not current.get("active") and active_count >= self.MAX_PLAYERS:
            raise ValueError("Poker8 — формат 6-max: за столом может быть не больше 6 игроков")

    def set_human_seat(self, seat: int, profile_id: str) -> dict:
        self._ensure_six_max_capacity(seat)
        return super().set_human_seat(seat, profile_id)

    def add_bot(self, seat: int, name: str | None = None, difficulty: str = "normal") -> dict:
        self._ensure_six_max_capacity(seat)
        return super().add_bot(seat, name, difficulty)

    def load_saved_table(self, table_id: str) -> dict:
        with self._lock, self._connect() as con:
            row = con.execute("SELECT seats_json FROM saved_tables WHERE table_id=?", (table_id,)).fetchone()
        if row:
            try:
                seats = json.loads(row["seats_json"] or "[]")
            except json.JSONDecodeError:
                seats = []
            active_count = sum(1 for seat in seats if seat.get("occupant_type") != "empty")
            if active_count > self.MAX_PLAYERS:
                raise ValueError("Этот сохранённый стол создан для 7-max. Уберите одного игрока и сохраните его как 6-max.")
        return super().load_saved_table(table_id)

    def return_ready_bots(self) -> list[dict]:
        table = self.get_table()
        active_count = sum(1 for row in table if row.get("active"))
        free_player_slots = max(0, self.MAX_PLAYERS - active_count)
        if free_player_slots <= 0:
            return []

        bot_count = sum(1 for row in table if row.get("active") and row.get("occupant_type") == "bot")
        original_max_bots = self.MAX_BOTS
        try:
            # The inherited routine already respects MAX_BOTS. Temporarily cap
            # it so it can fill only the remaining six-max player slots.
            self.MAX_BOTS = min(original_max_bots, bot_count + free_player_slots)
            return super().return_ready_bots()
        finally:
            self.MAX_BOTS = original_max_bots


__all__ = ["TrainingStore"]
