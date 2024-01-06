import asyncio
import cookbook
from cookbook.transform import META_PROMPT, _chatgpt_json_and_fix, fix_meta
from cookbook.cookbook import _push_recipes, _get_recipes
import json
from pprint import pprint


TRANSFORM_PROMPT = """
The following recipe is taken from a website and converted to a JSON object:
{recipe}
""" + META_PROMPT


async def convert_all(collection):
    recipes = await _get_recipes(collection)
    for key, recipe in recipes.recipes.items():
        print("converting", key)
        pprint(recipe)
        if "tags" in recipe:
            recipe.pop("tags")

        messages = [
            {"role": "system", "content": "You are a helpful assistant that converts recipies into JSON format."},
            {"role": "user", "content": TRANSFORM_PROMPT.format(recipe=json.dumps(recipe, indent=2))}
        ]
        _, meta = await _chatgpt_json_and_fix(messages, fix_meta)
        recipe["meta"] = meta
        pprint(meta)
    await _push_recipes(collection, "Add meta to all recipes")

if __name__ == '__main__':
    from pprint import pprint

    recipe = asyncio.run(convert_all("unmade"))
    pprint(recipe)
