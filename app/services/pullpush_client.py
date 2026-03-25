from typing import Any

import requests


PULLPUSH_SUBMISSION_SEARCH_URL = "https://api.pullpush.io/reddit/search/submission/"


class PullPushClient:
    def __init__(self, timeout_s: int = 30):
        self.session = requests.Session()
        self.timeout_s = timeout_s
        self.session.headers.update(
            {
                "User-Agent": "Distress-Detector/1.0 (pullpush-collector)",
                "Accept": "application/json",
            }
        )

    def fetch_submissions(self, subreddit: str, before_epoch: int, size: int = 100) -> list[dict[str, Any]]:
        params = {
            "subreddit": subreddit,
            "size": size,
            "sort": "desc",
            "sort_type": "created_utc",
            "before": before_epoch,
        }
        resp = self.session.get(
            PULLPUSH_SUBMISSION_SEARCH_URL,
            params=params,
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get("data") or []
        return data if isinstance(data, list) else []

