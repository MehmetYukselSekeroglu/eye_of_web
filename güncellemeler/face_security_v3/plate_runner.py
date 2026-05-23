"""
Face Security v3 — Plaka Tanıma (ALPR) Web Runner

Eski Tkinter `ui/plate_tab.py` mantığının headless/web sürümü.
Tkinter import etmez; sadece detection modüllerini kullanır ve durumu
(`status`, `recent_plates`, `current_frame`) Flask endpoint'leri için
expose eder.

Akış (özet):
  1. `initialize()` — PlateProcessor (YOLO + EasyOCR) yüklenir.
  2. `start()` — kamera + analiz thread'leri başlatılır.
  3. Camera thread: RTSP → motion detection → analysis_queue'ya frame.
  4. Analysis thread: process_frame → result_queue (plate, boxes, crop).
  5. Drain thread: result_queue → history + current_frame (bbox çizilmiş).

Endpoint'ler için API:
  • runner.status          -> dict
  • runner.recent_plates   -> deque
  • runner.current_frame   -> np.ndarray | None
  • runner.start()/.stop() -> idempotent toggle
"""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

import config
from detection.plate_processor import PlateProcessor
from detection.plate_whitelist import (
    get_ui_plates,
    save_whitelist,
    normalize_plate,
)

logger = logging.getLogger("plate_runner")

# Whitelist dosya yolu — PlateProcessor ile aynı kaynaktan
WHITELIST_PATH = os.environ.get("PLATE_WHITELIST_PATH", "config/plate_whitelist.txt")

# Sabitler — plate_tab.py'dan birebir
CAM_W, CAM_H = 854, 480
_ANALYSIS_W, _ANALYSIS_H = 1280, 720
_MOTION_W, _MOTION_H = 160, 90
_MOTION_THRESHOLD = 25
_MOTION_MIN_PIXELS = 500
_MOTION_REF_INTERVAL = 2.0
_ANALYSIS_INTERVAL = 0.3
_STATIC_INTERVAL = 2.0


@dataclass
class PlateReading:
    plate: str
    source: str          # "whitelist" | "bilinmeyen"
    timestamp: str       # "HH:MM:SS"
    full_ts: str         # "YYYY-MM-DD HH:MM:SS"


@dataclass
class PlateStatus:
    initialized: bool = False
    initializing: bool = False
    active: bool = False           # toggle açık mı (kamera + analiz çalışıyor)
    motion_detected: bool = False
    collection_progress: int = 0   # 0..10 (PlateProcessor.collection_progress)
    last_plate: Optional[str] = None
    last_plate_ts: Optional[str] = None
    vehicle_count: int = 0
    error: Optional[str] = None
    camera_connected: bool = False
    plate_cam_url_set: bool = field(default_factory=lambda: bool(getattr(config, "PLATE_CAM_URL", "")))


class PlateRunner:
    """Singleton-vari plate ALPR koordinatörü. Flask global olarak tutar."""

    def __init__(self) -> None:
        self._processor: Optional[PlateProcessor] = None
        self._status = PlateStatus()
        self._status_lock = threading.Lock()

        self._analysis_queue: queue.Queue = queue.Queue(maxsize=2)
        self._result_queue: queue.Queue = queue.Queue(maxsize=10)

        self._cam_thread: Optional[threading.Thread] = None
        self._anal_thread: Optional[threading.Thread] = None
        self._drain_thread: Optional[threading.Thread] = None

        self._running = False
        self._frame_lock = threading.Lock()
        self._current_frame: Optional[np.ndarray] = None
        self._last_result: Optional[dict] = None
        self._prev_gray = None
        self._motion_ref_time = 0.0
        self._last_analysis_time = 0.0

        # API'den okunacak son tespit listeleri (kalıcı)
        self.recent_plates: deque[PlateReading] = deque(maxlen=50)

        # Process-level log mesajları (JSON endpoint için)
        self.recent_logs: deque[dict] = deque(maxlen=100)

        # Telegram opsiyonel callback (FaceSecurity ile aynı bot kullanılabilir)
        self._notify_callback = None

        # Plate log dosyası
        self._log_file = Path(__file__).parent / "logs" / "plate_readings.log"
        self._log_file.parent.mkdir(exist_ok=True)

        # Whitelist eşzamanlılık kilidi — UI add/delete sırasında
        # read-modify-write atomicliği sağlar. Worker thread'in
        # match_plate çağrısı liste-okuma (atomic GIL), kilide girmez.
        self._whitelist_lock = threading.Lock()

    # ────────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ────────────────────────────────────────────────────────────────────────

    @property
    def status(self) -> dict:
        with self._status_lock:
            d = asdict(self._status)
        if self._processor is not None:
            d["collection_progress"] = self._processor.collection_progress
            d["initialized"] = self._processor.ready
            d["error"] = self._processor.error
        return d

    @property
    def current_frame(self) -> Optional[np.ndarray]:
        with self._frame_lock:
            return None if self._current_frame is None else self._current_frame.copy()

    def set_notify_callback(self, cb) -> None:
        self._notify_callback = cb

    def initialize_async(self) -> None:
        """Model yüklemeyi non-blocking başlat. İlk start()'ta otomatik çağrılır."""
        with self._status_lock:
            if self._status.initialized or self._status.initializing:
                return
            self._status.initializing = True

        def _worker():
            try:
                self._log("system", "YOLO + EasyOCR yükleniyor...")
                # unknown_plate_callback ile PlateProcessor bilinmeyen plaka
                # kaydettiğinde report_unknown'ı tetikler → arayüze pembe
                # satır + Telegram bildirimi (notify_callback ayarlıysa).
                self._processor = PlateProcessor(
                    unknown_plate_callback=self.report_unknown,
                )
                ok = self._processor.initialize()
                with self._status_lock:
                    self._status.initializing = False
                    self._status.initialized = ok
                    self._status.error = None if ok else (self._processor.error or "model yüklenemedi")
                if ok:
                    self._log("info", "Model hazır. Toggle açık ise kamera başlayacak.")
                else:
                    self._log("error", f"Model hatası: {self._status.error}")
            except Exception as e:
                logger.exception("PlateProcessor init exception")
                with self._status_lock:
                    self._status.initializing = False
                    self._status.error = str(e)
                self._log("error", f"İlklendirme istisnası: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def start(self) -> tuple[bool, str]:
        """Toggle ON — kamera + analiz başlat. Idempotent."""
        if not config.PLATE_CAM_URL:
            return False, ".env içinde PLATE_CAM_URL tanımlı değil."

        # Model henüz yüklenmediyse arka planda başlat
        if self._processor is None or not self._processor.ready:
            self.initialize_async()

        if self._running:
            return True, "zaten çalışıyor"

        self._running = True
        with self._status_lock:
            self._status.active = True
            self._status.camera_connected = False
        self._prev_gray = None
        self._motion_ref_time = 0.0
        self._last_analysis_time = 0.0
        self._last_result = None

        self._cam_thread = threading.Thread(
            target=self._camera_loop, args=(config.PLATE_CAM_URL,), daemon=True
        )
        self._cam_thread.start()

        self._anal_thread = threading.Thread(target=self._analysis_loop, daemon=True)
        self._anal_thread.start()

        if self._drain_thread is None or not self._drain_thread.is_alive():
            self._drain_thread = threading.Thread(target=self._result_drain_loop, daemon=True)
            self._drain_thread.start()

        self._log("plate", "Plaka tanıma sistemi AKTİF edildi.")
        return True, "ok"

    def stop(self) -> None:
        """Toggle OFF — kamera + analiz dur."""
        if not self._running:
            return
        self._running = False
        with self._status_lock:
            self._status.active = False
            self._status.camera_connected = False
        if self._processor is not None:
            try:
                self._processor.reset()
            except Exception:
                pass
        with self._frame_lock:
            self._current_frame = None
        self._log("warn", "Plaka tanıma sistemi PASİF edildi.")

    # ────────────────────────────────────────────────────────────────────────
    # CAMERA LOOP
    # ────────────────────────────────────────────────────────────────────────

    def _camera_loop(self, url: str) -> None:
        cap = cv2.VideoCapture(url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            self._log("error", "Kamera bağlantısı kurulamadı (PLATE_CAM_URL)")
            self._running = False
            with self._status_lock:
                self._status.active = False
                self._status.camera_connected = False
            return

        with self._status_lock:
            self._status.camera_connected = True
        self._log("info", "Kamera bağlandı.")

        while self._running:
            cap.grab()
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            now = time.time()
            try:
                u_frame = cv2.UMat(frame)
                u_small_gray = cv2.resize(
                    cv2.cvtColor(u_frame, cv2.COLOR_BGR2GRAY),
                    (_MOTION_W, _MOTION_H),
                )
            except Exception:
                continue

            has_motion = False
            if self._prev_gray is not None:
                try:
                    u_diff = cv2.absdiff(self._prev_gray, u_small_gray)
                    _, u_mask = cv2.threshold(u_diff, _MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)
                    motion_pixels = cv2.countNonZero(u_mask)
                    has_motion = motion_pixels > _MOTION_MIN_PIXELS
                except Exception:
                    has_motion = False

            if now - self._motion_ref_time >= _MOTION_REF_INTERVAL:
                self._prev_gray = u_small_gray
                self._motion_ref_time = now

            with self._status_lock:
                self._status.motion_detected = has_motion

            try:
                display = cv2.resize(u_frame, (CAM_W, CAM_H)).get()
            except Exception:
                continue

            with self._frame_lock:
                self._current_frame = display

            interval = _ANALYSIS_INTERVAL if has_motion else _STATIC_INTERVAL
            if (now - self._last_analysis_time) >= interval:
                self._last_analysis_time = now
                try:
                    self._analysis_queue.put_nowait(frame)
                except queue.Full:
                    pass

        cap.release()
        with self._status_lock:
            self._status.camera_connected = False

    # ────────────────────────────────────────────────────────────────────────
    # ANALYSIS LOOP
    # ────────────────────────────────────────────────────────────────────────

    def _analysis_loop(self) -> None:
        while self._running:
            try:
                frame = self._analysis_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if self._processor is None or not self._processor.ready:
                continue

            try:
                small = cv2.resize(frame, (_ANALYSIS_W, _ANALYSIS_H))
                plate, boxes, crop = self._processor.process_frame(small)
            except Exception as e:
                logger.warning("process_frame istisna: %s", e)
                continue

            # Toplama ilerlemesi
            try:
                n = self._processor.collection_progress
                if n > 0 and n % 5 == 0:
                    self._log("system", f"Frame toplama: {n}/10")
            except Exception:
                pass

            result = {"plate": plate, "boxes": boxes}
            try:
                self._result_queue.put_nowait(result)
            except queue.Full:
                try:
                    self._result_queue.get_nowait()
                    self._result_queue.put_nowait(result)
                except Exception:
                    pass

    # ────────────────────────────────────────────────────────────────────────
    # RESULT DRAIN LOOP — history + frame overlay
    # ────────────────────────────────────────────────────────────────────────

    def _result_drain_loop(self) -> None:
        while True:
            try:
                result = self._result_queue.get(timeout=0.5)
            except queue.Empty:
                # Yine de motion_detected ve collection_progress son durumu güncelle
                if self._processor is not None:
                    with self._status_lock:
                        self._status.collection_progress = self._processor.collection_progress
                continue

            self._last_result = result
            boxes = result.get("boxes", []) or []
            plate = result.get("plate")

            with self._status_lock:
                self._status.vehicle_count = len(boxes)

            # Frame'e bbox çiz
            with self._frame_lock:
                if self._current_frame is not None and boxes:
                    display = self._current_frame
                    for (x1, y1, x2, y2) in boxes:
                        rx1 = int(x1 * CAM_W / _ANALYSIS_W)
                        ry1 = int(y1 * CAM_H / _ANALYSIS_H)
                        rx2 = int(x2 * CAM_W / _ANALYSIS_W)
                        ry2 = int(y2 * CAM_H / _ANALYSIS_H)
                        cv2.rectangle(display, (rx1, ry1), (rx2, ry2), (0, 180, 255), 2)
                        cv2.putText(
                            display, "ARAC",
                            (rx1, max(0, ry1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 180, 255), 1,
                        )

            if plate:
                self._on_plate_detected(plate)

    # ────────────────────────────────────────────────────────────────────────
    # PLATE EVENTS
    # ────────────────────────────────────────────────────────────────────────

    def _on_plate_detected(self, plate: str) -> None:
        now = datetime.now()
        ts = now.strftime("%H:%M:%S")
        full_ts = now.strftime("%Y-%m-%d %H:%M:%S")

        reading = PlateReading(plate=plate, source="whitelist", timestamp=ts, full_ts=full_ts)
        self.recent_plates.appendleft(reading)

        with self._status_lock:
            self._status.last_plate = plate
            self._status.last_plate_ts = ts

        self._log("plate", f"✅ PLAKA TESPİT: {plate}")

        try:
            with self._log_file.open("a", encoding="utf-8") as fh:
                fh.write(f"[{full_ts}] PLAKA: {plate}\n")
        except Exception as e:
            logger.warning("Plate log dosyası yazılamadı: %s", e)

        self._fire_notify(plate, self.current_frame, "whitelist")

    def report_unknown(self, ham_plate: str) -> None:
        """
        PlateProcessor `unknown_plate_callback` parametresiyle çağrılır
        (whitelist eşleşmesi yok ama OCR oylaması geçti). Arayüzdeki
        "Son plakalar" listesine `bilinmeyen` rozetiyle düşer + Telegram
        notify_callback varsa tetiklenir.
        """
        now = datetime.now()
        ts = now.strftime("%H:%M:%S")
        reading = PlateReading(
            plate=ham_plate, source="bilinmeyen", timestamp=ts,
            full_ts=now.strftime("%Y-%m-%d %H:%M:%S"),
        )
        self.recent_plates.appendleft(reading)
        self._log("warn", f"⚠️ Bilinmeyen plaka: {ham_plate}")

        self._fire_notify(ham_plate, self.current_frame, "unknown")

    def _fire_notify(self, plate: str, frame, source: str) -> None:
        """
        notify_callback'i source='whitelist'|'unknown' bilgisiyle çağırır.
        Eski 2-arg callback imzalarını (frame, plate) graceful destekler.
        Callback hata fırlatırsa SADECE log'a düşer — runner thread'i
        asla bozulmaz.
        """
        if self._notify_callback is None:
            return
        try:
            try:
                self._notify_callback(plate, frame, source)
            except TypeError:
                # Eski 2-arg callback imzası fallback
                self._notify_callback(plate, frame)
        except Exception as e:
            logger.warning("notify_callback hatası (%s, %s): %s", source, plate, e)

    # ────────────────────────────────────────────────────────────────────────
    # WHITELIST CRUD (UI bölümü)
    # ────────────────────────────────────────────────────────────────────────

    def _resolve_whitelist_path(self) -> str:
        """Processor yüklendiyse onun path'ini kullan, yoksa env/default'a düş."""
        if self._processor is not None and getattr(self._processor, "_whitelist_path", None):
            return self._processor._whitelist_path
        return WHITELIST_PATH

    def get_whitelist_entries(self) -> list[tuple[str, str]]:
        """Whitelist'in UI bölümündeki tüm (plate, comment) çiftlerini döner."""
        path = self._resolve_whitelist_path()
        with self._whitelist_lock:
            return get_ui_plates(path)

    def add_whitelist_entry(self, plate: str, comment: str = "") -> tuple[bool, str]:
        """
        Yeni plakayı UI bölümüne ekle, dosyayı atomic re-write et,
        processor varsa whitelist'i yeniden yükle.

        Returns: (success, message_or_normalized_plate)
        """
        normalized = normalize_plate(plate or "")
        if not normalized:
            return False, "Plaka boş veya geçersiz karakterler içeriyor."
        if len(normalized) < 5 or len(normalized) > 9:
            return False, f"Plaka uzunluğu 5-9 karakter olmalı (gelen: {len(normalized)})."

        clean_comment = (comment or "").strip()[:60]  # UI'da uzun yorumlar
        path = self._resolve_whitelist_path()

        with self._whitelist_lock:
            current = get_ui_plates(path)
            existing_plates = {p for p, _ in current}
            if normalized in existing_plates:
                return False, f"'{normalized}' zaten listede."
            current.append((normalized, clean_comment))
            ok = save_whitelist(path, current)
            if not ok:
                return False, "Dosyaya yazma başarısız (I/O hatası)."

            # Processor varsa yeniden yükle (worker thread match_plate
            # liste referansını atomic okur, race yok).
            reloaded_count = None
            if self._processor is not None:
                try:
                    reloaded_count = self._processor.reload_whitelist()
                except Exception as e:
                    logger.warning("reload_whitelist hatası: %s", e)

        self._log(
            "system",
            f"Whitelist + {normalized}" + (f" ({clean_comment})" if clean_comment else "")
            + (f" — toplam {reloaded_count} plaka aktif" if reloaded_count is not None else ""),
        )
        return True, normalized

    def remove_whitelist_entry(self, plate: str) -> tuple[bool, str]:
        """UI bölümünden plakayı sil, dosyayı yeniden yaz, processor'ı reload et."""
        normalized = normalize_plate(plate or "")
        if not normalized:
            return False, "Plaka boş veya geçersiz."

        path = self._resolve_whitelist_path()

        with self._whitelist_lock:
            current = get_ui_plates(path)
            filtered = [(p, c) for (p, c) in current if p != normalized]
            if len(filtered) == len(current):
                return False, f"'{normalized}' UI bölümünde bulunamadı."

            ok = save_whitelist(path, filtered)
            if not ok:
                return False, "Dosyaya yazma başarısız (I/O hatası)."

            reloaded_count = None
            if self._processor is not None:
                try:
                    reloaded_count = self._processor.reload_whitelist()
                except Exception as e:
                    logger.warning("reload_whitelist hatası: %s", e)

        self._log(
            "warn",
            f"Whitelist - {normalized}"
            + (f" — kalan {reloaded_count} plaka aktif" if reloaded_count is not None else ""),
        )
        return True, normalized

    # ────────────────────────────────────────────────────────────────────────
    # LOGGING
    # ────────────────────────────────────────────────────────────────────────

    def _log(self, tag: str, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        entry = {"ts": ts, "tag": tag, "msg": msg}
        self.recent_logs.appendleft(entry)
        if tag in ("error", "warn"):
            logger.warning("[plate %s] %s", tag, msg)
        else:
            logger.info("[plate %s] %s", tag, msg)
