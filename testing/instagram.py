import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import random
import tldextract as tld


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


async def translate_url(url):
    print(f"Retrieving url {url}")
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False), headers=_get_headers(url)) as session:
        res = await session.get(url)
        if not res.ok:
            raise Exception(f"Could not get the specified url, status code {res.status}")
        soup = BeautifulSoup(await res.text(), features="html.parser")

        # remove comment sections from website
        print(soup.text)
        COMMENTS = ["comment", "opmerking"]
        for attr in ["class", "id"]:
            for element in soup.find_all(attrs={attr: re.compile(fr".*({'|'.join(COMMENTS)}).*", flags=re.IGNORECASE)}):
                element.decompose()

        text = re.sub(r"(\n\s*)+", "\n", soup.text)
        print(text)


if __name__ == '__main__':
    url = "https://www.instagram.com/reel/C04TLH4o-Yc/?igshid=MTdlMjRlYjZlMQ%3D%3D"
    asyncio.run(translate_url(url))