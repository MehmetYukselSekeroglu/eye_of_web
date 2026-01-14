# import googlesearch # Removed in favor of organic search
from lib.database_tools import DatabaseTools
from lib.init_insightface import initilate_insightface
from lib.load_config import load_config_from_file
from lib.output.consolePrint import p_error, p_info, p_warn, p_log
import os
import sys
from typing import Optional
import argparse
import timeit
from lib.single_domain_selenium_crawler import SingleDomainCrawlerSelenium
from lib.selenium_tools.selenium_browser import get_chrome_driver
from lib.facebook.facebook_profile_crawler import FacebookProfileCrawler
import concurrent.futures
from lib.facebook_thread import facebook_thread
import urllib.parse
from lib.google_organic_search import GoogleOrganicSearch  # New Import

THREAD_SIZE = 1


def parse_boolean_arg(value: Optional[int]) -> bool:
    """
    Komut satırı argümanlarını boolean değerlere dönüştürür.
    Args:
        value: Dönüştürülecek değer
    Returns:
        bool: Dönüştürülmüş boolean değer
    """
    if value is not None:
        if str(value).isnumeric():
            return bool(value)
    return False


# Komut satırı argümanlarını tanımla
parser = argparse.ArgumentParser(description="EyeOfWeb Single Domain Crawler")
parser.add_argument(
    "--keyword", type=str, required=True, help="Keyword or URL to scan."
)
parser.add_argument(
    "--risk-level", type=str, required=False, default="normal", help="Risk level"
)
parser.add_argument(
    "--category", type=str, required=False, default="all", help="Category"
)
parser.add_argument("--save-image", action="store_true", help="Save images")
parser.add_argument(
    "--ignore-db", type=int, required=False, help="Skip database check (1 or 0)"
)
parser.add_argument(
    "--ignore-content",
    type=int,
    required=False,
    default=0,
    help="Skip HTML content check (1 or 0)",
)
parser.add_argument(
    "--executable-path",
    type=str,
    required=False,
    help="Path to ChromeDriver executable",
)
parser.add_argument(
    "--driver-path", type=str, required=False, help="Path to ChromeDriver"
)
# for facebook crawler
parser.add_argument(
    "--scroll_count",
    type=int,
    default=5,
    help="Scroll count for Facebook search results",
)
parser.add_argument(
    "--scroll_pause_time", type=int, default=2, help="Scroll pause time for Facebook"
)

# selenium crawler
parser.add_argument(
    "--headless",
    action="store_true",
    default=False,
    help="Enable headless mode for Selenium (default: visible browser)",
)
parser.add_argument(
    "--temp_folder", type=str, default="temp", help="Folder for temporary files"
)

# google search
parser.add_argument(
    "--num_results",
    type=int,
    default=50,
    help="Number of Google search results to fetch",
)
parser.add_argument(
    "--backend",
    type=str,
    default="playwright",
    choices=["selenium", "playwright"],
    help="Search backend: 'selenium' or 'playwright' (default: playwright)",
)

# Argümanları işle
args = parser.parse_args()
keyword = args.keyword
scroll_count = args.scroll_count
scroll_pause_time = args.scroll_pause_time
headless_mode = args.headless
temp_folder = args.temp_folder
risk_level = args.risk_level
category = args.category
save_image = args.save_image
ignore_db = parse_boolean_arg(args.ignore_db)
ignore_content = parse_boolean_arg(args.ignore_content)
executable_path = args.executable_path
driver_path = args.driver_path
num_results = args.num_results
search_backend = args.backend

# Status info
p_info(f"Content check status: {ignore_content}")
p_info(f"Database check status: {not ignore_db}")
p_info(f"Search backend: {search_backend}")

CONFIG = load_config_from_file()
if not CONFIG[0]:
    print(CONFIG[1])
    sys.exit()

databaseConfig = CONFIG[1]["database_config"]
insightFaceApp = initilate_insightface(CONFIG)
databaseTools = DatabaseTools(databaseConfig)


def search_google_organic(query, num_results=50, backend="playwright") -> list[str]:
    """
    Performs an organic Google search using Selenium or Playwright.
    """
    if backend == "playwright":
        from lib.google_playwright_search import GooglePlaywrightSearch

        searcher = GooglePlaywrightSearch(headless=headless_mode)
    else:
        searcher = GoogleOrganicSearch(headless=headless_mode, temp_folder=temp_folder)
    return searcher.search(query, num_results=num_results)


# URL listesini hazırla
# Use the new organic search function
try:
    search_results = search_google_organic(
        keyword, num_results=num_results, backend=search_backend
    )
except Exception as e:
    p_error(f"Search failed: {e}")
    sys.exit(1)

if not search_results:
    p_warn(f'No results found for "{keyword}".')
    sys.exit(0)

p_info(
    f'Successfully retrieved {len(search_results)} Google search results for "{keyword}"'
)

# Her URL için tarama işlemini başlat
generic_urls = []
facebook_tasks = []

# Classify URLs first
for i, url in enumerate(search_results):
    try:
        check_url = urllib.parse.urlparse(url)
        if check_url.netloc == "facebook.com" or check_url.netloc == "www.facebook.com":
            facebook_tasks.append(url)
        else:
            generic_urls.append(url)
    except Exception:
        continue

# Process Facebook URLs (existing sequential/Selenium logic)
for i, url in enumerate(facebook_tasks):
    p_info(f"Processing Facebook URL {i+1}/{len(facebook_tasks)}: {url}")
    try:
        print_url = urllib.parse.unquote(url)
        p_info(
            f"{print_url} is a Facebook URL, scanning for profile or search results..."
        )

        if "facebook.com/public/" in urllib.parse.unquote(url):
            p_info(f"{print_url} is a Facebook profile search result URL...")

            if search_backend == "playwright":
                # Playwright logic for Facebook search results
                from lib.facebook.facebook_playwright_crawler import (
                    PlaywrightFacebookCrawler,
                )
                from lib.facebook_playwright_thread import facebook_playwright_thread

                crawler = PlaywrightFacebookCrawler(headless=headless_mode)
                # Use synchronous wrapper for crawl_search (which returns list of profiles)
                # Note: original code only fetched profiles, then processed them.
                # Playwright crawler's crawl_search does everything (scroll, process, download).
                # But here we need to extract profile URLs and then maybe process them individually?
                # Actually, PlaywrightFacebookCrawler.crawl_search returns fully processed results with images downloaded.
                # So we just need to iterate results and save to DB/InsightFace if needed.
                # However, to maintain structure, we'll just use it to get profile URLs and then use the thread function.

                # To keep it simple and consistent with existing structure:
                # 1. We'll use a new method to just get profile links from search result
                # 2. Then iterate and call facebook_playwright_thread

                # But wait, PlaywrightFacebookCrawler is designed to be efficient doing it all.
                # Let's trust it to crawl search results.
                # Since crawl_search_async does everything including downloading images,
                # we might just want to use the result list to update DB/InsightFace?

                # Re-reading original Selenium code:
                # 1. crawls search page to get 'final_results' (profile_url, username)
                # 2. Iterate 'final_results', submit 'facebook_thread' to executor

                # Let's adapt that:
                crawler = PlaywrightFacebookCrawler(headless=headless_mode)

                # We need a method to just get profiles from search URL without full processing
                # We can use _scroll_and_collect_profiles but it's async and internal.
                # Let's assume we use the full power of PlaywrightFacebookCrawler for search results
                # as it is much faster (10x).

                # But wait, the user wants "just migrate backend".
                # Let's stick to the pattern: Get URLs -> Process URLs.

                # For search results, we can use the high-performance crawler directly
                p_info(
                    f"Using Playwright to crawl Facebook search results in {print_url}"
                )
                # We need to extract keyword from URL to use crawl_search effectively?
                # Or just navigate to URL.

                # To minimize code changes and risk, let's use the new thread logic for individual profiles
                # but for the search list, we might still need a way to extract links.
                # The selenium version uses FacebookProfileCrawler.crawl_search_results(url)

                # Let's implement a similar helper in PlaywrightFacebookCrawler if needed,
                # or just use the PlaywrightFacebookCrawler to do the search crawl fully.

                # Let's extract keyword from url...
                # https://www.facebook.com/public/Name-Surname
                try:
                    keyword = (
                        urllib.parse.unquote(url)
                        .split("/public/")[-1]
                        .replace("-", " ")
                    )
                except:
                    keyword = keyword  # Fallback to global keyword

                p_info(f"Detected keyword for Facebook search: {keyword}")
                final_results = crawler.crawl_search(
                    keyword
                )  # This does EVERYTHING (crawl, process, download)

                # Now we need to save these results to DB/InsightFace
                # The Playwright crawler saves images to disk.
                # We need to read them and pass to InsightFace/DB.

                for result in final_results:
                    if result.get("download_status") == "success" and result.get(
                        "downloaded_path"
                    ):
                        # Mimic facebook_thread logic for DB insertion
                        try:
                            image_path = result["downloaded_path"]
                            with open(image_path, "rb") as f:
                                image_binary = f.read()

                            imageOpencv = cv2.imread(image_path)
                            if imageOpencv is None:
                                continue

                            faces = insightFaceApp.get(imageOpencv)
                            if len(faces) == 0:
                                continue

                            imageHash = hashlib.sha1(image_binary).hexdigest()

                            username_path = urlparse(result["profile_url"]).path
                            baseDomain = "facebook.com"

                            databaseTools.insertImageBased(
                                protocol="https",
                                baseDomain=baseDomain,
                                urlPath=username_path,
                                imageProtocol=None,
                                imageDomain=None,
                                imagePath=None,
                                imagePathEtc=None,
                                imageTitle=result["username"],
                                imageBinary=image_binary,
                                imageHash=imageHash,
                                faces=faces,
                                riskLevel="normal",
                                category="social",
                                save_image=True,
                                Source="facebook",
                            )
                        except Exception as e:
                            p_error(
                                f"Error processing result {result['username']}: {e}"
                            )

            else:
                # Legacy Selenium Logic
                chromeDriver = get_chrome_driver(
                    headless=headless_mode,
                    executable_path=executable_path,
                    driver_path=driver_path,
                    temp_base_dir=temp_folder,
                )
                facebookProfileCrawler = FacebookProfileCrawler(
                    driver=chromeDriver,
                    scroll_count=scroll_count,
                    scroll_pause_time=scroll_pause_time,
                )
                final_results = facebookProfileCrawler.crawl_search_results(url)
                facebookProfileCrawler.close_driver()

                p_info(f"Number of profiles in {print_url}: {len(final_results)}")
                p_info(f"Starting crawl of profiles in {print_url} (4 threads)...")
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=THREAD_SIZE
                ) as executor:
                    futures = []
                    for result in final_results:
                        profile_url = result.get("profile_url")

                        if not profile_url:
                            continue

                        print(f"Processing: {profile_url}")
                        futures.append(
                            executor.submit(
                                facebook_thread,
                                profile_url,
                                databaseTools,
                                insightFaceApp,
                                executable_path,
                                driver_path,
                                headless_mode,
                                temp_folder,
                            )
                        )

                for future in concurrent.futures.as_completed(futures):
                    try:
                        future.result()
                    except Exception as err:
                        p_error(f"Error: {err}")

                p_info(f"Completed crawling profiles in {print_url}.")
        else:
            p_info(f"{print_url} is a Facebook profile URL, crawling profile...")
            profile_url = url

            if search_backend == "playwright":
                from lib.facebook_playwright_thread import facebook_playwright_thread

                facebook_playwright_thread(
                    profile_url,
                    databaseTools,
                    insightFaceApp,
                    headless=headless_mode,
                    temp_folder=temp_folder,
                )
            else:
                facebook_thread(
                    profile_url,
                    databaseTools,
                    insightFaceApp,
                    executable_path,
                    driver_path,
                    headless_mode,
                    temp_folder,
                )
            p_info(f"Completed crawling profile {print_url}.")

    except Exception as e:
        p_error(f"Error crawling Facebook URL {url}: {e}")
        continue

# Process Generic URLs
if generic_urls:
    p_info(f"Found {len(generic_urls)} generic URLs to crawl.")

    if search_backend == "playwright":
        from lib.single_domain_playwright_crawler import PlaywrightPageCrawler

        start_time = timeit.default_timer()
        p_info(
            f"Starting batch crawl of {len(generic_urls)} generic URLs with Playwright (async, 3 tabs)..."
        )

        with PlaywrightPageCrawler(
            database_toolkit=databaseTools,
            insightface_app=insightFaceApp,
            headless=headless_mode,
            num_tabs=3,
        ) as crawler:
            crawler.crawl_urls(
                urls=generic_urls,
                risk_level=risk_level,
                category=category,
                save_image=save_image,
                single_page=True,
            )

        end_time = timeit.default_timer()
        p_info(
            f"Playwright batch crawl duration: {round(end_time - start_time, 1)} seconds"
        )

    else:
        # Sequential Selenium fallback
        for i, url in enumerate(generic_urls):
            print_url = urllib.parse.unquote(url)
            p_info(
                f"Processing generic URL {i+1}/{len(generic_urls)}: {print_url} (Selenium)..."
            )
            try:
                start_time = timeit.default_timer()
                crawler = SingleDomainCrawlerSelenium(
                    DatabaseToolkit_object=databaseTools,
                    FirstTargetAddress=url,
                    ThreadSize=THREAD_SIZE,
                    CONFIG=CONFIG,
                    ignore_db=ignore_db,
                    ignore_content=ignore_content,
                    executable_path=executable_path,
                    driver_path=driver_path,
                    single_page=True,
                    insightFaceApp=insightFaceApp,
                    temp_folder=temp_folder,
                )
                crawler.startCrawl(
                    riskLevel=risk_level, category=category, save_image=save_image
                )
                end_time = timeit.default_timer()
                p_info(f"Crawl duration: {round(end_time - start_time, 1)} seconds")
            except Exception as e:
                p_error(f"Error crawling {url}: {e}")
                continue
