from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Views(Base):
    __tablename__ = 'views'

    recipe_collection = Column(String, primary_key=True)
    recipe_id = Column(String, primary_key=True)
    viewcount = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<ViewCount({self.recipe_collection}/{self.recipe_id}: {self.viewcount})>"


class User(Base):
    __tablename__ = 'users'

    user_id = Column(String, primary_key=True)
    user_name = Column(String, nullable=True)
    user_whitelisted = Column(Boolean, default=False)

    def __repr__(self):
        return f"<User({self.user_id}: {self.user_name}" + (" [WL]>" if self.user_whitelisted else ")>")


class Comments(Base):
    __tablename__= 'comments'

    recipe_collection = Column(String, primary_key=True)
    recipe_id = Column(String, primary_key=True)
    user_id = Column(String, primary_key=True)
    comment_text = Column(String, nullable=True)
    comment_pending = Column(String, nullable=True)
    pending_secret = Column(String, nullable=True)
    comment_posted = Column(DateTime)
    comment_approved = Column(DateTime, nullable=True)
    comment_edited = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Comment({self.recipe_collection}/{self.recipe_id} {self.comment_text or self.comment_pending} [{self.user_id}])>"
