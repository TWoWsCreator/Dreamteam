from dataclasses import dataclass
from typing import Literal

from psycopg.errors import UniqueViolation

from .series import SeriesRepository

Map = Literal["ancient", "anubis", "dust2", "inferno", "mirage", "nuke", "train"]
Side = Literal["T", "CT"]
Preset = Literal["balanced", "fast", "hold"]

STARTERS = [
    {"role": "IGL", "name": "Капитан", "description": "Руководит командой"},
    {"role": "AWP", "name": "Снайпер", "description": "Контролирует дальние позиции"},
    {"role": "Entry", "name": "Первый номер", "description": "Первым выходит на позицию"},
    {"role": "Support", "name": "Поддержка", "description": "Помогает команде занять позицию"},
    {"role": "Lurker", "name": "Луркер", "description": "Контролирует фланги"},
]


@dataclass
class GameError(Exception):
    status: int
    message: str


class Game:
    def __init__(self, connection):
        self.db = connection
        self.series = SeriesRepository(connection)

    def login(self, user):
        self.db.execute(
            """INSERT INTO accounts (telegram_id, display_name) VALUES (%s, %s)
               ON CONFLICT (telegram_id) DO UPDATE SET display_name = EXCLUDED.display_name""",
            (user.id, user.name),
        )

    def profile(self, user_id):
        player = self.db.execute(
            "SELECT display_name FROM accounts WHERE telegram_id = %s", (user_id,)
        ).fetchone()
        active = self.db.execute(
            """SELECT l.id FROM lobby_members m JOIN lobbies l ON l.id = m.lobby_id
               WHERE m.telegram_id = %s AND m.active
                 AND (l.status = 'started' OR l.expires_at > clock_timestamp())""",
            (user_id,),
        ).fetchone()
        return {
            "displayName": player["display_name"],
            "team": STARTERS,
            "activeLobby": active["id"] if active else None,
        }

    def tactics(self, user_id):
        return self.db.execute(
            "SELECT map, side, preset FROM tactics WHERE telegram_id = %s ORDER BY map, side",
            (user_id,),
        ).fetchall()

    def save_tactic(self, user_id, map_name, side, preset):
        self.db.execute(
            """INSERT INTO tactics (telegram_id, map, side, preset) VALUES (%s, %s, %s, %s)
               ON CONFLICT (telegram_id, map, side) DO UPDATE SET preset = EXCLUDED.preset""",
            (user_id, map_name, side, preset),
        )

    def expire_lobbies(self):
        self.db.execute(
            """WITH expired AS (
                   UPDATE lobbies SET status = 'expired'
                   WHERE expires_at <= clock_timestamp() AND status IN ('waiting', 'ready')
                   RETURNING id
               )
               UPDATE lobby_members SET active = FALSE
               WHERE lobby_id IN (SELECT id FROM expired) AND active"""
        )

    def create_lobby(self, lobby_id, user_id):
        self.expire_lobbies()
        self.db.execute("SELECT telegram_id FROM accounts WHERE telegram_id = %s FOR NO KEY UPDATE", (user_id,))
        existing = self.db.execute(
            """SELECT l.id, l.host_id FROM lobby_members m JOIN lobbies l ON l.id = m.lobby_id
               WHERE m.telegram_id = %s AND m.active""",
            (user_id,),
        ).fetchone()
        if existing:
            if existing["host_id"] == user_id:
                return existing["id"]
            raise GameError(409, "Ты уже в другом лобби")
        self.db.execute(
            """INSERT INTO lobbies (id, host_id, expires_at)
               VALUES (%s, %s, clock_timestamp() + INTERVAL '30 minutes')""",
            (lobby_id, user_id),
        )
        self.db.execute("INSERT INTO lobby_members (lobby_id, telegram_id) VALUES (%s, %s)", (lobby_id, user_id))
        return lobby_id

    def join(self, lobby_id, user_id):
        self.expire_lobbies()
        self.db.execute("SELECT telegram_id FROM accounts WHERE telegram_id = %s FOR NO KEY UPDATE", (user_id,))
        lobby = self.lock_lobby(lobby_id)
        is_guest = lobby["host_id"] != user_id and self.is_member(lobby_id, user_id)
        if is_guest and lobby["status"] == "started":
            return
        self.require_open(lobby)
        if lobby["host_id"] == user_id:
            raise GameError(409, "Это твоё приглашение")
        if is_guest:
            return
        if len(self.members(lobby_id)) == 2:
            raise GameError(409, "В лобби уже два участника")
        try:
            self.db.execute(
                "INSERT INTO lobby_members (lobby_id, telegram_id) VALUES (%s, %s)", (lobby_id, user_id)
            )
        except UniqueViolation as exc:
            raise GameError(409, "Ты уже в другом лобби") from exc

    def lock_lobby(self, lobby_id):
        lobby = self.db.execute(
            """SELECT *, expires_at > clock_timestamp() AS valid
               FROM lobbies WHERE id = %s FOR UPDATE""",
            (lobby_id,),
        ).fetchone()
        if not lobby:
            raise GameError(404, "Приглашение или лобби не найдено")
        return lobby

    def require_open(self, lobby):
        if lobby["status"] == "cancelled":
            raise GameError(410, "Лобби закрыто")
        if not lobby["valid"] or lobby["status"] == "expired":
            raise GameError(410, "Срок приглашения истёк")

    def is_member(self, lobby_id, user_id):
        return self.db.execute(
            "SELECT 1 FROM lobby_members WHERE lobby_id = %s AND telegram_id = %s", (lobby_id, user_id)
        ).fetchone() is not None

    def require_member(self, lobby_id, user_id):
        if not self.is_member(lobby_id, user_id):
            raise GameError(404, "Лобби не найдено")

    def members(self, lobby_id):
        return self.db.execute(
            """SELECT a.telegram_id, a.display_name, m.ready FROM lobby_members m
               JOIN accounts a USING (telegram_id) WHERE m.lobby_id = %s ORDER BY a.telegram_id""",
            (lobby_id,),
        ).fetchall()

    def view(self, lobby_id, user_id):
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
                for m in self.members(lobby_id)
            ],
        }

    def ready(self, lobby_id, user_id, value):
        self.require_member(lobby_id, user_id)
        lobby = self.lock_lobby(lobby_id)
        if lobby["status"] == "started":
            if not value:
                raise GameError(409, "Серия уже создана")
            return
        self.require_open(lobby)
        self.db.execute(
            "UPDATE lobby_members SET ready = %s WHERE lobby_id = %s AND telegram_id = %s",
            (value, lobby_id, user_id),
        )
        members = self.members(lobby_id)
        status = "started" if len(members) == 2 and all(m["ready"] for m in members) else "waiting"
        if status == "started":
            self.series.start(lobby_id)
        self.db.execute("UPDATE lobbies SET status = %s WHERE id = %s", (status, lobby_id))

    def cancel(self, lobby_id, user_id):
        self.require_member(lobby_id, user_id)
        lobby = self.lock_lobby(lobby_id)
        if lobby["host_id"] != user_id:
            raise GameError(403, "Закрыть лобби может только организатор")
        if lobby["status"] != "cancelled":
            if lobby["status"] == "started":
                self.series.cancel_pending(lobby_id)
            else:
                self.require_open(lobby)
            self.db.execute("UPDATE lobbies SET status = 'cancelled' WHERE id = %s", (lobby_id,))
            self.db.execute("UPDATE lobby_members SET active = FALSE WHERE lobby_id = %s", (lobby_id,))
