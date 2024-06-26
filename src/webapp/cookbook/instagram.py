import instagrapi
import os
from dotenv import load_dotenv

load_dotenv()

client = instagrapi.Client()

def get_instagram_recipe(url):
    client.login(
        os.environ["INSTAGRAM_USER"],
        os.environ["INSTAGRAM_PASS"],
        relogin=False
    )
    media_pk = client.media_pk_from_url(url)
    media = client.media_info(media_pk)
    return media.caption_text, str(media.thumbnail_url)


if __name__ == '__main__':
    # install instagrapi, Pillow
    url = "https://www.instagram.com/reel/C8KpFGsoKC3/?igsh=aDdhdGRxc25qcmZk"
    get_instagram_recipe(url)
