from .models import Comment, User
from .base import Session
from sqlalchemy import select, update, and_, delete
import datetime


async def get_comments(collection, recipe_id):
    async with Session() as session:
        result = await session.execute(
            select(Comment, User) \
                .where(and_(
                    Comment.recipe_collection == collection,
                    Comment.recipe_id == recipe_id
                )).filter(
                    Comment.user_id == User.id
                )
        )
        return result.all()


async def add_comment(collection, recipe_id, user_id, text, rating):
    async with Session() as session:
        result = await session.execute(
            select(Comment).where(and_(
                Comment.recipe_collection == collection,
                Comment.recipe_id == recipe_id,
                Comment.user_id == user_id
            ))
        )
        comment = result.scalar()
        if comment is None:
            session.add(
                Comment(
                    recipe_collection=collection,
                    recipe_id=recipe_id,
                    user_id=user_id,
                    rating=rating,
                    text=text,
                    date_posted=datetime.datetime.now()
                )
            )
        else:
            comment.text = text
            comment.rating = rating
            comment.date_edited = datetime.datetime.now()
        await session.commit()


async def delete_comment(collection, recipe_id, user_id):
    async with Session() as session:
        await session.execute(
            delete(Comment).where(and_(
                Comment.recipe_collection == collection,
                Comment.recipe_id == recipe_id,
                Comment.user_id == user_id
            ))
        )
        await session.commit()


async def delete_comments(collection, recipe_id):
    async with Session() as session:
        await session.execute(
            delete(Comment).where(and_(
                Comment.recipe_collection == collection,
                Comment.recipe_id == recipe_id
            ))
        )
        await session.commit()


async def move_comments(collectionfrom, collectionto, idfrom, idto):
    async with Session() as session:
        await session.execute(
            update(Comment).where(and_(
                Comment.recipe_collection == collectionfrom,
                Comment.recipe_id == idfrom
            ))
            .values(
                recipe_collection=collectionto,
                recipe_id=idto
            )
        )
        await session.commit()
