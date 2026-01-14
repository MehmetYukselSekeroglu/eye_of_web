#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Playwright-based Single Domain Crawler with Async Multi-Tab Support
# High-performance page crawler using Playwright async API

import asyncio
import concurrent.futures
import time
from typing import Optional
from urllib.parse import urlparse, unquote, urlunparse

from lib.output.consolePrint import p_info, p_error, p_warn, p_log
from lib.database_tools import DatabaseTools
from lib.url_parser import prepare_url
from lib.proccess_image import proccessImage
from lib.css_image_extractor import extract_css_background_images
from lib.linkedin.linkedin_profile_crawler import extract_linkedin_profile_picture
from HiveWebCrawler.Crawler import WebCrawler

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    p_warn(
        "Playwright not installed. Run: pip install playwright && playwright install chromium"
    )


class PlaywrightPageCrawler:
    """
    High-performance page crawler using Playwright async API with multi-tab support.

    Features:
    - Async/await for true parallel page loading
    - Multiple tabs running concurrently
    - Shared browser context for session management
    """

    def __init__(
        self,
        database_toolkit: DatabaseTools,
        insightface_app,
        headless: bool = True,
        num_tabs: int = 3,
        page_timeout: int = 30000,
    ):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright not installed")

        self.db_toolkit = database_toolkit
        self.insightface_app = insightface_app
        self.headless = headless
        self.num_tabs = num_tabs
        self.page_timeout = page_timeout

        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.crawler = WebCrawler()

        # Stats
        self.pages_crawled = 0
        self.images_processed = 0
        self.errors = 0

    async def _init_browser_async(self):
        """Initialize the browser and context asynchronously."""
        if self.browser:
            return

        p_info("Initializing Playwright browser (async mode)...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        # Mask automation
        await self.context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """
        )

        p_info(f"Browser initialized with {self.num_tabs} concurrent tabs ready.")

    async def _crawl_single_page_async(
        self,
        url: str,
        risk_level: str = None,
        category: str = None,
        save_image: bool = False,
    ) -> dict:
        """Crawl a single page asynchronously."""
        result = {
            "url": url,
            "success": False,
            "images_found": 0,
            "error": None,
        }

        page = None
        try:
            p_log(f"[Async] Crawling: {url}")

            # Create new page for this crawl
            page = await self.context.new_page()

            # Navigate to page
            await page.goto(
                url, wait_until="domcontentloaded", timeout=self.page_timeout
            )
            await asyncio.sleep(2)  # Wait for dynamic content

            # Get page source
            page_source = await page.content()

            # Parse URL
            parsed_url = prepare_url(url)

            # Extract data using existing crawler (sync operations, but fast)
            emails = self.crawler.crawl_email_address_from_response_href(page_source)
            phones = self.crawler.crawl_phone_number_from_response_href(page_source)
            images = self.crawler.crawl_image_from_response(
                page_source, parsed_url["base_domain"]
            )

            # Extract LinkedIn/embedded profile pictures
            linkedin_results = extract_linkedin_profile_picture(page_source)
            if linkedin_results:
                images["data_array"].append((linkedin_results, "Embed Picture"))

            # Extract CSS background images
            css_images = extract_css_background_images(url, page_source)

            # Prepare image list
            image_list = []
            for img in images.get("data_array", []):
                image_list.append(img)
            for css_img in css_images:
                if css_img not in [
                    i[0] if isinstance(i, (list, tuple)) else i for i in image_list
                ]:
                    image_list.append((css_img, None))

            # Remove duplicates (convert to tuple for hashing, then back to list for processing)
            image_list = list(set(map(tuple, image_list)))
            image_list = [list(item) for item in image_list]

            result["images_found"] = len(image_list)
            p_log(f"[Async] Found {len(image_list)} images in {url}")

            # Prepare email and phone lists
            email_list = [e[1] for e in emails.get("data_array", [])] or None
            phone_list = [p[1] for p in phones.get("data_array", [])] or None

            # Save to database (sync but fast)
            self.db_toolkit.insertPageBased(
                protocol=parsed_url["protocol"],
                baseDomain=parsed_url["base_domain"],
                urlPath=parsed_url["path"],
                urlPathEtc=parsed_url["etc"],
                phoneNumber_list=phone_list,
                emailAddress_list=email_list,
                categortyNmae=category,
            )

            # Process images in a thread pool (CPU-bound work)
            if image_list:
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    futures = [
                        loop.run_in_executor(
                            executor,
                            proccessImage,
                            img,
                            parsed_url,
                            self.db_toolkit,
                            self.insightface_app,
                            risk_level,
                            category,
                            save_image,
                        )
                        for img in image_list
                    ]
                    await asyncio.gather(*futures, return_exceptions=True)
                    self.images_processed += len(image_list)

            # Mark as crawled
            self.db_toolkit.insert_is_crawled(url)

            result["success"] = True
            self.pages_crawled += 1

        except Exception as e:
            result["error"] = str(e)
            self.errors += 1
            p_error(f"[Async] Error crawling {url}: {e}")
        finally:
            if page:
                try:
                    await page.close()
                except:
                    pass

        return result

    async def crawl_urls_async(
        self,
        urls: list[str],
        risk_level: str = None,
        category: str = None,
        save_image: bool = False,
    ) -> list[dict]:
        """
        Crawl multiple URLs with true async parallelism.

        Uses semaphore to limit concurrent tabs.
        """
        await self._init_browser_async()

        results = []
        semaphore = asyncio.Semaphore(self.num_tabs)

        async def crawl_with_semaphore(url):
            async with semaphore:
                return await self._crawl_single_page_async(
                    url, risk_level, category, save_image
                )

        p_info(
            f"Starting async crawl of {len(urls)} URLs with {self.num_tabs} concurrent tabs..."
        )

        # Create tasks for all URLs
        tasks = [asyncio.create_task(crawl_with_semaphore(url)) for url in urls]

        # Wait for all with progress
        for i, task in enumerate(asyncio.as_completed(tasks)):
            result = await task
            results.append(result)
            p_log(f"Progress: {i+1}/{len(urls)} URLs processed")

        p_info(f"Async crawl complete. Total: {len(results)}/{len(urls)}")
        return results

    def crawl_urls(
        self,
        urls: list[str],
        risk_level: str = None,
        category: str = None,
        save_image: bool = False,
        single_page: bool = True,
    ) -> list[dict]:
        """
        Synchronous wrapper for async crawl.
        """
        return asyncio.run(
            self.crawl_urls_async(urls, risk_level, category, save_image)
        )

    async def _close_async(self):
        """Close browser asynchronously."""
        p_info("Closing Playwright browser...")
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except:
            pass

        self.context = None
        self.browser = None
        self.playwright = None

        p_info(
            f"Crawl stats: {self.pages_crawled} pages, {self.images_processed} images, {self.errors} errors"
        )

    def close(self):
        """Sync wrapper for close."""
        try:
            asyncio.run(self._close_async())
        except:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def crawl_with_playwright(
    urls: list[str],
    database_toolkit: DatabaseTools,
    insightface_app,
    headless: bool = True,
    num_tabs: int = 3,
    risk_level: str = None,
    category: str = None,
    save_image: bool = False,
) -> list[dict]:
    """
    Convenience function to crawl URLs with Playwright async.
    """
    crawler = PlaywrightPageCrawler(
        database_toolkit=database_toolkit,
        insightface_app=insightface_app,
        headless=headless,
        num_tabs=num_tabs,
    )
    try:
        return crawler.crawl_urls(
            urls=urls,
            risk_level=risk_level,
            category=category,
            save_image=save_image,
        )
    finally:
        crawler.close()
