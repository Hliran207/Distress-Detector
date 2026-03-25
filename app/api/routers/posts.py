import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorCollection

from app.api.deps import get_posts_collection
from app.api.schemas import PostsListResponse, RedditPost
from app.api.serialization import serialize_mongo_doc


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


@router.get("/{post_id}", response_model=RedditPost)
async def get_post(
    post_id: str,
    collection: AsyncIOMotorCollection = Depends(get_posts_collection),
) -> RedditPost:
    doc = await collection.find_one({"$or": [{"post_id": post_id}, {"id": post_id}]})
    if not doc:
        raise HTTPException(status_code=404, detail="Post not found")
    return RedditPost(**serialize_mongo_doc(doc))

