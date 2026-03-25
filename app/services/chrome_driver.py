import logging
import os
from dataclasses import dataclass
from typing import Optional

import undetected_chromedriver as uc
from selenium.common.exceptions import WebDriverException


@dataclass(frozen=True)
class ChromeDriverConfig:
    headless: bool = True
    user_data_dir: Optional[str] = None
    version_main: int = 145
    page_load_timeout_s: int = 60


class ChromeDriverFactory:
    @staticmethod
    def create(config: ChromeDriverConfig):
        options = uc.ChromeOptions()

        if config.user_data_dir:
            os.makedirs(config.user_data_dir, exist_ok=True)
            if config.headless:
                logging.info("Using Chrome profile: headless disabled.")
        elif config.headless:
            options.add_argument("--headless=new")

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--start-maximized")

        if config.user_data_dir:
            driver = uc.Chrome(
                options=options,
                version_main=config.version_main,
                user_data_dir=os.path.abspath(config.user_data_dir),
            )
        else:
            driver = uc.Chrome(options=options, version_main=config.version_main)

        driver.set_page_load_timeout(config.page_load_timeout_s)
        try:
            logging.info("Chrome started, navigating to reddit.com ...")
            driver.get("https://www.reddit.com/")
            logging.info(f"Landing page loaded: {driver.current_url}")
        except WebDriverException as e:
            logging.warning(f"Initial navigation failed: {e}")

        return driver

