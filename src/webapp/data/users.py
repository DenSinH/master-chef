from .models import User
from .base import Session
from hashlib import sha256
from sqlalchemy import select, update, and_, delete


class UserExistsException(Exception):
    pass


class InvalidPasswordException(Exception):
    pass


async def _get_user(session, email):
    result = await session.execute(
        select(User).where(User.user_email == email)
    )
    return result.scalar()


async def _login_user(session, email, password):
    user = await _get_user(session, email)
    if user is None:
        return False
    if user.user_password == sha256(password):
        return user
    return None


async def login_user(email, password):
    async with Session() as session:
        return (await _login_user(session, email, password)) is not None


async def register_user(name, email, password):
    async with Session() as session:
        user = await _get_user(session, email)
        if user is not None:
            raise UserExistsException(email)
        session.add(
            User(
                user_email=email,
                user_password=password,
                user_name=name
            )
        )
        await session.commit()


async def update_user_password(email, password):
    async with Session() as session:
        user = await _login_user(session, email, password)
        if user is None:
            raise InvalidPasswordException()
        user.user_password = sha256(password)
        await session.commit()
