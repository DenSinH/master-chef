import instagrapi
import instagrapi.exceptions
import tempfile
import aiohttp
import aiofiles
import tempfile
from pathlib import Path
import os

from .utils import InstagramError, get_headers


_CLIENT = instagrapi.Client()
_PERSIST_DIR = os.getenv("PERSIST_DIR")


def _get_settings_file() -> Path:
    if _PERSIST_DIR is not None:
        if not os.path.exists(_PERSIST_DIR):
            os.makedirs(_PERSIST_DIR, exist_ok=True)
        return Path(_PERSIST_DIR) / "instagram-session.json"
    return "instagram-session.json"


def _login(dump_settings=False) -> bool:
    """ Do login with global client """
    logged_in = _CLIENT.login(
        os.environ["INSTAGRAM_USER"],
        os.environ["INSTAGRAM_PASS"],
        relogin=False
    )
    if logged_in and dump_settings:
        _CLIENT.dump_settings(_get_settings_file())

    return logged_in



def _get_client() -> instagrapi.Client:
    """ Get (logged in) Instagram client """
    settings_file = _get_settings_file()
    if not os.path.exists(settings_file):
        print("No instagram session found, logging in with username / password")
        _login(dump_settings=True)
        return _CLIENT

    print("Loading instagram session")
    session = _CLIENT.load_settings(settings_file)

    if session:
        try:
            print("Logging in from session")
            _CLIENT.set_settings(session)
            _login()

            # check if session is valid
            try:
                _CLIENT.get_timeline_feed()
                return _CLIENT
            except instagrapi.exceptions.LoginRequired:
                print("Session is invalid, need to login via username and password")

            old_session = _CLIENT.get_settings()

            # use the same device uuids across logins
            _CLIENT.set_settings({})
            _CLIENT.set_uuids(old_session["uuids"])

            if _login(dump_settings=True):
                # another session test
                _CLIENT.get_timeline_feed()
                return _CLIENT
                
        except Exception as e:
            print(f"Couldn't login user using session information: {e}")

    try:
        print("Attempting to login via username and password.")
        if _login(dump_settings=True):
            return _CLIENT
    except Exception as e:
        raise InstagramError(f"Couldn't login user with either password or session: {e}")


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
