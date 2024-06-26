import datetime
import aiohttp
import base64
import msgspec
import string
import random
import dataclasses
from dotenv import load_dotenv

load_dotenv()

import os

from .recipe import Recipe
from .utils import *

RECIPE_REPO_USER = os.environ["RECIPE_REPO_USER"]
RECIPE_REPO_NAME = os.environ["RECIPE_REPO_NAME"]
RECIPE_PAT = os.environ["RECIPE_PAT"]


class CollectionCache:

    def __init__(self):
        self.recipes: list[Recipe] = None
        self.file: dict = None  # full file info from GitHub API
        self.recipe_timeout = None

    def asdict(self):
        return {
            recipe_id: dataclasses.asdict(recipe)
            for recipe_id, recipe in self.recipes.items()
        }

    def clear(self):
        self.recipes = None
        self.file = None
        self.recipe_timeout = None


DEFAULT_COLLECTION = "recipes"
COLLECTIONS = {
    DEFAULT_COLLECTION, 
    "unmade"
}
_COLLECTIONS = {c: CollectionCache() for c in COLLECTIONS}


def _now():
    return datetime.datetime.now().timestamp()


def _get_collection(collection) -> CollectionCache:
    if collection not in COLLECTIONS:
        raise CookbookError(f"Collection {collection} not found")

    return _COLLECTIONS[collection]


async def _get_recipes(collection) -> CollectionCache:
    col = _get_collection(collection)

    # check collection cache timeout
    if col.recipe_timeout is not None:
        if datetime.datetime.now() > col.recipe_timeout:
            col.recipe_timeout = None

    if col.recipes is not None and col.recipe_timeout is not None and col.file is not None:
        col.recipe_timeout = datetime.datetime.now() + datetime.timedelta(minutes=15)
        return col

    async with aiohttp.ClientSession() as session:
        try:
            res = await session.get(
                f"https://api.github.com/repos/{RECIPE_REPO_USER}/{RECIPE_REPO_NAME}/contents/{collection}.json",
                headers={
                    "accept": "application/vnd.github+json",
                    "authorization": f"token {RECIPE_PAT}"
                }
            )
        except aiohttp.ClientConnectionError:
            raise CookbookError(f"Error getting recipes: failed to connect")

        if not res.ok:
            raise CookbookError(f"Error getting recipes: {res.status} ({await res.text()})")

        col.file = await res.json()
        recipes = msgspec.json.decode(
            base64.b64decode(col.file["content"]),
            strict=False
        )
        col.recipes = {
            recipe_id: Recipe.from_data(**recipe)
            for recipe_id, recipe in recipes.items()
        }
        return col


async def get_recipes(collection) -> dict[str, Recipe]:
    return (await _get_recipes(collection)).recipes


def _generate_key(recipes) -> str:
    while True:
        key = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))
        if key not in recipes:
            return key


async def _push_recipes(collection, message):
    col = _get_collection(collection)

    async with aiohttp.ClientSession() as session:
        data = msgspec.json.encode(col.asdict(), order='sorted')
        formatted = msgspec.json.format(data, indent=2)
        res = await session.put(
            f"https://api.github.com/repos/{RECIPE_REPO_USER}/{RECIPE_REPO_NAME}/contents/{collection}.json",
            data=msgspec.json.encode({
                "message": message,
                "content": base64.b64encode(formatted).decode("ascii"),
                "committer": {
                    "name": "Master Chef",
                    "email": "robot@masterchef.com"
                },
                "sha": col.file["sha"]
            }),
            headers={
                "accept": "application/vnd.github+json",
                "authorization": f"token {RECIPE_PAT}"
            }
        )

        # regardless of whether the update was successful, we need to retrieve the recipies again, because
        # the SHA changed
        col.clear()

        if not res.ok:
            raise CookbookError(f"Error pushing recipe: {res.status} ({await res.text()})")


async def add_recipe(collection, recipe: Recipe):
    now = _now()
    if not recipe.date_created:
        recipe.date_created = now
    recipe.date_updated = now
    col = await _get_recipes(collection)
    key = _generate_key(col.recipes)
    col.recipes[key] = recipe
    await _push_recipes(collection, f"Add recipe {recipe.name} in {collection}")
    return key


async def update_recipe(collection, key, recipe):
    col = await _get_recipes(collection)
    if key not in col.recipes:
        raise CookbookError(f"Cannot update recipe with id {key} in collection {collection}, as it does not exist")

    old_recipe = col.recipes[key]
    new_recipe = Recipe.from_data(**{
        **dataclasses.asdict(old_recipe),
        **dataclasses.asdict(recipe),
        # preserved "date_created" field
        "date_created": old_recipe.date_created,
        "date_updated": _now()
    })

    if old_recipe == new_recipe:
        # nothing to update
        return

    col.recipes[key] = new_recipe
    await _push_recipes(collection, f"Update recipe {new_recipe.name} in {collection}")
    return key


async def delete_recipe(collection, key):
    col = await _get_recipes(collection)
    recipe = col.recipes.pop(key)

    await _push_recipes(collection, f"Delete recipe {recipe.name} in {collection}")
    return recipe