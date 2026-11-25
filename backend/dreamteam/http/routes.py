import hmac
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, StrictBool

from ..auth import InvalidCredentials
from ..domain.errors import GameError
from ..domain.rules import Map, Preset, Side
from ..services.game import Game
from .dependencies import create_dependencies

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


def create_router(database_url, auth, bot_username, secure_cookie):
    router = APIRouter(prefix="/api")
    game, user = create_dependencies(database_url, auth)

    def lobby_response(result):
        if result["canInvite"]:
            code = auth.invite_code(str(result["id"]))
            result["inviteUrl"] = f"https://t.me/{bot_username}?startapp={code}"
        return result

    @router.get("/health")
    def health(service: Game = Depends(game)):
        service.health()
        return {"status": "ok"}

    @router.post("/session")
    def login(body: Login, response: Response, service: Game = Depends(game)):
        try:
            player = auth.verify_init_data(body.initData)
        except InvalidCredentials:
            raise HTTPException(401, "Не удалось подтвердить вход через Telegram") from None
        profile = service.login(player)
        response.set_cookie(
            SESSION, auth.issue_session(player.id), httponly=True, secure=secure_cookie,
            samesite="lax", max_age=86400, path="/api",
        )
        return profile

    @router.get("/me")
    def profile(user_id: int = Depends(user), service: Game = Depends(game)):
        return service.profile(user_id)

    @router.get("/tactics")
    def tactics(user_id: int = Depends(user), service: Game = Depends(game)):
        return service.tactics(user_id)

    @router.put("/tactics")
    def save_tactic(body: Tactic, user_id: int = Depends(user), service: Game = Depends(game)):
        service.save_tactic(user_id, body.map, body.side, body.preset)
        return body

    @router.post("/lobbies")
    def create_lobby(user_id: int = Depends(user), service: Game = Depends(game)):
        return lobby_response(service.create_lobby(user_id))

    @router.post("/lobbies/join")
    def join(body: Invitation, user_id: int = Depends(user), service: Game = Depends(game)):
        if not INVITE.fullmatch(body.code):
            raise GameError("not_found", "Приглашение не найдено")
        try:
            lobby_id = UUID(body.code.split("_")[0])
        except ValueError:
            raise GameError("not_found", "Приглашение не найдено") from None
        if not hmac.compare_digest(body.code, auth.invite_code(str(lobby_id))):
            raise GameError("not_found", "Приглашение не найдено")
        return lobby_response(service.join(lobby_id, user_id))

    @router.get("/lobbies/{lobby_id}")
    def lobby(lobby_id: UUID, user_id: int = Depends(user), service: Game = Depends(game)):
        return lobby_response(service.lobby(lobby_id, user_id))

    @router.put("/lobbies/{lobby_id}/ready")
    def ready(lobby_id: UUID, body: Readiness, user_id: int = Depends(user), service: Game = Depends(game)):
        return lobby_response(service.ready(lobby_id, user_id, body.ready))

    @router.delete("/lobbies/{lobby_id}")
    def cancel(lobby_id: UUID, user_id: int = Depends(user), service: Game = Depends(game)):
        return lobby_response(service.cancel(lobby_id, user_id))

    @router.get("/series/{series_id}")
    def series(series_id: UUID, user_id: int = Depends(user), service: Game = Depends(game)):
        return service.read_series(series_id, user_id)

    return router
