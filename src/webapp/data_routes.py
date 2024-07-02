import sanic
from sanic import Sanic, Request
from sanic_jwt import protected, scoped
import re
import data.users as users
import data.comments as comments
import data.saves as saves
from data.models import Comment, Save
from limiter import RateLimiter


def add_data_routes(app: Sanic):
    @app.get("/saved/<collection>")
    @protected()
    @scoped("user")
    async def get_saved(request: Request, collection):
        """ Get saved recipes in collection for active user """
        username = await app.ctx.auth.extract_user_id(request)
        user = await users.get_user(username)
        if user is None:
            return sanic.json({"error": "Unknown user"}, 400)

        return sanic.json({
            "saves": await saves.get_saved(user.id, collection)
        })


    @app.get("/saved/<collection>/<recipe_id>")
    @protected()
    @scoped("user")
    async def get_saved_single(request: Request, collection, recipe_id):
        """ Get whether the specified recipe is saved by the active user """
        username = await app.ctx.auth.extract_user_id(request)
        user = await users.get_user(username)
        if user is None:
            return sanic.json({"error": "Unknown user"}, 400)

        return sanic.json({
            "saved": await saves.get_saved_single(user.id, collection, recipe_id)
        })


    @app.post("/saved/<collection>/<id>", ctx_limiter=RateLimiter(times=1, seconds=1))
    @protected()
    @scoped("user")
    async def post_save(request: Request, collection, id):
        """ Save the recipe for the active user """
        username = await app.ctx.auth.extract_user_id(request)
        user = await users.get_user(username)
        if user is None:
            return sanic.json({"error": "Unknown user"}, 400)
        await saves.add_save(user.id, collection, id)
        return sanic.empty()


    @app.delete("/saved/<collection>/<id>", ctx_limiter=RateLimiter(times=1, seconds=1))
    @protected()
    @scoped("user")
    async def delete_save(request: Request, collection, id):
        """ Unsave the recipe for the active user """
        username = await app.ctx.auth.extract_user_id(request)
        user = await users.get_user(username)
        if user is None:
            return sanic.json({"error": "Unknown user"}, 400)
        
        await Save.delete_for_user(user.id, collection, id)
        return sanic.empty()


    @app.post("/comment/<collection>/<id>", ctx_limiter=RateLimiter(times=5, minutes=1))
    @protected()
    @scoped("user")
    async def post_comment(request: Request, collection, id):
        """ Post a comment on the recipe for the active user """
        username = await app.ctx.auth.extract_user_id(request)
        user = await users.get_user(username)
        if user is None:
            return sanic.json({"error": "Unknown user"}, 400)
        text = re.sub(r"\s+", " ", request.json.get("text").strip())
        if len(text) > 500:
            return sanic.json({"error": "Review should be < 500 characters"}, 400)
        rating = request.json.get("rating")
        if rating is None or not (1 <= rating <= 5):
            return sanic.json({"error": "Rating should be between 1 and 5"}, 400)

        await comments.add_comment(collection, id, user.id, text, rating)
        return sanic.empty()


    @app.delete("/comment/<collection>/<id>", ctx_limiter=RateLimiter(times=5, minutes=1))
    @protected()
    @scoped("user")
    async def delete_comment(request: Request, collection, id):
        """ Delete a comment on the recipe for the active user """
        username = await app.ctx.auth.extract_user_id(request)
        user = await users.get_user(username)
        if user is None:
            return sanic.json({"error": "Unknown user"}, 400)

        await Comment.delete_for_user(user.id, collection, id)
        return sanic.empty()
