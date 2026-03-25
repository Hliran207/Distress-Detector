import random
import time
from dataclasses import dataclass
from typing import Dict, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchWindowException,
    WebDriverException,
)

from app.repositories.mongo_posts import MongoPostsRepository
from app.services.chrome_driver import ChromeDriverConfig, ChromeDriverFactory
from app.services.shreddit_parser import ShredditPostParser
from app.views.scraper_view import ScraperCLIView


@dataclass(frozen=True)
class RedditScrapeConfig:
    subreddits_with_label: Dict[str, int]
    max_per_subreddit: int = 1000
    headless: bool = True
    user_data_dir: Optional[str] = None
    version_main: int = 145
    wait_for_posts_s: int = 40
    base_sleep_min_s: float = 3.0
    base_sleep_max_s: float = 10.0
    long_break_every_n_posts: int = 20
    long_break_min_s: float = 5.0
    long_break_max_s: float = 15.0
    cooldown_min_s: float = 20.0
    cooldown_max_s: float = 40.0
    max_no_new_scrolls: int = 5


class RedditScraperController:
    def __init__(
        self,
        mongo_repo: MongoPostsRepository,
        parser: ShredditPostParser,
        view: ScraperCLIView,
        config: RedditScrapeConfig,
    ):
        self.mongo_repo = mongo_repo
        self.parser = parser
        self.view = view
        self.config = config

        self.driver = None

    def _sleep(self, min_s: float, max_s: float) -> None:
        time.sleep(random.uniform(min_s, max_s))

    def run(self) -> None:
        chrome_config = ChromeDriverConfig(
            headless=self.config.headless,
            user_data_dir=self.config.user_data_dir,
            version_main=self.config.version_main,
            page_load_timeout_s=60,
        )
        self.driver = ChromeDriverFactory.create(chrome_config)

        try:
            for subreddit, label in self.config.subreddits_with_label.items():
                self.view.subreddit_start(subreddit, label)
                try:
                    self._scrape_subreddit(subreddit, label)
                except Exception:
                    # Let caller see stacktrace via logging.exception if they want;
                    # controller should continue to next subreddit when possible.
                    raise

                self.view.cooldown()
                self._sleep(self.config.cooldown_min_s, self.config.cooldown_max_s)
        finally:
            if self.driver is not None:
                self.driver.quit()

    def _scrape_subreddit(self, subreddit: str, label: int) -> None:
        assert self.driver is not None

        already_collected = self.mongo_repo.count_posts_for_subreddit(subreddit)
        if already_collected >= self.config.max_per_subreddit:
            self.view.subreddit_skip(subreddit, already_collected, self.config.max_per_subreddit)
            return

        url = f"https://www.reddit.com/r/{subreddit}/"
        try:
            self.driver.get(url)
        except (NoSuchWindowException, WebDriverException):
            return

        try:
            WebDriverWait(self.driver, self.config.wait_for_posts_s).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "shreddit-post"))
            )
        except TimeoutException:
            self.view.subreddit_timeout(subreddit)
            return

        collected = already_collected
        seen_ids: set[str] = set()
        no_new_post_scrolls = 0

        while collected < self.config.max_per_subreddit and no_new_post_scrolls < self.config.max_no_new_scrolls:
            posts = self.driver.find_elements(By.CSS_SELECTOR, "shreddit-post")
            new_posts_this_round = 0

            for post_el in posts:
                try:
                    post_id = post_el.get_attribute("id")
                    if not post_id or post_id in seen_ids:
                        continue

                    post = self.parser.parse_post_element(post_el, subreddit=subreddit, label=label)
                    seen_ids.add(post_id)
                    if post is None:
                        continue

                    if self.mongo_repo.insert_post(post):
                        collected += 1
                        new_posts_this_round += 1
                        self.view.subreddit_progress(subreddit, collected, self.config.max_per_subreddit)

                        if (
                            self.config.long_break_every_n_posts > 0
                            and collected % self.config.long_break_every_n_posts == 0
                        ):
                            self._sleep(self.config.long_break_min_s, self.config.long_break_max_s)

                        if collected >= self.config.max_per_subreddit:
                            break
                except StaleElementReferenceException:
                    continue
                except NoSuchWindowException:
                    return

            if new_posts_this_round == 0:
                no_new_post_scrolls += 1
            else:
                no_new_post_scrolls = 0

            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except NoSuchWindowException:
                return

            self._sleep(self.config.base_sleep_min_s, self.config.base_sleep_max_s)

        self.view.subreddit_finished(subreddit, collected, self.config.max_per_subreddit)

