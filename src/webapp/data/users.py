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


async def _get_user(session, email):
    result = await session.execute(
        select(User).where(User.user_email == email)
    )
    return result.scalar()


async def _login_user(session, email, password):
    user = await _get_user(session, email)
    if user is None:
        return None
    if not user.user_verified:
        return None
    if user.user_password == sha256(password.encode()).hexdigest():
        return user
    return None


async def login_user(email, password):
    async with Session() as session:
        return (await _login_user(session, email, password)) is not None


def _generate_secret():
    return ''.join(random.choice(string.ascii_letters) for i in range(30))


async def register_user(name, email, password):
    async with Session() as session:
        user = await _get_user(session, email)
        if user is not None:
            if user.user_verified:
                raise UserExistsException(email)
            else:
                await session.delete(user)

        secret = _generate_secret()
        session.add(
            User(
                user_email=email,
                user_password=sha256(password.encode()).hexdigest(),
                user_name=name,
                user_verification_secret=secret,
                user_verification_sent=datetime.datetime.now(),
            )
        )
        await session.commit()
    return secret


async def validate_user(email, secret):
    async with Session() as session:
        user = await _get_user(session, email)
        if user.user_verification_secret != secret:
            raise RegistrationError("Wrong secret!")
        if datetime.datetime.now() - user.user_verification_sent > datetime.timedelta(hours=1):
            raise RegistrationError("Took too long!")
        user.user_verified = True
        user.user_verification_secret = None
        await session.commit()


async def update_user_password(email, password):
    async with Session() as session:
        user = await _login_user(session, email, password)
        if user is None:
            raise InvalidPasswordException()
        user.user_password = sha256(password.encode()).hexdigest()
        await session.commit()
