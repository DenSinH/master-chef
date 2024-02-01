# from .models import Comment
# from .base import Session
# from sqlalchemy import select, update, and_, delete
#
#
# async def _get_comments(session, collection, recipe_id):
#     result = await session.execute(
#         select(Comment) \
#             .where(and_(
#                 Comment.recipe_collection == collection,
#                 Comment.recipe_id == recipe_id,
#                 Comment.comment_approved
#             ))
#     )
#     return result.scalar()
#
#
# async def get_viewcount_single(collection, recipe_id):
#     async with Session() as session:
#         views = await _get_viewcount(session, collection, recipe_id)
#         if views is None:
#             return 0
#         return views.viewcount
#
#
# async def incr_viewcount(collection, recipe_id):
#     async with Session() as session:
#         views = await _get_viewcount(session, collection, recipe_id)
#
#         if views is not None:
#             views.viewcount += 1
#         else:
#             views = Views(recipe_collection=collection, recipe_id=recipe_id, viewcount=1)
#             session.add(views)
#         viewcount = views.viewcount
#         await session.commit()
#     return viewcount
#
#
# async def move_viewcount(collectionfrom, collectionto, idfrom, idto):
#     async with Session() as session:
#         viewsfrom = await _get_viewcount(session, collectionfrom, idfrom)
#
#         if viewsfrom is not None:
#             session.add(
#                 Views(
#                     recipe_collection=collectionto,
#                     recipe_id=idto,
#                     viewcount=viewsfrom.viewcount
#                 )
#             )
#             await session.execute(
#                 delete(Views) \
#                     .where(and_(Views.recipe_collection == collectionfrom, Views.recipe_id == idfrom))
#             )
#             await session.commit()
#
#
# async def delete_viewcount(collection, id):
#     async with Session() as session:
#         await session.execute(
#             delete(Views) \
#                 .where(and_(Views.recipe_collection == collection, Views.recipe_id == id))
#         )
#         await session.commit()
#
