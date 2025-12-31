#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Author: EyeOfWeb Team
# Description: Single domain crawler for scanning websites and detecting faces in images

from lib.output.banner import printBanner
from lib.output.consolePrint import p_info, p_error, p_warn, p_log
from lib.load_config import load_config_from_file
from lib.database_tools import DatabaseTools as DBTools
import sys
import timeit
import argparse
from typing import Optional, Dict, Any, List
from lib.single_domain_selenium_crawler import SingleDomainCrawlerSelenium
from insightface.app import FaceAnalysis
from lib.init_insightface import initilate_insightface



def load_configuration():
    """
    Yapılandırma dosyasını yükler ve gerekli kontrolleri yapar.
    
    Returns:
        tuple: Yapılandırma durumu ve yapılandırma verisi
    """
    config = load_config_from_file()
    if not config[0]:
        p_error("Yapılandırma dosyası yüklenemedi.")
        sys.exit(-1)
    return config

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

def process_url_file(file_path: str, black_list: List[str]) -> List[str]:
    """
    URL dosyasını okur ve kara listedeki domainleri filtreler.
    
    Args:
        file_path: URL dosyasının yolu
        black_list: Kara listedeki domainler
        
    Returns:
        List[str]: Filtrelenmiş URL listesi
    """
    valid_urls = []
    try:
        with open(file_path, "r") as url_file:
            for line in url_file:
                url = line.strip()
                if not url:
                    continue
                
                # Kara listedeki domainleri kontrol et
                skip_domain = any(blacklisted in url for blacklisted in black_list)
                
                if skip_domain:
                    p_warn(f"Kara listedeki domain atlanıyor: {url}")
                    continue
                
                valid_urls.append(url)
        return valid_urls
    except FileNotFoundError:
        p_error(f"Dosya bulunamadı: {file_path}")
        sys.exit(-1)
    except Exception as e:
        p_error(f"Dosya okuma hatası: {str(e)}")
        sys.exit(-1)

# Ana yapılandırma ve bağlantıları yükle
CONFIG = load_configuration()
ThreadSize = CONFIG[1]["service"]["thread"]
printBanner(CONFIG)
DatabaseTools = DBTools(CONFIG[1]["database_config"])
insightFaceApp = initilate_insightface(CONFIG)

if __name__ == "__main__":
    
    # Komut satırı argümanlarını tanımla
    parser = argparse.ArgumentParser(description="EyeOfWeb Single Domain Crawler")
    parser.add_argument("--file", type=str, required=False, help="Taranacak URL'lerin bulunduğu dosya yolu.")
    parser.add_argument("--url", type=str, required=False, help="Taranacak tek URL.")
    parser.add_argument("--risk-level", type=str, required=False, help="Risk seviyesi")
    parser.add_argument("--category", type=str, required=False, help="Kategori")
    parser.add_argument("--save-image", action="store_true", help="Resimleri kaydet")
    parser.add_argument("--ignore-db", type=int, required=False, help="Veritabanını kontrol etme (1 veya 0)")
    parser.add_argument("--ignore-content", type=int, required=False, default=0, help="HTML içeriğini kontrol etme (1 veya 0)")
    parser.add_argument("--executable-path", type=str, required=False, help="ChromeDriver'ın yolunu belirtmek için kullanılır")
    parser.add_argument("--driver-path", type=str, required=False, help="ChromeDriver'ın yolunu belirtmek için kullanılır")
    # Argümanları işle
    args = parser.parse_args()
    file_path = args.file
    single_url = args.url
    risk_level = args.risk_level
    category = args.category
    save_image = args.save_image
    ignore_db = parse_boolean_arg(args.ignore_db)
    ignore_content = parse_boolean_arg(args.ignore_content)
    executable_path = args.executable_path
    driver_path = args.driver_path
    # Durum bilgilerini göster
    p_info(f"İçerik kontrol durumu: {ignore_content}")
    p_info(f"Veritabanı kontrol durumu: {not ignore_db}")
    
    # Kara listedeki domainleri tanımla
    BLACK_LIST = ["cpanel.", "webdisk.", "webmail.", "mail.", "cpco.", "cpcontent.", "online."]
    
    # URL listesini hazırla
    urls = []
    
    # Dosya veya URL parametresi kontrolü
    if file_path and single_url:
        p_warn("Hem --file hem de --url parametreleri verilmiş. Dosya öncelikli olarak kullanılacak.")
        urls = process_url_file(file_path, BLACK_LIST)
    elif file_path:
        urls = process_url_file(file_path, BLACK_LIST)
    elif single_url:
        # Tek URL'yi kara liste kontrolünden geçir
        skip_domain = any(blacklisted in single_url for blacklisted in BLACK_LIST)
        if skip_domain:
            p_warn(f"Kara listedeki domain atlanıyor: {single_url}")
        else:
            urls.append(single_url)
    else:
        p_error("URL kaynağı belirtilmedi. --file veya --url parametrelerinden birini kullanın.")
        sys.exit(-1)
    
    if not urls:
        p_warn("İşlenecek URL bulunamadı.")
        sys.exit(0)
    
    # Her URL için tarama işlemini başlat
    for url in urls:
        # Kullanıcı onayı
        confirmation = input(f"{url} taranacak (Y/n): ").lower() or "y"
        
        if confirmation != "y":
            p_info("Tarama kullanıcı tarafından durduruldu.")
            break
        
        try:
            # Tarama süresini ölç
            start_time = timeit.default_timer()
            
            # SingleDomainCrawler oluştur ve taramayı başlat
            crawler = SingleDomainCrawlerSelenium(
                DatabaseToolkit_object=DatabaseTools,
                FirstTargetAddress=url,
                ThreadSize=ThreadSize,
                CONFIG=CONFIG,
                ignore_db=ignore_db,
                ignore_content=ignore_content,
                executable_path=executable_path,
                driver_path=driver_path,
                insightFaceApp=insightFaceApp
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