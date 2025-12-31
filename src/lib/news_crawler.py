import concurrent.futures
from .output.consolePrint import p_info, p_error, p_warn, p_log
from .database_tools import DatabaseTools
from HiveWebCrawler.Crawler import WebCrawler
from .proccess_image import proccessImage
from .url_parser import prepare_url
from .url_image_download import get_ImageFromUrl
from .user_agent_tools import randomUserAgent
from .url_checker import is_safe_url__html
import threading
import time

class SingleNewsCrawler():
    
    def __init__(self,
                DatabaseToolkit_object: DatabaseTools,
                FirstTargetAddress: str,
                ThreadSize: int,
                CONFIG: list,
                ignore_db: bool = False,
                ignore_content: bool = False,
                NewsTitle: str = None,
                NewsDate: str = None,
                insightfaceApp = None,
                 ) -> None:
        
        self.Crawler        = WebCrawler()
        self.dbToolkit      = DatabaseToolkit_object
        self.InsightfaceApp = insightfaceApp
        self.FirstTarget    = FirstTargetAddress
        self.TargetList     = []
        self.TargetList.append(self.FirstTarget)
        self.ignore_database= ignore_db
        self.ThreadSize     = ThreadSize
        self.ignore_content = ignore_content
        self.NewsTitle      = NewsTitle
        self.NewsDate       = NewsDate
        self.CrawledBuffer  = []
        
    def uniqList(self, target_list) -> list:
        """
        Hedef URL listesindeki tekrarlanan ve zaten taranmış URL'leri filtreleyerek benzersiz hedef listesi oluşturur.
        
        Args:
            target_list: Filtrelenecek hedef URL listesi
            
        Returns:
            Benzersiz ve taranmamış URL'lerin listesi
        """
        new_list = list(set(target_list))
        return new_list
    
    def startCrawl(self, riskLevel: str = None, category: str = None, save_image: bool = False) -> None:
        """
        Tarama işlemini başlatır.
        
        Args:
            riskLevel: Tarama için risk seviyesi 
            category: Tarama kategorisi
            save_image: Resmi kaydetme durumu
            
        Returns:
            None
        """
        # Tarama döngüsü
        while True:
            currentTarget = None
            
            # Hedef URL kalmadıysa ve tüm thread'ler tamamlandıysa döngüden çık
            if currentTarget is None and len(self.TargetList) < 1:
                p_info("Herhangi bir hedef kalmadı, döngüden çıkılıyor.")
                break

            # Listeden sıradaki hedefi al
            if len(self.TargetList) > 0:
                currentTarget = self.TargetList.pop(0) 
            else:
                # Hedef kalmadıysa döngünün başına dön
                continue
            
            # Taranmış URL'leri filtrele
            if not self.ignore_database:
                self.TargetList = self.uniqList(self.TargetList)
            else:
                self.TargetList = list(set(self.TargetList))
            
            # URL boşsa veya None ise atla
            if not currentTarget:
                continue
                
            # Bilgilendirme mesajları göster
            print(f"[HEDEF]: {currentTarget}")
            print(f"[TOPLAM]: {len(self.TargetList)}")
            
            self.CrawledBuffer.append(currentTarget)
            
            """
            # Veritabanında kontrol et
            isAddressCrawled = self.dbToolkit.check_crawled(raw_url=currentTarget)
            if isAddressCrawled and not self.ignore_database:
                p_info(f"{currentTarget} daha önce taranmış, atlanıyor.")
                continue
            """
            print(f"thread içi: {self.ignore_content}")
            imageTargetList = []
            
            # URL güvenliğini kontrol et
            if not is_safe_url__html(currentTarget) and not self.ignore_content:
                p_warn(f"{currentTarget} güvenli değil, atlanıyor.")
                continue
                
            # Hedef URL'ye istek gönder
            crawlData = self.Crawler.send_request(
                target_url=currentTarget,
                timeout_sec=10,
                req_headers={
                    "User-Agent": randomUserAgent()
                })
                    
            if not crawlData["success"]:
                p_error(f"{currentTarget} -> {crawlData['message']}")
                continue
            
            # URL'yi parse et
            parsedCurrentTarget = prepare_url(currentTarget)
            
            # Veri çıkarma işlemleri
            emails_from_url = self.Crawler.crawl_email_address_from_response_href(crawlData["data"])
            phone_from_url = self.Crawler.crawl_phone_number_from_response_href(crawlData["data"])
            links_from_url = self.Crawler.crawl_links_from_pesponse_href(parsedCurrentTarget["base_domain"], crawlData["data"])
            image_from_url = self.Crawler.crawl_image_from_response(crawlData["data"], parsedCurrentTarget["base_domain"])
                    
            _phone_list = []
            _email_list = []
        
            # E-posta adreslerini işle
            if len(emails_from_url["data_array"]) < 1:
                p_warn(f"No email detected on -> {currentTarget}")
                _email_list = None
            else:
                for single_email_list in emails_from_url["data_array"]:
                    _email = single_email_list[1]
                    _email_list.append(_email)
                    
            # Telefon numaralarını işle
            if len(phone_from_url["data_array"]) < 1:
                p_warn(f"No phone detected on -> {currentTarget}")
                _phone_list = None
            else:
                for single_phone_list in phone_from_url["data_array"]:
                    _phone = single_phone_list[1]
                    _phone_list.append(_phone)
                    
            # Veritabanına sayfa bilgilerini ekle
            _a = self.dbToolkit.insertPageBased(
                protocol=parsedCurrentTarget["protocol"],
                baseDomain=parsedCurrentTarget["base_domain"],
                urlPath=parsedCurrentTarget["path"],
                urlPathEtc=parsedCurrentTarget["etc"],
                phoneNumber_list=_phone_list,
                emailAddress_list=_email_list,
                categortyNmae=category
                )
            p_info(_a)
            
            # Resimleri işle
            for single_list in image_from_url["data_array"]:
                imageTargetList.append(single_list[0])
            
            imageTargetList = list(set(imageTargetList))
            p_info(f"{currentTarget} içerisindeki toplam resim adeti: {len(imageTargetList)}")
            
            # Resimleri işlemek için thread havuzu oluştur
            
            
            for idx, single_image_list in enumerate(imageTargetList):
                imageTargetList[idx] = [single_image_list, self.NewsTitle]

            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.ThreadSize) as threadExec:
                for single_image_list in imageTargetList:
                    
                    
                    threadExec.submit(
                        proccessImage, 
                        single_image_list, 
                        parsedCurrentTarget, 
                        self.dbToolkit, 
                        self.InsightfaceApp,
                        riskLevel,
                        category,
                        save_image
                    )
                
            
            p_info(f"{currentTarget} taraması tamamlandı.")
            self.dbToolkit.insert_is_crawled(currentTarget)
            