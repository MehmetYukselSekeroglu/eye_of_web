# AUTO-GENERATED LAUNCHER — realtime_search_camera_ornek.py'in türevi.
# Orijinal dosya DOKUNULMADI. Bu launcher CLI'dan / env'den
# `--cam-id N` veya `EOW_CAMERA_URL` ile çağrılır; başka her şey
# orijinalle birebir aynıdır (Milvus, PostgreSQL, PyQt5 UI, Cyber HUD
# tüm özellikleri korunur).
#
# Çağırma örnekleri:
#   python3 realtime_search_camera_launcher.py --cam-id 7
#   EOW_CAMERA_URL="rtsp://..." python3 realtime_search_camera_launcher.py
#   EOW_CAMERA_ID=12 EOW_CAMERA_URL="rtsp://..." python3 realtime_search_camera_launcher.py
#
# Express backend (port 5006) `/api/control/launch-camera/:id` endpoint'i
# bu dosyayı `cd src && source WorkEnv && python3 launcher.py --cam-id N`
# komutuyla başlatır.
# ─────────────────────────────────────────────────────────────────────────
import argparse as _eow_argparse
import os as _eow_os
import sys as _eow_sys
from pathlib import Path as _EowPath

def _eow_resolve_camera_url():
    """CLI args + env + .env dosyasından kamera URL'ini bulur."""
    _p = _eow_argparse.ArgumentParser(add_help=False)
    _p.add_argument("--cam-id", type=int, default=None)
    _p.add_argument("--rtsp-url", type=str, default=None)
    # Bilinmeyen argv'ler PyQt'a geçer
    _known, _rest = _p.parse_known_args()
    _eow_sys.argv = [_eow_sys.argv[0]] + _rest

    # Önce explicit URL
    url = _known.rtsp_url or _eow_os.environ.get("EOW_CAMERA_URL")
    cam_id = _known.cam_id
    if cam_id is None:
        _env_id = _eow_os.environ.get("EOW_CAMERA_ID")
        if _env_id and _env_id.isdigit():
            cam_id = int(_env_id)

    # URL yoksa cam_id'den .env'leri tarayarak çöz
    if not url and cam_id is not None:
        candidates = [
            _EowPath(__file__).parent / ".env",
            _EowPath(__file__).parent.parent / "güncellemeler" / "face_security_v3" / ".env",
            _EowPath.home() / ".env",
        ]
        for env_path in candidates:
            if env_path.exists():
                try:
                    for line in env_path.read_text(encoding="utf-8").splitlines():
                        if line.startswith(f"CAM_{cam_id:02d}_URL="):
                            url = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
                except Exception:
                    continue
                if url:
                    break

    if not url:
        print(f"[Launcher][ERR] cam_id={cam_id} için URL bulunamadı.", file=_eow_sys.stderr)
        print("Çözüm: --rtsp-url ile direkt URL ver veya .env'de CAM_NN_URL tanımla.", file=_eow_sys.stderr)
        _eow_sys.exit(2)

    print(f"[Launcher] cam_id={cam_id}  url={url[:60]}...")
    _eow_os.environ["EOW_CAMERA_URL"] = url
    if cam_id is not None:
        _eow_os.environ["EOW_CAMERA_ID"] = str(cam_id)
    return url, cam_id

_EOW_RESOLVED_URL, _EOW_RESOLVED_ID = _eow_resolve_camera_url()

# ─── AKILLI YEDEKLEME (Smart Fallback) ─────────────────────────────────────
# `config/config.json` Docker container'da `DB_HOST=db` ve `MILVUS_HOST=milvus`
# olarak donduruluyor. Bu launcher host shell'de (X server için zorunlu)
# çalıştığında "db" ve "milvus" hostname'leri Docker DNS olmadan çözümlenemez
# → `could not translate host name "db" to address`.
# Çözüm: env var DB_HOST/MILVUS_HOST varsa ÖZÜR DİLEMEZ override; yoksa
# `[db, eyeofweb_db, 127.0.0.1, localhost]` zincirini sırayla dener.
# `lib/database_tools.py` crawler tarafı için aynı tedaviyi zaten yapıyor —
# bu sadece kamera launcher'ın PyQt5 sürecinde tekrarıdır.

def _build_host_chain(primary, env_var, container_name, fallbacks=("127.0.0.1", "localhost")):
    """Env override → primary → container_name → 127.0.0.1 → localhost (dedup)."""
    chain = []
    env_val = _eow_os.environ.get(env_var)
    if env_val:
        chain.append(env_val)
    if primary and primary not in chain:
        chain.append(primary)
    if container_name and container_name not in chain:
        chain.append(container_name)
    for fb in fallbacks:
        if fb not in chain:
            chain.append(fb)
    return chain


def _eow_try_pg_connect(base_cfg):
    """psycopg2.connect fallback chain — başarılı olan host'u döner."""
    import psycopg2 as _psy
    primary = base_cfg.get("host", "db")
    chain = _build_host_chain(primary, "DB_HOST", "eyeofweb_db")
    last_err = None
    for host in chain:
        try:
            conn = _psy.connect(
                host=host,
                port=base_cfg.get("port", 5432),
                dbname=base_cfg.get("database", "EyeOfWeb"),
                user=base_cfg.get("user", "postgres"),
                password=base_cfg.get("password", "postgres"),
                connect_timeout=5,
            )
            if host != primary:
                print(f"[Launcher][PG] Fallback host '{host}' başarılı (primary '{primary}' fail).")
            else:
                print(f"[Launcher][PG] Primary host '{host}' başarılı.")
            return conn, host
        except _psy.OperationalError as e:
            last_err = e
            print(f"[Launcher][PG] '{host}' fail: {str(e).strip()[:80]}")
            continue
        except _psy.Error as e:
            # Auth / DB yok gibi hatalar — fallback'le düzelmez
            raise
    raise last_err if last_err else RuntimeError("PG: no host candidates")


def _eow_try_milvus_connect(alias, primary_host, port, user, password):
    """Milvus connections.connect fallback chain. Başarılı host'u döner."""
    from pymilvus import connections as _conns
    chain = _build_host_chain(primary_host, "MILVUS_HOST", "eyeofweb_milvus")
    last_err = None
    for host in chain:
        try:
            # Aynı alias daha önce başarısız bağlandıysa temizle
            if _conns.has_connection(alias):
                try:
                    _conns.disconnect(alias)
                except Exception:
                    pass
            _conns.connect(
                alias=alias,
                host=host,
                port=port,
                user=user or "",
                password=password or "",
                timeout=5,
            )
            if host != primary_host:
                print(f"[Launcher][Milvus] Fallback host '{host}' başarılı (primary '{primary_host}' fail).")
            else:
                print(f"[Launcher][Milvus] Primary host '{host}' başarılı.")
            return host
        except Exception as e:
            last_err = e
            print(f"[Launcher][Milvus] '{host}' fail: {str(e).strip()[:80]}")
            continue
    raise last_err if last_err else RuntimeError("Milvus: no host candidates")

# ─────────────────────────────────────────────────────────────────────────

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import cv2
import numpy as np
import time
import psycopg2
import psycopg2.extras
import io
from PyQt5 import sip
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
    QFormLayout,
    QHeaderView,
    QSplitter,
    QSizePolicy,
    QMessageBox,
    QGraphicsDropShadowEffect,
    QFrame,
    QProgressBar,
    QSpacerItem,
)
from PyQt5.QtGui import (
    QPixmap,
    QImage,
    QFont,
    QColor,
    QPalette,
    QLinearGradient,
    QPainter,
    QBrush,
    QPen,
)
from PyQt5.QtCore import (
    Qt,
    QTimer,
    pyqtSlot,
    QThread,
    pyqtSignal,
    QPropertyAnimation,
    QEasingCurve,
    QRect,
    QPoint,
)
from pymilvus import connections, Collection, utility
from PyQt5.QtCore import QSize

# Add InsightFace import if available in your project
from lib.init_insightface import initilate_insightface
from lib.load_config import load_config_from_file
from lib.database_tools import MILVUS_PASSWORD
from lib.database_tools import MILVUS_HOST
from lib.database_tools import MILVUS_PORT
from lib.database_tools import MILVUS_USER
from lib.database_tools import EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME
from lib.database_tools import get_milvus_collection
from lib.database_tools import get_default_db_config
from lib.compress_tools import decompress_image


class AnimatedLabel(QLabel):
    """Animasyonlu label widget"""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(1000)
        self.animation.setEasingCurve(QEasingCurve.OutBounce)

    def animate_pulse(self):
        """Nabız animasyonu"""
        self.animation.finished.connect(self.reset_animation)
        current_rect = self.geometry()
        expanded_rect = QRect(
            current_rect.x() - 5,
            current_rect.y() - 5,
            current_rect.width() + 10,
            current_rect.height() + 10,
        )
        self.animation.setStartValue(current_rect)
        self.animation.setEndValue(expanded_rect)
        self.animation.start()

    def reset_animation(self):
        """Animasyonu sıfırla"""
        current_rect = self.geometry()
        original_rect = QRect(
            current_rect.x() + 5,
            current_rect.y() + 5,
            current_rect.width() - 10,
            current_rect.height() - 10,
        )
        self.animation.setStartValue(current_rect)
        self.animation.setEndValue(original_rect)
        self.animation.start()


class CyberFrame(QFrame):
    """Sibernetik çerçeve widget"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Box)

        # Gölge efekti
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 255, 255, 100))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)


class SearchThread(QThread):
    """Arama işlemleri için ayrı thread"""

    search_completed = pyqtSignal(list)  # Search results
    search_error = pyqtSignal(str)  # Error message
    images_loaded = pyqtSignal(dict)  # Loaded images {milvus_id: binary_data}

    def __init__(
        self, face_embedding, milvus_collection, db_conn, search_threshold, max_results
    ):
        super().__init__()
        self.face_embedding = face_embedding
        self.milvus_collection = milvus_collection
        self.db_conn = db_conn
        self.search_threshold = search_threshold
        self.max_results = max_results

    def run(self):
        try:
            # Milvus search
            search_params = {
                "metric_type": "COSINE",
                "params": {"ef": max(1200, self.max_results * 1.2)},
            }

            results = self.milvus_collection.search(
                data=[self.face_embedding],
                anns_field="face_embedding_data",
                param=search_params,
                limit=self.max_results,
                output_fields=["id", "face_gender", "face_age", "detection_score"],
                consistency_level="Strong",
            )

            # Emit results
            self.search_completed.emit(results)

            # Load database images in background
            if results and results[0]:
                self.load_database_images(results)

        except Exception as e:
            self.search_error.emit(str(e))

    def load_database_images(self, results):
        """Load database images for search results"""
        db_images = {}

        if not self.db_conn:
            return

        try:
            cursor = self.db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            for hit in results[0]:
                milvus_id = hit.id

                # Get face ID
                cursor.execute(
                    'SELECT "ID" FROM "EyeOfWebFaceID" WHERE "MilvusRefID" = %s',
                    (milvus_id,),
                )
                face_record = cursor.fetchone()

                if not face_record:
                    continue

                face_id = face_record["ID"]

                # Find image with this face ID
                query_main = 'SELECT "ImageID" FROM "ImageBasedMain" WHERE "FaceID" @> ARRAY[%s]::bigint[]'
                cursor.execute(query_main, (face_id,))
                image_records = cursor.fetchall()

                if not image_records:
                    query_fallback = 'SELECT "ImageID" FROM "ImageBasedMain" WHERE %s = ANY("FaceID")'
                    cursor.execute(query_fallback, (face_id,))
                    image_records = cursor.fetchall()
                    if not image_records:
                        continue

                # Get first valid image ID
                image_id = None
                for record in image_records:
                    if record["ImageID"] is not None:
                        image_id = record["ImageID"]
                        break

                if not image_id:
                    continue

                # Get binary image data
                cursor.execute(
                    'SELECT "BinaryImage" FROM "ImageID" WHERE "ID" = %s', (image_id,)
                )
                binary_record = cursor.fetchone()

                if binary_record and binary_record["BinaryImage"]:
                    db_images[milvus_id] = binary_record["BinaryImage"]

            cursor.close()
            self.images_loaded.emit(db_images)

        except Exception as e:
            print(f"Database images loading error: {str(e)}")


class CameraThread(QThread):
    """Thread for camera capture to keep UI responsive"""

    frame_update = pyqtSignal(np.ndarray)

    def __init__(self, camera_id=0):
        super().__init__()
        self.camera_id = camera_id
        self.running = False
        self.cap = None

    def run(self):
        self.running = True
        self.cap = None  # Initialize cap
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
        except Exception as e:
            print(f"Kamera açma hatası (cv2.VideoCapture): {str(e)}")
            self.running = (
                False  # Stop the thread if VideoCapture constructor fails critically
            )
            return

        if not self.cap or not self.cap.isOpened():
            print(f"Hata: Kamera {self.camera_id} açılamadı veya self.cap None.")
            self.running = False  # Stop thread if camera couldn't be opened
            return

        while self.running:
            ret, frame = self.cap.read()
            if ret:
                self.frame_update.emit(frame)
            else:
                # If frame reading fails, try to reconnect for streams
                if (
                    isinstance(self.camera_id, str) and self.running
                ):  # Check self.running
                    print(
                        f"Kamera stream'i kesildi, yeniden bağlanmaya çalışılıyor: {self.camera_id}"
                    )
                    time.sleep(1)
                    if self.cap:
                        self.cap.release()
                    try:
                        self.cap = cv2.VideoCapture(self.camera_id)
                        if not self.cap or not self.cap.isOpened():
                            print(
                                f"Yeniden bağlanma başarısız: Kamera {self.camera_id} açılamadı."
                            )
                            self.running = False  # Stop if reconnect fails
                            break
                    except Exception as e:
                        print(f"Yeniden bağlanma sırasında istisna: {str(e)}")
                        self.running = False  # Stop on critical error during reconnect
                        break
                elif self.running:
                    print(
                        f"Kamera {self.camera_id} kare okuma hatası, thread durduruluyor."
                    )
                    self.running = False
                    break

            if not self.running:  # Check self.running again before sleep
                break
            time.sleep(0.03)  # ~30 FPS

        if self.cap and self.cap.isOpened():
            self.cap.release()
        # print(f"Kamera thread ({self.camera_id}) sonlandırıldı.") # Optional: for debugging

    def stop(self):
        self.running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()

    def change_camera(self, camera_id):
        was_running = self.running
        if was_running:
            self.stop()
            self.wait()

        self.camera_id = camera_id

        if was_running:
            self.start()


class RealtimeSearchApp(QMainWindow):
    """Gerçek Zamanlı Kamera Arama Uygulaması - Sibernetik UI"""

    def __init__(self):
        super().__init__()

        # App configuration
        self.setWindowTitle(
            f"👁️ EyeOfWeb - Kamera #{_EOW_RESOLVED_ID} - Kurumsal Yüz Tanıma v2.0"
            if _EOW_RESOLVED_ID is not None
            else "👁️ EyeOfWeb - Kurumsal Yüz Tanıma Sistemi v2.0"
        )
        self.setGeometry(50, 50, 1200, 800)  # Reduced size to fit better on screen

        # App state
        self.config = None
        self.face_analyzer = None
        self.milvus_collection = None
        self.db_conn = None
        self.current_frame = None
        self.detected_faces = []
        self.current_face_image = None  # Store current face image
        self.db_face_images = {}  # Store database face images {milvus_id: image}
        self.search_threshold = 0.60  # Default similarity threshold
        self.max_results = 5
        self.search_interval = 1.0  # Search every 1 second
        self.last_search_time = 0
        # AUTO-PATCHED — orijinaldeki hardcoded RTSP URL launcher tarafından override edilir
        self.camera_id = _EOW_RESOLVED_URL
        self.current_result_index = -1  # Currently selected result index

        # Multi-face detection state
        self.face_widgets = []  # Store face display widgets
        self.face_search_threads = (
            {}
        )  # Store search threads for each face {face_index: thread}
        self.face_results = {}  # Store results for each face {face_index: results}
        self.face_db_images = (
            {}
        )  # Store DB images for each face {face_index: {milvus_id: image}}
        self.selected_face_index = 0  # Currently selected face for detailed view
        self.max_faces = 6  # Maximum number of faces to display

        # Search thread
        self.search_thread = None
        self.is_searching = False

        # Statistics
        self.total_searches = 0
        self.successful_matches = 0

        # Animation timers
        self.status_blink_timer = QTimer(self)
        self.status_blink_timer.timeout.connect(self.blink_status)

        # Loading animation timer
        self.loading_timer = QTimer(self)
        self.loading_timer.timeout.connect(self.update_loading_animation)
        self.loading_dots = 0

        # Load configuration and models
        self.load_config_and_analyzer()

        # Connect to databases
        self.connect_to_milvus()
        self.connect_to_postgres()

        # Initialize camera thread
        self.camera_thread = CameraThread(self.camera_id)
        self.camera_thread.frame_update.connect(self.update_frame)

        # Create UI
        self._create_cyber_ui()

        # Start camera
        self.camera_thread.start()

        # Start processing timer
        self.process_timer = QTimer(self)
        self.process_timer.timeout.connect(self.process_frame)
        self.process_timer.start(100)  # Process frames every 100ms

    def load_config_and_analyzer(self):
        """Konfigürasyon ve InsightFace yükle"""
        try:
            # Load configuration
            config_data = load_config_from_file()
            if not config_data[0]:
                QMessageBox.critical(
                    self, "Hata", f"Konfigürasyon yüklenemedi: {config_data[1]}"
                )
                sys.exit(1)

            self.config = config_data[1]

            # Load InsightFace model
            self.face_analyzer = initilate_insightface(config_data)
            if self.face_analyzer is None:
                QMessageBox.critical(self, "Hata", "InsightFace modeli yüklenemedi!")
                sys.exit(1)

            print("InsightFace modeli başarıyla yüklendi.")
        except Exception as e:
            QMessageBox.critical(
                self, "Hata", f"Konfigürasyon ve model yükleme hatası: {str(e)}"
            )
            sys.exit(1)

    def connect_to_milvus(self):
        """
        Milvus veritabanına bağlan — akıllı fallback chain ile.

        Önce `MILVUS_HOST` env var (varsa), sonra config'teki primary host
        (`MILVUS_HOST` modül sabiti, default 'localhost' veya Docker env'den
        'milvus'), sonra container_name `eyeofweb_milvus`, sonra `127.0.0.1`,
        son olarak `localhost` denenir. İlk başarılı bağlantı kabul edilir.
        Tüm host'lar fail ederse orijinal hata fırlatılır.
        """
        try:
            # AKILLI YEDEKLEME — _eow_try_milvus_connect host chain'i sırayla dener.
            resolved_host = _eow_try_milvus_connect(
                alias="default",
                primary_host=MILVUS_HOST,
                port=MILVUS_PORT,
                user=MILVUS_USER,
                password=MILVUS_PASSWORD,
            )

            # Get collection name and load
            collection_name = EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME

            # Use the get_milvus_collection helper function for proper loading
            self.milvus_collection = get_milvus_collection(
                collection_name, alias="default"
            )

            if self.milvus_collection:
                print(f"Milvus koleksiyonuna başarıyla bağlanıldı: {collection_name} (host={resolved_host})")
            else:
                QMessageBox.warning(
                    self,
                    "Uyarı",
                    f"Milvus koleksiyonu '{collection_name}' yüklenemedi.",
                )

        except Exception as e:
            QMessageBox.critical(
                self, "Milvus Hatası", f"Milvus'a bağlanılamadı (tüm fallback host'lar denendi): {str(e)}"
            )

    def connect_to_postgres(self):
        """
        PostgreSQL veritabanına bağlan — akıllı fallback chain ile.

        Önce `DB_HOST` env var (varsa), sonra config.json'daki primary host
        (default 'db' Docker'da), sonra container_name `eyeofweb_db`, sonra
        `127.0.0.1`, son olarak `localhost` denenir. İlk başarılı bağlantı
        kabul edilir. host shell'den çalıştırıldığında 'db' hostname
        çözümlenemez → otomatik 127.0.0.1'e fallback.
        """
        try:
            db_config = load_config_from_file()[1]["database_config"]
            # AKILLI YEDEKLEME — _eow_try_pg_connect host chain'i sırayla dener.
            self.db_conn, resolved_host = _eow_try_pg_connect(db_config)
            print(f"PostgreSQL veritabanına başarıyla bağlanıldı (host={resolved_host})")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Veritabanı Hatası",
                f"PostgreSQL'e bağlanılamadı (tüm fallback host'lar denendi): {str(e)}",
            )

    def _create_cyber_ui(self):
        """Sibernetik ana UI oluştur"""
        # Ana widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Ana layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)  # Reduced margins
        main_layout.setSpacing(8)  # Reduced spacing

        # Başlık bölümü
        self.create_header()
        main_layout.addWidget(self.header_frame)

        # Ana içerik bölümü
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setChildrenCollapsible(False)

        # Sol panel (kamera ve kontroller)
        left_panel = self.create_left_panel()

        # Sağ panel (arama sonuçları)
        right_panel = self.create_right_panel()

        # Panelleri splitter'a ekle
        content_splitter.addWidget(left_panel)
        content_splitter.addWidget(right_panel)
        content_splitter.setSizes([int(self.width() * 0.65), int(self.width() * 0.35)])

        main_layout.addWidget(content_splitter)

        # Alt durum çubuğu
        self.create_footer()
        main_layout.addWidget(self.footer_frame)

        # Sibernetik tema uygula
        self.apply_cybernetic_theme()

        # Now that all UI is created, select initial face
        if self.face_widgets:
            print("UI fully created, selecting initial face 0")
            self.select_face(0)

    def create_header(self):
        """Sibernetik başlık oluştur"""
        self.header_frame = CyberFrame()
        self.header_frame.setFixedHeight(60)  # Reduced height

        header_layout = QHBoxLayout(self.header_frame)

        # Logo ve başlık
        title_label = QLabel("🔬 EYE OF WEB - Gelişmiş Yüz Tanıma Sistemi")
        title_label.setObjectName("mainTitle")

        # Sistem durumu
        self.system_status = AnimatedLabel("🟢 SİSTEM AKTİF")
        self.system_status.setObjectName("systemStatus")

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.system_status)

    def create_left_panel(self):
        """Sol panel oluştur"""
        left_panel = CyberFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)  # Reduced margins
        left_layout.setSpacing(10)  # Reduced spacing

        # Kamera görüntü bölümü
        camera_group = self.create_camera_section()
        left_layout.addWidget(camera_group)

        # Kontrol paneli
        control_group = self.create_control_section()
        left_layout.addWidget(control_group)

        # Parametreler
        params_group = self.create_parameters_section()
        left_layout.addWidget(params_group)

        return left_panel

    def create_camera_section(self):
        """Kamera bölümü oluştur"""
        camera_group = QGroupBox("📹 CANLI KAMERA GÖRÜNTÜSÜ")
        camera_group.setObjectName("cyberGroup")
        camera_layout = QVBoxLayout(camera_group)

        # Kamera görüntü alanı
        self.camera_view = QLabel()
        self.camera_view.setAlignment(Qt.AlignCenter)
        self.camera_view.setMinimumSize(480, 360)  # Reduced minimum size
        self.camera_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.camera_view.setObjectName("cameraView")
        self.camera_view.setText("🎥 KAMERA BAŞLATILIYOR...")

        camera_layout.addWidget(self.camera_view)

        # Kamera kontrolleri - daha iyi düzenlenmiş
        camera_controls_frame = QFrame()
        camera_controls_frame.setObjectName("controlsFrame")
        camera_controls_main_layout = QVBoxLayout(camera_controls_frame)
        camera_controls_main_layout.setSpacing(5)  # Reduced spacing

        # İlk satır: Kamera seçici ve manuel giriş
        first_row = QFrame()
        first_row_layout = QHBoxLayout(first_row)
        first_row_layout.setContentsMargins(5, 5, 5, 5)

        # Kamera seçici
        camera_label = QLabel("📸 Kamera:")
        camera_label.setObjectName("controlLabel")
        camera_label.setMinimumWidth(80)

        self.camera_selector = QComboBox()
        self.camera_selector.setObjectName("cyberCombo")
        self.camera_selector.addItems([f"Kamera {i}" for i in range(5)])
        self.camera_selector.currentIndexChanged.connect(self.change_camera)
        self.camera_selector.setMinimumWidth(120)

        # Manuel kamera adresi bölümü
        manual_section = QFrame()
        manual_section.setObjectName("manualSection")
        manual_layout = QHBoxLayout(manual_section)
        manual_layout.setContentsMargins(10, 5, 10, 5)
        manual_layout.setSpacing(10)

        manual_label = QLabel("🎯 Manuel Adres:")
        manual_label.setObjectName("controlLabel")
        manual_label.setMinimumWidth(100)

        self.manual_camera_input = QLineEdit()
        self.manual_camera_input.setObjectName("cyberLineEdit")
        self.manual_camera_input.setPlaceholderText(
            "rtsp://ip:port/stream, http://ip/video.mjpg, /dev/video0, 0"
        )
        self.manual_camera_input.setMinimumWidth(250)  # Reduced minimum width
        self.manual_camera_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.connect_manual_btn = QPushButton("🔗 BAĞLAN")
        self.connect_manual_btn.setObjectName("cyberButton")
        self.connect_manual_btn.clicked.connect(self.connect_manual_camera)
        self.connect_manual_btn.setMinimumWidth(80)  # Reduced width

        manual_layout.addWidget(manual_label)
        manual_layout.addWidget(self.manual_camera_input, 2)  # Give more space to input
        manual_layout.addWidget(self.connect_manual_btn)

        # Add widgets to first row
        first_row_layout.addWidget(camera_label)
        first_row_layout.addWidget(self.camera_selector)
        first_row_layout.addWidget(manual_section, 1)  # Give manual section most space

        # İkinci satır: Arama kontrolleri
        second_row = QFrame()
        second_row_layout = QHBoxLayout(second_row)
        second_row_layout.setContentsMargins(5, 5, 5, 5)

        self.manual_search_btn = QPushButton("🔍 MANUEL ARAMA")
        self.manual_search_btn.setObjectName("cyberButton")
        self.manual_search_btn.clicked.connect(self.manual_search)

        self.auto_search_toggle = QPushButton("🤖 OTOMATİK ARAMA: AKTİF")
        self.auto_search_toggle.setObjectName("cyberButtonActive")
        self.auto_search_toggle.setCheckable(True)
        self.auto_search_toggle.setChecked(True)
        self.auto_search_toggle.clicked.connect(self.toggle_auto_search)

        second_row_layout.addWidget(self.manual_search_btn)
        second_row_layout.addWidget(self.auto_search_toggle)
        second_row_layout.addStretch()

        # Add rows to main controls layout
        camera_controls_main_layout.addWidget(first_row)
        camera_controls_main_layout.addWidget(second_row)

        camera_layout.addWidget(camera_controls_frame)

        return camera_group

    def create_control_section(self):
        """Kontrol bölümü oluştur"""
        control_group = QGroupBox("🎛️ KONTROL PANELİ")
        control_group.setObjectName("cyberGroup")
        control_layout = QHBoxLayout(control_group)

        # Yüz algılama durumu
        self.face_status = AnimatedLabel("👤 YÜZ ALGILAMA: HAZIR")
        self.face_status.setObjectName("faceStatus")

        # Arama durumu
        self.search_status = AnimatedLabel("🔍 ARAMA DURUMU: BEKLİYOR")
        self.search_status.setObjectName("searchStatus")

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("cyberProgress")
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress

        control_layout.addWidget(self.face_status)
        control_layout.addWidget(self.progress_bar)
        control_layout.addStretch()
        control_layout.addWidget(self.search_status)

        return control_group

    def create_parameters_section(self):
        """Parametreler bölümü oluştur"""
        params_group = QGroupBox("⚙️ ARAMA PARAMETRELERİ")
        params_group.setObjectName("cyberGroup")
        params_layout = QFormLayout(params_group)

        # Benzerlik eşiği
        threshold_container = QWidget()
        threshold_layout = QHBoxLayout(threshold_container)
        threshold_layout.setContentsMargins(0, 0, 0, 0)

        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setObjectName("cyberSlider")
        self.threshold_slider.setMinimum(0)
        self.threshold_slider.setMaximum(100)
        self.threshold_slider.setValue(int(self.search_threshold * 100))
        self.threshold_slider.valueChanged.connect(self.update_threshold)

        self.threshold_label = QLabel(f"{self.search_threshold:.2f}")
        self.threshold_label.setObjectName("paramValue")

        threshold_layout.addWidget(self.threshold_slider)
        threshold_layout.addWidget(self.threshold_label)

        # Maksimum sonuç
        max_results_container = QWidget()
        max_results_layout = QHBoxLayout(max_results_container)
        max_results_layout.setContentsMargins(0, 0, 0, 0)

        self.max_results_slider = QSlider(Qt.Horizontal)
        self.max_results_slider.setObjectName("cyberSlider")
        self.max_results_slider.setMinimum(1)
        self.max_results_slider.setMaximum(20)
        self.max_results_slider.setValue(self.max_results)
        self.max_results_slider.valueChanged.connect(self.update_max_results)

        self.max_results_label = QLabel(f"{self.max_results}")
        self.max_results_label.setObjectName("paramValue")

        max_results_layout.addWidget(self.max_results_slider)
        max_results_layout.addWidget(self.max_results_label)

        # Parametreleri forma ekle
        threshold_label = QLabel("🎯 Benzerlik Eşiği:")
        threshold_label.setObjectName("paramLabel")
        results_label = QLabel("📊 Maksimum Sonuç:")
        results_label.setObjectName("paramLabel")

        params_layout.addRow(threshold_label, threshold_container)
        params_layout.addRow(results_label, max_results_container)

        return params_group

    def create_right_panel(self):
        """Sağ panel oluştur"""
        right_panel = CyberFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)  # Reduced margins
        right_layout.setSpacing(10)  # Reduced spacing

        # Yüz görüntüleri - yan yana
        faces_container = QWidget()
        faces_layout = QVBoxLayout(faces_container)
        faces_layout.setSpacing(8)  # Reduced spacing

        # Multi-face grid başlığı
        multi_face_label = QLabel("👥 ÇOKLU YÜZ TESPİTİ")
        multi_face_label.setObjectName("tabTitle")
        multi_face_label.setAlignment(Qt.AlignCenter)
        faces_layout.addWidget(multi_face_label)

        # Yüz grid'i oluştur
        self.faces_grid_widget = QWidget()
        self.faces_grid_layout = QVBoxLayout(self.faces_grid_widget)
        self.faces_grid_layout.setSpacing(8)  # Reduced spacing

        # Grid içeriğini oluştur
        self.create_faces_grid()

        faces_layout.addWidget(self.faces_grid_widget)

        # Seçili yüz için detaylı görünüm
        selected_face_container = QWidget()
        selected_face_layout = QHBoxLayout(selected_face_container)
        selected_face_layout.setSpacing(10)  # Reduced spacing

        # Seçili kamera yüzü
        selected_camera_section = QWidget()
        selected_camera_layout = QVBoxLayout(selected_camera_section)

        selected_camera_label = QLabel("📷 SEÇİLİ YÜZ")
        selected_camera_label.setObjectName("tabTitle")
        selected_camera_label.setAlignment(Qt.AlignCenter)
        selected_camera_layout.addWidget(selected_camera_label)

        self.selected_face_view = QLabel()
        self.selected_face_view.setAlignment(Qt.AlignCenter)
        self.selected_face_view.setMinimumSize(160, 160)  # Reduced size
        self.selected_face_view.setMaximumHeight(200)  # Reduced max height
        self.selected_face_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.selected_face_view.setObjectName("faceView")
        self.selected_face_view.setText("👤 YÜZ SEÇİLMEDİ")

        selected_camera_layout.addWidget(self.selected_face_view)

        # Seçili yüz veritabanı sonucu
        selected_db_section = QWidget()
        selected_db_layout = QVBoxLayout(selected_db_section)

        selected_db_label = QLabel("💾 VERİTABANI EŞLEŞME")
        selected_db_label.setObjectName("tabTitle")
        selected_db_label.setAlignment(Qt.AlignCenter)
        selected_db_layout.addWidget(selected_db_label)

        self.selected_db_view = QLabel()
        self.selected_db_view.setAlignment(Qt.AlignCenter)
        self.selected_db_view.setMinimumSize(160, 160)  # Reduced size
        self.selected_db_view.setMaximumHeight(200)  # Reduced max height
        self.selected_db_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.selected_db_view.setObjectName("faceView")
        self.selected_db_view.setText("🗄️ VERİTABANI GÖRÜNTÜSÜ")

        selected_db_layout.addWidget(self.selected_db_view)

        # Seçili yüz bölümlerini yan yana ekle
        selected_face_layout.addWidget(selected_camera_section)
        selected_face_layout.addWidget(selected_db_section)

        faces_layout.addWidget(selected_face_container)

        right_layout.addWidget(faces_container)

        # Arama sonuçları
        results_group = self.create_results_section()
        right_layout.addWidget(results_group)

        return right_panel

    def create_results_section(self):
        """Sonuçlar bölümü oluştur"""
        results_group = QGroupBox("🎯 ARAMA SONUÇLARI")
        results_group.setObjectName("cyberGroup")
        results_layout = QVBoxLayout(results_group)

        # Sonuç sayısı göstergesi
        self.results_indicator = QLabel("📊 0 sonuç bulundu")
        self.results_indicator.setObjectName("resultsIndicator")
        results_layout.addWidget(self.results_indicator)

        # Sonuçlar tablosu
        self.results_table = QTableWidget(0, 4)
        self.results_table.setObjectName("cyberTable")
        self.results_table.setHorizontalHeaderLabels(
            ["🆔 ID", "🎯 Benzerlik", "👤 Cinsiyet", "🎂 Yaş"]
        )

        # Tablo başlıkları
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.results_table.itemClicked.connect(self.on_result_selected)
        results_layout.addWidget(self.results_table)

        return results_group

    def create_faces_grid(self):
        """Çoklu yüz grid'ini oluştur"""
        # Clear existing widgets
        for widget in self.face_widgets:
            if not sip.isdeleted(widget):
                widget.deleteLater()
        self.face_widgets.clear()

        # Clear layout
        while self.faces_grid_layout.count():
            child = self.faces_grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Create grid layout for faces (2 rows x 3 columns)
        grid_rows = 2
        grid_cols = 3

        print(
            f"Creating face grid with {grid_rows}x{grid_cols} = {grid_rows * grid_cols} face widgets"
        )

        for row in range(grid_rows):
            row_widget = QWidget()
            row_widget.setObjectName("faceRowWidget")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setSpacing(10)
            row_layout.setContentsMargins(5, 5, 5, 5)

            for col in range(grid_cols):
                face_index = row * grid_cols + col
                if face_index >= self.max_faces:
                    break

                print(f"Creating face widget for index {face_index}")
                face_widget = self.create_face_widget(face_index)
                self.face_widgets.append(face_widget)
                row_layout.addWidget(face_widget)

            # Add stretch to center the widgets if not full row
            row_layout.addStretch()
            self.faces_grid_layout.addWidget(row_widget)

        # Add a stretch at the end
        self.faces_grid_layout.addStretch()

        print(f"Face grid created with {len(self.face_widgets)} widgets")

        # Don't call select_face here - will be called after all UI is created

    def create_face_widget(self, face_index):
        """Tek bir yüz widget'ı oluştur"""
        face_widget = QWidget()
        face_widget.setObjectName("faceWidget")
        face_widget.setFixedSize(140, 160)  # Smaller size to fit better
        face_layout = QVBoxLayout(face_widget)
        face_layout.setContentsMargins(3, 3, 3, 3)  # Reduced margins
        face_layout.setSpacing(3)  # Reduced spacing

        # Yüz başlığı
        face_title = QLabel(f"👤 YÜZ {face_index + 1}")
        face_title.setObjectName("faceTitle")
        face_title.setAlignment(Qt.AlignCenter)
        face_title.setFixedHeight(18)  # Reduced height
        face_layout.addWidget(face_title)

        # Yüz görüntüsü
        face_image = QLabel()
        face_image.setObjectName("faceImage")
        face_image.setAlignment(Qt.AlignCenter)
        face_image.setFixedSize(120, 120)  # Slightly smaller square size
        face_image.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        face_image.setText("⏳ BEKLİYOR")
        face_image.setStyleSheet(
            """
            QLabel#faceImage {
                border: 2px solid #666666;
                border-radius: 6px;
                background: rgba(45, 45, 45, 0.8);
                color: #888888;
                font-size: 9pt;
                font-weight: 500;
            }
        """
        )

        # Make clickable
        face_image.mousePressEvent = lambda event, idx=face_index: self.select_face(idx)
        face_image.setCursor(Qt.PointingHandCursor)

        face_layout.addWidget(face_image)

        # Durum göstergesi
        status_label = QLabel("⚪ PASİF")
        status_label.setObjectName("faceStatus")
        status_label.setAlignment(Qt.AlignCenter)
        status_label.setFixedHeight(12)  # Reduced height
        status_label.setStyleSheet(
            """
            QLabel#faceStatus {
                color: #888888;
                font-size: 8pt;
                font-weight: 500;
                padding: 1px;
                background: transparent;
                border: none;
            }
        """
        )
        face_layout.addWidget(status_label)

        # Widget'ı kaydet - reference'ları widgets'a ata
        face_widget.face_image = face_image
        face_widget.status_label = status_label
        face_widget.face_title = face_title
        face_widget.face_index = face_index

        print(
            f"Created face widget {face_index} with size {face_widget.size()}, image size {face_image.size()}"
        )

        return face_widget

    def select_face(self, face_index):
        """Yüz seçimi yap"""
        print(f"Face {face_index} selected")
        self.selected_face_index = face_index

        # Update selected face display first
        self.update_selected_face_display()

        # Update face widget borders to show selection with error handling
        for widget in self.face_widgets:
            if hasattr(widget, "face_index") and not sip.isdeleted(widget):
                try:
                    if widget.face_index == face_index:
                        # Selected face - blue border
                        if hasattr(widget, "face_image") and not sip.isdeleted(
                            widget.face_image
                        ):
                            widget.face_image.setStyleSheet(
                                """
                                QLabel#faceImage {
                                    border: 3px solid #0078d4;
                                    border-radius: 6px;
                                    background: rgba(45, 45, 45, 0.8);
                                    color: #e0e0e0;
                                    font-size: 9pt;
                                    font-weight: 500;
                                }
                            """
                            )
                        if hasattr(widget, "face_title") and not sip.isdeleted(
                            widget.face_title
                        ):
                            widget.face_title.setText(f"👤 YÜZ {face_index + 1} ✅")
                    else:
                        # Unselected face - normal border
                        if hasattr(widget, "face_image") and not sip.isdeleted(
                            widget.face_image
                        ):
                            widget.face_image.setStyleSheet(
                                """
                                QLabel#faceImage {
                                    border: 2px solid #666666;
                                    border-radius: 6px;
                                    background: rgba(45, 45, 45, 0.8);
                                    color: #888888;
                                    font-size: 9pt;
                                    font-weight: 500;
                                }
                            """
                            )
                        if hasattr(widget, "face_title") and not sip.isdeleted(
                            widget.face_title
                        ):
                            widget.face_title.setText(f"👤 YÜZ {widget.face_index + 1}")
                except RuntimeError as e:
                    if "wrapped C/C++ object" in str(e):
                        print(f"Face widget labels deleted during selection update")
                        continue
                    else:
                        print(f"Error updating face selection: {str(e)}")

        # Update results table for selected face
        if face_index in self.face_results:
            self.update_results_table(self.face_results[face_index])
        else:
            try:
                self.results_table.setRowCount(0)
                self.results_indicator.setText("📊 0 sonuç bulundu")
            except RuntimeError as e:
                if "wrapped C/C++ object" in str(e):
                    print("Results table/indicator deleted, skipping update")
                else:
                    print(f"Error updating results table: {str(e)}")

    def update_selected_face_display(self):
        """Seçili yüzün detaylı görünümünü güncelle"""
        # Check if the widgets exist first
        if not hasattr(self, "selected_face_view") or not hasattr(
            self, "selected_db_view"
        ):
            print("Selected face view widgets not yet created, skipping update")
            return

        face_index = self.selected_face_index

        # Update selected face image with error handling
        try:
            if (
                face_index < len(self.detected_faces)
                and face_index < len(self.face_widgets)
                and hasattr(self.face_widgets[face_index], "face_image")
                and not sip.isdeleted(self.face_widgets[face_index].face_image)
            ):

                # Get pixmap from face widget
                pixmap = self.face_widgets[face_index].face_image.pixmap()
                if pixmap and not sip.isdeleted(self.selected_face_view):
                    scaled_pixmap = pixmap.scaled(
                        self.selected_face_view.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                    self.selected_face_view.setPixmap(scaled_pixmap)
                elif not sip.isdeleted(self.selected_face_view):
                    self.selected_face_view.setText("👤 YÜZ SEÇİLMEDİ")
            elif not sip.isdeleted(self.selected_face_view):
                self.selected_face_view.setText("👤 YÜZ SEÇİLMEDİ")
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                print("Selected face view deleted during update")
            else:
                print(f"Error updating selected face view: {str(e)}")

        # Update selected DB image with error handling
        try:
            # Check if this face has database images AND search results
            has_db_images = (
                face_index in self.face_db_images and self.face_db_images[face_index]
            )
            has_search_results = (
                face_index in self.face_results
                and self.face_results[face_index]
                and self.face_results[face_index][0]
            )

            if (
                has_db_images
                and has_search_results
                and not sip.isdeleted(self.selected_db_view)
            ):
                # Get first result's image
                db_images = self.face_db_images[face_index]
                first_milvus_id = list(db_images.keys())[0]
                pixmap = self.get_db_image_pixmap_for_face(face_index, first_milvus_id)
                if pixmap:
                    scaled_pixmap = pixmap.scaled(
                        self.selected_db_view.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                    self.selected_db_view.setPixmap(scaled_pixmap)
                    print(f"Database image displayed for face {face_index}")
                else:
                    self.selected_db_view.clear()
                    self.selected_db_view.setText("🗄️ VERİTABANI GÖRÜNTÜSÜ MEVCUT DEĞİL")
                    print(f"Failed to load database image for face {face_index}")
            elif not sip.isdeleted(self.selected_db_view):
                # No database images or no results - clear the display
                self.selected_db_view.clear()
                if has_search_results:
                    self.selected_db_view.setText(
                        "🗄️ VERİTABANI GÖRÜNTÜSÜ YÜKLENİYOR..."
                    )
                    print(f"No database images loaded yet for face {face_index}")
                else:
                    self.selected_db_view.setText("❌ EŞLEŞME BULUNAMADI")
                    print(
                        f"No search results for face {face_index}, clearing database view"
                    )
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                print("Selected DB view deleted during update")
            else:
                print(f"Error updating selected DB view: {str(e)}")

    def create_footer(self):
        """Alt durum çubuğu oluştur"""
        self.footer_frame = CyberFrame()
        self.footer_frame.setFixedHeight(40)  # Reduced height

        footer_layout = QHBoxLayout(self.footer_frame)

        # Ana durum
        self.status_label = AnimatedLabel("🟢 SYSTEM READY")
        self.status_label.setObjectName("systemStatus")
        self.status_label.setAlignment(Qt.AlignCenter)

        # İstatistikler
        self.stats_label = QLabel("STATS: 0 SEARCH | 0 MATCH")
        self.stats_label.setObjectName("statsLabel")
        self.stats_label.setAlignment(Qt.AlignCenter)

        # Zaman
        self.time_label = QLabel()
        self.time_label.setObjectName("timeLabel")
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Zaman güncelleyici
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)
        self.update_time()

        footer_layout.addWidget(self.status_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.stats_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.time_label)

    def update_time(self):
        """Zamanı güncelle"""
        current_time = datetime.now().strftime("🕒 %H:%M:%S - %d/%m/%Y")
        self.time_label.setText(current_time)

    def blink_status(self):
        """Durum etiketi yanıp sönme efekti"""
        current_style = self.status_label.styleSheet()
        if "color: #00ff00" in current_style:
            self.status_label.setStyleSheet(current_style.replace("#00ff00", "#ff0000"))
        else:
            self.status_label.setStyleSheet(current_style.replace("#ff0000", "#00ff00"))

    def apply_cybernetic_theme(self):
        """Kurumsal sibernetik tema uygula"""
        corporate_cyber_style = """
        QMainWindow {
            background: #121212;
            color: #e0e0e0;
            font-family: 'Segoe UI', 'Roboto', 'Arial', sans-serif;
        }
        
        QWidget {
            background: transparent;
            color: #d0d0d0;
            font-family: 'Segoe UI', 'Roboto', 'Arial', sans-serif;
            font-size: 11pt;
        }
        
        #mainTitle {
            font-size: 22pt;
            font-weight: 700;
            color: #00e5ff; /* Cyan Neon */
            background: transparent;
            padding: 10px 0px;
            letter-spacing: 2px;
            text-shadow: 0 0 10px #00e5ff;
        }
        
        #systemStatus {
            font-size: 12pt;
            font-weight: 600;
            color: #00ff00; /* Green Neon */
            background: rgba(0, 50, 0, 0.4);
            border: 1px solid #00ff00;
            border-radius: 4px;
            padding: 8px 16px;
            text-transform: uppercase;
        }
        
        CyberFrame {
            background: rgba(20, 20, 20, 0.85);
            border: 1px solid #333333;
            border-radius: 10px;
        }
        
        QGroupBox#cyberGroup {
            font-size: 11pt;
            font-weight: 600;
            color: #00bcd4;
            background: rgba(25, 25, 25, 0.6);
            border: 1px solid #444444;
            border-radius: 8px;
            margin-top: 1.5em;
            padding-top: 10px;
        }
        
        QGroupBox#cyberGroup::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 10px;
            background: rgba(25, 25, 25, 1.0);
            color: #00bcd4; /* Header color */
            border: 1px solid #444444;
            border-bottom: none;
            border-radius: 4px 4px 0 0;
            margin-left: 10px;
        }
        
        #cameraView {
            background: #000000;
            border: 2px solid #005a9e; /* Blue border */
            border-radius: 4px;
            color: #555555;
            font-size: 16pt;
            font-weight: 500;
        }
        
        #faceView {
            background: #000000;
            border: 1px solid #444444;
            border-radius: 4px;
            color: #555555;
            font-size: 10pt;
        }
        
        /* Buttons - Futuristic */
        QPushButton#cyberButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                stop:0 #006064, stop:1 #00363a);
            border: 1px solid #00bcd4;
            border-radius: 4px;
            color: #e0f7fa;
            font-size: 11pt;
            font-weight: 600;
            padding: 10px 16px;
            min-width: 100px;
            text-transform: uppercase;
        }
        
        QPushButton#cyberButton:hover {
            background: #00838f;
            border: 1px solid #4dd0e1;
            box-shadow: 0 0 10px #4dd0e1;
        }
        
        QPushButton#cyberButton:pressed {
            background: #006064;
            border: 1px solid #0097a7;
        }
        
        /* Active specific button */
        QPushButton#cyberButtonActive {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                stop:0 #1b5e20, stop:1 #0d3311);
            border: 1px solid #4caf50;
            border-radius: 4px;
            color: #e8f5e9;
            font-size: 11pt;
            font-weight: 600;
            padding: 10px 16px;
            min-width: 100px;
        }
        
        QPushButton#cyberButtonActive:hover {
            background: #2e7d32;
            box-shadow: 0 0 10px #4caf50;
        }
        
        /* Inputs */
        QLineEdit#cyberLineEdit {
            background: rgba(30, 30, 30, 0.9);
            border: 1px solid #555555;
            border-radius: 2px;
            color: #00bcd4;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 11pt;
            padding: 8px;
        }
        
        QLineEdit#cyberLineEdit:focus {
            border: 1px solid #00bcd4;
            background: rgba(40, 40, 40, 1.0);
        }
        
        /* Combo Box */
        QComboBox#cyberCombo {
            background: rgba(30, 30, 30, 0.9);
            border: 1px solid #555555;
            border-radius: 2px;
            color: #e0e0e0;
            font-size: 11pt;
            padding: 6px;
        }
        
        QComboBox#cyberCombo::drop-down {
            border: none;
            background: #444444;
            width: 25px;
        }
        
        /* Table */
        QTableWidget#cyberTable {
            background: rgba(20, 20, 20, 0.9);
            border: 1px solid #444444;
            gridline-color: #333333;
            color: #d0d0d0;
            font-family: 'Consolas', monospace;
            font-size: 10pt;
        }
        
        QTableWidget#cyberTable::item:selected {
            background: rgba(0, 188, 212, 0.2);
            color: #ffffff;
            border: 1px solid #00bcd4;
        }
        
        QHeaderView::section {
            background: #252525;
            color: #00bcd4;
            padding: 6px;
            border: 1px solid #333333;
            font-weight: 700;
            text-transform: uppercase;
        }
        
        /* Scrollbars (Modern/Thin) */
        QScrollBar:vertical {
            background: #1a1a1a;
            width: 10px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background: #444444;
            min-height: 20px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical:hover {
            background: #00bcd4;
        }
        
        /* Labels & Misc */
        #controlLabel { color: #aaaaaa; }
        
        #paramValue {
            background: #000000;
            border: 1px solid #444444;
            color: #00bcd4;
            font-family: monospace;
            font-weight: bold;
            padding: 4px;
            text-align: center;
        }
        
        #faceStatus {
            color: #ff9800;
            font-weight: 600;
        }
        
        #resultsIndicator {
            color: #00e5ff;
            font-family: monospace;
        }
        
        #statsLabel, #timeLabel {
            font-family: 'Consolas', monospace;
            color: #666666;
            font-size: 9pt;
        }
        """

        self.setStyleSheet(corporate_cyber_style)

    def update_frame(self, frame):
        """Kamera karesi güncelle"""
        self.current_frame = frame

        # Convert frame to Qt format and display
        h, w, c = frame.shape
        bytes_per_line = c * w
        qt_image = QImage(
            frame.data, w, h, bytes_per_line, QImage.Format_RGB888
        ).rgbSwapped()
        pixmap = QPixmap.fromImage(qt_image)

        # Scale pixmap to fit the label while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(
            self.camera_view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.camera_view.setPixmap(scaled_pixmap)

    def process_frame(self):
        """Mevcut kareyi işle - çoklu yüzleri algıla ve ara"""
        if self.current_frame is None:
            return

        # Clone frame to avoid modification issues
        frame = self.current_frame.copy()

        # Detect faces
        try:
            self.detected_faces = self.face_analyzer.get(frame)

            # Draw face boxes and update grid
            if self.detected_faces:
                # Yüz bulundu - durumu güncelle
                face_count = len(self.detected_faces)
                print(f"Detected {face_count} faces in frame")

                try:
                    self.face_status.setText(f"👥 {face_count} YÜZ ALGILANDI")
                    self.face_status.setStyleSheet(
                        """
                        background: rgba(76, 175, 80, 0.15);
                        border: 1px solid #4CAF50;
                        border-radius: 6px;
                        color: #4CAF50;
                        font-size: 11pt;
                        font-weight: 500;
                        padding: 8px 12px;
                    """
                    )
                except RuntimeError as e:
                    if "wrapped C/C++ object" in str(e):
                        print("Face status label deleted, skipping update")
                        return
                    else:
                        raise

                # Process each detected face
                # Process each detected face based on search results
                current_time = time.time()

                # Draw Cybernetic HUD for each face
                for i, face in enumerate(self.detected_faces):
                    if i >= self.max_faces:
                        break

                    bbox = face.bbox.astype(int)

                    # Prepare face info
                    face_info = {
                        "gender": "ERKEK" if face.gender == 1 else "KADIN",
                        "age": int(face.age),
                        "score": face.det_score,
                    }

                    # Get match status if available
                    match_info = None
                    if (
                        i in self.face_results
                        and self.face_results[i]
                        and self.face_results[i][0]
                    ):
                        top_match = self.face_results[i][0][
                            0
                        ]  # First result of first detected face? Logic might need adjustment for multi-face
                        # Actually self.face_results key is face_index
                        # self.face_results[i] is a list of results (hits)
                        if len(self.face_results[i]) > 0:
                            best_hit = self.face_results[i][0]
                            match_info = {
                                "id": best_hit.id,
                                "distance": (
                                    best_hit.distance
                                    if hasattr(best_hit, "distance")
                                    else 0
                                ),  # Cosine similarity usually returns distance/score
                                "score": (
                                    best_hit.score if hasattr(best_hit, "score") else 0
                                ),
                            }

                    # Determine color based on match/no-match
                    # Cyan for scanning/neutral, Green for Match, Red for Alert (optional)
                    color = (255, 255, 0)  # Cyan (BGR)
                    if match_info:
                        color = (0, 255, 0)  # Green

                    # Draw futuristic HUD
                    self.draw_cyber_hud(frame, bbox, face_info, match_info, i, color)

                    # Update face widget...
                    try:
                        self.update_face_widget(i, face, frame)
                    except Exception as e:
                        # Widget update errors shouldn't crash drawing
                        pass

                # Draw System Overlay (Top-Left)
                self.draw_system_overlay(frame)

                # Clear unused widgets...
                for i in range(len(self.detected_faces), len(self.face_widgets)):
                    # ... (Existing clearing logic) ...
                    try:
                        self.clear_face_widget(i)
                    except Exception as e:
                        pass

            else:
                # Yüz bulunamadı
                print("No faces detected in frame")

                # Clear all cached data when no faces detected
                if self.face_results:
                    print("Clearing all face results cache - no faces detected")
                    self.face_results.clear()

                if self.face_db_images:
                    print("Clearing all face database images cache - no faces detected")
                    self.face_db_images.clear()

                try:
                    self.face_status.setText("👤 YÜZ ALGILAMA: TARAMA...")
                    self.face_status.setStyleSheet(
                        """
                        background: rgba(255, 193, 7, 0.15);
                        border: 1px solid #FFC107;
                        border-radius: 6px;
                        color: #FFC107;
                        font-size: 11pt;
                        font-weight: 500;
                        padding: 8px 12px;
                    """
                    )
                except RuntimeError as e:
                    if "wrapped C/C++ object" in str(e):
                        print("Face status label deleted, skipping update")
                        return
                    else:
                        raise

                # Clear all face widgets
                for i in range(len(self.face_widgets)):
                    try:
                        self.clear_face_widget(i)
                    except RuntimeError as e:
                        if "wrapped C/C++ object" in str(e):
                            print(f"Face widget {i} deleted during clear, skipping")
                            continue
                        else:
                            raise

                # Update selected face display to clear database view
                try:
                    self.update_selected_face_display()
                except RuntimeError as e:
                    if "wrapped C/C++ object" in str(e):
                        print("Selected face views deleted, skipping update")
                    else:
                        raise

            # Update frame display with face boxes
            try:
                if frame is not None:
                    h, w, c = frame.shape
                    bytes_per_line = c * w
                    qt_image = QImage(
                        frame.data, w, h, bytes_per_line, QImage.Format_RGB888
                    ).rgbSwapped()
                    pixmap = QPixmap.fromImage(qt_image)
                    scaled_pixmap = pixmap.scaled(
                        self.camera_view.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                    self.camera_view.setPixmap(scaled_pixmap)
            except RuntimeError as e:
                pass
            except Exception:
                pass

            # Auto search if enabled and interval passed
            if (
                self.auto_search_toggle.isChecked()
                and time.time() - self.last_search_time > self.search_interval
                and self.detected_faces
                and not self.is_searching
            ):
                try:
                    print("Triggering auto search for all faces")
                    self.search_all_faces()
                except:
                    pass

        except Exception as e:
            print(f"Kare işleme hatası: {str(e)}")
            import traceback

            traceback.print_exc()
            try:
                self.face_status.setText("⚠️ YÜZ ALGILAMA HATASI")
                self.face_status.setStyleSheet(
                    """
                    background: rgba(244, 67, 54, 0.15);
                    border: 1px solid #F44336;
                    border-radius: 6px;
                    color: #F44336;
                    font-size: 11pt;
                    font-weight: 500;
                    padding: 8px 12px;
                """
                )
            except RuntimeError as e2:
                if "wrapped C/C++ object" in str(e2):
                    print("Face status label deleted, skipping error update")
                else:
                    print(f"Error updating face status: {str(e2)}")

    def update_face_widget(self, face_index, face, frame):
        """Yüz widget'ını güncelle"""
        if face_index >= len(self.face_widgets):
            print(
                f"Face index {face_index} out of range, max widgets: {len(self.face_widgets)}"
            )
            return

        face_widget = self.face_widgets[face_index]

        if (
            sip.isdeleted(face_widget)
            or not hasattr(face_widget, "face_image")
            or sip.isdeleted(face_widget.face_image)
            or not hasattr(face_widget, "status_label")
            or sip.isdeleted(face_widget.status_label)
        ):
            print(
                f"Skipping update for deleted face_widget or its QLabel children at index {face_index}"
            )
            return

        try:
            # Extract face region with more robust bounds checking
            bbox = face.bbox.astype(int)

            # Add margin around face
            margin_w = int((bbox[2] - bbox[0]) * 0.3)  # Increased margin
            margin_h = int((bbox[3] - bbox[1]) * 0.3)  # Increased margin

            # Ensure bounds are within frame
            h, w = frame.shape[:2]
            x1 = max(0, bbox[0] - margin_w)
            y1 = max(0, bbox[1] - margin_h)
            x2 = min(w, bbox[2] + margin_w)
            y2 = min(h, bbox[3] + margin_h)

            # Ensure we have a valid region
            if x2 <= x1 or y2 <= y1:
                print(
                    f"Invalid face region for face {face_index}: ({x1},{y1}) to ({x2},{y2})"
                )
                return

            # Extract face region
            face_img = frame[y1:y2, x1:x2].copy()

            if face_img.size == 0:
                print(f"Empty face image for face {face_index}")
                return

            # Convert BGR to RGB for Qt
            face_img_rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)

            # Convert to Qt format
            img_h, img_w, img_c = face_img_rgb.shape
            bytes_per_line = img_c * img_w
            qt_image = QImage(
                face_img_rgb.data, img_w, img_h, bytes_per_line, QImage.Format_RGB888
            )

            if qt_image.isNull():
                print(f"Failed to create QImage for face {face_index}")
                return

            pixmap = QPixmap.fromImage(qt_image)

            if pixmap.isNull():
                print(f"Failed to create QPixmap for face {face_index}")
                return

            # Scale and set pixmap with error handling
            try:
                # Clear the label first
                face_widget.face_image.clear()

                # Get the current size of the face image widget
                widget_size = face_widget.face_image.size()
                if widget_size.width() <= 0 or widget_size.height() <= 0:
                    # Use default size if widget size is invalid
                    widget_size = face_widget.face_image.minimumSize()
                    if widget_size.width() <= 0 or widget_size.height() <= 0:
                        widget_size = face_widget.face_image.sizeHint()
                        if widget_size.width() <= 0 or widget_size.height() <= 0:
                            widget_size = QSize(140, 140)  # Fallback size

                scaled_pixmap = pixmap.scaled(
                    widget_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                face_widget.face_image.setPixmap(scaled_pixmap)

                # Force update and repaint
                face_widget.face_image.update()
                face_widget.face_image.repaint()

                # Debug: Confirm the pixmap was set
                if face_widget.face_image.pixmap():
                    print(
                        f"✅ Successfully updated face widget {face_index} with image {scaled_pixmap.size().width()}x{scaled_pixmap.size().height()}"
                    )
                else:
                    print(f"❌ Failed to set pixmap for face widget {face_index}")
                    # Try setting a basic text as fallback
                    face_widget.face_image.setText(f"YÜZ {face_index + 1}")

            except RuntimeError as e:
                if "wrapped C/C++ object" in str(e):
                    print(f"Face image label {face_index} deleted during pixmap update")
                    return
                else:
                    raise

            # Update status with error handling
            try:
                face_widget.status_label.setText("🟢 AKTİF")
                face_widget.status_label.setStyleSheet(
                    """
                    QLabel#faceStatus {
                        color: #4CAF50;
                        font-size: 9pt;
                        font-weight: 600;
                        padding: 2px;
                        background: transparent;
                        border: none;
                    }
                """
                )
                face_widget.status_label.update()
            except RuntimeError as e:
                if "wrapped C/C++ object" in str(e):
                    print(
                        f"Face status label {face_index} deleted during status update"
                    )
                    return
                else:
                    raise

        except Exception as e:
            print(f"Yüz widget güncelleme hatası (face {face_index}): {str(e)}")
            import traceback

            traceback.print_exc()

            # Set fallback text in case of error
            try:
                face_widget.face_image.setText(f"HATA: YÜZ {face_index + 1}")
                face_widget.status_label.setText("❌ HATA")
            except:
                pass

    def clear_face_widget(self, face_index):
        """Yüz widget'ını temizle"""
        if face_index >= len(self.face_widgets):
            return

        face_widget = self.face_widgets[face_index]

        if (
            sip.isdeleted(face_widget)
            or not hasattr(face_widget, "face_image")
            or sip.isdeleted(face_widget.face_image)
            or not hasattr(face_widget, "status_label")
            or sip.isdeleted(face_widget.status_label)
        ):
            # print(f"Skipping clear for deleted face_widget or its QLabel children at index {face_index}")
            return

        try:
            face_widget.face_image.clear()
            face_widget.face_image.setText("⏳ BEKLİYOR")
            face_widget.status_label.setText("⚪ PASİF")
            face_widget.status_label.setStyleSheet(
                """
                QLabel#faceStatus {
                    color: #888888;
                    font-size: 8pt;
                    font-weight: 500;
                    padding: 1px;
                    background: transparent;
                    border: none;
                }
            """
            )

            # Clear cached data for this face
            if face_index in self.face_results:
                print(f"Clearing face results cache for face {face_index}")
                del self.face_results[face_index]

            if face_index in self.face_db_images:
                print(f"Clearing face database images cache for face {face_index}")
                del self.face_db_images[face_index]

            # If this was the selected face, update the selected face display
            if face_index == self.selected_face_index:
                print(f"Cleared selected face {face_index}, updating display")
                self.update_selected_face_display()

            print(f"Cleared face widget {face_index}")
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                print(f"Face widget {face_index} labels deleted during clear")
            else:
                print(f"Error clearing face widget {face_index}: {str(e)}")

    def search_all_faces(self):
        """Tüm algılanan yüzler için arama yap"""
        if not self.detected_faces or not self.milvus_collection:
            return

        self.last_search_time = time.time()

        # Start search for each face
        for i, face in enumerate(self.detected_faces):
            if i >= self.max_faces:
                break

            if (
                i not in self.face_search_threads
                or not self.face_search_threads[i].isRunning()
            ):
                self.search_face(i, face)

    def search_face(self, face_index, face):
        """Belirli bir yüz için arama yap"""
        try:
            # Clear any existing database images for this face before starting new search
            if face_index in self.face_db_images:
                print(f"Clearing old database images for face {face_index}")
                del self.face_db_images[face_index]

            # Update face status to searching with error handling
            if face_index < len(self.face_widgets):
                face_widget = self.face_widgets[face_index]
                if (
                    not sip.isdeleted(face_widget)
                    and hasattr(face_widget, "status_label")
                    and not sip.isdeleted(face_widget.status_label)
                ):
                    try:
                        face_widget.status_label.setText("🔍 ARANIYOR")
                        face_widget.status_label.setStyleSheet(
                            """
                            QLabel#faceStatus {
                                color: #FF9800;
                                font-size: 8pt;
                                font-weight: 600;
                                padding: 1px;
                                background: transparent;
                                border: none;
                            }
                        """
                        )
                    except RuntimeError as e:
                        if "wrapped C/C++ object" in str(e):
                            print(
                                f"Face status label {face_index} deleted during search status update"
                            )
                        else:
                            raise

            # Get face embedding
            face_embedding = face.embedding
            if not isinstance(face_embedding, list):
                face_embedding = face_embedding.tolist()

            # Create search thread for this face
            search_thread = SearchThread(
                face_embedding,
                self.milvus_collection,
                self.db_conn,
                self.search_threshold,
                self.max_results,
            )

            # Connect signals with face index
            search_thread.search_completed.connect(
                lambda results, idx=face_index: self.on_face_search_completed(
                    idx, results
                )
            )
            search_thread.search_error.connect(
                lambda error, idx=face_index: self.on_face_search_error(idx, error)
            )
            search_thread.images_loaded.connect(
                lambda images, idx=face_index: self.on_face_images_loaded(idx, images)
            )

            # Store and start thread
            self.face_search_threads[face_index] = search_thread
            search_thread.start()

        except Exception as e:
            self.on_face_search_error(face_index, str(e))

    def on_face_search_completed(self, face_index, results):
        """Yüz arama tamamlandığında çağrılır"""
        # Store results
        self.face_results[face_index] = results

        # Check if any results found
        result_count = len(results[0]) if results and results[0] else 0

        # If no results found, explicitly clear database images for this face
        if result_count == 0:
            print(f"No matches found for face {face_index}, clearing database images")
            if face_index in self.face_db_images:
                del self.face_db_images[face_index]

        # Update face status
        if face_index < len(self.face_widgets):
            face_widget = self.face_widgets[face_index]
            if (
                sip.isdeleted(face_widget)
                or not hasattr(face_widget, "status_label")
                or sip.isdeleted(face_widget.status_label)
            ):
                # print(f"Skipping on_face_search_completed status update for deleted widget at index {face_index}")
                pass  # Skip if widget or label is deleted
            else:
                if result_count > 0:
                    face_widget.status_label.setText(f"✅ {result_count} EŞLEŞME")
                    face_widget.status_label.setStyleSheet(
                        """
                        QLabel#faceStatus {
                            color: #4CAF50;
                            font-size: 8pt;
                            font-weight: 600;
                            padding: 1px;
                            background: transparent;
                            border: none;
                        }
                    """
                    )
                else:
                    face_widget.status_label.setText("❌ EŞLEŞME YOK")
                    face_widget.status_label.setStyleSheet(
                        """
                        QLabel#faceStatus {
                            color: #F44336;
                            font-size: 8pt;
                            font-weight: 600;
                            padding: 1px;
                            background: transparent;
                            border: none;
                        }
                    """
                    )

        # Update statistics
        self.total_searches += 1
        if result_count > 0:
            self.successful_matches += 1

        # Update stats display
        self.stats_label.setText(
            f"📈 İstatistikler: {self.total_searches} arama, {self.successful_matches} eşleşme"
        )

        # If this is the selected face, update the results table
        if face_index == self.selected_face_index:
            self.update_results_table(results)

        # Update selected face display (this will clear DB image if no results)
        self.update_selected_face_display()

    def on_face_search_error(self, face_index, error_message):
        """Yüz arama hatası durumunda çağrılır"""
        # Update face status
        if face_index < len(self.face_widgets):
            face_widget = self.face_widgets[face_index]
            face_widget.status_label.setText("❌ HATA")
            face_widget.status_label.setStyleSheet(
                """
                color: #F44336;
                font-size: 9pt;
                font-weight: 600;
                padding: 2px;
            """
            )

        print(f"Face {face_index} search error: {error_message}")

    def on_face_images_loaded(self, face_index, db_images):
        """Yüz veritabanı görüntüleri yüklendiğinde çağrılır"""
        if face_index not in self.face_db_images:
            self.face_db_images[face_index] = {}
        self.face_db_images[face_index].update(db_images)

        # If this is the selected face, update display
        if face_index == self.selected_face_index:
            self.update_selected_face_display()

    def get_db_image_pixmap_for_face(self, face_index, milvus_id):
        """Belirli yüz için veritabanı görüntüsü QPixmap al"""
        if (
            face_index not in self.face_db_images
            or milvus_id not in self.face_db_images[face_index]
        ):
            return None

        try:
            # Get binary data
            binary_data = self.face_db_images[face_index][milvus_id]
            binary_data = bytes(binary_data)

            # Decode image
            img = decompress_image(binary_data)
            np_image = np.frombuffer(img, dtype=np.uint8)
            img = cv2.imdecode(np_image, cv2.IMREAD_COLOR)

            if img is None:
                return None

            # Convert to QPixmap
            h, w, c = img.shape
            bytes_per_line = c * w
            qt_image = QImage(
                img.data, w, h, bytes_per_line, QImage.Format_RGB888
            ).rgbSwapped()
            pixmap = QPixmap.fromImage(qt_image)

            return pixmap
        except Exception as e:
            print(f"Face {face_index} DB image conversion error: {str(e)}")
            return None

    def update_results_table(self, results):
        """Sonuçlar tablosunu Milvus arama sonuçlarıyla güncelle"""
        try:
            self.results_table.setRowCount(0)
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                print("Results table deleted, skipping update")
                return
            else:
                raise

        if not results or not results[0]:
            try:
                self.results_indicator.setText("📊 0 sonuç bulundu")
            except RuntimeError as e:
                if "wrapped C/C++ object" in str(e):
                    print("Results indicator deleted, skipping update")
                pass
            return

        threshold = self.search_threshold
        filtered_results = []

        # Filter by threshold and sort by similarity
        for hit in results[0]:
            similarity = hit.distance
            if similarity >= threshold:
                filtered_results.append((similarity, hit))

        # Sort by similarity (highest first)
        filtered_results.sort(reverse=True, key=lambda x: x[0])

        # Sonuç sayısını güncelle
        try:
            self.results_indicator.setText(
                f"📊 {len(filtered_results)} sonuç bulundu (Eşik: {threshold:.2f})"
            )
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                print("Results indicator deleted, skipping update")

        # Add to table
        for idx, (similarity, hit) in enumerate(filtered_results[: self.max_results]):
            try:
                self.results_table.insertRow(idx)

                # Milvus ID cell
                id_item = QTableWidgetItem(str(hit.id))
                id_item.setTextAlignment(Qt.AlignCenter)

                # Similarity cell with cyber styling
                similarity_item = QTableWidgetItem(f"{similarity:.3f}")
                similarity_item.setTextAlignment(Qt.AlignCenter)

                # Set background color based on similarity (cyber colors)
                if similarity >= 0.9:
                    color = QColor(0, 255, 0, 80)  # Bright green
                    similarity_item.setToolTip("🟢 ÇOK YÜKSEK EŞLEŞME")
                elif similarity >= 0.8:
                    color = QColor(0, 255, 255, 80)  # Cyan
                    similarity_item.setToolTip("🔵 YÜKSEK EŞLEŞME")
                elif similarity >= 0.7:
                    color = QColor(255, 255, 0, 80)  # Yellow
                    similarity_item.setToolTip("🟡 ORTA EŞLEŞME")
                else:
                    color = QColor(255, 165, 0, 80)  # Orange
                    similarity_item.setToolTip("🟠 DÜŞÜK EŞLEŞME")

                similarity_item.setBackground(color)

                # Gender cell with emojis
                is_male = hit.entity.get("face_gender", False)
                gender = "👨 Erkek" if is_male else "👩 Kadın"
                gender_item = QTableWidgetItem(gender)
                gender_item.setTextAlignment(Qt.AlignCenter)

                # Age cell with emoji
                age = hit.entity.get("face_age", 0)
                age_item = QTableWidgetItem(f"🎂 {age}")
                age_item.setTextAlignment(Qt.AlignCenter)

                self.results_table.setItem(idx, 0, id_item)
                self.results_table.setItem(idx, 1, similarity_item)
                self.results_table.setItem(idx, 2, gender_item)
                self.results_table.setItem(idx, 3, age_item)
            except RuntimeError as e:
                if "wrapped C/C++ object" in str(e):
                    print("Results table deleted during item addition, stopping")
                    return
                else:
                    raise

        # Select the first result if available
        try:
            if self.results_table.rowCount() > 0:
                self.results_table.selectRow(0)
                self.on_result_selected(self.results_table.item(0, 0))
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                print("Results table deleted during selection, skipping")
            else:
                raise

    def on_result_selected(self, item):
        """Tabloda sonuç seçimini işle"""
        if not item:
            return

        try:
            # Get row of selected item
            row = item.row()

            # Get Milvus ID from first column
            milvus_id = int(self.results_table.item(row, 0).text())

            # Display database image for selected face
            face_index = self.selected_face_index
            pixmap = self.get_db_image_pixmap_for_face(face_index, milvus_id)

            if pixmap and not sip.isdeleted(self.selected_db_view):
                try:
                    scaled_pixmap = pixmap.scaled(
                        self.selected_db_view.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                    self.selected_db_view.setPixmap(scaled_pixmap)
                except RuntimeError as e:
                    if "wrapped C/C++ object" in str(e):
                        print("Selected DB view deleted during pixmap update")
                    else:
                        raise
            elif not sip.isdeleted(self.selected_db_view):
                try:
                    self.selected_db_view.clear()
                    self.selected_db_view.setText(
                        "❌ VERİTABANI GÖRÜNTÜSÜ MEVCUT DEĞİL"
                    )
                except RuntimeError as e:
                    if "wrapped C/C++ object" in str(e):
                        print("Selected DB view deleted during clear")
                    else:
                        raise
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e):
                print(
                    "Results table or selected DB view deleted during result selection"
                )
            else:
                print(f"Error in result selection: {str(e)}")

    def manual_search(self):
        """Manuel arama tetikle"""
        if self.detected_faces:
            self.search_all_faces()
        else:
            try:
                self.status_label.setText("⚠️ YÜZ ALGILANMADI")
                self.status_label.setStyleSheet(
                    """
                    background: rgba(255, 193, 7, 0.15);
                    border: 1px solid #FFC107;
                    border-radius: 6px;
                    color: #FFC107;
                    font-size: 12pt;
                    font-weight: 500;
                    padding: 10px 16px;
                """
                )
            except RuntimeError as e:
                if "wrapped C/C++ object" in str(e):
                    print("Status label deleted, skipping manual search status update")
                else:
                    raise

    def toggle_auto_search(self):
        """Otomatik aramayı aç/kapat"""
        if self.auto_search_toggle.isChecked():
            self.auto_search_toggle.setText("🤖 OTOMATİK ARAMA: AKTİF")
            self.auto_search_toggle.setObjectName("cyberButtonActive")
        else:
            self.auto_search_toggle.setText("⏸️ OTOMATİK ARAMA: KAPALI")
            self.auto_search_toggle.setObjectName("cyberButton")

        # Stil yeniden uygula
        self.auto_search_toggle.setStyleSheet("")
        self.apply_cybernetic_theme()

    def update_threshold(self, value):
        """Kaydırıcıdan benzerlik eşiğini güncelle"""
        self.search_threshold = value / 100.0
        self.threshold_label.setText(f"{self.search_threshold:.2f}")

    def update_max_results(self, value):
        """Kaydırıcıdan maksimum sonuç sayısını güncelle"""
        self.max_results = value
        self.max_results_label.setText(f"{self.max_results}")

    def change_camera(self, index):
        """Kamera kaynağını değiştir"""
        if index >= 0:
            self.camera_id = index
            self.camera_thread.change_camera(index)
            self.status_label.setText(f"📹 Kamera {index} 'e geçildi")
            self.status_label.setStyleSheet(
                """
                background: rgba(33, 150, 243, 0.15);
                border: 1px solid #2196F3;
                border-radius: 6px;
                color: #2196F3;
                font-size: 12pt;
                font-weight: 500;
                padding: 10px 16px;
            """
            )

    def connect_manual_camera(self):
        """Manuel kamera adresine bağlan"""
        manual_address = self.manual_camera_input.text().strip()

        if not manual_address:
            self.status_label.setText("⚠️ KAMERA ADRESİ BOŞ")
            self.status_label.setStyleSheet(
                """
                background: rgba(255, 193, 7, 0.15);
                border: 1px solid #FFC107;
                border-radius: 6px;
                color: #FFC107;
                font-size: 12pt;
                font-weight: 500;
                padding: 10px 16px;
            """
            )
            return

        try:
            # Test if it's a number (camera index)
            if manual_address.isdigit():
                camera_source = int(manual_address)
            else:
                camera_source = manual_address

            # Update camera thread with new source
            self.camera_id = camera_source
            self.camera_thread.change_camera(camera_source)

            # Update status
            self.status_label.setText(f"🔗 MANUEL ADRESE BAĞLANILDI")
            self.status_label.setStyleSheet(
                """
                background: rgba(76, 175, 80, 0.15);
                border: 1px solid #4CAF50;
                border-radius: 6px;
                color: #4CAF50;
                font-size: 12pt;
                font-weight: 500;
                padding: 10px 16px;
            """
            )

            # Update button text to show connected
            self.connect_manual_btn.setText("✅ BAĞLI")
            self.connect_manual_btn.setObjectName("cyberButtonActive")
            self.connect_manual_btn.setStyleSheet("")
            self.apply_cybernetic_theme()

        except Exception as e:
            self.status_label.setText(f"❌ BAĞLANTI HATASI")
            self.status_label.setStyleSheet(
                """
                background: rgba(244, 67, 54, 0.15);
                border: 1px solid #F44336;
                border-radius: 6px;
                color: #F44336;
                font-size: 12pt;
                font-weight: 500;
                padding: 10px 16px;
            """
            )

            self.connect_manual_btn.setText("🔗 BAĞLAN")
            self.connect_manual_btn.setObjectName("cyberButton")
            self.connect_manual_btn.setStyleSheet("")
            self.apply_cybernetic_theme()

            print(f"Manuel kamera bağlantı hatası: {str(e)}")

    def update_loading_animation(self):
        """Loading animasyonu güncelle"""
        dots = "." * (self.loading_dots % 4)
        self.search_status.setText(f"🔍 ARAMA YAPILIYOR{dots}")
        self.loading_dots += 1

    def resizeEvent(self, event):
        """Pencere yeniden boyutlandırma işlemini ele al"""
        super().resizeEvent(event)
        if self.current_frame is not None:
            # Update camera view with current frame to maintain aspect ratio
            h, w, c = self.current_frame.shape
            bytes_per_line = c * w
            qt_image = QImage(
                self.current_frame.data, w, h, bytes_per_line, QImage.Format_RGB888
            ).rgbSwapped()
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                self.camera_view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.camera_view.setPixmap(scaled_pixmap)

    def closeEvent(self, event):
        """Pencere kapatma işlemini ele al"""
        # Stop all face search threads
        for thread in self.face_search_threads.values():
            if thread and thread.isRunning():
                thread.terminate()
                thread.wait()

        # Stop loading timer
        if self.loading_timer.isActive():
            self.loading_timer.stop()

        # Stop camera thread
        if self.camera_thread.isRunning():
            self.camera_thread.stop()
            self.camera_thread.wait()

        # Disconnect from databases
        try:
            connections.disconnect("default")
        except:
            pass

        if self.db_conn:
            try:
                self.db_conn.close()
            except:
                pass

        super().closeEvent(event)

    def draw_cyber_hud(self, img, bbox, face_info, match_info, index, color):
        """Futuristic Heads-Up Display drawing"""
        x1, y1, x2, y2 = bbox
        w = x2 - x1
        h = y2 - y1

        # 1. Corner Brackets (instead of full rectangle)
        line_len = int(min(w, h) * 0.25)
        thickness = 2

        # Top-Left
        cv2.line(img, (x1, y1), (x1 + line_len, y1), color, thickness)
        cv2.line(img, (x1, y1), (x1, y1 + line_len), color, thickness)

        # Top-Right
        cv2.line(img, (x2, y1), (x2 - line_len, y1), color, thickness)
        cv2.line(img, (x2, y1), (x2, y1 + line_len), color, thickness)

        # Bottom-Left
        cv2.line(img, (x1, y2), (x1 + line_len, y2), color, thickness)
        cv2.line(img, (x1, y2), (x1, y2 - line_len), color, thickness)

        # Bottom-Right
        cv2.line(img, (x2, y2), (x2 - line_len, y2), color, thickness)
        cv2.line(img, (x2, y2), (x2, y2 - line_len), color, thickness)

        # 2. Scanning Effect (Vertical Line)
        # Use time to animate
        scan_speed = 2.0
        scan_pos = (time.time() * scan_speed) % 1.0  # 0.0 to 1.0
        scan_y = int(y1 + scan_pos * h)

        # Semi-transparent scan line
        overlay = img.copy()
        cv2.line(overlay, (x1, scan_y), (x2, scan_y), color, 4)
        cv2.addWeighted(overlay, 0.3, img, 0.7, 0, img)

        # 3. Data Panel (Side)
        panel_w = 160
        panel_x = x2 + 10
        if panel_x + panel_w > img.shape[1]:
            panel_x = x1 - panel_w - 10  # Switch to left if no space

        # Transparent background for panel
        sub_img = img[
            y1 : min(y1 + 100, img.shape[0]),
            max(0, panel_x) : min(img.shape[1], panel_x + panel_w),
        ]
        white_rect = np.ones(sub_img.shape, dtype=np.uint8) * 0  # Black
        res = cv2.addWeighted(sub_img, 0.4, white_rect, 0.6, 1.0)
        img[
            y1 : min(y1 + 100, img.shape[0]),
            max(0, panel_x) : min(img.shape[1], panel_x + panel_w),
        ] = res

        # Draw Panel Border
        cv2.rectangle(img, (panel_x, y1), (panel_x + panel_w, y1 + 100), color, 1)

        # Text Settings
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.4
        font_color = (255, 255, 255)  # White
        line_spacing = 18

        text_y = y1 + 20
        cv2.putText(
            img,
            f"ID: TARGET-{index+1:02d}",
            (panel_x + 5, text_y),
            font,
            font_scale,
            color,
            1,
        )
        text_y += line_spacing
        cv2.putText(
            img,
            f"GEN: {face_info['gender']}",
            (panel_x + 5, text_y),
            font,
            font_scale,
            font_color,
            1,
        )
        text_y += line_spacing
        cv2.putText(
            img,
            f"AGE: {face_info['age']}",
            (panel_x + 5, text_y),
            font,
            font_scale,
            font_color,
            1,
        )
        text_y += line_spacing

        conf_percent = int(face_info["score"] * 100)
        cv2.putText(
            img,
            f"CONF: {conf_percent}%",
            (panel_x + 5, text_y),
            font,
            font_scale,
            font_color,
            1,
        )

        text_y += line_spacing + 5
        if match_info:
            cv2.putText(
                img, "MATCH FOUND", (panel_x + 5, text_y), font, 0.5, (0, 255, 0), 2
            )
        else:
            # Animated Searching Text
            dots = int(time.time() * 3) % 4
            search_text = "SCANNING" + "." * dots
            cv2.putText(
                img, search_text, (panel_x + 5, text_y), font, 0.4, (255, 255, 0), 1
            )

    def draw_system_overlay(self, img):
        """Draw general system stats on top-left"""
        overlay = img.copy()
        # Header bar
        cv2.rectangle(overlay, (0, 0), (img.shape[1], 30), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)

        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(
            img,
            "EYE OF WEB // SURVEILLANCE SYSTEM v2.0",
            (10, 20),
            font,
            0.5,
            (0, 255, 255),
            1,
        )

        # Time
        current_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        cv2.putText(
            img,
            f"SYS.TIME: {current_time}",
            (img.shape[1] - 200, 20),
            font,
            0.5,
            (0, 255, 0),
            1,
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Uygulama fontu ayarla
    font = QFont("Courier New", 11)
    app.setFont(font)

    # Ana pencereyi oluştur ve göster
    main_window = RealtimeSearchApp()
    main_window.show()

    sys.exit(app.exec_())
