import requests
from bs4 import BeautifulSoup
import re


if __name__ == '__main__':
    url = "https://www.instagram.com/reel/CvT9vFrq_3e/?igshid=NjIwNzIyMDk2Mg%3D%3D"

    res = requests.get(url)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, features="html.parser")
    text = re.sub(r"(\n\s*)+", "\n", soup.text)
    print(text)