from typing import Any

from pymongo.collection import Collection
from pymongo import errors
from pymongo.errors import BulkWriteError

from app.models.post import Post


class MongoPostsRepository:
    """
    Repository responsible for CRUD operations on the configured MongoDB posts collection
    (`MONGO_DB_NAME` / `MONGO_URI`, default database `reddit_distress_db`).
    """

    def __init__(self, collection: Collection):
        self.collection = collection
        self.ensure_indexes()

    def ensure_indexes(self) -> None:
        # Unique key for all sources (Selenium / PullPush)
        self.collection.create_index("post_id", unique=True)
        self.collection.create_index("reddit_id", unique=True, sparse=True)

    def count_posts_for_subreddit(self, subreddit: str) -> int:
        return self.collection.count_documents({"subreddit": subreddit})

    def exists_any_id(self, post_id: str) -> bool:
        """
        Backwards-compatible dedup: `reddit_id`, `post_id`, and legacy `id`.
        """
        return (
            self.collection.find_one({"reddit_id": post_id}, projection={"_id": 1}) is not None
            or self.collection.find_one({"post_id": post_id}, projection={"_id": 1}) is not None
            or self.collection.find_one({"id": post_id}, projection={"_id": 1}) is not None
        )

    def insert_post(self, post: Post) -> bool:
        try:
            self.collection.insert_one(post.to_mongo())
            return True
        except errors.DuplicateKeyError:
            return False

    def insert_raw(self, doc: dict) -> bool:
        try:
            self.collection.insert_one(doc)
            return True
        except errors.DuplicateKeyError:
            return False

    def insert_many_raw(self, docs: list[dict[str, Any]]) -> int:
        """Bulk insert; returns count of documents inserted (skips duplicates on partial failure)."""
        if not docs:
            return 0
        try:
            result = self.collection.insert_many(docs, ordered=False)
            return len(result.inserted_ids)
        except BulkWriteError as e:
            return int(e.details.get("nInserted", 0))

