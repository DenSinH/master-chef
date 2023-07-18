from sanic import Sanic
from sanic import Request
from sanic.exceptions import NotFound

from cookbook import get_recipes

app = Sanic(__name__)
app.static("/static", "./static")


@app.get("/")
@app.ext.template("cookbook.html")
async def cookbook(request: Request):
    return {
        "recipes": await get_recipes()
    }


@app.get("/recipe/<id>")
@app.ext.template("recipe.html")
async def recipe(request: Request, id: str):
    recipes = await get_recipes()
    if id not in recipes:
        raise NotFound("No such recipe exists on this website")

    return {
        "recipe": recipes[id]
    }


if __name__ == '__main__':
    import sys
    import os

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 80)), debug="--debug" in sys.argv)
