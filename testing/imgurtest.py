from pyimgur import Imgur
from dotenv import load_dotenv
import os
from pprint import pprint

load_dotenv()

# If you already have an access/refresh pair in hand
client_id = os.environ["IMGUR_CLIENT_ID"]
client_secret = os.environ["IMGUR_CLIENT_SECRET"]
refresh_token = os.environ["IMGUR_REFRESH_TOKEN"]
album_id = os.environ["IMGUR_ALBUM_ID"]

if __name__ == '__main__':
    client = Imgur(client_id, client_secret, access_token="test", refresh_token=refresh_token)
    client.refresh_access_token()

    # res = client.create_album("Recipes", "Album for recipe webpage")
    # pprint(res)
    # pprint(res.link)
    # quit(0)
    file = "./images/carpaccio-bommetjes.jpg"
    res = client.upload_image(
        path=file,
        title="Test Image",
        description="Image for testing",
        album=album_id
    )
    pprint(res)
