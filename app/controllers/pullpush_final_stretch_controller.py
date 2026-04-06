"""
PullPush.io collectors: turbo dataset re-collection (default) and legacy single-label stretch.

Run the turbo collector::

    python -m app.controllers.pullpush_final_stretch_controller

Reset only label 0 (delete all neutral posts, then re-collect 5,110 with ~1,022 per subreddit)::

    python -m app.controllers.pullpush_final_stretch_controller --reset-label0

Collect only label 0 (no delete; fills up to 5,110 with even caps across the five subs)::

    python -m app.controllers.pullpush_final_stretch_controller --label0-only
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import datetime, timezone
from collections import defaultdict
from itertools import cycle
from typing import TYPE_CHECKING, Any, Iterator, Optional

if TYPE_CHECKING:
    from app.models.pullpush import PullPushSubmission

import requests
from pymongo import MongoClient
from tqdm import tqdm

from app.mongo_config import COLLECTION_NAME, DB_NAME, load_mongo_uri
from app.repositories.mongo_posts import MongoPostsRepository
from app.services.pullpush_client import PullPushClient
from app.views.cli_progress import CLIProgressView

# --- Turbo collector defaults (10,220 posts total) ------------------------------------------------

PULLPUSH_TURBO_TARGET_PER_LABEL = 5_110
PULLPUSH_TURBO_PAGE_SIZE = 100
PULLPUSH_TURBO_SLEEP_S = 2.0
PULLPUSH_TURBO_MIN_WORDS = 20
PULLPUSH_TURBO_BULK_FLUSH = 100
PULLPUSH_TURBO_BACKOFF_EMPTY_S = 600

TURBO_LABEL_1_SUBREDDITS = (
    "depression",
    "anxiety",
    "suicidewatch",
    "lonely",
    "mentalhealth",
)
TURBO_LABEL_0_SUBREDDITS = (
    "askreddit",
    "casualconversation",
    "todayilearned",
    "LifeProTips",
    "explainlikeimfive",
)


def utc_iso_from_epoch_seconds(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()


def word_count(text: str) -> int:
    return len((text or "").split())


def normalize_subreddit(name: str) -> str:
    return name.strip().removeprefix("r/").lower()


def subreddit_quotas_for_total(
    normalized_subs: tuple[str, ...], total_needed: int
) -> dict[str, int]:
    """Split ``total_needed`` across subreddits as evenly as possible (larger shares first)."""
    n = len(normalized_subs)
    if n == 0 or total_needed <= 0:
        return {}
    base = total_needed // n
    rem = total_needed % n
    return {s: base + (1 if i < rem else 0) for i, s in enumerate(normalized_subs)}


def is_self_post(raw: dict[str, Any]) -> bool:
    v = raw.get("is_self")
    return v is True or v == 1


def load_dedup_ids(mongo_repo: MongoPostsRepository) -> set[str]:
    """All Reddit submission ids already stored (reddit_id, post_id, or legacy id)."""
    seen: set[str] = set()
    for doc in mongo_repo.collection.find(
        {}, {"reddit_id": 1, "post_id": 1, "id": 1}
    ).batch_size(2_000):
        for key in ("reddit_id", "post_id", "id"):
            val = doc.get(key)
            if val is not None and str(val).strip():
                seen.add(str(val).strip())
    return seen


def raw_to_turbo_doc(raw: dict[str, Any], label: int) -> Optional[dict[str, Any]]:
    if not is_self_post(raw):
        return None

    post_id = str(raw.get("id") or "").strip()
    if not post_id:
        return None

    selftext = str(raw.get("selftext") or "").strip()
    if not selftext:
        return None
    sl = selftext.lower()
    if sl in ("[removed]", "[deleted]"):
        return None

    if word_count(selftext) < PULLPUSH_TURBO_MIN_WORDS:
        return None

    created_raw = raw.get("created_utc")
    if created_raw is None:
        return None
    try:
        created_utc = int(created_raw)
    except (TypeError, ValueError):
        return None

    subreddit = str(raw.get("subreddit") or "").strip().lower()
    title = str(raw.get("title") or "").strip()
    scraped_at = datetime.now(timezone.utc).isoformat()

    return {
        "reddit_id": post_id,
        "post_id": post_id,
        "id": post_id,
        "title": title,
        "body": selftext,
        "selftext": selftext,
        "subreddit": subreddit,
        "label": label,
        "created_utc": created_utc,
        "timestamp": utc_iso_from_epoch_seconds(created_utc),
        "scraped_at": scraped_at,
        "source": "pullpush_turbo",
        "is_self": True,
    }


class PullPushTurboCollector:
    """
    High-throughput PullPush collector: two labels, per-subreddit `before` pagination,
    bulk `insert_many`, 1.2s between API calls, tqdm progress per label.
    Stops when each label reaches ``PULLPUSH_TURBO_TARGET_PER_LABEL`` documents in MongoDB.
    """

    def __init__(
        self,
        mongo_repo: MongoPostsRepository,
        pullpush: PullPushClient,
        *,
        target_per_label: int = PULLPUSH_TURBO_TARGET_PER_LABEL,
        page_size: int = PULLPUSH_TURBO_PAGE_SIZE,
        sleep_s: float = PULLPUSH_TURBO_SLEEP_S,
        backoff_empty_s: int = PULLPUSH_TURBO_BACKOFF_EMPTY_S,
    ) -> None:
        self.mongo_repo = mongo_repo
        self.pullpush = pullpush
        self.target_per_label = target_per_label
        self.page_size = page_size
        self.sleep_s = sleep_s
        self.backoff_empty_s = backoff_empty_s

    def _remaining_for_label(self, label: int) -> int:
        n = self.mongo_repo.collection.count_documents({"label": label})
        return max(0, self.target_per_label - n)

    def _collect_single_label(
        self,
        label: int,
        subreddits: tuple[str, ...],
        seen: set[str],
        *,
        even_subreddit_distribution: bool = False,
    ) -> None:
        needed = self._remaining_for_label(label)
        if needed <= 0:
            tqdm.write(
                f"Label {label}: already at {self.target_per_label:,} documents; skipping."
            )
            return

        if isinstance(subreddits, str):
            raise TypeError(
                "subreddits must be a tuple of names, not one str "
                "(iterating a string uses single letters as 'subreddits')."
            )

        normalized = tuple(normalize_subreddit(s) for s in subreddits)
        quota: Optional[dict[str, int]] = None
        inserted_per_sub: defaultdict[str, int] = defaultdict(int)
        buffer_counts: defaultdict[str, int] = defaultdict(int)

        if even_subreddit_distribution:
            quota = subreddit_quotas_for_total(normalized, needed)
            tqdm.write(
                f"Label {label}: per-subreddit caps (sum={needed:,}): "
                + ", ".join(f"r/{s}={quota[s]:,}" for s in normalized)
            )
            tqdm.write(
                "Each subreddit has a max share (roughly equal); no single sub can exceed its cap. "
                "Final counts may be below each cap if duplicates or filters block inserts."
            )
            tqdm.write(
                "Progress bar moves only after Mongo inserts. Early requests often yield 0 inserts "
                "(link posts filtered out, self-text min length, ids already in dedup set)."
            )

        before: dict[str, int] = {s: int(time.time()) for s in normalized}
        inserted_run = 0
        buffer: list[dict[str, Any]] = []

        pbar = tqdm(
            total=needed,
            desc=f"Label {label}",
            unit="post",
            dynamic_ncols=True,
        )

        sub_iter: Iterator[str] = cycle(normalized)
        rr = 0
        first_request = True
        fetch_count = 0

        def can_accept_sub(sub: str) -> bool:
            if not quota:
                return True
            cap = quota.get(sub, 0)
            return inserted_per_sub[sub] + buffer_counts[sub] < cap

        def subs_with_fetch_room() -> list[str]:
            if not quota:
                return list(normalized)
            return [s for s in normalized if can_accept_sub(s)]

        def flush_buffer() -> None:
            nonlocal inserted_run, buffer
            while buffer and inserted_run < needed:
                remaining_slots = needed - inserted_run
                chunk = buffer[:PULLPUSH_TURBO_BULK_FLUSH]
                if len(chunk) > remaining_slots:
                    chunk = chunk[:remaining_slots]
                buffer = buffer[len(chunk) :]
                if not chunk:
                    break
                for doc in chunk:
                    buffer_counts[doc["subreddit"]] -= 1
                n = self.mongo_repo.insert_many_raw(chunk)
                inserted_run += n
                for doc in chunk:
                    sub_d = doc["subreddit"]
                    inserted_per_sub[sub_d] += 1
                    seen.add(doc["reddit_id"])
                pbar.update(n)

        while inserted_run < needed:
            if quota:
                subs_room = subs_with_fetch_room()
                if not subs_room:
                    flush_buffer()
                    if inserted_run >= needed:
                        break
                    tqdm.write(
                        f"[Label {label}] No subreddit under its cap but total not reached; "
                        "stopping (check quotas / duplicates)."
                    )
                    break
                sub = subs_room[rr % len(subs_room)]
                rr += 1
            else:
                sub = next(sub_iter)

            if not first_request:
                time.sleep(self.sleep_s)
            first_request = False

            try:
                page = self.pullpush.fetch_submissions(
                    subreddit=sub,
                    before_epoch=before[sub],
                    size=self.page_size,
                )
            except requests.RequestException as e:
                logging.warning("PullPush request failed for r/%s: %s", sub, e)
                before[sub] = max(0, before[sub] - self.backoff_empty_s)
                continue

            fetch_count += 1
            if inserted_run == 0 and fetch_count in (3, 8, 15, 25, 40, 60, 90):
                tqdm.write(
                    f"[Label {label}] Still 0 inserts after {fetch_count} successful API pages "
                    f"(last r/{sub}). Pagination is moving backward in time; duplicates in DB are skipped."
                )

            if not page:
                before[sub] = max(0, before[sub] - self.backoff_empty_s)
                tqdm.write(
                    f"[Label {label}] Empty page for r/{sub}; moving `before` back {self.backoff_empty_s}s."
                )
                continue

            created_ints: list[int] = []
            for p in page:
                v = p.get("created_utc")
                try:
                    created_ints.append(int(v))
                except (TypeError, ValueError):
                    continue
            if created_ints:
                before[sub] = min(before[sub], min(created_ints))

            for raw in page:
                if inserted_run + len(buffer) >= needed:
                    break
                doc = raw_to_turbo_doc(raw, label)
                if doc is None:
                    continue
                rid = doc["reddit_id"]
                if rid in seen:
                    continue
                sub_d = doc["subreddit"]
                if quota and not can_accept_sub(sub_d):
                    continue
                buffer.append(doc)
                buffer_counts[sub_d] += 1

            flush_buffer()

        flush_buffer()
        pbar.close()

        final = self.mongo_repo.collection.count_documents({"label": label})
        tqdm.write(
            f"Label {label}: inserted {inserted_run:,} this run; collection now has {final:,} "
            f"with label={label} (target {self.target_per_label:,})."
        )
        if quota:
            parts = [f"r/{s}={inserted_per_sub[s]:,}/{quota[s]:,}" for s in normalized]
            tqdm.write(f"Label {label} per-subreddit: " + "  ".join(parts))

    def delete_posts_with_label(self, label: int) -> int:
        """Remove all documents with the given label (e.g. reset before re-collection)."""
        result = self.mongo_repo.collection.delete_many({"label": label})
        return int(result.deleted_count)

    def run(self, *, labels: Optional[set[int]] = None) -> None:
        """
        Collect until each selected label reaches ``target_per_label`` in MongoDB.

        ``labels``:
            ``None`` — collect label 1, then label 0 (full 10,220 run).
            ``{0}`` or ``{1}`` — only those labels (e.g. ``{0}`` after ``--reset-label0`` or
            ``--label0-only``). Label 0 uses per-subreddit **caps** (~one-fifth of the remaining
            quota each) so one subreddit cannot dominate; it does not guarantee each sub will
            reach its cap if duplicates or filters prevent inserts.
        """
        self.mongo_repo.ensure_indexes()
        seen = load_dedup_ids(self.mongo_repo)
        logging.info(
            "Turbo collector: loaded %s ids for deduplication.", f"{len(seen):,}"
        )

        run_labels = {0, 1} if labels is None else labels

        if 1 in run_labels:
            self._collect_single_label(1, TURBO_LABEL_1_SUBREDDITS, seen)
        if 0 in run_labels:
            self._collect_single_label(
                0,
                TURBO_LABEL_0_SUBREDDITS,
                seen,
                even_subreddit_distribution=True,
            )

        c1 = self.mongo_repo.collection.count_documents({"label": 1})
        c0 = self.mongo_repo.collection.count_documents({"label": 0})
        tqdm.write(f"Done. Totals — label 1: {c1:,}  |  label 0: {c0:,}")


# --- Legacy single-label stretch (kept for compatibility) -----------------------------------------


class PullPushFinalStretchController:
    """
    Legacy: pulls text posts from PullPush for one label and inserts up to N new docs.
    Prefer :class:`PullPushTurboCollector` for the full 10,220-post dataset.
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
    ) -> None:
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

    def _parse_submission(self, raw: dict) -> Optional["PullPushSubmission"]:
        from app.models.pullpush import PullPushSubmission

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

    def _to_mongo_doc(self, s: "PullPushSubmission") -> dict:
        return {
            "reddit_id": s.post_id,
            "post_id": s.post_id,
            "id": s.post_id,
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

        jan1_2026_epoch = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
        before_epoch = max(self._resume_before_epoch(), jan1_2026_epoch)

        logging.info(
            "Starting PullPush final stretch for label %s. Target new posts: %s. Starting before=%s (%s).",
            self.label,
            self.target_new_posts,
            before_epoch,
            utc_iso_from_epoch_seconds(before_epoch),
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
                    logging.warning(
                        "Request failed for r/%s: %s. Backing off %ss.",
                        subreddit,
                        e,
                        self.requests_backoff_s,
                    )
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

                    inserted = self.mongo_repo.insert_raw(
                        self._to_mongo_doc(submission)
                    )
                    if inserted:
                        collected_new += 1
                        made_progress = True
                        self.view.final_stretch(
                            collected_new, self.target_new_posts, subreddit=subreddit
                        )

                time.sleep(0.8)

            if not made_progress:
                before_epoch -= 60 * 10
                if before_epoch < jan1_2026_epoch:
                    logging.info(
                        "No more pages available within date window. Stopping."
                    )
                    return
                logging.info(
                    "No new inserts this cycle. Moving further back in time and backing off 5s."
                )
                time.sleep(5)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="PullPush turbo collector (Distress-Detector)."
    )
    parser.add_argument(
        "--reset-label0",
        action="store_true",
        help=(
            "Delete every document with label=0, then re-collect label 0 from the five "
            "TURBO_LABEL_0_SUBREDDITS until 5,110 total (~1,022 per subreddit). "
            "Does not change label 1."
        ),
    )
    parser.add_argument(
        "--label0-only",
        action="store_true",
        help=(
            "Collect only label 0 (skip label 1). No delete. Target 5,110 with even caps "
            "across the five neutral subreddits."
        ),
    )
    args = parser.parse_args()

    if args.reset_label0 and args.label0_only:
        parser.error("Use only one of --reset-label0 and --label0-only.")

    try:
        mongo_uri = load_mongo_uri()
    except RuntimeError:
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

    db_name = os.getenv("MONGO_DB_NAME", DB_NAME)

    print(
        f"MongoDB: {mongo_uri!r}  database={db_name!r}  collection={COLLECTION_NAME!r}"
    )
    client = MongoClient(mongo_uri)
    coll = client[db_name][COLLECTION_NAME]
    repo = MongoPostsRepository(coll)
    pullpush = PullPushClient(timeout_s=60)

    turbo = PullPushTurboCollector(repo, pullpush)

    if args.reset_label0:
        removed = turbo.delete_posts_with_label(0)
        print(f"Removed {removed:,} document(s) with label=0.")
        turbo.run(labels={0})
    elif args.label0_only:
        turbo.run(labels={0})
    else:
        turbo.run()

    client.close()


if __name__ == "__main__":
    main()
