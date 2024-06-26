from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os


Base = declarative_base()
engine = create_async_engine(os.environ["DATABASE_URL"])
Session = sessionmaker(bind=engine, class_=AsyncSession)
