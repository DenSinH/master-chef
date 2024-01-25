from .base import *

COMMENTS_COLLECTION = "comments"


def _comment_document_id(userid, recipecollection, recipeid):
    return f"{recipecollection}-{recipeid}"


@dataclass
class Comment(DataRow):
    pass