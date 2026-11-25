from contextlib import closing

import psycopg
from fastapi import Cookie, Depends, HTTPException
from psycopg.rows import dict_row

from ..auth import InvalidCredentials
from ..repositories.unit_of_work import UnitOfWork
from ..services.game import Game


def create_dependencies(database_url, auth):
    def game():
        with closing(psycopg.connect(database_url, autocommit=True, row_factory=dict_row, connect_timeout=5)) as db:
            yield Game(UnitOfWork(db))

    def user(dreamteam_session: str | None = Cookie(default=None), service: Game = Depends(game)):
        try:
            user_id = auth.verify_session(dreamteam_session or "")
            if service.account_exists(user_id):
                return user_id
        except InvalidCredentials:
            pass
        raise HTTPException(401, "Сессия истекла. Открой Dreamteam из Telegram")

    return game, user
