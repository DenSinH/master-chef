from miniopy_async import Minio
import miniopy_async.error
from PIL import Image
from io import BytesIO
import hashlib
import base64
import msgspec.json
from dataclasses import dataclass
import dataclasses
import re
import textwrap
from urllib.parse import urlparse, urljoin
import os


MINIO_INSECURE = bool(int(os.environ.get("MINIO_INSECURE", "0")))
MINIO_CLIENT: Minio = Minio(
    os.environ["MINIO_URL"],
    os.environ["MINIO_ACCESS_KEY"],
    os.environ["MINIO_SECRET_KEY"],
    # we may want to allow an insecure environment
    # for local development
    secure=not MINIO_INSECURE
)
# parse public URL once
MINIO_PUBLIC_URL = urlparse(os.environ.get("MINIO_PUBLIC_URL", os.environ["MINIO_URL"]))
MINIO_BUCKET = os.environ["MINIO_BUCKET"]
DEFAULT_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": ["*"]
            },
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{MINIO_BUCKET}/*"]
        }
    ]
}
IMAGE_MAX_SIZE = 300 * 1024  # 300kb


class MinioError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ImageMeta:
    size: int
    quality: int


async def init_client(*args):
    """ Initialize client """
    pass


async def _preprocess_image(filedata: bytes) -> tuple[BytesIO, ImageMeta]:
    """ Prepare an image. This includes:
    - WEBP compression down to IMAGE_MAX_SIZE 
    Return the image bytes, and metadata containing the
    final image quality """
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
    output.seek(0)
    metadata = ImageMeta(
        size=size,
        quality=quality
    )
    return output, metadata


def _get_objname(imagedata: BytesIO, title: str | None):
    """ Generate an image title, unique to the image data
    and title. It consists of a SHA256 hash of the image data,
    as well as the title converted to kebab-case, stripped of any
    non-alphanumeric characters. """

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
    single_space = re.sub("[\s_-]+", " ", title)
    only_alnum = re.sub(r"[^\w\s-]", "", single_space.strip())
    kebab_case = re.sub("[\s_-]", "-", only_alnum)

    # make sure filenames are not too long
    title = textwrap.shorten(f"{sha}-{kebab_case.lower()}", width=80).strip("-")
    return title


def _get_url(objname: str):
    """ Get a valid (public) url for the given object,
    in the MINIO_BUCKET. """
    base_url = MINIO_PUBLIC_URL

    # append scheme if none is passed
    if not base_url.scheme:
        scheme = "http"
        if not MINIO_INSECURE:
            scheme += "s"
        base_url = f"{scheme}://" + base_url

    # join base url and bucket/objname
    return urljoin(base_url.geturl(), f"{MINIO_BUCKET}/{objname}")


async def upload_image(filedata: bytes, title=None):
    """ Upload image data to Minio CDN. We first preprocess the
    image, compressing it to a small enough WEBP image. We then 
    compute a filename based on the (compressed) image data,
    and the provided title. The result is uploaded to Minio. """
    # preprocess image
    processed, metadata = await _preprocess_image(filedata)
    objname = _get_objname(processed, title=title)
    objname += ".webp"
    
    try:
        await MINIO_CLIENT.stat_object(MINIO_BUCKET, objname)
        print(f"Object {objname} already exists in {MINIO_BUCKET}")
    except miniopy_async.error.MinioException:
        # file does not exist (?), upload file with metadata
        await MINIO_CLIENT.put_object(
            MINIO_BUCKET,
            objname,
            processed,
            length=metadata.size,
            metadata=dataclasses.asdict(metadata)
        )

    return _get_url(objname)
