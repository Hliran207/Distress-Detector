import logging
import time
from typing import Any

import requests


PULLPUSH_SUBMISSION_SEARCH_URL = "https://api.pullpush.io/reddit/search/submission/"

# PullPush returns 429 when rate-limited; retry with backoff instead of failing one-off.
PULLPUSH_429_MAX_ATTEMPTS = 15
PULLPUSH_429_FALLBACK_WAIT_S = 8.0
PULLPUSH_429_WAIT_CAP_S = 300.0


def _sleep_seconds_after_429(resp: requests.Response, fallback: float) -> float:
    raw = resp.headers.get("Retry-After")
    if not raw:
        return min(fallback, PULLPUSH_429_WAIT_CAP_S)
    try:
        return min(float(raw), PULLPUSH_429_WAIT_CAP_S)
    except (TypeError, ValueError):
        return min(fallback, PULLPUSH_429_WAIT_CAP_S)


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
        fallback_wait = PULLPUSH_429_FALLBACK_WAIT_S
        for attempt in range(1, PULLPUSH_429_MAX_ATTEMPTS + 1):
            resp = self.session.get(
                PULLPUSH_SUBMISSION_SEARCH_URL,
                params=params,
                timeout=self.timeout_s,
            )
            if resp.status_code == 429:
                wait_s = _sleep_seconds_after_429(resp, fallback_wait)
                logging.warning(
                    "PullPush rate limit (429) for r/%s; waiting %.0fs then retry %s/%s.",
                    subreddit,
                    wait_s,
                    attempt,
                    PULLPUSH_429_MAX_ATTEMPTS,
                )
                if attempt == PULLPUSH_429_MAX_ATTEMPTS:
                    resp.raise_for_status()
                time.sleep(wait_s)
                fallback_wait = min(fallback_wait * 1.4, 120.0)
                continue
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("data") or []
            return data if isinstance(data, list) else []

