import instagrapi
import tempfile
import aiohttp
import aiofiles
import tempfile
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

from .utils import InstagramError, get_headers


_CLIENT = instagrapi.Client()

def _get_client() -> instagrapi.Client:
    """ Get (logged in) Instagram client """
    _CLIENT.login(
        os.environ["INSTAGRAM_USER"],
        os.environ["INSTAGRAM_PASS"],
        relogin=False
    )
    return _CLIENT



def get_instagram_recipe(url):
    """ Get recipe from Instagram media caption,
    as well as the thumbnail url """
    client = _get_client()
    media_pk = client.media_pk_from_url(url)
    media = client.media_info(media_pk)
    return media.caption_text, str(media.thumbnail_url)


async def _download_image(url: str, callback: callable, user_agent=None):
    """ Helper function to download an image from a URL,
    save it to a temporary path and call a callback on it """
    # Check if the URL ends with .jpg or .jpeg
    if not url.lower().endswith(('.jpg', '.jpeg')):
        raise InstagramError(f"Instagram post image URL does not point to a .jpg or .jpeg image: '{url}'")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers(url=url, user_agent=user_agent)) as response:
            if not response.ok:
                raise InstagramError(f"Failed to download image. HTTP status code: {response.status}")
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode="wb", suffix='.jpg') as jpg:
                jpg.write(await response.read())
                return callback(Path(jpg.name))


async def post_instagram_recipe(recipe_name, image_url, user_agent=None):
    """ Post the image from image_url to the Instagram account
    from the environment credentials. """
    def _upload_from_path(path: Path):
        print(f"Uploading from {path}")
        client = _get_client()
        media = client.photo_upload(
            path,
            recipe_name
        )
        return media.code

    return await _download_image(image_url, _upload_from_path, user_agent=user_agent)


if __name__ == '__main__':
    # install instagrapi, Pillow
    url = "https://www.instagram.com/reel/C8KpFGsoKC3/?igsh=aDdhdGRxc25qcmZk"
    get_instagram_recipe(url)
