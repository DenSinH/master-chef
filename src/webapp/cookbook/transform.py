import openai
import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

import os
import re
import json

from .utils import *
from .thumbnail import get_thumbnail


openai.api_key = os.environ["OPENAI_API_KEY"]

MAX_RETRIES = 1
MODEL = "gpt-3.5-turbo"
PROMPT = """
The following text is from a website, and it contains a recipe, possibly in Dutch, as well as unnecessary other text from the webpage.
The recipe contains information on the ingredients, the prepration and possibly nutritional information.
Could you convert the recipe to a JSON object with the following keys:
"name": the name of this recipe.
"ingredients": a list of dictionaries, with keys "ingredient", mapping to the name of the ingredient, and "amount" which is a string containing the amount of this ingredient needed including the unit, or null if no specific amount is given.
               For example, the ingredient "one onion" should yield {{'amount': '1', 'ingredient': 'onion'}}, and the ingredient "zout" should yield {{'amount': null, 'ingredient': 'zout'}}.
"preparation": a list of strings containing the steps of the recipe.
"nutrition": null if there is no nutritional information in the recipe, or a list of dictionaries containing the keys "group", with the type
of nutrional information, and "amount": with the amount of this group that is contained in the recipe, as a string including the unit.
"url:": the literal string "{url}"
"people": the amount of people that can be fed from this meal as an integer, in case this information is present, otherwise null
"time": the time that this recipe takes to make in minutes as an integer, in case this information is present, otherwise null
"tags": interpret the recipe, and generate a list of at most 5 English strings that describe this recipe. For example, what the main ingredient is,
        if it takes long or short to make, whether it is especially high or low in certain nutritional groups, tags like that. Make
        sure the strings are in English.
"thumbnail": the literal string "{thumbnail}"

Keep the language the same, except in the tags, and preferably do not change anything about the text in the recipe at all.
Only output the JSON object, and nothing else.
Here comes the text:

{text}
"""

URL_CACHE = {}


async def translate_url(url):
    if url in URL_CACHE:
        return URL_CACHE[url]

    print(f"Retrieving url {url}")
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
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
        URL_CACHE[url] = recipe
        return recipe


async def translate_page(text, url=None, thumbnail=None):
    print(f"Converting with ChatGPT ({MODEL})")
    messages = [
        {"role": "system", "content": "You are a helpful assistant that converts recipies into JSON format."},
        {"role": "user", "content": PROMPT.format(url=url or "", thumbnail=thumbnail or "", text=text)}
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
            return fix_recipe(json.loads(reply))
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
