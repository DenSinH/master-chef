from .models import Views
from .base import Session
from sqlalchemy import select, update, and_, delete


async def get_viewcount(collection):
    async with Session() as session:
        result = await session.execute(
            select(Views) \
                .where(Views.recipe_collection == collection)
        )
        views = result.scalars().all()

    return {
        view.recipe_id: view.viewcount for view in views
    }


async def _get_viewcount(session, collection, recipe_id):
    result = await session.execute(
        select(Views) \
            .where(and_(Views.recipe_collection == collection, Views.recipe_id == recipe_id))
    )
    return result.scalar()


async def get_viewcount_single(collection, recipe_id):
    async with Session() as session:
        views = await _get_viewcount(session, collection, recipe_id)
        if views is None:
            return 0
        return views.viewcount


async def incr_viewcount(collection, recipe_id):
    async with Session() as session:
        views = await _get_viewcount(session, collection, recipe_id)

        if views is not None:
            views.viewcount += 1
        else:
            views = Views(recipe_collection=collection, recipe_id=recipe_id, viewcount=1)
            session.add(views)
        viewcount = views.viewcount
        await session.commit()
    return viewcount


async def move_viewcount(collectionfrom, collectionto, idfrom, idto):
    async with Session() as session:
        viewsfrom = await _get_viewcount(session, collectionfrom, idfrom)

        if viewsfrom is not None:
            session.add(
                Views(
                    recipe_collection=collectionto,
                    recipe_id=idto,
                    viewcount=viewsfrom.viewcount
                )
            )
            await session.execute(
                delete(Views) \
                    .where(and_(Views.recipe_collection == collectionfrom, Views.recipe_id == idfrom))
            )
            await session.commit()


async def delete_viewcount(collection, id):
    async with Session() as session:
        await session.execute(
            delete(Views) \
                .where(and_(Views.recipe_collection == collection, Views.recipe_id == id))
        )
        await session.commit()

