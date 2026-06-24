import re
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import BaseModel, Field

from deps import get_posts_collection, get_telegram_collection
from schemas import StatsResponse

router = APIRouter(prefix="/stats", tags=["stats"])

STOP_WORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "her",
        "was",
        "one",
        "our",
        "out",
        "day",
        "get",
        "has",
        "him",
        "his",
        "how",
        "its",
        "may",
        "new",
        "now",
        "old",
        "see",
        "two",
        "way",
        "who",
        "boy",
        "did",
        "she",
        "use",
        "that",
        "this",
        "with",
        "have",
        "from",
        "they",
        "been",
        "were",
        "what",
        "when",
        "your",
        "just",
        "like",
        "will",
        "more",
        "than",
        "into",
        "also",
        "only",
        "very",
        "some",
        "them",
        "then",
        "over",
        "such",
        "make",
        "made",
        "much",
        "well",
        "back",
        "even",
        "most",
        "know",
        "take",
        "come",
        "want",
        "need",
        "feel",
        "feeling",
    }
)

WORD_PATTERN = re.compile(r"[a-zA-Z']+")

SCORE_FALLBACK = {"$ifNull": ["$distress_score", "$label"]}


class DistressDistributionResponse(BaseModel):
    distress: int
    not_distress: int
    average_distress_score: float = Field(description="Mean distress score across all records")
    escalated_count: int = Field(description="Records escalated to the transformer model")


class MessagesOverTimeItem(BaseModel):
    date: str
    total: int
    distress: int
    avg_score: float = Field(description="Mean distress score for records on this day")


class TopWordItem(BaseModel):
    text: str
    value: int


class SubredditCountItem(BaseModel):
    subreddit: str
    total: int
    distress: int


def _event_date_add_fields() -> dict[str, Any]:
    return {
        "$addFields": {
            "event_date": {
                "$ifNull": [
                    {
                        "$dateFromString": {
                            "dateString": "$timestamp",
                            "onError": None,
                            "onNull": None,
                        }
                    },
                    {
                        "$cond": [
                            {"$ne": ["$created_utc", None]},
                            {"$toDate": {"$multiply": ["$created_utc", 1000]}},
                            None,
                        ]
                    },
                ]
            }
        }
    }


def _fill_daily_rows(
    by_date: dict[str, MessagesOverTimeItem],
    cutoff: datetime,
    end: datetime,
) -> list[MessagesOverTimeItem]:
    rows: list[MessagesOverTimeItem] = []
    day_cursor = cutoff.date()
    end_day = end.date()
    while day_cursor <= end_day:
        day_key = day_cursor.isoformat()
        rows.append(
            by_date.get(
                day_key,
                MessagesOverTimeItem(
                    date=day_key,
                    total=0,
                    distress=0,
                    avg_score=0.0,
                ),
            )
        )
        day_cursor += timedelta(days=1)
    return rows


async def _distress_distribution(
    collection: AsyncIOMotorCollection,
    *,
    use_score_fallback: bool = False,
) -> DistressDistributionResponse:
    distress = await collection.count_documents({"label": 1})
    not_distress = await collection.count_documents({"label": 0})
    escalated_count = await collection.count_documents({"escalated": True})

    avg_field: Any = SCORE_FALLBACK if use_score_fallback else "$distress_score"
    avg_score = 0.0
    async for row in collection.aggregate(
        [{"$group": {"_id": None, "avg": {"$avg": avg_field}}}]
    ):
        if row.get("avg") is not None:
            avg_score = round(float(row["avg"]), 4)

    return DistressDistributionResponse(
        distress=distress,
        not_distress=not_distress,
        average_distress_score=avg_score,
        escalated_count=escalated_count,
    )


async def _messages_over_time(
    collection: AsyncIOMotorCollection,
    *,
    cutoff: datetime,
    end: datetime,
    use_score_fallback: bool = False,
) -> list[MessagesOverTimeItem]:
    avg_field: Any = SCORE_FALLBACK if use_score_fallback else "$distress_score"

    pipeline: list[dict[str, Any]] = [
        _event_date_add_fields(),
        {
            "$match": {
                "event_date": {"$ne": None, "$gte": cutoff, "$lte": end},
            }
        },
        {
            "$group": {
                "_id": {
                    "$dateToString": {"format": "%Y-%m-%d", "date": "$event_date"}
                },
                "total": {"$sum": 1},
                "distress": {
                    "$sum": {
                        "$cond": [{"$eq": ["$label", 1]}, 1, 0],
                    }
                },
                "avg_score": {"$avg": avg_field},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    by_date: dict[str, MessagesOverTimeItem] = {}
    async for row in collection.aggregate(pipeline):
        day = str(row.get("_id", ""))
        if not day:
            continue
        avg = row.get("avg_score")
        by_date[day] = MessagesOverTimeItem(
            date=day,
            total=int(row.get("total", 0)),
            distress=int(row.get("distress", 0)),
            avg_score=round(float(avg), 4) if avg is not None else 0.0,
        )

    return _fill_daily_rows(by_date, cutoff, end)


async def _top_words_from_text(
    collection: AsyncIOMotorCollection,
    *,
    text_fields: tuple[str, ...],
    label: int,
) -> list[TopWordItem]:
    word_counts: dict[str, int] = {}
    projection = {field: 1 for field in text_fields}

    cursor = collection.find({"label": label}, projection)

    async for doc in cursor:
        chunks: list[str] = []
        for field in text_fields:
            value = doc.get(field)
            if isinstance(value, str) and value.strip():
                chunks.append(value)
        combined = " ".join(chunks).strip()
        if not combined:
            continue
        for token in WORD_PATTERN.findall(combined.lower()):
            if len(token) < 3 or token in STOP_WORDS:
                continue
            word_counts[token] = word_counts.get(token, 0) + 1

    ranked = sorted(word_counts.items(), key=lambda item: item[1], reverse=True)[:50]
    return [TopWordItem(text=word, value=count) for word, count in ranked]


async def _posts_time_window(
    collection: AsyncIOMotorCollection,
) -> tuple[datetime, datetime]:
    newest = await collection.find_one(
        sort=[("created_utc", -1)],
        projection={"created_utc": 1},
    )
    if newest and newest.get("created_utc") is not None:
        try:
            end = datetime.fromtimestamp(float(newest["created_utc"]), tz=timezone.utc)
        except (TypeError, ValueError):
            end = datetime.now(timezone.utc)
    else:
        end = datetime.now(timezone.utc)

    return end - timedelta(days=30), end


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


@router.get("/distress-distribution", response_model=DistressDistributionResponse)
async def distress_distribution(
    collection: AsyncIOMotorCollection = Depends(get_telegram_collection),
) -> DistressDistributionResponse:
    return await _distress_distribution(collection)


@router.get("/messages-over-time", response_model=list[MessagesOverTimeItem])
async def messages_over_time(
    collection: AsyncIOMotorCollection = Depends(get_telegram_collection),
) -> list[MessagesOverTimeItem]:
    end = datetime.now(timezone.utc)
    cutoff = end - timedelta(days=30)
    return await _messages_over_time(collection, cutoff=cutoff, end=end)


@router.get("/top-words", response_model=list[TopWordItem])
async def top_words(
    label: int = Query(default=1, ge=0, le=1, description="0 = not distress, 1 = distress"),
    collection: AsyncIOMotorCollection = Depends(get_telegram_collection),
) -> list[TopWordItem]:
    return await _top_words_from_text(
        collection,
        text_fields=("clean_text", "body", "raw_text"),
        label=label,
    )


@router.get("/posts/distress-distribution", response_model=DistressDistributionResponse)
async def posts_distress_distribution(
    collection: AsyncIOMotorCollection = Depends(get_posts_collection),
) -> DistressDistributionResponse:
    return await _distress_distribution(collection, use_score_fallback=True)


@router.get("/posts/messages-over-time", response_model=list[MessagesOverTimeItem])
async def posts_messages_over_time(
    collection: AsyncIOMotorCollection = Depends(get_posts_collection),
) -> list[MessagesOverTimeItem]:
    cutoff, end = await _posts_time_window(collection)
    return await _messages_over_time(
        collection,
        cutoff=cutoff,
        end=end,
        use_score_fallback=True,
    )


@router.get("/posts/top-words", response_model=list[TopWordItem])
async def posts_top_words(
    label: int = Query(default=1, ge=0, le=1, description="0 = not distress, 1 = distress"),
    collection: AsyncIOMotorCollection = Depends(get_posts_collection),
) -> list[TopWordItem]:
    return await _top_words_from_text(
        collection,
        text_fields=("body", "selftext", "title"),
        label=label,
    )


@router.get("/posts/top-subreddits", response_model=list[SubredditCountItem])
async def posts_top_subreddits(
    collection: AsyncIOMotorCollection = Depends(get_posts_collection),
    limit: int = 10,
) -> list[SubredditCountItem]:
    pipeline: list[dict[str, Any]] = [
        {"$match": {"subreddit": {"$exists": True, "$nin": [None, ""]}}},
        {
            "$group": {
                "_id": "$subreddit",
                "total": {"$sum": 1},
                "distress": {
                    "$sum": {
                        "$cond": [{"$eq": ["$label", 1]}, 1, 0],
                    }
                },
            }
        },
        {"$sort": {"total": -1}},
        {"$limit": max(1, min(limit, 25))},
    ]

    rows: list[SubredditCountItem] = []
    async for row in collection.aggregate(pipeline):
        subreddit = row.get("_id")
        if subreddit is None:
            continue
        rows.append(
            SubredditCountItem(
                subreddit=str(subreddit),
                total=int(row.get("total", 0)),
                distress=int(row.get("distress", 0)),
            )
        )
    return rows
