import hmac
import os
import re
from contextlib import closing
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, StrictBool

from .auth import InvalidCredentials, TelegramAuth
from .game import Game, GameError, Map, Preset, Side

SESSION = "dreamteam_session"
INVITE = re.compile(r"[0-9a-f-]{36}_[0-9a-f]{24}")


class Login(BaseModel):
    initData: str = Field(min_length=1, max_length=16384)


class Invitation(BaseModel):
    code: str = Field(max_length=64)


class Tactic(BaseModel):
    map: Map
    side: Side
    preset: Preset


class Readiness(BaseModel):
    ready: StrictBool


def create_app(database_url=None, bot_token=None, bot_username=None, secure_cookie=None):
    database_url = database_url or os.environ["DREAMTEAM_DATABASE_URL"]
    bot_token = bot_token or os.environ["DREAMTEAM_BOT_TOKEN"]
    bot_username = bot_username or os.environ["DREAMTEAM_BOT_USERNAME"]
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", bot_username):
        raise ValueError("DREAMTEAM_BOT_USERNAME must be a Telegram bot username without @")
    if secure_cookie is None:
        secure_cookie = os.getenv("DREAMTEAM_INSECURE_LOCAL_COOKIE") != "1"
    auth = TelegramAuth(bot_token)
    app = FastAPI(title="Dreamteam", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

    @app.exception_handler(GameError)
    async def game_error(request, error):
        return JSONResponse(status_code=error.status, content={"detail": error.message})

    def game():
        with closing(psycopg.connect(database_url, row_factory=dict_row, connect_timeout=5)) as db:
            yield Game(db)

    def user(dreamteam_session: str | None = Cookie(default=None), game: Game = Depends(game)):
        try:
            user_id = auth.verify_session(dreamteam_session or "")
        except InvalidCredentials:
            raise HTTPException(401, "Сессия истекла. Открой Dreamteam из Telegram") from None
        if not game.db.execute("SELECT 1 FROM accounts WHERE telegram_id = %s", (user_id,)).fetchone():
            raise HTTPException(401, "Сессия истекла. Открой Dreamteam из Telegram")
        return user_id

    def lobby_response(game, lobby_id, user_id):
        result = game.view(lobby_id, user_id)
        if result["canInvite"]:
            code = auth.invite_code(str(lobby_id))
            result["inviteUrl"] = f"https://t.me/{bot_username}?startapp={code}"
        return result

    @app.get("/api/health")
    def health(game: Game = Depends(game)):
        game.db.execute("SELECT 1 FROM accounts LIMIT 1")
        return {"status": "ok"}

    @app.post("/api/session")
    def login(body: Login, response: Response, game: Game = Depends(game)):
        try:
            player = auth.verify_init_data(body.initData)
        except InvalidCredentials:
            raise HTTPException(401, "Не удалось подтвердить вход через Telegram") from None
        game.login(player)
        profile = game.profile(player.id)
        game.db.commit()
        response.set_cookie(
            SESSION, auth.issue_session(player.id), httponly=True, secure=secure_cookie,
            samesite="lax", max_age=86400, path="/api",
        )
        return profile

    @app.get("/api/me")
    def profile(user_id: int = Depends(user), game: Game = Depends(game)):
        return game.profile(user_id)

    @app.get("/api/tactics")
    def tactics(user_id: int = Depends(user), game: Game = Depends(game)):
        return game.tactics(user_id)

    @app.put("/api/tactics")
    def save_tactic(body: Tactic, user_id: int = Depends(user), game: Game = Depends(game)):
        game.save_tactic(user_id, body.map, body.side, body.preset)
        game.db.commit()
        return body

    @app.post("/api/lobbies")
    def create_lobby(user_id: int = Depends(user), game: Game = Depends(game)):
        lobby_id = game.create_lobby(uuid4(), user_id)
        result = lobby_response(game, lobby_id, user_id)
        game.db.commit()
        return result

    @app.post("/api/lobbies/join")
    def join(body: Invitation, user_id: int = Depends(user), game: Game = Depends(game)):
        if not INVITE.fullmatch(body.code):
            raise GameError(404, "Приглашение не найдено")
        try:
            lobby_id = UUID(body.code.split("_")[0])
        except ValueError:
            raise GameError(404, "Приглашение не найдено") from None
        if not hmac.compare_digest(body.code, auth.invite_code(str(lobby_id))):
            raise GameError(404, "Приглашение не найдено")
        game.join(lobby_id, user_id)
        result = lobby_response(game, lobby_id, user_id)
        game.db.commit()
        return result

    @app.get("/api/lobbies/{lobby_id}")
    def lobby(lobby_id: UUID, user_id: int = Depends(user), game: Game = Depends(game)):
        return lobby_response(game, lobby_id, user_id)

    @app.put("/api/lobbies/{lobby_id}/ready")
    def ready(lobby_id: UUID, body: Readiness, user_id: int = Depends(user), game: Game = Depends(game)):
        game.ready(lobby_id, user_id, body.ready)
        result = lobby_response(game, lobby_id, user_id)
        game.db.commit()
        return result

    @app.delete("/api/lobbies/{lobby_id}")
    def cancel(lobby_id: UUID, user_id: int = Depends(user), game: Game = Depends(game)):
        game.cancel(lobby_id, user_id)
        result = lobby_response(game, lobby_id, user_id)
        game.db.commit()
        return result

    @app.get("/api/series/{series_id}")
    def series(series_id: UUID, user_id: int = Depends(user), game: Game = Depends(game)):
        result = game.series.find_for_player(series_id, user_id)
        if result is None:
            raise GameError(404, "Серия не найдена")
        return result

    frontend = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")

    return app
