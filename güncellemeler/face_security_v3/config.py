"""
Merkezi yapılandırma modülü.
Tüm ayarlar .env dosyasından veya ortam değişkenlerinden yüklenir.
Kaynak koda gizli bilgi yazılmaz.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Telegram ---
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
SEND_TELEGRAM: bool = bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)

# --- Dizin Yolları ---
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "database")
KNOWN_PATH: str = os.getenv("KNOWN_PATH", "snapshots/known")
UNKNOWN_PATH: str = os.getenv("UNKNOWN_PATH", "snapshots/unknown")
LOG_DIR: str = os.getenv("LOG_DIR", "logs")

# Gerekli dizinleri oluştur (kırık sembolik bağları temizle)
for _dir in [DATABASE_PATH, KNOWN_PATH, UNKNOWN_PATH, LOG_DIR]:
    _p = Path(_dir)
    # Hem dizinin kendisi hem üst dizinleri kırık sembolik bağ olabilir
    for _part in [_p, *_p.parents]:
        if _part.is_symlink() and not _part.exists():
            _part.unlink()  # Hedefi olmayan bozuk sembolik bağı kaldır
    _p.mkdir(parents=True, exist_ok=True)

# --- Tespit Parametreleri ---
THRESHOLD: float = float(os.getenv("THRESHOLD", "0.45"))
INFERENCE_FPS: int = int(os.getenv("INFERENCE_FPS", "4"))
SNAPSHOT_COOLDOWN: int = int(os.getenv("SNAPSHOT_COOLDOWN", "20"))
PATROL_SCAN_SECONDS: int = int(os.getenv("PATROL_SCAN_SECONDS", "10"))
PATROL_HOLD_SECONDS: int = int(os.getenv("PATROL_HOLD_SECONDS", "20"))
LOG_THROTTLE_SECONDS: int = int(os.getenv("LOG_THROTTLE_SECONDS", "30"))

# --- Temizlik ---
SNAPSHOT_MAX_AGE_DAYS: int = int(os.getenv("SNAPSHOT_MAX_AGE_DAYS", "7"))
SNAPSHOT_MAX_FILES: int = int(os.getenv("SNAPSHOT_MAX_FILES", "500"))

# --- Ekran ---
DISPLAY_W: int = 900
DISPLAY_H: int = 500

# --- Kamera Adları ---
CAMERA_NAMES: dict[int, str] = {
    1: "1-Giriş 211",        2: "2-Plaka Tanıma",      3: "3-Toplantı Odası",
    4: "4-Ofis 2",           5: "5-Ofis 1",             6: "6-Bilgi İşlem",
    7: "7-Elektrik Üst",     8: "8-Soyunma O",          9: "9-C Blok Giriş İç",
    10: "10-Yemekhane",      11: "11-P. Otopark",        12: "12-Giriş Otopark",
    13: "13-Eski Ofis",      14: "14-Dış Saha 3",        15: "15-Personel Girişi",
    16: "16-C Blok Giriş Dış", 17: "17-Giriş Kapısı",  18: "18-Dış Saha 2",
    19: "19-Depo Girişi",    20: "20-Depo",              21: "21-Dış Saha Tankpalet",
    22: "22-Dış Saha 1",     23: "23-Elektrik",          24: "24-Hidrolik",
    25: "25-Güvenlik",
}

# --- Plaka Tanıma ---
PLATE_CAM_URL: str                = os.getenv("PLATE_CAM_URL", "")
PLATE_VOTE_COUNT: int             = int(os.getenv("PLATE_VOTE_COUNT",           "3"))
PLATE_VOTE_THRESHOLD: int         = int(os.getenv("PLATE_VOTE_THRESHOLD",       "2"))
PLATE_DUPLICATE_SECONDS: int      = int(os.getenv("PLATE_DUPLICATE_SECONDS",   "10"))
PLATE_INFERENCE_INTERVAL: float   = float(os.getenv("PLATE_INFERENCE_INTERVAL", "1.5"))
# YOLO modelleri:
#   PLATE_YOLO_CONF       — COCO/vehicle gate confidence eşiği
#   PLATE_DETECTOR_CONF   — plaka detector confidence eşiği (ayrı tunelable)
#   USE_CONTOUR_FALLBACK  — plaka detector 0 tespit verirse eski kontur akışına düşülsün mü
PLATE_YOLO_MODEL: str             = os.getenv("PLATE_YOLO_MODEL", "")
PLATE_YOLO_CONF: float            = float(os.getenv("PLATE_YOLO_CONF",        "0.35"))
PLATE_DETECTOR_CONF: float        = float(os.getenv("PLATE_DETECTOR_CONF",    "0.25"))
USE_CONTOUR_FALLBACK: bool        = os.getenv("USE_CONTOUR_FALLBACK", "false").lower() == "true"

# --- Kamera URL'leri (.env'den yüklenir) ---
CAMERAS: dict[int, str] = {}
for _i in range(1, 26):
    _url = os.getenv(f"CAM_{_i:02d}_URL", "")
    if _url:
        CAMERAS[_i] = _url
