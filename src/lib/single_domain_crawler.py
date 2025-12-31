#!/usr/bin/env python3
# ? Local Librarys 
from .output.consolePrint                import p_info,p_warn, p_error
from .database_tools                     import DatabaseTools
from .single_domain_thread               import single_domain_thread
from HiveWebCrawler.Crawler              import WebCrawler
import time
import threading
from insightface.app import FaceAnalysis
import queue # Python's thread-safe queue
import threading # For Lock
import traceback
from urllib.parse import urlparse # Ana domaini parse etmek için

class SingleDomainCrawler():
    """
    Web sitelerini taramak ve resim içerisindeki yüzleri tespit etmek için kullanılan sınıf.
    """
    
    def __init__(
            self, 
            DatabaseToolkit_object: DatabaseTools,
            FirstTargetAddress: str,
            ThreadSize: int,
            CONFIG: list,
            insightFaceApp: FaceAnalysis,
            ignore_db: bool = False, 
            ignore_content: bool = False,
            # YENİ: Max Queue Size (optional, prevents excessive memory usage)
            max_queue_size: int = 0, # 0 means infinite,
            max_deph_for_crawl: int = 75  # Changed default to 75 as requested
            
        ) -> None:
        """
        SingleDomainCrawler sınıfının başlatıcı metodu.
        
        Args:
            DatabaseToolkit_object: Veritabanı işlemleri için araç kutusu
            FirstTargetAddress: İlk taranacak adres
            ThreadSize: Kullanılacak worker thread sayısı
            CONFIG: Yapılandırma ayarları
            insightFaceApp: Yüz tanıma uygulaması objesi
            ignore_db: Veritabanından geçmiş sonuçları görmezden gelme durumu (artık daha az relevant)
            ignore_content: HTML içeriğini görmezden gelme durumu
            max_queue_size: Kuyruğun maksimum boyutu (0 = sınırsız)
            max_deph_for_crawl: Tarama işleminin maksimum derinliği (kaç URL katmanına kadar inileceği)
        """
        self.Crawler        = WebCrawler()
        self.dbToolkit      = DatabaseToolkit_object
        self.InsightfaceApp = insightFaceApp
        self.FirstTarget    = FirstTargetAddress
        self.max_deph_for_crawl = max_deph_for_crawl
        p_info(f"Maksimum tarama derinliği: {self.max_deph_for_crawl}")
        
        # --- YENİ: Ana (Kök) Domaini Belirle ---
        try:
            parsed_first_target = urlparse(self.FirstTarget)
            first_domain = parsed_first_target.netloc
            # www. önekini kaldır (varsa)
            if first_domain.startswith("www."):
                self.root_domain = first_domain[4:]
            else:
                self.root_domain = first_domain
            if not self.root_domain:
                 raise ValueError("İlk hedef URL'den geçerli bir domain çıkarılamadı.")
            p_info(f"Ana (kök) domain belirlendi: {self.root_domain}")
        except Exception as e:
            p_error(f"Başlangıç URL'sinden kök domain belirlenirken hata: {e}")
            # Hata durumunda devam etmemek daha iyi olabilir
            raise ValueError(f"Başlangıç URL'si ({self.FirstTarget}) geçersiz veya domain çıkarılamıyor.") from e
        # ---------------------------------------
        
        self.ignore_database= ignore_db
        self.ThreadSize     = ThreadSize
        self.ignore_content = ignore_content

        # --- YENİ: Thread-safe Queue ve Visited Set ---
        self.url_queue = queue.Queue(maxsize=max_queue_size)
        self.visited_urls = set() # Başlangıçta tarananları tutacak set
        self.visited_lock = threading.Lock() # Set'e erişim için kilit
        self.active_threads = set() # Aktif thread'leri takip etmek için
        self.threads_lock = threading.Lock() # Thread setine erişim için kilit
        self.stored_no_face_image_url_set = set() # Daha önce yüz bulunmayan resimleri tutacak set
        self.stored_no_face_image_url_lock = threading.Lock() # Set'e erişim için kilit
        
        # --- YENİ: URL Derinliği Sözlüğü ---
        self.url_depths = {} # URL'lerin derinliğini tutacak sözlük
        self.url_depths_lock = threading.Lock() # Sözlük erişimi için kilit
        # ---------------------------------------------

    def add_url_to_queue(self, url: str, depth: int = None, parent_url: str = None):
        """
        URL'yi ziyaret edilmemişse kuyruğa ve ziyaret edilenler setine ekler.
        Thread-safe.
        
        Args:
            url: Eklenecek URL
            depth: URL'nin derinliği (None ise, parent_url'den hesaplanacak)
            parent_url: URL'nin ebeveyn URL'si (derinlik hesaplamak için)
        """
        with self.visited_lock, self.url_depths_lock:
            # URL zaten ziyaret edilmiş mi?
            if url in self.visited_urls:
                return
            
            # Derinlik hesaplama
            current_depth = 0
            if depth is not None:
                current_depth = depth
            elif parent_url is not None and parent_url in self.url_depths:
                current_depth = self.url_depths[parent_url] + 1
            
            # Maksimum derinlik kontrolü
            if current_depth > self.max_deph_for_crawl:
                p_info(f"Maksimum derinliğe ulaşıldı ({current_depth} > {self.max_deph_for_crawl}), URL atlanıyor: {url}")
                return
                
            # URL'yi işlenmek üzere işaretle ve derinliğini kaydet
            self.visited_urls.add(url)
            self.url_depths[url] = current_depth
            
            try:
                # URL ve derinlik bilgisini tuplı olarak kuyruğa ekle
                self.url_queue.put_nowait((url, current_depth)) 
                p_info(f"Kuyruğa eklendi: {url} (Derinlik: {current_depth}, Kuyruk boyutu: {self.url_queue.qsize()})")
            except queue.Full:
                p_warn(f"Kuyruk dolu! URL eklenemedi: {url}")

    def worker_thread(self, thread_id: int, riskLevel: str = None, category: str = None, save_image: bool = False):
        """
        Kuyruktan URL alıp işleyen worker thread fonksiyonu.
        """
        p_info(f"Worker thread {thread_id} başlatıldı.")
        while True:
            try:
                # Kuyruktan URL ve derinlik bilgisini al (1 saniye bekle)
                url_info = self.url_queue.get(timeout=1)
                if isinstance(url_info, tuple) and len(url_info) == 2:
                    current_target, current_depth = url_info
                else:
                    # Eski format geriye uyumluluk için
                    current_target = url_info
                    current_depth = 0  # Bilinmiyorsa varsayılan 0
            except queue.Empty:
                # Kuyruk boşsa ve başka aktif thread yok gibi görünüyorsa (race condition olabilir, ama bir gösterge)
                # VEYA ana thread sinyal verdiyse çıkış yap (henüz sinyal mekanizması yok)
                # Şimdilik basitçe kuyruk boşsa bir süre sonra tekrar kontrol etsin
                # Daha sağlam bir mekanizma için Event kullanılabilir.
                with self.threads_lock:
                     # Eğer bu son aktif thread ise ve kuyruk hala boşsa çıkabilir
                     if len(self.active_threads) == 1 and self.url_queue.empty():
                          p_info(f"Worker thread {thread_id} kuyruk boş ve muhtemelen son thread, çıkıyor.")
                          break 
                time.sleep(0.5) # Kuyruk boşsa CPU'yu yorma
                continue
            
            p_info("*"*100)
            p_info(f"[Thread-{thread_id}] İşleniyor: {current_target} (Derinlik: {current_depth}, Kuyruk boyutu: {self.url_queue.qsize()})")
            p_info("*"*100)
            try:
                # Eski thread fonksiyonunu çağır ama yeni URL ekleme mekanizmasını kullanacak
                single_domain_thread(
                    currentTarget=current_target, 
                    Crawler=self.Crawler, 
                    root_domain=self.root_domain, # YENİ: Kök domaini gönder
                    add_url_func=lambda url: self.add_url_to_queue(url, parent_url=current_target), # Derinlik bilgisini de aktar
                    self_databaseToolkit=self.dbToolkit, 
                    self_insightFaceApp=self.InsightfaceApp,
                    ignore_content=self.ignore_content,
                    riskLevel=riskLevel,
                    category=category,
                    save_image=save_image,
                    stored_no_face_image_url_set=self.stored_no_face_image_url_set,
                    stored_no_face_image_url_lock=self.stored_no_face_image_url_lock,
                    current_depth=current_depth,  # Geçerli derinliği de gönder
                    max_depth=self.max_deph_for_crawl  # Maksimum derinliği gönder
                )
            except Exception as e:
                p_error(f"[Thread-{thread_id}] '{current_target}' işlenirken hata: {e}")
                traceback.print_exc() # Detaylı hata logu
            finally:
                # İşlem bitti veya hata oluştu, task_done() çağır
                self.url_queue.task_done()
                p_info(f"[Thread-{thread_id}] Tamamlandı: {current_target}")

        # Thread bittiğinde kendini aktif listeden çıkar
        with self.threads_lock:
            self.active_threads.remove(threading.current_thread())
        p_info(f"Worker thread {thread_id} bitti.")

    def startCrawl(self, riskLevel: str = None, category: str = None, save_image: bool = False) -> None:
        """
        Tarama işlemini başlatır. Worker thread'leri oluşturur ve yönetir.
        
        Args:
            riskLevel: Tarama için risk seviyesi 
            category: Tarama kategorisi
            save_image: Resmi kaydetme durumu
            
        Returns:
            None
        """
        p_info(f"Tarama başlatılıyor: {self.FirstTarget}")
        p_info(f"Thread sayısı: {self.ThreadSize}")
        p_info(f"Ignore Content: {self.ignore_content}")
        p_info(f"Save Image: {save_image}")
        p_info(f"Maksimum tarama derinliği: {self.max_deph_for_crawl}")

        # İlk hedef URL'yi kuyruğa ekle (derinlik 0)
        self.add_url_to_queue(self.FirstTarget, depth=0)

        threads = []
        for i in range(self.ThreadSize):
            thread = threading.Thread(
                target=self.worker_thread, 
                args=(i + 1, riskLevel, category, save_image), # Thread ID ekle
                daemon=True # Ana program bittiğinde thread'ler de bitsin
            )
            threads.append(thread)
            with self.threads_lock:
                 self.active_threads.add(thread) # Başlamadan aktif listesine ekle
            thread.start()

        # Kuyruk boşalana kadar bekle
        p_info("Ana thread kuyruğun boşalmasını bekliyor...")
        self.url_queue.join() # Kuyruktaki tüm işler bitene kadar bloklar (task_done çağrılmalı)
        p_info("Kuyruktaki tüm işler tamamlandı.")

        # Worker thread'lerin bitmesini bekle (join() sonrası emin olmak için)
        # Normalde daemon=True olduğu için ana thread bitince kapanırlar,
        # ama join() sonrası hala çalışan varsa diye kontrol edebiliriz.
        p_info("Worker thread'lerin bitmesi bekleniyor (join sonrası)...")
        for thread in threads:
             thread.join(timeout=5.0) # Maksimum 5 saniye bekle
             if thread.is_alive():
                  p_warn(f"Thread {thread.name} zaman aşımı sonrası hala çalışıyor.")

        p_info("Tarama tamamlandı.")




