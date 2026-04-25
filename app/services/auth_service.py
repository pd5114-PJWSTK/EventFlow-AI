from dataclasses import dataclass

from app.config import Settings


@dataclass
class User:
    username: str
    roles: list[str]


def authenticate_user(username: str, password: str, settings: Settings) -> User | None:
    if username == settings.demo_admin_username and password == settings.demo_admin_password:
        return User(username=username, roles=["manager", "coordinator", "technician"])
    return None
