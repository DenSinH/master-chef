import requests
from bs4 import BeautifulSoup


def get_thumbnail(url):
    res = requests.get(url)
    if not res.ok:
        raise Exception(f"Could not get the specified url, status code {res.status_code}")
    soup = BeautifulSoup(res.text, features="html.parser")
    image = soup.find("meta", {"property": "og:image"})
    return image["content"] if image else None


if __name__ == '__main__':
    from pprint import pprint

    thumbnail = get_thumbnail("https://15gram.be/recepten/wraps-kip-tikka-masala")
    print(thumbnail)
