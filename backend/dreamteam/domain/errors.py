from dataclasses import dataclass


@dataclass
class GameError(Exception):
    code: str
    message: str
