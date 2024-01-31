from sanic import Sanic

from .base import Base, engine
from .users import register_user, UserExistsException


async def init_db(app: Sanic, loop):
    print("Initializing DB")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        await register_user("Test User", "test@example.com", "password")
    except UserExistsException:
        print("Test user already created")
