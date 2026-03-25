import logging


class ScraperCLIView:
    def subreddit_start(self, subreddit: str, label: int) -> None:
        logging.info(f"Starting subreddit {subreddit} with label {label}")

    def subreddit_progress(self, subreddit: str, collected: int, target: int) -> None:
        logging.info(f"Subreddit {subreddit}: Collected {collected}/{target} posts")

    def subreddit_skip(self, subreddit: str, already_collected: int, max_per_subreddit: int) -> None:
        logging.info(
            f"Subreddit {subreddit}: already has {already_collected} posts (max={max_per_subreddit}), skipping."
        )

    def subreddit_timeout(self, subreddit: str) -> None:
        logging.warning(f"Timed out waiting for posts on r/{subreddit}")

    def subreddit_finished(self, subreddit: str, collected_total: int, max_per_subreddit: int) -> None:
        logging.info(
            f"Finished r/{subreddit}: collected {collected_total} posts total (max={max_per_subreddit})"
        )

    def cooldown(self) -> None:
        logging.info("Cooling down before next subreddit...")

