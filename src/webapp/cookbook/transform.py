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
from .meta import *
from .thumbnail import get_thumbnail


client = openai.AsyncOpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)


def _get_headers(url):
    _NO_USER_AGENT = {
        "cdninstagram",
        "ig",
        "igsonar",
        "facebook",
        "instagram"
    }
    _USER_AGENTS = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.2210.91',
        'Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (X11; Linux i686; rv:109.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:109.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0',
    ]
    headers = {}
    if tld.extract(url).domain.lower() not in _NO_USER_AGENT:
        headers["User-Agent"] = random.choice(_USER_AGENTS)
    return headers


MAX_RETRIES = 1
MODEL = "gpt-3.5-turbo-1106"
PROMPT = """
The following text is from a website, and it contains a recipe, possibly in Dutch, as well as unnecessary other text from the webpage.
The recipe contains information on the ingredients, the preparation and possibly nutritional information.
Convert the recipe to a JSON object with the following keys:
"name": the name of this recipe.
"ingredients": a list of dictionaries, with keys "ingredient", mapping to the name of the ingredient, and "amount" which is a string containing the amount of this ingredient needed including the unit, or 
               a null value if no specific amount is given.
               For example, the ingredient "one onion" should yield {{'amount': '1', 'ingredient': 'onion'}}, and the ingredient "zout" should yield {{'amount': null, 'ingredient': 'zout'}}
               and the ingredient "1el Komijn" should yield {{'amount': '1 el', 'ingredient': 'Komijn'}}, and "400gr tomaat" should yield {{'amount': '400 gr', 'ingredient': 'tomaat'}}
               and "packet of noodles" should yield {{'amount': '1 packet', 'ingredient': 'noodles'}}. If no amount is specified in a separate ingredients section,
               infer the "amount" from the recipe if it is mentioned there.
"preparation": a list of strings containing the steps of the recipe. Split the steps from the original recipe up into multiple steps
               if they are more than 2 or 3 sentences.
"nutrition": null if there is no nutritional information in the recipe, or a list of dictionaries containing the keys "group", with the type
of nutrional information, and "amount": with the amount of this group that is contained in the recipe, as a string including the unit, so
"Fats 12gr" should yield {{'group': 'fats', 'amount': '12 gr'}}.
"people": the amount of people that can be fed from this meal as an integer, in case this information is present, otherwise null
"time": the time that this recipe takes to make in minutes as an integer, in case this information is present, otherwise null

Keep the language the same, and do not change anything about the text in the recipe at all.
Only output the JSON object, and nothing else. You can do this!
Here comes the text:

{text}
"""

META_PROMPT = f"""
For this recipe, generate a JSON object containing meta information that classifies the recipe.
It should contain the following keys and values:
"language": One of {LANGUAGES}, depending on the language of the recipe.
"meal_type": One of {MEAL_TYPES} that best describes the meal.
"meat_type": A list of at most two of {MEAT_TYPES} that best describe the meal. Note that it is impossible for a recipe
             to be both vegetarian and contain meat, and that "other" should never go with another meat type.
"carb_type": A list of at most two of {CARB_TYPES} that best describe the meal. Note that it is impossible for a recipe
             to be have both "none" or "other" and any other carb type.
"cuisine": One of {CUISINE_TYPES} that best describes the meal.
"temperature": One of {TEMPERATURE_TYPES} that best describes the meal.

Please output only the JSON object and nothing else. You can do this!
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

    return recipe


def fix_meta(_meta):
    def _get_or(key, default=None, allowed_values=None):
        if allowed_values is not None:
            if _meta.get(key) in allowed_values:
                return _meta.get(key)
            return default
        else:
            return _meta.get(key, default=default)

    meta = {}
    meta["language"] = _get_or("language", allowed_values=LANGUAGES)
    meta["meal_type"] = _get_or("meal_type", default="other", allowed_values=MEAL_TYPES)
    meta["meat_type"] = []
    for meat_type in _meta.get("meat_type", []):
        if meat_type in MEAT_TYPES:
            meta["meat_type"].append(meat_type)
        if len(meta["meat_type"]) >= 2:
            break
    if not meta["meat_type"]:
        meta["meat_type"] = ["other"]

    meta["carb_type"] = []
    for carb_type in _meta.get("carb_type", []):
        if carb_type in CARB_TYPES:
            meta["carb_type"].append(carb_type)
        if len(meta["carb_type"]) >= 2:
            break
    if not meta["carb_type"]:
        meta["carb_type"] = ["other"]

    meta["cuisine"] = _get_or("cuisine", default="other", allowed_values=CUISINE_TYPES)
    meta["temperature"] = _get_or("temperature", allowed_values=TEMPERATURE_TYPES)
    return meta


def _get_tiktok_text(soup):
    data = soup.find("script", {"id": "__UNIVERSAL_DATA_FOR_REHYDRATION__"})
    json_data = json.loads(data.contents[0])
    return json_data["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"]["itemStruct"]["desc"]


def _get_instagram_text(soup):
    meta = soup.find("meta", {"property": "og:title"})
    if meta:
        return meta["content"]
    return _get_html_text(soup)


def _get_html_text(soup):
    # remove comment sections from website
    COMMENTS = ["comment", "opmerking"]
    for attr in ["class", "id"]:
        for element in soup.find_all(attrs={attr: re.compile(fr".*({'|'.join(COMMENTS)}).*", flags=re.IGNORECASE)}):
            element.decompose()

    text = re.sub(r"(\n\s*)+", "\n", soup.get_text(separator=" ", strip=True))
    return text


async def translate_url(url):
    print(f"Retrieving url {url}")
    async with aiohttp.ClientSession(headers=_get_headers(url)) as session:
        res = await session.get(url)
        if not res.ok:
            raise CookbookError(f"Could not get the specified url, status code {res.status}")
        soup = BeautifulSoup(await res.text(), features="html.parser")
        domain = tld.extract(url).domain.lower()
        if domain == "tiktok":
            text = _get_tiktok_text(soup)
        elif domain in {"instagram", "ig", "cdninstagram"}:
            text = _get_instagram_text(soup)
        else:
            text = _get_html_text(soup)
        recipe = await translate_page(text, url=url, thumbnail=get_thumbnail(soup))
        return recipe


async def _chatgpt_json_and_fix(messages, fix, temperature=0.7, **kwargs):
    for i in range(1 + MAX_RETRIES):
        try:
            chat_completion = await client.chat.completions.create(
                model=MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=temperature,
                **kwargs
            )
        except openai.BadRequestError as e:
            if e.code == "context_length_exceeded":
                raise
            raise
        reply = chat_completion.choices[0].message.content
        try:
            return reply, fix(json.loads(reply))
        except json.JSONDecodeError:
            print("Conversion failed, retrying")
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content": "this is not a parsable json object, "
                                                        "output only the json object"})
    raise CookbookError("ChatGPT did not return a parsable json object, please try again")


async def translate_page(text, url=None, thumbnail=None):
    print(f"Converting with ChatGPT ({MODEL})")
    messages = [
        {"role": "system", "content": "You are a helpful AI cook that converts recipes into JSON objects."},
        {"role": "user", "content": PROMPT.format(text=text)}
    ]

    reply, fixed = await _chatgpt_json_and_fix(messages, fix_recipe, temperature=0.7)
    messages.append({"role": "assistant", "content": reply})
    messages.append({"role": "user", "content": META_PROMPT})
    try:
        # higher temperature for interpreting the recipe for tags
        _, meta = await _chatgpt_json_and_fix(messages, fix_meta, temperature=0.7)
    except Exception as e:
        meta = {}
    fixed["meta"] = meta

    # add url / thumbnail after the fact, since we want to use as few tokens as possible
    fixed["url"] = url
    fixed["thumbnail"] = thumbnail
    return fixed


if __name__ == '__main__':
    import asyncio
    from pprint import pprint

    recipe = asyncio.run(translate_url("https://www.tiktok.com/t/ZT8VYSJYd/"))
    pprint(recipe)
