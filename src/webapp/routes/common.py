from fastapi import HTTPException

from webapp import cookbook


def require_collection(collection: str):
    if not cookbook.collection_exists(collection):
        raise HTTPException(
            status_code=404,
            detail="No such collection exists",
        )
