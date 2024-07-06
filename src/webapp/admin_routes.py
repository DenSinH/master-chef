import sanic
from sanic import Sanic, Request
from sanic.exceptions import NotFound
from sanic_ext import render
from sanic_jwt import protected, scoped
import datetime
import asyncio
import aiohttp
from aiohttp.client_exceptions import ClientResponseError
from data.models import *
from utils import imgupload
import cookbook


def add_admin_routes(app: Sanic):
    """ Add admin routes (cookbook editing) """

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
            link = await imgupload.upload_image(file.body, title=file.name)
            print(link)
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
        return sanic.json({
            "redirect": app.url_for("recipe", id=idto, collection=collectionto)
        })
