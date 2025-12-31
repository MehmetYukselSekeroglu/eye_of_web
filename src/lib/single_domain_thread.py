#! /usr/bin/env python3
#! -*- coding: utf-8 -*-
#! Author: Wesker
#! Date: 2025-03-19

import concurrent.futures
import traceback
from typing import Callable
from lib.output.consolePrint import p_info, p_error, p_warn, p_log
from insightface.app import FaceAnalysis
from lib.output.banner import printBanner
from lib.database_tools import DatabaseTools
from lib.url_parser import prepare_url
from lib.url_checker import is_safe_url__html
from lib.proccess_image import proccessImage
from lib.user_agent_tools import randomUserAgent
from HiveWebCrawler.Crawler import WebCrawler
from urllib.parse import urlparse, unquote, urlunparse, urljoin
from lib.css_image_extractor import extract_css_background_images
import threading
def single_domain_thread(
    currentTarget: str,
    Crawler: WebCrawler,
    root_domain: str,
    add_url_func: Callable[[str], None],
    self_databaseToolkit: DatabaseTools,
    self_insightFaceApp: FaceAnalysis,
    ignore_content: bool = False,
    autoSubThread: bool = True,
    subThreadSize: int = 2,
    riskLevel: str = None,
    category: str = None,
    save_image: bool = False,
    stored_no_face_image_url_set:set=None,
    stored_no_face_image_url_lock:threading.Lock=None,
    current_depth: int = 0,
    max_depth: int = 75
    ):
    """
    Belirtilen hedef URL için tek domain tarama işlevini gerçekleştirir.
    
    Args:
        currentTarget: Taranacak URL
        Crawler: Web crawler nesnesi
        root_domain: Taramanın başladığı kök domain (örn: 'example.com')
        add_url_func: URL ekleme fonksiyonu
        self_databaseToolkit: Veritabanı araç kutusu
        self_insightFaceApp: Yüz analizi nesnesi
        ignore_content: HTML içeriğini kontrol etmeden geçme durumu
        autoSubThread: Alt thread kullanımı
        subThreadSize: Alt thread sayısı
        riskLevel: Risk seviyesi
        category: Kategori
        save_image: Resim kaydetme durumu
        stored_no_face_image_url_set: Yüz bulunmayan resimlerin URL'lerini tutacak set
        stored_no_face_image_url_lock: Set'e erişim için kilit
        current_depth: Mevcut URL'nin derinliği
        max_depth: İzin verilen maksimum tarama derinliği
    
    Returns:
        None
    """
    # Taranacak resim URL'lerini saklayan liste
    imageTargetList = []
    current_thread_name = threading.current_thread().name

    # Forbidden extensions check for currentTarget
    try:
        parsed_initial_url = urlparse(currentTarget)
        current_path = parsed_initial_url.path.lower()
        forbidden_extensions = ('.exe',".msi", '.json', '.pdf', '.xls', '.xlsx', '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
                              '.doc', '.docx', '.ppt', '.pptx', '.txt', '.csv', '.xml', '.rss', '.mp3', '.mp4', '.avi',
                              '.mov', '.wmv', '.flv', '.wav', '.ogg', '.iso', '.img', '.bin', '.dll', '.sys', '.msi',
                              '.apk', '.ipa', '.jar', '.class', '.py', '.js', '.css', '.sql', '.db', '.sqlite', '.log')
        if any(current_path.endswith(ext) for ext in forbidden_extensions):
            p_warn(f"[{current_thread_name}] Hedef URL yasaklanmış bir dosya uzantısına sahip, atlanıyor: {currentTarget}")
            return
    except ValueError:
        p_warn(f"[{current_thread_name}] Hedef URL parse edilemedi, atlanıyor: {currentTarget}")
        return

    p_log(f"[{current_thread_name}] Başladı: {currentTarget} (Derinlik: {current_depth}/{max_depth})")

    """
    # URL'nin HTML içerik durumunu kontrol et
    if not is_safe_url__html(currentTarget) and not ignore_content:
        p_warn(f"Adres HTML içeriğine sahip değildir: {currentTarget}")
        return        
    """        
    # Crawler ile URL'ye istek gönder
    crawlData = Crawler.send_request(
        target_url=currentTarget,
        timeout_sec=10,
        req_headers={
            "User-Agent": randomUserAgent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "Referer": "https://www.google.com/search?q=site+information"
        })
            
    # İstek başarısız olduysa işlemi sonlandır
    if not crawlData["success"]:
        # Daha detaylı hata logu
        error_msg = crawlData.get('message', 'Bilinmeyen istek hatası')
        status_code = crawlData.get('status_code', 'N/A')
        p_error(f"[{current_thread_name}] İstek hatası: {currentTarget} -> Durum: {status_code}, Mesaj: {error_msg}")
        return
    else:
        p_log(f"[{current_thread_name}] İçerik alındı: {currentTarget}")
    
    # URL'yi ayrıştır
    parsedCurrentTarget = prepare_url(currentTarget)
    
    # Crawler ile URL içeriğinden e-posta, telefon, bağlantı ve resim bilgilerini çıkar
    emails_from_url = Crawler.crawl_email_address_from_response_href(crawlData["data"])
    phone_from_url = Crawler.crawl_phone_number_from_response_href(crawlData["data"])
    links_from_url = Crawler.crawl_links_from_pesponse_href(parsedCurrentTarget["base_domain"], crawlData["data"])
    image_from_url = Crawler.crawl_image_from_response(crawlData["data"], parsedCurrentTarget["base_domain"])
    css_image_from_url = extract_css_background_images(currentTarget, crawlData["data"])
    # E-posta ve telefon listelerini hazırla
    _phone_list = []
    _email_list = []
    
    # URL'den çıkarılan bağlantıları işle
    if len(links_from_url["data_array"]) > 0:
        for single_link_list in links_from_url["data_array"]:
            _url = str(single_link_list[0])
            _title = single_link_list[1]
            
            if _url.startswith("#"):
                continue
            
            if "namaz" in _url.lower() and "vakit" in _url.lower() or "namaz" in _url.lower() or "hava" in _url.lower() and "durumu" in _url.lower():
                p_log(f"[{current_thread_name}] Namaz vakitleri veya hava durumu URL'si, atlanıyor: {_url}")
                continue
            
            # URL formatını düzenle (fragment temizleme) ve parse et
            # Protokol kontrolünden önce parse etmeliyiz ki parsed_url hep tanımlı olsun
            try:
                # Önce parse edip, sonra fragment'ı temizleyelim
                parsed_url = urlparse(_url)
                _url = urlunparse(parsed_url._replace(fragment="")) # Fragment'ı temizle
            except ValueError:
                p_warn(f"[{current_thread_name}] Geçersiz URL formatı, atlanıyor: {_url}")
                continue # Sonraki linke geç
            
            # URL formatını düzenle (protokol ekleme ve göreceli path birleştirme)
            if not _url.startswith("http://") and not _url.startswith("https://"):
                if _url.startswith("//"):
                    # Protocol-relative URL (//) - add just the protocol
                    _url = f"{parsedCurrentTarget['protocol']}:{_url}"
                elif _url.startswith("/"):
                    # Absolute path - combine with domain
                    _url = f"{parsedCurrentTarget['protocol']}://{parsedCurrentTarget['base_domain']}{_url}"
                elif _url.startswith(parsedCurrentTarget["base_domain"]) or \
                     (_url.startswith(parsedCurrentTarget["base_domain"].replace("www.", "")) and "www." in parsedCurrentTarget["base_domain"]):
                    # URL already has the domain, just add protocol
                    # Check if there's a duplicate domain in the URL and remove it if needed
                    domain_parts = _url.split("/")
                    if len(domain_parts) > 1 and parsedCurrentTarget["base_domain"] in domain_parts[1:]:
                        # There's a duplicate domain in the path, clean it up
                        _url = f"{parsedCurrentTarget['protocol']}://{parsedCurrentTarget['base_domain']}/{'/'.join(domain_parts[domain_parts[1:].index(parsedCurrentTarget['base_domain'])+2:])}"
                    else:
                        # Normal case - just add the protocol
                        _url = f"{parsedCurrentTarget['protocol']}://{_url}"
                elif ":" not in _url: 
                    # Relative path - use urljoin for proper URL resolution
                    try:
                        _url = urljoin(currentTarget, _url)
                        try: 
                            parsed_url = urlparse(_url)
                        except ValueError:
                            p_warn(f"[{current_thread_name}] urljoin sonrası geçersiz URL, atlanıyor: {_url}")
                            continue
                    except ValueError:
                        p_warn(f"[{current_thread_name}] urljoin sonrası geçersiz URL, atlanıyor: {_url}")
                        continue
                else:
                    # Other schemes (mailto:, tel:, javascript:, etc.)
                    p_log(f"[{current_thread_name}] Desteklenmeyen şema veya format, kuyruğa eklenmiyor: {_url}")
                    continue
            
            # Resim dosyaları için kontrol
            is_image = False
            _url_path = str(parsed_url.path)
            for image_extension in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff", ".heic", ".heif"]:
                if _url_path.lower().endswith(image_extension):
                    if [_url, _title] not in imageTargetList:
                        imageTargetList.append([_url, _title])
                    is_image = True
                    break
            
            if is_image:
                continue
            
            # Forbidden extensions check for discovered links
            try:
                link_path = str(urlparse(_url).path).lower()
                if any(link_path.endswith(ext) for ext in ['.exe', '.json', '.pdf', '.xls', '.xlsx']):
                    p_log(f"[{current_thread_name}] Yasaklanmış dosya uzantılı link, kuyruğa eklenmiyor: {_url}")
                    continue
            except ValueError:
                p_warn(f"[{current_thread_name}] URL ayrıştırılamadı, uzantı kontrolü atlanıyor: {_url}")
                # Optionally, decide if you want to skip or proceed if parsing fails
                # For now, we'll let it proceed if parsing fails here, as it's a secondary check
            
            # Aynı domain içindeki URL'leri kuyruğa eklemeyi dene
            # Base domain kontrolünü daha sağlam yapalım
            try:
                link_domain = urlparse(_url).netloc
            except ValueError:
                p_warn(f"[{current_thread_name}] Eklenen URL parse edilemedi, atlanıyor: {_url}")
                continue
            
            # Kök domain kontrolü (alt domainleri kabul et)
            # Örnek: root_domain = 'sozcu.com.tr'
            # link_domain = 'uyelik.sozcu.com.tr' -> kabul
            # link_domain = 'sozcu.com.tr' -> kabul
            # link_domain = 'google.com' -> red
            # link_domain = 'testsozcu.com.tr' -> red
            if link_domain == root_domain or link_domain.endswith("." + root_domain):
                # Ziyaret edilmemişse crawler'daki fonksiyona gönder
                add_url_func(_url)
                # Loglama add_url_func içinde veya dışında yapılabilir
                # p_log(f"[{current_thread_name}] Potansiyel yeni URL kuyruğa gönderildi: {_url}")
            else:
                p_log(f"[{current_thread_name}] Kök domain ('{root_domain}') dışı link, atlanıyor: {_url}")
    
    # E-posta adreslerini işle
    if len(emails_from_url["data_array"]) > 0:
        for single_email_list in emails_from_url["data_array"]:
            _email = single_email_list[1]
            _email_list.append(_email)
    else:
        _email_list = None
            
    # Telefon numaralarını işle
    if len(phone_from_url["data_array"]) > 0:
        for single_phone_list in phone_from_url["data_array"]:
            _phone = single_phone_list[1]
            _phone_list.append(_phone)
    else:
        _phone_list = None
    

    
    # Veritabanına sayfa bilgilerini kaydet
    _a = self_databaseToolkit.insertPageBased(
        protocol=parsedCurrentTarget["protocol"],
        baseDomain=parsedCurrentTarget["base_domain"],
        urlPath=parsedCurrentTarget["path"],
        urlPathEtc=parsedCurrentTarget["etc"],
        phoneNumber_list=_phone_list,
        emailAddress_list=_email_list,categortyNmae=category
    )
    
    # Resim URL'lerini ekle
    for single_list in image_from_url["data_array"]:
        imageTargetList.append(single_list)
    

    for idx, single_image in enumerate(css_image_from_url):
        if single_image not in imageTargetList:
            imageTargetList.append((single_image, None))
            
    # Tekrarlayan URL'leri kaldır
    imageTargetList = list(set(map(tuple, imageTargetList)))
    imageTargetList = [list(item) if isinstance(item, tuple) else item for item in imageTargetList]
    
    
    p_info(f"{currentTarget} içerisindeki toplam resim adeti: {len(imageTargetList)}")
    
    # Resimleri ThreadPoolExecutor ile işle
    if imageTargetList:
        with concurrent.futures.ThreadPoolExecutor(max_workers=subThreadSize, thread_name_prefix="ImgProcessor") as executor:
            # Tüm resim işleme görevlerini başlat
            future_to_image = {
                executor.submit(
                    proccessImage, 
                    single_image, 
                    parsedCurrentTarget, 
                    self_databaseToolkit, 
                    self_insightFaceApp, 
                    riskLevel, 
                    category, 
                    save_image,
                    stored_no_face_image_url_set,
                    stored_no_face_image_url_lock
                ): single_image for single_image in imageTargetList
            }
            
            p_log(f"[{current_thread_name}] {len(imageTargetList)} adet resim işlenmek üzere {subThreadSize} alt thread'e gönderildi: {currentTarget}")
            # Tamamlanan görevleri takip et
            completed = 0
            for future in concurrent.futures.as_completed(future_to_image):
                completed += 1
                p_log(f"[{current_thread_name}] {currentTarget} işlenen resim: {completed}/{len(imageTargetList)}")
                
                # Hata kontrolü
                try:
                    future.result()
                except Exception as exc:
                    image = future_to_image[future]
                    # Hatalı resmi ve hatayı logla
                    p_error(f"[{current_thread_name}] Resim işleme hatası: {image} -> {exc}")
    else:
        p_log(f"[{current_thread_name}] İşlenecek resim bulunamadı: {currentTarget}")
    
    p_log(f"[{current_thread_name}] Sayfa işleme tamamlandı: {currentTarget}")
    self_databaseToolkit.insert_is_crawled(currentTarget)
    return
        
