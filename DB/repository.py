from pymongo.collection import Collection
from pymongo import errors

from DB.models.Post import Post


class MongoPostRepository:
    """
    Encapsulated MongoDB operrations for reddit posts
    """

    def __init__(self, collection: Collection):
        self.collection = collection
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """
        Create a unique index on post_id to avoid duplicates.
        """
        self.collection.create_index("post_id", unique=True)

    def count_posts_for_subreddit(self, subreddit: str) -> int:
        """
        Count how many posts already exist for a given subreddit.
        """
        return self.collection.count_documents({"subreddit": subreddit})

    def insert_post(self, post: Post) -> bool:
        """
        Insert a Post. Returns True if inserted, False if duplicate.
        """
        try:
            self.collection.insert_one(post.to_dict())
            return True
        except errors.DuplicateKeyError:
            # Duplicate post_id — skip
            return False
