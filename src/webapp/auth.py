import dataclasses
import datetime
import os
from dataclasses import dataclass
from typing import Any, Literal

import jwt
from fastapi import HTTPException, Request
from fastapi.responses import Response

JWT_ALGORITHM = "HS256"
JWT_COOKIE_NAME = "CookbookToken"
JWT_EXPIRATION_DELTA = datetime.timedelta(seconds=60 * 60)


# Load admin users from environment
def load_admin_users():
    admin_users = {}
    for __user in os.environ.get("ADMIN_USER", "admin").split(","):
        name, password = __user.split(":", maxsplit=1)
        name = name.strip()
        password = password.strip()
        if name and password:
            admin_users[name] = password
    return admin_users


ADMIN_USERS: dict[str, str] = load_admin_users()


@dataclass(frozen=True, kw_only=True, slots=True)
class User:
    username: str
    scopes: list[Literal["admin"]]
    exp: datetime.datetime

    @classmethod
    def admin(cls, username: str):
        assert username in ADMIN_USERS
        return cls(
            username=username,
            scopes=["admin"],
            exp=datetime.datetime.now().astimezone() + JWT_EXPIRATION_DELTA,
        )

    def dump(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def login(username: str, password: str | None) -> bool:
    """Try to login admin user"""
    return ADMIN_USERS.get(username) == password


def _encode_jwt(secret: str, username: str):
    """Encode a JWT token for the given username"""
    assert username in ADMIN_USERS, f"{username} is not admin, can't log them in!"

    user = User.admin(username)
    token = jwt.encode(
        user.dump(),
        secret,
        algorithm=JWT_ALGORITHM,
    )

    return token


def _decode_jwt(secret: str, token: str) -> User | None:
    """Decode a JWT token belonging to the given app"""
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
        )
        return User(**payload)
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _get_user(request: Request) -> User | None:
    """Read userdata from request"""
    token = request.cookies.get(JWT_COOKIE_NAME)

    if not token:
        return None

    return _decode_jwt(
        request.app.state.secret,
        token,
    )


def _get_username(request: Request) -> str | None:
    """Helper function to retrieve username from request
    without having to deal with the JWT manually."""
    user = _get_user(request)

    if not user:
        return None

    return user.username


def is_admin(request: Request) -> bool:
    """Helper function to retrieve admin role status from request
    without having to deal with the JWT manually."""
    user = _get_user(request)

    if not user:
        return False

    return "admin" in user.scopes


def login_user(
    username: str,
    request: Request,
    response: Response,
):
    """Login the given user by setting the JWT token cookie"""
    token = _encode_jwt(
        request.app.state.secret,
        username,
    )

    response.set_cookie(
        JWT_COOKIE_NAME,
        token,
        httponly=True,
        samesite="strict",
        max_age=int(JWT_EXPIRATION_DELTA.total_seconds()),
    )


def logout_user(response: Response) -> None:
    """Logout the user by removing the cookie"""
    response.delete_cookie(JWT_COOKIE_NAME)


def get_current_user(request: Request) -> User | None:
    """Read userdata from request."""
    token = request.cookies.get(JWT_COOKIE_NAME)

    if not token:
        return None

    return _decode_jwt(
        request.app.state.secret,
        token,
    )


async def require_admin(
    request: Request,
) -> User:
    """For use in fastapi.Depends(...) to require admin scope for a certain endpoint"""
    user = get_current_user(request)

    # validate user is logged in at all
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Token required",
        )

    # validate scopes
    user_scopes = user.scopes
    if "admin" not in user_scopes:
        raise HTTPException(
            status_code=403,
            detail="Insufficient scope",
        )

    return user
