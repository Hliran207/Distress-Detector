import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorCollection

from app.api.deps import (
    get_posts_collection,
    get_telegram_collection,
    get_telegram_monitor_controller,
)
from app.api.schemas import (
    PostsListResponse,
    RedditPost,
    TelegramScanItemModel,
    TelegramScanRequest,
    TelegramScanResponse,
)
from app.api.serialization import serialize_mongo_doc
from app.controllers.telegram_monitor import TelegramMonitorController
from app.services.telegram_service import TelegramFetchError


router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("", response_model=PostsListResponse)
async def list_posts(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    label: Optional[int] = Query(default=None, ge=0, le=1),
    subreddit: Optional[str] = Query(default=None, min_length=1),
    collection: AsyncIOMotorCollection = Depends(get_posts_collection),
) -> PostsListResponse:
    query: dict[str, Any] = {}
    if label is not None:
        query["label"] = label
    if subreddit is not None:
        query["subreddit"] = subreddit

    total = await collection.count_documents(query)
    cursor = (
        collection.find(query)
        .skip(offset)
        .limit(limit)
        .sort([("created_utc", -1), ("_id", -1)])
    )
    docs = await cursor.to_list(length=limit)
    items = [RedditPost(**serialize_mongo_doc(d)) for d in docs]
    return PostsListResponse(total=total, items=items)


@router.get("/search", response_model=PostsListResponse)
async def search_posts(
    q: str = Query(..., min_length=1, description="Keyword to search for"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    label: Optional[int] = Query(default=None, ge=0, le=1),
    collection: AsyncIOMotorCollection = Depends(get_posts_collection),
) -> PostsListResponse:
    safe = re.escape(q)
    regex = {"$regex": safe, "$options": "i"}

    query: dict[str, Any] = {
        "$or": [
            {"title": regex},
            {"body": regex},
            {"selftext": regex},
        ]
    }
    if label is not None:
        query["label"] = label

    total = await collection.count_documents(query)
    cursor = (
        collection.find(query)
        .skip(offset)
        .limit(limit)
        .sort([("created_utc", -1), ("_id", -1)])
    )
    docs = await cursor.to_list(length=limit)
    items = [RedditPost(**serialize_mongo_doc(d)) for d in docs]
    return PostsListResponse(total=total, items=items)


@router.get(
    "/telegram",
    response_model=PostsListResponse,
    summary="List analyzed Telegram messages",
    description=(
        "Reads from the dedicated `telegram_messages` collection (populated by "
        "`POST /posts/scan/telegram`). Supports filtering by `chat_id` and a "
        "minimum `distress_score`."
    ),
)
async def list_telegram_messages(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    chat_id: Optional[str] = Query(default=None, min_length=1),
    min_score: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    collection: AsyncIOMotorCollection = Depends(get_telegram_collection),
) -> PostsListResponse:
    query: dict[str, Any] = {}
    if chat_id is not None:
        query["subreddit"] = chat_id
    if min_score is not None:
        query["distress_score"] = {"$gte": min_score}

    total = await collection.count_documents(query)
    cursor = (
        collection.find(query)
        .skip(offset)
        .limit(limit)
        .sort([("created_utc", -1), ("_id", -1)])
    )
    docs = await cursor.to_list(length=limit)
    items = [RedditPost(**serialize_mongo_doc(d)) for d in docs]
    return PostsListResponse(total=total, items=items)


@router.post(
    "/scan/telegram",
    response_model=TelegramScanResponse,
    summary="Scan pending Telegram updates for distress",
    description=(
        "Drains the Telegram bot's pending update queue (Bot API "
        "`getUpdates`), keeps messages whose `chat.id` matches the "
        "requested `chat_id`, scores each with the distress ensemble, "
        "and stores the analyzed messages in the `telegram_messages` "
        "collection (separate from the Reddit `posts` collection). "
        "Note: only messages received while the bot was online and not "
        "yet acknowledged are available — older chat history cannot be "
        "fetched through the Bot API. Serializes against the background "
        "auto-scan loop via `app.state.telegram_lock`."
    ),
)
async def scan_telegram(
    request: Request,
    body: TelegramScanRequest,
    controller: TelegramMonitorController = Depends(get_telegram_monitor_controller),
) -> TelegramScanResponse:
    try:
        async with request.app.state.telegram_lock:
            summary = await controller.scan_chat(body.chat_id, limit=body.limit)
    except TelegramFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return TelegramScanResponse(
        chat_id=summary.chat_id,
        fetched=summary.fetched,
        processed=summary.processed,
        inserted=summary.inserted,
        skipped_duplicates=summary.skipped_duplicates,
        skipped_empty=summary.skipped_empty,
        items=[
            TelegramScanItemModel(
                post_id=item.post_id,
                label=item.label,
                distress_score=item.distress_score,
                preview=item.preview,
            )
            for item in summary.items
        ],
    )


@router.get("/{post_id}", response_model=RedditPost)
async def get_post(
    post_id: str,
    collection: AsyncIOMotorCollection = Depends(get_posts_collection),
) -> RedditPost:
    doc = await collection.find_one(
        {"$or": [{"post_id": post_id}, {"id": post_id}, {"reddit_id": post_id}]}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Post not found")
    return RedditPost(**serialize_mongo_doc(doc))
