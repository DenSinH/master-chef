import base64
import dataclasses
import hashlib
import logging
import os
import re
import textwrap
from contextlib import asynccontextmanager
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urljoin, urlparse

from aiobotocore.client import AioBaseClient
from aiobotocore.session import get_session
from botocore.exceptions import ClientError
from PIL import Image

logger = logging.getLogger(__name__)

S3_ENDPOINT = os.environ["S3_ENDPOINT"]
S3_ACCESS_KEY = os.environ["S3_ACCESS_KEY"]
S3_SECRET_KEY = os.environ["S3_SECRET_KEY"]
S3_BUCKET = os.environ["S3_BUCKET"]
S3_PUBLIC_URL = urlparse(os.environ["S3_PUBLIC_URL"])

IMAGE_MAX_SIZE = 150 * 1024  # 150kb

S3_CLIENT: AioBaseClient = None  # type: ignore


class MinioError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ImageMeta:
    size: int
    quality: int


@asynccontextmanager
async def client_lifetime(*args):
    global S3_CLIENT

    session = get_session()

    async with session.create_client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name=os.environ.get("S3_REGION", "us-east-1"),
    ) as client:
        S3_CLIENT = client
        yield


async def _preprocess_image(filedata: bytes) -> tuple[BytesIO, ImageMeta]:
    """Prepare an image. This includes:
    - WEBP compression down to IMAGE_MAX_SIZE
    Return the image bytes, and metadata containing the
    final image quality"""
    logger.info(f"Compressing image of size {len(filedata)}")
    image = Image.open(BytesIO(filedata))
    output = BytesIO()
    size = -1
    quality = 0

    # keep retrying lower quality rates compression
    # until we compressed enough or until the quality is too low
    for quality in range(100, 10, -5):
        output.seek(0)
        output.truncate()
        image.save(output, format="WEBP", quality=quality, optimize=True)
        size = output.tell()
        if size <= IMAGE_MAX_SIZE:
            break
    else:
        raise MinioError(
            f"Uploaded image too large: {output.tell()} bytes with quality level {quality}"
        )

    # return data, seek 0 in output stream
    logger.info(f"Compressed image to {size} with quality {quality}")
    output.seek(0)
    metadata = ImageMeta(size=size, quality=quality)
    return output, metadata


def _get_objname(imagedata: BytesIO, title: str | None):
    """Generate an image title, unique to the image data
    and title. It consists of a SHA256 hash of the image data,
    as well as the title converted to kebab-case, stripped of any
    non-alphanumeric characters."""

    # get sha of image
    sha256 = hashlib.sha256(imagedata.read(), usedforsecurity=False)
    sha = base64.urlsafe_b64encode(sha256.digest())
    sha = sha.rstrip(b"=").decode()  # strip = encoder bytes

    # revert stream position
    imagedata.seek(0)

    # no title, filename is just sha
    if title is None:
        return sha

    # convert title to kebab case
    single_space = re.sub(r"[\s_-]+", " ", title)
    only_alnum = re.sub(r"[^\w\s-]", "", single_space.strip())
    kebab_case = re.sub(r"[\s_-]", "-", only_alnum)

    # make sure filenames are not too long
    title = textwrap.shorten(
        f"{sha}-{kebab_case.lower()}", width=80, placeholder=""
    ).strip("-")
    return title


def _get_url(objname: str):
    """Get the public URL for an object in the S3 bucket."""
    base_url = S3_PUBLIC_URL
    return urljoin(base_url.geturl(), f"{S3_BUCKET}/{objname}")


async def upload_image(filedata: bytes, title=None):
    """Upload image data to Minio CDN. We first preprocess the
    image, compressing it to a small enough WEBP image. We then
    compute a filename based on the (compressed) image data,
    and the provided title. The result is uploaded to Minio."""
    logger.info(f"Uploading image with size {len(filedata)}")

    # preprocess image
    processed, metadata = await _preprocess_image(filedata)
    objname = _get_objname(processed, title=title)
    objname += ".webp"

    logger.info(f"Got object name {objname}")
    try:
        await S3_CLIENT.head_object(
            Bucket=S3_BUCKET,
            Key=objname,
        )
        logger.info(f"Object {objname} already exists in {S3_BUCKET}")
    except ClientError as e:
        # Only treat a missing object as "doesn't exist". Don't hide
        # authentication, connectivity, etc. errors.
        if e.response["Error"]["Code"] not in ("404", "NoSuchKey"):
            raise
        # file does not exist (?), upload file with metadata
        logger.info(f"Uploading new object {objname}")
        await S3_CLIENT.put_object(
            Bucket=S3_BUCKET,
            Key=objname,
            Body=processed,
            ContentLength=metadata.size,
            ContentType="image/webp",
            Metadata={
                key: str(value) for key, value in dataclasses.asdict(metadata).items()
            },
        )

    return _get_url(objname)
