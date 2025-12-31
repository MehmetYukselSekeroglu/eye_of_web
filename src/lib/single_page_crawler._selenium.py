#!/usr/bin/env python3
# ? Local Librarys 
from .output.consolePrint                import p_info,p_warn
from .init_insightface                   import initilate_insightface
from .database_tools                     import DatabaseTools
from .single_domain_selenium_thread      import single_domain_thread__selenium
from HiveWebCrawler.Crawler              import WebCrawler
import time
import threading


class SingleDomainCrawlerSelenium():
    """
    Web sitelerini taramak ve resim içerisindeki yüzleri tespit etmek için kullanılan sınıf.
    """
    
    def __init__(
            self, 
            DatabaseToolkit_object: DatabaseTools,
            FirstTargetAddress: str,
            ThreadSize: int,
            CONFIG: list,
            ignore_db: bool = False, 
            ignore_content: bool = False,
            executable_path: str = None,
            driver_path: str = None
        ) -> None:
        """
        SingleDomainCrawler sınıfının başlatıcı metodu.
        
        Args:
            DatabaseToolkit_object: Veritabanı işlemleri için araç kutusu
            FirstTargetAddress: İlk taranacak adres
            ThreadSize: Kullanılacak thread sayısı
            CONFIG: Yapılandırma ayarları
            ignore_db: Veritabanından geçmiş sonuçları görmezden gelme durumu
            ignore_content: HTML içeriğini görmezden gelme durumu
            executable_path: ChromeDriver'ın yolunu belirtmek için kullanılır
            driver_path: ChromeDriver'ın yolunu belirtmek için kullanılır
        """
        self.Crawler        = WebCrawler()
        self.dbToolkit      = DatabaseToolkit_object
        self.InsightfaceApp = initilate_insightface(main_conf=CONFIG)
        self.FirstTarget    = FirstTargetAddress
        self.TargetList     = []
        self.TargetList.append(self.FirstTarget)
        self.ignore_database= ignore_db
        self.ThreadSize     = ThreadSize
        self.ignore_content = ignore_content
        self.CrawledBuffer  = []
        self.executable_path = executable_path
        self.driver_path     = driver_path
        
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
                p_info("Thread'lar bekleniyor...")
                
                # Aktif thread'lerin tamamlanmasını bekle
                while threading.activeCount() > 1:
                    time.sleep(0.1)
                
                p_info("Thread'lar tamamlandı.")
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
                
            if currentTarget not in self.CrawledBuffer:
                self.CrawledBuffer.append(currentTarget)
            else:
                p_warn(f"(Buffer) Target already crawled: {currentTarget}")
                continue
            
            # Thread yönetimi: Eğer listedeki hedef sayısı thread sayısından fazlaysa
            # Yeni thread başlat, değilse ana thread üzerinde işlem yap
            if len(self.TargetList) > self.ThreadSize:
                # Aktif thread sayısı maksimum thread sayısını aşıyorsa bekle
                while threading.activeCount() >= self.ThreadSize:
                    time.sleep(0.1)

                threading.Thread(
                    target=single_domain_thread__selenium, 
                    args=(
                        currentTarget, 
                        self.Crawler, 
                        self.TargetList, 
                        self.dbToolkit, 
                        self.InsightfaceApp,
                        self.ignore_content,
                        True,
                        4,
                        riskLevel,
                        category,
                        save_image,
                        self.executable_path,
                        self.driver_path
                    ),
                    daemon=True
                ).start()
            else:
                # Ana thread üzerinde işlem yap
                single_domain_thread__selenium(
                    currentTarget, 
                    self.Crawler, 
                    self.TargetList, 
                    self.dbToolkit, 
                    self.InsightfaceApp,
                    ignore_content=self.ignore_content,
                    riskLevel=riskLevel,
                    category=category,
                    save_image=save_image,
                    executable_path=self.executable_path,
                    driver_path=self.driver_path
                )




