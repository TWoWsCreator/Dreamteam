import os
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .auth import TelegramAuth
from .domain.errors import GameError
from .http.routes import create_router

STATUS_CODES = {"not_found": 404, "conflict": 409, "forbidden": 403, "gone": 410}


def create_app(database_url=None, bot_token=None, bot_username=None, secure_cookie=None):
    database_url = database_url or os.environ["DREAMTEAM_DATABASE_URL"]
    bot_token = bot_token or os.environ["DREAMTEAM_BOT_TOKEN"]
    bot_username = bot_username or os.environ["DREAMTEAM_BOT_USERNAME"]
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", bot_username):
        raise ValueError("DREAMTEAM_BOT_USERNAME must be a Telegram bot username without @")
    if secure_cookie is None:
        secure_cookie = os.getenv("DREAMTEAM_INSECURE_LOCAL_COOKIE") != "1"
    app = FastAPI(title="Dreamteam", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

    @app.exception_handler(GameError)
    async def game_error(request, error):
        return JSONResponse(status_code=STATUS_CODES[error.code], content={"detail": error.message})

    app.include_router(create_router(database_url, TelegramAuth(bot_token), bot_username, secure_cookie))
    frontend = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app
