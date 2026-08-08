import hashlib
from collections import OrderedDict

import sanic
from dotenv import load_dotenv
from sanic import Request
from sanic.exceptions import NotFound
from sanic_ext import render

from . import auth, cookbook

load_dotenv()

from .app import app

""" initialize sectioned routes """
from .admin_routes import add_admin_routes
from .error_routes import add_error_routes
from .user_routes import add_user_routes

add_error_routes(app)
add_user_routes(app)
add_admin_routes(app)


""" General public cookbook viewing routes """


@app.get("/")
async def index(request: Request):
    """Index page"""
    # show default collection
    return await collection(request, collection=cookbook.DEFAULT_COLLECTION)


def _update_etag_reqinfo(
    etag: hashlib._Hash, is_admin: bool, username: str | None
) -> str:
    """Update etag hash with request info"""
    etag.update(is_admin.to_bytes())
    etag.update((username or "").encode("utf-8", errors="ignore"))
    return etag.hexdigest()


@app.get("/collection/<collection:str>")
async def collection(request: Request, collection: str = cookbook.DEFAULT_COLLECTION):
    """Get a recipe collection"""
    # get request info
    is_admin = auth.is_admin(request)
    username = auth.get_username(request)

    # check caching with collection SHA
    etag = _update_etag_reqinfo(
        hashlib.sha256(
            (await cookbook.get_collection_etag(collection)).encode("ascii"),
            usedforsecurity=False,
        ),
        is_admin=is_admin,
        username=username,
    )

    if not app.debug:
        if_match = request.headers.get("If-None-Match")
        if if_match is not None and if_match == etag:
            # use cached response
            return sanic.empty(headers={"ETag": etag}, status=304)

    recipes = await cookbook.get_recipes(collection)

    # sort recipes by date_updated (default ordering)
    ordered = OrderedDict(
        sorted(recipes.items(), key=lambda x: x[1].date_updated, reverse=True)
    )

    # user-specific rendering
    if username is not None:
        title = f"{username}'s Kitchen"
    else:
        title = cookbook.generate_title()

    return await render(
        "cookbook.html",
        headers={"ETag": etag},
        context={
            "collection": collection,
            "collections": cookbook.COLLECTIONS,
            "recipes": ordered,
            "is_admin": is_admin,
            "username": username,
            "latest": max(
                recipes,
                key=lambda recipe_id: recipes[recipe_id].date_created,
                default=None,
            ),
            "title": title,
        },
    )


@app.get("/about")
@app.ext.template("about.html")
async def about(request: Request):
    """About page"""
    return {}


@app.get("/recipe/<collection:str>/<id>")
async def recipe(request: Request, collection: str, id: str):
    """Recipe viewer page"""
    recipes = await cookbook.get_recipes(collection)
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    # user specific data
    is_admin = auth.is_admin(request)
    username = auth.get_username(request)

    # update recipe sha with user info
    recipe = recipes[id]
    etag = _update_etag_reqinfo(
        recipe.sha,
        is_admin=is_admin,
        username=username,
    )
    if not app.debug:
        if_match = request.headers.get("If-None-Match")
        if if_match is not None and if_match == etag:
            # use cached response
            return sanic.empty(headers={"ETag": etag}, status=304)

    response = await render(
        "recipe.html",
        headers={"ETag": etag},
        context={
            "collection": collection,
            "recipe": recipe,
            "recipe_id": id,
            "is_admin": is_admin,
        },
    )

    response.add_cookie("last-recipe", id)
    response.add_cookie("last-collection", collection)

    return response


# extra endpoint with a "pretty recipe name"
# this is discarded and can be anything really
@app.get("/recipe/<collection:str>/<id>/<name>")
async def _recipe(request: Request, collection: str, id: str, name: str):
    return await recipe(request, collection, id)
