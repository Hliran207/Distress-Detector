import os

from dotenv import load_dotenv

COLLECTION_NAME = "posts"
TELEGRAM_COLLECTION_NAME = "telegram_messages"


def load_mongo_uri() -> str:
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise RuntimeError("MONGO_URI is not set in .env")
    return mongo_uri


def get_db_name() -> str:
    load_dotenv()
    return os.getenv("MONGO_DB_NAME", "reddit_distress_db")
