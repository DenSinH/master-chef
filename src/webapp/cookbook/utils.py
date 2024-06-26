import random
import tldextract as tld


class CookbookError(Exception):
    pass


class InstagramError(CookbookError):
    pass


def get_headers(url, user_agent=None):
    """ Get headers for requesting 'url', with a default
        user-agent header passed """
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
