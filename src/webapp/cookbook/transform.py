import asyncio
import logging
import os
import re

import aiohttp
import msgspec.json
import openai
import tldextract as tld
from bs4 import BeautifulSoup

from webapp.cookbook.errors import CookbookError

from .headers import get_headers
from .instagram import get_instagram_recipe
from .recipe import Recipe, RecipeBase
from .thumbnail import get_thumbnail

logger = logging.getLogger(__name__)
client = openai.AsyncOpenAI(
    base_url=os.getenv("OPENAI_URL", "localhost:4000"),
    api_key=os.environ["OPENAI_API_KEY"],
)

MAX_RETRIES = 1
MODEL = os.environ["OPENAI_MODEL"]
DEFAULT_TEMPERATURE = 0.1
SYSTEM_PROMPT = """
Extract the recipe from the provided webpage text.
Preserve the recipe exactly as written. Do not invent, omit, summarize,
or modify ingredients, quantities, instructions, or nutritional information.
If a step, ingredient, or nutritional value is missing, unclear, or cut off
in the source text, leave it out rather than guessing or completing it -
an incomplete but accurate list is correct; a complete-looking list that
includes anything you inferred is wrong.
If no steps are provided, or no nutritional information is given, just leave it an empty list.
If the recipe is neither Dutch nor English, translate the recipe content
to English.
Ignore advertisements, navigation, comments, and unrelated webpage text.
Do NOT make up anything, simply copy the recipe and the steps present in the webpage (if present).
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


async def get_recipe_text(url: str, user_agent=None) -> tuple[str, str | None]:
    """Retrieve the raw recipe text and thumbnail for a url. This is the
    "fast" part of translating a url, i.e. it does not involve calling
    ChatGPT, and is expected to fail quickly (e.g. if the url cannot be
    reached) rather than taking a long time."""
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

    return text, thumbnail


async def translate_page_stream(text: str, url=None, thumbnail=None):
    """Like `translate_page`, but yields the raw JSON text as ChatGPT streams
    it back, piece by piece, so the frontend can show live progress (this
    also serves as a heartbeat, keeping the underlying connection alive
    during slow ChatGPT responses). The final yielded value is always the
    resulting Recipe, unless translation failed, in which case the original
    exception is raised."""
    logger.info(f"Converting with ChatGPT ({MODEL})")
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {"role": "user", "content": text},
    ]

    kwargs: dict = {}
    for i in range(1 + MAX_RETRIES):
        logger.info(f"ChatGPT message attempt {i + 1}")
        try:
            async with client.responses.stream(
                model=MODEL,
                input=messages,
                text_format=RecipeBase,
                temperature=DEFAULT_TEMPERATURE,
                extra_body={
                    # dum-dum, no need to think
                    "think": False,
                },
                **kwargs,
            ) as stream:
                async for event in stream:
                    if event.type == "response.output_text.delta":
                        yield event.delta
                final_response = await stream.get_final_response()
            recipe_base: RecipeBase = final_response.output_parsed  # type: ignore
            recipe = Recipe.model_validate(recipe_base.model_dump())
            recipe.url = url
            recipe.thumbnail = thumbnail
            break
        except asyncio.exceptions.CancelledError:
            # retry because timeout, use longer timeout
            kwargs["timeout"] = kwargs.get("timeout", 60) * 2
    else:
        raise CookbookError(
            "ChatGPT did not return a parsable json object, please try again"
        )

    yield recipe.model_copy(
        update={
            "url": url,
            "thumbnail": thumbnail,
        }
    )
