from random import Random

from ..domain.errors import GameError
from ..domain.rules import DEFAULT_PRESET
from ..domain.simulation import MIRAGE, simulate_mirage


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
        last_finished = self.series.last_finished_lobby(user_id)
        return {
            "displayName": player["display_name"],
            "team": self.players.team(user_id),
            "activeLobby": active["id"] if active else None,
            "activeSeries": bool(active and active["status"] == "started"),
            "lastFinishedLobby": last_finished["lobby_id"] if last_finished else None,
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
                self.players.record_guest_joined(lobby_id)
            return self.lobby(lobby_id, user_id)

    def lock_lobby(self, lobby_id):
        lobby = self.players.lock_lobby(lobby_id)
        if lobby is None:
            raise GameError("not_found", "Приглашение или лобби не найдено")
        return lobby

    def require_open(self, lobby):
        if lobby["status"] == "cancelled":
            raise GameError("gone", "Лобби закрыто")
        if lobby["status"] == "finished":
            raise GameError("gone", "Карта уже сыграна")
        if lobby["status"] == "expired" or (not lobby["valid"] and not lobby["guest_joined"]):
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
            if status == "waiting" and not lobby["valid"] and not lobby["guest_joined"]:
                status = "expired"
            side = "T" if lobby["host_id"] == user_id else "CT"
            return {
                "id": lobby_id,
                "status": status,
                "series": series,
                "canInvite": lobby["host_id"] == user_id and status == "waiting" and lobby["valid"],
                "canCancel": status in ("waiting", "ready"),
                "preparation": {"map": MIRAGE, "side": side, "preset": self.mirage_tactics(user_id)[side]},
                "participants": [
                    {
                        "name": m["display_name"],
                        "ready": m["ready"],
                        "you": m["telegram_id"] == user_id,
                        "seat": "host" if m["telegram_id"] == lobby["host_id"] else "guest",
                    }
                    for m in self.players.members(lobby_id)
                ],
            }

    def read_series(self, series_id, user_id):
        result = self.series.find_for_player(series_id, user_id)
        if result is None:
            raise GameError("not_found", "Серия не найдена")
        return result

    def mirage_tactics(self, user_id):
        presets = {"T": DEFAULT_PRESET, "CT": DEFAULT_PRESET}
        presets.update({
            item["side"]: item["preset"] for item in self.players.list_tactics(user_id)
            if item["map"] == MIRAGE
        })
        return presets

    def finish_map(self, lobby_id, host_id, members):
        guest_id = next(member["telegram_id"] for member in members if member["telegram_id"] != host_id)
        result = simulate_mirage(self.mirage_tactics(host_id), self.mirage_tactics(guest_id), Random().random)
        self.series.start(lobby_id)
        self.series.finish(lobby_id, result)
        self.players.set_lobby_status(lobby_id, "finished")
        self.players.deactivate_members(lobby_id)

    def ready(self, lobby_id, user_id, value):
        with self.unit.transaction():
            self.require_member(lobby_id, user_id)
            lobby = self.lock_lobby(lobby_id)
            if lobby["status"] == "finished":
                if not value:
                    raise GameError("conflict", "Карта уже сыграна")
                return self.lobby(lobby_id, user_id)
            self.require_open(lobby)
            self.players.set_member_ready(lobby_id, user_id, value)
            members = self.players.members(lobby_id)
            if len(members) == 2 and all(member["ready"] for member in members):
                self.finish_map(lobby_id, lobby["host_id"], members)
            return self.lobby(lobby_id, user_id)

    def cancel(self, lobby_id, user_id):
        with self.unit.transaction():
            self.require_member(lobby_id, user_id)
            lobby = self.lock_lobby(lobby_id)
            if lobby["status"] == "finished":
                raise GameError("conflict", "Карта уже сыграна")
            if lobby["status"] != "cancelled":
                self.require_open(lobby)
                self.series.cancel_pending(lobby_id)
                self.players.set_lobby_status(lobby_id, "cancelled")
                self.players.deactivate_members(lobby_id)
            return self.lobby(lobby_id, user_id)
