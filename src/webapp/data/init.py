from sanic import Sanic
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .models import Base

from dotenv import load_dotenv
import os

load_dotenv()

engine = create_async_engine(os.environ["DATABASE_URL"])
Session = sessionmaker(bind=engine, class_=AsyncSession)


async def init_db(app: Sanic, loop):
    print("Initializing DB")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

