import time
import re
import argparse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
import requests
# Optional: If chromedriver is not in PATH, uncomment and set the path
# from webdriver_manager.chrome import ChromeDriverManager

# --- Constants ---
# Use a common User Agent, not Google Bot, as browsers don't typically use that.
# Using Google Bot in Selenium might be a bigger red flag.
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36"
# Potential profile picture container element to wait for
PROFILE_PIC_CONTAINER_SELECTOR = "div.pv-top-card" # More general container

# --- HTML Parsing Function (Remains the same, works on HTML source) ---
def extract_linkedin_profile_picture(html_content: str) -> str | None:
    """
    Parses the HTML content of a LinkedIn profile page and extracts the URL
    of the main profile picture using multiple strategies.

    Args:
        html_content: The HTML source code of the LinkedIn profile page as a string.

    Returns:
        The URL of the profile picture as a string, or None if not found or
        an error occurs during parsing.
    """
    if not html_content:
        # print("Debug: HTML content is empty.")
        return None

    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        profile_pic_img = None

        # List of CSS selectors to try in order (Adjust based on observed Selenium results if needed)
        selectors = [
            'img.pv-top-card-profile-picture__image--show',         # Primary target
            'img.profile-photo-edit__preview',                     # Edit mode preview
            'div.pv-top-card__photo-wrapper img',                  # Different wrapper structure
            'div.profile-photo-edit img',                          # Another edit structure
            'button[aria-label*="profile photo"] img',           # Button containing image
            'div.pv-top-card-profile-picture img',                 # Older structure?
            # Add more specific selectors here if new patterns emerge from Selenium page source
        ]

        for selector in selectors:
            profile_pic_img = soup.select_one(selector)
            if profile_pic_img:
                # print(f"Debug: Found image with selector: {selector}")
                break # Found one, stop searching

        # Fallback: Find image by alt text
        if not profile_pic_img:
            alt_text_pattern = re.compile(r'(profile picture|profil resmi)( of .+)?', re.IGNORECASE)
            profile_pic_img = soup.find('img', alt=alt_text_pattern)
            # if profile_pic_img:
            #     print("Debug: Found image with alt text fallback.")

        # --- Extract URL from the found tag ---
        if profile_pic_img:
            image_url = None
            # Prioritize data-attributes often used for lazy loading
            if profile_pic_img.has_attr('data-delayed-url'):
                 image_url = profile_pic_img['data-delayed-url']
            elif profile_pic_img.has_attr('data-src'):
                 image_url = profile_pic_img['data-src']
            elif profile_pic_img.has_attr('src'):
                 src_val = profile_pic_img['src']
                 # Ignore placeholder images
                 if not src_val.startswith('data:image'):
                     image_url = src_val

            if image_url:
                # print(f"Debug: Extracted URL: {image_url}")
                return image_url
            else:
                 # print("Debug: Found img tag, but no valid URL attribute.")
                 return None
        else:
            # print("Debug: Did not find a suitable img tag using any strategy.")
            return None

    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return None

# --- Guest Mode: Function to Extract Profile Picture (Simplified) ---
def extract_linkedin_profile_picture_guest(html_content: str) -> str | None:
    """Simplified picture extraction for Guest mode (less reliable)."""
    if not html_content:
        return None
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        # Guest view might have different structures, often simpler
        # Prioritize og:image meta tag if available (common fallback)
        og_image_tag = soup.find('meta', property='og:image')
        if og_image_tag and og_image_tag.has_attr('content'):
            img_url = og_image_tag['content']
            if not img_url.startswith('data:image') and 'ghost-person' not in img_url:
                # print("Debug (Guest): Found picture via og:image")
                return img_url

        # Try common selectors from Selenium mode, might work sometimes
        selectors = [
            'img.pv-top-card-profile-picture__image--show',
            'div.profile-photo-edit img',
            'img.feed-identity-module__member-photo', # Common in feed/public view?
            'img[alt*="profile picture" i]' # Alt text search (case-insensitive)
        ]
        for selector in selectors:
            profile_pic_img = soup.select_one(selector)
            if profile_pic_img:
                image_url = None
                if profile_pic_img.has_attr('src'):
                    src_val = profile_pic_img['src']
                    if not src_val.startswith('data:image') and 'ghost-person' not in src_val:
                        image_url = src_val
                # Add data-src check if needed based on guest view analysis
                # elif profile_pic_img.has_attr('data-src'):
                #    ... handle data-src ...
                if image_url:
                    # print(f"Debug (Guest): Found picture via selector {selector}")
                    return image_url
        # print("Debug (Guest): Picture not found via guest strategies.")
        return None
    except Exception as e:
        print(f"Error parsing picture (Guest): {e}")
        return None

# --- Guest Mode: Function to Extract Profile Details ---
def extract_profile_details_guest(html_content: str) -> dict:
    """Parses HTML for details in Guest mode (adapted from reference)."""
    details = {
        "name": "Not found",
        "headline": "Not found", # Headline often less prominent/absent in guest
        "connections_followers": "Not found",
        "about": "Not found"    # About section often requires login
    }
    if not html_content:
        return details
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # 1. Name (From title, same as Selenium)
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            name_part = title_text.split('|')[0].strip()
            if len(name_part) < 50:
                details["name"] = name_part

        # 2. Headline/Designation (Try h2 or specific classes - less reliable)
        headline_tag = soup.select_one('h2.top-card-layout__headline') # A guess for guest view
        if not headline_tag:
            headline_tag = soup.find('h2') # Generic h2 from reference
        if headline_tag:
            headline_text = headline_tag.get_text(strip=True)
            if headline_text != details["name"]:
                 details["headline"] = headline_text

        # 3. Followers/Connections (og:description from reference is a good bet for companies)
        meta_tag = soup.find('meta', {"property": "og:description"})
        if meta_tag and meta_tag.has_attr('content'):
            content = meta_tag['content']
            # Try extracting connections/followers from meta description
            match = re.search(r'\b(\d[\d,.]*\+?)\s+(connections|followers|bağlantı|takipçi)\b', content, re.IGNORECASE)
            if match:
                details["connections_followers"] = match.group(0) # e.g., "500+ connections"
            else:
                # If no follower count, use the start of the description as "About" fallback
                 details["about"] = content.split('.')[0] + "... (from meta description)"

        # 4. About/Description (Often limited in guest view, try reference code's p tag)
        if details["about"] == "Not found": # Only if not found via meta
            description_tag = soup.find('p', class_='break-words') # From reference
            if description_tag:
                details["about"] = description_tag.get_text(strip=True)
            else:
                 # Maybe look for profile summary section if structure differs
                 summary_div = soup.find('div', class_='core-section-container__content') # Another guess
                 if summary_div:
                     details["about"] = summary_div.get_text(strip=True)[:500] + "..."

    except Exception as e:
        print(f"Error parsing details (Guest): {e}")
    return details

# --- Guest Mode: Function to Fetch HTML using Requests ---
def fetch_profile_html_guest(url: str, timeout: int = 15) -> str | None:
    """Fetches HTML using requests with Guest User-Agent."""
    print(f"  Attempting Guest fetch: {url}")
    headers = {
        "User-Agent": "Guest", # Simple Guest agent
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()

        final_url = response.url.lower()
        if any(wall in final_url for wall in ['/login', '/signup', '/authwall', '/feed', '/checkpoint']):
            print(f"  Warning (Guest): Redirected to login/auth wall ({response.url}).")
            return None

        content_type = response.headers.get('Content-Type', '')
        if 'text/html' not in content_type:
             print(f"  Warning (Guest): Content-Type is not HTML ({content_type}).")
             return None

        print(f"  Successfully fetched HTML (Guest - Status: {response.status_code}).")
        return response.text

    except requests.exceptions.Timeout:
        print(f"  Error (Guest): Request timed out for {url}")
        return None
    except requests.exceptions.HTTPError as http_err:
         print(f"  Error (Guest): HTTP {http_err.response.status_code} for {url}")
         return None
    except requests.exceptions.RequestException as req_err:
        print(f"  Error (Guest): Failed fetching {url}: {req_err}")
        return None
    except Exception as e:
        print(f"  Error (Guest): Unexpected error fetching {url}: {e}")
        return None


# --- Function to run the Guest Mode crawl ---
def crawl_linkedin_profiles_guest(profile_urls: list[str], delay: float = 1.0):
    """Crawls profiles using requests (Guest mode)."""
    print("--- Running in Guest Mode (Requests only) ---")
    print("WARNING: Guest access is limited. Details and pictures may be unavailable.")
    print("="*60 + "\n")

    results = {}
    for i, url in enumerate(profile_urls):
        print(f"Processing URL {i+1}/{len(profile_urls)}: {url}")
        html_content = fetch_profile_html_guest(url)
        result_data = {
            "profile_picture": None,
            "details": {},
            "status": "OK"
        }

        if html_content:
            result_data["profile_picture"] = extract_linkedin_profile_picture_guest(html_content)
            result_data["details"] = extract_profile_details_guest(html_content)

            if result_data["profile_picture"]:
                print(f"  ✅ Found Profile Picture (Guest)")
            else:
                print(f"  ⚠️ Could not extract profile picture (Guest).")

            details = result_data["details"]
            print(f"    Name: {details.get('name', 'Not found')}")
            print(f"    Headline: {details.get('headline', 'Not found')}")
            print(f"    Connections/Followers: {details.get('connections_followers', 'Not found')}")
            print(f"    About: {details.get('about', 'Not found')[:100]}...")
        else:
             print(f"  ❌ Failed to fetch profile HTML (Guest).")
             result_data["status"] = "Error: Failed to fetch HTML (Guest)."
             # Initialize details dict even on failure
             result_data["details"] = {"name": "Fetch Failed", "headline": "N/A", "connections_followers": "N/A", "about": "N/A"}

        results[url] = result_data

        if i < len(profile_urls) - 1:
            print(f"  Waiting for {delay} seconds...")
            time.sleep(delay)
        print("-" * 40)

    return results

# --- New Function to Extract Profile Details (Selenium) ---
# Renamed from extract_profile_details to avoid confusion
def extract_profile_details_selenium(html_content: str) -> dict:
    """
    Parses the HTML content of a LinkedIn profile page (from Selenium) and extracts details
    like name, headline, connections/followers, and about section.

    Args:
        html_content: The HTML source code of the LinkedIn profile page as a string.

    Returns:
        A dictionary containing extracted details. Returns 'Not found' for missing items.
    """
    details = {
        "name": "Not found",
        "headline": "Not found",
        "connections_followers": "Not found",
        "about": "Not found"
    }
    if not html_content:
        return details

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # 1. Name (from Title tag - usually reliable)
        title_tag = soup.find('title')
        if title_tag:
            # Typical format: "John Doe | Headline | LinkedIn"
            title_text = title_tag.get_text(strip=True)
            name_part = title_text.split('|')[0].strip()
            # Avoid picking up things like "LinkedIn" if the title is unexpected
            if len(name_part) < 50: # Basic sanity check
                details["name"] = name_part

        # 2. Headline/Designation (Top card area - selectors might need adjustment)
        # Try a few common selectors for the headline
        headline_selectors = [
            'div.pv-text-details__left-panel h2', # Common structure
            'div.text-body-medium.break-words',   # Another common class for headline
            '.pv-top-card--list > li:first-child', # Sometimes it's the first list item
            'h2' # Generic fallback (less reliable)
        ]
        for selector in headline_selectors:
            headline_tag = soup.select_one(selector)
            if headline_tag:
                headline_text = headline_tag.get_text(strip=True)
                # Avoid grabbing the name again if h2 is used generically
                if headline_text != details["name"]:
                    details["headline"] = headline_text
                    break

        # 3. Connections/Followers (Often requires login - Best effort)
        # Look for elements containing keywords like "connections" or "followers"
        # These selectors are guesses and highly dependent on being logged in / profile visibility
        connection_selectors = [
            'span.link-without-visited-state', # Often used for links like "500+ connections"
            '.pv-top-card--list-bullet > li span.visually-hidden', # Accessibility text might contain it
            '.pvs-header__subtitle span:first-child', # Newer structures might have it here
            '.pv-member-tooltip__connections span' # Tooltip text
        ]
        found_connections = False
        for selector in connection_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True).lower()
                # Use regex to find patterns like "500+ connections", "1,234 followers"
                match = re.search(r'(\d[\d,.]*\+?)\s+(connections|followers|bağlantı|takipçi)', text)
                if match:
                    details["connections_followers"] = match.group(0) # Get the full match (e.g., "500+ connections")
                    found_connections = True
                    break
            if found_connections:
                break
        # Fallback using og:description (more likely for Company pages, but try)
        if not found_connections:
            followers_tag = soup.find('meta', {"property": "og:description"})
            if followers_tag and followers_tag.has_attr('content'):
                 match = re.search(r'\b(\d[\d,.]*)\s+(followers|takipçi)\b', followers_tag["content"], re.IGNORECASE)
                 if match:
                     details["connections_followers"] = f"{match.group(1)} followers (from meta)"

        # 4. About Section (Look for common section IDs/classes)
        about_section = soup.find('section', { 'id': 'about' }) # Common ID
        if not about_section:
            # Try finding by aria-label or class name patterns (these can change)
            about_section = soup.find('div', { 'aria-label': lambda x: x and 'about' in x.lower() })
        if not about_section:
             about_section = soup.find('section', class_=lambda x: x and 'summary' in x.lower())

        if about_section:
            # Try to get text, excluding potential "See more" buttons within
            all_text_parts = about_section.find_all(string=True, recursive=True)
            about_text = ' '.join(part.strip() for part in all_text_parts if part.parent.name not in ['button', 'script', 'style'] and part.strip()) # Basic filtering
            if len(about_text) > 2000: # Limit length if needed
                about_text = about_text[:2000] + "..."
            details["about"] = about_text.strip() if about_text else "About section found but text extraction failed."
        else:
            # Fallback to generic paragraph tag from snippet (less likely for personal profiles)
            description_tag = soup.find('p', class_='break-words')
            if description_tag:
                 details["about"] = description_tag.get_text(strip=True) + " (from p.break-words fallback)"


    except Exception as e:
        print(f"Error parsing details from HTML: {e}")
        # Keep whatever details were found before the error

    return details

# --- Selenium WebDriver Setup ---
def setup_driver(headless: bool = True, driver_path: str | None = None, browser_binary_path: str | None = None):
    """Configures and initializes the Selenium WebDriver."""
    options = ChromeOptions()
    options.add_argument(f"user-agent={DEFAULT_USER_AGENT}")
    options.add_argument("--disable-blink-features=AutomationControlled") # Try to hide automation
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--window-size=1920,1080") # Standard size
    options.add_argument("--disable-gpu") # Often needed in headless
    options.add_argument("--no-sandbox") # Often needed in Linux environments
    options.add_argument("--disable-dev-shm-usage") # Overcome limited resource problems
    options.add_argument("--lang=en-US") # Request English language
    options.add_argument("--accept-lang=en-US,en")
    # Referer is less effective with direct navigation but doesn't hurt
    options.add_argument("referer=https://www.google.com/")

    if headless:
        options.add_argument("--headless")

    # Set browser binary location if provided
    if browser_binary_path:
        print(f"Using custom browser binary path: {browser_binary_path}")
        options.binary_location = browser_binary_path

    try:
        # Configure the service with the driver path if provided
        if driver_path:
            print(f"Using custom chromedriver path: {driver_path}")
            service = ChromeService(executable_path=driver_path)
            driver = webdriver.Chrome(service=service, options=options)
        else:
            # If driver_path is not provided, assume chromedriver is in PATH
            print("Using chromedriver from system PATH.")
            # This line might need adjustment if ChromeService() without args doesn't work
            # depending on the selenium version. Explicitly passing None might be needed.
            # service = ChromeService() # Or try without service for default behavior
            driver = webdriver.Chrome(options=options)

        # Minimize detection vectors
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("WebDriver initialized successfully.")
        return driver
    except WebDriverException as e:
        print(f"Error initializing WebDriver: {e}")
        if not driver_path:
            print("Ensure 'chromedriver' is installed and in your PATH, or provide the path using --driver-path.")
        if not browser_binary_path and 'cannot find Chrome binary' in str(e):
            print("Ensure Chrome browser is installed in the default location, or provide the path using --browser-binary-path.")
        print("ChromeDriver download: https://chromedriver.chromium.org/downloads")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during WebDriver setup: {e}")
        return None


# --- Main Crawling Logic using Selenium ---
def crawl_linkedin_profiles_selenium(driver: webdriver.Chrome, profile_urls: list[str], delay: float = 5.0, page_load_timeout: int = 30):
    """
    Crawls a list of LinkedIn profile URLs using Selenium, attempting to extract the profile picture.
    Adds delays and waits for page elements.
    """
    if not driver:
        print("WebDriver is not available. Cannot start crawling.")
        return {}

    print("\n" + "="*60)
    print("WARNING: Scraping LinkedIn is against their Terms of Service.")
    print("Using Selenium increases chances but doesn't guarantee success or prevent blocks.")
    print("This script does NOT handle logins. Access may be limited.")
    print("USE RESPONSIBLY AND AT YOUR OWN RISK.")
    print("="*60 + "\n")

    results = {}

    for i, url in enumerate(profile_urls):
        print(f"Processing URL {i+1}/{len(profile_urls)}: {url}")
        try:
            driver.get(url)
            time.sleep(1) # Small initial pause

            # Check for immediate redirection to login/auth wall
            current_url = driver.current_url.lower()
            if any(wall in current_url for wall in ['/login', '/signup', '/authwall', '/feed', '/checkpoint']):
                print(f"  ❌ Warning: Immediately redirected to login/auth wall ({driver.current_url}). Scraping blocked.")
                results[url] = "Error: Blocked by login/auth wall."
                # Optional: Attempt a longer wait or different strategy if needed
                # time.sleep(delay) # Wait before next attempt
                continue # Skip to next URL

            # Wait for a general container element to be present
            print(f"  Waiting up to {page_load_timeout}s for profile container '{PROFILE_PIC_CONTAINER_SELECTOR}'...")
            wait = WebDriverWait(driver, page_load_timeout)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, PROFILE_PIC_CONTAINER_SELECTOR)))
            print("  Profile container found. Page likely loaded.")
            time.sleep(2) # Additional small delay for elements to settle after container appears

            # Optional: Add more specific waits here if needed, e.g., for the image itself
            # try:
            #    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "img.pv-top-card-profile-picture__image--show")))
            #    print("  Specific profile image element found.")
            # except TimeoutException:
            #    print("  Warning: Specific profile image element did not appear within timeout.")


            # --- Get HTML and Extract ---
            html_content = driver.page_source
            # Optional: Save HTML for debugging
            # try:
            #     profile_name = url.strip('/').split('/in/')[-1].split('/')[0]
            #     filename = f"selenium_linkedin_{profile_name}.html"
            #     with open(filename, "w", encoding="utf-8") as f:
            #         f.write(html_content)
            #     print(f"  Saved HTML to {filename}")
            # except Exception as e:
            #      print(f"  Could not save HTML: {e}")


            profile_pic_url = extract_linkedin_profile_picture(html_content)
            profile_details = extract_profile_details_selenium(html_content) # Use renamed function

            result_data = {
                "profile_picture": None,
                "details": profile_details # Store the details dict
            }

            if profile_pic_url:
                print(f"  ✅ Found Profile Picture: {profile_pic_url}")
                result_data["profile_picture"] = profile_pic_url
            else:
                print(f"  ⚠️ Could not extract profile picture URL.")
                # Check again for auth wall after waiting, as it might appear later
                current_url = driver.current_url.lower()
                # Inner if condition (level 5)
                if any(wall in current_url for wall in ['/login', '/signup', '/authwall', '/feed', '/checkpoint']):
                     # Indentation level 6
                     print(f"  ❌ Blocked by login/auth wall after loading ({driver.current_url}). Details might be incomplete.")
                     # Update status if blocked, even if some details were parsed
                     result_data["status"] = "Error: Blocked by login/auth wall after load."
                # Inner else (level 5, aligned with the 'if' above)
                else:
                     # Indentation level 6
                     print(f"  (Check page structure/selectors in saved HTML if picture missing).")
                     # Innermost if (level 6)
                     if not any(v != 'Not found' for v in profile_details.values()): # If no details were found either
                         # Indentation level 7
                         result_data["status"] = "Error: Could not extract picture or details from HTML."

            # Print extracted details
            print(f"    Name: {profile_details.get('name', 'Not found')}")
            print(f"    Headline: {profile_details.get('headline', 'Not found')}")
            print(f"    Connections/Followers: {profile_details.get('connections_followers', 'Not found')}")
            print(f"    About: {profile_details.get('about', 'Not found')[:100]}...") # Print snippet of about

            results[url] = result_data # Store combined results

        except TimeoutException:
            print(f"  ❌ Error: Timed out waiting for page elements to load for {url}. Might be blocked or page too slow.")
            results[url] = "Error: Page load timeout."
            # Check URL in case of timeout on auth wall
            current_url = driver.current_url.lower()
            if any(wall in current_url for wall in ['/login', '/signup', '/authwall', '/feed','/checkpoint']):
                 print(f"  Timeout occurred on a potential login/auth wall: {driver.current_url}")
                 results[url] = "Error: Timeout on login/auth wall."
        except WebDriverException as e:
             print(f"  ❌ WebDriver error processing {url}: {e}")
             results[url] = f"Error: WebDriverException - {e}"
             # Consider quitting and restarting the driver if errors persist
        except Exception as e:
            print(f"  ❌ An unexpected error occurred while processing {url}: {e}")
            results[url] = f"Error: Unexpected - {e}"

        # Add delay between requests
        if i < len(profile_urls) - 1:
            print(f"  Waiting for {delay} seconds...")
            time.sleep(delay)
        print("-" * 40) # Separator

    return results

# --- Command Line Argument Parsing and Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="LinkedIn Profile Picture Crawler using Selenium (Educational Purposes Only - Use Responsibly)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "profile_urls",
        nargs='+',
        help="One or more full LinkedIn profile URLs (e.g., https://www.linkedin.com/in/username)"
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=5.0, # Increased default delay for Selenium
        help="Delay in seconds between requests (default: 5.0). Increase if getting blocked.",
    )
    parser.add_argument(
        "--load-timeout",
        type=int,
        default=30,
        help="Maximum time in seconds to wait for page elements to load (default: 30)."
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run the browser in non-headless mode (visible window)."
    )
    # Add argument for Chromedriver path if needed
    # parser.add_argument("--driver-path", help="Path to the chromedriver executable")
    parser.add_argument(
        "--driver-path",
        help="Path to the chromedriver executable (if not in system PATH)."
    )
    parser.add_argument(
        "--browser-binary-path",
        help="Path to the Chrome browser binary (if not in default location)."
    )
    parser.add_argument(
        "--guest-only",
        action="store_true",
        help="Use simple Guest mode (requests) instead of Selenium."
    )

    args = parser.parse_args()

    # Basic URL validation
    valid_urls = []
    for url in args.profile_urls:
        if url.startswith("http") and "linkedin.com/in/" in url:
             valid_urls.append(url)
        else:
            print(f"Skipping invalid or non-profile URL format: {url}")

    if valid_urls:
        # --- CHOOSE CRAWLING MODE ---
        if args.guest_only:
            # --- Guest Mode Execution ---
            crawl_results = crawl_linkedin_profiles_guest(valid_urls, delay=max(1.0, args.delay / 2)) # Faster delay for requests
        else:
            # --- Selenium Mode Execution ---
            driver = setup_driver(
                headless=not args.no_headless,
                driver_path=args.driver_path,
                browser_binary_path=args.browser_binary_path
            )
            crawl_results = {}
            if driver:
                try:
                    crawl_results = crawl_linkedin_profiles_selenium(
                        driver,
                        valid_urls,
                        delay=args.delay,
                        page_load_timeout=args.load_timeout
                    )
                finally:
                    print("\nClosing WebDriver...")
                    driver.quit()
                    print("WebDriver closed.")
            else:
                print("Failed to initialize WebDriver. Cannot proceed with Selenium mode.")

        # --- Print Summary (Common for both modes) ---
        print("\n--- Crawl Summary ---")
        if crawl_results:
            for url, result in crawl_results.items():
                 if isinstance(result, str) and result.startswith("Error:"):
                      print(f"- {url}: {result}")
                 elif result:
                      # Print details (level 4)
                      print(f"\n--- Profile: {url} ---")
                      print(f"  Picture: {result.get('profile_picture', 'Not found')}")
                      details = result.get('details', {})
                      print(f"  Name: {details.get('name', 'Not found')}")
                      print(f"  Headline: {details.get('headline', 'Not found')}")
                      print(f"  Connections/Followers: {details.get('connections_followers', 'Not found')}")
                      print(f"  About: {details.get('about', 'Not found')}")
                      # Inner if (level 4)
                      if result.get("status"): 
                           # Print status (level 5)
                           print(f"  Status: {result.get('status')}")
                 else: # Handle case where result might be None or unexpected
                     print(f"- {url}: Unknown status or None result")
        else:
            print("No results were generated (or WebDriver failed to start).")

    else:
        print("No valid LinkedIn profile URLs were provided to process.")

    print("\n--- Crawler Finished ---")
    print("Reminder: Direct scraping violates LinkedIn's ToS. Consider official APIs if available.")
    print("Check saved HTML files (if enabled) for debugging if pictures aren't found.")
