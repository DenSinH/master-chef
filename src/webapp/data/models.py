from sqlalchemy import Column, Integer, String, DateTime, Boolean

from .base import Base


class Views(Base):
    __tablename__ = 'views'

    recipe_collection = Column(String, primary_key=True)
    recipe_id = Column(String, primary_key=True)
    viewcount = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<ViewCount({self.recipe_collection}/{self.recipe_id}: {self.viewcount})>"


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, primary_key=True)
    password = Column(String, nullable=True)
    verified = Column(Boolean, default=False)
    date_registered = Column(DateTime)

    def __repr__(self):
        return f"<User({self.user_email}: {self.user_name}" + (" [WL]>" if self.user_whitelisted else ")>")


class Comment(Base):
    __tablename__ = 'comments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    recipe_collection = Column(String, primary_key=True)
    recipe_id = Column(String, primary_key=True)
    user_id = Column(String, primary_key=True)
    rating = Column(Integer, nullable=False)
    text = Column(String, nullable=True)
    date_posted = Column(DateTime)
    date_edited = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Comment({self.recipe_collection}/{self.recipe_id} {self.comment_text or self.comment_pending} [{self.user_id}])>"
