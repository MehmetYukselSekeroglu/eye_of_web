# High-Performance Playwright Facebook Crawler
# Multi-browser and multi-tab support for maximum speed

import asyncio
import aiohttp
import os
import re
import time
from urllib.parse import urljoin, urlparse, unquote, quote
from bs4 import BeautifulSoup
from lib.output.consolePrint import p_error, p_info, p_warn, p_log
import typing

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class PlaywrightFacebookCrawler:
    """
    High-performance Facebook crawler using Playwright with multi-browser
    and multi-tab parallelization for maximum crawling speed.

    Performance Features:
    - Multiple browser contexts for isolation
    - Multiple tabs per context for parallel profile loading
    - Async/await for non-blocking I/O
    - Batch processing with configurable concurrency
    - Optimized page load strategies (no images/CSS for speed)
    """

    DEFAULT_IMAGE_EXTENSION = ".jpg"

    # Performance presets
    PRESETS = {
        "conservative": {
            "browsers": 1,
            "tabs_per_browser": 2,
            "concurrent_downloads": 4,
        },
        "balanced": {"browsers": 2, "tabs_per_browser": 4, "concurrent_downloads": 8},
        "aggressive": {
            "browsers": 3,
            "tabs_per_browser": 6,
            "concurrent_downloads": 16,
        },
        "maximum": {"browsers": 4, "tabs_per_browser": 8, "concurrent_downloads": 32},
    }

    def __init__(
        self,
        headless: bool = True,
        preset: str = "aggressive",
        scroll_count: int = 5,
        scroll_pause_time: float = 1.0,
        download_folder: str = "downloaded_profile_pics",
    ):
        """
        Initialize the high-performance Facebook crawler.

        Args:
            headless: Run browsers in headless mode
            preset: Performance preset ('conservative', 'balanced', 'aggressive', 'maximum')
            scroll_count: Number of scrolls on search results page
            scroll_pause_time: Pause between scrolls (seconds)
            download_folder: Folder for downloaded images
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )

        self.headless = headless
        self.scroll_count = scroll_count
        self.scroll_pause_time = scroll_pause_time
        self.download_folder = download_folder
        self.base_url = "https://www.facebook.com"

        # Apply preset
        config = self.PRESETS.get(preset, self.PRESETS["aggressive"])
        self.num_browsers = config["browsers"]
        self.tabs_per_browser = config["tabs_per_browser"]
        self.concurrent_downloads = config["concurrent_downloads"]

        self.playwright = None
        self.browsers: list[Browser] = []
        self.contexts: list[BrowserContext] = []

        # Stats
        self.stats = {
            "profiles_found": 0,
            "profiles_processed": 0,
            "images_downloaded": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }

        # Create download folder
        os.makedirs(self.download_folder, exist_ok=True)

        p_info(f"Facebook Playwright Crawler initialized with preset: {preset}")
        p_info(
            f"  Browsers: {self.num_browsers}, Tabs/Browser: {self.tabs_per_browser}, Concurrent Downloads: {self.concurrent_downloads}"
        )

    async def _init_browsers(self):
        """Initialize multiple browser instances for parallel processing."""
        p_info(f"Step 1: Initializing {self.num_browsers} browser(s)...")

        self.playwright = await async_playwright().start()

        for i in range(self.num_browsers):
            browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-extensions",
                    "--disable-gpu",
                ],
            )
            self.browsers.append(browser)

            # Create context with optimized settings
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="tr-TR",
            )

            # Block unnecessary resources for speed
            await context.route(
                "**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2}",
                lambda route: route.abort(),
            )
            await context.route("**/*analytics*", lambda route: route.abort())
            await context.route("**/*tracking*", lambda route: route.abort())

            # Mask automation detection
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            self.contexts.append(context)
            p_log(f"  Browser {i+1}/{self.num_browsers} initialized")

        p_info("All browsers initialized successfully.")

    def _clean_filename(self, filename: str) -> str:
        """Clean filename for safe file system usage."""
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        return filename.strip(". ")[:100]

    def _get_username_from_url(self, profile_url: str) -> str:
        """Extract username from profile URL."""
        try:
            parsed = urlparse(profile_url)
            path = unquote(parsed.path).strip("/")
            parts = path.split("/")

            if "people" in parts:
                idx = parts.index("people")
                if len(parts) > idx + 1:
                    return parts[idx + 1]
            if "profile.php" in path:
                query = dict(q.split("=") for q in parsed.query.split("&") if "=" in q)
                return query.get("id", parts[-1])
            return parts[-1] if parts else "unknown"
        except:
            return "unknown"

    async def _scroll_and_collect_profiles(
        self, page: Page, search_url: str
    ) -> list[dict]:
        """Scroll through search results and collect profile links."""
        p_info(f"Step 2: Loading search results: {search_url}")

        await page.goto(search_url, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # Accept cookies if present
        try:
            accept_btn = page.locator(
                "button:has-text('Allow'), button:has-text('Accept'), button:has-text('Kabul')"
            )
            if await accept_btn.count() > 0:
                await accept_btn.first.click()
                await asyncio.sleep(1)
        except:
            pass

        p_info(f"Step 3: Scrolling {self.scroll_count} times to load more results...")

        for i in range(self.scroll_count):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            p_log(f"  Scroll {i+1}/{self.scroll_count}")
            await asyncio.sleep(self.scroll_pause_time)

        # Extract profile links
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        profiles = []
        seen_urls = set()

        # Find profile links
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "/people/" in href or "/profile.php" in href:
                full_url = urljoin(self.base_url, href)
                if full_url not in seen_urls and "facebook.com" in full_url:
                    seen_urls.add(full_url)
                    profiles.append(
                        {
                            "profile_url": full_url,
                            "username": self._get_username_from_url(full_url),
                        }
                    )

        # Also try alternative selectors
        for container in soup.find_all("div", class_=["_3u1", "_gli", "_4p2o"]):
            link = container.find("a", href=True)
            if link:
                href = link["href"]
                full_url = urljoin(self.base_url, href)
                if full_url not in seen_urls and "facebook.com" in full_url:
                    seen_urls.add(full_url)
                    profiles.append(
                        {
                            "profile_url": full_url,
                            "username": self._get_username_from_url(full_url),
                        }
                    )

        self.stats["profiles_found"] = len(profiles)
        p_info(f"Found {len(profiles)} unique profile URLs")

        return profiles

    async def _process_profile(self, page: Page, profile: dict) -> dict:
        """Process a single profile to extract main image URL."""
        profile_url = profile["profile_url"]
        result = {
            **profile,
            "main_image_url": None,
            "status": "pending",
            "error": None,
        }

        try:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(1)

            # Try to get og:image
            og_image = await page.evaluate(
                """
                () => {
                    const meta = document.querySelector('meta[property="og:image"]');
                    return meta ? meta.getAttribute('content') : null;
                }
            """
            )

            if og_image:
                result["main_image_url"] = og_image.replace("&amp;", "&")
                result["status"] = "image_found"
            else:
                result["status"] = "no_image"

            self.stats["profiles_processed"] += 1

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            self.stats["errors"] += 1

        return result

    async def _process_profiles_parallel(self, profiles: list[dict]) -> list[dict]:
        """Process multiple profiles in parallel using multiple tabs."""
        p_info(f"Step 4: Processing {len(profiles)} profiles in parallel...")

        results = []
        semaphore = asyncio.Semaphore(self.num_browsers * self.tabs_per_browser)

        async def process_with_semaphore(profile: dict, context_idx: int):
            async with semaphore:
                context = self.contexts[context_idx % len(self.contexts)]
                page = await context.new_page()
                try:
                    result = await self._process_profile(page, profile)
                    return result
                finally:
                    await page.close()

        # Create tasks for all profiles
        tasks = []
        for i, profile in enumerate(profiles):
            task = asyncio.create_task(process_with_semaphore(profile, i))
            tasks.append(task)

        # Process with progress reporting
        for i, task in enumerate(asyncio.as_completed(tasks)):
            result = await task
            results.append(result)
            if (i + 1) % 10 == 0 or i + 1 == len(profiles):
                p_log(f"  Processed {i+1}/{len(profiles)} profiles")

        return results

    async def _download_images_parallel(self, profiles: list[dict]) -> list[dict]:
        """Download profile images in parallel using aiohttp."""
        profiles_with_images = [p for p in profiles if p.get("main_image_url")]

        if not profiles_with_images:
            p_warn("No images to download.")
            return profiles

        p_info(f"Step 5: Downloading {len(profiles_with_images)} images in parallel...")

        semaphore = asyncio.Semaphore(self.concurrent_downloads)

        async def download_image(session: aiohttp.ClientSession, profile: dict):
            async with semaphore:
                try:
                    url = profile["main_image_url"]
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=20)
                    ) as response:
                        if response.status == 200:
                            content = await response.read()

                            # Determine extension
                            content_type = response.headers.get("content-type", "")
                            if "png" in content_type:
                                ext = ".png"
                            elif "gif" in content_type:
                                ext = ".gif"
                            else:
                                ext = ".jpg"

                            filename = (
                                f"{self._clean_filename(profile['username'])}{ext}"
                            )
                            filepath = os.path.join(self.download_folder, filename)

                            with open(filepath, "wb") as f:
                                f.write(content)

                            profile["downloaded_path"] = filepath
                            profile["download_status"] = "success"
                            self.stats["images_downloaded"] += 1
                        else:
                            profile["download_status"] = f"failed_{response.status}"
                except Exception as e:
                    profile["download_status"] = f"error: {str(e)}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            tasks = [download_image(session, p) for p in profiles_with_images]
            await asyncio.gather(*tasks)

        p_info(f"Downloaded {self.stats['images_downloaded']} images")

        return profiles

    async def crawl_search_async(self, keyword: str) -> list[dict]:
        """
        Main async crawl method for Facebook profile search.

        Args:
            keyword: Search keyword for Facebook people search

        Returns:
            List of profile dictionaries with image data
        """
        self.stats["start_time"] = time.time()

        try:
            await self._init_browsers()

            # Use first context's page for search
            page = await self.contexts[0].new_page()

            # Build search URL
            search_query = quote(keyword)
            search_url = f"https://www.facebook.com/public/{search_query}"

            # Collect profiles
            profiles = await self._scroll_and_collect_profiles(page, search_url)
            await page.close()

            if not profiles:
                p_warn("No profiles found.")
                return []

            # Process profiles in parallel
            results = await self._process_profiles_parallel(profiles)

            # Download images in parallel
            results = await self._download_images_parallel(results)

            return results

        finally:
            await self._cleanup()
            self.stats["end_time"] = time.time()
            self._print_stats()

    def crawl_search(self, keyword: str) -> list[dict]:
        """
        Synchronous wrapper for crawl_search_async.

        Args:
            keyword: Search keyword for Facebook people search

        Returns:
            List of profile dictionaries with image data
        """
        return asyncio.run(self.crawl_search_async(keyword))

    async def _cleanup(self):
        """Clean up all browser resources."""
        p_info("Closing all browsers...")
        for context in self.contexts:
            try:
                await context.close()
            except:
                pass
        for browser in self.browsers:
            try:
                await browser.close()
            except:
                pass
        if self.playwright:
            await self.playwright.stop()

        self.contexts = []
        self.browsers = []
        self.playwright = None

    def _print_stats(self):
        """Print crawling statistics."""
        duration = (self.stats["end_time"] or time.time()) - (
            self.stats["start_time"] or time.time()
        )

        p_info("=" * 50)
        p_info("CRAWL STATISTICS")
        p_info("=" * 50)
        p_info(f"  Duration: {duration:.2f} seconds")
        p_info(f"  Profiles Found: {self.stats['profiles_found']}")
        p_info(f"  Profiles Processed: {self.stats['profiles_processed']}")
        p_info(f"  Images Downloaded: {self.stats['images_downloaded']}")
        p_info(f"  Errors: {self.stats['errors']}")
        if duration > 0 and self.stats["profiles_processed"] > 0:
            p_info(
                f"  Speed: {self.stats['profiles_processed'] / duration:.2f} profiles/second"
            )
        p_info("=" * 50)

    def get_profile_image_data(self, profile_url: str) -> typing.Tuple[bytes, str]:
        """
        Get profile image data as binary for database storage.

        Args:
            profile_url: Facebook profile URL

        Returns:
            Tuple of (image_bytes, extension) or (None, None) if failed
        """

        async def _get_image():
            await self._init_browsers()
            try:
                page = await self.contexts[0].new_page()
                profile = {
                    "profile_url": profile_url,
                    "username": self._get_username_from_url(profile_url),
                }
                result = await self._process_profile(page, profile)
                await page.close()

                if result.get("main_image_url"):
                    import aiohttp

                    async with aiohttp.ClientSession() as session:
                        async with session.get(result["main_image_url"]) as resp:
                            if resp.status == 200:
                                content = await resp.read()
                                content_type = resp.headers.get("content-type", "")
                                ext = ".png" if "png" in content_type else ".jpg"
                                return content, ext
                return None, None
            finally:
                await self._cleanup()

        return asyncio.run(_get_image())
