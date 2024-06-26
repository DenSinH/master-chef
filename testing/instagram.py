import instagrapi
import os
from dotenv import load_dotenv

load_dotenv()


def get_instagram_description(url):
    client = instagrapi.Client()
    client.login(
        os.environ["INSTAGRAM_USER"],
        os.environ["INSTAGRAM_PASS"]
    )
    media_pk = client.media_pk_from_url(url)
    media = client.media_info(media_pk)
    print(media)
    print(media.model_dump())


if __name__ == '__main__':
    # install instagrapi, Pillow
    url = "https://www.instagram.com/reel/C8KpFGsoKC3/?igsh=aDdhdGRxc25qcmZk"
    get_instagram_description(url)
