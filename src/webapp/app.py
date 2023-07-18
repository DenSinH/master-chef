import sanic
from sanic import Sanic
from sanic import Request
from sanic.exceptions import NotFound

import cookbook

app = Sanic(__name__)
app.static("/static", "./static")


@app.get("/")
@app.ext.template("cookbook.html")
async def cookbook(request: Request):
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
        "recipe": recipes[id]
    }


@app.get("/add/url")
@app.ext.template("add/url.html")
async def add_recipe_url_form(request: Request):
    return {}


@app.post("/add/url")
async def add_recipe_url(request: Request):
    recipe = await cookbook.translate_url(request.form["url"][0])
    import pprint
    pprint.pprint(recipe)
    # cookbook.add_recipe(recipe)
    # return to form.html filled with data
    # this might need to be a dynamic route or something...
    return sanic.redirect("/")


@app.get("/add/text")
@app.ext.template("add/text.html")
async def add_recipe_text_form(request: Request):
    return {}


@app.post("/add/text")
async def add_recipe_text(request: Request):
    from pprint import pprint
    pprint(request.form)
    print("Hello!")
    return sanic.redirect("/")


if __name__ == '__main__':
    import sys
    import os

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 80)), debug="--debug" in sys.argv)
