from ..domain.errors import GameError


class Game:
    def __init__(self, unit):
        self.unit = unit
        self.players = unit.players
        self.series = unit.series

    def health(self):
        self.players.health()

    def account_exists(self, user_id):
        return self.players.account_exists(user_id)

    def login(self, user):
        with self.unit.transaction():
            self.players.save_account(user)
            self.players.grant_starting_team(user.id)
            return self.profile(user.id)

    def profile(self, user_id):
        player = self.players.account(user_id)
        active = self.players.active_lobby(user_id)
        return {
            "displayName": player["display_name"],
            "team": self.players.team(user_id),
            "activeLobby": active["id"] if active else None,
            "activeSeries": bool(active and active["status"] == "started"),
        }

    def tactics(self, user_id):
        return self.players.list_tactics(user_id)

    def save_tactic(self, user_id, map_name, side, preset):
        with self.unit.transaction():
            self.players.save_tactic(user_id, map_name, side, preset)

    def create_lobby(self, user_id):
        with self.unit.transaction():
            self.players.release_expired_lobbies()
            self.players.lock_account(user_id)
            existing = self.players.active_lobby(user_id)
            if existing:
                if existing["host_id"] == user_id:
                    return self.lobby(existing["id"], user_id)
                raise GameError("conflict", "Ты уже в другом лобби")
            lobby_id = self.players.create_lobby(user_id)
            return self.lobby(lobby_id, user_id)

    def join(self, lobby_id, user_id):
        with self.unit.transaction():
            self.players.release_expired_lobbies()
            self.players.lock_account(user_id)
            lobby = self.lock_lobby(lobby_id)
            is_guest = lobby["host_id"] != user_id and self.players.is_member(lobby_id, user_id)
            if is_guest and lobby["status"] == "started":
                return self.lobby(lobby_id, user_id)
            self.require_open(lobby)
            if lobby["host_id"] == user_id:
                raise GameError("conflict", "Это твоё приглашение")
            if not is_guest:
                if len(self.players.members(lobby_id)) == 2:
                    raise GameError("conflict", "В лобби уже два участника")
                if not self.players.add_member(lobby_id, user_id):
                    raise GameError("conflict", "Ты уже в другом лобби")
            return self.lobby(lobby_id, user_id)

    def lock_lobby(self, lobby_id):
        lobby = self.players.lock_lobby(lobby_id)
        if lobby is None:
            raise GameError("not_found", "Приглашение или лобби не найдено")
        return lobby

    def require_open(self, lobby):
        if lobby["status"] == "cancelled":
            raise GameError("gone", "Лобби закрыто")
        if not lobby["valid"] or lobby["status"] == "expired":
            raise GameError("gone", "Срок приглашения истёк")

    def require_member(self, lobby_id, user_id):
        if not self.players.is_member(lobby_id, user_id):
            raise GameError("not_found", "Лобби не найдено")

    def lobby(self, lobby_id, user_id):
        with self.unit.transaction():
            self.require_member(lobby_id, user_id)
            lobby = self.lock_lobby(lobby_id)
            series = self.series.find_by_lobby(lobby_id)
            status = "ready" if lobby["status"] == "started" else lobby["status"]
            if lobby["status"] in ("waiting", "ready") and not lobby["valid"]:
                status = "expired"
            return {
                "id": lobby_id,
                "status": status,
                "series": series,
                "canInvite": lobby["host_id"] == user_id and status == "waiting",
                "canCancel": lobby["host_id"] == user_id and status in ("waiting", "ready"),
                "participants": [
                    {"name": m["display_name"], "ready": m["ready"], "you": m["telegram_id"] == user_id}
                    for m in self.players.members(lobby_id)
                ],
            }

    def read_series(self, series_id, user_id):
        result = self.series.find_for_player(series_id, user_id)
        if result is None:
            raise GameError("not_found", "Серия не найдена")
        return result

    def ready(self, lobby_id, user_id, value):
        with self.unit.transaction():
            self.require_member(lobby_id, user_id)
            lobby = self.lock_lobby(lobby_id)
            if lobby["status"] == "started":
                if not value:
                    raise GameError("conflict", "Серия уже создана")
                return self.lobby(lobby_id, user_id)
            self.require_open(lobby)
            self.players.set_member_ready(lobby_id, user_id, value)
            members = self.players.members(lobby_id)
            status = "started" if len(members) == 2 and all(m["ready"] for m in members) else "waiting"
            if status == "started":
                self.series.start(lobby_id)
            self.players.set_lobby_status(lobby_id, status)
            return self.lobby(lobby_id, user_id)

    def cancel(self, lobby_id, user_id):
        with self.unit.transaction():
            self.require_member(lobby_id, user_id)
            lobby = self.lock_lobby(lobby_id)
            if lobby["host_id"] != user_id:
                raise GameError("forbidden", "Закрыть лобби может только организатор")
            if lobby["status"] != "cancelled":
                if lobby["status"] == "started":
                    self.series.cancel_pending(lobby_id)
                else:
                    self.require_open(lobby)
                self.players.set_lobby_status(lobby_id, "cancelled")
                self.players.deactivate_members(lobby_id)
            return self.lobby(lobby_id, user_id)
