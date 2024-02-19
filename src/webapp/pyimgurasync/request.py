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

"""Handles sending and parsing requests to/from Imgur REST API."""

from numbers import Integral
import aiohttp


MAX_RETRIES = 3
RETRY_CODES = [500]


def convert_general(value):
    """Take a python object and convert it to the format Imgur expects."""
    if isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, list):
        value = [convert_general(item) for item in value]
        value = convert_to_imgur_list(value)
    elif isinstance(value, Integral):
        return str(value)
    elif 'pyimgur' in str(type(value)):
        return str(getattr(value, 'id', value))
    return value


def convert_to_imgur_list(regular_list):
    """Turn a python list into the list format Imgur expects."""
    if regular_list is None:
        return None
    return ",".join(str(id) for id in regular_list)


def to_imgur_format(params):
    """Convert the parameters to the format Imgur expects."""
    if params is None:
        return None
    return dict((k, convert_general(val)) for (k, val) in params.items())


async def send_request(url, params=None, method='GET', data_field='data', authentication=None, verify=True, data=None):
    params = to_imgur_format(params)
    # We may need to add more elements to the header later. For now, it seems
    # the only thing in the header is the authentication
    headers = authentication
    # NOTE I could also convert the returned output to the correct object here.
    # The reason I don't is that some queries just want the json, so they can
    # update an existing object. This we do with lazy evaluation. Here we
    # wouldn't know that, although obviously we could have a "raw" parameter
    # that just returned the json. Dunno. Having parsing of the returned output
    # be done here could make the code simpler at the highest level. Just
    # request an url with some parameters and voila you get the object back you
    # wanted.
    is_succesful_request = False
    tries = 0
    content = None
    async with aiohttp.ClientSession() as session:
        while not is_succesful_request and tries <= MAX_RETRIES:
            if method == 'GET':
                req = session.get(url, params=params, headers=headers, verify_ssl=verify)
            elif method == 'POST':
                if data is not None:
                    req = session.post(url, data=data, headers=headers, verify_ssl=verify)
                else:
                    req = session.post(url, json=params, headers=headers, verify_ssl=verify)
            elif method == 'PUT':
                req = session.put(url, json=params, headers=headers, verify_ssl=verify)
            elif method == 'DELETE':
                req = session.delete(url, headers=headers, verify_ssl=verify)

            async with req as resp:
                if resp.status in RETRY_CODES or resp.content == "":
                    tries += 1
                else:
                    is_succesful_request = True
                    if not resp.ok:
                        resp.raise_for_status()
                    ratelimit_info = dict((k, int(v)) for (k, v) in resp.headers.items() if k.startswith('x-ratelimit'))
                    content = await resp.json()
                    if data_field is not None:
                        content = content[data_field]
    return content, ratelimit_info
