import sanic
from sanic import Sanic
from sanic import Request
from sanic.exceptions import NotFound

import cookbook

app = Sanic(__name__)
app.static("/static", "./static")


@app.get("/")
@app.ext.template("cookbook.html")
async def index(request: Request):
    return {
        "recipes": await cookbook.get_recipes()
    }


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


@app.get("/recipe/<id>/update")
@app.ext.template("add/form.html")
async def update_recipe_form(request: Request, id: str):
    recipes = await cookbook.get_recipes()
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    return {
        "recipe": recipes[id],
        "action": app.url_for('update_recipe', id=id)
    }


@app.post("/recipe/<id>/update")
async def update_recipe(request: Request, id: str):
    recipe = _parse_recipe_form(request.form)
    await cookbook.update_recipe(id, recipe)

    return sanic.redirect(app.url_for("recipe", id=id))


@app.post("/recipe/<id>/delete")
async def delete_recipe(request: Request, id: str):
    recipes = await cookbook.get_recipes()
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    await cookbook.delete_recipe(id)
    return sanic.redirect("/")


@app.get("/add/url")
@app.ext.template("add/url.html")
async def add_recipe_url_form(request: Request):
    return {}


@app.post("/add/url")
@app.ext.template("add/form.html")
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
async def add_recipe_text_form(request: Request):
    return {}


@app.post("/add/text")
@app.ext.template("add/form.html")
async def add_recipe_text(request: Request):
    recipe = cookbook.translate_page(request.form["text"][0])
    return {
        "recipe": recipe,
        "action": app.url_for('add_recipe_form'),
        "refresh_warning": True
    }


@app.get("/add/form")
@app.ext.template("add/form.html")
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
async def add_recipe_form(request: Request):
    recipe = _parse_recipe_form(request.form)
    id = await cookbook.add_recipe(recipe)
    return sanic.redirect(app.url_for("recipe", id=id))


if __name__ == '__main__':
    import sys
    import os

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 80)), debug="--debug" in sys.argv)
