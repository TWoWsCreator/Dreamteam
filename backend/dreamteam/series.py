from uuid import uuid4


class SeriesRepository:
    def __init__(self, connection):
        self.db = connection

    def find_by_lobby(self, lobby_id):
        return self.db.execute(
            "SELECT id, phase FROM series WHERE lobby_id = %s",
            (lobby_id,),
        ).fetchone()

    def find_for_player(self, series_id, user_id):
        return self.db.execute(
            """SELECT s.id, s.phase FROM series s
               JOIN lobby_members m ON m.lobby_id = s.lobby_id
               WHERE s.id = %s AND m.telegram_id = %s""",
            (series_id, user_id),
        ).fetchone()

    def start(self, lobby_id):
        self.db.execute(
            """INSERT INTO series (id, lobby_id, phase) VALUES (%s, %s, 'awaiting_veto')
               ON CONFLICT (lobby_id) DO NOTHING""",
            (uuid4(), lobby_id),
        )

    def cancel_pending(self, lobby_id):
        self.db.execute(
            "UPDATE series SET phase = 'cancelled' WHERE lobby_id = %s AND phase = 'awaiting_veto'",
            (lobby_id,),
        )
