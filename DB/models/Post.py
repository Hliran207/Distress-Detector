from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class Post:
    post_id: str
    title: str
    body: str
    subreddit: str
    label: int  # 1 for distress, 0 for control
    timestamp: Optional[str]
    scraped_at: str

    def to_dict(self) -> Dict[str, object]:
        """
        Convert the dataclass to a plain dictionary for MongoDB.
        """
        return {
            "post_id": self.post_id,
            "title": self.title,
            "body": self.body,
            "subreddit": self.subreddit,
            "label": self.label,
            "timestamp": self.timestamp,
            "scraped_at": self.scraped_at,
        }
