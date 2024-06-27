from .models import Save, User
from .base import Session
from sqlalchemy import select, and_


async def get_saved(user_id, collection):
    async with Session() as session:
        result = await session.execute(
            select(Save).where(and_(
                Save.user_id == user_id,
                Save.recipe_collection == collection,
            ))
        )
        return [save.recipe_id for save in result.scalars().all()]


async def get_saved_single(user_id, collection, recipe_id):
    async with Session() as session:
        result = await session.execute(
            select(Save).where(and_(
                Save.user_id == user_id,
                Save.recipe_collection == collection,
                Save.recipe_id == recipe_id,
            ))
        )
        return result.scalar() is not None


async def add_save(user_id, collection, recipe_id):
    async with Session() as session:
        result = await session.execute(
            select(Save).where(and_(
                Save.user_id == user_id,
                Save.recipe_collection == collection,
                Save.recipe_id == recipe_id,
            ))
        )
        comment = result.scalar()
        if comment is None:
            session.add(
                Save(
                    user_id=user_id,
                    recipe_collection=collection,
                    recipe_id=recipe_id,
                )
            )
            await session.commit()
