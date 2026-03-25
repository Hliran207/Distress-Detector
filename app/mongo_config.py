import os

from dotenv import load_dotenv

COLLECTION_NAME = "posts"


def _load_env() -> None:
    load_dotenv()


def load_mongo_uri() -> str:
    _load_env()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise RuntimeError("MONGO_URI is not set in .env")
    return mongo_uri


def resolve_db_name() -> str:
    _load_env()
    return os.getenv("MONGO_DB_NAME", "reddit_distress_db")


DB_NAME = resolve_db_name()
