from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class UserMeResponse(BaseModel):
    user_id: str
    username: str
    roles: list[str]
    is_superadmin: bool = False
