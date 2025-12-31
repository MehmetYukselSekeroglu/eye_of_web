import requests
import time
import os
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
from lib.selenium_tools.selenium_browser import BrowserToolkit # Assuming BrowserToolkit is needed or pass driver directly
import typing
class FacebookProfileCrawler:
    """Facebook arama sonuçlarından profil resimlerini tarar ve indirir."""

    DEFAULT_IMAGE_EXTENSION = ".jpg"

    def __init__(self, driver, download_folder="downloaded_profile_pics", scroll_count=5, scroll_pause_time=2):
        """
        Crawler'ı başlatır.

        Args:
            driver: Kullanılacak Selenium WebDriver örneği.
            download_folder (str): Resimlerin indirileceği klasör.
            scroll_count (int): Arama sonuçları sayfasında kaç kez scroll yapılacağı.
            scroll_pause_time (int): Scroll işlemleri arası bekleme süresi (saniye).
        """
        self.driver = driver
        self.toolkit = BrowserToolkit(self.driver) # Toolkit'i sınıf içinde oluştur
        self.download_folder = download_folder
        self.scroll_count = scroll_count
        self.scroll_pause_time = scroll_pause_time
        self.base_url = "https://tr-tr.facebook.com" # Base URL'i sınıf içinde sakla

        # İndirme klasörünü oluştur
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)
            print(f"Klasör oluşturuldu: {self.download_folder}")

    def _clean_filename(self, filename):
        """Dosya adı olarak kullanılamayacak karakterleri temizler."""
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.strip('. ')
        return filename

    def _get_username_from_url(self, profile_url):
        """Profil URL'sinden kullanıcı adını veya kimliğini çıkarmaya çalışır."""
        try:
            parsed_url = urlparse(profile_url)
            path = unquote(parsed_url.path).strip('/')
            if path.startswith('public/'): return path.split('/')[1]
            if path.startswith('people/'):
                parts = path.split('/')
                if len(parts) > 1:
                    if parts[-1].startswith('pfbid') or parts[-1].isdigit():
                        if len(parts) > 2: return parts[1]
                    else:
                        return parts[1]
            if 'profile.php' in path and parsed_url.query:
                query_params = dict(qc.split("=") for qc in parsed_url.query.split("&"))
                return query_params.get('id', path)
            else:
                parts = path.split('/')
                potential_username = parts[-1] if parts else path
                if len(potential_username) > 50 and len(parts) > 1:
                     potential_username = parts[-2]
                return potential_username if potential_username else path
        except Exception:
            fallback = profile_url.split('/')[-1] if '?' not in profile_url else profile_url.split('?')[0].split('/')[-1]
            return unquote(fallback) # Fallback'i de decode et


    def _get_image_extension(self, image_url):
        """Resim URL'sinden dosya uzantısını çıkarmaya çalışır."""
        try:
            parsed_url = urlparse(image_url)
            path = parsed_url.path
            filename = path.split('?')[0]
            if '.' in filename:
                ext = '.' + filename.split('.')[-1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
                    return ext
        except Exception:
            pass
        return self.DEFAULT_IMAGE_EXTENSION

    def _extract_profile_links(self, html_content):
        """
        Verilen HTML içeriğinden Facebook arama sonuçlarındaki profil URL'lerini ve
        küçük resim URL'lerini çıkarır.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        results = []
        profile_containers = soup.find_all('div', class_='_3u1 _gli')
        print(f"Arama HTML'inde {len(profile_containers)} potansiyel profil konteyneri bulundu.")
        if not profile_containers:
            profile_containers = soup.find_all('div', class_='_4p2o _87m1')
            print(f"Alternatif seçici ile {len(profile_containers)} potansiyel profil konteyneri bulundu.")

        for container in profile_containers:
            profile_info = {}
            profile_link_tag = container.find('a', class_='_32mo')
            profile_url = None
            if profile_link_tag and profile_link_tag.has_attr('href'):
                profile_url = urljoin(self.base_url, profile_link_tag['href'])
            else:
                profile_image_anchor = container.find('a', class_='_2ial')
                if profile_image_anchor and profile_image_anchor.has_attr('href'):
                    profile_url = urljoin(self.base_url, profile_image_anchor['href'])

            if profile_url:
                profile_info['profile_url'] = profile_url
                img_tag = container.find('img', class_='_1glk _6phc')
                profile_info['thumbnail_url'] = img_tag['src'] if img_tag and img_tag.has_attr('src') else None

                # Aynı URL'nin tekrar eklenmesini önle
                if not any(existing.get('profile_url') == profile_url for existing in results):
                    results.append(profile_info)
        return results

    def _get_main_picture_url(self, profile_soup):
        """Profil sayfasının soup nesnesinden ana resim URL'sini bulur."""
        main_pic_url = None
        # 1. og:image kontrolü
        og_image_tag = profile_soup.find('meta', property='og:image')
        if og_image_tag and og_image_tag.get('content'):
            main_pic_url = og_image_tag['content'].replace('&amp;', '&')
            print(f"  -> Resim bulundu ('og:image', URL: {main_pic_url[:100]}...)")
            return main_pic_url
        else:
            print("  -> 'og:image' meta etiketi bulunamadı.")

        # 2. CSS Seçicileri
        selectors_to_try = [
            'div[data-visualcompletion="profile-header"] svg image',
            'div[role="img"] svg image',
            'svg[aria-label*="Profil resmi"] image',
            'img[data-imgperflogname="profilePhoto"]',
            'div[role="banner"] img[alt*="Profil resmi"], div[role="banner"] img[alt*="profile picture"]',
            'a[aria-label*="Profil resmi"] img',
        ]
        for selector in selectors_to_try:
            img_tag = profile_soup.select_one(selector)
            if img_tag:
                if img_tag.name == 'image' and img_tag.has_attr('xlink:href'):
                    main_pic_url = img_tag['xlink:href']
                    return main_pic_url
                elif img_tag.name == 'img' and img_tag.has_attr('src'):
                    height = int(img_tag.attrs.get('height', 100))
                    width = int(img_tag.attrs.get('width', 100))
                    src = img_tag['src']
                    if height > 40 and width > 40 and not src.startswith('data:image'):
                        main_pic_url = src
                        return main_pic_url

        return None
    

    def download_profile_picture_return_binary(self, profile_url, main_pic_url) -> typing.Tuple[bytes,str]:
        download_status = 'failed: unknown_error'
        downloaded_path = None
        error_message = None
        try:
            username_base = self._get_username_from_url(profile_url)
            safe_filename_base = self._clean_filename(username_base)
            extension = self._get_image_extension(main_pic_url)

            if extension.lower() == ".png":
                # no profile picture
                # default image
                return None,None
            
            
            print(f"  -> Resim indiriliyor: {main_pic_url[:100]}...")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            img_response = requests.get(main_pic_url, headers=headers, stream=True, timeout=20)
            img_response.raise_for_status()
            print("  -> İndirme başarılı!")
            
            image_binary = img_response.content
            return image_binary,extension
            

        except requests.exceptions.RequestException as download_err:
            print(f"  -> Resim indirme hatası: {download_err}")
            download_status = f'download_failed: {download_err}'
            error_message = str(download_err)
        except Exception as save_err:
            print(f"  -> Resim kaydetme hatası: {save_err}")
            download_status = f'save_failed: {save_err}'
            error_message = str(save_err)

        return None,None

    def _download_profile_picture(self, profile_url, main_pic_url):
        """Verilen URL'den resmi indirir ve kullanıcı adına göre kaydeder."""
        download_status = 'failed: unknown_error'
        downloaded_path = None
        error_message = None
        try:
            username_base = self._get_username_from_url(profile_url)
            safe_filename_base = self._clean_filename(username_base)
            extension = self._get_image_extension(main_pic_url)
            downloaded_path = os.path.join(self.download_folder, f"{safe_filename_base}{extension}")

            print(f"  -> Resim indiriliyor: {main_pic_url[:100]}...")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            img_response = requests.get(main_pic_url, headers=headers, stream=True, timeout=20)
            img_response.raise_for_status()

            print(f"  -> Resim kaydediliyor: {downloaded_path}")
            with open(downloaded_path, 'wb') as f:
                for chunk in img_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            download_status = 'success'
            print("  -> İndirme başarılı!")

        except requests.exceptions.RequestException as download_err:
            print(f"  -> Resim indirme hatası: {download_err}")
            download_status = f'download_failed: {download_err}'
            error_message = str(download_err)
        except Exception as save_err:
            print(f"  -> Resim kaydetme hatası: {save_err}")
            download_status = f'save_failed: {save_err}'
            error_message = str(save_err)

        return {
            'download_status': download_status,
            'downloaded_path': downloaded_path if download_status == 'success' else None,
            'error': error_message
        }

    def crawl_search_results(self, search_url):
        """
        Verilen Facebook arama URL'sindeki profilleri tarar ve resimleri indirir.

        Args:
            search_url (str): Taranacak Facebook arama sonuçları URL'si.

        Returns:
            list: Her profil için detayları içeren sözlük listesi.
        """
        final_results = []
        try:
            self.toolkit.getUrl(search_url)
            for i in range(self.scroll_count):
                self.toolkit.scroll_page((i + 1) * 1000)
                print(f"Scroll {i+1}/{self.scroll_count} yapıldı, {self.scroll_pause_time} saniye bekleniyor...")
                time.sleep(self.scroll_pause_time)

            html_source = self.toolkit.pageSource()
            initial_profiles = self._extract_profile_links(html_source)

            print(f"\nArama sonuçlarından {len(initial_profiles)} benzersiz potansiyel profil URL'si bulundu. Profiller işleniyor...")

            for profile_data in initial_profiles:
                profile_url = profile_data.get('profile_url')
                if not profile_url:
                    print("Geçersiz profil verisi atlanıyor.")
                    continue
                
                                
                print(f"\nİşleniyor: {profile_url}")
                profile_result = {
                    'profile_url': profile_url,
                    'main_image_url': None,
                    'thumbnail_url': profile_data.get('thumbnail_url'),
                    'download_status': 'not_processed',
                    'downloaded_path': None,
                    'error': None
                }
                final_results.append(profile_result)    
                continue
                try:
                    self.toolkit.getUrl(profile_url)
                    time.sleep(4) # Sayfanın yüklenmesi için bekleme süresi
                    profile_html = self.toolkit.pageSource()
                    profile_soup = BeautifulSoup(profile_html, 'html.parser')

                    main_pic_url = self._get_main_picture_url(profile_soup)
                    profile_result['main_image_url'] = main_pic_url

                    #if main_pic_url:
                    #    download_info = self._download_profile_picture(profile_url, main_pic_url)
                    #    profile_result.update(download_info) # İndirme sonuçlarını ekle
                    #else:
                    #    profile_result['download_status'] = 'no_url_found'

                except Exception as process_err:
                    print(f"  -> Profil işlenirken Hata oluştu: {process_err}")
                    profile_result['error'] = str(process_err)
                    profile_result['download_status'] = 'processing_error'

                final_results.append(profile_result)
                time.sleep(1) # Rate limiting için bekle

        except Exception as general_err:
            print(f"Genel bir hata oluştu: {general_err}")
            # İsteğe bağlı olarak hatayı loglayabilir veya yeniden fırlatabilirsiniz.

        print("\nTarama işlemi tamamlandı.")
        return final_results

    def close_driver(self):
        """WebDriver'ı kapatır ve geçici klasörleri temizler."""
        if self.driver:
            # Clean up temp user data directory if it was created by us
            temp_dir = getattr(self.driver, '_temp_user_data_dir', None)
            
            try:
                print("Tarayıcı kapatılıyor.")
                self.driver.quit()
            except Exception as e:
                print(f"Error closing driver: {e}")
            finally:
                self.driver = None
            
            # Clean up temp directory after driver is closed
            if temp_dir and os.path.exists(temp_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                    print(f"  -> Geçici klasör temizlendi: {temp_dir}")
                except Exception as e:
                    print(f"  -> Uyarı: Geçici klasör silinemedi {temp_dir}: {e}")
