from sanic import Sanic, Request, HTTPResponse
import gzip


COMPRESS_MIME_TYPES = frozenset([
    "text/html",
    "text/css",
    "text/xml",
    "application/json",
    "application/javascript"
])
COMPRESS_LEVEL = 6
COMPRESS_MIN_SIZE = 500


def _compress(response: HTTPResponse):
    """ Perform actual compression on response """
    out = gzip.compress(
        response.body,
        compresslevel=COMPRESS_LEVEL
    )

    return out

async def _compress_response(request: Request, response: HTTPResponse):
    """ Compress the given response, or return None """
    if not response.body:
        return None
    
    # read response data
    accept_encoding = request.headers.get("Accept-Encoding", "")
    content_length = len(response.body)
    content_type, *_ = (response.content_type or "").split(";", maxsplit=1)

    # check if we want to compress this response, it has to:
    # - be compressible
    # - accept gzip encoding
    # - have a "successful" response status
    # - be large enough to warrant compressing
    # - not already be encoded in some other way
    do_compress = content_type in COMPRESS_MIME_TYPES \
                  and "gzip" in accept_encoding.lower() \
                  and 200 <= response.status < 300 \
                  and content_length > COMPRESS_MIN_SIZE \
                  and "Content-Encoding" not in response.headers
    if not do_compress:
        return None

    # compress response body
    gzip_content = _compress(response)
    response.body = gzip_content

    # set proper values
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Length"] = len(response.body)

    # notify the client that the Accept-Encoding influenced
    # generation of this response, possibly marking it uncachable
    vary = response.headers.get("Vary")
    if vary:
        if "accept-encoding" not in vary.lower():
            response.headers["Vary"] = f"{vary}, Accept-Encoding"
    else:
        response.headers["Vary"] = "Accept-Encoding"

    return None


def init_compression(app: Sanic):
    """ Initialize compression middleware on response """
        
    @app.middleware("response")
    async def compress_response(request: Request, response: HTTPResponse):
        return await _compress_response(request, response)
