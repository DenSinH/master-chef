from .models import Save, User
from .base import Session
from sqlalchemy import select, update, and_, delete


async def get_saves(user_id, collection):
    async with Session() as session:
        result = await session.execute(
            select(Save).where(and_(
                Save.user_id == user_id,
                Save.recipe_collection == collection,
            ))
        )
        return [save.recipe_id for save in result.scalars().all()]


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


async def delete_save(user_id, collection, recipe_id):
    async with Session() as session:
        await session.execute(
            delete(Save).where(and_(
                Save.recipe_collection == collection,
                Save.recipe_id == recipe_id,
                Save.user_id == user_id
            ))
        )
        await session.commit()


async def delete_saves(collection, recipe_id):
    async with Session() as session:
        await session.execute(
            delete(Save).where(and_(
                Save.recipe_collection == collection,
                Save.recipe_id == recipe_id
            ))
        )
        await session.commit()


async def move_saves(collectionfrom, collectionto, idfrom, idto):
    async with Session() as session:
        await session.execute(
            update(Save).where(and_(
                Save.recipe_collection == collectionfrom,
                Save.recipe_id == idfrom
            ))
            .values(
                recipe_collection=collectionto,
                recipe_id=idto
            )
        )
        await session.commit()
