from collections import OrderedDict
import datetime
import aiohttp
from aiohttp.client_exceptions import ClientResponseError
import traceback
import sanic
from sanic import Sanic
from sanic import Request
from sanic_ext import render
from sanic.exceptions import NotFound
from sanic_jwt import initialize, protected
from auth import authenticate, JwtResonses
from minifyloader import MinifyingFileSystemLoader
from imgupload import upload_imgur

import cookbook

from dotenv import load_dotenv; load_dotenv()
import os


app = Sanic(__name__)
app.ext.templating.environment.loader = MinifyingFileSystemLoader(
    "templates/"
)


def _strftimestamp(timestamp):
    date = datetime.datetime.fromtimestamp(timestamp)
    return date.strftime("%Y-%m-%d")


app.ext.templating.environment.filters["strftimestamp"] = _strftimestamp
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
initialize(
    app,
    authenticate=authenticate,
    cookie_set=True,
    cookie_access_token_name="jwt_access_token",
    url_prefix="/login",  # post to authenticate function from .auth
    login_redirect_url="/login",
    secret=app.config.SECRET,
    responses_class=JwtResonses,
    expiration_delta=60 * 60
)


""" UNPROTECTED ACCESS """


@app.exception(NotFound)
async def notfound(request: Request, exc):
    return sanic.html(f"""
    <h2>Resource not found:</h2>
    <p>{' '.join(exc.args)}</p>
    """)


@app.exception(Exception)
async def exception(request: Request, exc):
    return sanic.html(f"""
    <p>An exception occurred: </p>
    <pre>{traceback.format_exc()}</pre>
    """)


@app.get("/")
async def index(request: Request):
    return await collection(request, collection=cookbook.DEFAULT_COLLECTION)


@app.get("/collection/<collection:str>")
@app.ext.template("cookbook.html")
async def collection(request: Request, collection: str = cookbook.DEFAULT_COLLECTION):
    recipes = await cookbook.get_recipes(collection)

    ordered = OrderedDict(
        sorted(
            recipes.items(),
            key=lambda x: x[1].get("date_updated", 0),
            reverse=True
        )
    )
    return {
        "collection": collection,
        "collections": cookbook.COLLECTIONS,
        "recipes": ordered,
        "authenticated": await app.ctx.auth.is_authenticated(request)
    }


@app.get("/about")
@app.ext.template("about.html")
async def about(request: Request):
    return {
        "album": os.environ["IMGUR_ALBUM_ID"]
    }


@app.get("/login")
@app.ext.template("login.html")
async def login_form(request: Request):
    return {
        "redirect": dict(request.query_args).get("redirect", "/")
    }


@app.get("/recipe/<collection:str>/<id>")
async def recipe(request: Request, collection: str, id: str):
    recipes = await cookbook.get_recipes(collection)
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    response = await render(
        "recipe.html",
        context={
            "collection": collection,
            "recipe": recipes[id],
            "recipe_id": id,
            "authenticated": await app.ctx.auth.is_authenticated(request)
        }
    )

    response.add_cookie("last-recipe", id)
    response.add_cookie("last-collection", collection)

    return response


@app.get("/recipe/<collection:str>/<id>/<name>")
async def _recipe(request: Request, collection: str, id: str, name: str):
    return await recipe(request, collection, id)


""" PROTECTED ACCESS """


@app.get("/get-usage")
@protected()
async def get_usage(request: Request):
    date = request.args.get("date")
    try:
        usage = await cookbook.get_usage(date)
    except ClientResponseError as e:
        if e.status == 429:
            return sanic.empty(500)
        raise
    return sanic.json(usage)


@app.get("/usage")
@app.ext.template("usage.html")
@protected(redirect_on_fail=True, redirect_url=app.url_for("login_form", redirect="/usage"))
async def usage(request: Request):
    today = datetime.date.today()
    dates = set()
    for collection in cookbook.COLLECTIONS:
        recipes = await cookbook.get_recipes(collection)
        for _, recipe in recipes.items():
            if "date_created" in recipe:
                dates.add(datetime.datetime.fromtimestamp(recipe["date_created"]).date())

    return {
        "dates": [
            date.strftime("%Y-%m-%d") for date in sorted(dates, reverse=True)
        ],
        "today": today.strftime("%Y-%m-%d"),
        "ctx_cost_1k": 0.0015,
        "out_cost_1k": 0.002,
    }


@app.get("/recipe//<collection:str>/<id>/update")
@app.ext.template("add/form.html")
# recipe id is obtained from last visited recipe page in cookies
@protected(redirect_on_fail=True, redirect_url=app.url_for("login_form", redirect="recipe"))
async def update_recipe_form(request: Request, collection: str, id: str):
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
async def update_recipe(request: Request, collection: str, id: str):
    recipe = _parse_recipe_form(request.form)
    await cookbook.update_recipe(collection, id, recipe)

    return sanic.redirect(app.url_for("recipe", id=id, collection=collection))


# todo: fix login redirect to recipe page
@app.post("/recipe/<collection:str>/<id>/delete")
@protected()
async def delete_recipe(request: Request, collection: str, id: str):
    recipes = await cookbook.get_recipes(collection)
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    await cookbook.delete_recipe(collection, id)
    return sanic.empty()


@app.get("/collection/<collection:str>/add/url")
@app.ext.template("add/url.html")
@protected(redirect_on_fail=True, redirect_url=app.url_for("login_form", redirect="/add/url"))
async def add_recipe_url_form(request: Request, collection: str):
    return {
        "collection": collection,
        "error": dict(request.query_args).get("error")
    }


@app.post("/collection/<collection:str>/add/url")
@protected()
async def add_recipe_url(request: Request, collection: str):
    url = request.form["url"][0]
    try:
        recipe = await cookbook.translate_url(url)
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
async def add_recipe_text_form(request: Request, collection: str):
    return {
        "collection": collection,
        "error": dict(request.query_args).get("error")
    }


@app.post("/collection/<collection:str>/add/text")
@app.ext.template("add/form.html")
@protected()
async def add_recipe_text(request: Request, collection: str):
    recipe = await cookbook.translate_page(request.form["text"][0])
    return {
        "collection": collection,
        "recipe": recipe,
        "action": app.url_for('add_recipe_form', collection=collection),
        "refresh_warning": True
    }


@app.post("/add/upload-image")
@protected()
async def upload_image(request: Request):
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
async def add_recipe_form_form(request: Request, collection: str):
    return {
        "collection": collection,
        "recipe": {},  # empty recipe for template rendering
        "action": app.url_for('add_recipe_form', collection=collection),
        "error": dict(request.query_args).get("error"),
    }


def _parse_recipe_form(form: sanic.request.RequestParameters):
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

    recipe = {
        "name": form["name"][0],
        "url": form["url"][0] if "url" in form else None,
        "people": int(form["people"][0]) if "people" in form else None,
        "time": int(form["time"][0]) if "time" in form else None,
        "ingredients": ingredients,
        "remarks": form["remarks"][0] if "remarks" in form else None,
        "nutrition": nutrition,
        "preparation": form.getlist("preparation", []),
        "meta": {
            "language": form["language"][0] if "language" in form else None,
            "meal_type": form["meal_type"][0] if "meal_type" in form else None,
            "cuisine": form["cuisine"][0] if "cuisine" in form else None,
            "meat_type": [meat for meat in form["meat_type"] if meat] if "meat_type" in form else None,
            "carb_type": [carb for carb in form["carb_type"] if carb] if "carb_type" in form else None,
            "temperature": form["temperature"][0] if "cuisine" in form else None,
        },
        "thumbnail": str(form["thumbnail"][0]) if "thumbnail" in form else None
    }

    return recipe


@app.post("/collection/<collection:str>/add/form")
@protected()
async def add_recipe_form(request: Request, collection: str):
    recipe = _parse_recipe_form(request.form)
    id = await cookbook.add_recipe(collection, recipe)
    return sanic.redirect(app.url_for("recipe", id=id, collection=collection))


@app.post("/move/<collectionfrom:str>/<collectionto:str>/<id>")
@protected()
async def move_recipe(request: Request, collectionfrom: str, collectionto: str, id: str):
    recipe = await cookbook.delete_recipe(collectionfrom, id)
    id = await cookbook.add_recipe(collectionto, recipe)
    return sanic.json({"redirect": app.url_for("recipe", id=id, collection=collectionto)})


if __name__ == '__main__':
    import sys
    import os

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 80)), debug="--debug" in sys.argv)
