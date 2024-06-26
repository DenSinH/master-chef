import requests
from bs4 import BeautifulSoup


IMAGE_EXTENSIONS = [
    "jpg",
    "jpeg",
    "png",
    "webp",
    "gif"
]

THUMBNAIL_META_ATTR = [
    {"property": "og:image"},
    {"name": "twitter:image:src"}
]


def get_thumbnail(soup: BeautifulSoup):
    """ Try to find a thumbnail image from an HTML page """
    # try to find known meta attributes for thumbnails
    for attr in THUMBNAIL_META_ATTR:
        image = soup.find("meta", attr)
        if image:
            return image["content"]

    # just try to find any meta tag with an image attached to it
    for meta in soup.find_all("meta"):
        try:
            content = meta["content"].lower()
            if any(content.endswith(ext) for ext in IMAGE_EXTENSIONS):
                return meta["content"]
        except KeyError:
            continue

    return None
