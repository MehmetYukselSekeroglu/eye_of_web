#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import traceback
import argparse
import flask
import gc
import signal
import sys
import threading
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

# Gerekli kütüphaneleri import edelim (varsayılan)
try:
    import onnxruntime  # CUDA kontrolü için

    ONNXRUNTIME_AVAILABLE = True
except ImportError:
    ONNXRUNTIME_AVAILABLE = False
    print("Uyarı: 'onnxruntime' kütüphanesi bulunamadı. CUDA kontrolü yapılamayacak.")
try:
    import numba

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    print("Uyarı: 'numba' kütüphanesi bulunamadı. CPU hızlandırma kullanılamayacak.")
# YENİ: PyTorch import ve CUDA kontrolü
try:
    import torch

    PYTORCH_AVAILABLE = True
    # PyTorch ile gerçek CUDA kullanılabilirliğini kontrol et
    PYTORCH_CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    PYTORCH_AVAILABLE = False
    PYTORCH_CUDA_AVAILABLE = False
    print(
        "Uyarı: 'torch' kütüphanesi bulunamadı. PyTorch CUDA kontrolü ve benzerlik hesaplama kullanılamayacak."
    )

# Production server imports
try:
    import gunicorn
    from gunicorn.app.base import BaseApplication

    GUNICORN_AVAILABLE = True
except ImportError:
    GUNICORN_AVAILABLE = False
    print("Uyarı: 'gunicorn' kütüphanesi bulunamadı. Development server kullanılacak.")

from app import create_app
from lib.load_config import load_config_from_file
from lib.init_insightface import initilate_insightface
from lib.env import USE_CUDA as ENV_USE_CUDA
from lib.env import ALLOWED_HOSTS  # <<< ALLOWED_HOSTS import edildi
import lib.env as env_config  # Import env constants
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
    g,
    jsonify,
    send_file,
)
import bcrypt  # bcrypt import edin
from lib.database_tools import DatabaseTools  # Veritabanı işlemleri için

# Global app instance for signal handling
app_instance = None


# Memory cleanup function
def cleanup_memory():
    """Bellek temizleme fonksiyonu"""
    try:
        gc.collect()
        if PYTORCH_AVAILABLE and torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception as e:
        print(f"Bellek temizleme hatası: {e}")


# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    """Graceful shutdown için signal handler"""
    print(f"\n{datetime.now()}: Shutdown signal received ({sig})")
    cleanup_memory()
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# Setup logging
def setup_logging():
    """Production-level logging kurulumu"""
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # File handler with rotation
    file_handler = RotatingFileHandler(
        "logs/eyeofweb.log", maxBytes=10240000, backupCount=10  # 10MB
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        )
    )
    file_handler.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Configure root logger
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

    return logging.getLogger(__name__)


# Gunicorn WSGI Application
class GunicornApplication(BaseApplication):
    """Custom Gunicorn application"""

    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


argparser = argparse.ArgumentParser(
    description=f"{env_config.VENDOR_NAME} - {env_config.APP_NAME}"
)  # Use constants
argparser.add_argument(
    "--config", type=str, required=False, help="Yapılandırma dosyasının yolu."
)
argparser.add_argument(
    "--mode",
    type=str,
    choices=["development", "production"],
    default="production",
    help="Çalıştırma modu",
)
argparser.add_argument("--workers", type=int, default=4, help="Gunicorn worker sayısı")
argparser.add_argument(
    "--threads", type=int, default=2, help="Worker başına thread sayısı"
)
argparser.add_argument(
    "--timeout", type=int, default=120, help="Request timeout (saniye)"
)
args = argparser.parse_args()

# Setup logging
logger = setup_logging()

if args.config and os.path.exists(args.config) and os.path.isfile(args.config):
    CONFIG = load_config_from_file(args.config)
else:
    CONFIG = load_config_from_file()

# Ortam değişkenlerini ayarla
os.environ["FLASK_ENV"] = args.mode

print("-----------------------------------")
print(
    f"{env_config.APP_TITLE} Başlatılıyor - {args.mode.upper()} Mode"
)  # Use constants
print("-----------------------------------")

# --- Benzerlik Hesaplama Backend Belirleme (GLOBAL SCOPE) ---
# Gerçek CUDA kullanımı ENV_USE_CUDA ve PyTorch CUDA durumuna bağlı
actual_use_cuda = ENV_USE_CUDA and PYTORCH_AVAILABLE and PYTORCH_CUDA_AVAILABLE
backend_info_global = (
    "CUDA (PyTorch)"
    if actual_use_cuda
    else "CPU (Numba)" if NUMBA_AVAILABLE else "CPU (NumPy)"
)

print("-" * 20)
print(f"(Global Check) ENV_USE_CUDA: {ENV_USE_CUDA}")
print(f"(Global Check) PyTorch CUDA Available: {PYTORCH_CUDA_AVAILABLE}")
print(f"==> (Global Check) Benzerlik Hesaplama Backend: {backend_info_global}")
print("-" * 20)


# Helper function to create the initial admin user
def _setup_initial_admin_user(
    db_conn_config: dict, admin_username: str, admin_plain_password: str
):
    """Checks for and creates the initial admin user if not present."""
    if not admin_username or not admin_plain_password:
        logger.warning(
            "Yapılandırmada ilk admin kullanıcı adı veya parolası eksik. Admin oluşturulamadı."
        )
        return

    db_tools = None
    conn = None
    cursor = None
    try:
        db_tools = DatabaseTools(db_conn_config)
        conn = db_tools.connect()
        if not conn:
            logger.error(
                "İlk admin kullanıcısı kurulumu için veritabanı bağlantısı kurulamadı."
            )
            return
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE username = %s", (admin_username,))
        if cursor.fetchone():
            logger.info(f"Admin kullanıcısı '{admin_username}' zaten mevcut.")
            return

        # Parolayı bcrypt ile hash'le
        hashed_password = bcrypt.hashpw(
            admin_plain_password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        insert_query = """
        INSERT INTO users (username, password, name, email, is_active, is_admin, is_owner, is_demo)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        # email için varsayılan bir değer (örneğin admin_username + '@example.com') veya None ekleyebilirsiniz.
        # users.sql şemanızda email UNIQUE ama NULL olabilir.
        admin_email = f"{admin_username}@example.local"  # Geçici bir email veya None
        cursor.execute(
            insert_query,
            (
                admin_username,
                hashed_password,
                admin_username,
                admin_email,  # email
                True,  # is_active
                True,  # is_admin
                True,  # is_owner
                False,  # is_demo
            ),
        )
        conn.commit()
        logger.info(
            f"İlk admin kullanıcısı '{admin_username}' (bcrypt hashli) oluşturuldu."
        )

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception as rb_err:
                logger.error(f"Rollback sırasında hata: {rb_err}")
        logger.error(f"İlk admin kullanıcısı oluşturulurken hata oluştu: {e}")
        traceback.print_exc()
    finally:
        if db_tools and conn:
            db_tools.releaseConnection(conn, cursor)


# Memory monitoring thread
def memory_monitor():
    """Bellek kullanımını izleyen thread"""
    import psutil

    process = psutil.Process(os.getpid())

    while True:
        try:
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()

            # Bellek kullanımı %80'i geçerse temizlik yap
            if memory_percent > 80:
                logger.warning(f"Yüksek bellek kullanımı: {memory_percent:.2f}%")
                cleanup_memory()

            time.sleep(60)  # Her dakika kontrol et
        except Exception as e:
            logger.error(f"Bellek izleme hatası: {e}")
            time.sleep(60)


# Flask uygulamasını başlatan fonksiyon
def start_flask_app(config_file: str):
    global app_instance

    # Config yükleme - load_config_from_file [success: bool, data: dict|str] döndürür
    main_conf_tuple = load_config_from_file(config_file)

    # Config dosyası yoksa veya yüklenemezse environment variable'lardan oku
    if main_conf_tuple is None or not main_conf_tuple[0]:
        logger.warning(
            f"Config dosyası yüklenemedi, environment variable'lardan okunuyor..."
        )
        # Environment variable'lardan database config oluştur
        db_connection_config = {
            "host": os.environ.get("DB_HOST", "localhost"),
            "port": os.environ.get("DB_PORT", "5432"),
            "user": os.environ.get("DB_USER", "postgres"),
            "password": os.environ.get("DB_PASSWORD", "postgres"),
            "database": os.environ.get("DB_NAME", "EyeOfWeb"),
        }
        main_settings = {
            "database_config": db_connection_config,
            "initial_admin_user": {
                "username": os.environ.get("ADMIN_USERNAME", "admin"),
                "password": os.environ.get("ADMIN_PASSWORD", "admin123"),
            },
        }
    else:
        # Config dosyası başarıyla yüklendi
        main_settings = main_conf_tuple[1]
        db_connection_config = main_settings.get(
            "database_config",
            {
                "host": os.environ.get("DB_HOST", "localhost"),
                "port": os.environ.get("DB_PORT", "5432"),
                "user": os.environ.get("DB_USER", "postgres"),
                "password": os.environ.get("DB_PASSWORD", "postgres"),
                "database": os.environ.get("DB_NAME", "EyeOfWeb"),
            },
        )

    # --- ONNX Runtime Provider Seçimi (InsightFace için) ---
    insightface_providers = ["CPUExecutionProvider"]  # InsightFace için varsayılan CPU
    onnx_cuda_provider_available = False
    if ONNXRUNTIME_AVAILABLE:
        available_providers = onnxruntime.get_available_providers()
        logger.info(f"Kullanılabilir ONNX Runtime Sağlayıcıları: {available_providers}")
        if "CUDAExecutionProvider" in available_providers:
            onnx_cuda_provider_available = True

        # InsightFace provider'ları ENV_USE_CUDA ve ONNX provider durumuna göre ayarla
        if ENV_USE_CUDA and onnx_cuda_provider_available:
            logger.info(
                "InsightFace için ONNX CUDAExecutionProvider bulundu ve ENV_USE_CUDA=True."
            )
            insightface_providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        elif ENV_USE_CUDA:
            logger.warning(
                "InsightFace için ENV_USE_CUDA=True ancak ONNX CUDAExecutionProvider bulunamadı. InsightFace CPU kullanacak."
            )
        else:
            logger.info(
                "InsightFace için ENV_USE_CUDA=False. InsightFace CPU kullanacak."
            )
    else:
        logger.warning(
            "onnxruntime kütüphanesi bulunamadı. InsightFace sadece CPU kullanabilir."
        )

    logger.info(
        f"InsightFace için Seçilen ONNX Runtime Sağlayıcıları: {insightface_providers}"
    )

    # InsightFace modelini yükle (provider listesini göndererek)
    try:
        insightface_app = initilate_insightface(
            main_conf=main_settings,  # main_settings dictionary kullanılıyor
            providers=insightface_providers,  # <<< InsightFace providerları gönderiliyor
        )
        if insightface_app is None:
            logger.error("InsightFace başlatılamadı.")
            return  # Uygulamayı başlatma
        else:
            logger.info("InsightFace başarıyla yüklendi.")
            print("-----------------------------------")

    except Exception as insight_err:
        logger.error(f"InsightFace başlatılırken kritik hata: {insight_err}")
        traceback.print_exc()
        return  # Uygulamayı başlatma

    # Flask uygulamasını oluştur
    app: flask.Flask = create_app(connection_config=db_connection_config)
    app_instance = app

    # InsightFace uygulamasını Flask app context'ine ekle (başarılıysa)
    if insightface_app:
        app.face_app = insightface_app

    # Kullanılan backend bilgisini Flask config'e ekle (Globaldeki değerleri kullan)
    app.config["BACKEND_INFO"] = backend_info_global
    app.config["USE_CUDA"] = actual_use_cuda  # <<< Globaldeki değeri kullan
    app.config["NUMBA_AVAILABLE"] = NUMBA_AVAILABLE  # Numba durumu değişmez
    app.config["PYTORCH_AVAILABLE"] = PYTORCH_AVAILABLE  # PyTorch durumunu da ekleyelim

    # Production optimizations
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000  # 1 year cache for static files
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size
    app.config["PERMANENT_SESSION_LIFETIME"] = 3600  # 1 hour session timeout

    # Request timeout and error handling
    @app.before_request
    def before_request():
        g.start_time = time.time()

    @app.after_request
    def after_request(response):
        # Request süresini logla
        if hasattr(g, "start_time"):
            duration = time.time() - g.start_time
            if duration > 10:  # 10 saniyeden uzun istekleri logla
                logger.warning(f"Uzun istek: {request.endpoint} - {duration:.2f}s")

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        cleanup_memory()  # Hata durumunda bellek temizle
        return "Internal Server Error", 500

    @app.errorhandler(404)
    def not_found(error):
        return "Not Found", 404

    @app.teardown_request
    def teardown_request(exception):
        # Her request sonrası hafif bellek temizliği
        if exception:
            logger.error(f"Request exception: {exception}")

    # --- Host Kontrolü ---
    if ALLOWED_HOSTS:  # Sadece liste boş değilse kontrol et

        @app.before_request
        def check_host():
            # localhost ve 127.0.0.1 için özel durum (Flask development server'ı için)
            # veya request.host doğrudan ALLOWED_HOSTS içinde varsa
            host = request.host.split(":")[0]  # Port numarasını kaldır
            if not (
                host == "localhost" or host == "127.0.0.1" or host in ALLOWED_HOSTS
            ):
                logger.warning(f"İzin verilmeyen host'tan istek geldi: {request.host}")
                abort(403)  # Forbidden

    # --- Host Kontrolü Bitti ---

    # --- YENİ: İlk Admin Kullanıcısını Ayarla ---
    admin_user_config = main_settings.get("initial_admin_user")
    if admin_user_config:
        admin_username = admin_user_config.get("username")
        admin_password = admin_user_config.get("password")
        if admin_username and admin_password:
            logger.info("İlk admin kullanıcısı ayarlanıyor...")
            # Pass the specific database connection config dictionary
            _setup_initial_admin_user(
                db_connection_config, admin_username, admin_password
            )
        else:
            logger.warning(
                "Yapılandırmada 'initial_admin_user' için kullanıcı adı veya parola eksik."
            )
    else:
        logger.warning(
            "Yapılandırmada 'initial_admin_user' bölümü bulunamadı. Admin oluşturulamayacak."
        )
    # --- Admin Kurulumu Bitti ---

    # Start memory monitoring thread
    if args.mode == "production":
        try:
            import psutil

            monitor_thread = threading.Thread(target=memory_monitor, daemon=True)
            monitor_thread.start()
            logger.info("Bellek izleme thread'i başlatıldı")
        except ImportError:
            logger.warning("psutil kütüphanesi bulunamadı. Bellek izleme devre dışı.")

    # Flask app çalıştırma kısmı
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", 5000))

    logger.info(f"Web uygulaması başlatılıyor: http://{host}:{port}")
    logger.info(
        f"Kullanılacak Hesaplama Backend: {app.config.get('BACKEND_INFO', 'Bilinmiyor')}"
    )
    logger.info(f"Çalıştırma Modu: {args.mode}")
    logger.info(f"Sağlayan: {env_config.VENDOR_NAME}")
    print("-----------------------------------")

    # Production mode için Gunicorn kullan
    if args.mode == "production" and GUNICORN_AVAILABLE:
        options = {
            "bind": f"{host}:{port}",
            "workers": args.workers,
            "threads": args.threads,
            "timeout": args.timeout,
            "keepalive": 2,
            "max_requests": 1000,  # Worker restart after 1000 requests
            "max_requests_jitter": 100,
            "preload_app": True,
            "worker_class": "gthread",
            "worker_connections": 1000,
            "backlog": 2048,
            "access_log_format": '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s',
            "accesslog": "logs/access.log",
            "errorlog": "logs/error.log",
            "loglevel": "info",
            "capture_output": True,
            "enable_stdio_inheritance": True,
        }

        # SSL için gerekirse
        if os.path.exists("certs/cert.pem") and os.path.exists("certs/key.pem"):
            options.update(
                {
                    "keyfile": "certs/key.pem",
                    "certfile": "certs/cert.pem",
                    "ssl_version": 2,  # TLSv1_2
                }
            )
            logger.info("SSL sertifikaları bulundu ve Gunicorn'e eklendi")

        logger.info(
            f"Gunicorn ile başlatılıyor: {args.workers} worker, {args.threads} threads"
        )
        GunicornApplication(app, options).run()

    else:
        # Development mode veya Gunicorn yoksa Flask development server
        if args.mode == "production":
            logger.warning(
                "Production mode ama Gunicorn bulunamadı. Development server kullanılıyor!"
            )

        ssl_context = None
        if os.path.exists("certs/cert.pem") and os.path.exists("certs/key.pem"):
            ssl_context = ("certs/cert.pem", "certs/key.pem")

        app.run(
            host=host,
            port=port,
            debug=(args.mode == "development"),
            threaded=True,  # Threading etkinleştir
            ssl_context=ssl_context,
        )


# <<< YENİ BAŞLATMA ŞEKLİ >>>
if __name__ == "__main__":
    config_path_arg = args.config if args.config else "config/config.json"
    start_flask_app(config_path_arg)
