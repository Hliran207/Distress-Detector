from dataclasses import dataclass
from typing import Optional, Dict


@dataclass(frozen=True)
class Post:
    """
    Canonical post model stored in MongoDB.
    """

    post_id: str
    title: str
    body: str
    subreddit: str
    label: int  # 1 for distress, 0 for control
    timestamp: Optional[str]
    scraped_at: str

    def to_mongo(self) -> Dict[str, object]:
        return {
            "post_id": self.post_id,
            "title": self.title,
            "body": self.body,
            "subreddit": self.subreddit,
            "label": self.label,
            "timestamp": self.timestamp,
            "scraped_at": self.scraped_at,
        }

