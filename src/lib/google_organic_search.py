# Hümanlık Davranışı ile Organik Google Arama
# Organic Google Search with Human-Like Behavior

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import random
import urllib.parse
from lib.output.consolePrint import p_error, p_info, p_warn, p_log
from lib.selenium_tools.selenium_browser import get_chrome_driver


def human_delay(min_sec=0.5, max_sec=2.0):
    """Simulates human-like random delay."""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def human_type(element, text, min_delay=0.05, max_delay=0.2):
    """
    Types text into an element character by character with random delays,
    simulating human typing behavior.
    """
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(min_delay, max_delay))


class GoogleOrganicSearch:
    """
    Performs organic Google searches using Selenium with human-like behavior
    to avoid robot detection systems.
    """

    def __init__(self, headless=True, temp_folder="temp"):
        self.headless = headless
        self.temp_folder = temp_folder
        self.driver = None

    def init_driver(self):
        p_info("Step 1: Initializing Browser for Organic Search...")
        try:
            self.driver = get_chrome_driver(
                headless=self.headless, temp_base_dir=self.temp_folder
            )
            # Set a longer implicit wait for elements
            self.driver.implicitly_wait(10)
            p_info("Browser initialized successfully.")
        except Exception as e:
            p_error(f"Failed to initialize browser: {e}")
            raise e

    def _accept_cookies(self):
        """Attempts to accept Google's cookie consent dialog."""
        try:
            human_delay(1, 2)
            # Try multiple selectors for different languages/regions
            selectors = [
                "//button[contains(., 'Accept all')]",
                "//button[contains(., 'Tümünü kabul et')]",
                "//button[contains(., 'Accept')]",
                "//button[contains(., 'Kabul')]",
                "//button[contains(., 'I agree')]",
                "//button[@id='L2AGLb']",  # Common Google consent button ID
                "//div[@role='none']//button[1]",  # First button in consent dialog
            ]
            for selector in selectors:
                try:
                    buttons = self.driver.find_elements(By.XPATH, selector)
                    if buttons:
                        # Use ActionChains for more human-like click
                        actions = ActionChains(self.driver)
                        actions.move_to_element(buttons[0])
                        human_delay(0.3, 0.7)
                        actions.click()
                        actions.perform()
                        p_log("Cookie consent accepted.")
                        human_delay(0.5, 1)
                        return True
                except:
                    continue
        except Exception as e:
            p_log(f"No cookie consent found or error: {e}")
        return False

    def _scroll_like_human(self):
        """Scrolls the page in a human-like manner."""
        scroll_amount = random.randint(200, 500)
        self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        human_delay(0.5, 1.5)

    def search(self, query: str, num_results: int = 10) -> list[str]:
        """
        Performs an organic Google search and returns a list of result URLs.

        Args:
            query: The search query string.
            num_results: Approximate number of result URLs to collect.

        Returns:
            A list of unique URLs from the search results.
        """
        if not self.driver:
            self.init_driver()

        p_info(f"Step 2: Navigating to Google...")
        results = set()

        try:
            # Navigate to Google
            self.driver.get("https://www.google.com")
            human_delay(1.5, 3)  # Wait for page to load fully

            # Handle cookie consent
            self._accept_cookies()
            human_delay(0.5, 1.5)

            p_info(f"Step 3: Typing search query: '{query}'")

            # Find search box - try multiple selectors
            search_box = None
            search_selectors = [
                (By.NAME, "q"),
                (By.CSS_SELECTOR, "textarea[name='q']"),
                (By.CSS_SELECTOR, "input[name='q']"),
                (By.CSS_SELECTOR, "[aria-label='Search']"),
                (By.CSS_SELECTOR, "[title='Search']"),
            ]

            for by, selector in search_selectors:
                try:
                    search_box = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    if search_box:
                        break
                except:
                    continue

            if not search_box:
                p_error("Could not find search box on Google.")
                return list(results)

            # Click on search box first (human behavior)
            actions = ActionChains(self.driver)
            actions.move_to_element(search_box)
            human_delay(0.3, 0.8)
            actions.click()
            actions.perform()
            human_delay(0.5, 1)

            # Type query like a human (character by character with delays)
            human_type(search_box, query, min_delay=0.08, max_delay=0.25)
            human_delay(0.5, 1.5)

            # Press Enter to search
            search_box.send_keys(Keys.RETURN)
            p_info("Step 4: Waiting for search results...")
            human_delay(2, 4)  # Wait for results page

            p_info("Step 5: Extracting URLs from search results...")

            page_count = 0
            max_pages = (num_results // 10) + 2  # Estimate pages needed

            while len(results) < num_results and page_count < max_pages:
                page_count += 1
                p_log(f"Processing page {page_count}...")

                # Scroll like a human reading the page
                for _ in range(random.randint(2, 4)):
                    self._scroll_like_human()

                # Wait for results to be present
                human_delay(1, 2)

                # Extract URLs using JavaScript for robustness (class names change, but structure doesn't)
                extracted_urls = self.driver.execute_script(
                    """
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
                """
                )

                for url in extracted_urls:
                    if url not in results:
                        results.add(url)

                p_log(f"Collected {len(results)}/{num_results} URLs so far...")

                if len(results) >= num_results:
                    break

                # Try to go to next page
                try:
                    # Scroll to bottom first
                    self.driver.execute_script(
                        "window.scrollTo(0, document.body.scrollHeight);"
                    )
                    human_delay(1, 2)

                    # Look for "Next" button
                    next_selectors = [
                        "#pnnext",
                        "a[aria-label='Next page']",
                        "a[id='pnnext']",
                        "//a[contains(., 'Next')]",
                        "//a[contains(., 'Sonraki')]",
                    ]

                    next_clicked = False
                    for selector in next_selectors:
                        try:
                            if selector.startswith("//"):
                                next_btn = self.driver.find_element(By.XPATH, selector)
                            else:
                                next_btn = self.driver.find_element(
                                    By.CSS_SELECTOR, selector
                                )

                            if next_btn:
                                actions = ActionChains(self.driver)
                                actions.move_to_element(next_btn)
                                human_delay(0.5, 1)
                                actions.click()
                                actions.perform()
                                next_clicked = True
                                p_log("Navigating to next page...")
                                human_delay(2, 4)
                                break
                        except:
                            continue

                    if not next_clicked:
                        p_warn("No more pages available.")
                        break

                except Exception as e:
                    p_warn(f"Could not navigate to next page: {e}")
                    break

        except Exception as e:
            p_error(f"Error during search: {e}")
        finally:
            self.close()

        p_info(f"Step 6: Search completed. Total unique URLs found: {len(results)}")
        return list(results)[:num_results]

    def close(self):
        """Closes the browser and cleans up resources."""
        if self.driver:
            p_info("Closing browser...")
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
