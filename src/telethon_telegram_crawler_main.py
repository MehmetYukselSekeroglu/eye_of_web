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
from collections import OrderedDict # Sıralı dictionary için eklendi
import colorlog
from datetime import datetime, timedelta

# Telethon Imports
from telethon import TelegramClient, events, types, functions, errors as telethon_errors
from telethon.tl.types import MessageMediaPhoto, UserProfilePhoto, Chat, Channel, User, Message

# Shared Library Imports (Assuming they are compatible)
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

# Telethon loglarını biraz kısmak için (isteğe bağlı)
# logging.getLogger('telethon').setLevel(logging.WARNING)


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


# --- Telethon Configuration ---
API_ID = 12345
API_HASH = 'YOUR_API_HASH'
SESSION_NAME = 'telethon_crawler_user' # Farklı bir session ismi kullanalım

# --- Operating Mode ---
# True ise sadece yeni gelen mesajları işler, False ise periyodik olarak geçmişi tarar.
PROCESS_REALTIME_MESSAGES = True# <<< Bu mod ve yeni moddan sadece biri True olmalı
# <<< YENİ MOD >>> True ise sadece yeni mesaj gönderenlerin profil fotoğraflarını işler.
PROCESS_ONLY_SENDER_PROFILES = False # <<< Yeni mod ayarı

MAX_QUEUE_SIZE = 50
LISTENED_CHAT_IDS = [] # Dinlenecek chat ID'leri fetch_all_chats_telethon içinde doldurulacak
DOWNLOAD_QUEUE = asyncio.Queue(maxsize=MAX_QUEUE_SIZE * 2) # İndirme görevleri için async kuyruk
PROCESSING_QUEUE = queue.Queue(maxsize=MAX_QUEUE_SIZE) # İşleme için thread-safe kuyruk
DOWNLOAD_TIMEOUT = 30 # İndirme zaman aşımı (saniye)
DOWNLOAD_PROFILE_PHOTOS = True # <<< Profil fotoları indirilecekse bu True olmalı
PROCESSED_USER_PROFILES = OrderedDict() # İşlenen profilleri takip et
MAX_PROCESSED_USER_PROFILES = 100 # Maksimum takip edilen profil sayısı
PROFILE_TRACKING_TIMEOUT_DAYS = 7 # Profil takip zaman aşımı (gün)
# LAST_PROFILE_RESET_TIME = datetime.now() # Gerekirse kullanılabilir
NUM_DOWNLOAD_WORKERS = 4 # Asenkron indirme işçisi sayısı
NUM_PROCESSING_WORKERS = 2 # Senkron işleme işçisi sayısı (CPU/DB bound)

# --- Telethon Client Initialization ---
# Client'ı global olarak tanımlayalım, main içinde başlatacağız
client = TelegramClient(SESSION_NAME, API_ID, API_HASH,
                        base_logger=logger, # Mevcut logger'ı kullan
                        # connection_retries=5, # Bağlantı deneme sayısı
                        # retry_delay=5 # Denemeler arası bekleme süresi
                        )

# ==============================================================================
# Processing Thread (Handles CPU/DB bound tasks: CV2, InsightFace, DB Insert)
# ==============================================================================
def process_downloaded_item_thread():
    """
    PROCESSING_QUEUE'dan öğeleri alır (indirilen veriler),
    görüntü işleme (CV2, InsightFace) yapar ve veritabanına kaydeder.
    Bu thread Telethon client ile doğrudan etkileşime girmez.
    """
    global database_tools, insightFaceApp
    thread_name = threading.current_thread().name
    logging.info(f"[{thread_name}] İşleme thread'i başlatıldı.")

    while True:
        item_data = None
        try:
            logging.debug(f"[{thread_name}] İşleme kuyruğundan öğe bekleniyor... (Mevcut boyut: {PROCESSING_QUEUE.qsize()})")
            item_data = PROCESSING_QUEUE.get() # Bloklayarak bekle
            if item_data is None:
                logging.info(f"[{thread_name}] İşleme thread'i durdurma sinyali (None) aldı.")
                break # Döngüyü sonlandır

            # Gerekli verileri item_data'dan çıkar
            item_type = item_data.get("item_type", "unknown")
            log_id = item_data.get("log_id", "Unknown ID") # Mesaj ID veya File ID
            chat_id_for_log = item_data.get("chat_id_for_log", "N/A")
            photo_data_bytes = item_data.get("photo_data_bytes")
            photoHash = item_data.get("photoHash")
            url_path = item_data.get("url_path")
            base_domain = item_data.get("base_domain", "t.me")
            image_title = item_data.get("image_title", "Untitled")
            source_type = item_data.get("source_type", "telegram")

            log_prefix = f"Processor:{item_type.capitalize()} {log_id}"
            logging.debug(f"[{log_prefix}] İşlenmek üzere öğe alındı. İlgili ID: {chat_id_for_log}")

            if not photo_data_bytes or not photoHash or not url_path:
                logging.error(f"[{log_prefix}] İşleme için gerekli veri eksik (bytes: {photo_data_bytes is not None}, hash: {photoHash is not None}, path: {url_path is not None}). Öğe atlanıyor.")
                PROCESSING_QUEUE.task_done()
                continue

            # --- Görüntü İşleme & Yüz Tespiti ---
            photoCv2 = None
            photo_png_binary = None
            faces = []
            try:
                logging.debug(f"[{log_prefix}] Görüntü çözülüyor...")
                photoNumpy = np.frombuffer(photo_data_bytes, dtype=np.uint8)
                photoCv2 = cv2.imdecode(photoNumpy, cv2.IMREAD_COLOR)
                if photoCv2 is None: raise ValueError("cv2.imdecode None döndürdü.")

                logging.debug(f"[{log_prefix}] Görüntü çözüldü. PNG'ye dönüştürülüyor...")
                encode_success, photo_png_binary_np = cv2.imencode('.png', photoCv2)
                if not encode_success: raise ValueError("Görüntü PNG formatına dönüştürülemedi.")
                photo_png_binary = photo_png_binary_np.tobytes()
                logging.debug(f"[{log_prefix}] PNG dönüşümü tamamlandı.")

                logging.debug(f"[{log_prefix}] Yüz tespiti başlatılıyor...")
                faces = insightFaceApp.get(photoCv2) # Use the actual CV2 image
                if faces is None:
                     logging.warning(f"[{log_prefix}] Yüz tespiti None döndürdü.")
                     faces = []
                logging.debug(f"[{log_prefix}] Yüz tespiti tamamlandı. Bulunan yüz sayısı: {len(faces)}")

            except Exception as img_err:
                logging.error(f"[{log_prefix}] Görüntü işlenirken/dönüştürülürken veya yüz tespiti sırasında hata: {img_err}", exc_info=True)
                # Bellek temizleme
                if 'photo_data_bytes' in locals(): del photo_data_bytes
                if 'photoNumpy' in locals(): del photoNumpy
                if 'photoCv2' in locals(): del photoCv2
                if 'faces' in locals(): del faces
                if 'photo_png_binary' in locals(): del photo_png_binary
                PROCESSING_QUEUE.task_done()
                continue
            finally:
                # Görüntü verilerini işledikten sonra temizle
                if 'photo_data_bytes' in locals(): del photo_data_bytes
                if 'photoNumpy' in locals(): del photoNumpy
                if 'photoCv2' in locals(): del photoCv2


            # --- Veritabanı Ekleme ---
            if not photo_png_binary:
                logging.error(f"[{log_prefix}] Veritabanına eklenemiyor, PNG binary yok.")
                PROCESSING_QUEUE.task_done()
                continue

            try:
                logging.debug(f"[{log_prefix}] Veritabanına ekleniyor (Hash: {photoHash}, Path: {url_path})...")
                db_response = database_tools.insertImageBased(
                    protocol='https', baseDomain=base_domain, urlPath=url_path,
                    imageProtocol=None, imageDomain=None, imagePath=None, imagePathEtc=None,
                    imageTitle=image_title, imageBinary=photo_png_binary, imageHash=photoHash,
                    faces=faces, riskLevel='low', category='social', # Kategori profil için değişebilir
                    save_image=True, Source=source_type # Source tipini dinamik olarak ayarla
                )
                logging.info(f"[{log_prefix}] Veritabanı yanıtı: {db_response}")
            except Exception as db_err:
                 logging.error(f"[{log_prefix}] Veritabanına ekleme hatası (Path: {url_path}, Hash: {photoHash}): {db_err}", exc_info=True)
            finally:
                 # Bellek temizleme
                 if 'faces' in locals(): del faces
                 if 'photo_png_binary' in locals(): del photo_png_binary

            # --- Görevi Tamamlandı İşaretle ---
            logging.debug(f"[{log_prefix}] Görev tamamlandı olarak işaretleniyor.")
            PROCESSING_QUEUE.task_done()

        except queue.Empty:
            # Bu normalde get() blokladığı için olmamalı, ama güvenlik için kalsın
            time.sleep(0.1) # CPU kullanımı için kısa bekleme
            continue
        except Exception as e:
            # Genel hata yakalama
            log_id_err = item_data.get("log_id", "Unknown Item") if item_data else "Unknown Item"
            logging.error(f"[{thread_name}: {log_id_err}] İşleme thread ana döngüsünde beklenmeyen hata: {e}", exc_info=True)
            # Mümkünse görevi tamamlandı işaretle ki kuyruk kilitlenmesin
            if item_data is not None:
                 try:
                     PROCESSING_QUEUE.task_done()
                     logging.warning(f"[{thread_name}: {log_id_err}] Hata sonrası task_done çağrıldı.")
                 except ValueError: pass # Zaten çağrılmış olabilir
                 except Exception as td_err:
                     logging.error(f"[{thread_name}: {log_id_err}] Hata sonrası task_done çağrılırken ek hata: {td_err}")
            # Bellek temizliği (hata durumunda) - Yukarıda yapılıyor zaten
        finally:
            # Her öğe işlendikten sonra kısa bir süre bekle (I/O veya CPU'yu rahatlatmak için)
            time.sleep(0.05)

    logging.info(f"[{thread_name}] İşleme thread döngüsü tamamlandı ve çıkılıyor.")


# ==============================================================================
# Download Worker (Handles Async Download Tasks)
# ==============================================================================
async def download_worker(name: str, download_queue: asyncio.Queue, processing_queue: queue.Queue):
    """
    DOWNLOAD_QUEUE'dan görevleri alır, Telethon kullanarak medyayı indirir,
    hash hesaplar ve işlenmek üzere PROCESSING_QUEUE'ya gönderir.
    """
    logging.info(f"[{name}] İndirme işçisi başlatıldı.")
    while True:
        task_info = None
        try:
            logging.debug(f"[{name}] İndirme kuyruğundan görev bekleniyor... (Mevcut boyut: {download_queue.qsize()})")
            task_info = await download_queue.get()
            if task_info is None:
                logging.info(f"[{name}] İndirme işçisi durdurma sinyali aldı.")
                download_queue.task_done()
                break

            task_type = task_info.get("type")
            log_id = "Unknown ID"
            chat_id_for_log = "N/A"

            photo_data_bytes = None
            photoHash = None
            url_path = None
            base_domain = "t.me"
            image_title = "Untitled"
            source_type = "telegram"
            media_to_download = None # İndirilecek medya objesi (MessageMedia veya UserProfilePhoto)

            # --- İndirme İşlemi ---
            max_retries = 3
            initial_backoff = 2 # saniye

            if task_type == "message_photo":
                message = task_info.get("message")
                if not message or not hasattr(message, 'photo') or not message.photo: # hasattr ekleyelim
                    logging.warning(f"[{name}] Geçersiz mesaj fotoğrafı görevi alındı (mesaj veya fotoğraf yok): {task_info}")
                    download_queue.task_done()
                    continue
                log_id = message.id
                # chat_id 'yi message objesinden almak daha güvenli olabilir
                chat_id_for_log = message.chat_id if hasattr(message, 'chat_id') else "N/A"
                log_prefix = f"{name}:Msg {log_id}"
                media_to_download = message.media # Veya message.photo doğrudan kullanılabilir

                # Mesaj linki ve başlık hazırlama
                try:
                    # Telethon'da message.link yok, elle oluşturmak gerekebilir veya PeerID kullan
                    chat = await message.get_chat() # Veya task_info içinde chat objesi gönderilebilir
                    if isinstance(chat, (Chat, Channel)) and chat.username:
                         base_domain = "t.me"
                         url_path = f"/{chat.username}/{message.id}"
                    else: # Özel sohbet veya kullanıcı adı olmayan kanal/grup
                         # Peer ID'leri kullanmak daha stabil olabilir
                         peer_id_val = None
                         if hasattr(message, 'peer_id'):
                              peer_id_val = getattr(message.peer_id, 'channel_id', None) or \
                                            getattr(message.peer_id, 'chat_id', None) or \
                                            getattr(message.peer_id, 'user_id', None)
                         if peer_id_val:
                              peer_id = abs(peer_id_val)
                              if chat_id_for_log == "N/A": chat_id_for_log = peer_id # Eğer chat_id alamadıysak buradan alalım
                         else: # peer_id bile yoksa chat_id'yi kullanalım
                              peer_id = abs(chat_id_for_log) if isinstance(chat_id_for_log, int) else chat_id_for_log

                         if peer_id != abs(chat_id_for_log) and chat_id_for_log != "N/A": # Check consistency (mutlak değerle karşılaştır)
                              logging.warning(f"[{log_prefix}] PeerID ({peer_id}) ve chat_id_for_log ({chat_id_for_log}) farklı.")
                         url_path = f"/c/{peer_id}/{message.id}" # 'c' prefix genel kullanım
                         base_domain = "t.me" # Veya başka bir belirteç

                    image_title = message.text if message.text else None # Telethon'da caption=text
                    title_extended = ""

                    # Chat title/username
                    if chat:
                         chat_title = getattr(chat, 'title', None)
                         chat_username = getattr(chat, 'username', None)
                         chat_id_log = chat.id if hasattr(chat, 'id') else chat_id_for_log
                         if chat_title:
                             title_extended += f"||| Source: '{chat_title}' (ID: {chat_id_log})"
                         elif chat_username:
                             title_extended += f"||| Source: @{chat_username} (ID: {chat_id_log})"
                         else:
                              title_extended += f"||| Source Chat ID: {chat_id_log}"

                    # Forwarding info
                    if message.forward:
                        fwd_from = None
                        fwd_from_id = None
                        # Telethon'da forward bilgisi message.forward içinde
                        if message.forward.chat: # Kanal/Gruptan forward
                             fwd_from = message.forward.chat
                        elif message.forward.sender: # Kullanıcıdan forward (gizli değilse)
                             fwd_from = message.forward.sender
                        elif message.forward.from_id: # Gizli kullanıcı/kanal ID'si
                             fwd_from_id = message.forward.from_id

                        fwd_name = "Unknown Source"
                        if fwd_from:
                           fwd_name = getattr(fwd_from, 'title', None) or \
                                        getattr(fwd_from, 'username', None) or \
                                        f"{getattr(fwd_from, 'first_name', '')} {getattr(fwd_from, 'last_name', '')}".strip() or \
                                        f"ID: {getattr(fwd_from, 'id', 'N/A')}"
                        elif fwd_from_id:
                            try: # ID'den entity almayı dene (pahalı olabilir, dikkat)
                                fwd_entity = await client.get_entity(fwd_from_id)
                                fwd_name = getattr(fwd_entity, 'title', None) or \
                                           getattr(fwd_entity, 'username', None) or \
                                           f"{getattr(fwd_entity, 'first_name', '')} {getattr(fwd_entity, 'last_name', '')}".strip() or \
                                           f"ID: {fwd_entity.id}"
                            except Exception as fwd_exc:
                                 logging.warning(f"[{log_prefix}] Forward ID'sinden entity alınamadı ({fwd_from_id}): {fwd_exc}")
                                 fwd_name = f"Unknown ID: {fwd_from_id}"
                        else: # Belki forward.from_name vardır? (Nadiren)
                            fwd_name = getattr(message.forward, 'from_name', "Hidden Source")

                        title_extended += f" ||| Forwarded from: '{fwd_name}'"

                    if image_title: image_title = f"{image_title} {title_extended}"
                    else: image_title = title_extended.strip("| ") if title_extended else "Untitled Telegram Photo"

                    source_type = "telegram_message"
                    logging.debug(f"[{log_prefix}] URL Path: {base_domain}{url_path}, Title: {image_title[:50]}...")

                except Exception as info_err:
                    logging.error(f"[{log_prefix}] Mesaj bilgileri alınırken hata: {info_err}", exc_info=True)
                    # Fallback bilgilerle devam et
                    url_path = f"/error_path/{chat_id_for_log}/{log_id}"
                    image_title = f"Error Processing Info (Msg ID: {log_id})"
                    source_type = "telegram_message"

            elif task_type == "user_profile_photo":
                user_id = task_info.get("user_id")
                user_info = task_info.get("user_info") # User objesi veya dict olabilir
                photo_info = task_info.get("photo") # UserProfilePhoto objesi
                if not user_id or not user_info or not photo_info:
                    logging.warning(f"[{name}] Geçersiz profil fotoğrafı görevi alındı: {task_info}")
                    download_queue.task_done()
                    continue

                # photo_id daha unique ama UserProfilePhoto'da yok, photo objesinin ID'si var mı?
                # UserProfilePhoto objesi doğrudan media gibi indirilebilir. Log için user_id yeterli.
                log_id = f"User_{user_id}_Profile"
                chat_id_for_log = user_id # Loglama için
                log_prefix = f"{name}:Profile {user_id}"
                media_to_download = photo_info # İndirme için UserProfilePhoto kullanılabilir

                # Profil linki ve başlık hazırlama
                try:
                     user_name = f"{getattr(user_info, 'first_name', '')} {getattr(user_info, 'last_name', '')}".strip()
                     username = getattr(user_info, 'username', None)

                     # tg://user?id=USER_ID formatı
                     base_domain = "tg"
                     url_path = f"://user?id={user_id}"

                     username_text = f" (@{username})" if username else ""
                     image_title = f"Profile photo for '{user_name}'{username_text} (ID: {user_id})"
                     source_type = "telegram_user"
                     logging.debug(f"[{log_prefix}] URL Path: {base_domain}{url_path}, Title: {image_title}")

                except Exception as info_err:
                     logging.error(f"[{log_prefix}] Profil bilgileri alınırken hata: {info_err}", exc_info=True)
                     url_path = f"/error_profile_path/{user_id}"
                     image_title = f"Error Processing Profile Info (User ID: {user_id})"
                     source_type = "telegram_user"

            else:
                logging.error(f"[{name}] Bilinmeyen görev tipi: {task_type}. Görev: {task_info}")
                download_queue.task_done()
                continue

            # Eğer indirilecek medya objesi yoksa devam etme
            if not media_to_download:
                logging.error(f"[{log_prefix}] İndirilecek medya objesi bulunamadı. Görev atlanıyor.")
                download_queue.task_done()
                continue

            # --- Asıl İndirme Döngüsü ---
            for attempt in range(max_retries):
                try:
                    logging.debug(f"[{log_prefix}] İndirme deneniyor... (Deneme {attempt + 1}/{max_retries})")
                    # Telethon'da download_media dosyayı byte dizisi olarak döndürebilir
                    # Timeout için asyncio.wait_for kullanalım
                    photo_data_bytes = await asyncio.wait_for(
                        client.download_media(media_to_download, file=bytes),
                        timeout=DOWNLOAD_TIMEOUT
                    )

                    if photo_data_bytes:
                        logging.debug(f"[{log_prefix}] Başarıyla indirildi ({len(photo_data_bytes)} bytes)")
                        # Hash hesapla
                        photoHash = hashlib.sha1(photo_data_bytes).hexdigest()
                        logging.debug(f"[{log_prefix}] Hash hesaplandı: {photoHash}")
                        break # Başarılı, döngüden çık
                    else:
                        logging.warning(f"[{log_prefix}] İndirme None veya boş byte döndürdü (Deneme {attempt + 1}).")
                        # None dönerse tekrar denemek mantıklı olabilir mi? Şimdilik deneyelim.
                        if attempt + 1 >= max_retries:
                            logging.error(f"[{log_prefix}] Maksimum deneme sonrası boş sonuç.")
                            photo_data_bytes = None # Emin olalım
                            break
                        else:
                            # Tekrar denemeden önce bekle
                            backoff_time = initial_backoff * (2 ** attempt)
                            logging.info(f"[{log_prefix}] Boş sonuç sonrası {backoff_time} saniye sonra tekrar denenecek...")
                            await asyncio.sleep(backoff_time)
                            continue

                except asyncio.TimeoutError:
                    logging.warning(f"[{log_prefix}] İndirme zaman aşımına uğradı ({DOWNLOAD_TIMEOUT}s) (Deneme {attempt + 1}).")
                    if attempt + 1 >= max_retries:
                         logging.error(f"[{log_prefix}] Zaman aşımı sonrası maksimum deneme sayısına ulaşıldı.")
                         photo_data_bytes = None
                         break
                    else:
                         backoff_time = initial_backoff * (2 ** attempt)
                         logging.info(f"[{log_prefix}] Zaman aşımı sonrası {backoff_time} saniye sonra tekrar denenecek...")
                         await asyncio.sleep(backoff_time)
                         continue
                except telethon_errors.FloodWaitError as e:
                    wait_time = e.seconds + 1
                    logging.warning(f"[{log_prefix}] İndirme sırasında Flood wait: {wait_time} saniye bekleniyor. (Deneme {attempt + 1})")
                    if attempt + 1 >= max_retries:
                        logging.error(f"[{log_prefix}] FloodWait sonrası maksimum deneme sayısına ulaşıldı.")
                        photo_data_bytes = None
                        break
                    else:
                         logging.info(f"[{log_prefix}] FloodWait sonrası {wait_time} saniye sonra tekrar denenecek...")
                         await asyncio.sleep(wait_time)
                         # FloodWait sonrası deneme sayısını artırmadan tekrar deneyebiliriz belki?
                         # Şimdilik normal backoff ile devam edelim.
                         continue # Aynı deneme sayısıyla devam etmek yerine bir sonraki attempt'e geçelim
                except (telethon_errors.FileReferenceExpiredError, telethon_errors.MediaExpiredError) as e:
                     logging.warning(f"[{log_prefix}] İndirme hatası: File Reference Expired ({e}). Bu görev tekrar denenmeyecek.")
                     # TODO: Belki mesajı tekrar fetch edip yeni referans alınabilir? Şimdilik atla.
                     photo_data_bytes = None
                     break # Bu hatada tekrar deneme anlamsız
                except telethon_errors.PhotoInvalidError as e:
                     logging.warning(f"[{log_prefix}] İndirme hatası: Photo Invalid ({e}). Bu fotoğraf indirilemiyor.")
                     photo_data_bytes = None
                     break # Bu hatada tekrar deneme anlamsız
                except telethon_errors.rpcerrorlist.WebpageMediaEmptyError as e:
                     logging.warning(f"[{log_prefix}] İndirme hatası: WebpageMediaEmpty ({e}). Genellikle önizlemesi olmayan linklerde olur. Atlanıyor.")
                     photo_data_bytes = None
                     break # Bu hatada tekrar deneme anlamsız
                except Exception as e:
                    # Yaygın olmayan veya beklenmedik hataları logla
                    logging.error(f"[{log_prefix}] Beklenmedik indirme hatası (Deneme {attempt + 1}): {type(e).__name__}: {e}", exc_info=True)
                    if attempt + 1 >= max_retries:
                        logging.error(f"[{log_prefix}] Bilinmeyen hata sonrası maksimum deneme sayısına ulaşıldı.")
                        photo_data_bytes = None
                        break
                    else:
                        backoff_time = initial_backoff * (2 ** attempt)
                        logging.info(f"[{log_prefix}] Bilinmeyen hata sonrası {backoff_time} saniye sonra tekrar denenecek...")
                        await asyncio.sleep(backoff_time)
                        continue

            # --- İşleme Kuyruğuna Gönderme ---
            if photo_data_bytes and photoHash and url_path:
                processing_task = {
                    "item_type": task_type,
                    "log_id": log_id,
                    "chat_id_for_log": chat_id_for_log,
                    "photo_data_bytes": photo_data_bytes,
                    "photoHash": photoHash,
                    "url_path": url_path,
                    "base_domain": base_domain,
                    "image_title": image_title,
                    "source_type": source_type
                }
                try:
                    # Processing queue'nun dolmasını beklemeden önce kontrol et
                    while processing_queue.full():
                        logging.warning(f"[{log_prefix}] İşleme kuyruğu dolu ({processing_queue.qsize()}/{MAX_QUEUE_SIZE}), 0.5 saniye bekleniyor...")
                        await asyncio.sleep(0.5) # Async bekleme

                    processing_queue.put_nowait(processing_task)
                    logging.info(f"[{log_prefix}] İndirilen öğe ({len(photo_data_bytes)} bytes) işleme kuyruğuna eklendi.")
                except queue.Full:
                     # Put_nowait nadiren hata vermeli ama yakalayalım
                     logging.error(f"[{log_prefix}] İşleme kuyruğuna eklenemedi (hala dolu mu?). Veri kayboldu!")
                     # Kaybolan veriyi belki loglamak veya başka bir yere yazmak gerekebilir.
                     if 'photo_data_bytes' in locals(): del photo_data_bytes # Belleği temizle
                except Exception as q_err:
                    logging.error(f"[{log_prefix}] İşleme kuyruğuna eklerken hata: {q_err}", exc_info=True)
                    if 'photo_data_bytes' in locals(): del photo_data_bytes # Belleği temizle

            else:
                if not photo_data_bytes: # Sadece indirme başarısızsa logla, bilgi eksikse yukarıda loglandı zaten
                     logging.error(f"[{log_prefix}] İndirme başarısız oldu. İşleme kuyruğuna eklenmedi.")

            # Görevi tamamlandı olarak işaretle
            download_queue.task_done()

        except Exception as e:
            # Ana döngüde hata
            log_id_err = log_id if 'log_id' in locals() else task_info.get("log_id", "Unknown Task") if task_info else "Unknown Task"
            logging.error(f"[{name}: {log_id_err}] İndirme işçisi ana döngüsünde beklenmeyen hata: {type(e).__name__}: {e}", exc_info=True)
            if task_info:
                try:
                     # Hata durumunda da task_done çağırılmalı ki kuyruk ilerlesin
                     download_queue.task_done()
                     logging.warning(f"[{name}: {log_id_err}] Hata sonrası download_queue.task_done() çağrıldı.")
                except ValueError: pass # Zaten çağrılmış olabilir
                except Exception as td_err:
                     logging.error(f"[{name}: {log_id_err}] Hata sonrası task_done çağrılırken ek hata: {td_err}")
            # Bellek temizliği? photo_data_bytes yukarıda yönetiliyor olmalı.
        finally:
             # Her görevden sonra çok kısa bir süre bekle (API limitleri için biraz nefes aldır)
             await asyncio.sleep(0.1)

    logging.info(f"[{name}] İndirme işçisi döngüsü tamamlandı ve çıkılıyor.")


# ==============================================================================
# Chat Fetching Logic
# ==============================================================================
async def fetch_all_chats_telethon():
    """Telethon kullanarak dinlenecek chat'leri alır."""
    global LISTENED_CHAT_IDS
    LISTENED_CHAT_IDS = [] # Başlangıçta temizle
    # Program başında işlenen chat profil listesini temizle (opsiyonel, başlangıçta kalsın)
    # PROCESSED_USER_PROFILES.clear()
    # logging.info("İşlenen profil fotoğrafları listesi temizlendi.")

    logging.info("Dialoglar alınıyor...")
    processed_dialogs = 0
    added_chats = 0
    try:
        # limit=None ile tüm dialogları çekmeyi dener, çok fazla dialog varsa yavaş olabilir/kısıtlanabilir.
        # Gerekirse `limit` parametresi eklenebilir.
        async for dialog in client.iter_dialogs():
            processed_dialogs += 1
            chat = dialog.entity
            chat_id = dialog.id # Bu ID event handler için kullanılacak
            chat_title = dialog.name
            is_group = dialog.is_group
            is_channel = dialog.is_channel
            is_user = dialog.is_user # Kullanıcıları da alıyor, filtrelemek gerekebilir

            # Sadece Gruplar, Süpergruplar ve Kanalları dahil et
            if not (is_group or is_channel):
                continue

            log_prefix = f"ChatFetch:{chat_id}"

            try:
                # Chat entity'sini alalım (daha fazla bilgi için)
                # iter_dialogs zaten entity veriyor ama bazen eksik olabilir? get_entity daha garanti.
                # Ancak her dialog için get_entity çağırmak yavaş olabilir. dialog.entity kullanalım.
                if isinstance(chat, (types.Chat, types.Channel)):
                    # Üye sayısı ve izin kontrolü (Sadece gruplar için mantıklı)
                    if is_group:
                        member_count = getattr(chat, 'participants_count', None)
                        # Telethon'da izinler biraz daha farklı alınır.
                        # dialog.entity üzerinden veya get_permissions ile alınabilir.
                        # Şimdilik basitçe medya gönderme iznine bakalım (genelde botlar için değil, kullanıcı hesabı için)
                        # Botlar genelde admin değilse gönderemez, kullanıcılar için `send_media` yetkisi önemli.
                        # Bu kontrol kullanıcı hesabı ile çalıştırılıyorsa anlamlı.
                        # Bot ile çalıştırılıyorsa, genellikle kanal/grup mesajlarını okuyabilir.
                        # can_send_media = True # Varsayılan olarak izinli kabul edelim, aksi ispatlanmadıkça
                        # İzinleri detaylı kontrol etmek gerekirse:
                        # full_chat = await client(functions.channels.GetFullChannelRequest(channel=chat)) # veya GetFullChatRequest
                        # permissions = full_chat.chat.default_banned_rights # veya admin_rights vs.
                        # can_send_media = not full_chat.chat.default_banned_rights.send_media # Yasaklanmamışsa gönderebilir

                        # Gerekli kontroller (Pyrogram'daki gibi) - Sadece üye sayısı kontrolü yeterli olabilir
                        if member_count is not None and member_count < 100:
                             logging.info(f"[{log_prefix}] Listeye eklenmeyecek (< 100 üye): {chat_title} ({member_count} üye)")
                             continue

                        # Medya gönderme izni ve profil fotosu indirme kapalıysa ekleme - Şimdilik kaldırıldı
                        # if not can_send_media and not DOWNLOAD_PROFILE_PHOTOS:
                        #     logging.info(f"[{log_prefix}] Listeye eklenmeyecek (medya izni yok ve profil indirme kapalı): {chat_title}")
                        #     continue

                        logging.info(f"[+] Grup listeye ekleniyor: {chat_id} | {chat_title} ({member_count or 'N/A'} üye)")
                        LISTENED_CHAT_IDS.append(chat_id)
                        added_chats += 1

                    elif is_channel:
                        # Kanallar için üye sayısı veya izin kontrolü genelde gerekmez (mesajları okuyabiliyorsak)
                        logging.info(f"[+] Kanal listeye ekleniyor: {chat_id} | {chat_title}")
                        LISTENED_CHAT_IDS.append(chat_id)
                        added_chats += 1

                else:
                    logging.warning(f"[{log_prefix}] Beklenmedik dialog entity tipi: {type(chat)}")

            except telethon_errors.ChannelPrivateError:
                 logging.warning(f"[{log_prefix}] Kanala erişim yok (private): {chat_title}")
            except telethon_errors.ChatAdminRequiredError:
                 logging.warning(f"[{log_prefix}] Chat bilgisi için admin yetkisi gerekli: {chat_title}")
            except Exception as e:
                 logging.error(f"[{log_prefix}] Dialog işlenirken hata: {chat_title} - {e}", exc_info=True)

    except telethon_errors.FloodWaitError as e:
         logging.error(f"Dialogları alırken FloodWait hatası: {e.seconds} saniye bekleniyor...")
         await asyncio.sleep(e.seconds + 1)
         # İsteğe bağlı olarak burada tekrar çağırmayı deneyebiliriz veya programı durdurabiliriz.
    except Exception as e:
        logging.error(f"Dialoglar alınırken genel hata: {e}", exc_info=True)

    logging.info(f"{processed_dialogs} dialog işlendi, dinlenecek {added_chats} chat bulundu ({len(LISTENED_CHAT_IDS)} toplam).")


# ==============================================================================
# Real-time Message Handlers
# ==============================================================================

# --- Handler for ONLY Message Photos (when PROCESS_REALTIME_MESSAGES is True) ---
async def handle_new_message_photo_only(event: events.NewMessage.Event):
    """
    Sadece yeni gelen MESAJ FOTOĞRAFLARINI işleyen event handler.
    PROCESS_REALTIME_MESSAGES = True olduğunda kullanılır.
    """
    message = event.message
    chat_id = event.chat_id
    log_prefix = f"RealTimePhoto:Chat {chat_id}:Msg {message.id}"

    logging.debug(f"[{log_prefix}] Yeni mesaj alındı (Sadece Fotoğraf Modu): {message.text[:50] if message.text else '[Medya/Boş]'}")

    # Sadece fotoğraf içeren mesajları işle
    if message.photo:
        logging.info(f"[{log_prefix}] Fotoğraf içeren yeni mesaj bulundu.")
        # Fotoğraf boyutu kontrolü
        try:
            photo_size_bytes = getattr(message.photo.sizes[-1], 'size', 0) if message.photo.sizes else 0
            if photo_size_bytes > 1024 * 1024 * 5: # 5 MB limit
                logging.warning(f"[{log_prefix}] Fotoğraf boyutu 5MB'tan büyük ({photo_size_bytes} bytes), atlandı...")
                return # Handler'dan çık
        except Exception as size_err:
            logging.error(f"[{log_prefix}] Fotoğraf boyutu alınırken hata: {size_err}")
            pass # Devam etmeyi dene

        # İndirme kuyruğunu kontrol et (Async bekleme ile)
        while DOWNLOAD_QUEUE.full():
             logging.warning(f"[{log_prefix}] İndirme kuyruğu dolu ({DOWNLOAD_QUEUE.qsize()}/{DOWNLOAD_QUEUE.maxsize}), 0.5 saniye bekleniyor...")
             await asyncio.sleep(0.5)

        # Kuyruğa ekle
        try:
             download_task_info = {
                 "type": "message_photo",
                 "message": message,
             }
             await DOWNLOAD_QUEUE.put(download_task_info)
             logging.info(f"[{log_prefix}] Mesaj fotoğrafı indirme görevi kuyruğa eklendi.")
        except asyncio.QueueFull:
             logging.warning(f"[{log_prefix}] İndirme kuyruğu hala dolu, mesaj fotoğrafı görevi atlandı.")
        except Exception as q_err:
             logging.error(f"[{log_prefix}] İndirme kuyruğuna eklerken hata: {q_err}", exc_info=True)

# --- <<< YENİ HANDLER >>> Handler for ONLY Sender Profile Photos (when PROCESS_ONLY_SENDER_PROFILES is True) ---
async def handle_new_message_profile_only(event: events.NewMessage.Event):
    """
    Sadece yeni mesaj GÖNDEREN KULLANICILARIN PROFİL FOTOĞRAFLARINI işleyen event handler.
    PROCESS_ONLY_SENDER_PROFILES = True olduğunda kullanılır.
    """
    message = event.message
    chat_id = event.chat_id
    log_prefix = f"RealTimeProfile:Chat {chat_id}:Msg {message.id}"

    # Sadece profil fotoğrafı olan kullanıcılardan gelen mesajları işle
    if DOWNLOAD_PROFILE_PHOTOS and message.sender and isinstance(message.sender, User) and message.sender.photo:
        user = message.sender
        user_id = user.id
        photo = user.photo # UserProfilePhoto
        user_name_log = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip() or f"ID:{user_id}"

        logging.debug(f"[{log_prefix}] Yeni mesaj alındı (Sadece Profil Modu). Gönderen: {user_name_log}")

        # Daha önce işlenmiş mi kontrol et (Kısa süre içinde tekrar işlememek için)
        if user_id in PROCESSED_USER_PROFILES:
            logging.debug(f"[{log_prefix}] Kullanıcı profil fotoğrafı (ID: {user_id}) daha önce işlenmiş/kuyruğa eklenmiş, atlanıyor.")
            return # Bu mesaj için başka işlem yapma

        # Kuyruğu kontrol et
        while DOWNLOAD_QUEUE.full():
             logging.warning(f"[{log_prefix}] İndirme kuyruğu dolu ({DOWNLOAD_QUEUE.qsize()}/{DOWNLOAD_QUEUE.maxsize}), profil fotoğrafı için 0.5 saniye bekleniyor...")
             await asyncio.sleep(0.5)

        # Kuyruğa ekle
        try:
            profile_photo_task_info = {
                 "type": "user_profile_photo",
                 "user_id": user_id,
                 "user_info": user,
                 "photo": photo
            }
            await DOWNLOAD_QUEUE.put(profile_photo_task_info)

            # İşlenenler listesine ekle (Cache yönetimi)
            if len(PROCESSED_USER_PROFILES) >= MAX_PROCESSED_USER_PROFILES:
                 oldest_user_id, _ = PROCESSED_USER_PROFILES.popitem(last=False)
                 logging.debug(f"[Cache] Kullanıcı profil listesi limiti aşıldı ({MAX_PROCESSED_USER_PROFILES}). En eski ID ({oldest_user_id}) silindi.")
            PROCESSED_USER_PROFILES[user_id] = datetime.now()
            logging.info(f"[{log_prefix}] Kullanıcı profil fotoğrafı indirme görevi kuyruğa eklendi: User ID {user_id}, Name: {user_name_log}")

        except asyncio.QueueFull:
             logging.warning(f"[{log_prefix}] İndirme kuyruğu hala dolu, profil fotoğrafı görevi atlandı (User ID: {user_id})")
        except Exception as q_err:
             logging.error(f"[{log_prefix}] Profil fotoğrafı görevini indirme kuyruğuna eklerken hata (User ID: {user_id}): {q_err}", exc_info=True)
    else:
        # Kullanıcının profil fotosu yoksa veya sender User değilse debug logu basabiliriz
        sender_info = "No Sender"
        if message.sender:
            if isinstance(message.sender, User):
                 sender_info = f"User ID {message.sender.id} (No Photo)"
            else:
                 sender_info = f"Type {type(message.sender).__name__}"
        logging.debug(f"[{log_prefix}] Mesaj gönderenin işlenecek profil fotosu yok veya DOWNLOAD_PROFILE_PHOTOS kapalı. Sender: {sender_info}")


# ==============================================================================
# Main Application Logic
# ==============================================================================
async def main_telethon():
    global client, PROCESSED_USER_PROFILES
    processing_threads = []
    download_tasks = []

    try:
        # --- Client Bağlantısı ---
        if not client.is_connected():
            logging.info("Telegram Client'a bağlanılıyor...")
            # Telefon numarası veya bot token isteyebilir
            await client.connect()
            if not await client.is_user_authorized():
                logging.info("Yetkilendirme gerekli. Lütfen istemleri takip edin.")
                # Gerekirse telefon no ve kod girişi
                phone_number = input("Lütfen telefon numaranızı girin (+90...): ")
                await client.send_code_request(phone_number)
                try:
                    await client.sign_in(phone_number, input('Doğrulama kodunu girin: '))
                except telethon_errors.SessionPasswordNeededError:
                    await client.sign_in(password=input('İki adımlı doğrulama şifrenizi girin: '))
            logging.info("Telegram Client başarıyla bağlandı ve yetkilendirildi.")
        else:
            logging.info("Telegram Client zaten bağlı.")


        # --- Başlangıç Ayarları ---
        await fetch_all_chats_telethon()
        if not LISTENED_CHAT_IDS:
             logging.warning("Dinlenecek hiçbir chat bulunamadı. Çıkılıyor.")
             return

        # --- Worker Thread'leri ve Task'ları Başlat ---
        logging.info(f"{NUM_PROCESSING_WORKERS} adet işleme thread'i başlatılıyor...")
        for i in range(NUM_PROCESSING_WORKERS):
            thread = threading.Thread(
                target=process_downloaded_item_thread,
                daemon=True, # Ana program bitince thread'lerin de bitmesini sağlar
                name=f"ProcessingThread-{i+1}"
            )
            processing_threads.append(thread)
            thread.start()
            logging.info(f"İşleme thread'i {thread.name} başlatıldı.")

        logging.info(f"{NUM_DOWNLOAD_WORKERS} adet indirme işçisi (async task) başlatılıyor...")
        for i in range(NUM_DOWNLOAD_WORKERS):
            task_name = f"DownloadWorker-{i+1}"
            # İki kuyruğu da worker'a verelim
            task = asyncio.create_task(download_worker(task_name, DOWNLOAD_QUEUE, PROCESSING_QUEUE), name=task_name)
            download_tasks.append(task)
            logging.info(f"İndirme işçisi {task_name} başlatıldı.")


        # --- Çalışma Modunu Seç ve Çalıştır ---
        if PROCESS_ONLY_SENDER_PROFILES:
            # --- YENİ MOD: Sadece Gönderen Profil Fotoğrafları ---
            logging.info("*** YENİ MOD AKTİF: Sadece yeni mesaj gönderenlerin profil fotoğrafları işlenecek. ***")
            if not DOWNLOAD_PROFILE_PHOTOS:
                logging.warning("UYARI: PROCESS_ONLY_SENDER_PROFILES modu aktif ancak DOWNLOAD_PROFILE_PHOTOS kapalı!")
                # İsteğe bağlı olarak burada programı durdurabilir veya devam edebiliriz.
                # return # Veya devam etmesine izin ver (hiçbir şey yapmayacak)

            logging.info(f"Dinlenen chat ID'leri: {LISTENED_CHAT_IDS}")
            client.add_event_handler(handle_new_message_profile_only, events.NewMessage(chats=LISTENED_CHAT_IDS))
            logging.info("Sadece profil fotoğrafı işleyen event handler kaydedildi.")

            logging.info("Client yeni mesajları dinliyor (Profil Modu)... (Çıkmak için Ctrl+C)")
            await client.run_until_disconnected()
            logging.info("Client durduruldu veya bağlantı kesildi (Profil Modu).")

        elif PROCESS_REALTIME_MESSAGES:
            # --- ESKİ REAL-TIME MODU: Sadece Mesaj Fotoğrafları ---
            # (handle_new_message artık sadece fotoğrafları işliyor)
            logging.info("Gerçek zamanlı MESAJ FOTOĞRAFI işleme modu aktif.")
            logging.info(f"Dinlenen chat ID'leri: {LISTENED_CHAT_IDS}")

            # Profil foto indirme bu modda opsiyoneldi, şimdi handle_new_message_photo_only sadece mesaj fotolarını alıyor.
            # Eğer bu modda hem mesaj hem profil fotosu istenirse, orijinal handle_new_message kullanılmalı
            # ve PROCESS_REALTIME_MESSAGES ile PROCESS_ONLY_SENDER_PROFILES'in ikisi de False olmalıydı.
            # Şimdiki haliyle bu mod SADECE mesaj fotoğraflarını alacak.
            client.add_event_handler(handle_new_message_photo_only, events.NewMessage(chats=LISTENED_CHAT_IDS))
            logging.info("Sadece mesaj fotoğrafı işleyen event handler kaydedildi.")

            logging.info("Client yeni mesajları dinliyor (Mesaj Fotoğrafı Modu)... (Çıkmak için Ctrl+C)")
            await client.run_until_disconnected()
            logging.info("Client durduruldu veya bağlantı kesildi (Mesaj Fotoğrafı Modu).")

        else:
            # --- GEÇMİŞ TARAMA MODU (Değişiklik yok) ---
            logging.info("Geçmiş tarama modu aktif (Son 1 gün).")
            one_day_ago = datetime.now(tz=None) - timedelta(days=1)
            while True:
                try:
                    logging.info("Periyodik geçmiş tarama döngüsü başlıyor...")
                    active_chats = list(LISTENED_CHAT_IDS)
                    logging.info(f"{len(active_chats)} adet chat taranacak...")
                    for chat_id in active_chats:
                        if chat_id not in LISTENED_CHAT_IDS: continue
                        log_prefix = f"HistoryScan:Chat {chat_id}"
                        message_count_in_chat = 0
                        photo_queued_in_chat = 0
                        try:
                            logging.info(f"[{log_prefix}] Chat geçmişi taranıyor (Son 1 gün)...")
                            async for message in client.iter_messages(chat_id, limit=None, reverse=True):
                                message: Message
                                message_count_in_chat += 1
                                msg_date_naive = None
                                if hasattr(message, 'date') and message.date:
                                    msg_date_naive = message.date.replace(tzinfo=None) if message.date.tzinfo else message.date
                                else:
                                    logging.warning(f"[{log_prefix}] Mesajda tarih bilgisi yok (Msg ID: {message.id}). Atlanıyor.")
                                    continue
                                if msg_date_naive < one_day_ago:
                                    logging.info(f"[{log_prefix}] 1 günden eski mesajlara ulaşıldı (Msg ID: {message.id}, Date: {message.date}). Bu chat için tarama durduruluyor.")
                                    break
                                if message.photo:
                                    logging.debug(f"[{log_prefix}] Fotoğraf içeren mesaj bulundu (Msg ID: {message.id}).")
                                    photo_size_bytes = 0
                                    try:
                                        photo_size_bytes = getattr(message.photo.sizes[-1], 'size', 0) if message.photo.sizes else 0
                                    except Exception as size_err:
                                         logging.error(f"[{log_prefix}] Fotoğraf boyutu alınırken hata (Msg ID: {message.id}): {size_err}")
                                    if photo_size_bytes > 1024 * 1024 * 5:
                                        logging.warning(f"[{log_prefix}] Fotoğraf boyutu 5MB'tan büyük ({photo_size_bytes} bytes), atlandı... Msg ID: {message.id}")
                                        continue
                                    while DOWNLOAD_QUEUE.full():
                                         logging.warning(f"[{log_prefix}] İndirme kuyruğu dolu ({DOWNLOAD_QUEUE.qsize()}/{DOWNLOAD_QUEUE.maxsize}), 0.5 saniye bekleniyor...")
                                         await asyncio.sleep(0.5)
                                    try:
                                         download_task_info = {
                                             "type": "message_photo",
                                             "message": message,
                                         }
                                         await DOWNLOAD_QUEUE.put(download_task_info)
                                         photo_queued_in_chat += 1
                                         logging.info(f"[{log_prefix}] Mesaj fotoğrafı indirme görevi kuyruğa eklendi (Msg ID: {message.id})")
                                    except asyncio.QueueFull:
                                         logging.warning(f"[{log_prefix}] İndirme kuyruğu hala dolu, mesaj fotoğrafı görevi atlandı (Msg ID: {message.id})")
                                    except Exception as q_err:
                                         logging.error(f"[{log_prefix}] İndirme kuyruğuna eklerken hata (Msg ID: {message.id}): {q_err}", exc_info=True)
                        except telethon_errors.ChannelPrivateError:
                             logging.warning(f"[{log_prefix}] Chat'e erişilemiyor (Private?). Bu chat listeden çıkarılabilir.")
                             if chat_id in LISTENED_CHAT_IDS: LISTENED_CHAT_IDS.remove(chat_id)
                        except telethon_errors.ChatAdminRequiredError:
                             logging.warning(f"[{log_prefix}] Chat geçmişini okumak için admin yetkisi gerekli. Atlanıyor.")
                        except telethon_errors.FloodWaitError as e:
                             wait_time = e.seconds + 1
                             logging.warning(f"[{log_prefix}] FloodWait hatası: {wait_time} saniye bekleniyor...")
                             await asyncio.sleep(wait_time)
                        except ValueError as ve:
                             if "Could not find the input entity for" in str(ve) or "No user has" in str(ve):
                                  logging.error(f"[{log_prefix}] Chat bulunamadı veya erişilemiyor: {ve}. Bu chat listeden çıkarılıyor.")
                                  if chat_id in LISTENED_CHAT_IDS: LISTENED_CHAT_IDS.remove(chat_id)
                             else:
                                  logging.error(f"[{log_prefix}] Chat işlenirken ValueError: {ve}", exc_info=True)
                        except Exception as e:
                             logging.error(f"[{log_prefix}] Chat işlenirken bilinmeyen hata: {type(e).__name__}: {e}", exc_info=True)
                             logging.debug(traceback.format_exc())
                        finally:
                             logging.info(f"[{log_prefix}] Tarama tamamlandı. Kontrol edilen mesaj sayısı: {message_count_in_chat}, Kuyruğa eklenen fotoğraf: {photo_queued_in_chat}")
                             await asyncio.sleep(1)
                    logging.info(f"Tüm ({len(LISTENED_CHAT_IDS)}) chatlerin son 1 günlük mesajları tarandı. 1 saat bekleniyor...")
                    await asyncio.sleep(3600)
                    one_day_ago = datetime.now(tz=None) - timedelta(days=1)
                except Exception as hist_err:
                     logging.critical(f"Ana mesaj döngüsünde (geçmiş tarama) kritik hata: {type(hist_err).__name__}: {hist_err}", exc_info=True)
                     await asyncio.sleep(60)


    except KeyboardInterrupt:
        logging.info("Kullanıcı tarafından durduruldu (KeyboardInterrupt).")
    except Exception as e:
        logging.critical(f"Ana başlatma/çalıştırma sırasında kritik hata: {str(e)}")
        logging.debug(traceback.format_exc())
    finally:
        logging.info("Program sonlandırılıyor...")
        # --- Worker'ları Durdur ---
        if download_tasks:
             logging.info("İndirme işçileri durduruluyor...")
             try:
                 for _ in range(len(download_tasks)):
                      try:
                           DOWNLOAD_QUEUE.put_nowait(None)
                      except asyncio.QueueFull:
                           logging.warning("İndirme kuyruğu durdurma sinyali gönderilirken dolu.")
                      except Exception as put_err:
                           logging.error(f"İndirme kuyruğuna None eklerken hata: {put_err}")
                 await asyncio.gather(*download_tasks, return_exceptions=True)
                 logging.info("Tüm indirme işçileri durduruldu (veya bitmeleri beklendi).")
             except asyncio.CancelledError:
                  logging.warning("İndirme işçileri beklenirken iptal edildi.")
             except Exception as dw_stop_err:
                  logging.error(f"İndirme işçilerini durdururken hata: {dw_stop_err}", exc_info=True)
        logging.info("İşleme thread'leri durduruluyor...")
        for _ in processing_threads:
             try:
                 PROCESSING_QUEUE.put(None, block=False)
             except queue.Full:
                  logging.warning("İşleme kuyruğu durdurma sinyali gönderilirken dolu.")
             except Exception as put_err:
                  logging.error(f"İşleme kuyruğuna None eklerken hata: {put_err}")
        for thread in processing_threads:
             thread.join(timeout=10.0)
             if thread.is_alive():
                 logging.warning(f"İşleme thread'i {thread.name} zamanında durmadı.")
             logging.info("Tüm işleme thread'leri durduruldu (veya zaman aşımına uğradı).")
        # --- Client Bağlantısını Kes ---
        if client and client.is_connected():
            logging.info("Telegram Client bağlantısı kesiliyor...")
            await client.disconnect()
            logging.info("Telegram Client bağlantısı kesildi.")
        logging.info("Program başarıyla sonlandırıldı.")


if __name__ == "__main__":
    # Ana asenkron fonksiyonu çalıştır
    try:
        # <<< Modların Önceliği >>>
        # Eğer hem PROCESS_ONLY_SENDER_PROFILES hem de PROCESS_REALTIME_MESSAGES True ise,
        # PROCESS_ONLY_SENDER_PROFILES öncelikli olacak şekilde ayarlandı.
        # İkisinin de True olması durumunda bir uyarı verilebilir:
        if PROCESS_ONLY_SENDER_PROFILES and PROCESS_REALTIME_MESSAGES:
             logging.warning("UYARI: Hem 'PROCESS_ONLY_SENDER_PROFILES' hem de 'PROCESS_REALTIME_MESSAGES' True olarak ayarlanmış.")
             logging.warning("Öncelik 'PROCESS_ONLY_SENDER_PROFILES' moduna verilecek.")
             PROCESS_REALTIME_MESSAGES = False # Diğerini devre dışı bırak

        # Geçmiş tarama modu (ikisi de False ise) zaten else bloğunda çalışıyor.

        asyncio.run(main_telethon())
    except KeyboardInterrupt:
         logging.info("Program asyncio döngüsü dışında durduruldu.")
