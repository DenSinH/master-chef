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


def get_thumbnail(url):
    res = requests.get(url)
    if not res.ok:
        raise Exception(f"Could not get the specified url, status code {res.status_code}")

    # try to find known meta attributes for thumbnails
    soup = BeautifulSoup(res.text, features="html.parser")
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


if __name__ == '__main__':
    thumbnail = get_thumbnail("https://www.ah.nl/allerhande/video/R-V4312248/eenpans-mozzarella-stokbrood-schotel")
    print(thumbnail)
