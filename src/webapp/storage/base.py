from google.cloud import firestore
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DataRow:
    @classmethod
    def from_dict(cls, source):
        return cls(**source)

    def to_dict(self):
        return asdict(self)


_db = None


def get_db() -> firestore.Client:
    global _db

    if _db is None:
        _db = firestore.Client()
    return _db
