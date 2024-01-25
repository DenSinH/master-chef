from .base import *


VIEWS_COLLECTION = "views"


def _view_document_id(recipecollection, recipeid):
    return f"{recipecollection}-{recipeid}"


@dataclass
class Views(DataRow):
    recipecollection: str
    recipeid: str
    views: int = 0


def view_recipe(recipecollection, recipeid):
    db = get_db()
    views = db.collection(VIEWS_COLLECTION).document(_view_document_id(recipecollection, recipeid))
    result = views.set(Views(recipecollection, recipeid, views=firestore.Increment(1)).to_dict(), merge=True)
    return result.transform_results[0].integer_value


def move_recipe(collectionfrom, collectionto, idfrom, idto):
    db = get_db()
    views_ref = db.collection(VIEWS_COLLECTION).document(_view_document_id(collectionfrom, idfrom))
    views = views_ref.get()
    if views.exists:
        # insert moved recipe
        db.collection(VIEWS_COLLECTION).document(_view_document_id(collectionto, idto)).set(views.to_dict())
        views_ref.delete()
    else:
        # no data, just do nothing
        pass


def collection_views(collection):
    db = get_db()
    result = {}
    for doc in db.collection(VIEWS_COLLECTION).where(filter=FieldFilter("recipecollection", "==", collection)).stream():
        views = Views(**doc.to_dict())
        result[views.recipeid] = views.views
    return result
