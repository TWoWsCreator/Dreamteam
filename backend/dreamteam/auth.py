import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class InvalidCredentials(ValueError):
    pass


@dataclass(frozen=True)
class TelegramUser:
    id: int
    name: str


class TelegramAuth:
    def __init__(self, bot_token: str):
        self.init_key = hmac.digest(b"WebAppData", bot_token.encode(), "sha256")
        self.session_key = hmac.digest(bot_token.encode(), b"dreamteam-session", "sha256")
        self.invite_key = hmac.digest(bot_token.encode(), b"dreamteam-invite", "sha256")

    def verify_init_data(self, raw: str) -> TelegramUser:
        try:
            pairs = parse_qsl(raw, strict_parsing=True, keep_blank_values=True, max_num_fields=32)
            fields = dict(pairs)
            if len(fields) != len(pairs):
                raise ValueError
            supplied = fields.pop("hash")
            check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
            expected = hmac.new(self.init_key, check_string.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(supplied, expected):
                raise ValueError
            age = int(time.time()) - int(fields["auth_date"])
            if not -30 <= age <= 900:
                raise ValueError

            user = json.loads(fields["user"])
            user_id = user["id"]
            if type(user_id) is not int or not 0 < user_id < 2**52:
                raise ValueError
            name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x)
            return TelegramUser(user_id, name.strip()[:128] or "Игрок")
        except (TypeError, ValueError, KeyError) as exc:
            raise InvalidCredentials from exc

    def issue_session(self, user_id: int) -> str:
        body = f"{user_id}.{int(time.time()) + 86400}"
        signature = hmac.digest(self.session_key, body.encode(), "sha256").hex()
        return f"{body}.{signature}"

    def verify_session(self, token: str) -> int:
        try:
            user, expiry, signature = token.split(".")
            expected = hmac.digest(self.session_key, f"{user}.{expiry}".encode(), "sha256").hex()
            if not hmac.compare_digest(signature, expected) or int(expiry) <= time.time():
                raise ValueError
            return int(user)
        except (TypeError, ValueError) as exc:
            raise InvalidCredentials from exc

    def invite_code(self, lobby_id: str) -> str:
        checksum = hmac.digest(self.invite_key, lobby_id.encode(), "sha256").hex()[:24]
        return f"{lobby_id}_{checksum}"
