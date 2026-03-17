import logging
import os
import random
import time
from typing import Dict, Optional
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from DB.config import get_mongo_collection
from DB.repository import MongoPostRepository
from Scraper.parser import ShredditPostParser


class RedditScraper:
    """
    Uses undetected-chromedriver to scrape subreddits and store posts in MongoDB.
    """

    def __init__(
        self,
        mongo_repo: MongoPostRepository,
        subreddits_with_label: Dict[str, int],
        max_per_subreddit: int = 1000,
        batch_size: int = 100,
        headless: bool = True,
        user_data_dir: Optional[str] = None,
    ):
        self.mongo_repo = mongo_repo
        self.subreddits_with_label = subreddits_with_label
        self.max_per_subreddit = max_per_subreddit
        self.batch_size = batch_size
        self.headless = headless
        self.user_data_dir = user_data_dir
        self.driver = None

    def _init_driver(self):
        options = uc.ChromeOptions()
        if self.user_data_dir:
            # Persisted profile: log in to Reddit once in this browser; session is reused.
            os.makedirs(self.user_data_dir, exist_ok=True)
            # Chrome does not support headless when using a user data dir.
            if self.headless:
                logging.info("Using Chrome profile: headless disabled.")
        elif self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # Pin to current Chrome major version (145). Update or remove
        # version_main if you upgrade Chrome in the future.
        if self.user_data_dir:
            self.driver = uc.Chrome(
                options=options,
                version_main=145,
                user_data_dir=os.path.abspath(self.user_data_dir),
            )
        else:
            self.driver = uc.Chrome(options=options, version_main=145)

    @staticmethod
    def _random_sleep(min_sec: float = 3.0, max_sec: float = 10.0):
        time.sleep(random.uniform(min_sec, max_sec))

    def _scrape_subreddit(self, subreddit: str, label: int):
        assert self.driver is not None

        already_collected = self.mongo_repo.count_posts_for_subreddit(subreddit)
        if already_collected >= self.max_per_subreddit:
            logging.info(
                f"Subreddit {subreddit}: already has {already_collected} posts "
                f"(max={self.max_per_subreddit}), skipping."
            )
            return

        url = f"https://www.reddit.com/r/{subreddit}/"
        logging.info(f"Opening {url}")
        self.driver.get(url)
        try:
            WebDriverWait(self.driver, 40).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "shreddit-post"))
            )
        except TimeoutException:
            logging.warning(f"Timed out waiting for posts on r/{subreddit}")
            return
        collected = already_collected
        seen_ids: set[str] = set()
        no_new_post_scrolls = 0
        max_no_new_scrolls = 5
        while (
            collected < self.max_per_subreddit
            and no_new_post_scrolls < max_no_new_scrolls
        ):
            posts = self.driver.find_elements(By.CSS_SELECTOR, "shreddit-post")
            new_posts_this_round = 0
            for post_el in posts:
                try:
                    post_id = post_el.get_attribute("id")
                    if not post_id or post_id in seen_ids:
                        continue
                    post = ShredditPostParser.parse_post_element(
                        post_el, subreddit=subreddit, label=label
                    )
                    seen_ids.add(post_id)
                    if post is None:
                        continue
                    inserted = self.mongo_repo.insert_post(post)
                    if inserted:
                        collected += 1
                        new_posts_this_round += 1
                        logging.info(
                            f"Subreddit {subreddit}: Collected {collected}/{self.max_per_subreddit} posts"
                        )

                        # Take a slightly longer break every 20 successful posts
                        if collected % 20 == 0:
                            self._random_sleep(5.0, 15.0)

                        if collected >= self.max_per_subreddit:
                            break
                except StaleElementReferenceException:
                    # DOM updated (e.g. infinite scroll); skip this element, re-fetch next loop
                    continue
            if new_posts_this_round == 0:
                no_new_post_scrolls += 1
            else:
                no_new_post_scrolls = 0
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            self._random_sleep()
        logging.info(
            f"Finished r/{subreddit}: collected {collected} posts total "
            f"(max={self.max_per_subreddit})"
        )

    def run(self):
        self._init_driver()
        try:
            for subreddit, label in self.subreddits_with_label.items():
                try:
                    logging.info(f"Starting subreddit {subreddit} with label {label}")
                    self._scrape_subreddit(subreddit, label)
                except Exception as e:
                    logging.exception(f"Error while scraping r/{subreddit}: {e}")

                # Cooldown between subreddits to reduce rate limiting
                logging.info("Cooling down before next subreddit...")
                self._random_sleep(20.0, 40.0)
        finally:
            if self.driver is not None:
                self.driver.quit()


def build_subreddit_label_mapping() -> Dict[str, int]:
    distress_subreddits = [
        "lonely",
        "depression",
        "Anxiety",
        "MentalHealth",
        "SuicideWatch",
    ]
    control_subreddits = [
        "CasualConversation",
        "LifeProTips",
        "movies",
        "hobbies",
        "technology",
    ]
    mapping: Dict[str, int] = {}
    for sub in control_subreddits:
        mapping[sub] = 0
    for sub in distress_subreddits:
        mapping[sub] = 1
    return mapping


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    collection = get_mongo_collection()
    mongo_repo = MongoPostRepository(collection)
    subreddits_with_label = build_subreddit_label_mapping()

    # Persisted Chrome profile: first run opens Reddit so you can log in;
    # later runs reuse the same profile and stay logged in (fewer blocks).
    profile_dir = os.path.join(os.getcwd(), "reddit_scraper_profile")

    scraper = RedditScraper(
        mongo_repo=mongo_repo,
        subreddits_with_label=subreddits_with_label,
        max_per_subreddit=1000,
        batch_size=100,
        headless=False,
        user_data_dir=profile_dir,
    )
    scraper.run()


if __name__ == "__main__":
    main()
