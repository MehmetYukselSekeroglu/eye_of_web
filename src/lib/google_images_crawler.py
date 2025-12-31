#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Google Görseller'den resim arama ve indirme aracı
#
# 2025-04-30
#



from lib.google_images_crawler_tools import *
from lib.selenium_tools.selenium_browser import BrowserToolkit,get_chrome_driver
from lib.output.consolePrint import p_info, p_error, p_warn, p_log
import concurrent.futures
from lib.database_tools import DatabaseTools
from lib.proccess_image import proccessImage
from lib.user_agent_tools import randomUserAgent
from lib.selenium_tools import selenium_browser
import insightface

class               GoogleImagesCrawler:
    def __init__(self, databaseToolkit: DatabaseTools,
                 faceAnalysis: insightface.app.FaceAnalysis,
                 numThreads: int = 2
                 ):
        self.databaseToolkit = databaseToolkit
        self.driver = get_chrome_driver()
        self.perma_link = None
        self.numThreads = numThreads
        self.faceAnalysis = faceAnalysis
        
    def start(self, keyword: str, num_images: int = 25, scroll_attempts_limit: int = 2, headless: bool = True) -> List[str]:
        """
        Google Görseller'den resim arama ve indirme işlemini başlatır.

        Args:
            keyword: Arama kelimesi
            num_images: İndirilecek resim sayısı
            scroll_attempts_limit: Tarama yapılırken kaç kere aşağı kaydırma yapılacağı
            headless: Tarama yapılırken headless modda çalışıp çalışmayacağı

        Returns:
            İndirilen resimlerin dosya yollarının listesi
        """
        p_info(f"Google Görseller'den '{keyword}' için {num_images} resim aranıyor...")
        result = find_image_urls_from_google(
            keyword=keyword,
            scroll_attempts_limit=scroll_attempts_limit,
            num_urls_target=num_images,
            headless=headless
        )
        p_info(f"Google Görseller'den '{keyword}' için {len(result)} resim bulundu.")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.numThreads) as executor:
            futures = []
            
            # Use the url_parser to properly parse the Google Images search URL
            from lib.url_parser import prepare_url
            
            # Create the Google Images search URL with the keyword
            google_search_url = f"https://www.google.com/search?q={keyword}&tbm=isch"
            
            # Parse the URL to get the components needed for database storage
            parsedCurrentTarget = prepare_url(google_search_url)
            
            
            for url in result:
                single_image_list = [url, f"Google Images Search Results For {keyword}"]
                futures.append(
                    executor.submit(proccessImage,
                                    single_image_list=single_image_list,
                                    parsedCurrentTarget=parsedCurrentTarget,
                                    self_databaseToolkit=self.databaseToolkit,
                                    self_insightFaceApp=self.faceAnalysis,
                                    riskLevel="normal",
                                    category="google_images",
                                    save_image=True)
                )
            
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    response = future.result()
                    p_info(f"Resim işlendi ...")
                except Exception as e:
                    p_error(f"Resim işleme hatası: {e}")
















