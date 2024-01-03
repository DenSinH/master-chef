import requests.exceptions
from pyimgur import Imgur

from pyimgur import Imgur, Album, Image
from dotenv import load_dotenv
import os
import base64

load_dotenv()

class ImgurUploadBlob(Imgur):

    def upload_image_blob(self, blob, title=None, description=None, album=None):
        # from upload_image
        image = base64.b64encode(blob)
        payload = {'album_id': album, 'image': image,
                   'title': title, 'description': description}

        resp = self._send_request(self._base_url + "/3/image",
                                  params=payload, method='POST')
        # TEMPORARY HACK:
        # On 5-08-2013 I noticed Imgur now returned enough information from
        # this call to fully populate the Image object. However those variables
        # that matched arguments were always None, even if they had been given.
        # See https://groups.google.com/forum/#!topic/imgur/F3uVb55TMGo
        resp['title'] = title
        resp['description'] = description
        if album is not None:
            resp['album'] = (Album({'id': album}, self, False) if not
            isinstance(album, Album) else album)
        return Image(resp, self)

# If you already have an access/refresh pair in hand
client_id = os.environ["IMGUR_CLIENT_ID"]
client_secret = os.environ["IMGUR_CLIENT_SECRET"]
refresh_token = os.environ["IMGUR_REFRESH_TOKEN"]
album_id = os.environ["IMGUR_ALBUM_ID"]
client = ImgurUploadBlob(client_id, client_secret, refresh_token=refresh_token)


def upload_imgur(filedata, title=None, description=None):
    if client.access_token is None:
        client.refresh_access_token()
    try:
        res = client.upload_image_blob(filedata, title=title, description=description, album=album_id)
    except requests.exceptions.HTTPError as e:
        if e.errno == 403:
            client.refresh_access_token()
            res = client.upload_image_blob(filedata, title=title, description=description, album=album_id)
        else:
            raise
    return res.link
