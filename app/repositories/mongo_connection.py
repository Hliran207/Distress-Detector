from pymongo import MongoClient
from pymongo.collection import Collection

from app.mongo_config import DB_NAME, load_mongo_uri


def get_posts_collection() -> Collection:
    mongo_uri = load_mongo_uri()
    client = MongoClient(mongo_uri)
    db = client[DB_NAME]
    return db["posts"]

