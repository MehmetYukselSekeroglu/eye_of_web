#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Google Görseller'den resim arama ve indirme aracı

import os
import time
import random
import logging
import hashlib
import urllib.parse
from typing import List, Tuple, Dict, Set, Optional, Union
# Kaydırma ve URL toplama değişkenleri
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException, ElementClickInterceptedException
        
# Yerel modüller
from .selenium_tools.selenium_browser import get_chrome_driver, BrowserToolkit
from .url_image_download import downloadImage_defaultSafe

# PIL (Pillow) kütüphanesi resim doğrulaması ve format tespiti için
try:
    from PIL import Image
    import io
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# --- Temel Ayarlar ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- URL Bulma Fonksiyonu ---
def click_more_results(driver, timeout=10):
    """
    Sayfada "More results" metnini içeren ve tıklanabilir hale gelen
    elementi bulup tıklar.

    Args:
        driver: Aktif Selenium WebDriver nesnesi.
        timeout (int): Elementin tıklanabilir hale gelmesi için beklenecek maksimum süre (saniye).

    Returns:
        bool: Tıklama başarılı olduysa True, aksi takdirde False.
    """
    logging.info("Daha fazla sonuç ('More results') butonu aranıyor...")

    try:
        # Tam HTML yapısına göre güncellenmiş, en kesin XPath ve CSS seçicileri
        selectors = [
            # Seçici 1: Doğrudan ana 'a' etiketi (en doğru hedef - bu tıklanmalı)
            "//a[contains(@class, 'T7sFge') and contains(@class, 'VknLRd') and @role='button']",
            
            # Seçici 2: role="button" ile a etiketi
            "//a[@role='button' and contains(@jsname, 'oHxHid')]",
            
            # Seçici 3: 'More results' metni içeren link
            "//a[.//span[contains(text(), 'More results')]]",
            
            # Seçici 4: 'More results' metni içeren ve href özniteliği olan a etiketi
            "//a[contains(@href, 'start=') and .//span[contains(text(), 'More results')]]",
            
            # Seçici 5: CSS seçicileri (bazen daha iyi çalışabilir)
            # CSS Seçicisi, doğrudan sınıf adlarıyla
            (By.CSS_SELECTOR, "a.T7sFge.sW9g3e.VknLRd[role='button']"),
            
            # CSS Seçicisi, span içeriğine göre
            (By.CSS_SELECTOR, "a.VknLRd span.RVQdVd")
        ]
        
        more_results_element = None
        
        # Tüm seçicileri sırayla dene
        for selector in selectors:
            try:
                if isinstance(selector, tuple):
                    # CSS Seçicisi durumu
                    by_method, selector_value = selector
                    logging.debug(f"CSS Seçici deneniyor: {selector_value}")
                    elements = driver.find_elements(by_method, selector_value)
                else:
                    # XPath durumu
                    logging.debug(f"XPath Seçici deneniyor: {selector}")
                    elements = driver.find_elements(By.XPATH, selector)
                
                if elements:
                    # İlk görünür elementi seç
                    for element in elements:
                        if element.is_displayed():
                            # CSS seçici span döndürürse, parent a etiketini bul
                            if element.tag_name == "span":
                                # Span'dan link'e git
                                element = driver.execute_script("""
                                    var element = arguments[0];
                                    while(element && element.tagName !== 'A') {
                                        element = element.parentElement;
                                    }
                                    return element;
                                """, element)
                            
                            more_results_element = element
                            logging.info(f"Element bulundu: {selector}")
                            break
                    if more_results_element:
                        break
            except Exception as selector_err:
                logging.debug(f"Seçici '{selector}' başarısız: {selector_err}")
                continue
        
        # Eğer XPath/CSS seçicileri başarısız olduysa, doğrudan JavaScript kullan
        if not more_results_element:
            logging.info("Seçiciler ile element bulunamadı, JavaScript ile deneniyor...")
            try:
                # JavaScript ile "More results" metni içeren bir <a> etiketi ara
                js_element = driver.execute_script("""
                    // "More results" metnini içeren tüm a etiketlerini bul
                    const links = Array.from(document.querySelectorAll('a'));
                    return links.find(link => {
                        return link.textContent.includes('More results') && 
                               link.offsetParent !== null &&
                               (link.getAttribute('role') === 'button' || 
                                link.classList.contains('VknLRd'));
                    });
                """)
                
                if js_element:
                    more_results_element = js_element
                    logging.info("JavaScript ile 'More results' butonu bulundu")
                else:
                    # Son çare - herhangi bir "More results" metni içeren görünür element
                    js_element = driver.execute_script("""
                        // İç içe fonksiyon - elementten başlayarak üst elemana git
                        function findClickableAncestor(el, maxDepth = 4) {
                            let current = el;
                            let depth = 0;
                            while (current && depth < maxDepth) {
                                // Tıklanabilir mi kontrol et
                                if (current.tagName === 'A' || 
                                    current.tagName === 'BUTTON' || 
                                    current.getAttribute('role') === 'button' ||
                                    current.getAttribute('jsaction') !== null) {
                                    return current;
                                }
                                current = current.parentElement;
                                depth++;
                            }
                            return el; // Hiçbir uygun üst bulunamazsa, orijinal elementi döndür
                        }
                        
                        // "More results" metnini içeren herhangi bir element
                        const allElements = Array.from(document.querySelectorAll('*'));
                        const elementWithText = allElements.find(el => 
                            el.textContent.trim() === 'More results' && 
                            window.getComputedStyle(el).display !== 'none'
                        );
                        
                        if (elementWithText) {
                            return findClickableAncestor(elementWithText);
                        }
                        return null;
                    """)
                    
                    if js_element:
                        more_results_element = js_element
                        logging.info("JavaScript ile metin içeren bir element bulundu (son çare)")
            except Exception as js_err:
                logging.warning(f"JavaScript ile element arama başarısız: {js_err}")
        
        if not more_results_element:
            logging.warning("'More results' elementi bulunamadı.")
            return False
        
        # Elementi görünür yap ve ortala
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", more_results_element)
        time.sleep(1.5)  # Scroll sonrası yeterli bekleme
        
        # Önce elementin durumunu logla
        tag_name = more_results_element.tag_name
        href = more_results_element.get_attribute("href") or "Yok"
        classes = more_results_element.get_attribute("class") or "Yok"
        is_displayed = more_results_element.is_displayed()
        is_enabled = more_results_element.is_enabled()
        
        logging.info(f"""
        Bulunan element:
        - Etiket: {tag_name}
        - Sınıflar: {classes}
        - Href: {href}
        - Görünür: {is_displayed}
        - Etkin: {is_enabled}
        """)
        
        # Tıklamayı dene - üç farklı yöntemle
        try:
            # 1. JavaScript tıklama - en güvenilir yöntem
            driver.execute_script("arguments[0].click();", more_results_element)
            logging.info("'More results' elementine JS ile tıklandı.")
            time.sleep(1.5)  # Tıklama sonrası yeterli bekleme
            return True
        except Exception as js_click_err:
            logging.warning(f"JS click hatası: {js_click_err}, href'e gitmeyi deneyeceğim...")
            
            try:
                # 2. Href değerini al ve doğrudan sayfaya git (tıklama çalışmazsa)
                href = more_results_element.get_attribute("href")
                if href and href.startswith("/"):
                    # Göreli URL'yi tam URL'ye çevir
                    base_url = driver.current_url.split("/search")[0]  # örn: https://www.google.com
                    full_url = base_url + href
                    logging.info(f"Tıklama çalışmadı, href değerine gidiliyor: {full_url}")
                    driver.get(full_url)
                    time.sleep(1.5)
                    return True
                elif href and href.startswith("http"):
                    logging.info(f"Tıklama çalışmadı, href değerine gidiliyor: {href}")
                    driver.get(href)
                    time.sleep(1.5)
                    return True
            except Exception as href_err:
                logging.warning(f"Href'e gitme hatası: {href_err}, normal click deneniyor...")
            
            try:
                # 3. Normal click dene
                more_results_element.click()
                logging.info("'More results' elementine normal yöntemle tıklandı.")
                time.sleep(1.5)
                return True
            except Exception as normal_click_err:
                logging.error(f"Normal click de başarısız: {normal_click_err}")
                return False

    except Exception as e:
        logging.error(f"'More results' elementi işlenirken beklenmedik hata: {e}", exc_info=True)
        return False

def find_image_urls_from_google(
    keyword: str,
    num_urls_target: int = 25,
    scroll_pause_time: float = 1.5,
    scroll_attempts_limit: int = 2,
    headless: bool = True,
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
) -> List[str]:
    """
    Google Görseller'de arama yaparak resim URL'lerini bulur.
    
    Args:
        keyword: Aranacak anahtar kelime
        num_urls_target: Hedeflenen URL sayısı
        scroll_pause_time: Her kaydırma sonrası bekleme süresi (saniye)
        scroll_attempts_limit: Sayfa yüksekliği değişmese bile maksimum kaydırma denemesi
        headless: Tarayıcıyı arka planda çalıştırma durumu
        user_agent: Tarayıcı kullanıcı ajanı

    Returns:
        Bulunan resim URL'lerinin listesi
    """
    image_urls = set()  # Tekrar eden URL'leri önlemek için set kullan
    driver = None
    
    try:
        # Tarayıcıyı başlat (selenium_browser.py kullanarak)
        logging.info(f"Chrome tarayıcı başlatılıyor (Headless: {headless})...")
        driver = get_chrome_driver(
            headless=True,
            user_agent=user_agent
        )
        browser = BrowserToolkit(driver)  # Yardımcı sınıfı kullan
        
        # Google Görseller arama sayfasına git
        search_query = urllib.parse.quote(keyword)
        search_url = f"https://www.google.com/search?q={search_query}&tbm=isch"
        logging.info(f"Google Görseller sayfasına gidiliyor: {search_url}")
        browser.getUrl(search_url)
        time.sleep(random.uniform(2.0, 3.5))  # Sayfanın ilk yüklenmesini bekle
        
        # Çerezleri kabul et butonu görünüyorsa tıkla
        try:
            from selenium.webdriver.common.by import By
            cookie_buttons = driver.find_elements(By.XPATH, 
                "//button[contains(., 'Reject') or contains(., 'Accept') or contains(., 'Kabul') or contains(., 'Tümünü kabul et')]")
            if cookie_buttons:
                for button in cookie_buttons:
                    if button.is_displayed():
                        button.click()
                        logging.info("Çerez izni butonu tıklandı")
                        time.sleep(1)
                        break
        except Exception as e:
            logging.debug(f"Çerez butonu işleme hatası (önemli değil): {e}")
        

        last_height = driver.execute_script("return document.body.scrollHeight")
        no_change_attempts = 0
        total_scrolls = 0
        
        logging.info(f"Hedef {num_urls_target} resim URL'si bulmak için sayfa kaydırılacak...")
        
        # URL toplama döngüsü
        while len(image_urls) < num_urls_target and total_scrolls < scroll_attempts_limit * 3:
            total_scrolls += 1
            logging.debug(f"--- Kaydırma #{total_scrolls} ---")
            
            # Küçük resim (thumbnail) elementlerini bul
            # 2024 ortası güncel CSS seçicileri
            selectors = [
                "img.rg_i", 
                "img.Q4LuWd", 
                "div.isv-r img",
                "a.wXeWr.islib img",
                "div.bRMDJf img",
                "img[data-src]",  # data-src özniteliği olan herhangi bir img
                "img[src^='http']" # src özniteliği http ile başlayan img'ler
            ]
            
            thumbnail_elements = []
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        thumbnail_elements.extend(elements)
                        logging.debug(f"'{selector}' ile {len(elements)} element bulundu.")
                except (NoSuchElementException, StaleElementReferenceException):
                    continue
                except Exception as e:
                    logging.warning(f"Element ararken hata ({selector}): {e}")
            
            if not thumbnail_elements:
                logging.warning("Bu kaydırma sonrası işlenecek küçük resim elementi bulunamadı.")
                
                # JavaScript kullanarak resimleri direkt al
                try:
                    urls_from_js = driver.execute_script("""
                    const images = Array.from(document.querySelectorAll('img'));
                    return images
                        .filter(img => img.src && img.src.startsWith('http') && !img.src.startsWith('data:'))
                        .map(img => img.src);
                    """)
                    
                    if urls_from_js:
                        logging.info(f"JavaScript ile {len(urls_from_js)} resim URL'si bulundu.")
                        for url in urls_from_js:
                            if url.startswith('http'):
                                image_urls.add(url)
                except Exception as js_err:
                    logging.error(f"JavaScript ile URL çıkarırken hata: {js_err}")
            
            # Bulunan elementlerden URL'leri çıkar
            initial_url_count = len(image_urls)
            for img in thumbnail_elements:
                url_to_add = None
                try:
                    # Öncelik: data-src (genellikle daha yüksek çözünürlüklü olabilir)
                    data_src = img.get_attribute('data-src')
                    
                    if data_src and data_src.startswith('http'):
                        url_to_add = data_src
                    else:
                        # Alternatif: src
                        src = img.get_attribute('src')
                        # Base64 olmayan ve http ile başlayanları al
                        if src and src.startswith('http') and not src.startswith('data:image'):
                            url_to_add = src
                        else:
                            # Diğer potansiyel URL öznitelikleri
                            for attr in ['data-iurl', 'data-url', 'datasrc']:
                                val = img.get_attribute(attr)
                                if val and val.startswith('http'):
                                    url_to_add = val
                                    break
                    
                    if url_to_add:
                        image_urls.add(url_to_add)  # Set tekrarları otomatik engeller
                
                except StaleElementReferenceException:
                    continue
                except Exception as e:
                    logging.debug(f"Resim elementi işlenirken hata: {e}")
                    continue
            
            found_this_cycle = len(image_urls) - initial_url_count
            if found_this_cycle > 0:
                logging.info(f"Bu döngüde {found_this_cycle} yeni URL eklendi. Toplam: {len(image_urls)}")
            else:
                logging.debug("Bu döngüde yeni URL eklenmedi.")
            
            # Hedefe ulaşıldıysa döngüden çık
            if len(image_urls) >= num_urls_target:
                logging.info(f"Hedef URL sayısına ({num_urls_target}) ulaşıldı.")
                break
            
            # Sayfayı aşağı kaydır
            try:
                browser.scroll_page(1000 * (total_scrolls + 1))  # Her seferinde biraz daha aşağı
                time.sleep(scroll_pause_time)
                
                # Ekstra kaydırma - her üç kaydırmada bir "Daha fazla sonuç göster" butonunu dene
                if total_scrolls % 3 == 0:
                    if click_more_results(driver):
                        logging.info("'Daha fazla sonuç göster' butonu başarıyla tıklandı")
                        time.sleep(2)  # Yeni içeriğin yüklenmesi için bekleme
                        no_change_attempts = 0  # Tıklama başarılı olduğu için sayacı sıfırla
                
            except Exception as e:
                logging.error(f"Sayfa kaydırılamadı: {e}")
                break
            
            # Sayfa yüksekliğini kontrol et (yeni içerik yüklendi mi?)
            try:
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    no_change_attempts += 1
                    logging.info(f"Sayfa yüksekliği değişmedi. ({no_change_attempts}/{scroll_attempts_limit})")
                    if no_change_attempts >= scroll_attempts_limit:
                        logging.warning(f"Sayfa yüksekliği {scroll_attempts_limit} denemedir değişmiyor. Kaydırma durduruluyor.")
                        break
                else:
                    last_height = new_height
                    no_change_attempts = 0  # Yükseklik değişti, sayacı sıfırla
            except Exception as e:
                logging.error(f"Sayfa yüksekliği alınamadı: {e}")
                break
        
        logging.info(f"URL toplama tamamlandı. Toplam {len(image_urls)} benzersiz URL bulundu.")
        
    except Exception as e:
        logging.error(f"URL toplama sırasında bir hata oluştu: {e}")
    finally:
        # Tarayıcıyı her durumda kapat
        if driver:
            try:
                driver.quit()
                logging.info("WebDriver kapatıldı.")
            except Exception as e:
                logging.error(f"WebDriver kapatılırken hata: {e}")
    
    # Set'i listeye çevir
    return list(image_urls)

# --- İndirme Fonksiyonu ---
def download_images_from_urls(
    image_urls: List[str],
    keyword: str,
    num_images_target: int,
    output_directory: str = "indirilen_google_resimleri",
    timeout: int = 20
) -> List[str]:
    """
    Verilen URL listesinden resimleri indirir.
    
    Args:
        image_urls: İndirilecek resim URL'lerinin listesi
        keyword: Arama anahtar kelimesi (dosya adı oluşturmak için)
        num_images_target: İndirilecek maksimum resim sayısı
        output_directory: Resimlerin kaydedileceği klasör
        timeout: İndirme zaman aşımı süresi (saniye)
    
    Returns:
        İndirilen resimlerin dosya yollarının listesi
    """
    if not image_urls:
        logging.warning("İndirilecek URL bulunamadı.")
        return []
    
    # Klasör hazırlığı
    try:
        os.makedirs(output_directory, exist_ok=True)
        logging.info(f"Resimler '{output_directory}' klasörüne kaydedilecek.")
    except OSError as e:
        logging.error(f"Çıkış klasörü oluşturulamadı: {output_directory} - Hata: {e}")
        return []
    
    downloaded_file_paths = []
    download_count = 0
    
    logging.info(f"Bulunan {len(image_urls)} URL'den en fazla {num_images_target} tanesi indirilecek...")
    
    for url in image_urls:
        if download_count >= num_images_target:
            logging.info(f"Hedeflenen indirme sayısına ({num_images_target}) ulaşıldı.")
            break
        
        try:
            logging.info(f"İndiriliyor [{download_count + 1}/{num_images_target}]: {url[:80]}...")
            
            # url_image_download.py'deki downloadImage_defaultSafe fonksiyonunu kullan
            download_result, image_data, image_hash = downloadImage_defaultSafe(
                target_url=url,
                timeout_sec=timeout
            )
            
            if not download_result or image_data is None:
                logging.warning(f"İndirme başarısız: {image_data}. URL: {url}")
                continue
            
            # Dosya uzantısını belirle
            file_extension = 'jpg'  # Varsayılan
            if PIL_AVAILABLE:
                try:
                    # NumPy array'i PIL Image'e çevir
                    import numpy as np
                    pil_image = Image.fromarray(np.uint8(image_data))
                    
                    # Format'ı al
                    format_map = {
                        'JPEG': 'jpg',
                        'PNG': 'png',
                        'GIF': 'gif',
                        'BMP': 'bmp',
                        'WEBP': 'webp'
                    }
                    
                    if pil_image.format and pil_image.format in format_map:
                        file_extension = format_map[pil_image.format]
                except Exception as pil_err:
                    logging.debug(f"PIL ile format belirlenirken hata: {pil_err}")
            
            # Dosya adını oluştur
            safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '_')).rstrip().replace(' ', '_')
            url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
            filename = f"{safe_keyword}_{download_count + 1}_{url_hash}.{file_extension}"
            filepath = os.path.join(output_directory, filename)
            
            # Resim verilerini OpenCV BGR formatından dönüştürüp kaydet
            if PIL_AVAILABLE:
                try:
                    pil_image.save(filepath)
                except Exception:
                    # Direkt OpenCV kullanarak kaydet
                    import cv2
                    cv2.imwrite(filepath, image_data)
            else:
                # OpenCV kullanarak kaydet
                import cv2
                cv2.imwrite(filepath, image_data)
            
            downloaded_file_paths.append(filepath)
            download_count += 1
            logging.info(f"Başarıyla kaydedildi: {filepath}")
            time.sleep(0.1)
            
        except Exception as e:
            logging.error(f"İndirme/kaydetme hatası: {e}. URL: {url}")
    
    logging.info(f"İndirme işlemi tamamlandı. Toplam {download_count}/{len(image_urls)} resim indirildi (Hedef: {num_images_target}).")
    return downloaded_file_paths

# --- Ana Fonksiyon ---
def download_google_images(
    keyword: str,
    num_images_target: int = 25,
    output_directory: str = "indirilen_google_resimleri",
    scroll_pause_time: float = 1.5,
    scroll_attempts_limit: int = 2,
    timeout: int = 20,
    headless: bool = False,
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    only_find_urls: bool = False
) -> Union[List[str], Tuple[List[str], List[str]]]:
    """
    Google Görseller'den belirtilen anahtar kelimeyle resim arar ve indirir.
    
    Args:
        keyword: Aranacak anahtar kelime
        num_images_target: Hedeflenen indirme/bulma sayısı 
        output_directory: Resimlerin kaydedileceği klasör
        scroll_pause_time: Her kaydırma sonrası bekleme süresi (saniye)
        scroll_attempts_limit: Sayfa yüksekliği değişmese bile maksimum kaydırma denemesi
        timeout: İndirme zaman aşımı süresi (saniye)
        headless: Tarayıcıyı arka planda çalıştırma durumu
        user_agent: Tarayıcı kullanıcı ajanı
        only_find_urls: Sadece URL'leri bul, indirme yapma
    
    Returns:
        only_find_urls=False ise: İndirilen resimlerin dosya yollarının listesi
        only_find_urls=True ise: (URL listesi, indirilen dosya yolları listesi) içeren tuple
    """
    # Adım 1: Google'dan resim URL'lerini bul
    image_urls = find_image_urls_from_google(
        keyword=keyword,
        num_urls_target=num_images_target,
        scroll_pause_time=scroll_pause_time,
        scroll_attempts_limit=scroll_attempts_limit,
        headless=headless,
        user_agent=user_agent
    )
    
    # Eğer sadece URL'leri istiyorsa dön
    if only_find_urls:
        return image_urls
    
    # Adım 2: Bulunan URL'lerden resimleri indir
    downloaded_paths = download_images_from_urls(
        image_urls=image_urls,
        keyword=keyword,
        num_images_target=num_images_target,
        output_directory=output_directory,
        timeout=timeout
    )
    
    return downloaded_paths

# --- Ana Çalıştırma Bloğu ---
if __name__ == "__main__":
    # === Ayarlar ===
    ARANACAK_KELIME = "Mehmet Yüksel Şekeroğlu"
    INDIRILECEK_RESIM_SAYISI = 25
    KAYDEDILECEK_KLASOR = "google_images_thumb"
    HEADLESS_MOD = False  # Tarayıcı görünür olsun (sorun tespiti için)
    
    print("-" * 60)
    print(f"Google Görsellerden '{ARANACAK_KELIME}' için {INDIRILECEK_RESIM_SAYISI} resim aranıyor...")
    print(f"Resimler '{KAYDEDILECEK_KLASOR}' klasörüne kaydedilecek.")
    print(f"Headless mod: {'Aktif' if HEADLESS_MOD else 'Devre Dışı'}")
    print("-" * 60)
    
    try:
        # İlk önce URL'leri bul
        start_time = time.time()
        urls = find_image_urls_from_google(
            keyword=ARANACAK_KELIME,
            num_urls_target=INDIRILECEK_RESIM_SAYISI,
            headless=HEADLESS_MOD,
            scroll_attempts_limit=2
        )
        
        # Bulunan URL'leri ekrana yazdır
        print("\nBulunan Resim URL'leri:")
        print("-" * 60)
        for i, url in enumerate(urls):
            print(f"{i+1}. {url}")
        print("-" * 60)
        
        # Sonra resimleri indir
        if urls:
            downloaded_files = download_images_from_urls(
                image_urls=urls,
                keyword=ARANACAK_KELIME,
                num_images_target=INDIRILECEK_RESIM_SAYISI,
                output_directory=KAYDEDILECEK_KLASOR
            )
            
            end_time = time.time()
            
            print("\nSonuçlar:")
            print("-" * 60)
            if downloaded_files:
                print(f"Başarıyla {len(downloaded_files)} resim indirildi.")
                print("İndirilen dosyalar:")
                for dosya in downloaded_files:
                    print(f"- {dosya}")
            else:
                print("Hiç resim indirilemedi.")
            print(f"Toplam süre: {end_time - start_time:.2f} saniye")
        else:
            print("Hiç URL bulunamadı.")
        
    except Exception as e:
        print(f"Hata oluştu: {e}")