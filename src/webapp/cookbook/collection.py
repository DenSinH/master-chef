import base64
import datetime
import logging
import os
import random
import string
from dataclasses import dataclass, field

import aiohttp
import msgspec.json
import pydantic

from .errors import CookbookError
from .recipe import Recipe
from .timeutil import now

logger = logging.getLogger(__name__)

RECIPE_REPO_USER = os.environ["RECIPE_REPO_USER"]
RECIPE_REPO_NAME = os.environ["RECIPE_REPO_NAME"]
RECIPE_PAT = os.environ["RECIPE_PAT"]

RECIPE_KEY_LEN = 10
RECIPE_ADAPTER = pydantic.TypeAdapter(dict[str, Recipe])


@dataclass(kw_only=True, slots=True)
class Collection:
    """Cache for recipes, so we do not need to retrieve them from the GitHub every time"""

    name: str
    _recipes: dict[str, Recipe] = field(default_factory=dict)
    _sha: str | None = None  # file SHA from GitHub API
    _timeout: datetime.datetime | None = None

    def asdict(self):
        return {
            recipe_id: recipe.model_dump()
            for recipe_id, recipe in self._recipes.items()
        }

    def reset_timeout(self):
        self._timeout = now() + datetime.timedelta(minutes=15)

    async def _refresh(self) -> None:
        """Refresh cache, and get collection"""
        # check collection cache timeout
        if self._timeout is not None:
            if datetime.datetime.now().astimezone() > self._timeout:
                logger.info(f"Collection {self.name} expired")
                self._timeout = None
            elif self._recipes and self._sha is not None:
                # invalid timeout, reset it
                self.reset_timeout()
                return
            else:
                # cache still valid
                return

        # refresh cached collection
        async with aiohttp.ClientSession() as session:
            logger.info(f"Retrieving collection {self.name}")
            try:
                # get recipe collection from GitHub repo
                # use GitHub API, as the repo may be private
                res = await session.get(
                    f"https://api.github.com/repos/{RECIPE_REPO_USER}/{RECIPE_REPO_NAME}/contents/{self.name}.json",
                    headers={
                        "accept": "application/vnd.github+json",
                        "authorization": f"token {RECIPE_PAT}",
                    },
                )
            except aiohttp.ClientConnectionError:
                raise CookbookError("Error getting recipes: failed to connect")

            if not res.ok:
                raise CookbookError(
                    f"Error getting recipes: {res.status} ({await res.text()})"
                )

            # save all data from the repo
            # (part of) this is needed to correctly
            # push the updated collection on an update
            file = await res.json()
            self._sha = file["sha"]
            recipes = msgspec.json.decode(
                base64.b64decode(file["content"]), strict=False
            )

            # load the recipes
            self._recipes = RECIPE_ADAPTER.validate_python(recipes)
            self.reset_timeout()

    def clear(self):
        self._recipes = {}
        self._sha = None
        self._timeout = None

    async def get_sha(self) -> str:
        await self._refresh()
        assert (
            self._sha is not None
        ), f"Expected file sha after reloading recipes for collection {self.name}"
        return self._sha

    async def get_recipes(self) -> dict[str, Recipe]:
        await self._refresh()
        return self._recipes

    def _generate_key(self) -> str:
        """Generate a new key for a recipe"""
        while True:
            key = "".join(
                random.choice(string.ascii_lowercase) for _ in range(RECIPE_KEY_LEN)
            )
            if key not in self._recipes:
                return key

    async def add(self, recipe: Recipe) -> str:
        """Add a recipe to this collection, return the key that was added"""
        await self._refresh()
        recipe = recipe.model_copy(
            update={
                "date_created": recipe.date_created or now().timestamp(),
                "date_updated": now().timestamp(),
            }
        )
        key = self._generate_key()
        self._recipes[key] = recipe
        await self.push(f"Add recipe {recipe.name} in {self.name}")
        return key

    async def update(self, key: str, recipe: Recipe) -> None:
        """Update a given recipe"""
        await self._refresh()
        if key not in self._recipes:
            msg = (
                f"Cannot update recipe with id {key} in collection {self.name}, "
                f"as it does not exist"
            )
            raise CookbookError(msg)

        old_recipe = self._recipes[key]
        new_recipe = recipe.model_copy(
            # preserved automatic fields
            update={
                "date_created": old_recipe.date_created,
                "date_updated": now().timestamp(),
                "igcode": recipe.igcode or old_recipe.igcode,
            }
        )

        if old_recipe == new_recipe:
            # nothing to update
            return

        # replace recipe in collection
        self._recipes[key] = new_recipe
        await self.push(f"Update recipe {new_recipe.name} in {self.name}")

    async def delete(self, key: str) -> Recipe:
        """Delete a recipe from this collection"""
        await self._refresh()
        recipe = self._recipes.pop(key)

        await self.push(f"Delete recipe {recipe.name} in {self.name}")
        return recipe

    async def push(self, message: str):
        """Push an updated collection to the repository with a given message"""
        logger.info(f"Pushing collection {self.name}")
        assert self._sha is not None

        async with aiohttp.ClientSession() as session:
            # encode and format collection
            data = msgspec.json.encode(self.asdict(), order="sorted")
            formatted = msgspec.json.format(data, indent=2)

            # execute push
            res = await session.put(
                f"https://api.github.com/repos/{RECIPE_REPO_USER}/{RECIPE_REPO_NAME}/contents/{self.name}.json",
                data=msgspec.json.encode(
                    {
                        "message": message,
                        "content": base64.b64encode(formatted).decode("ascii"),
                        "committer": {
                            "name": "Master Chef",
                            "email": "chef@dennishilhorst.nl",
                        },
                        "sha": self._sha,
                    }
                ),
                headers={
                    "accept": "application/vnd.github+json",
                    "authorization": f"token {RECIPE_PAT}",
                },
            )

            # update cache SHA
            commit = await res.json()
            self._sha = commit["content"]["sha"]

            if not res.ok:
                self.clear()
                raise CookbookError(
                    f"Error pushing recipe: {res.status} ({await res.text()})"
                )

            # reset timeout on successful push
            self.reset_timeout()


DEFAULT_COLLECTION = "recipes"
COLLECTIONS = {DEFAULT_COLLECTION, "unmade"}

# initialize with empty caches
_COLLECTIONS = {name: Collection(name=name) for name in COLLECTIONS}


def _get_collection(collection: str) -> Collection:
    """Get (cached) recipe collection by name"""
    if collection not in COLLECTIONS:
        raise CookbookError(f"Collection {collection} not found")

    return _COLLECTIONS[collection]


async def get_collection_etag(collection: str) -> str:
    """Get the current file sha for a collection"""
    col = _get_collection(collection)
    return await col.get_sha()


async def get_recipes(collection: str) -> dict[str, Recipe]:
    """Get the (possibly cached) recipes for a collection"""
    col = _get_collection(collection)
    return await col.get_recipes()


async def add_recipe(collection: str, recipe: Recipe):
    """Add recipe to collection by name"""
    col = _get_collection(collection)
    return await col.add(recipe)


async def update_recipe(collection: str, key: str, recipe: Recipe) -> None:
    """Update recipe in collection by name and ID"""
    col = _get_collection(collection)
    await col.update(key, recipe)


async def delete_recipe(collection: str, key: str) -> Recipe:
    """Remove recipe from collection, returns the deleted recipe"""
    col = _get_collection(collection)
    return await col.delete(key)
