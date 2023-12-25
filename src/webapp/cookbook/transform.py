import openai
import aiohttp
from bs4 import BeautifulSoup
import tldextract as tld
from dotenv import load_dotenv

load_dotenv()

import os
import re
import json
import random

from .utils import *
from .thumbnail import get_thumbnail


openai.api_key = os.environ["OPENAI_API_KEY"]


def _get_headers(url):
    _NO_USER_AGENT = {
        "cdninstagram",
        "ig",
        "igsonar",
        "facebook",
        "instagram"
    }
    _USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.62',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/111.0'
    ]
    headers = {}
    if tld.extract(url).domain.lower() not in _NO_USER_AGENT:
        headers["User-Agent"] = random.choice(_USER_AGENTS)
    return headers


MAX_RETRIES = 1
MODEL = "gpt-3.5-turbo"
PROMPT = """
The following text is from a website, and it contains a recipe, possibly in Dutch, as well as unnecessary other text from the webpage.
The recipe contains information on the ingredients, the preparation and possibly nutritional information.
Convert the recipe to a JSON object with the following keys:
"name": the name of this recipe.
"ingredients": a list of dictionaries, with keys "ingredient", mapping to the name of the ingredient, and "amount" which is a string containing the amount of this ingredient needed including the unit, or 
               a null value if no specific amount is given.
               For example, the ingredient "one onion" should yield {{'amount': '1', 'ingredient': 'onion'}}, and the ingredient "zout" should yield {{'amount': null, 'ingredient': 'zout'}}.
"preparation": a list of strings containing the steps of the recipe.
"nutrition": null if there is no nutritional information in the recipe, or a list of dictionaries containing the keys "group", with the type
of nutrional information, and "amount": with the amount of this group that is contained in the recipe, as a string including the unit.
"people": the amount of people that can be fed from this meal as an integer, in case this information is present, otherwise null
"time": the time that this recipe takes to make in minutes as an integer, in case this information is present, otherwise null
"tags": interpret the recipe, and generate a list of at most 5 English strings that describe this recipe. For example, what the main ingredient is,
        if it takes long or short to make, whether it is especially high or low in certain nutritional groups, tags like that. Make
        sure the strings are in English.

Keep the language the same, except in the tags, and preferably do not change anything about the text in the recipe at all.
Only output the JSON object, and nothing else.
Here comes the text:

{text}
"""


def fix_recipe(_recipe):
    def _get_or_none(obj, key, typ):
        return typ(obj[key]) if (key in obj and obj[key] is not None) else None

    recipe = {}
    if "name" not in _recipe:
        raise CookbookError("Recipe has no name")
    recipe["name"] = str(_recipe["name"])

    for (key, typ) in [("time", int), ("people", int), ("url", str), ("thumbnail", str)]:
        recipe[key] = _get_or_none(_recipe, key, typ)

    recipe["ingredients"] = []
    for ingredient in _recipe.get("ingredients", []):
        recipe["ingredients"].append({
            "amount": _get_or_none(ingredient, "amount", str),
            "ingredient": str(ingredient["ingredient"])
        })

    recipe["preparation"] = []
    for step in _recipe.get("preparation", []):
        recipe["preparation"].append(str(step))

    if "nutrition" in _recipe and _recipe["nutrition"] is not None:
        recipe["nutrition"] = []
        for group in _recipe.get("nutrition", []):
            recipe["nutrition"].append({
                "amount": _get_or_none(group, "amount", str),
                "group": str(group["group"])
            })
    else:
        recipe["nutrition"] = None

    recipe["tags"] = []
    for tag in _recipe.get("tags", []):
        recipe["tags"].append(str(tag))

    return recipe


async def translate_url(url):
    print(f"Retrieving url {url}")
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False), headers=_get_headers(url)) as session:
        res = await session.get(url)
        if not res.ok:
            raise CookbookError(f"Could not get the specified url, status code {res.status}")
        soup = BeautifulSoup(await res.text(), features="html.parser")

        # remove comment sections from website
        COMMENTS = ["comment", "opmerking"]
        for attr in ["class", "id"]:
            for element in soup.find_all(attrs={attr: re.compile(fr".*({'|'.join(COMMENTS)}).*", flags=re.IGNORECASE)}):
                element.decompose()

        text = re.sub(r"(\n\s*)+", "\n", soup.text)
        recipe = await translate_page(text, url=url, thumbnail=get_thumbnail(soup))
        return recipe


async def translate_page(text, url=None, thumbnail=None):
    print(f"Converting with ChatGPT ({MODEL})")
    messages = [
        {"role": "system", "content": "You are a helpful assistant that converts recipies into JSON format."},
        {"role": "user", "content": PROMPT.format(text=text)}
    ]
    for i in range(1 + MAX_RETRIES):
        try:
            chat_completion = await openai.ChatCompletion.acreate(
                model=MODEL, messages=messages, temperature=0.2
            )
        except openai.error.ServiceUnavailableError:
            # todo: openai.error.ServiceUnavailableError: The server is overloaded or not ready yet.
            # try again later
            raise
        except openai.error.InvalidRequestError:
            # openai.error.InvalidRequestError: This model's maximum context length is 4097 tokens. However, your messages resulted in 4119 tokens. Please reduce the length of the messages.
            # try using text or increase model size
            raise
        reply = chat_completion.choices[0].message.content
        try:
            # add url / thumbnail after the fact, since we want to use as few tokens as possible
            fixed = fix_recipe(json.loads(reply))
            fixed["url"] = url
            fixed["thumbnail"] = thumbnail
            return fixed
        except json.JSONDecodeError:
            print("Conversion failed, retrying")
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content": "this is not a parseable json object, "
                                                        "only output the json object"})
    raise CookbookError("ChatGPT did not return a parsable json object, please try again")


if __name__ == '__main__':
    from pprint import pprint

    recipe = translate_url("https://15gram.be/recepten/wraps-kip-tikka-masala")
    pprint(recipe)
