from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
import asyncpg

Base = declarative_base()


class Views(Base):
    __tablename__ = 'views'

    id = Column(Integer, primary_key=True)
    recipe_collection = Column(String, nullable=False)
    recipe_id = Column(String, nullable=False)
    viewcount = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<ViewCount({self.recipe_collection}/{self.recipe_id}: {self.viewcount})>"