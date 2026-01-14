# Playwright ile Organik Google Arama
# Organic Google Search with Playwright (Human-Like Behavior)

import asyncio
import random
import urllib.parse
from lib.output.consolePrint import p_error, p_info, p_warn, p_log

try:
    from playwright.sync_api import sync_playwright, Playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    p_warn(
        "Playwright not installed. Run: pip install playwright && playwright install chromium"
    )


def human_delay(min_sec=0.5, max_sec=2.0):
    """Simulates human-like random delay."""
    import time

    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


class GooglePlaywrightSearch:
    """
    Performs organic Google searches using Playwright with human-like behavior.
    Playwright is often more reliable than Selenium for modern web automation.
    """

    def __init__(self, headless=True):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is not installed. Run: pip install playwright && playwright install chromium"
            )
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

    def init_browser(self):
        p_info("Step 1: Initializing Playwright Browser...")
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            # Create context with realistic viewport and user agent
            self.context = self.browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
            )
            # Mask webdriver detection
            self.context.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """
            )
            self.page = self.context.new_page()
            p_info("Playwright browser initialized successfully.")
        except Exception as e:
            p_error(f"Failed to initialize Playwright browser: {e}")
            raise e

    def _human_type(self, selector: str, text: str):
        """Types text character by character with random delays."""
        for char in text:
            self.page.type(selector, char, delay=random.randint(80, 250))

    def _scroll_like_human(self):
        """Scrolls the page in a human-like manner."""
        scroll_amount = random.randint(200, 500)
        self.page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        human_delay(0.5, 1.5)

    def _accept_cookies(self):
        """Attempts to accept Google's cookie consent dialog."""
        try:
            human_delay(1, 2)
            selectors = [
                "button:has-text('Accept all')",
                "button:has-text('Tümünü kabul et')",
                "button:has-text('Accept')",
                "button:has-text('I agree')",
                "#L2AGLb",
            ]
            for selector in selectors:
                try:
                    if self.page.locator(selector).count() > 0:
                        self.page.click(selector, timeout=3000)
                        p_log("Cookie consent accepted.")
                        human_delay(0.5, 1)
                        return True
                except:
                    continue
        except:
            pass
        return False

    def search(self, query: str, num_results: int = 10) -> list[str]:
        """
        Performs an organic Google search and returns a list of result URLs.
        """
        if not self.page:
            self.init_browser()

        p_info(f"Step 2: Navigating to Google...")
        results = set()

        try:
            self.page.goto("https://www.google.com", wait_until="networkidle")
            human_delay(1.5, 3)

            self._accept_cookies()
            human_delay(0.5, 1.5)

            p_info(f"Step 3: Typing search query: '{query}'")

            # Find and click search box
            search_selectors = ["textarea[name='q']", "input[name='q']"]
            search_box = None
            for sel in search_selectors:
                if self.page.locator(sel).count() > 0:
                    search_box = sel
                    break

            if not search_box:
                p_error("Could not find search box on Google.")
                return list(results)

            self.page.click(search_box)
            human_delay(0.3, 0.8)

            # Type like a human
            self._human_type(search_box, query)
            human_delay(0.5, 1.5)

            # Press Enter
            self.page.press(search_box, "Enter")
            p_info("Step 4: Waiting for search results...")
            self.page.wait_for_load_state("networkidle")
            human_delay(2, 4)

            p_info("Step 5: Extracting URLs from search results...")

            page_count = 0
            max_pages = (num_results // 10) + 2

            while len(results) < num_results and page_count < max_pages:
                page_count += 1
                p_log(f"Processing page {page_count}...")

                # Scroll like human
                for _ in range(random.randint(2, 4)):
                    self._scroll_like_human()

                human_delay(1, 2)

                # Extract URLs using multiple robust methods
                # Use Playwright to extract links with JavaScript (most reliable)
                extracted_urls = self.page.evaluate(
                    """
                    () => {
                        const urls = new Set();
                        
                        // Method 1: Links with jsname attribute (Google's internal naming)
                        document.querySelectorAll('a[jsname]').forEach(a => {
                            const href = a.getAttribute('href');
                            if (href && href.startsWith('http') && !href.includes('google.com') && !href.includes('youtube.com')) {
                                urls.add(href);
                            }
                        });
                        
                        // Method 2: Links inside h3 elements (search result titles)
                        document.querySelectorAll('h3').forEach(h3 => {
                            const parent = h3.closest('a');
                            if (parent && parent.href) {
                                const href = parent.href;
                                if (href.startsWith('http') && !href.includes('google.com') && !href.includes('youtube.com')) {
                                    urls.add(href);
                                }
                            }
                        });
                        
                        // Method 3: Links with cite elements nearby (showing URL)
                        document.querySelectorAll('cite').forEach(cite => {
                            const container = cite.closest('div');
                            if (container) {
                                const link = container.querySelector('a[href^="http"]') || container.parentElement?.querySelector('a[href^="http"]');
                                if (link && link.href && !link.href.includes('google.com')) {
                                    urls.add(link.href);
                                }
                            }
                        });
                        
                        // Method 4: All links that look like search results
                        document.querySelectorAll('a[href^="http"]').forEach(a => {
                            const href = a.href;
                            // Filter out Google internal links and common non-result links
                            if (href && 
                                !href.includes('google.com') && 
                                !href.includes('youtube.com') &&
                                !href.includes('accounts.google') &&
                                !href.includes('support.google') &&
                                !href.includes('policies.google') &&
                                !href.includes('maps.google') &&
                                !href.includes('translate.google') &&
                                !href.startsWith('https://webcache.') &&
                                !href.includes('/search?') &&
                                !href.includes('javascript:')) {
                                // Check if this looks like a real result (has a parent with certain depth)
                                let parent = a.parentElement;
                                let depth = 0;
                                while (parent && depth < 10) {
                                    if (parent.tagName === 'DIV') depth++;
                                    parent = parent.parentElement;
                                }
                                if (depth >= 3) {
                                    urls.add(href);
                                }
                            }
                        });
                        
                        return Array.from(urls);
                    }
                """
                )

                for url in extracted_urls:
                    if url not in results:
                        results.add(url)

                p_log(f"Collected {len(results)}/{num_results} URLs so far...")

                if len(results) >= num_results:
                    break

                # Next page
                try:
                    next_btn = self.page.locator("#pnnext")
                    if next_btn.count() > 0:
                        next_btn.click()
                        p_log("Navigating to next page...")
                        self.page.wait_for_load_state("networkidle")
                        human_delay(2, 4)
                    else:
                        p_warn("No more pages available.")
                        break
                except:
                    break

        except Exception as e:
            p_error(f"Error during search: {e}")
        finally:
            self.close()

        p_info(f"Step 6: Search completed. Total unique URLs found: {len(results)}")
        return list(results)[:num_results]

    def close(self):
        """Closes the browser and cleans up resources."""
        p_info("Closing Playwright browser...")
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except:
            pass
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
