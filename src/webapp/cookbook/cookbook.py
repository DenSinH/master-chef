import datetime

import aiohttp
import base64
import json
import string
import random
from dotenv import load_dotenv

load_dotenv()

import os

from .utils import *


RECIPES = None
FILE = None

def _now():
    return datetime.datetime.now().timestamp()


async def _get_recipes():
    global RECIPES, FILE

    if RECIPES is not None:
        return RECIPES, FILE

    async with aiohttp.ClientSession() as session:
        try:
            res = await session.get(
                "https://api.github.com/repos/DenSinH/master-chef-recipes/contents/recipes.json",
                headers={
                    "accept": "application/vnd.github+json",
                    "authorization": f"token {os.environ['GITHUB_RECIPES_READ_PAT_TOKEN']}"
                }
            )
        except aiohttp.ClientConnectionError:
            raise CookbookError(f"Error getting recipes: failed to connect")

        if not res.ok:
            raise CookbookError(f"Error getting recipes: {res.status} ({res.text})")

        FILE = await res.json()
        RECIPES = json.loads(base64.b64decode(FILE["content"]).decode("utf-8"))
        return RECIPES, FILE


async def get_recipes():
    return (await _get_recipes())[0]


def _generate_key(recipes):
    while True:
        key = ''.join(random.choice(string.ascii_lowercase) for x in range(10))
        if key not in recipes:
            return key


async def _push_recipes(recipes, file, message):

    async with aiohttp.ClientSession() as session:
        res = await session.put(
            "https://api.github.com/repos/DenSinH/master-chef-recipes/contents/recipes.json",
            data=json.dumps({
                "message": message,
                "content": base64.b64encode(json.dumps(recipes, indent=2, sort_keys=True).encode("ascii")).decode("ascii"),
                "committer": {
                    "name": "Master Chef",
                    "email": "robot@masterchef.com"
                },
                "sha": file["sha"]
            }),
            headers={
                "accept": "application/vnd.github+json",
                "authorization": f"token {os.environ['GITHUB_RECIPES_WRITE_PAT_TOKEN']}"
            }
        )

        if not res.ok:
            raise CookbookError(f"Error adding recipe: {res.status} ({await res.text()})")


async def add_recipe(recipe):
    recipe = fix_recipe(recipe)
    now = _now()
    recipe["date_created"] = now
    recipe["date_updated"] = now
    recipes, file = await _get_recipes()
    key = _generate_key(recipes)
    recipes[key] = recipe
    await _push_recipes(recipes, file, f"Add recipe {recipe['name']}")
    return key


async def update_recipe(key, recipe):
    recipe = fix_recipe(recipe)
    recipes, file = await _get_recipes()
    if key not in recipes:
        raise CookbookError(f"Cannot update recipe with id {key}, as it does not exist")

    if recipes[key] == recipe:
        # nothing to update
        return
    recipe["date_updated"] = _now()

    recipes[key] = recipe
    await _push_recipes(recipes, file, f"Update recipe {recipe['name']}")
    return key


async def delete_recipe(key):
    recipes, file = await _get_recipes()
    recipe = recipes.pop(key)

    await _push_recipes(recipes, file, f"Delete recipe {recipe['name']}")
