import hashlib
import logging
from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from webapp import auth, cookbook
from webapp.app import templates

from .common import require_collection

logger = logging.getLogger()
router = APIRouter()


@router.get("/")
async def index(request: Request):
    """Index page"""
    # show default collection
    return await collection(request, collection=cookbook.DEFAULT_COLLECTION)


def _update_etag_reqinfo(
    etag: hashlib._Hash, is_admin: bool, username: str | None
) -> str:
    """Update etag hash with request info"""
    etag.update(is_admin.to_bytes())
    etag.update((username or "").encode("utf-8", errors="ignore"))
    return etag.hexdigest()


@router.get("/collection/{collection}")
async def collection(
    request: Request,
    collection: str = cookbook.DEFAULT_COLLECTION,
    _: None = Depends(require_collection),
):
    """Get a recipe collection"""
    is_admin = auth.is_admin(request)
    username = auth._get_username(request)

    etag = _update_etag_reqinfo(
        hashlib.sha256(
            (await cookbook.get_collection_etag(collection)).encode("ascii"),
            usedforsecurity=False,
        ),
        is_admin=is_admin,
        username=username,
    )

    if not request.app.debug:
        if_match = request.headers.get("If-None-Match")

        if if_match == etag:
            return Response(
                status_code=304,
                headers={"ETag": etag},
            )

    recipes = await cookbook.get_recipes(collection)

    ordered = OrderedDict(
        sorted(recipes.items(), key=lambda x: x[1].date_updated, reverse=True)
    )

    # user-specific rendering
    if username is not None:
        title = f"{username}'s Kitchen"
    else:
        title = cookbook.generate_title()

    return templates.TemplateResponse(
        request=request,
        name="cookbook.html",
        context={
            "collection": collection,
            "collections": cookbook.COLLECTIONS,
            "recipes": ordered,
            "is_admin": is_admin,
            "username": username,
            "latest": max(
                recipes,
                key=lambda recipe_id: recipes[recipe_id].date_created,
                default=None,
            ),
            "title": title,
        },
        headers={"ETag": etag},
    )


@router.get("/about")
async def about(request: Request):
    """About page"""
    return templates.TemplateResponse(
        request=request,
        name="about.html",
        context={},
    )


@router.get("/health")
async def health():
    return Response(status_code=200)


@router.get("/recipe/{collection}/{id}")
async def recipe(
    request: Request,
    collection: str,
    id: str,
    _: None = Depends(require_collection),
):
    """Recipe viewer page"""
    recipes = await cookbook.get_recipes(collection)
    if id not in recipes:
        raise HTTPException(
            status_code=404,
            detail="No such recipe exists on this website",
        )

    # user specific data
    is_admin = auth.is_admin(request)
    username = auth._get_username(request)

    # update recipe sha with user info
    recipe = recipes[id]
    etag = _update_etag_reqinfo(
        recipe.sha,
        is_admin=is_admin,
        username=username,
    )
    if not request.app.debug:
        if_match = request.headers.get("If-None-Match")
        if if_match is not None and if_match == etag:
            # use cached response
            return Response(
                status_code=304,
                headers={"ETag": etag},
            )

    response = templates.TemplateResponse(
        request=request,
        name="recipe.html",
        context={
            "collection": collection,
            "recipe": recipe,
            "recipe_id": id,
            "is_admin": is_admin,
        },
        headers={"ETag": etag},
    )

    response.set_cookie("last-recipe", id)
    response.set_cookie("last-collection", collection)

    return response


# extra endpoint with a "pretty recipe name"
# this is discarded and can be anything really
@router.get("/recipe/{collection}/{id}/{name}")
async def _recipe(
    request: Request,
    collection: str,
    id: str,
    name: str,
    _: None = Depends(require_collection),
):
    return await recipe(request, collection, id)
