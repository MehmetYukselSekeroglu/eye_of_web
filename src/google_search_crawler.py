import googlesearch
from lib.database_tools import DatabaseTools
from lib.init_insightface import initilate_insightface
from lib.load_config import load_config_from_file
from lib.output.consolePrint import p_error,p_info,p_warn,p_log
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
parser.add_argument("--keyword", type=str, required=True, help="Taranacak tek URL.")
parser.add_argument("--risk-level", type=str, required=False,default="normal", help="Risk seviyesi")
parser.add_argument("--category", type=str, required=False,default="all", help="Kategori")
parser.add_argument("--save-image", action="store_true", help="Resimleri kaydet")
parser.add_argument("--ignore-db", type=int, required=False, help="Veritabanını kontrol etme (1 veya 0)")
parser.add_argument("--ignore-content", type=int, required=False, default=0, help="HTML içeriğini kontrol etme (1 veya 0)")
parser.add_argument("--executable-path", type=str, required=False, help="ChromeDriver'ın yolunu belirtmek için kullanılır")
parser.add_argument("--driver-path", type=str, required=False, help="ChromeDriver'ın yolunu belirtmek için kullanılır")
# for facebook crawler 
parser.add_argument("--scroll_count", type=int, default=5, help="Facebook arama sonuçlarında kaydırma sayısı")
parser.add_argument("--scroll_pause_time", type=int, default=2, help="Facebook arama sonuçlarında kaydırma bekleme süresi")

# selenium crawler
parser.add_argument("--headless", action="store_true", default=True, help="Selenium için başlıksız mod")
parser.add_argument("--temp_folder", type=str, default="temp", help="Geçici dosyalar için klasör")

# google search
parser.add_argument("--num_results", type=int, default=50, help="Google arama sonuçları sayısı")


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
# Durum bilgilerini göster
p_info(f"İçerik kontrol durumu: {ignore_content}")
p_info(f"Veritabanı kontrol durumu: {not ignore_db}") 





CONFIG = load_config_from_file()
if not CONFIG[0]:
    print(CONFIG[1])
    sys.exit()


databaseConfig = CONFIG[1]["database_config"]
insightFaceApp = initilate_insightface(CONFIG)
databaseTools = DatabaseTools(databaseConfig)



def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


clear_screen()

def search_google(query, num_results=num_results) -> list[str]:
    search_results = googlesearch.search(query, num_results=num_results)
    return search_results



    
# URL listesini hazırla
search_results = search_google(keyword)

p_info(f"\"{keyword}\" için google arama sonuçları alındı")


# Her URL için tarama işlemini başlat
for url in search_results:
    p_info(f"{url} için tarama işlemini başlatılıyor...")
    try:
        
        print_url = urllib.parse.unquote(url)
        p_info(f"{print_url} in facebook url i olup olmadığını kontrol ediliyor...")
        check_url = urllib.parse.urlparse(url)
        if check_url.netloc == "facebook.com":
            p_info(f"{print_url} bir facebook url'idir profil veya arama sonuçları için taranıyor...")
            if "facebook.com/public/" in urllib.parse.unquote(url):
                p_info(f"{print_url} bir facebook profil arama sonuçları url'idir...")
                # is facebook profile search
                chromeDriver = get_chrome_driver(
                    headless=headless_mode, 
                    executable_path=executable_path, 
                    driver_path=driver_path,
                    temp_base_dir=temp_folder
                    )
                facebookProfileCrawler = FacebookProfileCrawler(driver=chromeDriver, scroll_count=scroll_count, scroll_pause_time=scroll_pause_time)
                final_results = facebookProfileCrawler.crawl_search_results(url)
                facebookProfileCrawler.close_driver()
                
                
                p_info(f"{print_url} içerisindeki profil sayısı: {len(final_results)}")
                p_info(f"{print_url} içerisindeki profillerin taranması başlatılıyor (4 thread)...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_SIZE) as executor:
                    futures = []
                    for result in final_results:
                        profile_url = result.get('profile_url')
                        
                        if not profile_url:
                            continue
                    
                        print(f"İşleniyor: {profile_url}")
                        futures.append(executor.submit(facebook_thread, profile_url, databaseTools, insightFaceApp, executable_path, driver_path, headless_mode, temp_folder))
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        future.result()
                    except Exception as err:
                        p_error(f"Hata: {err}")
                
                p_info(f"{print_url} içerisindeki profillerin taranması tamamlandı.")
            else:
                p_info(f"{print_url} bir facebook profil url'idir profil taranıyor...")
                profile_url = url
                facebook_thread(
                    profile_url,
                    databaseTools,
                    insightFaceApp,
                    executable_path,
                    driver_path,
                    headless_mode,
                    temp_folder
                )
                p_info(f"{print_url} içerisindeki profil taranması tamamlandı.")
        else:
            p_info(f"{print_url} bir google arama sonuçları url'idir sayfa taranıyor...")
            
            # Tarama süresini ölç
            start_time = timeit.default_timer()
            # SingleDomainCrawler oluştur ve taramayı başlat
            p_info(f"{print_url} içerisindeki sayfa taranması başlatılıyor (selenium crawler)...")
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
                temp_folder=temp_folder
            )
            crawler.startCrawl(
                riskLevel=risk_level,
                category=category,
                save_image=save_image
            )
            # Tarama süresini raporla
            end_time = timeit.default_timer()
            print("*" * 40)
            p_info(f"Tarama süresi: {round(end_time - start_time, 1)} saniye")
            print("*" * 40)
        
    except KeyboardInterrupt:
        p_warn("Tarama kullanıcı tarafından durduruldu (CTRL+C).")
        break
    except Exception as e:
        p_error(f"Tarama sırasında hata oluştu: {str(e)}")
        continue



















