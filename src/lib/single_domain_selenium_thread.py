#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Author: Mehmet yüksel şekeroğlu
# @Date: 2025-04-22
# @Filename: single_domain_selenium_thread.py
# @Last modified by: Mehmet yüksel şekeroğlu
# @Last modified time: 2025-04-22

import concurrent.futures
from lib.output.consolePrint import p_info, p_error, p_warn, p_log
from insightface.app import FaceAnalysis
from lib.output.banner import printBanner
from lib.database_tools import DatabaseTools
from lib.url_parser import prepare_url
from lib.url_checker import is_safe_url__html
from lib.proccess_image import proccessImage
from lib.user_agent_tools import randomUserAgent
from HiveWebCrawler.Crawler import WebCrawler
from urllib.parse import urlparse, unquote, urlunparse
from lib.css_image_extractor import extract_css_background_images
from lib.selenium_tools import selenium_browser
from lib.linkedin.linkedin_profile_crawler import extract_linkedin_profile_picture
import time

def single_domain_thread__selenium(
    currentTarget: str,
    Crawler: WebCrawler,
    self_targetList: list,
    self_databaseToolkit: DatabaseTools,
    self_insightFaceApp: FaceAnalysis,
    ignore_content: bool = False,
    autoSubThread: bool = True,
    subThreadSize: int = 2,
    riskLevel: str = None,
    category: str = None,
    save_image: bool = False,
    executable_path: str = None,
    driver_path: str = None,
    single_page: bool = False,
    temp_folder: str = None
    ):
    """
    Belirtilen hedef URL için tek domain tarama işlevini gerçekleştirir.
    
    Args:
        currentTarget: Taranacak URL
        Crawler: Web crawler nesnesi
        self_targetList: Hedef URL listesi
        self_databaseToolkit: Veritabanı araç kutusu
        self_insightFaceApp: Yüz analizi nesnesi
        ignore_content: HTML içeriğini kontrol etmeden geçme durumu
        autoSubThread: Alt thread kullanımı
        subThreadSize: Alt thread sayısı
        riskLevel: Risk seviyesi
        category: Kategori
        save_image: Resim kaydetme durumu
        executable_path: ChromeDriver'ın yolunu belirtmek için kullanılır
        driver_path: ChromeDriver'ın yolunu belirtmek için kullanılır
        single_page: Sadece tek sayfa taranacak mı
        temp_folder: Geçici dosyalar için klasör
    
    Returns:
        None
    """
    # Taranacak resim URL'lerini saklayan liste
    imageTargetList = []
    """
    # URL'nin HTML içerik durumunu kontrol et
    if not is_safe_url__html(currentTarget) and not ignore_content:
        p_warn(f"Adres HTML içeriğine sahip değildir: {currentTarget}")
        return        
    """        
    
    chromeDriver = selenium_browser.get_chrome_driver(
        headless=True, 
        executable_path=executable_path, 
        driver_path=driver_path,
        temp_base_dir=temp_folder
    )
    browserToolkit = selenium_browser.BrowserToolkit(chromeDriver)
    try:
        browserToolkit.getUrl(currentTarget, timeout=30)
        time.sleep(5)
        pageSource = browserToolkit.pageSource()
    except Exception as e:
        p_error(f"{currentTarget} -> {e}")
        return
    finally:
        browserToolkit.close()

               
    # URL'yi ayrıştır
    parsedCurrentTarget = prepare_url(currentTarget)
    
    # Crawler ile URL içeriğinden e-posta, telefon, bağlantı ve resim bilgilerini çıkar
    emails_from_url = Crawler.crawl_email_address_from_response_href(pageSource)
    phone_from_url = Crawler.crawl_phone_number_from_response_href(pageSource)
    
    if not single_page:
        links_from_url = Crawler.crawl_links_from_pesponse_href(parsedCurrentTarget["base_domain"], pageSource)
    else:
        links_from_url = {
            "data_array": [],
            "success": True,
            "error": None
        }

    
    image_from_url = Crawler.crawl_image_from_response(pageSource, parsedCurrentTarget["base_domain"])
    linkedin_profile_results = extract_linkedin_profile_picture(pageSource)

    if linkedin_profile_results:
        print(f"-> Found Embed Picture Instagram | Linkedin | Etc...: {linkedin_profile_results}")
        image_from_url["data_array"].append((linkedin_profile_results, "Embed Picture Instagram | Linkedin | Etc..."))
        
    
    css_image_from_url = extract_css_background_images(currentTarget, pageSource)
    # E-posta ve telefon listelerini hazırla
    _phone_list = []
    _email_list = []
    
    """
    links_from_url = {
        "data_array": []
    }
    """
    # URL'den çıkarılan bağlantıları işle
    if len(links_from_url["data_array"]) > 0:
        for single_link_list in links_from_url["data_array"]:
            _url = str(single_link_list[0])
            _title = single_link_list[1]
            
            if _url.startswith("#"):
                continue
            
            _url = unquote(_url)
            if _url not in self_targetList:
                parsed_url = urlparse(_url)
                _url = urlunparse(parsed_url._replace(fragment=""))
                
                # URL formatını düzenle
                if not _url.startswith("http://") and not _url.startswith("https://"):
                    if _url.startswith(parsedCurrentTarget["base_domain"]) or _url.startswith(parsedCurrentTarget["base_domain"].replace("www.","")):
                        _url = parsedCurrentTarget["protocol"] + "://" + _url
                    else:
                        if _url.startswith("#/"):
                            _url = _url[2:]
                        
                        _url = parsedCurrentTarget["protocol"] + "://" + parsedCurrentTarget["base_domain"] + "/" + _url                        
                
                # Resim dosyaları için kontrol
                break_flag = False
                _url_path = str(parsed_url.path)
                
                for image_extension in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp", ".tiff", ".heic", ".heif"]:    
                    if _url_path.endswith(image_extension):        
                        imageTargetList.append([_url, _title])
                        break_flag = True
                        break
                
                if break_flag:
                    continue
                
                # Aynı domain içindeki URL'leri listeye ekle
                if parsedCurrentTarget["base_domain"] in _url or str(parsedCurrentTarget["base_domain"]).replace("www.", "") in _url:        
                    if _url not in self_targetList:
                        p_info(f"Yeni URL listeye eklendi: {_url} | Toplam URL: {len(self_targetList)}", "")
                        self_targetList.append(_url)
                
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
                    save_image
                ): single_image for single_image in imageTargetList
            }
            
            # Tamamlanan görevleri takip et
            completed = 0
            for future in concurrent.futures.as_completed(future_to_image):
                completed += 1
                p_info(f"{currentTarget} işlenen resim: {completed}/{len(imageTargetList)}")
                
                # Hata kontrolü
                try:
                    future.result()
                except Exception as exc:
                    image = future_to_image[future]
                    p_error(f"{image} işlenirken hata oluştu: {exc}")
    
    p_info(f"{currentTarget} taraması tamamlandı.")
    self_databaseToolkit.insert_is_crawled(currentTarget)
    return
        
