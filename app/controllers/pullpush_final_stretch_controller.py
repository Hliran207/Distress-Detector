import logging
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from app.models.pullpush import PullPushSubmission
from app.repositories.mongo_posts import MongoPostsRepository
from app.services.pullpush_client import PullPushClient
from app.views.cli_progress import CLIProgressView


def utc_iso_from_epoch_seconds(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()


def word_count(text: str) -> int:
    return len((text or "").split())


class PullPushFinalStretchController:
    """
    Controller: pulls label-0 text posts from PullPush and inserts exactly N new docs into Mongo.
    """

    def __init__(
        self,
        mongo_repo: MongoPostsRepository,
        pullpush: PullPushClient,
        view: CLIProgressView,
        subreddits: list[str],
        target_new_posts: int,
        min_selftext_words: int = 40,
        label: int = 0,
        page_size: int = 100,
        requests_backoff_s: int = 10,
    ):
        self.mongo_repo = mongo_repo
        self.pullpush = pullpush
        self.view = view
        self.subreddits = subreddits
        self.target_new_posts = target_new_posts
        self.min_selftext_words = min_selftext_words
        self.label = label
        self.page_size = page_size
        self.requests_backoff_s = requests_backoff_s

    def _resume_before_epoch(self) -> int:
        """
        Resume point: go older than what we already collected (for these subreddits + label).
        Uses the oldest `created_utc` present (min).
        """
        doc = self.mongo_repo.collection.find_one(
            {
                "label": self.label,
                "subreddit": {"$in": self.subreddits},
                "created_utc": {"$type": "number"},
            },
            sort=[("created_utc", 1)],
            projection={"created_utc": 1},
        )
        if doc and isinstance(doc.get("created_utc"), (int, float)):
            return int(doc["created_utc"])
        return int(time.time())

    def _parse_submission(self, raw: dict) -> Optional[PullPushSubmission]:
        post_id = str(raw.get("id") or "").strip()
        if not post_id:
            return None

        subreddit = str(raw.get("subreddit") or "").strip()
        title = str(raw.get("title") or "").strip()
        selftext = str(raw.get("selftext") or "").strip()

        created_utc_raw = raw.get("created_utc")
        if created_utc_raw is None:
            return None
        try:
            created_utc = int(created_utc_raw)
        except (TypeError, ValueError):
            return None

        if word_count(selftext) <= self.min_selftext_words:
            return None

        return PullPushSubmission(
            post_id=post_id,
            subreddit=subreddit,
            title=title,
            selftext=selftext,
            created_utc=created_utc,
        )

    def _to_mongo_doc(self, s: PullPushSubmission) -> dict:
        return {
            "post_id": s.post_id,  # keep compatibility with unique index
            "id": s.post_id,       # keep original PullPush field name too
            "title": s.title,
            "body": s.selftext,
            "selftext": s.selftext,
            "subreddit": s.subreddit,
            "label": self.label,
            "created_utc": s.created_utc,
            "timestamp": utc_iso_from_epoch_seconds(s.created_utc),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "source": "pullpush",
        }

    def run(self) -> None:
        collected_new = 0

        # Start from last timestamp used in previous run OR Jan 1, 2026
        jan1_2026_epoch = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
        before_epoch = max(self._resume_before_epoch(), jan1_2026_epoch)

        logging.info(
            f"Starting PullPush final stretch for label {self.label}. "
            f"Target new posts: {self.target_new_posts}. "
            f"Starting before={before_epoch} ({utc_iso_from_epoch_seconds(before_epoch)})."
        )

        while collected_new < self.target_new_posts:
            made_progress = False

            for subreddit in self.subreddits:
                if collected_new >= self.target_new_posts:
                    break

                try:
                    page = self.pullpush.fetch_submissions(
                        subreddit=subreddit,
                        before_epoch=before_epoch,
                        size=self.page_size,
                    )
                except requests.RequestException as e:
                    logging.warning(f"Request failed for r/{subreddit}: {e}. Backing off {self.requests_backoff_s}s.")
                    time.sleep(self.requests_backoff_s)
                    continue

                if not page:
                    continue

                created_ints: list[int] = []
                for p in page:
                    v = p.get("created_utc")
                    try:
                        created_ints.append(int(v))
                    except (TypeError, ValueError):
                        continue
                if created_ints:
                    before_epoch = min(before_epoch, min(created_ints))

                for raw in page:
                    if collected_new >= self.target_new_posts:
                        break

                    submission = self._parse_submission(raw)
                    if submission is None:
                        continue

                    if submission.created_utc < jan1_2026_epoch:
                        logging.info("Reached posts older than Jan 1, 2026. Stopping.")
                        return

                    if self.mongo_repo.exists_any_id(submission.post_id):
                        continue

                    inserted = self.mongo_repo.insert_raw(self._to_mongo_doc(submission))
                    if inserted:
                        collected_new += 1
                        made_progress = True
                        self.view.final_stretch(collected_new, self.target_new_posts, subreddit=subreddit)

                time.sleep(0.8)

            if not made_progress:
                before_epoch -= 60 * 10
                if before_epoch < jan1_2026_epoch:
                    logging.info("No more pages available within date window. Stopping.")
                    return
                logging.info("No new inserts this cycle. Moving further back in time and backing off 5s.")
                time.sleep(5)

