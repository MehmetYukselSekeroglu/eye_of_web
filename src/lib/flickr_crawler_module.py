#! /usr/bin/env python3
# -*- coding: utf-8 -*-
from lib.flickr_crawler.flickr_modules.image_downloader import ImageDownloader
from lib.flickr_crawler.flickr_modules.link_extractor import LinkExtractor
from lib.database_tools import DatabaseTools
from insightface.app import FaceAnalysis
from lib.output.consolePrint import p_info,p_error,p_warn
from lib.selenium_tools.selenium_browser import get_chrome_driver
from lib.selenium_tools.selenium_browser import BrowserToolkit
import concurrent.futures
from lib.url_parser import prepare_url
import cv2
import numpy as np
import hashlib
import time

# Timeout değeri (örnek, daha sonra yapılandırılabilir)
DEFAULT_TIMEOUT = 45
WAIT_BETWEEN_PHOTOS = 1.0 # Fotoğraflar arası bekleme süresi (saniye)
WAIT_BETWEEN_PAGES = 2.0 # Sayfalar arası bekleme süresi (saniye)

class FlickrCrawlerModule():
    def __init__(self,
                databaseTools:DatabaseTools,
                insightFaceApp:FaceAnalysis,
                targetUrl:str,
                maxPages:int,
                driver_path:str,
                executable_path:str,
                imageThreadCount:int=2,
                riskLevel:str="",
                category:str="",
                timeout: int = DEFAULT_TIMEOUT # Timeout parametresi eklendi
        ):
        
        self.chrome_driver = get_chrome_driver(
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            profile_dir_path=None,
            executable_path=executable_path,
            driver_path=driver_path
        )
        self.link_extractor = LinkExtractor(self.chrome_driver)
        self.image_downloader = ImageDownloader(self.chrome_driver)
        self.databaseTools = databaseTools
        self.insightFaceApp = insightFaceApp
        self.targetUrl = targetUrl
        self.maxPages = maxPages
        self.imageThreadCount = imageThreadCount
        self.parsedCurrentTarget = prepare_url(targetUrl)
        self.riskLevel = riskLevel
        self.category = category
        self.timeout = timeout # Timeout değeri atandı
    def _subWorker(self,photo_url):
        try:
            # Timeout parametresi eklendi
            photo_data = self.image_downloader.download_from_page_as_bytes(photo_url, timeout=self.timeout)
            
            photo_success = photo_data[0]
            photo_blob = photo_data[1]
            
            if not photo_success:
                p_error("Error downloading image: "+photo_url)
                return None
            
            # Resim başlığını al
            photo_title = photo_data[2]
            imageHash = hashlib.sha1(photo_blob).hexdigest()
            photoCv2 = np.frombuffer(photo_blob, dtype=np.uint8)
            photoCv2 = cv2.imdecode(photoCv2, cv2.IMREAD_COLOR)
            
            
            parsed_image_url = prepare_url(photo_url)
            
            
            
            faces = self.insightFaceApp.get(photoCv2)
            if len(faces) < 1:
                p_error("No faces detected in image: "+photo_url)
                return None
            
            
            
            
            # Veritabanına kaydet
            _b = self.databaseTools.insertImageBased(
                protocol=self.parsedCurrentTarget["protocol"],
                baseDomain=self.parsedCurrentTarget["base_domain"],
                urlPath=self.parsedCurrentTarget["path"],
                urlPathEtc=self.parsedCurrentTarget["etc"],
                imageProtocol=parsed_image_url["protocol"],
                imageDomain=parsed_image_url["base_domain"],
                imagePath=parsed_image_url["path"],
                imagePathEtc=parsed_image_url["etc"],
                imageTitle=f"Flickr Image From {self.targetUrl}",
                imageBinary=photo_blob,
                imageHash=imageHash,
                faces=faces,
                riskLevel=self.riskLevel,
                category=self.category,
                save_image=True,
                Source='flickr'
            )
            p_info(f"Image saved to database: {_b}")
            
        
        except Exception as err:
            p_error("Error processing image: "+str(err))
            return None
        
    def start(self):
        p_info("Starting Flickr Crawler Module")
        p_info("Target URL: "+self.targetUrl)
        p_info("Max Pages: "+str(self.maxPages))
        p_info(f"Image processing threads: {self.imageThreadCount}")
        p_info(f"Timeout: {self.timeout} seconds")

        processed_photo_count = 0
        processed_page_count = 0
        all_page_urls = []

        try:
            p_info("Detecting pagination links...")
            # Önce tüm sayfa URL'lerini (varsa) alalım (referans koddaki gibi)
            # extract_all_pages_urls metodu sayfa URL'lerini döndürmeli
            all_page_urls = self.link_extractor.extract_all_pages_urls(self.targetUrl, max_pages=self.maxPages)

            if not all_page_urls:
                p_warn("No pagination URLs found or only one page detected. Processing target URL as a single page.")
                all_page_urls = [self.targetUrl] # Sadece başlangıç URL'sini işle
            else:
                p_info(f"Found {len(all_page_urls)} pages to process.")

            # Eğer maxPages belirtilmişse ve bulunan sayfa sayısı daha fazlaysa listeyi kırp
            if self.maxPages > 0 and len(all_page_urls) > self.maxPages:
                p_info(f"Limiting processing to first {self.maxPages} pages based on maxPages setting.")
                all_page_urls = all_page_urls[:self.maxPages]

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.imageThreadCount) as executor:
                for i, page_url in enumerate(all_page_urls):
                    processed_page_count += 1
                    p_info(f"\n{'='*30} Processing Page {processed_page_count}/{len(all_page_urls)} {'='*30}")
                    p_info(f"Page URL: {page_url}")

                    # Her sayfa için fotoğraf URL'lerini çekelim
                    photo_urls_on_page = self.link_extractor.extract_urls(page_url, timeout=self.timeout)

                    if not photo_urls_on_page:
                        p_warn(f"No photo URLs found on page: {page_url}")
                        continue # Sonraki sayfaya geç

                    p_info(f"Found {len(photo_urls_on_page)} photo URLs on this page.")

                    futures = []
                    for j, photo_url in enumerate(photo_urls_on_page):
                        futures.append(executor.submit(self._subWorker, photo_url))
                        # Fotoğraflar arası bekleme (isteğe bağlı, sunucuyu yormamak için)
                        if j < len(photo_urls_on_page) - 1:
                            time.sleep(WAIT_BETWEEN_PHOTOS)

                    # Bu sayfadaki işlerin bitmesini bekle ve sonuçları al
                    results = [future.result() for future in concurrent.futures.as_completed(futures)]
                    successful_tasks = sum(1 for r in results if r is True)
                    processed_photo_count += successful_tasks
                    p_info(f"Successfully processed {successful_tasks} photos from page {processed_page_count}.")

                    # Sayfalar arası bekleme (isteğe bağlı)
                    if i < len(all_page_urls) - 1:
                        p_info(f"Waiting {WAIT_BETWEEN_PAGES} seconds before next page...")
                        time.sleep(WAIT_BETWEEN_PAGES)

            p_info("\n" + "="*50)
            p_info("Flickr Crawler Module Finished")
            p_info(f"Total pages processed: {processed_page_count}")
            p_info(f"Total photos successfully processed: {processed_photo_count}")
            p_info("="*50)

        except Exception as e:
            p_error(f"An error occurred during crawling: {e}")
            import traceback
            traceback.print_exc() # Hatanın detayını görmek için
        finally:
            # Tarayıcıyı her durumda kapatmayı garanti altına alalım
            self._cleanup()

    def _cleanup(self):
        """Clean up resources (close browser)."""
        if hasattr(self, 'chrome_driver') and self.chrome_driver:
            try:
                p_info("Closing browser...")
                self.chrome_driver.quit()
                self.chrome_driver = None # Referansı temizle
                p_info("Browser closed.")
            except Exception as e:
                p_error(f"Error closing browser: {e}")

    def __del__(self):
        # __del__ içinde çağırmak yerine explicit cleanup metodu daha güvenilir
        # self.chrome_driver.quit()
        self._cleanup() # Yine de __del__ içinde çağrılabilir, ancak start içinde finally bloğu daha iyi













