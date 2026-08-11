import asyncio
import dataclasses
import datetime
import logging
import secrets
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

import aiohttp
from aiohttp.client_exceptions import ClientResponseError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from starlette.datastructures import FormData

from webapp import auth, cookbook
from webapp.app import templates
from webapp.utils import s3

from .common import require_collection

logger = logging.getLogger(__name__)

router = APIRouter()

# Translation jobs (kicked off by /add/url or /add/text) run independently
# of any particular HTTP connection, so the frontend can stream their
# progress via a native EventSource, which reconnects automatically without
# re-triggering the (slow, non-idempotent) ChatGPT call. Jobs are looked up
# by token, and cleaned up TRANSLATION_JOB_TTL seconds after they finish.
TRANSLATION_JOB_TTL = 600

# Cache for freshly generated recipes to avoid losing them on client disconnect
# cleaned after PENDING_RECIPE_TTL seconds when another recipe is added
PENDING_RECIPE_TTL = 3600


@dataclasses.dataclass(frozen=True)
class _PendingRecipe:
    """Transformed recipe that has not been (manually) confirmed yet."""

    created: float
    collection: str
    recipe: cookbook.Recipe


_pending_recipes: dict[str, _PendingRecipe] = {}


def _store_pending_recipe(collection: str, recipe: cookbook.Recipe) -> str:
    """Store a freshly generated recipe, returning a token that can be used
    to retrieve (and remove) it via `add_recipe_pending_form`."""

    # clear out unused recipes
    now = time.monotonic()
    for key, pending in list(_pending_recipes.items()):
        if now - pending.created > PENDING_RECIPE_TTL:
            del _pending_recipes[key]

    token = secrets.token_urlsafe(16)
    _pending_recipes[token] = _PendingRecipe(now, collection, recipe)
    return token


@dataclasses.dataclass
class _TranslationJob:
    collection: str
    error_redirect: str
    chunks: list[str] = dataclasses.field(default_factory=list)
    recipe: cookbook.Recipe | None = None
    error: str | None = None
    new_data: asyncio.Event = dataclasses.field(default_factory=asyncio.Event)
    done: asyncio.Event = dataclasses.field(default_factory=asyncio.Event)
    finished: float | None = None


_translation_jobs: dict[str, _TranslationJob] = {}


async def _run_translation_job(
    job: _TranslationJob, events: AsyncIterator[str | cookbook.Recipe]
) -> None:
    """Consume a `translate_page_stream`-style async generator, buffering its
    output on `job` so it can be replayed to (possibly multiple, reconnecting)
    SSE consumers, independently of this task's own lifetime."""
    try:
        async for event in events:
            if isinstance(event, cookbook.Recipe):
                job.recipe = event
            else:
                job.chunks.append(event)
                job.new_data.set()
    except Exception:
        logger.exception("Failed to generate recipe")
        job.error = "Something went wrong while generating the recipe"
    finally:
        job.finished = time.monotonic()
        job.done.set()
        job.new_data.set()


def _start_translation_job(
    collection: str, error_redirect: str, events: AsyncIterator[str | cookbook.Recipe]
) -> str:
    """Start `events` (a `translate_page_stream`-style async generator)
    running in the background, returning a token that can be used to stream
    its progress via `add_recipe_stream`."""
    now = time.monotonic()
    for key, old_job in list(_translation_jobs.items()):
        if (
            old_job.finished is not None
            and now - old_job.finished > TRANSLATION_JOB_TTL
        ):
            del _translation_jobs[key]

    token = secrets.token_urlsafe(16)
    job = _TranslationJob(collection, error_redirect)
    _translation_jobs[token] = job
    asyncio.ensure_future(_run_translation_job(job, events))
    return token


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
    _: None = Depends(require_collection),
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
    _: None = Depends(require_collection),
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
    _: None = Depends(require_collection),
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
    _: None = Depends(require_collection),
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
    _: None = Depends(require_collection),
    user: dict = Depends(auth.require_admin),
):
    """Start translating a recipe from a URL in the background, returning a
    token that can be used to stream its progress via `add_recipe_stream`."""
    form = await request.form()
    url = form["url"]

    try:
        text, thumbnail = await cookbook.get_recipe_text(
            url,
            user_agent=request.headers.get("user-agent"),
        )
    except aiohttp.client_exceptions.ClientConnectorError:
        return JSONResponse(
            {
                "redirect": (
                    str(
                        request.app.url_path_for(
                            "add_recipe_url_form",
                            collection=collection,
                        )
                    )
                    + "?error=notfound"
                )
            }
        )

    error_redirect = (
        str(request.app.url_path_for("add_recipe_url_form", collection=collection))
        + "?error=chatgpt"
    )

    token = _start_translation_job(
        collection,
        error_redirect,
        cookbook.translate_page_stream(text, url=url, thumbnail=thumbnail),
    )

    return JSONResponse(
        {
            "stream": str(
                request.app.url_path_for(
                    "add_recipe_stream",
                    collection=collection,
                    token=token,
                )
            )
        }
    )


@router.get(
    "/collection/{collection}/add/stream/{token}", response_class=EventSourceResponse
)
async def add_recipe_stream(
    request: Request,
    collection: str,
    token: str,
    _: None = Depends(require_collection),
    user: dict = Depends(auth.require_admin),
):
    """Stream the progress of a translation job started by `add_recipe_url` or
    `add_recipe_text`, as raw JSON text chunks, followed by a final "done" or
    "error" event."""
    job = _translation_jobs.get(token)
    if job is None or job.collection != collection:
        yield ServerSentEvent(
            event="error",
            data={
                "message": "This translation could not be found, it may have expired",
                "redirect": (
                    str(
                        request.app.url_path_for(
                            "add_recipe_url_form", collection=collection
                        )
                    )
                    + "?error=chatgpt"
                ),
            },
        )
        return

    position = 0
    while True:
        while position < len(job.chunks):
            yield ServerSentEvent(event="progress", data={"text": job.chunks[position]})
            position += 1

        if job.done.is_set():
            break

        await job.new_data.wait()
        job.new_data.clear()

    if job.recipe is not None:
        recipe_token = _store_pending_recipe(collection, job.recipe)
        yield ServerSentEvent(
            event="done",
            data={
                "redirect": str(
                    request.app.url_path_for(
                        "add_recipe_pending_form",
                        collection=collection,
                        token=recipe_token,
                    )
                )
            },
        )
    else:
        yield ServerSentEvent(
            event="error",
            data={
                "message": job.error
                or "Something went wrong while generating the recipe",
                "redirect": job.error_redirect,
            },
        )


@router.get("/collection/{collection}/add/pending/{token}")
async def add_recipe_pending_form(
    request: Request,
    collection: str,
    token: str,
    _: None = Depends(require_collection),
    user: dict = Depends(auth.require_admin),
):
    """Render a freshly generated (not yet saved) recipe produced by
    streaming translation of a URL or piece of text. The recipe is looked up
    (and removed) from the in-memory pending store by `token`."""
    pending = _pending_recipes.pop(token, None)
    if pending is None or pending.collection != collection:
        return RedirectResponse(
            str(request.app.url_path_for("add_recipe_url_form", collection=collection))
            + "?error=chatgpt",
            status_code=303,
        )

    return templates.TemplateResponse(
        request=request,
        name="add/form.html",
        context={
            "collection": collection,
            "recipe": pending.recipe,
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
    _: None = Depends(require_collection),
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
    _: None = Depends(require_collection),
    user: dict = Depends(auth.require_admin),
):
    """Start translating a recipe from text in the background, returning a
    token that can be used to stream its progress via `add_recipe_stream`."""
    form = await request.form()

    error_redirect = (
        str(request.app.url_path_for("add_recipe_text_form", collection=collection))
        + "?error=chatgpt"
    )

    token = _start_translation_job(
        collection,
        error_redirect,
        cookbook.translate_page_stream(form["text"]),
    )

    return JSONResponse(
        {
            "stream": str(
                request.app.url_path_for(
                    "add_recipe_stream",
                    collection=collection,
                    token=token,
                )
            )
        }
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
    _: None = Depends(require_collection),
    user: dict = Depends(auth.require_admin),
):
    """Add recipe from form, form page."""
    return templates.TemplateResponse(
        request=request,
        name="add/form.html",
        context={
            "collection": collection,
            "recipe": cookbook.Recipe(name=""),
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
    _: None = Depends(require_collection),
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
    _: None = Depends(require_collection),
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
