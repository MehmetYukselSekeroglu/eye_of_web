#!/usr/bin/env python3
"""
Face Security v3 — Web App (Flask)

Tkinter masaüstü arayüzünün YERİNE geçer. EyeOfWeb React dashboard'unun
"YÜZ GÜVENLİĞİ" sekmesi tarafından iframe ile gömülmek üzere
http://127.0.0.1:5007/ üzerinde yayın yapar.

Not: User isteği "5005" idi ama 5005 portu React Vite dev server
tarafından kullanılıyor. Çakışmamak için 5007 seçildi; .env'de
`FACE_SEC_PORT` ile override edilebilir.

Kullanılan tüm backend modülleri (camera/detection/database/notifications/
auth) eski main.py ile birebir aynı — sadece UI katmanı değişti.

Endpoint'ler:
    GET  /                  — Ana web arayüzü (HTML)
    GET  /video_feed        — MJPEG canlı kamera akışı
    GET  /api/cameras       — Tanımlı kamera listesi (JSON)
    POST /api/switch        — Aktif kamerayı değiştir ({cam_id})
    POST /api/patrol/start  — Devriye modu (rotasyonlu)
    POST /api/patrol/stop   — Devriye dur
    GET  /api/status        — Sistem durumu (ayakta mı, aktif kamera, yüz sayısı)
    GET  /api/detections    — Son N yüz tespiti (JSON)
    GET  /snapshots/<name>  — Snapshot servisi

Çalıştırma:
    python3 web_app.py
veya `launch.sh` (yeni varsayılan).
"""
from __future__ import annotations

# OpenCL devre dışı bırakma — cv2 import edilmeden ÖNCE env var set edilmeli.
import os
os.environ.setdefault("OPENCV_OPENCL_RUNTIME", "disabled")

import base64
import json
import logging
import queue
import re
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
from flask import Flask, Response, jsonify, render_template, request, send_from_directory

import config
from camera.camera_manager import CameraManager
from camera.stream_handler import StreamHandler
from database.db_manager import DatabaseManager
from detection.embedding_cache import EmbeddingCache
from detection.face_processor import FaceProcessor
from notifications.telegram_bot import TelegramBot
from utils.snapshot_cleaner import SnapshotCleaner
from plate_runner import PlateRunner

# ── Loglama ──────────────────────────────────────────────────────────────────
_log_dir = Path(__file__).parent / "logs"
_log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_log_dir / "web_app.log", mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger("web_app")

# Sessiz Flask access logu — gunicorn-vari spam'i azalt
logging.getLogger("werkzeug").setLevel(logging.WARNING)

# ── OpenCL kapama (AMD Radeon driver bug) ────────────────────────────────────
cv2.ocl.setUseOpenCL(False)

# ── Globaller ────────────────────────────────────────────────────────────────
APP_ROOT = Path(__file__).parent
HOST = os.getenv("FACE_SEC_HOST", "127.0.0.1")
PORT = int(os.getenv("FACE_SEC_PORT", "5007"))

img_queue: queue.Queue = queue.Queue(maxsize=2)
result_queue: queue.Queue = queue.Queue(maxsize=20)
recent_detections: deque = deque(maxlen=50)  # son tespitler — JSON için
_result_drain_thread: threading.Thread | None = None

# Son tespit crop'ları (UI preview için) — JPEG base64 cache
_last_known_crop_b64: str | None = None
_last_known_name: str | None = None
_last_unknown_crop_np = None    # numpy ndarray (save_unknown için)
_last_unknown_crop_b64: str | None = None
_last_unknown_ts: str | None = None

# Yüz arama (patrol search) — Tkinter'daki _start_search eşdeğeri
_search_state = {
    "active": False,
    "target": None,
    "found": False,
    "found_cam": None,
    "found_ts": None,
}
_search_lock = threading.Lock()

# Settings dosya yolları — settings_tab.py'dan ödünç
_ENV_PATH = Path(__file__).parent / ".env"
_ENV_BAK = Path(__file__).parent / ".env.bak"
_ENV_TMP = Path(__file__).parent / ".env.tmp"
_CAM_CONFIG_PATH = Path(__file__).parent / "camera_config.json"
_STARTUP_CONFIG_PATH = Path(__file__).parent / "startup_config.json"
_CAM_URL_RE_PY = re.compile(r"^CAM_(\d{2})_URL=")
_settings_lock = threading.Lock()

stream_handler: StreamHandler | None = None
cam_manager: CameraManager | None = None
db_manager: DatabaseManager | None = None
face_processor: FaceProcessor | None = None
telegram: TelegramBot | None = None
plate_runner: PlateRunner | None = None

_init_lock = threading.Lock()
_initialized = False


def _init_components() -> None:
    """Ağır kaynakları (InsightFace, kameralar) Flask başlamadan ÖNCE yükler."""
    global stream_handler, cam_manager, db_manager, face_processor, telegram
    global plate_runner, _initialized

    with _init_lock:
        if _initialized:
            return

        logger.info("InsightFace modeli yükleniyor (buffalo_s)...")
        face_processor = FaceProcessor(model_name="buffalo_s", det_size=(640, 640))

        logger.info("Embedding önbelleği derleniyor...")
        embedding_cache = EmbeddingCache(
            db_path=config.DATABASE_PATH,
            face_app=face_processor.app,
        )
        embeddings = embedding_cache.build()
        face_processor.load_embeddings(embeddings)
        logger.info("Veritabanı hazır: %d kişi", len(embeddings))

        # Snapshot temizleme
        try:
            cleaner = SnapshotCleaner(
                max_age_days=config.SNAPSHOT_MAX_AGE_DAYS,
                max_files=config.SNAPSHOT_MAX_FILES,
            )
            deleted = cleaner.clean_all(config.KNOWN_PATH, config.UNKNOWN_PATH)
            if deleted:
                logger.info("Snapshot temizliği: %d eski dosya silindi.", deleted)
        except Exception as e:
            logger.warning("Snapshot temizliği başarısız: %s", e)

        # Kamera + StreamHandler
        stream_handler = StreamHandler(
            face_processor=face_processor,
            img_queue=img_queue,
            result_queue=result_queue,
        )
        cam_manager = CameraManager(stream_handler=stream_handler)

        # DB
        db_manager = DatabaseManager(
            db_path=config.DATABASE_PATH,
            face_processor=face_processor,
            embedding_cache=embedding_cache,
        )
        db_manager.db_manager = db_manager  # type: ignore[attr-defined]

        # Telegram (opsiyonel)
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
            logger.info("Telegram devre dışı (env tokens yok).")

        # result_queue drain thread (queue full olmasın + JSON için son tespitler)
        global _result_drain_thread
        _result_drain_thread = threading.Thread(target=_drain_results, daemon=True)
        _result_drain_thread.start()

        # İlk kamerayı otomatik başlat (ayar varsa)
        if config.CAMERAS:
            first_cam_id = sorted(config.CAMERAS.keys())[0]
            try:
                cam_manager.switch(first_cam_id)
                logger.info("Otomatik kamera başlatıldı: cam_id=%s", first_cam_id)
            except Exception as e:
                logger.warning("Otomatik kamera başlatılamadı: %s", e)
        else:
            logger.warning(
                "Hiç kamera URL'i tanımlı değil (.env'de CAM_NN_URL). "
                "Manuel olarak /api/switch çağrılması gerekir."
            )

        # Plate runner (ALPR) — model arka planda async yüklenir, kamera ise
        # kullanıcı toggle açana kadar başlamaz (PLATE_CAM_URL ayrıdır).
        plate_runner = PlateRunner()

        # ── Telegram bot köprüsü ──────────────────────────────────────────
        # Aynı yüz tanıma altyapısındaki TelegramBot instance'ı, plaka
        # tespitlerinde de fotoğraflı bildirim için bağlanır.
        # Bot env'de tanımlı DEĞİLSE (telegram is None) callback set
        # edilmez — try/except içinde sessiz fallback.
        if telegram is not None:
            def _plate_telegram_notify(plate: str, frame, source: str = "whitelist"):
                """
                PlateRunner callback'i — bilinen/bilinmeyen plaka tespitinde
                Telegram'a foto + caption gönderir. send_photo_cv2 zaten
                ayrı thread'de çalışır + hata fırlatmaz (logger'a düşer),
                ama yine de dış try/except koruması var.
                """
                try:
                    if source == "unknown":
                        caption = f"⚠️ BİLİNMEYEN PLAKA\nOCR: {plate}\nWhitelist'te eşleşme yok."
                    else:
                        caption = f"🚗 PLAKA TESPİT\nPlaka: {plate}\nDurum: Whitelist'te tanımlı."
                    if frame is not None:
                        telegram.send_photo_cv2(frame, caption=caption)
                    else:
                        telegram.send_message(caption)
                except Exception as e:
                    logger.warning("Plate Telegram bildirimi gönderilemedi: %s", e)

            try:
                plate_runner.set_notify_callback(_plate_telegram_notify)
                logger.info("Plate → Telegram köprüsü bağlandı.")
            except Exception as e:
                logger.warning("Plate Telegram köprüsü bağlanamadı: %s", e)
        else:
            logger.info("Telegram bot yok (env tokens eksik) — plaka bildirimi devre dışı.")

        if config.PLATE_CAM_URL:
            plate_runner.initialize_async()
            logger.info("Plate runner async init başlatıldı (PLATE_CAM_URL set).")
        else:
            logger.info("PLATE_CAM_URL boş — plate runner pasif, model yüklenmeyecek.")

        _initialized = True


def _drain_results() -> None:
    """result_queue'yu sürekli boşaltıp recent_detections'a yazar (queue full olmasın).
    Ayrıca son known/unknown crop'unu base64 cache'ler ve arama (patrol search)
    aktifse hedef bulununca _search_state'i günceller."""
    global _last_known_crop_b64, _last_known_name
    global _last_unknown_crop_np, _last_unknown_crop_b64, _last_unknown_ts
    while True:
        try:
            r = result_queue.get(timeout=1)
        except queue.Empty:
            continue
        try:
            now_iso = datetime.now().isoformat(timespec="seconds")
            recent_detections.appendleft({
                "name": r.name,
                "score": float(r.score),
                "cam_id": r.cam_id,
                "cam_name": r.cam_name,
                "bbox": list(r.bbox),
                "timestamp": now_iso,
                "snapshot": getattr(r, "snap_path", None),
            })

            # Crop'u base64'le (UI preview için) — küçültülmüş 200x250
            try:
                crop = getattr(r, "crop", None)
                if crop is not None:
                    preview = cv2.resize(crop, (200, 250))
                    ok, jpg = cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ok:
                        b64 = base64.b64encode(jpg.tobytes()).decode("ascii")
                        if r.name == "unknown":
                            _last_unknown_crop_np = crop  # save_person için orijinal
                            _last_unknown_crop_b64 = b64
                            _last_unknown_ts = now_iso
                        else:
                            _last_known_crop_b64 = b64
                            _last_known_name = r.name

                            # Arama aktifse hedef bulundu mu?
                            with _search_lock:
                                if (
                                    _search_state["active"]
                                    and _search_state["target"]
                                    and r.name.lower() == _search_state["target"]
                                ):
                                    _search_state["found"] = True
                                    _search_state["found_cam"] = r.cam_name
                                    _search_state["found_ts"] = now_iso
                                    if telegram is not None:
                                        try:
                                            snap_path = getattr(r, "snap_path", None)
                                            cap = f"🔍 HEDEF BULUNDU\n👤 {r.name.upper()}\n📹 {r.cam_name}"
                                            if snap_path and os.path.exists(snap_path):
                                                telegram.send_photo(snap_path, cap)
                                            else:
                                                telegram.send_message(cap)
                                        except Exception as tg_e:
                                            logger.warning("Search Telegram: %s", tg_e)
            except Exception as crop_err:
                logger.debug("Crop encode hatası: %s", crop_err)

        except Exception as e:
            logger.warning("Detection drain hatası: %s", e)


# ── Flask app ────────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder=str(APP_ROOT / "web_templates"),
    static_folder=str(APP_ROOT / "web_static"),
)


@app.after_request
def _allow_iframe(resp):
    """
    X-Frame-Options başlığını kaldır → iframe'lemeye izin ver.
    EyeOfWeb React dashboard (http://localhost:5005) bu uygulamayı
    aynı host'tan farklı portta iframe ediyor.

    Ayrıca CORS açılır: React (5005) dashboard'u doğrudan
    /api/settings/cameras gibi endpoint'leri fetch edebilsin diye.
    """
    resp.headers.pop("X-Frame-Options", None)
    resp.headers["Content-Security-Policy"] = "frame-ancestors *;"
    # CORS — dev için açık; production'da Origin whitelist daraltılabilir
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Max-Age"] = "3600"
    return resp


# Preflight (OPTIONS) — tüm /api/ rotaları için tek handler
@app.route("/api/<path:_any>", methods=["OPTIONS"])
def _api_preflight(_any):
    return ("", 204)



@app.route("/")
def index():
    return render_template(
        "index.html",
        cameras=sorted(config.CAMERA_NAMES.items()),
        configured_cams=list(config.CAMERAS.keys()),
        host=HOST,
        port=PORT,
    )


def _mjpeg_generator():
    """img_queue'dan kare çekip JPEG olarak multipart akışa basar."""
    boundary = b"--frame"
    last_frame = None
    while True:
        try:
            frame = img_queue.get(timeout=0.5)
            last_frame = frame
        except queue.Empty:
            if last_frame is None:
                # Boş zaman kareleri — siyah placeholder
                import numpy as np
                placeholder = np.zeros((config.DISPLAY_H, config.DISPLAY_W, 3), dtype="uint8")
                cv2.putText(
                    placeholder,
                    "Kamera bekleniyor...",
                    (50, config.DISPLAY_H // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 2,
                )
                frame = placeholder
            else:
                frame = last_frame

        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            continue
        yield boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"


@app.route("/video_feed")
def video_feed():
    return Response(
        _mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.route("/api/cameras")
def api_cameras():
    return jsonify({
        "cameras": [
            {
                "id": cid,
                "name": name,
                "configured": cid in config.CAMERAS,
            }
            for cid, name in sorted(config.CAMERA_NAMES.items())
        ],
        "active": cam_manager.active_cam_id if cam_manager else None,
    })


@app.route("/api/switch", methods=["POST"])
def api_switch():
    if cam_manager is None:
        return jsonify({"error": "Henüz başlatılmadı"}), 503
    data = request.get_json(silent=True) or {}
    cam_id = data.get("cam_id")
    if cam_id is None:
        return jsonify({"error": "cam_id zorunlu"}), 400
    try:
        cam_id = int(cam_id)
    except (TypeError, ValueError):
        return jsonify({"error": "cam_id integer olmalı"}), 400
    if cam_id not in config.CAMERAS:
        return jsonify({"error": f"cam_id {cam_id} için RTSP URL yok"}), 404
    success = cam_manager.switch(cam_id)
    return jsonify({"success": success, "active": cam_manager.active_cam_id})


@app.route("/api/patrol/start", methods=["POST"])
def api_patrol_start():
    if cam_manager is None:
        return jsonify({"error": "Henüz başlatılmadı"}), 503
    return jsonify({"started": cam_manager.start_patrol()})


@app.route("/api/patrol/stop", methods=["POST"])
def api_patrol_stop():
    if cam_manager is None:
        return jsonify({"error": "Henüz başlatılmadı"}), 503
    cam_manager.stop()
    return jsonify({"stopped": True})


@app.route("/api/status")
def api_status():
    return jsonify({
        "ok": True,
        "initialized": _initialized,
        "active_camera": cam_manager.active_cam_id if cam_manager else None,
        "active_camera_name": (
            config.CAMERA_NAMES.get(cam_manager.active_cam_id, "—")
            if (cam_manager and cam_manager.active_cam_id)
            else None
        ),
        "people_known": (
            len(db_manager.list_people()) if db_manager else 0
        ),
        "telegram_active": telegram is not None,
        "recent_detection_count": len(recent_detections),
        "port": PORT,
    })


@app.route("/api/detections")
def api_detections():
    return jsonify(list(recent_detections))


# ── ALPR / Plaka Tanıma endpoint'leri ────────────────────────────────────────


def _plate_mjpeg_generator():
    """Plate kamera frame'lerini JPEG olarak multipart akışa basar."""
    last_frame = None
    boundary = b"--frame"
    placeholder = None
    while True:
        frame = plate_runner.current_frame if plate_runner else None
        if frame is None:
            if placeholder is None:
                import numpy as np
                placeholder = np.zeros((480, 854, 3), dtype="uint8")
                cv2.putText(
                    placeholder,
                    "Plaka kamerasi bekleniyor...",
                    (60, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (160, 160, 160), 2,
                )
            frame = placeholder if last_frame is None else last_frame
        else:
            last_frame = frame
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            time.sleep(0.05)
            continue
        yield boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
        time.sleep(0.05)  # ~20fps cap


@app.route("/plate_feed")
def plate_feed():
    return Response(
        _plate_mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.route("/api/plates/status")
def api_plates_status():
    if plate_runner is None:
        return jsonify({"available": False, "reason": "PlateRunner henüz init edilmedi"})
    s = plate_runner.status
    s["available"] = True
    return jsonify(s)


@app.route("/api/plates/start", methods=["POST"])
def api_plates_start():
    if plate_runner is None:
        return jsonify({"error": "PlateRunner yok"}), 503
    ok, msg = plate_runner.start()
    return jsonify({"success": ok, "message": msg})


@app.route("/api/plates/stop", methods=["POST"])
def api_plates_stop():
    if plate_runner is None:
        return jsonify({"error": "PlateRunner yok"}), 503
    plate_runner.stop()
    return jsonify({"success": True})


@app.route("/api/plates/history")
def api_plates_history():
    """Son tespit edilen plakalar (whitelist + bilinmeyen birlikte)."""
    if plate_runner is None:
        return jsonify([])
    return jsonify([
        {
            "plate": r.plate,
            "source": r.source,        # "whitelist" | "bilinmeyen"
            "timestamp": r.timestamp,
            "full_ts": r.full_ts,
        }
        for r in list(plate_runner.recent_plates)
    ])


@app.route("/api/plates/logs")
def api_plates_logs():
    if plate_runner is None:
        return jsonify([])
    return jsonify(list(plate_runner.recent_logs))


@app.route("/api/plates/whitelist", methods=["GET"])
def api_plates_whitelist_list():
    """UI bölümündeki tanımlı plakaları listeler (read)."""
    if plate_runner is None:
        return jsonify([])
    try:
        items = plate_runner.get_whitelist_entries()
        return jsonify([{"plate": p, "owner": o} for (p, o) in items])
    except Exception as e:
        logger.warning("Whitelist listeleme hatası: %s", e)
        return jsonify([])


@app.route("/api/plates/whitelist", methods=["POST"])
def api_plates_whitelist_add():
    """
    Yeni plaka ekle. Body: {"plate": "34NNF012", "comment": "Anne araba"}.
    `comment` opsiyonel. Plaka otomatik normalize edilir (büyük harf,
    boşluk + tire silinir). Aynı plaka varsa 409, geçersizse 400.
    """
    if plate_runner is None:
        return jsonify({"error": "PlateRunner yok (servis henüz init edilmedi)"}), 503
    data = request.get_json(silent=True) or {}
    plate = data.get("plate", "")
    comment = data.get("comment", "")
    if not isinstance(plate, str):
        return jsonify({"error": "plate string olmalı"}), 400

    ok, msg = plate_runner.add_whitelist_entry(plate, comment if isinstance(comment, str) else "")
    if ok:
        return jsonify({"success": True, "plate": msg, "comment": (comment or "").strip()[:60]}), 201
    # Duplicate vs validation hatası ayrımı
    status = 409 if "zaten" in msg else 400
    return jsonify({"success": False, "error": msg}), status


@app.route("/api/plates/whitelist/<plate>", methods=["DELETE"])
def api_plates_whitelist_delete(plate: str):
    """Belirtilen plakayı UI whitelist bölümünden sil."""
    if plate_runner is None:
        return jsonify({"error": "PlateRunner yok"}), 503
    ok, msg = plate_runner.remove_whitelist_entry(plate)
    if ok:
        return jsonify({"success": True, "plate": msg})
    status = 404 if "bulunamadı" in msg else 400
    return jsonify({"success": False, "error": msg}), status


@app.route("/snapshots/<path:filename>")
def serve_snapshot(filename: str):
    """known/ veya unknown/ altındaki snapshot'ları serve eder."""
    safe = filename.replace("..", "")
    candidates = [
        Path(config.KNOWN_PATH) / safe,
        Path(config.UNKNOWN_PATH) / safe,
        Path(safe),
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return send_from_directory(c.parent, c.name)
    return ("Not found", 404)


# ═══════════════════════════════════════════════════════════════════════════
# SETTINGS — Kamera RTSP URL CRUD (.env atomic) + Test
# ═══════════════════════════════════════════════════════════════════════════


def _read_env_var(key: str) -> str | None:
    """settings_tab._read_env_var web sürümü."""
    try:
        if not _ENV_PATH.exists():
            return None
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1]
    except Exception:
        return None
    return None


def _write_env_cam_urls(new_urls: dict) -> tuple[bool, str]:
    """Atomik .env yazımı. settings_tab._write_env'in thread-safe web kopyası."""
    if not _ENV_PATH.exists():
        return False, f".env bulunamadı: {_ENV_PATH}"
    try:
        with _settings_lock:
            original = _ENV_PATH.read_text(encoding="utf-8")
            lines = original.splitlines(keepends=True)
            seen: set[int] = set()
            out_lines: list[str] = []
            for line in lines:
                m = _CAM_URL_RE_PY.match(line)
                if m:
                    cid = int(m.group(1))
                    if cid in new_urls:
                        seen.add(cid)
                        eol = "\n" if line.endswith("\n") else ""
                        out_lines.append(f"CAM_{cid:02d}_URL={new_urls[cid]}{eol}")
                        continue
                out_lines.append(line)
            # Yeni eklemeler
            missing = [cid for cid in sorted(new_urls) if cid not in seen and new_urls[cid]]
            if missing:
                if out_lines and not out_lines[-1].endswith("\n"):
                    out_lines[-1] = out_lines[-1] + "\n"
                for cid in missing:
                    out_lines.append(f"CAM_{cid:02d}_URL={new_urls[cid]}\n")
            _ENV_BAK.write_text(original, encoding="utf-8")
            _ENV_TMP.write_text("".join(out_lines), encoding="utf-8")
            _ENV_TMP.replace(_ENV_PATH)
        return True, "ok"
    except Exception as e:
        logger.error(".env yazma hatası: %s", e)
        return False, str(e)


@app.route("/api/settings/cameras", methods=["GET"])
def api_settings_cameras_get():
    """25 kameranın isim + URL + etkinlik + startup durumunu döner."""
    enabled = {}
    startup_id = None
    try:
        if _CAM_CONFIG_PATH.exists():
            enabled = json.loads(_CAM_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("camera_config.json okuma: %s", e)
    try:
        if _STARTUP_CONFIG_PATH.exists():
            startup_id = json.loads(_STARTUP_CONFIG_PATH.read_text(encoding="utf-8")).get("startup_id")
    except Exception as e:
        logger.warning("startup_config.json okuma: %s", e)

    rows = []
    for cid in range(1, 26):
        rows.append({
            "id": cid,
            "name": config.CAMERA_NAMES.get(cid, str(cid)),
            "url": _read_env_var(f"CAM_{cid:02d}_URL") or "",
            "enabled": bool(enabled.get(str(cid), True)),
            "is_startup": (startup_id == cid),
            "is_active": (cam_manager.active_cam_id == cid) if cam_manager else False,
        })
    return jsonify({"cameras": rows, "startup_id": startup_id})


@app.route("/api/settings/cameras", methods=["POST"])
def api_settings_cameras_save():
    """Bulk update: {urls: {"1": "rtsp://...", "2": ""}}"""
    data = request.get_json(silent=True) or {}
    urls = data.get("urls") or {}
    if not isinstance(urls, dict):
        return jsonify({"error": "urls dict olmalı"}), 400
    parsed: dict[int, str] = {}
    for k, v in urls.items():
        try:
            cid = int(k)
        except (TypeError, ValueError):
            continue
        if not (1 <= cid <= 25):
            continue
        parsed[cid] = (v or "").strip() if isinstance(v, str) else ""

    if not parsed:
        return jsonify({"error": "Geçerli kamera id bulunamadı"}), 400

    ok, msg = _write_env_cam_urls(parsed)
    if not ok:
        return jsonify({"error": msg}), 500

    # Runtime config.CAMERAS güncellemesi + aktif kameranın yeniden bağlanması
    changed = []
    for cid, url in parsed.items():
        old = config.CAMERAS.get(cid, "")
        if url:
            config.CAMERAS[cid] = url
        else:
            config.CAMERAS.pop(cid, None)
        if url != old:
            changed.append(cid)

    if cam_manager and cam_manager.active_cam_id in changed:
        try:
            active = cam_manager.active_cam_id
            cam_manager.active_cam_id = None
            cam_manager.switch(active)
            logger.info("Aktif kamera (#%s) yeni URL ile yeniden bağlandı.", active)
        except Exception as e:
            logger.warning("Aktif kamera yeniden bağlanamadı: %s", e)

    return jsonify({"success": True, "changed": changed, "count": len(changed)})


@app.route("/api/settings/cameras/test", methods=["POST"])
def api_settings_cameras_test():
    """Tek URL'yi probe et — VideoCapture 3sn timeout, 1 frame okuma."""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "URL boş"}), 400
    try:
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        try:
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000)
        except Exception:
            pass
        ok = False
        if cap.isOpened():
            ret, _frame = cap.read()
            ok = bool(ret)
        cap.release()
        return jsonify({"ok": ok})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════
# SETTINGS — Kamera etkinleştirme + Startup config (json persist)
# ═══════════════════════════════════════════════════════════════════════════


@app.route("/api/settings/cam_enabled", methods=["POST"])
def api_settings_cam_enabled():
    """{cam_id, enabled} — camera_config.json'a yaz."""
    data = request.get_json(silent=True) or {}
    cam_id = data.get("cam_id")
    enabled = data.get("enabled")
    try:
        cam_id = int(cam_id)
    except (TypeError, ValueError):
        return jsonify({"error": "cam_id int olmalı"}), 400
    if not (1 <= cam_id <= 25):
        return jsonify({"error": "cam_id 1-25 aralığında olmalı"}), 400
    if not isinstance(enabled, bool):
        return jsonify({"error": "enabled bool olmalı"}), 400

    try:
        with _settings_lock:
            cfg = {}
            if _CAM_CONFIG_PATH.exists():
                try:
                    cfg = json.loads(_CAM_CONFIG_PATH.read_text(encoding="utf-8"))
                except Exception:
                    cfg = {}
            cfg[str(cam_id)] = enabled
            _CAM_CONFIG_PATH.write_text(
                json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        return jsonify({"success": True, "cam_id": cam_id, "enabled": enabled})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/settings/startup_cam", methods=["POST"])
def api_settings_startup_cam():
    """Otomatik başlangıç kamerasını ayarla. {startup_id: int|null}"""
    data = request.get_json(silent=True) or {}
    sid = data.get("startup_id")
    if sid is not None:
        try:
            sid = int(sid)
            if not (1 <= sid <= 25):
                return jsonify({"error": "startup_id 1-25 veya null"}), 400
        except (TypeError, ValueError):
            return jsonify({"error": "startup_id int veya null olmalı"}), 400
    try:
        with _settings_lock:
            _STARTUP_CONFIG_PATH.write_text(
                json.dumps({"startup_id": sid}, indent=2), encoding="utf-8"
            )
        return jsonify({"success": True, "startup_id": sid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# RUNTIME CONFIG — Threshold + FPS gibi ayarlar (anlık)
# ═══════════════════════════════════════════════════════════════════════════


@app.route("/api/settings/runtime", methods=["GET"])
def api_settings_runtime_get():
    """Mevcut runtime config (config modülünden okur)."""
    return jsonify({
        "threshold": getattr(config, "THRESHOLD", 0.45),
        "inference_fps": getattr(config, "INFERENCE_FPS", 4),
        "snapshot_cooldown": getattr(config, "SNAPSHOT_COOLDOWN", 20),
        "patrol_scan_seconds": getattr(config, "PATROL_SCAN_SECONDS", 10),
        "patrol_hold_seconds": getattr(config, "PATROL_HOLD_SECONDS", 20),
    })


@app.route("/api/settings/runtime", methods=["POST"])
def api_settings_runtime_set():
    """Runtime config değiştir. {key: value} — config modülünde set + log."""
    data = request.get_json(silent=True) or {}
    allowed = {
        "threshold": (float, 0.1, 0.99),
        "inference_fps": (int, 1, 30),
        "snapshot_cooldown": (int, 1, 600),
        "patrol_scan_seconds": (int, 1, 120),
        "patrol_hold_seconds": (int, 1, 600),
    }
    updates = {}
    for k, v in data.items():
        if k not in allowed:
            continue
        cast, lo, hi = allowed[k]
        try:
            val = cast(v)
        except (TypeError, ValueError):
            return jsonify({"error": f"{k} {cast.__name__} olmalı"}), 400
        if not (lo <= val <= hi):
            return jsonify({"error": f"{k} {lo}-{hi} aralığında olmalı"}), 400
        # config modülünde attribute set (runtime)
        attr = k.upper()
        if hasattr(config, attr):
            setattr(config, attr, val)
            updates[k] = val
    return jsonify({"success": True, "updated": updates})


# ═══════════════════════════════════════════════════════════════════════════
# FACE DB — kişiler listesi, son unknown crop, save, photo serve
# ═══════════════════════════════════════════════════════════════════════════


@app.route("/api/faces/people", methods=["GET"])
def api_faces_people():
    """Veritabanındaki kişi isimleri."""
    if db_manager is None:
        return jsonify({"people": []})
    try:
        return jsonify({"people": db_manager.list_people()})
    except Exception as e:
        return jsonify({"people": [], "error": str(e)})


@app.route("/api/faces/last_unknown", methods=["GET"])
def api_faces_last_unknown():
    """Son tespit edilen bilinmeyen yüzün JPEG base64 + timestamp."""
    return jsonify({
        "available": _last_unknown_crop_b64 is not None,
        "image_b64": _last_unknown_crop_b64,
        "timestamp": _last_unknown_ts,
    })


@app.route("/api/faces/last_known", methods=["GET"])
def api_faces_last_known():
    """Son tespit edilen bilinen yüzün JPEG base64 + adı."""
    return jsonify({
        "available": _last_known_crop_b64 is not None,
        "name": _last_known_name,
        "image_b64": _last_known_crop_b64,
    })


@app.route("/api/faces/register", methods=["POST"])
def api_faces_register():
    """
    Aktif kameradan o anki frame'i yakalayıp `{name}` ile DB'ye kaydeder.

    Akış:
      1) JSON body'den `name` al, alfanumerik+boşluk sanitize et.
      2) StreamHandler.last_frame_raw'dan full-res frame kopyala (frame_lock altında).
      3) face_processor.get_faces(frame) → tek yüz değilse 400.
      4) Frame'i config.DATABASE_PATH/<safe>.jpg olarak yaz (db_manager.save_person).
         save_person zaten EmbeddingCache invalidate + reload yapar — uygulamayı
         yeniden başlatmaya gerek YOK.

    Hata kodları:
      503 — stream/face_processor/db_manager hazır değil
      400 — geçersiz isim / yüz sayısı uygun değil / DB save_person fail
      200 — başarılı, embedding'lere eklendi
    """
    if (
        face_processor is None
        or db_manager is None
        or stream_handler is None
    ):
        return jsonify({"error": "Servis henüz hazır değil (model yükleniyor)"}), 503

    data = request.get_json(silent=True) or {}
    raw_name = data.get("name", "")
    if not isinstance(raw_name, str):
        return jsonify({"error": "name string olmalı"}), 400

    # Sunucu-tarafı sanitization (frontend zaten temizler ama defansif katman):
    # sadece harf, rakam, boşluk; sonra alt çizgiye dönüştür ve lowercase.
    cleaned = re.sub(r"[^a-zA-Z0-9çÇğĞıİöÖşŞüÜ\s]", "", raw_name).strip()
    if not cleaned or len(cleaned) > 50:
        return jsonify({"error": "İsim 1-50 karakter olmalı (sadece harf/rakam)"}), 400

    # Aktif kameradan son full-res frame'i kilit altında al
    frame = None
    try:
        with stream_handler.frame_lock:
            if stream_handler.last_frame_raw is not None:
                frame = stream_handler.last_frame_raw.copy()
    except Exception as e:
        return jsonify({"error": f"Frame yakalama hatası: {e}"}), 500

    if frame is None:
        return jsonify({
            "error": "Aktif kamera frame'i yok. Önce bir kamera seçin "
                     "ve birkaç saniye bekleyin."
        }), 400

    # Yüz tespiti — InsightFace
    try:
        faces = face_processor.get_faces(frame)
    except Exception as e:
        return jsonify({"error": f"Yüz tespit motoru hatası: {e}"}), 500

    if not faces:
        return jsonify({
            "error": "Yüz tespit edilemedi. Kameraya net bakın ve tekrar deneyin."
        }), 400
    if len(faces) > 1:
        return jsonify({
            "error": f"Karede {len(faces)} yüz var; tek bir kişi olmalı.",
            "face_count": len(faces),
        }), 400

    # Kayıt — db_manager.save_person tüm frame'i yazar + EmbeddingCache reload eder
    try:
        ok, safe_name = db_manager.save_person(cleaned, frame)
        if not ok:
            return jsonify({
                "error": "DB save_person başarısız (geçersiz isim veya I/O)"
            }), 400
    except Exception as e:
        return jsonify({"error": f"Kayıt hatası: {e}"}), 500

    logger.info(
        "Yeni yüz kaydedildi: %s (frame %dx%d, embedding sayısı: %d)",
        safe_name, frame.shape[1], frame.shape[0],
        len(face_processor.known_faces),
    )
    return jsonify({
        "success": True,
        "name": safe_name,
        "embeddings_total": len(face_processor.known_faces),
    })


@app.route("/api/faces/save_unknown", methods=["POST"])
def api_faces_save_unknown():
    """Son bilinmeyen crop'a isim verip DB'ye kaydet."""
    if db_manager is None:
        return jsonify({"error": "DB manager hazır değil"}), 503
    if _last_unknown_crop_np is None:
        return jsonify({"error": "Henüz bilinmeyen yüz tespit edilmedi"}), 404
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name or len(name) > 50:
        return jsonify({"error": "İsim 1-50 karakter olmalı"}), 400
    try:
        ok, safe_name = db_manager.save_person(name, _last_unknown_crop_np)
        if not ok:
            return jsonify({"error": "DB save_person başarısız (geçersiz isim?)"}), 400
        return jsonify({"success": True, "name": safe_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/faces/photo/<name>")
def api_faces_photo(name: str):
    """Kişi referans fotoğrafı (DATABASE_PATH/<name>.jpg|png|jpeg)."""
    safe = re.sub(r"[^a-z0-9_-]", "", name.lower())
    if not safe:
        return ("Bad name", 400)
    db_dir = Path(config.DATABASE_PATH)
    for ext in (".jpg", ".png", ".jpeg"):
        p = db_dir / f"{safe}{ext}"
        if p.exists():
            return send_from_directory(p.parent, p.name)
    return ("Not found", 404)


@app.route("/api/faces/delete/<name>", methods=["DELETE"])
def api_faces_delete(name: str):
    """Kişiye ait tüm görselleri DB'den sil + reload."""
    if db_manager is None:
        return jsonify({"error": "DB manager hazır değil"}), 503
    safe = re.sub(r"[^a-z0-9_-]", "", name.lower())
    if not safe:
        return jsonify({"error": "Geçersiz isim"}), 400
    db_dir = Path(config.DATABASE_PATH)
    deleted = 0
    try:
        for f in db_dir.iterdir():
            stem = f.stem.lower()
            base = stem.rsplit("_", 1)[0] if stem[-1:].isdigit() else stem
            if base == safe:
                try:
                    f.unlink()
                    deleted += 1
                except Exception:
                    pass
        if deleted:
            try:
                db_manager.cache.invalidate()
            except Exception:
                pass
            try:
                db_manager.reload()
            except Exception:
                pass
        return jsonify({"success": True, "deleted": deleted, "name": safe})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/faces/reload", methods=["POST"])
def api_faces_reload():
    """DB cache'i temizle, embedding'leri yeniden derle."""
    if db_manager is None:
        return jsonify({"error": "DB manager hazır değil"}), 503
    try:
        db_manager.cache.invalidate()
        n = db_manager.reload()
        return jsonify({"success": True, "people": n})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# FACE SEARCH (patrol modu) — Tkinter _start_search eşdeğeri
# ═══════════════════════════════════════════════════════════════════════════


@app.route("/api/faces/search/start", methods=["POST"])
def api_faces_search_start():
    if cam_manager is None or db_manager is None:
        return jsonify({"error": "Henüz hazır değil"}), 503
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip().lower()
    if not name:
        return jsonify({"error": "name boş olamaz"}), 400
    if not db_manager.person_exists(name):
        return jsonify({"error": f"{name.upper()} DB'de yok"}), 404

    with _search_lock:
        _search_state["active"] = True
        _search_state["target"] = name
        _search_state["found"] = False
        _search_state["found_cam"] = None
        _search_state["found_ts"] = None

    try:
        cam_manager.start_patrol()
    except Exception as e:
        logger.warning("start_patrol hatası: %s", e)

    return jsonify({"success": True, "target": name})


@app.route("/api/faces/search/stop", methods=["POST"])
def api_faces_search_stop():
    with _search_lock:
        _search_state["active"] = False
        # found/target log için tutulur, sadece active off
    if cam_manager is not None:
        try:
            cam_manager.stop()
        except Exception:
            pass
    return jsonify({"success": True})


@app.route("/api/faces/search/status")
def api_faces_search_status():
    with _search_lock:
        return jsonify(dict(_search_state))


# ═══════════════════════════════════════════════════════════════════════════
# LOGS — listele + indir
# ═══════════════════════════════════════════════════════════════════════════


_LOG_DIR_PATH = Path(__file__).parent / "logs"


@app.route("/api/logs/files")
def api_logs_files():
    """logs/ altındaki dosya listesi (.log, .txt) — boyut + mtime."""
    items = []
    try:
        if _LOG_DIR_PATH.exists():
            for f in sorted(_LOG_DIR_PATH.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if f.is_file() and f.suffix.lower() in (".log", ".txt"):
                    st = f.stat()
                    items.append({
                        "name": f.name,
                        "size": st.st_size,
                        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                    })
    except Exception as e:
        return jsonify({"files": [], "error": str(e)})
    return jsonify({"files": items})


@app.route("/api/logs/download/<name>")
def api_logs_download(name: str):
    """Log dosyası indir (path traversal koruması)."""
    safe = name.replace("..", "").replace("/", "").replace("\\", "")
    target = _LOG_DIR_PATH / safe
    if not target.exists() or not target.is_file():
        return ("Not found", 404)
    if target.suffix.lower() not in (".log", ".txt"):
        return ("Forbidden type", 403)
    return send_from_directory(_LOG_DIR_PATH, safe, as_attachment=True)


@app.route("/api/logs/tail/<name>")
def api_logs_tail(name: str):
    """Log dosyasının son N satırı (default 200)."""
    safe = name.replace("..", "").replace("/", "").replace("\\", "")
    target = _LOG_DIR_PATH / safe
    if not target.exists() or not target.is_file():
        return jsonify({"error": "not found"}), 404
    try:
        n = max(1, min(int(request.args.get("n", "200")), 2000))
    except Exception:
        n = 200
    try:
        # Bellek dostu son N satır
        with target.open("rb") as f:
            # Naif ama makul: dosyayı oku ve son N satırı al
            content = f.read().decode("utf-8", errors="replace")
        lines = content.splitlines()
        return jsonify({"name": safe, "lines": lines[-n:], "total": len(lines)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def main() -> None:
    _init_components()
    logger.info("Flask sunucusu başlıyor: http://%s:%s/", HOST, PORT)
    # debug=False — production-vari; use_reloader=False — init iki kez koşmasın
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
