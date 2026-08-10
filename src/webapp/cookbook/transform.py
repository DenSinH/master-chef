import asyncio
import logging
import os
import re
from typing import TypeVar

import aiohttp
import msgspec.json
import openai
import tldextract as tld
from bs4 import BeautifulSoup
from pydantic import BaseModel

from webapp.cookbook.errors import CookbookError

from .headers import get_headers
from .instagram import get_instagram_recipe
from .recipe import Recipe
from .thumbnail import get_thumbnail

_B = TypeVar("_B", bound="BaseModel")

logger = logging.getLogger(__name__)
client = openai.AsyncOpenAI(
    base_url=os.getenv("OPENAI_URL", "localhost:4000"),
    api_key=os.environ["OPENAI_API_KEY"],
)

MAX_RETRIES = 1
MODEL = os.environ["OPENAI_MODEL"]
DEFAULT_TEMPERATURE = 0.2
PROMPT = """
The following text is from a website, and it contains a recipe, possibly in Dutch, as well as unnecessary other text 
from the webpage.
The recipe contains information on the ingredients, the preparation and possibly nutritional information.
Convert the recipe to a JSON object with the specified schema.
You should NOT change anything about the recipe, EXCEPT if the language is not Dutch or English, in which
case, please translate it to English.
Do not change ANYTHING else about the text in the recipe at all.
Only output the JSON object, and nothing else. You can do this!
Here comes the text:

{text}
"""


def _get_tiktok_text(soup: BeautifulSoup):
    """Get description of tiktok page. We cannot use simple scraping, since the
    caption is loaded lazily."""
    data = soup.find("script", {"id": "__UNIVERSAL_DATA_FOR_REHYDRATION__"})
    json_data = msgspec.json.decode(data.contents[0], strict=False)
    return json_data["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"][
        "itemStruct"
    ]["desc"]


def _get_text(soup: BeautifulSoup):
    """Get text from soup. We remove any unnecessary spacing."""
    return re.sub(r"(\n\s*)+", "\n", soup.get_text(separator=" ", strip=True))


def _get_html_text(soup: BeautifulSoup):
    """Get text from html page
    First, we try to just get all the text. If this is too long,
    we attempt to strip away any 'small' comment sections."""
    text = _get_text(soup)

    # text is "short enough", do not remove comments
    if len(text) < 8000:
        return text

    # get initial text length
    text_length = len(text)

    # remove comment sections from website
    COMMENTS = ["comment", "opmerking"]
    COMMENTS_RE = re.compile(rf".*({'|'.join(COMMENTS)}).*", flags=re.IGNORECASE)
    for attr in ["class", "id"]:
        for element in soup.find_all(attrs={attr: COMMENTS_RE}):
            # only remove "small" text sections
            if len(_get_text(element)) < 0.1 * text_length:
                element.decompose()

    # return reduced text
    text = _get_text(soup)
    return text


async def translate_url(url: str, user_agent=None) -> Recipe:
    """Transform a recipe from a url, determining the thumbnail automatically"""
    logger.info(f"Retrieving url {url}")
    domain = tld.extract(url).domain.lower()
    if domain in {"instagram", "ig", "cdninstagram"}:
        # instagram must be handled separately
        text = await get_instagram_recipe(url, user_agent=user_agent)
        thumbnail = None
    else:
        async with aiohttp.ClientSession(
            headers=get_headers(url, user_agent=user_agent)
        ) as session:
            res = await session.get(url)
            if not res.ok:
                headers = "\n".join(
                    f"{header}: {value}" for header, value in res.headers.items()
                )
                msg = f"Could not get the specified url, status code {res.status}\n{headers}"
                raise CookbookError(msg)

            soup = BeautifulSoup(await res.text(), features="html.parser")
            if domain == "tiktok":
                text = _get_tiktok_text(soup)
            else:
                text = _get_html_text(soup)
            thumbnail = get_thumbnail(soup)

    recipe = await translate_page(
        text,
        url=url,
        thumbnail=thumbnail,
    )
    return recipe


async def _chatgpt_json_and_fix(
    model: type[_B],
    messages,
    temperature=DEFAULT_TEMPERATURE,
    **kwargs,
) -> _B:
    """Send message to chatgpt, and load object of type 'model' from the response.
    'model' should be a subclass of BaseModel"""

    # we may do a multi-shot recipe conversion if chatgpt
    # fails the first time around
    for i in range(1 + MAX_RETRIES):
        logger.info(f"ChatGPT message attempt {i + 1}")
        try:
            response = await client.responses.parse(
                model=MODEL,
                input=messages,
                text_format=model,
                temperature=temperature,
                extra_body={
                    # dum-dum, no need to think
                    "think": False,
                },
                **kwargs,
            )
        except openai.BadRequestError as e:
            if e.code == "context_length_exceeded":
                raise
            raise
        except asyncio.exceptions.CancelledError:
            # retry because timeout, use longer timeout
            kwargs["timeout"] = kwargs.get("timeout", 60) * 2
            continue

        return response.output_parsed
    raise CookbookError(
        "ChatGPT did not return a parsable json object, please try again"
    )


async def translate_page(text: str, url=None, thumbnail=None) -> Recipe:
    """Tranform a recipe from text, filling in the url and thumbnail
    fields from the given parameters"""
    logger.info(f"Converting with ChatGPT ({MODEL})")
    messages = [
        {
            "role": "system",
            "content": "You are a helpful AI cook that converts recipes into JSON objects.",
        },
        {"role": "user", "content": PROMPT.format(text=text)},
    ]

    recipe = await _chatgpt_json_and_fix(
        Recipe, messages, temperature=DEFAULT_TEMPERATURE
    )
    return recipe.model_copy(
        update={
            "url": url,
            "thumbnail": thumbnail,
        }
    )
