# This file is part of PyImgur.

# PyImgur is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# PyImgur is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with PyImgur.  If not, see <http://www.gnu.org/licenses/>.

"""
PyImgur - The Simple Way of Using Imgur

PyImgur is a python wrapper of the popular image hosting and sharing website
imgur.com. It makes the process of writing applications that uses Imgur faster,
easier and less frustrating by automatically handling a lot of stuff for you.
For instance you'll only need to use your client_id when you instantiate the
Imgur object and when changing authentication. For the REST API this value
needs to be sent with every request, but PyImgur handles this automatically.

Before using PyImgur, or the Imgur REST API in general, you'll need to register
your application here: https://api.imgur.com/oauth2/addclient

For more information on usage visit https://github.com/Damgaard/PyImgur
"""

from base64 import b64encode
import os.path
import re
import aiohttp

from .request import *

__version__ = '0.6.0'

MASHAPE_BASE = "https://imgur-apiv3.p.mashape.com"
IMGUR_BASE = "https://api.imgur.com"

AUTHORIZE_URL = ("{}/oauth2/authorize?"
                 "client_id={}&response_type={}&state={}")
EXCHANGE_URL = "{}/oauth2/token"
REFRESH_URL = "{}/oauth2/token"


class Basic_object(object):
    """Contains basic functionality shared by a lot of PyImgur's classes."""

    def __getattr__(self, attribute):
        if not self._has_fetched:
            self.refresh()
            return getattr(self, attribute)
        raise AttributeError("{0} instance has no attribute '{1}'".format(
            type(self).__name__, attribute))

    def __init__(self, json_dict, imgur, has_fetched=True):
        self._has_fetched = has_fetched
        self._imgur = imgur
        self._populate(json_dict)

    def __repr__(self):
        return "<{0} {1}>".format(type(self).__name__, self.id)

    @property
    def _delete_or_id_hash(self):
        if self._imgur.access_token:
            return self.id
        else:
            return self.deletehash

    def _populate(self, json_dict):
        for key, value in json_dict.items():
            setattr(self, key, value)
        # TODO: ups will need to be likes, because that's what the webinterface
        # is. But we also have "voted" which is the current users vote on it.
        # Update certain attributes for certain objects, to be link to lazily
        # created objects rather than a string of ID or similar.
        if isinstance(self, Album) or isinstance(self, Image):
            if "favorite" in vars(self):
                self.is_favorited = self.favorite
                del self.favorite
            if "nsfw" in vars(self):
                self.is_nsfw = self.nsfw
                del self.nsfw
        if isinstance(self, Image):
            if "animated" in vars(self):
                self.is_animated = self.animated
                del self.animated
            if "link" in vars(self):
                base, sep, ext = self.link.rpartition('.')
                self.link_small_square = base + "s" + sep + ext
                self.link_big_square = base + "b" + sep + ext
                self.link_small_thumbnail = base + "t" + sep + ext
                self.link_medium_thumbnail = base + "m" + sep + ext
                self.link_large_thumbnail = base + "l" + sep + ext
                self.link_huge_thumbnail = base + "h" + sep + ext
        if isinstance(self, Album):
            if "account_url" in vars(self):
                del self.account_url
            if "cover" in vars(self) and self.cover is not None:  # pylint: disable=access-member-before-definition
                self.cover = Image({'id': self.cover}, self._imgur,
                                   has_fetched=False)
            if "images" in vars(self):
                self.images = [Image(img, self._imgur, has_fetched=False) for
                               img in self.images]
            if "images_count" in vars(self):
                del self.images_count
        elif isinstance(self, Comment):
            # Problem with this naming is that children / parent are normal
            # terminology for tree structures such as this. But elsewhere the
            # children are referred to as replies, for instance a comment can
            # be replies to not procreated with. I've decided to use replies
            # and parent_comment as a compromise, where both attributes should
            # be individually obvious but their connection may not.
            if "author_id" in vars(self):
                # author_id is not used for anything, and can also be gotten
                # with comment.author.id which fits with how the id of anything
                # else is gotten. So having it here only complicates the API.
                del self.author_id
            if "children" in vars(self):
                self.replies = [Comment(com, self._imgur) for com in
                                self.children]
                del self.children
            if "comment" in vars(self):
                self.text = self.comment
                del self.comment
            if "deleted" in vars(self):
                self.is_deleted = self.deleted
                del self.deleted
            if "image_id" in vars(self):
                self.permalink = ("http://imgur.com/gallery/{0}/comment/"
                                  "{1}".format(self.image_id, self.id))
                self.image = Image({'id': self.image_id}, self._imgur,
                                   has_fetched=False)
                del self.image_id
            if "parent_id" in vars(self):
                if self.parent_id == 0:  # Top level comment
                    self.parent = None
                else:
                    self.parent = Comment({'id': self.parent_id}, self._imgur,
                                          has_fetched=False)
                del self.parent_id

    async def refresh(self):
        """
        Refresh this objects attributes to the newest values.

        Attributes that weren't added to the object before, due to lazy
        loading, will be added by calling refresh.
        """
        resp = await self._imgur._send_request(self._INFO_URL)
        self._populate(resp)
        self._has_fetched = True
        # NOTE: What if the object has been deleted in the meantime? That might
        # give a pretty cryptic error.


class Album(Basic_object):
    """
    An album is a collection of images.

    :ivar author: The user that authored the album. None if anonymous.
    :ivar cover: The albums cover image.
    :ivar datetime: Time inserted into the gallery, epoch time.
    :ivar deletehash: For anonymous uploads, this is used to delete the album.
    :ivar description: A short description of the album.
    :ivar id: The ID for the album.
    :ivar images: A list of the images in this album. Only set at instantiation
        if created with Imgur.get_album. But even if it isn't set, then you can
        still access the attribute. This will make PyImgur fetch the newest
        version of all attributes for this class, including images. So it will
        work as though images was set all along.
    :ivar is_favorited: Has the logged in user favorited this album?
    :ivar is_nsfw: Is the album Not Safe For Work (contains gore/porn)?
    :ivar layout: The view layout of the album.
    :ivar link: The URL link to the album.
    :ivar public: The privacy level of the album, you can only view public
        albums if not logged in as the album owner.
    :ivar section: ??? - No info in Imgur documentation.
    :ivar title: The album's title
    :ivar views: Total number of views the album has received.
    """

    def __init__(self, json_dict, imgur, has_fetched=True):
        self._INFO_URL = (imgur._base_url + "/3/album/"
                                            "{0}".format(json_dict['id']))
        self.deletehash = None
        super(Album, self).__init__(json_dict, imgur, has_fetched)

    async def add_images(self, images):
        """
        Add images to the album.

        :param images: A list of the images we want to add to the album. Can be
            Image objects, ids or a combination of the two.  Images that you
            cannot add (non-existing or not owned by you) will not cause
            exceptions, but fail silently.
        """
        url = self._imgur._base_url + "/3/album/{0}/add".format(self.id)
        params = {'ids': images}
        return await self._imgur._send_request(url, needs_auth=True, params=params,
                                         method="POST")

    async def delete(self):
        """Delete this album."""
        url = (self._imgur._base_url + "/3/album/"
                                       "{0}".format(self._delete_or_id_hash))
        return await self._imgur._send_request(url, method="DELETE")

    async def favorite(self):
        """
        Favorite the album.

        Favoriting an already favorited album will unfavor it.
        """
        url = self._imgur._base_url + "/3/album/{0}/favorite".format(self.id)
        return await self._imgur._send_request(url, needs_auth=True, method="POST")

    async def remove_images(self, images):
        """
        Remove images from the album.

        :param images: A list of the images we want to remove from the album.
            Can be Image objects, ids or a combination of the two. Images that
            you cannot remove (non-existing, not owned by you or not part of
            album) will not cause exceptions, but fail silently.
        """
        url = (self._imgur._base_url + "/3/album/{0}/"
                                       "remove_images".format(self._delete_or_id_hash))
        # NOTE: Returns True and everything seem to be as it should in testing.
        # Seems most likely to be upstream bug.
        params = {'ids': images}
        return await self._imgur._send_request(url, params=params, method="DELETE")

    async def set_images(self, images):
        """
        Set the images in this album.

        :param images: A list of the images we want the album to contain.
            Can be Image objects, ids or a combination of the two. Images that
            images that you cannot set (non-existing or not owned by you) will
            not cause exceptions, but fail silently.
        """
        url = (self._imgur._base_url + "/3/album/"
                                       "{0}/".format(self._delete_or_id_hash))
        params = {'ids': images}
        return await self._imgur._send_request(url, needs_auth=True, params=params,
                                         method="POST")

    async def update(self, title=None, description=None, images=None, cover=None,
               layout=None, privacy=None):
        """
        Update the album's information.

        Arguments with the value None will retain their old values.

        :param title: The title of the album.
        :param description: A description of the album.
        :param images: A list of the images we want the album to contain.
            Can be Image objects, ids or a combination of the two. Images that
            images that you cannot set (non-existing or not owned by you) will
            not cause exceptions, but fail silently.
        :param privacy: The albums privacy level, can be public, hidden or
            secret.
        :param cover: The id of the cover image.
        :param layout: The way the album is displayed, can be blog, grid,
            horizontal or vertical.
        """
        url = (self._imgur._base_url + "/3/album/"
                                       "{0}".format(self._delete_or_id_hash))
        is_updated = await self._imgur._send_request(url, params=locals(),
                                               method='POST')
        if is_updated:
            self.title = title or self.title
            self.description = description or self.description
            self.layout = layout or self.layout
            self.privacy = privacy or self.privacy
            if cover is not None:
                self.cover = (cover if isinstance(cover, Image)
                              else Image({'id': cover}, self._imgur,
                                         has_fetched=False))
            if images:
                self.images = [img if isinstance(img, Image) else
                               Image({'id': img}, self._imgur, False)
                               for img in images]
        return is_updated


class Comment(Basic_object):
    """
    A comment a user has made.

    Users can comment on Gallery album, Gallery image or other Comments.

    :ivar album_cover: If this Comment is on a Album, this will be the Albums
        cover Image.
    :ivar author: The user that created the comment.
    :ivar datetime: Time inserted into the gallery, epoch time.
    :ivar deletehash: For anonymous uploads, this is used to delete the image.
    :ivar downs: The total number of dislikes (downvotes) the comment has
        received.
    :ivar image: The image the comment belongs to.
    :ivar is_deleted: Has the comment been deleted?
    :ivar on_album: Is the image part of an album.
    :ivar parent: The comment this one has replied to, if it is a top-level
        comment i.e. it's a comment directly to the album / image then it will
        be None.
    :ivar permalink: A permanent link to the comment.
    :ivar points: ups - downs.
    :ivar replies: A list of comment replies to this comment. This variable is
        only available if the comment was returned via Album.get_comments().
        Use get_replies instead to get the replies if this variable is not
        available.
    :ivar text: The comments text.
    :ivar ups: The total number of likes (upvotes) the comment has received.
    :ivar vote: The currently logged in users vote on the comment.
    """

    def __init__(self, json_dict, imgur, has_fetched=True):
        self.deletehash = None
        self._INFO_URL = (imgur._base_url + "/3/comment/"
                                            "{0}".format(json_dict['id']))
        super(Comment, self).__init__(json_dict, imgur, has_fetched)

    async def delete(self):
        """Delete the comment."""
        url = (self._imgur._base_url + "/3/image/"
                                       "{0}".format(self._delete_or_id_hash))
        return await self._imgur._send_request(url, method='DELETE')
        # NOTE: Gives a 403 permission denied error on comment 77087313 which
        # made by me.

    async def downvote(self):
        """Downvote this comment."""
        url = self._imgur._base_url + "/3/comment/{0}/vote/down".format(self.id)
        return await self._imgur._send_request(url, needs_auth=True, method='POST')

    async def get_replies(self):
        """Get the replies to this comment."""
        url = self._imgur._base_url + "/3/comment/{0}/replies".format(self.id)
        json = await self._imgur._send_request(url)
        child_comments = json['children']
        return [Comment(com, self._imgur) for com in child_comments]

    async def reply(self, text):
        """Make a comment reply."""
        url = self._imgur._base_url + "/3/comment/{0}".format(self.id)
        payload = {'image_id': self.image.id, 'comment': text}
        resp = await self._imgur._send_request(url, params=payload, needs_auth=True,
                                         method='POST')
        return Comment(resp, imgur=self._imgur, has_fetched=False)

    async def upvote(self):
        """Upvote this comment."""
        url = self._imgur._base_url + "/3/comment/{0}/vote/up".format(self.id)
        return await self._imgur._send_request(url, needs_auth=True, method='POST')


class Image(Basic_object):
    """
    An image uploaded to Imgur.

    :ivar bandwidth: Bandwidth consumed by the image in bytes.
    :ivar datetime: Time inserted into the gallery, epoch time.
    :ivar deletehash: For anonymous uploads, this is used to delete the image.
    :ivar description: A short description of the image.
    :ivar height: The height of the image in pixels.
    :ivar id: The ID for the image.
    :ivar is_animated: is the image animated?
    :ivar is_favorited: Has the logged in user favorited this album?
    :ivar is_nsfw: Is the image Not Safe For Work (contains gore/porn)?
    :ivar link: The URL link to the image.
    :ivar link_big_square: The URL to a big square thumbnail of the image.
    :ivar link_huge_thumbnail: The URL to a huge thumbnail of the image.
    :ivar link_large_square: The URL to a large square thumbnail of the image.
    :ivar link_large_thumbnail: The URL to a large thumbnail of the image.
    :ivar link_medium_thumbnail: The URL to a medium thumbnail of the image.
    :ivar link_small_square: The URL to a small square thumbnail of the image.
    :ivar section: ??? - No info in Imgur documentation.
    :ivar size: The size of the image in bytes.
    :ivar title: The albums title.
    :ivar views: Total number of views the album has received.
    :ivar width: The width of the image in bytes.
    """

    def __init__(self, json_dict, imgur, has_fetched=True):
        self._INFO_URL = (imgur._base_url + "/3/image/"
                                            "{0}".format(json_dict['id']))
        self.deletehash = None
        super(Image, self).__init__(json_dict, imgur, has_fetched)

    async def delete(self):
        """Delete the image."""
        url = (self._imgur._base_url + "/3/image/"
                                       "{0}".format(self._delete_or_id_hash))
        return await self._imgur._send_request(url, method='DELETE')

    async def download(self, path='', name=None, overwrite=False, size=None):
        """
        Download the image.

        :param path: The image will be downloaded to the folder specified at
            path, if path is None (default) then the current working directory
            will be used.
        :param name: The name the image will be stored as (not including file
            extension). If name is None, then the title of the image will be
            used. If the image doesn't have a title, it's id will be used. Note
            that if the name given by name or title is an invalid filename,
            then the hash will be used as the name instead.
        :param overwrite: If True overwrite already existing file with the same
            name as what we want to save the file as.
        :param size: Instead of downloading the image in it's original size, we
            can choose to instead download a thumbnail of it. Options are
            'small_square', 'big_square', 'small_thumbnail',
            'medium_thumbnail', 'large_thumbnail' or 'huge_thumbnail'.

        :returns: Name of the new file.
        """

        async def save_as(filename):
            local_path = os.path.join(path, filename)
            if os.path.exists(local_path) and not overwrite:
                raise Exception("Trying to save as {0}, but file "
                                "already exists.".format(local_path))
            with open(local_path, 'wb') as out_file:
                out_file.write(await resp.content.read())
            return local_path

        valid_sizes = {'small_square': 's', 'big_square': 'b',
                       'small_thumbnail': 't', 'medium_thumbnail': 'm',
                       'large_thumbnail': 'l', 'huge_thumbnail': 'h'}
        if size is not None:
            size = size.lower().replace(' ', '_')
            if size not in valid_sizes:
                raise LookupError('Invalid size. Valid options are: {0}'.format(
                    ", ".join(valid_sizes.keys())))
        suffix = valid_sizes.get(size, '')
        base, sep, ext = self.link.rpartition('.')
        async with aiohttp.ClientSession() as session:
            async with session.get(base + suffix + sep + ext) as resp:
                if name or self.title:
                    try:
                        return await save_as((name or self.title) + suffix + sep + ext)
                    except IOError:
                        pass
                    # Invalid filename
                return await save_as(self.id + suffix + sep + ext)

    async def favorite(self):
        """
        Favorite the image.

        Favoriting an already favorited image will unfavorite it.
        """
        url = self._imgur._base_url + "/3/image/{0}/favorite".format(self.id)
        return await self._imgur._send_request(url, needs_auth=True, method='POST')

    async def update(self, title=None, description=None):
        """Update the image with a new title and/or description."""
        url = (self._imgur._base_url + "/3/image/"
                                       "{0}".format(self._delete_or_id_hash))
        is_updated = await self._imgur._send_request(url, params=locals(),
                                               method='POST')
        if is_updated:
            self.title = title or self.title
            self.description = description or self.description
        return is_updated


class Imgur:
    """
    The base class containing general functionality for Imgur.

    You should create an Imgur object at the start of your code and use it to
    interact with Imgur. You shouldn't directly initialize any other classes,
    but instead use the methods in this class to get them.
    """

    def __init__(self, client_id, client_secret=None, access_token=None,
                 refresh_token=None, verify=True, mashape_key=None):
        """
        Initialize the Imgur object.

        Before using PyImgur, or the Imgur REST API in general, you need to
        register your application with Imgur. This can be done at
        https://api.imgur.com/oauth2/addclient

        :param client_id: Your applications client_id.
        :param client_secret: Your applications client_secret. This is only
            needed when a user needs to authorize the app.
        :param access_token: is your secret key used to access the user's data.
            It can be thought of the user's password and username combined into
            one, and is used to access the user's account. It expires after 1
            hour.
        :param refresh_token: is used to request new access_tokens. Since
            access_tokens expire after 1 hour, we need a way to request new
            ones without going through the entire authorization step again. It
            does not expire.
        :param verify: Verify SSL certificate of server
            (can result in SSLErrors)?
        """
        self.is_authenticated = False
        self.access_token = access_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.DEFAULT_LIMIT = 100
        self.ratelimit_clientlimit = None
        self.ratelimit_clientremaining = None
        self.ratelimit_userlimit = None
        self.ratelimit_userremaining = None
        self.ratelimit_userreset = None
        self.refresh_token = refresh_token
        self.verify = verify
        self.mashape_key = mashape_key
        if self.mashape_key:
            self._base_url = MASHAPE_BASE
        else:
            self._base_url = IMGUR_BASE

    async def _send_request(self, url, needs_auth=False, **kwargs):
        """
        Handles top level functionality for sending requests to Imgur.

        This mean
            - Raising client-side error if insufficient authentication.
            - Adding authentication information to the request.
            - Split the request into multiple request for pagination.
            - Retry calls for certain server-side errors.
            - Refresh access token automatically if expired.
            - Updating ratelimit info

        :param needs_auth: Is authentication as a user needed for the execution
            of this method?
        """
        # TODO: Add automatic test for timed_out access_tokens and
        # automatically refresh it before carrying out the request.
        refreshed_token = False
        if needs_auth and self.access_token is None:
            try:
                await self.refresh_access_token()
                refreshed_token = True
            except Exception as e:
                raise Exception("Authentication as a user is required to use this method.")
        if self.access_token is None:
            # Not authenticated as a user. Use anonymous access.
            auth = {'Authorization': 'Client-ID {0}'.format(self.client_id)}
        else:
            auth = {'Authorization': 'Bearer {0}'.format(self.access_token)}
        if self.mashape_key:
            auth.update({'X-Mashape-Key': self.mashape_key})
        content = []
        is_paginated = False
        if 'limit' in kwargs:
            is_paginated = True
            limit = kwargs['limit'] or self.DEFAULT_LIMIT
            del kwargs['limit']
            page = 0
            base_url = url
            url.format(page)
        kwargs['authentication'] = auth
        while True:
            try:
                result = await request.send_request(url, verify=self.verify, **kwargs)
            except aiohttp.ClientResponseError as e:
                if e.status == 403 and self.access_token is not None and needs_auth and not refreshed_token:
                    await self.refresh_access_token()
                    refreshed_token = True
                    result = await request.send_request(url, verify=self.verify, **kwargs)
                else:
                    raise

            new_content, ratelimit_info = result
            if is_paginated and new_content and limit > len(new_content):
                content += new_content
                page += 1
                url = base_url.format(page)
            else:
                if is_paginated:
                    content = (content + new_content)[:limit]
                else:
                    content = new_content
                break

        # Note: When the cache is implemented, it's important that the
        # ratelimit info doesn't get updated with the ratelimit info in the
        # cache since that's likely incorrect.
        for key, value in ratelimit_info.items():
            setattr(self, key[2:].replace('-', '_'), value)
        return content

    def authorization_url(self, response, state=""):
        """
        Return the authorization url that's needed to authorize as a user.

        :param response: Can be either code or pin. If it's code the user will
            be redirected to your redirect url with the code as a get parameter
            after authorizing your application. If it's pin then after
            authorizing your application, the user will instead be shown a pin
            on Imgurs website. Both code and pin are used to get an
            access_token and refresh token with the exchange_code and
            exchange_pin functions respectively.
        :param state: This optional parameter indicates any state which may be
            useful to your application upon receipt of the response. Imgur
            round-trips this parameter, so your application receives the same
            value it sent. Possible uses include redirecting the user to the
            correct resource in your site, nonces, and
            cross-site-request-forgery mitigations.
        """
        return AUTHORIZE_URL.format(self._base_url, self.client_id, response, state)

    def change_authentication(self, client_id=None, client_secret=None,
                              access_token=None, refresh_token=None):
        """Change the current authentication."""
        # TODO: Add error checking so you cannot change client_id and retain
        # access_token. Because that doesn't make sense.
        self.client_id = client_id or self.client_id
        self.client_secret = client_secret or self.client_secret
        self.access_token = access_token or self.access_token
        self.refresh_token = refresh_token or self.refresh_token

    async def create_album(self, title=None, description=None, images=None,
                     cover=None):
        """
        Create a new Album.

        :param title: The title of the album.
        :param description: The albums description.
        :param images: A list of the images that will be added to the album
            after it's created.  Can be Image objects, ids or a combination of
            the two.  Images that you cannot add (non-existing or not owned by
            you) will not cause exceptions, but fail silently.
        :param cover: The id of the image you want as the albums cover image.

        :returns: The newly created album.
        """
        url = self._base_url + "/3/album/"
        payload = {'ids': images, 'title': title,
                   'description': description, 'cover': cover}
        resp = await self._send_request(url, params=payload, method='POST')
        return Album(resp, self, has_fetched=False)

    async def exchange_code(self, code):
        """Exchange one-use code for an access_token and request_token."""
        params = {'client_id': self.client_id,
                  'client_secret': self.client_secret,
                  'grant_type': 'authorization_code',
                  'code': code}
        result = await self._send_request(EXCHANGE_URL.format(self._base_url),
                                    params=params, method='POST',
                                    data_field=None)
        self.access_token = result['access_token']
        self.refresh_token = result['refresh_token']
        return self.access_token, self.refresh_token

    async def exchange_pin(self, pin):
        """Exchange one-use pin for an access_token and request_token."""
        params = {'client_id': self.client_id,
                  'client_secret': self.client_secret,
                  'grant_type': 'pin',
                  'pin': pin}
        result = await self._send_request(EXCHANGE_URL.format(self._base_url),
                                    params=params, method='POST',
                                    data_field=None)
        self.access_token = result['access_token']
        self.refresh_token = result['refresh_token']
        return self.access_token, self.refresh_token

    async def get_album(self, id):
        """Return information about this album."""
        url = self._base_url + "/3/album/{0}".format(id)
        json = await self._send_request(url)
        return Album(json, self)

    async def get_comment(self, id):
        """Return information about this comment."""
        url = self._base_url + "/3/comment/{0}".format(id)
        json = await self._send_request(url)
        return Comment(json, self)

    async def get_image(self, id):
        """Return a Image object representing the image with the given id."""
        url = self._base_url + "/3/image/{0}".format(id)
        resp = await self._send_request(url)
        return Image(resp, self)

    def is_imgur_url(self, url):
        """Is the given url a valid Imgur url?"""
        return re.match("(http://)?(www\.)?imgur\.com", url, re.I) is not None

    async def refresh_access_token(self):
        """
        Refresh the access_token.

        The self.access_token attribute will be updated with the value of the
        new access_token which will also be returned.
        """
        if self.client_secret is None:
            raise Exception("client_secret must be set to execute "
                            "refresh_access_token.")
        if self.refresh_token is None:
            raise Exception("refresh_token must be set to execute "
                            "refresh_access_token.")
        params = {'client_id': self.client_id,
                  'client_secret': self.client_secret,
                  'grant_type': 'refresh_token',
                  'refresh_token': self.refresh_token}
        result = await self._send_request(REFRESH_URL.format(self._base_url),
                                    params=params, method='POST',
                                    data_field=None)
        self.access_token = result['access_token']
        return self.access_token

    async def _upload_image_data(self, data, title=None, description=None, album=None, anon=False):
        payload = {'album_id': album, 'image': data,
                   'title': title, 'description': description}

        resp = await self._send_request(self._base_url + "/3/image", params=payload, method='POST', needs_auth=not anon)
        # TEMPORARY HACK:
        # On 5-08-2013 I noticed Imgur now returned enough information from
        # this call to fully populate the Image object. However those variables
        # that matched arguments were always None, even if they had been given.
        # See https://groups.google.com/forum/#!topic/imgur/F3uVb55TMGo
        resp['title'] = title
        resp['description'] = description
        if album is not None:
            resp['album'] = (Album({'id': album}, self, False) if not isinstance(album, Album) else album)
        return Image(resp, self)

    async def upload_image_blob(self, blob, title=None, description=None, album=None, anon=False):
        return await self._upload_image_data(b64encode(blob).decode("ascii"), title=title, description=description, album=album, anon=anon)

    async def upload_image(self, path=None, url=None, title=None, description=None, album=None, anon=False):
        """
        Upload the image at either path or url.

        :param path: The path to the image you want to upload.
        :param url: The url to the image you want to upload.
        :param title: The title the image will have when uploaded.
        :param description: The description the image will have when uploaded.
        :param album: The album the image will be added to when uploaded. Can
            be either a Album object or it's id. Leave at None to upload
            without adding to an Album, adding it later is possible.
            Authentication as album owner is necessary to upload to an album
            with this function.

        :returns: An Image object representing the uploaded image.
        """
        if bool(path) == bool(url):
            raise LookupError("Either path or url must be given.")
        if path:
            with open(path, 'rb') as image_file:
                binary_data = image_file.read()
                return await self.upload_image_blob(binary_data, title=title, description=description, album=album, anon=anon)
        else:
            return await self._upload_image_data(url, title=title, description=description, album=album, anon=anon)
