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

    """ Cache for recipes, so we do not need to
    retrieve them from the GitHub every time """

    def __init__(self):
        self.recipes: dict[str, Recipe] = None
        self.sha: str = None  # file SHA from GitHub API
        self.recipe_timeout = None

    def asdict(self):
        return {
            recipe_id: dataclasses.asdict(recipe)
            for recipe_id, recipe in self.recipes.items()
        }

    def clear(self):
        self.recipes = None
        self.sha = None
        self.recipe_timeout = None


DEFAULT_COLLECTION = "recipes"
COLLECTIONS = {
    DEFAULT_COLLECTION, 
    "unmade"
}

# initialize with empty caches
_COLLECTIONS = {c: CollectionCache() for c in COLLECTIONS}


def _now() -> float:
    return datetime.datetime.now().timestamp()


def _get_collection(collection) -> CollectionCache:
    """ Get (cached) recipe collection by name """
    if collection not in COLLECTIONS:
        raise CookbookError(f"Collection {collection} not found")

    return _COLLECTIONS[collection]


async def _get_recipes(collection) -> CollectionCache:
    """ Refresh cache, and get collection """
    col = _get_collection(collection)

    # check collection cache timeout
    if col.recipe_timeout is not None:
        if datetime.datetime.now() > col.recipe_timeout:
            col.recipe_timeout = None

    if col.recipes is not None and col.recipe_timeout is not None and col.sha is not None:
        # invalid timeout, reset it
        col.recipe_timeout = datetime.datetime.now() + datetime.timedelta(minutes=15)
        return col

    # refresh cached collection
    async with aiohttp.ClientSession() as session:
        try:
            # get recipe collection from GitHub repo
            # use GitHub API, as the repo may be private
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

        # save all data from the repo
        # (part of) this is needed to correctly
        # push the updated collection on an update
        file = await res.json()
        col.sha = file["sha"]
        recipes = msgspec.json.decode(
            base64.b64decode(file["content"]),
            strict=False
        )

        # load the recipes
        col.recipes = {
            recipe_id: Recipe.from_data(**recipe)
            for recipe_id, recipe in recipes.items()
        }
        return col


async def get_recipes(collection: str) -> dict[str, Recipe]:
    """ Get the (possibly cached) recipes for a collection """
    return (await _get_recipes(collection)).recipes


def _generate_key(recipes) -> str:
    """ Generate a key for a new recipe """ 
    while True:
        key = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))
        if key not in recipes:
            return key


async def _push_recipes(collection: str, message: str):
    """ Push an updated collection to the repository
    with a given message """
    col = _get_collection(collection)

    async with aiohttp.ClientSession() as session:
        # encode and format collection
        data = msgspec.json.encode(col.asdict(), order='sorted')
        formatted = msgspec.json.format(data, indent=2)

        # execute push
        res = await session.put(
            f"https://api.github.com/repos/{RECIPE_REPO_USER}/{RECIPE_REPO_NAME}/contents/{collection}.json",
            data=msgspec.json.encode({
                "message": message,
                "content": base64.b64encode(formatted).decode("ascii"),
                "committer": {
                    "name": "Master Chef",
                    "email": "robot@masterchef.com"
                },
                "sha": col.sha
            }),
            headers={
                "accept": "application/vnd.github+json",
                "authorization": f"token {RECIPE_PAT}"
            }
        )

        # update cache SHA
        commit = await res.json()
        col.sha = commit["content"]["sha"]

        if not res.ok:
            col.clear()
            raise CookbookError(f"Error pushing recipe: {res.status} ({await res.text()})")


async def add_recipe(collection: str, recipe: Recipe):
    """ Add recipe to collection by name """
    now = _now()
    recipe = dataclasses.replace(
        recipe,
        date_created=recipe.date_created or now,
        date_updated=now
    )
    col = await _get_recipes(collection)
    key = _generate_key(col.recipes)
    col.recipes[key] = recipe
    await _push_recipes(
        collection, 
        f"Add recipe {recipe.name} in {collection}"
    )
    return key


async def update_recipe(collection: str, key: str, recipe: Recipe):
    """ Update recipe in collection by name and ID """
    col = await _get_recipes(collection)
    if key not in col.recipes:
        raise CookbookError(f"Cannot update recipe with id {key} in collection {collection}, as it does not exist")

    old_recipe = col.recipes[key]
    new_recipe = Recipe.from_data(**{
        **dataclasses.asdict(old_recipe),
        **dataclasses.asdict(recipe),
        # preserved "date_created" field
        "date_created": old_recipe.date_created,
        "date_updated": _now(),
        "igcode": recipe.igcode or old_recipe.igcode
    })

    if old_recipe == new_recipe:
        # nothing to update
        return

    # replace recipe in collection
    col.recipes[key] = new_recipe
    await _push_recipes(
        collection, 
        f"Update recipe {new_recipe.name} in {collection}"
    )
    return key


async def delete_recipe(collection: str, key: str):
    """ Remove recipe from collection """
    col = await _get_recipes(collection)
    recipe = col.recipes.pop(key)

    await _push_recipes(
        collection, 
        f"Delete recipe {recipe.name} in {collection}"
    )
    return recipe