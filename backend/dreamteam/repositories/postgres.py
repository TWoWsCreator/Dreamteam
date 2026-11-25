from uuid import uuid4


class PostgresRepository:
    def __init__(self, connection):
        self.db = connection

    def health(self):
        self.db.execute("SELECT 1 FROM accounts LIMIT 1")

    def account_exists(self, user_id):
        return self.db.execute(
            "SELECT 1 FROM accounts WHERE telegram_id = %s", (user_id,)
        ).fetchone() is not None

    def save_account(self, user):
        self.db.execute(
            """INSERT INTO accounts (telegram_id, display_name) VALUES (%s, %s)
               ON CONFLICT (telegram_id) DO UPDATE SET display_name = EXCLUDED.display_name""",
            (user.id, user.name),
        )

    def grant_starting_team(self, user_id):
        self.db.execute(
            """INSERT INTO team_players (telegram_id, slot, template_code, power)
               SELECT %s, slot, code, power FROM card_templates
               ON CONFLICT (telegram_id, slot) DO NOTHING""",
            (user_id,),
        )

    def account(self, user_id):
        return self.db.execute(
            "SELECT display_name FROM accounts WHERE telegram_id = %s", (user_id,)
        ).fetchone()

    def team(self, user_id):
        return self.db.execute(
            """SELECT t.slot, c.role, c.name, c.description, t.power
               FROM team_players t JOIN card_templates c ON c.code = t.template_code
               WHERE t.telegram_id = %s ORDER BY t.slot""",
            (user_id,),
        ).fetchall()

    def list_tactics(self, user_id):
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

    def active_lobby(self, user_id):
        return self.db.execute(
            """SELECT l.id, l.host_id, l.status FROM lobby_members m JOIN lobbies l ON l.id = m.lobby_id
               WHERE m.telegram_id = %s AND m.active
                 AND (l.status = 'started' OR l.expires_at > clock_timestamp())""",
            (user_id,),
        ).fetchone()

    def release_expired_lobbies(self):
        self.db.execute(
            """WITH expired AS (
                   UPDATE lobbies SET status = 'expired'
                   WHERE expires_at <= clock_timestamp() AND status IN ('waiting', 'ready')
                   RETURNING id
               )
               UPDATE lobby_members SET active = FALSE
               WHERE lobby_id IN (SELECT id FROM expired) AND active"""
        )

    def lock_account(self, user_id):
        self.db.execute("SELECT telegram_id FROM accounts WHERE telegram_id = %s FOR NO KEY UPDATE", (user_id,))

    def create_lobby(self, user_id):
        lobby_id = uuid4()
        self.db.execute(
            """INSERT INTO lobbies (id, host_id, expires_at)
               VALUES (%s, %s, clock_timestamp() + INTERVAL '30 minutes')""",
            (lobby_id, user_id),
        )
        self.add_member(lobby_id, user_id)
        return lobby_id

    def add_member(self, lobby_id, user_id):
        return self.db.execute(
            """INSERT INTO lobby_members (lobby_id, telegram_id) VALUES (%s, %s)
               ON CONFLICT DO NOTHING RETURNING telegram_id""",
            (lobby_id, user_id),
        ).fetchone() is not None

    def lock_lobby(self, lobby_id):
        return self.db.execute(
            """SELECT *, expires_at > clock_timestamp() AS valid
               FROM lobbies WHERE id = %s FOR UPDATE""",
            (lobby_id,),
        ).fetchone()

    def is_member(self, lobby_id, user_id):
        return self.db.execute(
            "SELECT 1 FROM lobby_members WHERE lobby_id = %s AND telegram_id = %s", (lobby_id, user_id)
        ).fetchone() is not None

    def members(self, lobby_id):
        return self.db.execute(
            """SELECT a.telegram_id, a.display_name, m.ready FROM lobby_members m
               JOIN accounts a USING (telegram_id) WHERE m.lobby_id = %s ORDER BY a.telegram_id""",
            (lobby_id,),
        ).fetchall()

    def set_member_ready(self, lobby_id, user_id, ready):
        self.db.execute(
            "UPDATE lobby_members SET ready = %s WHERE lobby_id = %s AND telegram_id = %s",
            (ready, lobby_id, user_id),
        )

    def set_lobby_status(self, lobby_id, status):
        self.db.execute("UPDATE lobbies SET status = %s WHERE id = %s", (status, lobby_id))

    def deactivate_members(self, lobby_id):
        self.db.execute("UPDATE lobby_members SET active = FALSE WHERE lobby_id = %s", (lobby_id,))
