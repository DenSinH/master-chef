import datetime
from collections import defaultdict
from typing import Any

import aiohttp
from aiohttp.client_exceptions import ClientResponseError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.datastructures import FormData

from webapp import auth, cookbook
from webapp.app import templates
from webapp.utils import s3

router = APIRouter()


def _form_to_dict(form: FormData) -> dict[str, Any]:
    values: dict[str, list[Any]] = defaultdict(list)

    for key, value in form.multi_items():
        values[key].append(value)

    return {
        key: values[0] if len(values) == 1 else values for key, values in values.items()
    }


def _parse_recipe_form(form: FormData) -> cookbook.Recipe:
    """Parse an HTML form into a Request"""

    # fix ingredients (zip fields)
    ingredients = []
    for amount, ingredient in zip(
        form.getlist("ingredient-amount"),
        form.getlist("ingredient-type"),
    ):
        if ingredient == "null":
            continue
        if amount == "-1":
            amount = None

        ingredients.append({"amount": amount, "ingredient": ingredient})

    # fix nutrition (zip fields)
    nutrition: list[str] = []
    for amount, group in zip(
        form.getlist("nutrition-amount"),
        form.getlist("nutrition-group"),
    ):
        if group == "null":
            continue
        if amount == "-1":
            amount = None

        nutrition.append({"amount": amount, "group": group})
    if not nutrition:
        nutrition = []

    preparation = form.getlist("preparation")

    # Recipe factory
    data = dict(
        _form_to_dict(form),
        ingredients=ingredients,
        nutrition=nutrition,
        preparation=preparation,
    )
    data["meta"] = {
        field: value
        for field, value in data.items()
        if field in cookbook.RecipeMeta.model_fields
    }
    recipe = cookbook.Recipe(**data)
    return recipe


@router.get("/get-usage")
async def get_usage(
    request: Request,
    user: dict = Depends(auth.require_admin),
):
    """Get OpenAI usage data."""
    date = request.query_params.get("date")

    try:
        usage = await cookbook.get_usage(date)
    except ClientResponseError as e:
        # too many requests for OpenAI usage endpoint
        # this limit is actually fairly low,
        # so it may be triggered pretty often
        # we don't want to get a stacktrace page in this case
        if e.status == 429:
            return JSONResponse(status_code=500, content={})

        raise

    return JSONResponse(usage)


@router.get("/usage")
async def usage(
    request: Request,
    user: dict = Depends(auth.require_admin),
):
    """OpenAI usage page."""
    today = datetime.datetime.now().astimezone().date()

    dates = {
        datetime.datetime.fromtimestamp(recipe.date_created).astimezone().date()
        for collection in cookbook.COLLECTIONS
        for _, recipe in (await cookbook.get_recipes(collection)).items()
        if recipe.date_created
    }

    return templates.TemplateResponse(
        request=request,
        name="usage.html",
        context={
            "dates": [
                date.strftime("%Y-%m-%d") for date in sorted(dates, reverse=True)
            ],
            "today": today.strftime("%Y-%m-%d"),
            "ctx_cost_1k": 0.0015,
            "out_cost_1k": 0.002,
        },
    )


@router.get("/recipe/{collection}/{id}/update")
async def update_recipe_form(
    request: Request,
    collection: str,
    id: str,
    user: dict = Depends(auth.require_admin),
):
    """Update recipe form page."""
    recipes = await cookbook.get_recipes(collection)

    if id not in recipes:
        raise HTTPException(
            status_code=404,
            detail="No such recipe exists on this website",
        )

    return templates.TemplateResponse(
        request=request,
        name="add/form.html",
        context={
            "collection": collection,
            "recipe": recipes[id],
            "action": request.app.url_path_for(
                "update_recipe",
                id=id,
                collection=collection,
            ),
        },
    )


@router.post("/recipe/{collection}/{id}/update")
async def update_recipe(
    request: Request,
    collection: str,
    id: str,
    user: dict = Depends(auth.require_admin),
):
    """Update recipe."""
    form = await request.form()
    recipe = _parse_recipe_form(form)

    await cookbook.update_recipe(collection, id, recipe)

    return RedirectResponse(
        request.app.url_path_for("recipe", id=id, collection=collection),
        status_code=303,
    )


@router.post("/recipe/{collection}/{id}/delete")
async def delete_recipe(
    request: Request,
    collection: str,
    id: str,
    user: dict = Depends(auth.require_admin),
):
    """Delete recipe."""
    recipes = await cookbook.get_recipes(collection)

    if id not in recipes:
        raise HTTPException(
            status_code=404,
            detail="No such recipe exists on this website",
        )

    await cookbook.delete_recipe(collection, id)

    return Response(status_code=204)


@router.get("/collection/{collection}/add/url")
async def add_recipe_url_form(
    request: Request,
    collection: str,
    user: dict = Depends(auth.require_admin),
):
    """Add recipe with URL form page."""
    return templates.TemplateResponse(
        request=request,
        name="add/url.html",
        context={
            "collection": collection,
            "error": request.query_params.get("error"),
        },
    )


@router.post("/collection/{collection}/add/url")
async def add_recipe_url(
    request: Request,
    collection: str,
    user: dict = Depends(auth.require_admin),
):
    """Add recipe with URL."""
    form = await request.form()
    url = form["url"]

    try:
        recipe = await cookbook.translate_url(
            url,
            user_agent=request.headers.get("user-agent"),
        )
    except aiohttp.client_exceptions.ClientConnectorError:
        return RedirectResponse(
            request.app.url_path_for(
                "add_recipe_url_form",
                collection=collection,
                error="notfound",
            ),
            status_code=303,
        )

    return templates.TemplateResponse(
        request=request,
        name="add/form.html",
        context={
            "collection": collection,
            "recipe": recipe,
            "action": request.app.url_path_for(
                "add_recipe_form",
                collection=collection,
            ),
            "refresh_warning": True,
        },
    )


@router.get("/collection/{collection}/add/text")
async def add_recipe_text_form(
    request: Request,
    collection: str,
    user: dict = Depends(auth.require_admin),
):
    """Add recipe from text form page."""
    return templates.TemplateResponse(
        request=request,
        name="add/text.html",
        context={
            "collection": collection,
            "error": request.query_params.get("error"),
        },
    )


@router.post("/collection/{collection}/add/text")
async def add_recipe_text(
    request: Request,
    collection: str,
    user: dict = Depends(auth.require_admin),
):
    """Add recipe from text."""
    form = await request.form()
    recipe = await cookbook.translate_page(form["text"])

    return templates.TemplateResponse(
        request=request,
        name="add/form.html",
        context={
            "collection": collection,
            "recipe": recipe,
            "action": request.app.url_path_for(
                "add_recipe_form",
                collection=collection,
            ),
            "refresh_warning": True,
        },
    )


@router.post("/add/upload-image")
async def upload_image(
    request: Request,
    user: dict = Depends(auth.require_admin),
):
    """Upload an image and return its URL."""
    form = await request.form()

    link = None

    for file in form.values():
        if not isinstance(file, UploadFile):
            continue

        link = await s3.upload_image(
            await file.read(),
            title=file.filename,
        )
        break

    return JSONResponse({"link": link})


@router.get("/collection/{collection}/add/form")
async def add_recipe_form_form(
    request: Request,
    collection: str,
    user: dict = Depends(auth.require_admin),
):
    """Add recipe from form, form page."""
    return templates.TemplateResponse(
        request=request,
        name="add/form.html",
        context={
            "collection": collection,
            "recipe": cookbook.Recipe(),
            "action": request.app.url_path_for(
                "add_recipe_form",
                collection=collection,
            ),
            "error": request.query_params.get("error"),
        },
    )


@router.post("/collection/{collection}/add/form")
async def add_recipe_form(
    request: Request,
    collection: str,
    user: dict = Depends(auth.require_admin),
):
    """Add recipe from form."""
    form = await request.form()
    recipe = _parse_recipe_form(form)

    id = await cookbook.add_recipe(collection, recipe)

    return RedirectResponse(
        request.app.url_path_for(
            "recipe",
            id=id,
            collection=collection,
        ),
        status_code=303,
    )


@router.post("/post/{collection}/{id}")
async def post_recipe(
    request: Request,
    collection: str,
    id: str,
    user: dict = Depends(auth.require_admin),
):
    """Post a recipe to Instagram."""
    recipes = await cookbook.get_recipes(collection)

    if id not in recipes:
        raise HTTPException(
            status_code=404,
            detail="No such recipe exists on this website",
        )

    recipe = recipes[id]

    if recipe.igcode:
        raise cookbook.instagram.InstagramError(
            f"Recipe was already posted to instagram " f"with code {recipe.igcode}"
        )

    if not recipe.name or not recipe.thumbnail:
        raise cookbook.instagram.InstagramError(
            "Cannot upload recipe without name or thumbnail"
        )

    code = await cookbook.instagram.post_instagram_recipe(
        recipe_name=recipe.name,
        image_url=recipe.thumbnail,
        user_agent=request.headers.get("user-agent"),
    )

    object.__setattr__(recipe, "igcode", code)

    await cookbook.update_recipe(collection, id, recipe)

    return JSONResponse(
        {
            "redirect": request.app.url_path_for(
                "recipe",
                id=id,
                collection=collection,
            )
        }
    )


@router.post("/move/{collectionfrom}/{collectionto}/{id}")
async def move_recipe(
    request: Request,
    collectionfrom: str,
    collectionto: str,
    id: str,
    user: dict = Depends(auth.require_admin),
):
    """Move recipe to other collection."""
    recipe = await cookbook.delete_recipe(collectionfrom, id)
    idto = await cookbook.add_recipe(collectionto, recipe)

    return JSONResponse(
        {
            "redirect": request.app.url_path_for(
                "recipe",
                id=idto,
                collection=collectionto,
            )
        }
    )
