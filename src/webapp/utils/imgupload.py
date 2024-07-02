from pyimgurasync import Imgur
import os


# If you already have an access/refresh pair in hand
client_id = os.environ["IMGUR_CLIENT_ID"]
client_secret = os.environ["IMGUR_CLIENT_SECRET"]
refresh_token = os.environ["IMGUR_REFRESH_TOKEN"]
album_id = os.environ["IMGUR_ALBUM_ID"]
client = Imgur(client_id, client_secret, refresh_token=refresh_token)


async def upload_imgur(filedata, title=None, description=None):
    res = await client.upload_image_blob(filedata, title=title, description=description, album=album_id, anon=False)
    return res.link
