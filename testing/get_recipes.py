import aiohttp
from bs4 import BeautifulSoup
import tldextract as tld
import re
import random


def _get_headers(url, user_agent=None):
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
        headers["User-Agent"] = user_agent or random.choice(_USER_AGENTS)
    return headers


def _get_text(soup: BeautifulSoup):
    return re.sub(r"(\n\s*)+", "\n", soup.get_text(separator=" ", strip=True))


def _get_html_text(soup: BeautifulSoup):
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
    
    text = _get_text(soup)
    return text


async def translate_url(url, user_agent=None):
    print(f"Retrieving url {url}")
    domain = tld.extract(url).domain.lower()
    async with aiohttp.ClientSession(headers=_get_headers(url, user_agent=user_agent)) as session:
        res = await session.get(url)
        if not res.ok:
            headers = "\n".join(f"{header}: {value}" for header, value in res.headers.items())
            message = f"Could not get the specified url, status code {res.status}\n" + headers
            raise Exception(message)
        soup = BeautifulSoup(await res.text(), features="html.parser")
        text = _get_html_text(soup)
        print(text)


if __name__ == "__main__":
    url = "https://www.thegoodbite.co.uk/recipes/one-pan-cajun-lime-chicken/"
    import asyncio
    asyncio.run(translate_url(url))