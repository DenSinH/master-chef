from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Views(Base):
    __tablename__ = 'views'

    recipe_collection = Column(String, primary_key=True)
    recipe_id = Column(String, primary_key=True)
    viewcount = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<ViewCount({self.recipe_collection}/{self.recipe_id}: {self.viewcount})>"