import aiograpi
import aiograpi.exceptions
import aiohttp
import aiofiles.os
import aiofiles.tempfile
from PIL import Image
from io import BytesIO
from pathlib import Path
import os
import logging

from .utils import InstagramError, get_headers

logger = logging.getLogger(__name__)


_CLIENT = aiograpi.Client()
_PERSIST_DIR = os.getenv("PERSIST_DIR")


async def _get_settings_file() -> Path:
    if _PERSIST_DIR is not None:
        if not await aiofiles.os.path.exists(_PERSIST_DIR):
            await aiofiles.os.makedirs(_PERSIST_DIR, exist_ok=True)
        return Path(_PERSIST_DIR) / "instagram-session.json"
    return "instagram-session.json"


async def _login(dump_settings=False) -> bool:
    """ Do login with global client """
    logged_in = await _CLIENT.login(
        os.environ["INSTAGRAM_USER"],
        os.environ["INSTAGRAM_PASS"],
        relogin=False
    )
    if logged_in and dump_settings:
        _CLIENT.dump_settings(await _get_settings_file())

    return logged_in



async def _get_client() -> aiograpi.Client:
    """ Get (logged in) Instagram client """
    settings_file = await _get_settings_file()
    if not os.path.exists(settings_file):
        logger.info("No instagram session found, logging in with username / password")
        await _login(dump_settings=True)
        return _CLIENT

    logger.info("Loading instagram session")
    session = _CLIENT.load_settings(settings_file)

    if session:
        try:
            logger.info("Logging in from session")
            _CLIENT.set_settings(session)
            await _login()

            # check if session is valid
            try:
                await _CLIENT.get_timeline_feed()
                return _CLIENT
            except aiograpi.exceptions.LoginRequired:
                logger.warn("Session is invalid, need to login via username and password")

            old_session = _CLIENT.get_settings()

            # use the same device uuids across logins
            _CLIENT.set_settings({})
            _CLIENT.set_uuids(old_session["uuids"])

            if await _login(dump_settings=True):
                # another session test
                await _CLIENT.get_timeline_feed()
                return _CLIENT
                
        except Exception as e:
            logger.warn(f"Couldn't login user using session information: {e}")

    try:
        logger.info("Attempting to login via username and password.")
        if await _login(dump_settings=True):
            return _CLIENT
    except Exception as e:
        raise InstagramError(f"Couldn't login user with either password or session: {e}")


async def get_instagram_recipe(url):
    """ Get recipe from Instagram media caption,
    as well as the thumbnail url """
    client = await _get_client()
    media_pk = await client.media_pk_from_url(url)
    media = await client.media_info(media_pk)
    return media.caption_text, str(media.thumbnail_url)


async def _download_image(url: str, callback: callable, user_agent=None):
    """ Helper function to download an image from a URL,
    save it to a temporary path and call a callback on it """
    # Check if the URL ends with .jpg or .jpeg
    url_path = Path(url)
    if url_path.suffix.lower() not in {".jpg", ".jpeg", ".webp", ".png", ".avif"}:
        raise InstagramError(f"Instagram post image URL does not point to an image file: '{url}'")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_headers(url=url, user_agent=user_agent)) as response:
            if not response.ok:
                raise InstagramError(f"Failed to download image. HTTP status code: {response.status}")
            
            # Create a temporary file
            try:
                async with aiofiles.tempfile.NamedTemporaryFile(mode="wb", suffix="jpg", delete=False) as img:
                    img_name = Path(img.name)
                    image_data = Image.open(BytesIO(await response.read())).convert("RGB")
                    jpg = BytesIO()
                    image_data.save(jpg, format="jpeg", quality=95, optimize=True)
                    jpg.seek(0)
                    await img.write(await jpg.read())
                return await callback(img_name)
            finally:
                await aiofiles.os.remove(img_name)


async def post_instagram_recipe(recipe_name, image_url, user_agent=None):
    """ Post the image from image_url to the Instagram account
    from the environment credentials. """
    async def _upload_from_path(path: Path):
        logger.info(f"Uploading from {path}")
        client = await _get_client()
        media = await client.photo_upload(
            path,
            recipe_name
        )
        return media.code

    return await _download_image(image_url, _upload_from_path, user_agent=user_agent)


if __name__ == '__main__':
    # install instagrapi, Pillow
    url = "https://www.instagram.com/reel/C8KpFGsoKC3/?igsh=aDdhdGRxc25qcmZk"
    get_instagram_recipe(url)
