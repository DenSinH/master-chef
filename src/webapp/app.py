from collections import OrderedDict
import traceback
import sanic
from sanic import Sanic
from sanic import Request
from sanic.exceptions import NotFound
from sanic_jwt import initialize, protected
from auth import authenticate, JwtResonses

import cookbook

from dotenv import load_dotenv; load_dotenv()
import os


app = Sanic(__name__)
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
@app.ext.template("cookbook.html")
async def index(request: Request):
    raise Exception("test")
    recipes = await cookbook.get_recipes()
    # todo: multiple ordering methods (date_updated, date_created, name, time)
    ordered = OrderedDict(
        sorted(
            recipes.items(),
            key=lambda x: x[1].get("date_updated", 0),
            reverse=True
        )
    )
    return {
        "recipes": ordered
    }


@app.get("/login")
@app.ext.template("login.html")
async def login_form(request: Request):
    return {}


@app.get("/recipe/<id>")
@app.ext.template("recipe.html")
async def recipe(request: Request, id: str):
    recipes = await cookbook.get_recipes()
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    return {
        "recipe": recipes[id],
        "recipe_id": id
    }


""" PROTECTED ACCESS """


@app.get("/recipe/<id>/update")
@app.ext.template("add/form.html")
@protected(redirect_on_fail=True)
async def update_recipe_form(request: Request, id: str):
    recipes = await cookbook.get_recipes()
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    return {
        "recipe": recipes[id],
        "action": app.url_for('update_recipe', id=id)
    }


@app.post("/recipe/<id>/update")
@protected(redirect_on_fail=True)
async def update_recipe(request: Request, id: str):
    recipe = _parse_recipe_form(request.form)
    await cookbook.update_recipe(id, recipe)

    return sanic.redirect(app.url_for("recipe", id=id))


@app.post("/recipe/<id>/delete")
@protected()
async def delete_recipe(request: Request, id: str):
    recipes = await cookbook.get_recipes()
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    await cookbook.delete_recipe(id)
    return sanic.empty()


@app.get("/add/url")
@app.ext.template("add/url.html")
@protected(redirect_on_fail=True)
async def add_recipe_url_form(request: Request):
    return {}


@app.post("/add/url")
@app.ext.template("add/form.html")
@protected()
async def add_recipe_url(request: Request):
    url = request.form["url"][0]
    recipe = await cookbook.translate_url(url)
    return {
        "recipe": recipe,
        "action": app.url_for('add_recipe_form'),
        "refresh_warning": True
    }


@app.get("/add/text")
@app.ext.template("add/text.html")
@protected(redirect_on_fail=True)
async def add_recipe_text_form(request: Request):
    return {}


@app.post("/add/text")
@app.ext.template("add/form.html")
@protected()
async def add_recipe_text(request: Request):
    recipe = cookbook.translate_page(request.form["text"][0])
    return {
        "recipe": recipe,
        "action": app.url_for('add_recipe_form'),
        "refresh_warning": True
    }


@app.get("/add/form")
@app.ext.template("add/form.html")
@protected(redirect_on_fail=True)
async def add_recipe_form_form(request: Request):
    return {
        "recipe": {},  # empty recipe for template rendering
        "action": app.url_for('add_recipe_form')
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
        "nutrition": nutrition,
        "preparation": form.getlist("preparation", []),
        "tags": form.getlist("tag", []),
        "thumbnail": str(form["thumbnail"][0]) if "thumbnail" in form else None
    }
    return recipe


@app.post("/add/form")
@protected()
async def add_recipe_form(request: Request):
    recipe = _parse_recipe_form(request.form)
    id = await cookbook.add_recipe(recipe)
    return sanic.redirect(app.url_for("recipe", id=id))


if __name__ == '__main__':
    import sys
    import os

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 80)), debug="--debug" in sys.argv)
