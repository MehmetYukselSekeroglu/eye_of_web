import os
import asyncio
import logging
import queue
import threading
import time
import cv2
import hashlib
import numpy as np
from urllib.parse import urlparse
import traceback # Hata ayıklama için
import io # BytesIO için eklendi
import concurrent.futures
import colorlog
import threading
from collections import OrderedDict # Sıralı dictionary için eklendi

from pyrogram.types import Dialog
# Pyrogram Imports
from pyrogram import Client, filters, enums
# Daha spesifik hataları yakalamak gerekebilir, şimdilik temel olanlar:
from pyrogram.errors import (
    UserDeactivatedBan, AuthKeyUnregistered, UserNotParticipant, FloodWait,
    AuthKeyDuplicated # Oturum çakışması için eklendi
)
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler
from datetime import datetime, timedelta

from queue import Queue
try:
    from lib.database_tools import DatabaseTools
    from lib.load_config import load_config_from_file
    from lib.init_insightface import initilate_insightface
except ImportError as e:
    logging.error(f"Gerekli kütüphane(ler) yüklenemedi: {e}. Lütfen 'lib' klasörünün doğru yerde olduğundan ve gerekli dosyaları içerdiğinden emin olun.", exc_info=True)
    exit(1)


# --- Configuration Loading ---
CONFIG = load_config_from_file()

if not CONFIG or not CONFIG[0]:
    logging.error("Yapılandırma dosyası yüklenemedi veya boş.")
    raise Exception("Yapılandırma dosyası bulunamadı veya geçersiz")

# --- Logging Setup with Colors ---
# Renkli log formatını ayarla
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
))

# Root logger'ı yapılandır
logger = colorlog.getLogger()
logger.setLevel(logging.INFO)
logger.handlers = []  # Mevcut handler'ları temizle
logger.addHandler(handler)

# Pyrogram'ın kendi loglarını biraz kısmak için (isteğe bağlı, DEBUG modunda daha fazla bilgi verebilir)
# logging.getLogger("pyrogram").setLevel(logging.WARNING)


# --- Database and InsightFace Initialization ---
try:
    # CONFIG[1] içinde gerekli config anahtarlarının olduğunu varsayıyoruz
    database_tools = DatabaseTools(dbConfig=CONFIG[1]['database_config'])
    logging.info("Veritabanı araçları başarıyla başlatıldı.")
except KeyError as e:
    logging.error(f"Yapılandırma dosyasında eksik anahtar: 'database_config'. Hata: {e}", exc_info=True)
    exit(1)
except Exception as e:
    logging.error(f"Veritabanı araçları başlatılırken hata: {e}", exc_info=True)
    exit(1)

try:
    insightFaceApp = initilate_insightface(main_conf=CONFIG)
    if insightFaceApp is None:
        raise ValueError("InsightFace başlatma None döndürdü, yapılandırmayı kontrol edin.")
    logging.info("InsightFace başarıyla başlatıldı.")
except Exception as e:
    logging.error(f"InsightFace başlatılırken kritik hata: {e}", exc_info=True)
    exit(1) # InsightFace olmadan devam edilemez
    
    

# --- Pyrogram Configuration ---
# Doğrudan API bilgileri hardcoded olarak tanımlandı
API_ID = 12345
API_HASH = 'your_api_hash'
# PHONE_NUMBER = '+905516768147'  # Auth için gerekirse kullanılabilir
SESSION_NAME = 'telegram_crawler_user'
# Hata yakalama bloklarına gerek kalmadı çünkü değerler doğrudan tanımlandı
MAX_QUEUE_SIZE = 50 # Kuyruk boyutunu 25'ten 50'ye çıkaralım
LISTENED_CHAT_IDS = []
THREAD_QUEUE = Queue(maxsize=MAX_QUEUE_SIZE)
DOWNLOAD_TIMEOUT = 20 # Zaman aşımını 10'dan 20 saniyeye çıkar
DOWNLOAD_PROFILE_PHOTOS = False # Profil fotoğraflarını indirme seçeneği
# İşlenen profil fotoğraflarını takip etmek için set
PROCESSED_USER_PROFILES = OrderedDict() # set() yerine OrderedDict kullan
MAX_PROCESSED_USER_PROFILES = 100 # Kullanıcı takip listesi için maksimum boyut
# Profil fotoğrafı takip zaman aşımı (gün cinsinden) - bu süreden sonra profiller tekrar işlenir
PROFILE_TRACKING_TIMEOUT_DAYS = 7
LAST_PROFILE_RESET_TIME = datetime.now()
app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)


# Asenkron versiyon
async def download_photo_async_pyro(client: Client, message: Message) -> bytes | None:
    logger.info("Sleeping for 5 seconds before downloading photo for rate limit")
    asyncio.sleep(5)
    logger.info("Starting photo download")
    """Asenkron olarak fotoğrafı indirir ve byte olarak döndürür. Zaman aşımı için yeniden deneme mekanizması içerir."""
    msg_id = getattr(message, 'id', 'Unknown') # Loglama için ID al
    max_retries = 3
    initial_backoff = 2 # saniye

    if not client or not client.is_connected:
        logging.error(f"[Downloader:Msg {msg_id}] Pyrogram client başlatılmamış veya bağlı değil.")
        return None
        
    if not message or not message.photo:
        logging.warning(f"[Downloader:Msg {msg_id}] download_photo_async_pyro çağrıldı ancak mesajda fotoğraf yok.")
        return None

    for attempt in range(max_retries):
        try:
            logging.debug(f"[Downloader:Msg {msg_id}] Fotoğraf indirme deneniyor... (Deneme {attempt + 1}/{max_retries})")
            # Asenkron indirme API'sini kullan
            # Timeout doğrudan download_media içinde yönetilmiyor, bu yüzden future.result içinde yakalamıştık.
            # Ancak burada coroutine'i doğrudan await ettiğimiz için timeout hatasını burada yakalayabiliriz.
            # Pyrogram'ın kendi timeout'ları olabilir veya genel asyncio timeout ile sarmalamak gerekebilir.
            # Şimdilik doğrudan await kullanalım ve process_queue_subthread'deki timeout yakalamaya güvenelim.
            # Not: Eğer Pyrogram client'ı bir timeout ile konfigüre edilmediyse, bu await potansiyel olarak
            # çok uzun süre bekleyebilir. Timeout kontrolünü çağıran yerde (run_coroutine_threadsafe sonrası) yapmak daha doğru.
            # Bu fonksiyon içindeki retry mantığını timeout yerine diğer olası hatalar için (örn. geçici ağ sorunları)
            # saklayabiliriz veya timeout'u burada yönetmek için asyncio.wait_for kullanabiliriz.
            # Şimdilik process_queue_subthread'deki timeout mantığına dokunmayalım ve burayı basit tutalım.
            downloaded_media = await client.download_media(message, in_memory=True)

            # Handle both bytes and BytesIO return types
            photo_bytes: bytes | None = None
            if isinstance(downloaded_media, bytes):
                photo_bytes = downloaded_media
            elif isinstance(downloaded_media, io.BytesIO):
                logging.debug(f"[Downloader:Msg {msg_id}] İndirilen medya BytesIO, .getvalue() çağrılıyor.")
                photo_bytes = downloaded_media.getvalue() 
                downloaded_media.close() 
            elif downloaded_media is None:
                logging.warning(f"[Downloader:Msg {msg_id}] Fotoğraf indirme None döndürdü (Deneme {attempt + 1}).")
                # None dönmesi tekrar denemeyi gerektirmeyebilir, belki de medya gerçekten yok.
                # Şimdilik None durumunda döngüden çıkalım.
                return None 
            else:
                logging.error(f"[Downloader:Msg {msg_id}] Fotoğraf indirme beklenmedik tip döndürdü (Tip: {type(downloaded_media)}).)")
                if isinstance(downloaded_media, str) and os.path.exists(downloaded_media):
                    try: os.remove(downloaded_media); logging.info(f"[Downloader:Msg {msg_id}] Beklenmedik indirilen dosya silindi: {downloaded_media}")
                    except OSError as e: logging.error(f"[Downloader:Msg {msg_id}] Beklenmedik dosya silinemedi {downloaded_media}: {e}")
                return None # Beklenmedik tipte tekrar deneme yapma

            if photo_bytes:
                logging.debug(f"[Downloader:Msg {msg_id}] Fotoğraf başarıyla byte olarak alındı ({len(photo_bytes)} bytes)")
                return photo_bytes
            else:
                logging.error(f"[Downloader:Msg {msg_id}] İndirme sonrası photo_bytes alınamadı (downloaded_media type: {type(downloaded_media)}).)")
                return None # Hata durumunda tekrar deneme yapma

        except FloodWait as e:
            logging.warning(f"[Downloader:Msg {msg_id}] İndirme sırasında Flood wait: {e.value} saniye bekleniyor. (Deneme {attempt + 1})")
            # FloodWait durumunda Pyrogram zaten bekleme süresi veriyor, biz de uyalım.
            # Tekrar deneme döngüsünden önce bekleyelim.
            wait_time = e.value + 1
            if attempt + 1 < max_retries:
                logging.info(f"[Downloader:Msg {msg_id}] FloodWait sonrası {wait_time} saniye sonra tekrar denenecek...")
                await asyncio.sleep(wait_time)
            else:
                logging.error(f"[Downloader:Msg {msg_id}] FloodWait sonrası maksimum deneme sayısına ulaşıldı.")
                return None
        except asyncio.TimeoutError as e:
            logging.warning(f"[Downloader:Msg {msg_id}] İndirme zaman aşımına uğradı (Deneme {attempt + 1}). Hata: {e}")
            if attempt + 1 < max_retries:
                backoff_time = initial_backoff * (2 ** attempt)
                logging.info(f"[Downloader:Msg {msg_id}] {backoff_time} saniye sonra tekrar denenecek...")
                await asyncio.sleep(backoff_time)
            else:
                logging.error(f"[Downloader:Msg {msg_id}] Zaman aşımı sonrası maksimum deneme sayısına ulaşıldı.")
                return None
        except Exception as e:
            # Diğer beklenmedik hatalar için de tekrar deneyebiliriz, ancak dikkatli olmalı.
            # Şimdilik sadece TimeoutError ve FloodWait için özel işlem yapalım.
            logging.error(f"[Downloader:Msg {msg_id}] Fotoğraf indirme hatası (Deneme {attempt + 1}): {e}", exc_info=True)
            # Beklenmedik hatalarda hemen çıkmak daha güvenli olabilir.
            return None 

    # Döngü bitti ve başarılı olmadıysa
    logging.error(f"[Downloader:Msg {msg_id}] Maksimum deneme ({max_retries}) sonrası fotoğraf indirilemedi.")
    return None


async def download_profile_photo_async_pyro(client: Client, entity_id: int, file_id: str) -> bytes | None:
    """Profil fotoğrafını asenkron olarak indirir. Zaman aşımı için yeniden deneme mekanizması içerir."""
    log_prefix = f"ProfileDownloader:Entity {entity_id}"
    max_retries = 3
    initial_backoff = 2 # saniye

    logger.info("Sleeping for 5 seconds before downloading profile photo for rate limit")
    asyncio.sleep(5)
    logging.info(f"[{log_prefix}] Profil fotoğrafı indirme başlatılıyor (File ID: {file_id})...")
    
    
    if not client or not client.is_connected:
        logging.error(f"[{log_prefix}] Pyrogram client başlatılmamış veya bağlı değil.")
        return None

    for attempt in range(max_retries):
        try:
            logging.debug(f"[{log_prefix}] Profil fotoğrafı indirme deneniyor (File ID: {file_id})... (Deneme {attempt + 1}/{max_retries})")
            downloaded_media = await client.download_media(file_id, in_memory=True)

            photo_bytes: bytes | None = None
            if isinstance(downloaded_media, bytes):
                photo_bytes = downloaded_media
            elif isinstance(downloaded_media, io.BytesIO):
                logging.debug(f"[{log_prefix}] İndirilen profil fotoğrafı BytesIO, .getvalue() çağrılıyor.")
                photo_bytes = downloaded_media.getvalue()
                downloaded_media.close()
            elif downloaded_media is None:
                logging.warning(f"[{log_prefix}] Profil fotoğrafı indirme None döndürdü (Deneme {attempt + 1}).")
                return None # None ise tekrar deneme
            else:
                logging.error(f"[{log_prefix}] Profil fotoğrafı indirme beklenmedik tip döndürdü (Tip: {type(downloaded_media)}).")
                if isinstance(downloaded_media, str) and os.path.exists(downloaded_media):
                    try: os.remove(downloaded_media); logging.info(f"[{log_prefix}] Beklenmedik indirilen profil dosyası silindi: {downloaded_media}")
                    except OSError as e: logging.error(f"[{log_prefix}] Beklenmedik profil dosyası silinemedi {downloaded_media}: {e}")
                return None # Beklenmedik tipte tekrar deneme yapma

            if photo_bytes:
                logging.debug(f"[{log_prefix}] Profil fotoğrafı başarıyla byte olarak alındı ({len(photo_bytes)} bytes)")
                return photo_bytes
            else:
                logging.error(f"[{log_prefix}] İndirme sonrası profil fotoğrafı bytes alınamadı (downloaded_media type: {type(downloaded_media)}).")
                return None # Hata durumunda tekrar deneme yapma

        except FloodWait as e:
            logging.warning(f"[{log_prefix}] Profil fotoğrafı indirme sırasında Flood wait: {e.value} saniye bekleniyor. (Deneme {attempt + 1})")
            wait_time = e.value + 1
            if attempt + 1 < max_retries:
                logging.info(f"[{log_prefix}] FloodWait sonrası {wait_time} saniye sonra tekrar denenecek...")
                await asyncio.sleep(wait_time)
            else:
                logging.error(f"[{log_prefix}] FloodWait sonrası maksimum deneme sayısına ulaşıldı.")
                return None
        except asyncio.TimeoutError as e:
            logging.warning(f"[{log_prefix}] Profil fotoğrafı indirme zaman aşımına uğradı (Deneme {attempt + 1}). Hata: {e}")
            if attempt + 1 < max_retries:
                backoff_time = initial_backoff * (2 ** attempt)
                logging.info(f"[{log_prefix}] {backoff_time} saniye sonra tekrar denenecek...")
                await asyncio.sleep(backoff_time)
            else:
                logging.error(f"[{log_prefix}] Zaman aşımı sonrası maksimum deneme sayısına ulaşıldı.")
                return None
        except Exception as e:
            logging.error(f"[{log_prefix}] Profil fotoğrafı indirme hatası (Deneme {attempt + 1}): {e}", exc_info=True)
            return None # Beklenmedik hatalarda çık

    logging.error(f"[{log_prefix}] Maksimum deneme ({max_retries}) sonrası profil fotoğrafı indirilemedi.")
    return None


def process_queue_subthread(client: Client):
    """Kuyruktan öğeleri tüketir, medyayı indirir, işler ve veritabanına kaydeder."""
    global database_tools, insightFaceApp
    logging.info("İşleyici thread başlatıldı.")

    # Worker thread içerisinden asenkron fonksiyonları çağırmak için gerekli
    try:
        loop = asyncio.get_running_loop()
        logging.info(f"Mevcut olay döngüsü alındı: {loop}")
    except RuntimeError:
        logging.info("Çalışan olay döngüsü yok, yenisi oluşturuluyor.")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Client'ın kendi döngüsünü kullanmak daha güvenli olabilir, ancak client
        # ana thread'de başlatıldığı için worker'da doğrudan erişmek riskli olabilir.
        # Şimdilik yeni bir döngü kullanalım.

    if not client or not client.is_connected:
        # Client bağlantısı thread başladığında kontrol edilmeli
        logging.warning("Worker thread başlatıldığında Pyrogram client bağlı değil. Bağlantı bekleniyor...")
        # client.start() burada çağrılmamalı, ana thread'de yönetilmeli.
        # Gerekirse client objesinin thread'e geçirilmeden önce başlatıldığından emin olunmalı.

    while True:
        item = None
        item_type = "unknown"
        item_id_for_log = "Unknown"
        chat_id_for_log = "N/A"

        try:
            logging.debug(f"İşleyici thread kuyruktan öğe bekliyor... (Mevcut boyut: {THREAD_QUEUE.qsize()})")
            item = THREAD_QUEUE.get() # Bloklayarak bekle
            if item is None:
                logging.info("İşleyici thread durdurma sinyali (None) aldı.")
                break # Döngüyü sonlandır

            # Öğenin tipini belirle
            if isinstance(item, Message):
                item_type = "message"
                message = item
                item_id_for_log = message.id
                chat_id_for_log = message.chat.id if message.chat else "N/A"
            elif isinstance(item, dict) and item.get("type") == "user_profile_photo":
                item_type = "user_profile_photo"
                profile_task = item
                item_id_for_log = profile_task.get("file_id", "Unknown File ID")
                chat_id_for_log = profile_task.get("user_id", "N/A") # user_id'yi log için alalım
            else:
                logging.error(f"Kuyrukta bilinmeyen öğe tipi alındı: {type(item)}, Öğe: {item}")
                THREAD_QUEUE.task_done()
                continue

            logging.debug(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Öğe kuyruktan alındı. İşleme başlıyor. İlgili ID: {chat_id_for_log}")

            # --- Medya İndirme --- (Asenkron)
            photo_data_bytes = None
            future = None
            try:
                if item_type == "message":
                    logging.debug(f"[Processor:Msg {item_id_for_log}] Async mesaj fotoğrafı indirme çağrılıyor...")
                    coro = download_photo_async_pyro(client, message)
                    future = asyncio.run_coroutine_threadsafe(coro, client.loop)
                    try:
                        photo_data_bytes = future.result(timeout=DOWNLOAD_TIMEOUT)
                    except asyncio.TimeoutError:
                        logging.error(f"[Processor:Msg {item_id_for_log}] Fotoğraf indirme zaman aşımına uğradı ({DOWNLOAD_TIMEOUT}s).")
                        THREAD_QUEUE.task_done()
                        continue
                    except concurrent.futures.CancelledError:
                        logging.error(f"[Processor:Msg {item_id_for_log}] Fotoğraf indirme işlemi iptal edildi.")
                        THREAD_QUEUE.task_done()
                        continue

                elif item_type == "user_profile_photo":
                    log_prefix = "UserProfile"
                    entity_id = profile_task["user_id"]
                    file_id = profile_task["file_id"]
                    
                    logging.debug(f"[Processor:{log_prefix} {item_id_for_log}] Async profil fotoğrafı indirme çağrılıyor...")
                    # Not: download_profile_photo_async_pyro fonksiyonu chat_id bekliyor, biz user_id gönderiyoruz.
                    # Bu fonksiyonun ikinci argümanı loglama için kullanılıyordu, sorun olmamalı.
                    coro = download_profile_photo_async_pyro(client, entity_id, file_id)
                    future = asyncio.run_coroutine_threadsafe(coro, client.loop)
                    try:
                        photo_data_bytes = future.result(timeout=DOWNLOAD_TIMEOUT)
                    except asyncio.TimeoutError:
                        logging.error(f"[Processor:{log_prefix} {item_id_for_log}] Profil fotoğrafı indirme zaman aşımına uğradı ({DOWNLOAD_TIMEOUT}s).")
                        THREAD_QUEUE.task_done()
                        continue
                    except concurrent.futures.CancelledError:
                        logging.error(f"[Processor:{log_prefix} {item_id_for_log}] Profil fotoğrafı indirme işlemi iptal edildi.")
                        THREAD_QUEUE.task_done()
                        continue

                logging.debug(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Async indirme sonucu alındı (Bytes: {photo_data_bytes is not None}).")

            except FloodWait as e:
                 # FloodWait'i burada yakalamak daha mantıklı olabilir
                 logging.warning(f"[Processor:{item_type.capitalize()} {item_id_for_log}] İndirme sırasında Flood wait: {e.value} saniye bekleniyor.")
                 time.sleep(e.value + 1)
                 THREAD_QUEUE.task_done()
                 continue # Tekrar denemek yerine şimdilik atla
            except Exception as future_err:
                 logging.error(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Fotoğraf indirme sırasında hata: {future_err}", exc_info=True)
                 THREAD_QUEUE.task_done()
                 continue

            if not photo_data_bytes:
                logging.warning(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Fotoğraf indirilemedi veya None döndü. İşleme atlanıyor.")
                THREAD_QUEUE.task_done()
                continue

            # --- Görüntü İşleme & Hash --- (Aynı kalabilir)
            photoHash = None
            photoCv2 = None
            photo_png_binary = None
            faces = []
            try:
                logging.debug(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Hash hesaplanıyor ve görüntü çözülüyor...")
                photoHash = hashlib.sha1(photo_data_bytes).hexdigest()
                photoNumpy = np.frombuffer(photo_data_bytes, dtype=np.uint8)
                photoCv2 = cv2.imdecode(photoNumpy, cv2.IMREAD_COLOR)
                if photoCv2 is None: raise ValueError("cv2.imdecode None döndürdü.")
                logging.debug(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Görüntü çözüldü. PNG'ye dönüştürülüyor...")
                encode_success, photo_png_binary_np = cv2.imencode('.png', photoCv2)
                if not encode_success: raise ValueError("Görüntü PNG formatına dönüştürülemedi.")
                photo_png_binary = photo_png_binary_np.tobytes()
                logging.debug(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Görüntü işleme tamamlandı. Hash: {photoHash}")
            except Exception as img_err:
                logging.error(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Görüntü işlenirken/dönüştürülürken hata: {img_err}", exc_info=True)
                THREAD_QUEUE.task_done()
                continue
            finally:
                 if 'photo_data_bytes' in locals() and photo_data_bytes is not None: del photo_data_bytes # İndirilen byte'ları temizle
                 if 'photoNumpy' in locals() and photoNumpy is not None: del photoNumpy

            # --- Yüz Tespiti --- (Profil fotoları için opsiyonel yapılabilir, şimdilik hep çalışsın)
            try:
                logging.debug(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Yüz tespiti başlatılıyor...")
                faces = insightFaceApp.get(photoCv2)
                if faces is None:
                     logging.warning(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Yüz tespiti None döndürdü.")
                     faces = [] # Hata olmaması için boş liste ata
                logging.debug(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Yüz tespiti tamamlandı. Bulunan yüz sayısı: {len(faces)}")
            except Exception as face_err:
                 logging.error(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Yüz tespiti sırasında hata: {face_err}", exc_info=True)
                 # Yüz tespiti hatası nedeniyle işlemi durdurma, devam et
                 faces = [] # Hata durumunda boş liste ile devam et
            finally:
                  if 'photoCv2' in locals() and photoCv2 is not None: del photoCv2 # Cv2 görüntüsünü temizle

            # --- Veritabanı Bilgilerini Hazırla --- 
            url_path = None
            base_domain = "t.me"
            image_title = "Untitled Photo"
            source_type = "telegram_message"

            if item_type == "message":
                source_type = "telegram_message"
                # --- Mesaj Linki --- (Mevcut kod korunuyor)
                try:
                    logging.debug(f"[Processor:Msg {item_id_for_log}] Mesaj linki alınıyor...")
                    full_link = message.link
                    if full_link:
                        parsed_link = urlparse(full_link)
                        if parsed_link.path and parsed_link.path.startswith('/'):
                             url_path = parsed_link.path
                        else:
                             logging.warning(f"[Processor:Msg {item_id_for_log}] Message.link ({full_link}) geçerli path içermiyor, fallback kullanılacak.")
                        base_domain = parsed_link.netloc if parsed_link.netloc else base_domain
                    else:
                         logging.warning(f"[Processor:Msg {item_id_for_log}] 'message.link' özelliği yok, fallback kullanılacak.")

                    if not url_path:
                        if message.chat and message.chat.username:
                            url_path = f"/{message.chat.username}/{message.id}"
                        elif message.chat and message.chat.id:
                             # Özel sohbetler için ID'yi pozitif yapalım
                             url_path = f"/c/{abs(message.chat.id)}/{message.id}" # 'private' yerine 'c' kullanalım
                        else: url_path = f"/unknown_chat/{message.id}"
                        logging.warning(f"[Processor:Msg {item_id_for_log}] Fallback URL Path: {url_path}")
                    logging.debug(f"[Processor:Msg {item_id_for_log}] Mesaj linki: {base_domain}{url_path}")
                except Exception as link_err:
                    logging.error(f"[Processor:Msg {item_id_for_log}] Mesaj linki alınırken/parse edilirken hata: {link_err}", exc_info=True)
                    url_path = f"/error_path/{message.chat.id if message.chat else 'nochat'}/{message.id}"
                
                # --- Mesaj Başlığı --- (Mevcut kod korunuyor ve genişletiliyor)
                image_title = message.caption if message.caption else None
                title_extended = ""
                is_forwarded = bool(getattr(message, 'forward_date', None))

                if message.chat and message.chat.title:
                    title_extended = f"||| Source: '{message.chat.title}' (ID: {message.chat.id})"
                elif message.chat and message.chat.username:
                    title_extended = f"||| Source: @{message.chat.username} (ID: {message.chat.id})"
                elif message.chat:
                     title_extended = f"||| Source Chat ID: {message.chat.id}"

                if is_forwarded:
                    if message.forward_from_chat:
                        fwd_chat_name = getattr(message.forward_from_chat, 'title', None) or getattr(message.forward_from_chat, 'username', f'Unknown Channel {message.forward_from_chat.id}')
                        title_extended += f" ||| Forwarded from: '{fwd_chat_name}'"
                    elif message.forward_from:
                        fwd_user = f"{getattr(message.forward_from, 'first_name', '')} {getattr(message.forward_from, 'last_name', '')}"
                        fwd_user = fwd_user.strip() or getattr(message.forward_from, 'username', f'Unknown User {message.forward_from.id}')
                        title_extended += f" ||| Forwarded from user: '{fwd_user}'"
                    else:
                        title_extended += f" ||| Forwarded message (hidden source)"
                
                if image_title:
                    image_title = f"{image_title} {title_extended}"
                else:
                    image_title = title_extended.strip("| ") if title_extended else "Untitled Telegram Photo"

            elif item_type == "user_profile_photo":
                source_type = "telegram_user"
                user_id = profile_task["user_id"]
                user_name = profile_task["user_name"]
                username = profile_task.get("username")
                
                # Kullanıcı profil fotoğrafları için istenen formatta URL oluştur
                base_domain = "tg" # tg://user?id=USER_ID formatı için
                url_path = f"://user?id={user_id}"
                
                # Eğer username varsa başlığa ekle
                username_text = f" (@{username})" if username else ""
                image_title = f"Profile photo for '{user_name}'{username_text} (ID: {user_id})"
                
                logging.debug(f"[Processor:UserProfile {item_id_for_log}] Kullanıcı profil fotoğrafı linki: {base_domain}{url_path}")

            # --- Veritabanı Ekleme --- (Genelleştirilmiş)
            if not photo_png_binary:
                logging.error(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Veritabanına eklenemiyor, PNG binary yok.")
                THREAD_QUEUE.task_done()
                continue
            if not photoHash:
                logging.error(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Veritabanına eklenemiyor, fotoğraf hash'i yok.")
                THREAD_QUEUE.task_done()
                continue
            if not url_path:
                logging.error(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Veritabanına eklenemiyor, URL path yok.")
                THREAD_QUEUE.task_done()
                continue

            try:
                logging.debug(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Veritabanına ekleniyor (Hash: {photoHash}, Path: {url_path})...")
                db_response = database_tools.insertImageBased(
                    protocol='https', baseDomain=base_domain, urlPath=url_path,
                    imageProtocol=None, imageDomain=None, imagePath=None, imagePathEtc=None,
                    imageTitle=image_title, imageBinary=photo_png_binary, imageHash=photoHash,
                    faces=faces, riskLevel='low', category='social', # Kategori profil için değişebilir
                    save_image=True, Source=source_type # Source tipini dinamik olarak ayarla
                )
                logging.info(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Veritabanı yanıtı: {db_response}")
            except Exception as db_err:
                 logging.error(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Veritabanına ekleme hatası (Path: {url_path}, Hash: {photoHash}): {db_err}", exc_info=True)
            finally:
                 # Bellek temizleme (faces ve photo_png_binary)
                 if 'faces' in locals() and faces is not None: del faces
                 if 'photo_png_binary' in locals() and photo_png_binary is not None: del photo_png_binary

            # --- Görevi Tamamlandı İşaretle --- 
            logging.debug(f"[Processor:{item_type.capitalize()} {item_id_for_log}] Görev tamamlandı olarak işaretleniyor.")
            THREAD_QUEUE.task_done()

        except queue.Empty:
            # Bu normalde get() blokladığı için olmamalı, ama güvenlik için kalsın
            time.sleep(0.1)
            continue
        except Exception as e:
            # Genel hata yakalama
            item_id_log = item_id_for_log if 'item_id_for_log' in locals() else "Unknown Item"
            logging.error(f"[Processor: {item_id_log}] İşleyici thread ana döngüsünde beklenmeyen hata: {e}", exc_info=True)
            # Mümkünse görevi tamamlandı işaretle ki kuyruk kilitlenmesin
            if item is not None:
                 try:
                     THREAD_QUEUE.task_done()
                     logging.warning(f"[Processor: {item_id_log}] Hata sonrası task_done çağrıldı.")
                 except ValueError:
                     # Zaten çağrılmış olabilir
                     pass
                 except Exception as td_err:
                     logging.error(f"[Processor: {item_id_log}] Hata sonrası task_done çağrılırken ek hata: {td_err}")
            # Bellek temizliği (hata durumunda)
            if 'photo_data_bytes' in locals() and photo_data_bytes is not None: del photo_data_bytes
            if 'photoNumpy' in locals() and photoNumpy is not None: del photoNumpy
            if 'photoCv2' in locals() and photoCv2 is not None: del photoCv2
            if 'faces' in locals() and faces is not None: del faces
            if 'photo_png_binary' in locals() and photo_png_binary is not None: del photo_png_binary
        finally:
            # Her öğe işlendikten sonra kısa bir süre bekle (rate limit yememek için)
            time.sleep(0.1) 

    logging.info("İşleyici thread döngüsü tamamlandı ve çıkılıyor.")


def fetch_all_chats():
    with app:
        # Program başında işlenen chat profil listesini temizle
        PROCESSED_USER_PROFILES.clear()
        logging.info("İşlenen profil fotoğrafları listesi temizlendi.")
        
        for dialog in app.get_dialogs():
            dialog: Dialog
            if dialog.chat.type == enums.ChatType.GROUP or dialog.chat.type == enums.ChatType.SUPERGROUP or dialog.chat.type == enums.ChatType.CHANNEL:
                if dialog.chat.type == enums.ChatType.GROUP or dialog.chat.type == enums.ChatType.SUPERGROUP:
                    member_count = app.get_chat_members_count(dialog.chat.id)
                    permissions = dialog.chat.permissions
                    if member_count < 100:
                        print(f"[-] Listeden eklenmicek (>100 üye veya medya gönderme izni yok): {dialog.chat.id} | {dialog.chat.title} | {member_count} üye")
                        continue
                    
                    if permissions.can_send_media_messages == False and DOWNLOAD_PROFILE_PHOTOS == False:
                        print(f"[-] Listeden eklenmicek (medya gönderme izni yok): {dialog.chat.id} | {dialog.chat.title} | {member_count} üye")
                        continue
                    else:
                        print(f"[+] Listeye ekleniyor: {dialog.chat.id} | {dialog.chat.title} | {member_count} üye")
                        LISTENED_CHAT_IDS.append(dialog.chat.id)
                else:
                    print(f"[+] Listeye ekleniyor: {dialog.chat.id} | {dialog.chat.title} | Kanal")
                    LISTENED_CHAT_IDS.append(dialog.chat.id)

fetch_all_chats()

# --- İşleyici Thread'leri Başlat --- 
NUM_WORKER_THREADS = 2 # İşleyici sayısını 2'den 4'e çıkaralım
worker_threads = []
logging.info(f"{NUM_WORKER_THREADS} adet işleyici thread başlatılıyor...")
for i in range(NUM_WORKER_THREADS):
    thread = threading.Thread(
        target=process_queue_subthread, 
        args=(app,), # Client objesini worker'a geç
        daemon=True, 
        name=f"WorkerThread-{i+1}" # Loglama için isimlendirme
    )
    worker_threads.append(thread)
    thread.start()
    logging.info(f"Worker thread {thread.name} başlatıldı.")

def main():
    try:
        # Programın her başlatılmasında işlenen profilleri temizle
        PROCESSED_USER_PROFILES.clear()
        logging.info("İşlenen profil fotoğrafları listesi temizlendi.")
        
        while True:
            with app:
                for chat_id in LISTENED_CHAT_IDS:
                    try:
                        counter = 0
                        old_messages_found = False
                        
                        while not old_messages_found:
                            chat = app.get_chat(chat_id)
                            logging.info(f"[+] Chat işleniyor: {chat.id} | {chat.title} | {chat.username} | {chat.type}")
                            
                            messages = list(app.get_chat_history(chat_id, limit=300, offset=counter*300))
                            counter += 1
                            
                            if not messages:
                                logging.info(f"[!] {chat.id} için daha fazla mesaj bulunamadı.")
                                break  # Mesaj kalmadıysa döngüyü kır
                            
                            for message in messages:
                                message: Message
                                
                                # 1 günden eski mesaj kontrolü
                                if message.date < datetime.now() - timedelta(days=1):
                                    old_messages_found = True
                                    logging.info(f"[!] 1 günden eski mesajlara ulaşıldı: {message.date}")
                                    break
                                
                                # Sadece fotoğraf içeren mesajları işle
                                if message.photo:
                                    # Fotoğraf boyutu kontrolü
                                    if hasattr(message.photo, 'file_size') and message.photo.file_size > 1024 * 1024 * 5:
                                        logging.warning(f"[-] Fotoğraf boyutu 5MB'tan büyük, atlandı... Chat: {chat.id}, Msg: {message.id}")
                                        continue
                                    
                                    while True:
                                        if not THREAD_QUEUE.full():
                                            break
                                        else:
                                            logging.warning(f"[-] Queue dolu {THREAD_QUEUE.qsize()} mesaj var, 1 saniye bekleniyor...")
                                            time.sleep(1)
                                    
                                    # Queue kontrolü
                                    if THREAD_QUEUE.full():
                                        logging.warning(f"[-] Queue dolu, mesaj atlandı... Chat: {chat.id}, Msg: {message.id}")
                                        continue
                                    else:
                                        # Kuyruğa eklemeden önce çok kısa bekle
                                        time.sleep(0.02)
                                        THREAD_QUEUE.put_nowait(message)
                                        logging.info(f"[+] Queue'ya eklendi:{message.link} Chat: {chat.id}, Msg: {message.id}")
                                
                                # Mesajı gönderenin profil fotoğrafını kontrol et ve ekle (DOWNLOAD_PROFILE_PHOTOS aktifse)
                                if DOWNLOAD_PROFILE_PHOTOS and message.from_user and message.from_user.photo:
                                    user_id = message.from_user.id
                                    
                                    # Bu kullanıcının profil fotoğrafı daha önce işlenmişse atla
                                    if user_id in PROCESSED_USER_PROFILES:
                                        logging.debug(f"[+] Kullanıcı profil fotoğrafı daha önce eklenmiş, atlanıyor: User ID {user_id}")
                                        continue
                                        
                                        
                                        
                                    while True:
                                        if not THREAD_QUEUE.full():
                                            break
                                        else:
                                            logging.warning(f"[-] Queue dolu {THREAD_QUEUE.qsize()} mesaj var profil fotoğrafı için, 1 saniye bekleniyor...")
                                            time.sleep(1)
                                            
                                            
                                    # Kuyruğu kontrol et
                                    if THREAD_QUEUE.full():
                                        logging.warning(f"[-] Queue dolu, kullanıcı profil fotoğrafı atlandı... User ID: {user_id}")
                                        continue
                                    
                                    # Profil fotoğrafını kuyruğa ekle
                                    user_name = message.from_user.first_name
                                    if message.from_user.last_name:
                                        user_name += f" {message.from_user.last_name}"
                                    
                                    profile_photo_task = {
                                        "type": "user_profile_photo",
                                        "user_id": user_id,
                                        "user_name": user_name,
                                        "username": message.from_user.username,
                                        "file_id": message.from_user.photo.big_file_id
                                    }
                                    
                                    try:
                                        # Eklemeden önce boyut kontrolü yap
                                        if len(PROCESSED_USER_PROFILES) >= MAX_PROCESSED_USER_PROFILES:
                                            oldest_user_id, _ = PROCESSED_USER_PROFILES.popitem(last=False)
                                            logging.debug(f"[Cache] Kullanıcı profil listesi limiti aşıldı. En eski ID ({oldest_user_id}) silindi.")
                                            
                                        # Kuyruğa eklemeden önce çok kısa bekle
                                        time.sleep(0.02)
                                        THREAD_QUEUE.put_nowait(profile_photo_task)
                                        PROCESSED_USER_PROFILES[user_id] = None  # İşlenen profillere ekle (değer önemli değil)
                                        logging.info(f"[+] Kullanıcı profil fotoğrafı görevi kuyruğa eklendi: User ID {user_id}, Name: {user_name}")
                                    except queue.Full:
                                        logging.warning(f"[!] Kullanıcı profil fotoğrafı eklenemedi, kuyruk dolu: User ID {user_id}")
                    
                    except FloodWait as e:
                        logging.warning(f"[!] FloodWait hatası: {e.value} saniye bekleniyor...")
                        time.sleep(e.value + 1)
                    except Exception as e:
                        logging.error(f"[-] Chat işlenirken hata: {chat_id} - {str(e)}")
                        logging.debug(traceback.format_exc())
                
                # Her döngü sonunda biraz bekle
                time.sleep(1)
                
            time.sleep(3600)  # 1 saat bekle
    except KeyboardInterrupt:
        logging.info("Kullanıcı tarafından durduruldu.")
    except Exception as e:
        logging.critical(f"Ana döngüde kritik hata: {str(e)}")
        logging.debug(traceback.format_exc())
    finally:
        # İşleyici thread'leri durdur
        logging.info("İşleyici thread'ler durduruluyor...")
        for _ in worker_threads:
             THREAD_QUEUE.put(None) # Her işleyici için durma sinyali gönder
        
        # Thread'lerin bitmesini bekle
        for thread in worker_threads:
            thread.join(timeout=10.0) # 10 saniye bekleme süresi
            if thread.is_alive():
                logging.warning(f"İşleyici thread {thread.name} zamanında durmadı.")

        logging.info("Program sonlandırıldı.")


if __name__ == "__main__":
    asyncio.run(main())




