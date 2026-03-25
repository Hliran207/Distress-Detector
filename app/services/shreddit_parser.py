from datetime import datetime, timezone
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException

from app.models.post import Post


class ShredditPostParser:
    """
    Service that parses data from a <shreddit-post> WebElement into a Post model.
    """

    @staticmethod
    def parse_post_element(element, subreddit: str, label: int) -> Optional[Post]:
        try:
            post_id = element.get_attribute("id") or ""

            title = (element.get_attribute("post-title") or "").strip()

            body_div = element.find_element(
                By.CSS_SELECTOR,
                'div[property="schema:articleBody"]',
            )
            body = (body_div.text or "").strip()

            # Filter: skip body < 40 words
            if len(body.split()) < 40:
                return None

            timestamp_iso = None
            try:
                time_el = element.find_element(By.CSS_SELECTOR, "time")
                timestamp_iso = time_el.get_attribute("datetime") or time_el.text
            except Exception:
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

