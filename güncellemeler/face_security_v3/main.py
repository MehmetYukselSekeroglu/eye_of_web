"""
Face Security v3 — Tkinter Entry Point (DEPRECATED — kullanmayın)

⚠️  TKINTER ARAYÜZÜ İPTAL EDİLDİ.
EyeOfWeb dashboard entegrasyonu için yeni giriş noktası: `web_app.py`
(Flask) — http://127.0.0.1:5007/ üzerinden tarayıcıda çalışır.

Bu dosya tarihsel referans / acil-fallback amaçlı korunmaktadır;
`launch.sh` artık `web_app.py`'i çağırıyor. Eski davranışa dönmek
gerekirse `launch.sh` içindeki son satırı manuel değiştirin.

Başlatma sırası (eski Tkinter modu):
  1. PIN doğrulama
  2. Model yükleme (InsightFace + embedding önbelleği)
  3. Snapshot temizleme
  4. Telegram bot başlatma
  5. Ana Tkinter UI başlatma
"""
import logging
import queue
import sys
from pathlib import Path
from tkinter import Tk, messagebox

# OpenCL process-wide disable — AMD Radeon RX 580 driver bug workaround.
# cv2.ocl.setUseOpenCL() thread-local olduğu için tek başına yetmez.
# launch.sh bunu zaten set eder; fail-safe olarak burada da koruyoruz.
# cv2 import'u env var set edildikten SONRA gelmeli.
import os
os.environ.setdefault("OPENCV_OPENCL_RUNTIME", "disabled")
import cv2

import config
from auth.auth_manager import AuthManager
from camera.camera_manager import CameraManager
from camera.stream_handler import StreamHandler
from database.db_manager import DatabaseManager
from detection.embedding_cache import EmbeddingCache
from detection.face_processor import FaceProcessor
from notifications.telegram_bot import TelegramBot
from ui.security_panel_ui import SecurityPanelApp
from utils.snapshot_cleaner import SnapshotCleaner

# ── Loglama yapılandırması ────────────────────────────────────────────────────
_log_dir = Path(__file__).parent / "logs"
_log_dir.mkdir(exist_ok=True)
_log_file = _log_dir / "ocr_debug.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_log_file, mode='a', encoding='utf-8'),
    ],
)
logger = logging.getLogger("main")


def _init_opencl() -> None:
    """
    OpenCL devre dışı — AMD Radeon RX 580 driver bug workaround.

    cv2 operasyonları CL_INVALID_WORK_GROUP_SIZE hatası veriyor,
    pipeline başına 13+ saniye gecikme oluşuyor. CPU fallback'e
    zorla. Driver güncellenirse setUseOpenCL(True)'a revert edilebilir.
    """
    cv2.ocl.setUseOpenCL(False)
    logger.info("OpenCL devre dışı — CPU mode (AMD driver bug workaround).")


def main() -> None:
    # ── 0. OpenCL GPU hızlandırma ────────────────────────────────────────────
    _init_opencl()

    # ── 1. PIN Doğrulama (kendi Tk penceresiyle, ana pencereden bağımsız) ─────
    auth = AuthManager()
    logger.info("PIN doğrulama ekranı açılıyor...")

    if not auth.show_login_dialog():
        logger.warning("Giriş iptal edildi veya PIN hatalı.")
        sys.exit(1)

    logger.info("Giriş başarılı.")

    # ── 2. Ana Tkinter penceresi (PIN onayından sonra oluştur) ────────────────
    root = Tk()

    # ── 3. Model yükleme ─────────────────────────────────────────────────────
    logger.info("InsightFace modeli yükleniyor...")
    face_processor = FaceProcessor(model_name="buffalo_s", det_size=(640, 640))

    logger.info("Embedding önbelleği derleniyor...")
    embedding_cache = EmbeddingCache(
        db_path=config.DATABASE_PATH,
        face_app=face_processor.app,
    )
    embeddings = embedding_cache.build()
    face_processor.load_embeddings(embeddings)
    logger.info("Veritabanı hazır: %d kişi", len(embeddings))

    # ── 4. Snapshot temizleme ─────────────────────────────────────────────────
    cleaner = SnapshotCleaner(
        max_age_days=config.SNAPSHOT_MAX_AGE_DAYS,
        max_files=config.SNAPSHOT_MAX_FILES,
    )
    deleted = cleaner.clean_all(config.KNOWN_PATH, config.UNKNOWN_PATH)
    if deleted:
        logger.info("Temizlik: %d eski snapshot silindi.", deleted)

    # ── 5. Kuyruklar ─────────────────────────────────────────────────────────
    img_queue: queue.Queue = queue.Queue(maxsize=2)
    result_queue: queue.Queue = queue.Queue(maxsize=20)

    # ── 6. Kamera & Veritabanı ───────────────────────────────────────────────
    stream = StreamHandler(
        face_processor=face_processor,
        img_queue=img_queue,
        result_queue=result_queue,
    )
    cam_manager = CameraManager(stream_handler=stream)

    db_manager = DatabaseManager(
        db_path=config.DATABASE_PATH,
        face_processor=face_processor,
        embedding_cache=embedding_cache,
    )
    # DatabaseManager içinde face_processor referansı için geçici bağlantı
    db_manager.db_manager = db_manager  # type: ignore[attr-defined]

    # ── 7. Telegram Bot ──────────────────────────────────────────────────────
    telegram: TelegramBot | None = None
    if config.SEND_TELEGRAM:
        try:
            telegram = TelegramBot(
                token=config.TELEGRAM_TOKEN,
                chat_id=config.TELEGRAM_CHAT_ID,
            )
            telegram.start_polling()
            logger.info("Telegram bot başlatıldı.")
        except ValueError as e:
            logger.warning("Telegram başlatılamadı: %s", e)
    else:
        logger.warning(
            "Telegram devre dışı. .env dosyasında TELEGRAM_BOT_TOKEN ve "
            "TELEGRAM_CHAT_ID tanımlanmamış."
        )

    # ── 8. Ana UI ────────────────────────────────────────────────────────────
    app = SecurityPanelApp(
        root=root,
        auth=auth,
        cam_manager=cam_manager,
        db_manager=db_manager,
        telegram=telegram,
        result_queue=result_queue,
        img_queue=img_queue,
    )

    root.after(1000, app.auto_start)
    logger.info("Arayüz başlatıldı. Hazır.")

    root.mainloop()


if __name__ == "__main__":
    main()
