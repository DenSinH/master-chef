import openai
import aiohttp
from bs4 import BeautifulSoup
import tldextract as tld
import dataclasses
from dotenv import load_dotenv

load_dotenv()

import os
import re
import msgspec

from .utils import *
from .meta import *
from .recipe import Recipe, RecipeMeta, Fixable
from .instagram import get_instagram_recipe
from .thumbnail import get_thumbnail


client = openai.AsyncOpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)


MAX_RETRIES = 1
MODEL = "gpt-4o"
PROMPT = """
The following text is from a website, and it contains a recipe, possibly in Dutch, as well as unnecessary other text from the webpage.
The recipe contains information on the ingredients, the preparation and possibly nutritional information.
Convert the recipe to a JSON object with the following keys:
"name": the name of this recipe.
"ingredients": a list of dictionaries, with keys "ingredient", mapping to the name of the ingredient, and "amount" which is a string containing the amount of this ingredient needed including the unit, or 
               a null value if no specific amount is given.
               For example, the ingredient "one onion" should yield {{'amount': '1', 'ingredient': 'onion'}}, and the ingredient "zout" should yield {{'amount': null, 'ingredient': 'zout'}}
               and the ingredient "1el Komijn" should yield {{'amount': '1el', 'ingredient': 'Komijn'}}, and "400gr tomaat" should yield {{'amount': '400gr', 'ingredient': 'tomaat'}}
               and "packet of noodles" should yield {{'amount': '1 packet', 'ingredient': 'noodles'}}.
               In case there are multiple 'sections' of ingredients, insert an ingredient object with 'ingredient' value '#name of section'. For
               example, if there is a section of ingredients for the sauce, insert {{ 'amount': null, 'ingredient': '#For the sauce' }}.
               So for example, Chicken marinade: - 10g cumin - one onion should yield [{{'amount': null, 'ingredient': '#Chicken marinade:'}}, {{'amount': '10g', 'ingredient': 'cumin'}}, {{'amount': 'one', 'ingredient': 'onion'}}]
"preparation": a list of strings containing the steps of the recipe. Split the steps from the original recipe up into multiple steps
               if they are more than 2 or 3 sentences. If there are sections, insert steps with the value '#name of section'.
               For example, if there are steps for making rice, insert a step '#For the rice'. 
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


def _get_tiktok_text(soup: BeautifulSoup):
    """ Get description of tiktok page 
    We cannot use simple scraping, since the 
    caption is loaded lazily. """
    data = soup.find("script", {"id": "__UNIVERSAL_DATA_FOR_REHYDRATION__"})
    json_data = msgspec.json.decode(data.contents[0], strict=False)
    return json_data["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"]["itemStruct"]["desc"]


def _get_text(soup: BeautifulSoup):
    """ Get text from soup. We remove any unnecessary spacing. """
    return re.sub(r"(\n\s*)+", "\n", soup.get_text(separator=" ", strip=True))


def _get_html_text(soup: BeautifulSoup):
    """ Get text from html page
    First, we try to just get all the text. If this is too long,
    we attempt to strip away any 'small' comment sections. """
    text = _get_text(soup)
    
    # text is "short enough", do not remove comments
    if len(text) < 8000:
        return text
    
    # get initial text length
    text_length = len(text)
    
    # remove comment sections from website
    COMMENTS = ["comment", "opmerking"]
    for attr in ["class", "id"]:
        for element in soup.find_all(attrs={attr: re.compile(fr".*({'|'.join(COMMENTS)}).*", flags=re.IGNORECASE)}):
            # only remove "small" text sections
            if len(_get_text(element)) < 0.1 * text_length:
                element.decompose()
    
    # return reduced text
    text = _get_text(soup)
    return text


async def translate_url(url, user_agent=None) -> Recipe:
    """ Transform a recipe from a url, determining
    the thumbnail automatically """
    print(f"Retrieving url {url}")
    domain = tld.extract(url).domain.lower()
    if domain in {"instagram", "ig", "cdninstagram"}:
        # instagram must be handled separately
        text, thumbnail = get_instagram_recipe(url)
    else:
        async with aiohttp.ClientSession(headers=get_headers(url, user_agent=user_agent)) as session:
            res = await session.get(url)
            if not res.ok:
                headers = "\n".join(f"{header}: {value}" for header, value in res.headers.items())
                message = f"Could not get the specified url, status code {res.status}\n" + headers
                raise CookbookError(message)
            soup = BeautifulSoup(await res.text(), features="html.parser")
            if domain == "tiktok":
                text = _get_tiktok_text(soup)
            else:
                text = _get_html_text(soup)
            thumbnail = get_thumbnail(soup)

    recipe = await translate_page(text, url=url, thumbnail=thumbnail)
    return recipe


async def _chatgpt_json_and_fix(cls, messages, temperature=0.7, **kwargs):
    """ Send message to chatgpt, and load object of type 'cls'
    from the response. 'cls' should be a subclass of Fixable """
    assert issubclass(cls, Fixable)

    # we may do a multi-shot recipe conversion if chatgpt
    # fails the first time around
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
            return reply, cls.from_data(**msgspec.json.decode(reply, strict=False))
        except msgspec.DecodeError:
            print("Conversion failed, retrying")
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content": "this is not a parsable json object, "
                                                        "output only the json object"})
    raise CookbookError("ChatGPT did not return a parsable json object, please try again")


async def translate_page(text, url=None, thumbnail=None) -> Recipe:
    """ Tranform a recipe from text, filling in the url and thumbnail
    fields from the given parameters """
    print(f"Converting with ChatGPT ({MODEL})")
    messages = [
        {"role": "system", "content": "You are a helpful AI cook that converts recipes into JSON objects."},
        {"role": "user", "content": PROMPT.format(text=text)}
    ]

    reply, fixed = await _chatgpt_json_and_fix(Recipe, messages, temperature=0.7)
    messages.append({"role": "assistant", "content": reply})
    messages.append({"role": "user", "content": META_PROMPT})
    try:
        # higher temperature for interpreting the recipe for tags
        _, meta = await _chatgpt_json_and_fix(RecipeMeta, messages, temperature=0.7)
    except Exception as e:
        meta = {}

    # update meta and predetermined values
    # add url / thumbnail after the fact, since we 
    # want to use as few tokens as possible
    fixed = dataclasses.replace(
        fixed,
        meta=meta,
        url=url,
        thumbnail=thumbnail
    )
    return fixed


if __name__ == '__main__':
    import asyncio
    from pprint import pprint

    recipe = asyncio.run(translate_url("https://www.tiktok.com/t/ZT8VYSJYd/"))
    pprint(recipe)
