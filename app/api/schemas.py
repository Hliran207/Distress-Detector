from typing import Optional

from pydantic import BaseModel, Field


class RedditPost(BaseModel):
    post_id: str
    title: Optional[str] = None
    body: Optional[str] = None
    subreddit: Optional[str] = None
    label: Optional[int] = Field(default=None, ge=0, le=1)
    created_utc: Optional[int] = None
    timestamp: Optional[str] = None


class PostsListResponse(BaseModel):
    total: int
    items: list[RedditPost]


class StatsResponse(BaseModel):
    total_records: int
    counts_by_label: dict[str, int]
    posts_per_subreddit: dict[str, int]

