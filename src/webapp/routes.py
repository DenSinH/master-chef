from collections import OrderedDict
import sanic
import asyncio
import os
import hashlib
from sanic import Request
from sanic_ext import render
from sanic.exceptions import NotFound

import auth
import cookbook
import cookbook.instagram
import data.views as views
import data.users as users
import data.comments as comments

from dotenv import load_dotenv

load_dotenv()

from app import app

""" initialize sectioned routes """
from error_routes import add_error_routes
from user_routes import add_user_routes
from data_routes import add_data_routes
from admin_routes import add_admin_routes
from management_routes import add_management_routes

add_error_routes(app)
add_user_routes(app)
add_data_routes(app)
add_admin_routes(app)
add_management_routes(app)


""" General public cookbook viewing routes """

@app.get("/")
async def index(request: Request):
    """ Index page """
    # show default collection
    return await collection(
        request, 
        collection=cookbook.DEFAULT_COLLECTION
    )


def _update_etag_reqinfo(etag: 'hashlib._Hash', is_admin: bool, is_user: bool, username: str | None) -> str:
    """ Update etag hash with request info """
    etag.update(is_admin.to_bytes())
    etag.update(is_user.to_bytes())
    etag.update((username or "").encode("utf-8", errors="ignore"))
    return etag.hexdigest()


@app.get("/collection/<collection:str>")
async def collection(request: Request, collection: str = cookbook.DEFAULT_COLLECTION):
    """ Get a recipe collection """
    # get request info
    is_admin = auth.is_admin(request)
    is_user = auth.is_user(request)
    username = auth.get_username(request)

    # check caching with collection SHA
    etag = _update_etag_reqinfo(
        hashlib.sha256(
            (await cookbook.get_collection_etag(collection)).encode("ascii"),
            usedforsecurity=False
        ),
        is_admin, is_user, username
    )

    if not app.debug:
        if_match = request.headers.get("If-None-Match")
        if if_match is not None and if_match == etag:
            # use cached response
            return sanic.empty(
                headers={"ETag": etag},
                status=304
            )

    recipes = await cookbook.get_recipes(collection)

    # sort recipes by date_updated (default ordering)
    ordered = OrderedDict(
        sorted(
            recipes.items(),
            key=lambda x: x[1].date_updated,
            reverse=True
        )
    )

    # user-specific rendering
    if username is not None:
        title = f"{username}'s Kitchen"
    else:
        title = cookbook.generate_title()

    if is_admin:
        unverified_users = await users.count_unverified()
    else:
        unverified_users = None

    return await render(
        "cookbook.html",
        headers={
            "ETag": etag
        },
        context={
            "collection": collection,
            "collections": cookbook.COLLECTIONS,
            "recipes": ordered,
            "is_admin": is_admin,
            "is_user": is_user,
            "username": username,
            "latest": max(recipes, key=lambda recipe_id: recipes[recipe_id].date_created, default=None),
            "unverified_users": unverified_users,
            "title": title,
        }
    )


@app.get("/views/<collection:str>")
async def collection_views(request: Request, collection: str = cookbook.DEFAULT_COLLECTION):
    """ Get viewcount for recipe collection """
    return sanic.json(
        await views.get_viewcount(collection)
    )


@app.get("/about")
@app.ext.template("about.html")
async def about(request: Request):
    """ About page """
    return {
        "album": os.environ["IMGUR_ALBUM_ID"]
    }


async def _get_or_increment_recipe_views(request: Request, collection: str, id: str):
    """ Get recipe viewcount, possibly incremented after request """
    # only register a single recipe view per session
    session = request.ctx.session
    if "views" not in session:
        session["views"] = {}
    session_views = session["views"]

    viewcount = None
    if collection in session_views:
        if id in session_views[collection]:
            viewcount = await views.get_viewcount_single(collection, id)
        else:
            session_views[collection].append(id)
    else:
        session_views[collection] = [id]

    # increment views if recipe was not viewed in session
    if viewcount is None:
        viewcount = await views.incr_viewcount(collection, id)

    return viewcount


@app.get("/recipe/<collection:str>/<id>")
async def recipe(request: Request, collection: str, id: str):
    """ Recipe viewer page """
    recipes = await cookbook.get_recipes(collection)
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    # user specific data
    is_admin = auth.is_admin(request)
    is_user = auth.is_user(request)
    username = auth.get_username(request)

    # update recipe sha with user info
    recipe = recipes[id]
    etag = _update_etag_reqinfo(
        recipe.sha,
        is_admin, is_user, username
    )
    if not app.debug:
        if_match = request.headers.get("If-None-Match")
        if if_match is not None and if_match == etag:
            # use cached response
            return sanic.empty(
                headers={"ETag": etag},
                status=304
            )

    if username is not None:
        requser = await users.get_user(username)
    else:
        requser = None

    comments_users = []
    user_comment = None
    found_admin_comment = False
    for comment, user in await comments.get_comments(collection, id):
        if requser is not None and user.id == requser.id:
            # select user comment
            user_comment = comment
        else:
            # place admin comment at the top
            if user.username == os.environ.get("ADMIN_USER", "admin"):
                comments_users.insert(0, (comment, user))
                found_admin_comment = True
            else:
                comments_users.append((comment, user))

    response = await render(
        "recipe.html",
        headers={"ETag": etag},
        context={
            "collection": collection,
            "recipe": recipe,
            "recipe_id": id,
            "is_admin": is_admin,
            "is_user": is_user,
            "user_comment": user_comment,
            "comments_users": comments_users,
            "found_admin_comment": found_admin_comment,
            "viewcount": await _get_or_increment_recipe_views(request, collection, id),
        }
    )

    response.add_cookie("last-recipe", id)
    response.add_cookie("last-collection", collection)

    return response


@app.get("/views/<collection:str>/<id:str>")
async def recipe_views(request: Request, collection: str, id: str):
    """ Get viewcount for a single recipe """
    return sanic.json({
        id: await _get_or_increment_recipe_views(request, collection, id)
    })


# extra endpoint with a "pretty recipe name"
# this is discarded and can be anything really
@app.get("/recipe/<collection:str>/<id>/<name>")
async def _recipe(request: Request, collection: str, id: str, name: str):
    return await recipe(request, collection, id)
