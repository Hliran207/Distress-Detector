from motor.motor_asyncio import AsyncIOMotorCollection
from fastapi import APIRouter, Depends

from app.api.deps import get_posts_collection
from app.api.schemas import StatsResponse


router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary", response_model=StatsResponse)
async def stats_summary(
    collection: AsyncIOMotorCollection = Depends(get_posts_collection),
) -> StatsResponse:
    total_records = await collection.count_documents({})

    label_pipeline = [
        {"$group": {"_id": "$label", "count": {"$sum": 1}}},
    ]
    label_counts: dict[str, int] = {"0": 0, "1": 0}
    async for row in collection.aggregate(label_pipeline):
        if row.get("_id") is None:
            continue
        label_counts[str(row["_id"])] = int(row.get("count", 0))

    subreddit_pipeline = [
        {"$group": {"_id": "$subreddit", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    per_subreddit: dict[str, int] = {}
    async for row in collection.aggregate(subreddit_pipeline):
        subreddit = row.get("_id")
        if subreddit is None:
            continue
        per_subreddit[str(subreddit)] = int(row.get("count", 0))

    return StatsResponse(
        total_records=total_records,
        counts_by_label=label_counts,
        posts_per_subreddit=per_subreddit,
    )

