#! /usr/bin/env python3

from lib.facebook_thread import facebook_thread
from lib.facebook.facebook_profile_crawler import FacebookProfileCrawler
from lib.selenium_tools.selenium_browser import BrowserToolkit, get_chrome_driver
from lib.database_tools import DatabaseTools
from lib.init_insightface import initilate_insightface
from lib.load_config import load_config_from_file
import argparse
import concurrent.futures
from urllib.parse import quote, urlparse
import sys
import os
import cv2
import hashlib

# Playwright imports (conditional)
try:
    from lib.facebook.facebook_playwright_crawler import PlaywrightFacebookCrawler

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

CONFIG = load_config_from_file()

if not CONFIG[0]:
    print("Hata: Config dosyası yüklenemedi")
    exit(1)

argparser = argparse.ArgumentParser(description="Facebook Crawler")
argparser.add_argument(
    "--keyword", type=str, help="Facebook araması için anahtar kelime"
)
argparser.add_argument("--file", type=str, help="Arama anahtar kelimeleri için dosya")
argparser.add_argument(
    "--scroll_count",
    type=int,
    default=5,
    help="Facebook arama sonuçlarında kaydırma sayısı",
)
argparser.add_argument(
    "--scroll_pause_time",
    type=int,
    default=2,
    help="Facebook arama sonuçlarında kaydırma bekleme süresi",
)
argparser.add_argument(
    "--headless", action="store_true", default=True, help="Selenium için başlıksız mod"
)
argparser.add_argument(
    "--executable_path", type=str, help="Selenium için yürütülebilir dosya yolu"
)
argparser.add_argument("--driver_path", type=str, help="Selenium için sürücü yolu")
argparser.add_argument(
    "--temp_folder", type=str, default="temp", help="Geçici dosyalar için klasör"
)
argparser.add_argument(
    "--backend",
    type=str,
    default="playwright",
    choices=["selenium", "playwright"],
    help="Tarayıcı altyapısı (selenium varsayılan)",
)

args = argparser.parse_args()

# Gerekli parametreleri kontrol et ve varsayılan değerleri ata
if args.keyword is None and args.file is None:
    print("Hata: Arama için ya --keyword ya da --file parametresi gereklidir")
    exit(1)

# Değişkenleri ata
keyword = args.keyword
file_path = args.file
scroll_count = args.scroll_count
scroll_pause_time = args.scroll_pause_time
headless_mode = args.headless
executable_path = args.executable_path
driver_path = args.driver_path
temp_folder = args.temp_folder
backend = args.backend

print(f"Arama parametreleri:")
print(f"  Backend: {backend}")
print(f"  Anahtar kelime: {keyword}")
print(f"  Dosya: {file_path}")
print(f"  Kaydırma sayısı: {scroll_count}")
print(f"  Kaydırma bekleme süresi: {scroll_pause_time} saniye")
print(f"  Başlıksız mod: {'Evet' if headless_mode else 'Hayır'}")
print(f"  Geçici klasör: {temp_folder}")


KEYWORDS = []

if file_path is not None:
    with open(file_path, "r") as file:
        keywords = file.readlines()
    for keyword in keywords:
        keyword = keyword.strip()
        KEYWORDS.append(keyword)

if keyword is not None:
    if "," in keyword:
        KEYWORDS.extend(keyword.split(","))
    else:
        KEYWORDS.append(keyword)

databaseToolkit = DatabaseTools(CONFIG[1]["database_config"])
insightFaceApp = initilate_insightface(CONFIG)

if backend == "playwright":
    if not PLAYWRIGHT_AVAILABLE:
        print("Hata: Playwright kütüphanesi bulunamadı veya import edilemedi.")
        exit(1)

    print("Playwright backend başlatılıyor...")
    crawler = PlaywrightFacebookCrawler(
        headless=headless_mode,
        preset="aggressive",  # Use aggressive perfromance
        scroll_count=scroll_count,
        scroll_pause_time=scroll_pause_time,
        download_folder=temp_folder,
    )

    for kw in KEYWORDS:
        print(f"Playwright ile aranıyor: {kw}")
        # search_query = quote(kw) # PlaywrightCrawler handles encoding internally inside crawl_search

        # Playwright crawler handles search + collect + process + download in one go
        results = crawler.crawl_search(kw)

        print(f"Playwright taraması tamamlandı: {len(results)} sonuç bulundu.")

        # Save results to Database
        # PlaywrightCrawler saves images to disk. We need to read them and insert to DB.
        for result in results:
            if result.get("download_status") == "success" and result.get(
                "downloaded_path"
            ):
                print(f"Veritabanına kaydediliyor: {result['username']}")
                try:
                    image_path = result["downloaded_path"]
                    with open(image_path, "rb") as f:
                        image_binary = f.read()

                    # Read with OpenCV for InsightFace
                    imageOpencv = cv2.imread(image_path)
                    if imageOpencv is None:
                        print(f"Resim okunamadı: {image_path}")
                        continue

                    faces = insightFaceApp.get(imageOpencv)
                    if len(faces) == 0:
                        print(f"Yüz bulunamadı: {result['username']}")
                        continue

                    imageHash = hashlib.sha1(image_binary).hexdigest()

                    # Parse URL for path
                    try:
                        parsed_url = urlparse(result["profile_url"])
                        username_path = parsed_url.path
                        baseDomain = "facebook.com"
                    except:
                        username_path = result["username"]
                        baseDomain = "facebook.com"

                    db_result = databaseToolkit.insertImageBased(
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
                    print(f"DB Sonuç: {db_result}")

                except Exception as e:
                    print(f"Hata oluştu ({result['username']}): {e}")

else:
    # Legacy Selenium Backend
    for keyword in KEYWORDS:
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

        search_query = quote(keyword)
        search_url = f"https://tr-tr.facebook.com/public/{search_query}"
        final_results = facebookProfileCrawler.crawl_search_results(search_url)
        facebookProfileCrawler.close_driver()

        print(f"{len(final_results)} profil bulundu. İşleniyor...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for result in final_results:
                profile_url = result.get("profile_url")

                if not profile_url:
                    continue

                print(f"İşleniyor: {profile_url}")
                futures.append(
                    executor.submit(
                        facebook_thread,
                        profile_url,
                        databaseToolkit,
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
                print(f"Hata: {err}")
