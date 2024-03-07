from sanic import Sanic

from .base import Base, engine
from .users import register_user, UserExistsException

from dotenv import load_dotenv
import os

load_dotenv()


async def init_db(app: Sanic, loop):
    print("Initializing DB")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        await register_user(os.environ.get("ADMIN_USER", "admin"), os.environ["PASSWORD"], force_verified=True)
        print("Admin user created")
    except UserExistsException:
        print("Admin user already exists")
