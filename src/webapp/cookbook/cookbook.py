import aiohttp
import base64
import json
from dotenv import load_dotenv

load_dotenv()

import os


class CookbookError(Exception):
    pass


RECIPES = None


async def get_recipes():
    global RECIPES

    if RECIPES is not None:
        return RECIPES

    async with aiohttp.ClientSession() as session:
        res = await session.get(
            "https://api.github.com/repos/DenSinH/master-chef-recipes/contents/recipes.json",
            headers={
                "accept": "application/vnd.github+json",
                "authorization": f"token {os.environ['GITHUB_RECIPES_READ_PAT_TOKEN']}"
            }
        )

        if not res.ok:
            raise CookbookError(f"Error getting recipes: {res.status} ({res.text})")

        file = await res.json()
        RECIPES = json.loads(base64.b64decode(file["content"]).decode("utf-8"))
        return RECIPES
