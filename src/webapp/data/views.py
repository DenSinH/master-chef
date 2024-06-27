from .models import Views
from .base import Session
from sqlalchemy import select, and_


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

