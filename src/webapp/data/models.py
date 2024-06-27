from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy import select, update, and_, delete

from .base import Base, Session


class RecipeBoundMixin:
    """ Mixin to handle basic recipe CRUD operations like
    moving, deleting ... """
        
    @classmethod
    async def move_recipe(cls, collectionfrom, collectionto, idfrom, idto):
        async with Session() as session:
            await session.execute(
                update(cls).where(and_(
                    cls.recipe_collection == collectionfrom,
                    cls.recipe_id == idfrom
                ))
                .values(
                    recipe_collection=collectionto,
                    recipe_id=idto
                )
            )
            await session.commit()

    @classmethod
    async def delete_recipe(cls, collection, recipe_id):
        async with Session() as session:
            await session.execute(
                delete(cls).where(and_(
                    cls.recipe_collection == collection,
                    cls.recipe_id == recipe_id
                ))
            )
            await session.commit()


class UserRecipeBoundMixin:

    """ Mixin for handling operations on user/recipe bound CRUD
    operations """

    @classmethod
    async def delete_for_user(cls, user_id: str, collection: str, recipe_id: str):
        async with Session() as session:
            await session.execute(
                delete(cls).where(and_(
                    cls.recipe_collection == collection,
                    cls.recipe_id == recipe_id,
                    cls.user_id == user_id
                ))
            )
            await session.commit()



class Views(Base, RecipeBoundMixin):
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
        return f"<User({self.username}" + (" [V]>" if self.verified else ")>")


class Comment(Base, RecipeBoundMixin, UserRecipeBoundMixin):
    __tablename__ = 'comments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    recipe_collection = Column(String, primary_key=True)
    recipe_id = Column(String, primary_key=True)
    user_id = Column(Integer, primary_key=True)
    rating = Column(Integer, nullable=False)
    text = Column(String, nullable=True)
    date_posted = Column(DateTime)
    date_edited = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Comment({self.recipe_collection}/{self.recipe_id} {self.text} [{self.user_id}])>"


class Save(Base, RecipeBoundMixin, UserRecipeBoundMixin):
    __tablename__ = 'saves'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, primary_key=True)
    recipe_collection = Column(String, primary_key=True)
    recipe_id = Column(String, primary_key=True)