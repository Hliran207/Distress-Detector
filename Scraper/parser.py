from datetime import datetime, timezone
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException

from DB.models.Post import Post


class ShredditPostParser:
    """
    Parses data from a <shreddit-post> element.
    """

    @staticmethod
    def parse_post_element(element, subreddit: str, label: int) -> Optional[Post]:
        """
        Extract fields from a shreddit-post WebElement.
        Returns a Post object or None if it should be skipped.
        """
        try:
            post_id = element.get_attribute("id") or ""

            title = (element.get_attribute("post-title") or "").strip()

            body_div = element.find_element(
                By.CSS_SELECTOR,
                'div[property="schema:articleBody"]',
            )
            body = (body_div.text or "").strip()

            # Filter: skip body < 40 words
            word_count = len(body.split())
            if word_count < 40:
                return None

            timestamp_iso = None
            try:
                time_el = element.find_element(By.CSS_SELECTOR, "time")
                timestamp_iso = time_el.get_attribute("datetime") or time_el.text
            except Exception:
                # If no time element, leave timestamp as None
                pass

            scraped_at = datetime.now(timezone.utc).isoformat()

            return Post(
                post_id=post_id,
                title=title,
                body=body,
                subreddit=subreddit,
                label=label,
                timestamp=timestamp_iso,
                scraped_at=scraped_at,
            )
        except StaleElementReferenceException:
            return None
        except Exception:
            return None