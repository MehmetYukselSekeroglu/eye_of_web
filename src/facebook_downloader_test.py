import time
import os
import shutil # Klasör silme için
from urllib.parse import quote
import concurrent.futures # ThreadPoolExecutor için

from lib.selenium_tools.selenium_browser import get_chrome_driver, DEFAULT_USER_AGENT
from lib.facebook.facebook_profile_crawler import FacebookProfileCrawler

# --- Ayarlar ---
DOWNLOAD_FOLDER = "downloaded_profile_pics"
TEMP_FOLDER_BASE = "tmp/selenium_profiles" # Geçici profil klasörlerinin ana dizini
SCROLL_COUNT = 10
SCROLL_PAUSE_TIME = 2
MAX_THREADS = 4
USER_AGENT = DEFAULT_USER_AGENT
HEADLESS_MODE = True

# Türkiye'deki en popüler 100 ad soyad listesi
TURKISH_NAMES = [
    "Mehmet Şekeroğlu", # Başa eklendi
    "Ahmet Yılmaz", "Mehmet Kaya", "Mustafa Demir", "Ali Öztürk",
    "Ayşe Yıldız", "Fatma Şahin", "Emine Çelik", "Hüseyin Arslan",
    "Zeynep Kara", "İbrahim Aydın", "Hatice Doğan", "Ömer Aslan",
    "Murat Özdemir", "Hasan Şimşek", "Hüseyin Kılıç", "İsmail Özkan",
    "Osman Yılmazer", "Ramazan Acar", "Abdullah Koç", "Halil Çetin",
    "Süleyman Polat", "Mustafa Erdoğan", "Ahmet Aksoy", "Mehmet Özer",
    "Ali Yüksel", "Hasan Kaya", "Hüseyin Demirci", "İbrahim Yavuz",
    "Murat Güneş", "Mehmet Şahin", "Mustafa Aydın", "Ahmet Çelik",
    "Ali Demir", "Hasan Kılıç", "Fatma Yılmaz", "Ayşe Kaya", "Emine Demir",
    "Zeynep Öztürk", "Hatice Şahin", "Sultan Yıldız", "Fadime Çelik",
    "Hanife Arslan", "Zeliha Kara", "Havva Aydın", "Elif Doğan",
    "Meryem Aslan", "Şerife Özdemir", "Hacer Şimşek", "Cemile Kılıç",
    "Emine Özkan", "Ayşe Yılmazer", "Fatma Acar", "Hatice Koç",
    "Zeynep Çetin", "Fadime Polat", "Hanife Erdoğan", "Zeliha Aksoy",
    "Havva Özer", "Elif Yüksel", "Meryem Kaya", "Şerife Demirci",
    "Hacer Yavuz", "Cemile Güneş", "Emine Şahin", "Ayşe Aydın",
    "Fatma Çelik", "Hatice Demir", "Zeynep Kılıç", "Fadime Yılmaz",
    "Hanife Kaya", "Zeliha Demir", "Havva Öztürk", "Elif Şahin",
    "Meryem Yıldız", "Şerife Çelik", "Hacer Arslan", "Cemile Kara",
    "Emine Aydın", "Ayşe Doğan", "Fatma Aslan", "Hatice Özdemir",
    "Zeynep Şimşek", "Fadime Kılıç", "Hanife Özkan", "Zeliha Yılmazer",
    "Havva Acar", "Elif Koç", "Meryem Çetin", "Şerife Polat",
    "Hacer Erdoğan", "Cemile Aksoy", "Emine Özer", "Ayşe Yüksel"
]
# ---------------

def worker(name_to_search, thread_id):
    """Her bir iş parçacığının çalıştıracağı fonksiyon."""
    web_driver = None
    crawler = None
    profile_dir = os.path.join(TEMP_FOLDER_BASE, f"thread_{thread_id}")
    print(f"[Thread-{thread_id}] Başlatıldı. İsim: {name_to_search}, Profil: {profile_dir}")

    search_results = {'name': name_to_search, 'results': [], 'error': None}

    try:
        # Her thread kendi driver'ını ve profil dizinini kullanır
        # print(f"[Thread-{thread_id}] Tarayıcı başlatılıyor...") # Daha az log
        web_driver = get_chrome_driver(
            headless=HEADLESS_MODE,
            user_agent=USER_AGENT,
            profile_dir_path=profile_dir
        )

        # print(f"[Thread-{thread_id}] Crawler başlatılıyor...") # Daha az log
        crawler = FacebookProfileCrawler(
            driver=web_driver,
            download_folder=DOWNLOAD_FOLDER,
            scroll_count=SCROLL_COUNT,
            scroll_pause_time=SCROLL_PAUSE_TIME
        )

        search_query = quote(name_to_search)
        search_url = f"https://tr-tr.facebook.com/public/{search_query}"

        print(f"[Thread-{thread_id}] Tarama başlıyor: {search_url}")
        crawl_results = crawler.crawl_search_results(search_url)
        search_results['results'] = crawl_results
        print(f"[Thread-{thread_id}] {len(crawl_results)} profil işlendi.")

    except Exception as e:
        error_msg = f"[Thread-{thread_id}] Hata oluştu ({name_to_search}): {e}"
        print(error_msg)
        search_results['error'] = str(e)

    finally:
        # İş parçacığı bittiğinde kendi tarayıcısını kapatır
        if crawler:
            # print(f"[Thread-{thread_id}] Tarayıcı kapatılıyor...") # Daha az log
            crawler.close_driver()
        elif web_driver:
            # print(f"[Thread-{thread_id}] Tarayıcı (doğrudan) kapatılıyor...") # Daha az log
            web_driver.quit()

        # # Opsiyonel: Her iş bitiminde geçici profil klasörünü temizle
        # try:
        #     if os.path.exists(profile_dir):
        #         print(f"[Thread-{thread_id}] Geçici klasör temizleniyor: {profile_dir}")
        #         shutil.rmtree(profile_dir)
        # except OSError as e:
        #     print(f"[Thread-{thread_id}] Geçici klasör silinemedi ({profile_dir}): {e}")

    print(f"[Thread-{thread_id}] Tamamlandı. İsim: {name_to_search}")
    return search_results


def main():
    start_time = time.time()

    # Ana geçici klasörü temizle/oluştur (başlamadan önce)
    if os.path.exists(TEMP_FOLDER_BASE):
         print(f"Mevcut geçici klasör temizleniyor: {TEMP_FOLDER_BASE}")
         try:
             shutil.rmtree(TEMP_FOLDER_BASE)
         except OSError as e:
             print(f"Uyarı: Geçici klasör silinemedi ({TEMP_FOLDER_BASE}): {e}")
    os.makedirs(TEMP_FOLDER_BASE, exist_ok=True)
    print(f"Geçici klasör oluşturuldu: {TEMP_FOLDER_BASE}")

    all_results = []
    print(f"{len(TURKISH_NAMES)} isim {MAX_THREADS} iş parçacığı ile işlenecek.")

    # ThreadPoolExecutor kullanarak işleri yönet
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        # Görevleri (futures) oluştur
        futures = {executor.submit(worker, name, i % MAX_THREADS + 1): name
                   for i, name in enumerate(TURKISH_NAMES)}

        print("Görevler iş parçacığı havuzuna gönderildi. Sonuçlar bekleniyor...")

        # Görevler tamamlandıkça sonuçları al
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                result = future.result() # Worker fonksiyonundan dönen değeri al
                all_results.append(result)
                print(f"  -> Sonuç alındı: {name} (Hata: {result.get('error') is not None})")
            except Exception as exc:
                print(f"'{name}' işlenirken bir istisna oluştu: {exc}")
                all_results.append({'name': name, 'results': [], 'error': str(exc)})

    end_time = time.time()
    print(f"\nTüm görevler tamamlandı. Toplam süre: {end_time - start_time:.2f} saniye")

    # Opsiyonel: Tüm işlemler bittikten sonra ana geçici klasörü temizle
    try:
        if os.path.exists(TEMP_FOLDER_BASE):
            print(f"İşlem sonrası geçici klasör temizleniyor: {TEMP_FOLDER_BASE}")
            shutil.rmtree(TEMP_FOLDER_BASE)
    except OSError as e:
        print(f"Uyarı: İşlem sonrası geçici klasör silinemedi ({TEMP_FOLDER_BASE}): {e}")

    # --- Toplanan Sonuçları Yazdır --- (Öncekiyle aynı kalabilir)
    print("\n\n=== TOPLANAN TÜM PROFİL BİLGİLERİ ===")
    total_profiles_found = 0
    total_images_downloaded = 0
    total_errors = 0

    for search_result in all_results:
        name = search_result.get('name')
        results = search_result.get('results', [])
        error = search_result.get('error')

        print(f"\n--- Arama: {name} ---")
        # Arama bazlı hatayı yazdır (worker fonksiyonundaki genel hata)
        if error:
            print(f"  !! Bu arama sırasında genel hata: {error}")
            total_errors += 1 # Eğer hata varsa, indirilen profil sayılmaz

        if results:
            print(f"  {len(results)} profil işlendi:")
            for data in results:
                total_profiles_found += 1 # İşlenen her profil için sayacı artır
                print(f"    Profil URL:      {data.get('profile_url', 'Bulunamadı')}")
                # print(f"    Ana Resim URL:   {data.get('main_image_url', 'Bulunamadı')}")
                print(f"    İndirme Durumu: {data.get('download_status', 'Bilinmiyor')}")
                if data.get('downloaded_path'):
                     print(f"    Kaydedilen Yol:  {data.get('downloaded_path')}")
                     if data.get('download_status') == 'success':
                         total_images_downloaded += 1
                # Profile özel hatayı yazdır (örn. indirme hatası)
                profile_error = data.get('error')
                if profile_error and not error:
                     print(f"    Hata:            {profile_error}")
                     total_errors += 1
                print("    " + "-" * 36)
        elif not error:
            print("  Bu arama için profil bulunamadı veya işlenemedi.")
        else:
            print("  Arama hatası nedeniyle profil işlenemedi.")

    print("\n=== ÖZET ===")
    print(f"Toplam işlenen profil sayısı: {total_profiles_found}")
    print(f"Başarıyla indirilen resim sayısı: {total_images_downloaded}")
    print(f"Karşılaşılan hata sayısı (Genel + Profil): {total_errors}")

if __name__ == "__main__":
    main()
