from dataclasses import dataclass


@dataclass(frozen=True)
class PullPushSubmission:
    post_id: str
    subreddit: str
    title: str
    selftext: str
    created_utc: int

