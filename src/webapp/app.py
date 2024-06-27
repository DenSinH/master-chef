from collections import OrderedDict
import datetime
import aiohttp
from aiohttp.client_exceptions import ClientResponseError
import traceback
import re
import string
import sanic
import asyncio
import msgspec
import dataclasses
from sanic import Sanic, response
from sanic import Request
from sanic_ext import render
from sanic.exceptions import NotFound
from sanic_jwt import initialize, protected, scoped
from sanic_session import Session
from auth import authenticate, extend_scopes, JwtResonses, validate_scopes, CookbookAuthFailed
from minifyloader import MinifyingFileSystemLoader
from imgupload import upload_imgur

import cookbook
import cookbook.instagram
from data import init_db
import data.views as views
import data.users as users
import data.comments as comments
import data.saves as saves
from limiter import init_limiter, close_limiter, RateLimiter, TooManyRequests

from dotenv import load_dotenv; load_dotenv()
import os

response.BaseHTTPResponse._dumps = msgspec.json.encode

app = Sanic(__name__)
app.ext.templating.environment.loader = MinifyingFileSystemLoader(
    "templates/"
)


def _strftimestamp(timestamp):
    """ Format timestamp to text """
    date = datetime.datetime.fromtimestamp(timestamp)
    return date.strftime("%Y-%m-%d")


def _add_ingredient_references(step: str, recipe: cookbook.Recipe):
    """ Add ingredient references to recipe step """
    return cookbook.replace_ingredient_references(
        step, 
        tuple(ingredient.ingredient for ingredient in recipe.ingredients)
    )


# 10MB max request size
app.config.REQUEST_MAX_SIZE = 10000000

app.ext.templating.environment.filters["strftimestamp"] = _strftimestamp
app.ext.templating.environment.filters["ingredientrefs"] = _add_ingredient_references
app.ext.templating.environment.filters["capwords"] = string.capwords
app.ext.templating.environment.globals["CUISINE_TYPES"] = cookbook.CUISINE_TYPES
app.ext.templating.environment.globals["MEAL_TYPES"] = cookbook.MEAL_TYPES
app.ext.templating.environment.globals["MEAT_TYPES"] = cookbook.MEAT_TYPES
app.ext.templating.environment.globals["CARB_TYPES"] = cookbook.CARB_TYPES
app.ext.templating.environment.globals["TEMPERATURE_TYPES"] = cookbook.TEMPERATURE_TYPES
app.ext.templating.environment.globals["LANGUAGES"] = {
    "nl": "Nederlands",
    "en": "English"
}

app.config.SECRET = os.environ.get("SECRET", os.environ["PASSWORD"])
app.static("/static", "./static")

JWT_TOKEN_NAME = "jwt_access_token"
initialize(
    app,
    authenticate=authenticate,
    cookie_set=True,
    cookie_access_token_name=JWT_TOKEN_NAME,
    url_prefix="/login",  # post to authenticate function from .auth
    login_redirect_url="/login",
    secret=app.config.SECRET,
    responses_class=JwtResonses,
    expiration_delta=60 * 60,
    algorithm="HS256",
    add_scopes_to_payload=extend_scopes,
    scope_enabled=True,
)
_session = Session(app)
app.before_server_start(init_db)

# global rate limit of 5 requests per second
app.ctx.global_limiter = RateLimiter(times=5, seconds=1)
app.before_server_start(init_limiter)
app.after_server_stop(close_limiter)


async def _get_username(request: Request):
    """ Get username from request """
    try:
        return await app.ctx.auth.extract_user_id(request)
    except AttributeError:
        return None


""" UNPROTECTED ACCESS """


@app.exception(NotFound)
@app.ext.template("sorry.html")
async def notfound(request: Request, exc):
    """ 404 page """
    return {
        "title": "Resource not found",
        "message": f"<p>{' '.join(exc.args)}</p>"
    }


@app.exception(CookbookAuthFailed)
async def auth_failed(request: Request, exc):
    """ Authentication failed default response """
    return sanic.json({
        "error": str(exc)
    }, 401)


@app.exception(TooManyRequests)
async def too_many_requests(request: Request, exc: TooManyRequests):
    """ Too many requests default response """
    return sanic.json({
        "error": "Too many requests"
    }, exc.status_code)


@app.exception(Exception)
async def exception(request: Request, exc):
    """ Stacktrace page """
    return await render(
        "sorry.html",
        500,
        context={
            "title": "Whoops!",
            "message": "<p>An error occurred:</p>"
                       f"<pre>{traceback.format_exc()}</pre>"
        }
    )


@app.get("/")
async def index(request: Request):
    """ Index page """
    # show default collection
    return await collection(
        request, 
        collection=cookbook.DEFAULT_COLLECTION
    )


@app.get("/collection/<collection:str>")
@app.ext.template("cookbook.html")
async def collection(request: Request, collection: str = cookbook.DEFAULT_COLLECTION):
    """ Get a recipe collection """
    recipes = await cookbook.get_recipes(collection)

    # sort recipes by date_updated (default ordering)
    ordered = OrderedDict(
        sorted(
            recipes.items(),
            key=lambda x: x[1].date_updated,
            reverse=True
        )
    )

    # get recipe views and request info
    viewcount, is_admin, is_user, username = await asyncio.gather(
        views.get_viewcount(collection),
        validate_scopes(request, "admin"),
        validate_scopes(request, "user"),
        _get_username(request)
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

    return {
        "collection": collection,
        "collections": cookbook.COLLECTIONS,
        "recipes": ordered,
        "is_admin": is_admin,
        "is_user": is_user,
        "username": username,
        "latest": max(recipes, key=lambda recipe_id: recipes[recipe_id].date_created, default=None),
        "viewcount": viewcount,
        "unverified_users": unverified_users,
        "title": title,
    }


@app.get("/about")
@app.ext.template("about.html")
async def about(request: Request):
    """ About page """
    return {
        "album": os.environ["IMGUR_ALBUM_ID"]
    }


@app.get("/login")
@app.ext.template("users/login.html")
async def login_form(request: Request):
    """ User login form """
    return {
        "redirect": dict(request.query_args).get("redirect", "/")
    }


@app.get("/register")
@app.ext.template("users/register.html")
async def register_form(request: Request):
    """ User registration form """
    return {}


@app.post("/register")
async def register(request: Request):
    """ User registration endpoint """
    
    username = request.form.get("username").strip()

    # username validation
    if not username:
        return sanic.json({
            "error": "Username must be specified"
        }, 400)
    if len(username) < 3:
        return sanic.json({
            "error": "Username must be at least 3 characters long"
        }, 400)
    if len(username) > 50:
        return sanic.json({
            "error": "Username must be at most 50 characters long"
        }, 400)
    
    password = request.form.get("password")

    # password validation
    if not password or len(password) < 6:
        return sanic.json({
            "error": "Password must be at least of length 6"
        }, 400)
    if (await users.get_user(username)) is not None:
        return sanic.json({
            "error": "Username already exists"
        }, 400)

    # rate limit after checks, otherwise
    # failed attempts will trigger rate limiting
    await RateLimiter(times=1, hours=1)(request)
    try:
        await users.register_user(username, password)
    except users.UserExistsException as e:
        return sanic.json({
            "error": "Username already exists"
        }, 400)

    return sanic.json({"redirect": app.url_for("registered")})


@app.get("/forgot-password")
async def forgot_password(request: Request):
    """ Forgot password page """
    username = dict(request.query_args).get("username")
    user = await users.get_user(username)
    if user is None:
        return sanic.redirect("login")

    # password can only be reset if the admin cleared it
    if user.password is not None:
        return await render(
            "sorry.html",
            context={
                "title": "Please wait...",
                "message": "<p>Please ask for Dennis to clear your password so you can reset it.</p>",
                "centering": True
            }
        )
    return await render(
        "users/forgot.html",
        context={
            "username": username
        }
    )


@app.post("/forgot-password", ctx_limiter=RateLimiter(times=1, minutes=5))
async def update_password(request: Request):
    """ Update password post route """
    username = dict(request.query_args).get("username")
    user = await users.get_user(username)
    if user is None:
        return sanic.json({"error": "This user does not exist, are you sure you entered the right name before hitting 'Forgot password'"}, 400)
    
    # can only update password if it has been cleared
    if user.password is not None:
        return sanic.redirect(app.url_for("forgot_password", username=username))

    newpassword = request.form.get("password")
    if not newpassword or len(newpassword) < 6:
        return sanic.json({"error": "Password must be at least length 6"}, 400)
    await users.update_user_password(username, newpassword)
    return sanic.json({"redirect": app.url_for("login_form")})


@app.get("/registered")
@app.ext.template("users/registered.html")
async def registered(request: Request):
    """ Registration form landing page """
    username = (await _get_username(request)) or "there"
    return {
        "username": username
    }


@app.get("/logout")
async def logout(request: Request):
    """ User logout page """
    response = sanic.redirect(request.app.url_for("index"))
    response.cookies.delete_cookie(JWT_TOKEN_NAME)
    return response


@app.get("/recipe/<collection:str>/<id>")
async def recipe(request: Request, collection: str, id: str):
    """ Recipe viewer page """

    recipes = await cookbook.get_recipes(collection)
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

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

    # user specific data
    is_admin, is_user, username = await asyncio.gather(
        validate_scopes(request, "admin"),
        validate_scopes(request, "user"),
        _get_username(request)
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
        context={
            "collection": collection,
            "recipe": recipes[id],
            "recipe_id": id,
            "is_admin": is_admin,
            "is_user": is_user,
            "user_comment": user_comment,
            "comments_users": comments_users,
            "found_admin_comment": found_admin_comment,
            "viewcount": viewcount
        }
    )

    response.add_cookie("last-recipe", id)
    response.add_cookie("last-collection", collection)

    return response


# extra endpoint with a "pretty recipe name"
# this is discarded and can be anything really
@app.get("/recipe/<collection:str>/<id>/<name>")
async def _recipe(request: Request, collection: str, id: str, name: str):
    return await recipe(request, collection, id)


""" PROTECTED ACCESS """


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


@app.get("/get-usage")
@protected()
@scoped("admin")
async def get_usage(request: Request):
    """ Get OpenAI usage data """
    date = request.args.get("date")
    try:
        usage = await cookbook.get_usage(date)
    except ClientResponseError as e:
        # too many requests for OpenAI usage endpoint
        # this limit is actually fairly low,
        # so it may be triggered pretty often
        # we don't want to get a stacktrace page in this case
        if e.status == 429:
            return sanic.empty(500)
        raise
    return sanic.json(usage)


@app.get("/usage")
@app.ext.template("usage.html")
@protected(redirect_on_fail=True, redirect_url=app.url_for("login_form", redirect="/usage"))
@scoped("admin")
async def usage(request: Request):
    """ OpenAI usage page """
    today = datetime.date.today()

    # get relevant dates (creation dates of recipes)
    dates = {
        datetime.datetime.fromtimestamp(recipe.date_created).date()
        for collection in cookbook.COLLECTIONS
        for _, recipe in (await cookbook.get_recipes(collection)).items()
        if recipe.date_created
    }

    return {
        "dates": [
            date.strftime("%Y-%m-%d") for date in sorted(dates, reverse=True)
        ],
        "today": today.strftime("%Y-%m-%d"),
        "ctx_cost_1k": 0.0015,
        "out_cost_1k": 0.002,
    }


@app.get("/recipe/<collection:str>/<id>/update")
@app.ext.template("add/form.html")
# recipe id is obtained from last visited recipe page in cookies
@protected(redirect_on_fail=True, redirect_url=app.url_for("login_form", redirect="recipe"))
@scoped("admin")
async def update_recipe_form(request: Request, collection: str, id: str):
    """ Update recipe form page """
    recipes = await cookbook.get_recipes(collection)
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    return {
        "collection": collection,
        "recipe": recipes[id],
        "action": app.url_for('update_recipe', id=id, collection=collection)
    }


@app.post("/recipe/<collection:str>/<id>/update")
@protected()
@scoped("admin")
async def update_recipe(request: Request, collection: str, id: str):
    """ Update recipe """
    recipe = _parse_recipe_form(request.form)
    await cookbook.update_recipe(collection, id, recipe)
    return sanic.redirect(app.url_for("recipe", id=id, collection=collection))


# todo: fix login redirect to recipe page
@app.post("/recipe/<collection:str>/<id>/delete")
@protected()
@scoped("admin")
async def delete_recipe(request: Request, collection: str, id: str):
    """ Delete recipe """
    recipes = await cookbook.get_recipes(collection)
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    # delete all info
    await asyncio.gather(
        cookbook.delete_recipe(collection, id),
        Views.delete_recipe(collection, id),
        Comment.delete_recipe(collection, id),
        Save.delete_recipe(collection, id),
    )
    return sanic.empty()


@app.get("/collection/<collection:str>/add/url")
@app.ext.template("add/url.html")
@protected(redirect_on_fail=True, redirect_url=app.url_for("login_form", redirect="/add/url"))
@scoped("admin")
async def add_recipe_url_form(request: Request, collection: str):
    """ Add recipe with URL form page """
    return {
        "collection": collection,
        "error": dict(request.query_args).get("error")
    }


@app.post("/collection/<collection:str>/add/url")
@protected()
@scoped("admin")
async def add_recipe_url(request: Request, collection: str):
    """ Add recipe with URL """
    url = request.form["url"][0]
    try:
        # pass user agent through to transform
        recipe = await cookbook.translate_url(url, user_agent=request.headers.get("user-agent"))
    except aiohttp.client_exceptions.ClientConnectorError:
        return sanic.response.redirect(app.url_for("add_recipe_url_form", error="notfound"))

    return await render(
        "add/form.html",
        context={
            "collection": collection,
            "recipe": recipe,
            "action": app.url_for('add_recipe_form', collection=collection),
            "refresh_warning": True
        }
    )


@app.get("/collection/<collection:str>/add/text")
@app.ext.template("add/text.html")
@protected(redirect_on_fail=True, redirect_url=app.url_for("login_form", redirect="/add/text"))
@scoped("admin")
async def add_recipe_text_form(request: Request, collection: str):
    """ Add recipe from text form page """
    return {
        "collection": collection,
        "error": dict(request.query_args).get("error")
    }


@app.post("/collection/<collection:str>/add/text")
@app.ext.template("add/form.html")
@protected()
@scoped("admin")
async def add_recipe_text(request: Request, collection: str):
    """ Add recipe from text """
    recipe = await cookbook.translate_page(request.form["text"][0])
    return {
        "collection": collection,
        "recipe": recipe,
        "action": app.url_for('add_recipe_form', collection=collection),
        "refresh_warning": True
    }


@app.post("/add/upload-image")
@protected()
@scoped("admin")
async def upload_image(request: Request):
    """ Upload an image, and return the url of the
        uploaded image """
    link = None
    for name, file in request.files.items():
        if not file:
            continue
        file = file[0]
        try:
            link = await upload_imgur(file.body, title=file.name)
        except Exception as e:
            raise e
        break

    return sanic.json({"link": link})


@app.get("/collection/<collection:str>/add/form")
@app.ext.template("add/form.html")
@protected(redirect_on_fail=True, redirect_url=app.url_for("login_form", redirect="/add/form"))
@scoped("admin")
async def add_recipe_form_form(request: Request, collection: str):
    """ Add recipe from form, form page """
    return {
        "collection": collection,
        "recipe": cookbook.Recipe(),  # empty recipe for template rendering
        "action": app.url_for('add_recipe_form', collection=collection),
        "error": dict(request.query_args).get("error"),
    }


def _parse_recipe_form(form: sanic.request.RequestParameters) -> cookbook.Recipe:
    """ Parse an HTML form into a Request """

    # fix ingredients (zip fields)
    ingredients = []
    for amount, ingredient in zip(form.getlist("ingredient-amount", []), form.getlist("ingredient-type", [])):
        if ingredient == "null":
            continue
        if amount == "-1":
            amount = None

        ingredients.append({
            "amount": amount,
            "ingredient": ingredient
        })

    # fix nutrition (zip fields)
    nutrition = []
    for amount, group in zip(form.getlist("nutrition-amount", []), form.getlist("nutrition-group", [])):
        if group == "null":
            continue
        if amount == "-1":
            amount = None

        nutrition.append({
            "amount": amount,
            "group": group
        })
    if not nutrition:
        nutrition = None

    # Recipe factory
    recipe = cookbook.Recipe.from_data(
        name=form.get("name"),
        meta={
            "language": form.get("language"),
            "meal_type": form.get("meal_type"),
            "meat_type": form.get("meat_type"),
            "carb_type": form.get("carb_type"),
            "cuisine": form.get("cuisine"),
            "temperature": form.get("temperature")
        },
        time=form.get("time"),
        people=form.get("people"),
        url=form.get("url"),
        ingredients=ingredients,
        preparation=form.getlist("preparation"),
        nutrition=nutrition,
        remarks=form.get("remarks"),
        thumbnail=form.get("thumbnail"),
    )
    return recipe


@app.post("/collection/<collection:str>/add/form")
@protected()
@scoped("admin")
async def add_recipe_form(request: Request, collection: str):
    """ Add recipe from form """
    recipe = _parse_recipe_form(request.form)
    id = await cookbook.add_recipe(collection, recipe)
    return sanic.redirect(app.url_for("recipe", id=id, collection=collection))


@app.post("/post/<collection:str>/<id>")
@protected()
@scoped("admin")
async def post_recipe(request: Request, collection: str, id: str):
    """ Post a recipe to instagram
        Triggers a refresh on the page """
    recipes = await cookbook.get_recipes(collection)
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    recipe = recipes[id]
    if recipe.igcode:
        raise cookbook.instagram.InstagramError(f"Recipe was already posted to instagram with code {recipe.igcode}")

    if not recipe.name or not recipe.thumbnail:
        raise cookbook.instagram.InstagramError("Cannot upload recipe without name or thumbnail")
    
    # upload recipe and get instagram code
    code = await cookbook.instagram.post_instagram_recipe(
        recipe_name=recipe.name,
        image_url=recipe.thumbnail,
        user_agent=request.headers.get("user-agent")
    )

    # ugly way of updating a frozen dataclass
    # I want to keep recipes frozen though, as to
    # not accidentally update them anywhere
    object.__setattr__(recipe, "igcode", code)
    await cookbook.update_recipe(collection, id, recipe)
    return sanic.json({
        "redirect": app.url_for("recipe", id=id, collection=collection)
    })


@app.post("/move/<collectionfrom:str>/<collectionto:str>/<id>")
@protected()
@scoped("admin")
async def move_recipe(request: Request, collectionfrom: str, collectionto: str, id: str):
    """ Move recipe to other collection """
    recipe = await cookbook.delete_recipe(collectionfrom, id)
    idto = await cookbook.add_recipe(collectionto, recipe)

    # move user data
    await asyncio.gather(
        Views.move_recipe(collectionfrom, collectionto, id, idto),
        Comment.move_recipe(collectionfrom, collectionto, id, idto),
        Save.move_recipe(collectionfrom, collectionto, id, idto)
    )
    return sanic.json({"redirect": app.url_for("recipe", id=idto, collection=collectionto)})


""" DATA MANAGEMENT """
from data.models import *
import data
from sqlalchemy import select

# endpoint name -> sqlalchemy model mapping
TABLES = {
    "users": User,
    "comments": Comment,
    "saves": Save
}


def convert_field(field):
    """ Convert a sqlalchmy field to something that can be
        rendered properly in HTML """
    if isinstance(field, (datetime.datetime, datetime.date)):
        return str(field)
    return field


def to_dict(row):
    """ Convert sqlalchemy object columns """
    return {
        col.name: convert_field(getattr(row, col.name))
        for col in row.__table__.columns
    }


def col_type(col):
    """ Get column type as string """
    if isinstance(col.type, Boolean):
        return "boolean"
    if isinstance(col.type, Integer):
        if col.nullable:
            return "intnull"
        return "integer"
    if isinstance(col.type, DateTime):
        if col.nullable:
            return "datetimenull"
        return "datetime"
    if col.nullable:
        return "stringnull"
    return "string"


@app.route("/manage/<table_name>")
@app.ext.template("/manage/table.html")
@protected()
@scoped("admin")
async def manage(request, table_name):
    """ Data management table view """
    return {
        "columns": list([col.name for col in TABLES[table_name].__table__.columns]),
        "column_types": {
            col.name: col_type(col)
            for col in TABLES[table_name].__table__.columns
        },
        "table_name": table_name
    }


@app.get("/api/<table_name>")
@protected()
@scoped("admin")
async def api_get_all(request, table_name):
    """ Data management table contents """
    async with data.Session() as session:
        table_class = TABLES[table_name]
        result = await session.execute(select(table_class))
        return sanic.json({
            "data": [to_dict(row) for row in result.scalars().all()]
        })


@app.get("/api/<table_name>/<id>")
@protected()
@scoped("admin")
async def api_get_one(request, table_name, id: int):
    """ Data management get single row by id """
    async with data.Session() as session:
        table_class = TABLES[table_name]
        result = await session.execute(select(table_class).where(table_class.id == id))
        obj = result.scalar()
        if obj:
            return sanic.json({"data": to_dict(obj)})
        else:
            return sanic.json({"error": "Not found"}, status=404)


@app.post("/api/<table_name>")
@protected()
@scoped("admin")
async def api_create(request: Request, table_name):
    """ Data management create row """
    async with data.Session() as session:
        table_class = TABLES[table_name]
        obj_data = request.json

        # convert datetime columns
        for col, val in obj_data.items():
            if isinstance(table_class.__table__.columns[col], (DateTime,)):
                if isinstance(val, (int, float)):
                    obj_data[col] = datetime.datetime.utcfromtimestamp(val / 1000)
        
        # create instance
        obj = table_class(**obj_data)
        session.add(obj)
        res_data = to_dict(obj)
        await session.commit()
        return sanic.json({"data": res_data})


@app.put("/api/<table_name>/<id>")
@protected()
@scoped("admin")
async def api_update(request, table_name, id: int):
    """ Data management update single row """
    async with data.Session() as session:
        table_class = TABLES[table_name]
        result = await session.execute(select(table_class).where(table_class.id == id))
        obj = result.scalar()

        if obj:
            # convert datetime columns
            for key, value in request.json.items():
                if isinstance(table_class.__table__.columns[key].type, (DateTime,)):
                    if isinstance(value, (int, float)):
                        value = datetime.datetime.utcfromtimestamp(value / 1000)
                
                # update object
                setattr(obj, key, value)
            res_data = to_dict(obj)
            await session.commit()
            return sanic.json({"data": res_data})
        else:
            return sanic.json({"error": "Not found"}, status=404)


@app.delete("/api/<table_name>/<id>")
@protected()
@scoped("admin")
async def api_delete(request, table_name, id: int):
    """ Data management delete single row """
    async with data.Session() as session:
        table_class = TABLES[table_name]
        result = await session.execute(select(table_class).where(table_class.id == id))
        obj = result.scalar()
        if obj:
            await session.delete(obj)
            await session.commit()
            return sanic.json({"message": "Deleted successfully"})
        else:
            return sanic.json({"error": "Not found"}, status=404)


if __name__ == '__main__':
    import sys
    import os

    debug = "--debug" in sys.argv
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 80)), debug=debug, auto_reload=debug)
