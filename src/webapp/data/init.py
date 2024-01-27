from sanic import Sanic
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import asyncio

from .models import Base

from dotenv import load_dotenv
import os

load_dotenv()

print(os.environ["DATABASE_URL"])
engine = create_async_engine(os.environ["DATABASE_URL"], echo=True)


async def _init_app(app: Sanic):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return sessionmaker(bind=engine, class_=AsyncSession)


def init_app(app: Sanic):
    return asyncio.run(_init_app(app))
