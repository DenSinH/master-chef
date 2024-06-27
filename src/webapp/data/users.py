import sanic

from .models import User
from .base import Session
from hashlib import sha256
from sqlalchemy import select
import datetime


class UserExistsException(Exception):
    pass


class InvalidPasswordException(Exception):
    pass


class RegistrationError(Exception):
    pass


async def _get_user(session, username) -> User:
    username = username.strip()
    result = await session.execute(
        select(User).where(User.username == username)
    )
    return result.scalar()


async def _login_user(session, username, password) -> User | None:
    username = username.strip()
    user = await _get_user(session, username)
    if user is None:
        return None
    if user.password == sha256(password.encode()).hexdigest():
        return user
    return None


async def get_user(username) -> User | None:
    username = username.strip()
    async with Session() as session:
        return await _get_user(session, username.strip())


async def login_user(username, password) -> User | None:
    username = username.strip()
    async with Session() as session:
        return (await _login_user(session, username, password)) is not None


async def register_user(username, password, force_verified=False):
    username = username.strip()
    async with Session() as session:
        user = await _get_user(session, username)
        if user is not None:
            raise UserExistsException(username)

        session.add(
            User(
                username=username,
                password=sha256(password.encode()).hexdigest(),
                date_registered=datetime.datetime.now(),
                verified=force_verified
            )
        )
        await session.commit()


async def update_user_password(username, newpassword):
    username = username.strip()
    async with Session() as session:
        user = await _get_user(session, username)
        if user is None:
            raise sanic.NotFound()

        user.password = sha256(newpassword.encode()).hexdigest()
        await session.commit()


async def count_unverified():
    async with Session() as session:
        count = await session.execute(
            select(func.count()).filter(User.verified == False)
        )
        return count.scalar()
