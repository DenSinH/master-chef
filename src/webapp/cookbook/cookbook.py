import datetime
import aiohttp
import base64
import json
import string
import random
import copy
from dotenv import load_dotenv

load_dotenv()

import os

from .utils import *

RECIPE_REPO_USER = os.environ["RECIPE_REPO_USER"]
RECIPE_REPO_NAME = os.environ["RECIPE_REPO_NAME"]
RECIPE_PAT = os.environ["RECIPE_PAT"]


class CollectionCache:

    def __init__(self):
        self.recipes = None
        self.file = None
        self.recipe_timeout = None

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
        col.recipes = json.loads(base64.b64decode(col.file["content"]).decode("utf-8"))
        return col


async def get_recipes(collection):
    # for external use, ensure we don't mutate our collection cache
    return copy.deepcopy((await _get_recipes(collection)).recipes)


def _generate_key(recipes):
    while True:
        key = ''.join(random.choice(string.ascii_lowercase) for x in range(10))
        if key not in recipes:
            return key


async def _push_recipes(collection, message):
    col = _get_collection(collection)

    async with aiohttp.ClientSession() as session:
        res = await session.put(
            f"https://api.github.com/repos/{RECIPE_REPO_USER}/{RECIPE_REPO_NAME}/contents/{collection}.json",
            data=json.dumps({
                "message": message,
                "content": base64.b64encode(json.dumps(col.recipes, indent=2, sort_keys=True).encode("ascii")).decode("ascii"),
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


async def add_recipe(collection, recipe):
    now = _now()
    if "date_created" not in recipe:
        recipe["date_created"] = now
    recipe["date_updated"] = now
    col = await _get_recipes(collection)
    key = _generate_key(col.recipes)
    col.recipes[key] = recipe
    await _push_recipes(collection, f"Add recipe {recipe['name']} in {collection}")
    return key


async def update_recipe(collection, key, recipe):
    col = await _get_recipes(collection)
    if key not in col.recipes:
        raise CookbookError(f"Cannot update recipe with id {key} in collection {collection}, as it does not exist")

    new_recipe = copy.deepcopy(col.recipes[key])

    # preserved "date_created" fields etc.
    new_recipe.update(**recipe)
    if col.recipes[key] == new_recipe:
        # nothing to update
        return
    new_recipe["date_updated"] = _now()

    col.recipes[key] = new_recipe
    await _push_recipes(collection, f"Update recipe {new_recipe['name']} in {collection}")
    return key


async def delete_recipe(collection, key):
    col = await _get_recipes(collection)
    recipe = col.recipes.pop(key)

    await _push_recipes(collection, f"Delete recipe {recipe['name']} in {collection}")
    return recipe