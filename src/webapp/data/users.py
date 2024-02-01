import sanic

from .models import User
from .base import Session
from hashlib import sha256
from sqlalchemy import select, update, and_, delete
import random
import string
import datetime


class UserExistsException(Exception):
    pass


class InvalidPasswordException(Exception):
    pass


class RegistrationError(Exception):
    pass


async def _get_user(session, username):
    username = username.strip()
    result = await session.execute(
        select(User).where(User.username == username)
    )
    return result.scalar()


async def _login_user(session, username, password):
    username = username.strip()
    user = await _get_user(session, username)
    if user is None:
        return None
    if user.password == sha256(password.encode()).hexdigest():
        return user
    return None


async def get_user(username):
    username = username.strip()
    async with Session() as session:
        return await _get_user(session, username.strip())


async def login_user(username, password):
    username = username.strip()
    async with Session() as session:
        return (await _login_user(session, username, password)) is not None


def _generate_secret():
    return ''.join(random.choice(string.ascii_letters) for i in range(30))


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
