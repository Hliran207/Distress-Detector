from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo.errors import BulkWriteError, DuplicateKeyError


class PostsRepository:
    """
    Async MongoDB repository for the FastAPI layer (Motor).

    Mirrors the sync `MongoPostsRepository` API where needed by Telegram
    scan flows; index creation for `telegram_messages` runs at startup in
    `api_main.lifespan`.
    """

    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("post_id", unique=True)
        await self.collection.create_index("reddit_id", unique=True, sparse=True)

    async def count_posts_for_subreddit(self, subreddit: str) -> int:
        return await self.collection.count_documents({"subreddit": subreddit})

    async def exists_any_id(self, post_id: str) -> bool:
        projection = {"_id": 1}
        for field in ("reddit_id", "post_id", "id"):
            doc = await self.collection.find_one({field: post_id}, projection=projection)
            if doc is not None:
                return True
        return False

    async def insert_raw(self, doc: dict[str, Any]) -> bool:
        try:
            await self.collection.insert_one(doc)
            return True
        except DuplicateKeyError:
            return False

    async def insert_many_raw(self, docs: list[dict[str, Any]]) -> int:
        if not docs:
            return 0
        try:
            result = await self.collection.insert_many(docs, ordered=False)
            return len(result.inserted_ids)
        except BulkWriteError as exc:
            return int(exc.details.get("nInserted", 0))
