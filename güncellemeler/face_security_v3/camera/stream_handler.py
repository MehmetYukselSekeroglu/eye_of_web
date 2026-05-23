"""
RTSP kamera akış yönetimi.
Her kamera için ayrı thread; kare kuyruğu ve tespit sonuçları
thread-safe paylaşımlı nesnelerle aktarılır.
"""
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import config

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    name: str
    score: float
    bbox: tuple          # (x1, y1, x2, y2) orijinal koordinatlarda
    crop: np.ndarray
    timestamp: datetime = field(default_factory=datetime.now)
    cam_id: int = 0
    cam_name: str = ""


class StreamHandler:
    """
    Tek bir RTSP kamerayı arka planda okur.
    - img_queue: GUI'ye gönderilecek display frame'leri
    - result_queue: Yüz tespit sonuçları (DetectionResult)
    """

    def __init__(self, face_processor, img_queue: queue.Queue, result_queue: queue.Queue):
        self.face_processor = face_processor
        self.img_queue = img_queue
        self.result_queue = result_queue

        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._inf_running = threading.Event()

        self.last_frame_raw: np.ndarray | None = None
        self.frame_lock = threading.Lock()

        self.active_cam_id: int | None = None
        self.face_detected_event = threading.Event()

        self._last_saved: dict[str, float] = {}

    # ── Kontrol ──────────────────────────────────────────────────────────────

    def switch(self, cam_id: int, rtsp_url: str) -> None:
        """Aktif kamerayı değiştirir (önceki thread'i durdurur)."""
        self.stop()
        self.active_cam_id = cam_id
        self._running = True
        self._inf_running = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, args=(rtsp_url, cam_id), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    # ── Ana döngü ────────────────────────────────────────────────────────────

    def _loop(self, rtsp_url: str, cam_id: int) -> None:
        cap = cv2.VideoCapture(rtsp_url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        # Donanım hızlandırmalı decode (destekleniyorsa V4L2/VAAPI/VDPAU)
        cap.set(cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY)

        if not cap.isOpened():
            logger.error("Kamera açılamadı: %s", config.CAMERA_NAMES.get(cam_id, cam_id))
            cap.release()
            return

        cam_name = config.CAMERA_NAMES.get(cam_id, str(cam_id))
        logger.info("Kamera bağlandı: %s", cam_name)

        last_inf = 0.0
        inf_interval = 1.0 / config.INFERENCE_FPS

        while self._running and self.active_cam_id == cam_id:
            # RTSP tamponunu temizle: eski kareleri atla
            cap.grab()
            ret, frame = cap.retrieve()
            if not ret or frame is None:
                logger.warning("Görüntü alınamadı: %s", cam_name)
                time.sleep(0.1)
                continue

            with self.frame_lock:
                self.last_frame_raw = frame.copy()

            # Display resize — GPU'da yap, InsightFace için numpy'a indir
            try:
                display = cv2.resize(cv2.UMat(frame),
                                     (config.DISPLAY_W, config.DISPLAY_H)).get()
            except Exception:
                continue

            now = time.time()
            if now - last_inf >= inf_interval and not self._inf_running.is_set():
                last_inf = now
                self._inf_running.set()
                f_copy = frame.copy()
                d_copy = display.copy()
                threading.Thread(
                    target=self._run_inference_async,
                    args=(f_copy, d_copy, cam_id, cam_name),
                    daemon=True,
                ).start()

            if not self.img_queue.full():
                self.img_queue.put_nowait(display)

        cap.release()
        logger.info("Kamera kapatıldı: %s", cam_name)

    # ── Çıkarım ──────────────────────────────────────────────────────────────

    def _run_inference_async(
        self,
        orig_frame: np.ndarray,
        display_frame: np.ndarray,
        cam_id: int,
        cam_name: str,
    ) -> None:
        """Inference'ı ayrı thread'de çalıştırır; okuma döngüsünü bloklamaz."""
        try:
            self._run_inference(orig_frame, display_frame, cam_id, cam_name)
        finally:
            self._inf_running.clear()

    def _run_inference(
        self,
        orig_frame: np.ndarray,
        display_frame: np.ndarray,
        cam_id: int,
        cam_name: str,
    ) -> None:
        faces = self.face_processor.get_faces(display_frame)
        if not faces:
            return

        self.face_detected_event.set()

        orig_h, orig_w = orig_frame.shape[:2]
        scale_x = orig_w / config.DISPLAY_W
        scale_y = orig_h / config.DISPLAY_H

        now = time.time()

        for face in faces:
            name, score = self.face_processor.recognize(face, threshold=config.THRESHOLD)

            bbox = face.bbox.astype(int)
            x1, y1, x2, y2 = bbox
            rx1 = int(x1 * scale_x)
            ry1 = int(y1 * scale_y)
            rx2 = int(x2 * scale_x)
            ry2 = int(y2 * scale_y)

            crop = self._safe_crop(orig_frame, rx1, ry1, rx2, ry2)
            if crop is None:
                continue

            # Snapshot cooldown
            if now - self._last_saved.get(name, 0) < config.SNAPSHOT_COOLDOWN:
                continue
            self._last_saved[name] = now

            # Snapshot kaydet
            snap_path = self._save_snapshot(name, crop)

            result = DetectionResult(
                name=name,
                score=round(score, 3),
                bbox=(rx1, ry1, rx2, ry2),
                crop=crop,
                cam_id=cam_id,
                cam_name=cam_name,
            )
            result.snap_path = snap_path  # type: ignore[attr-defined]

            if not self.result_queue.full():
                self.result_queue.put_nowait(result)

    def _save_snapshot(self, name: str, crop: np.ndarray) -> str:
        ts = datetime.now().strftime("%H-%M-%S")
        if name == "unknown":
            path = Path(config.UNKNOWN_PATH) / f"unknown_{ts}.jpg"
        else:
            path = Path(config.KNOWN_PATH) / f"{name}_{ts}.jpg"
        cv2.imwrite(str(path), crop)
        return str(path)

    @staticmethod
    def _safe_crop(
        frame: np.ndarray, x1: int, y1: int, x2: int, y2: int, margin: int = 30
    ) -> np.ndarray | None:
        h, w = frame.shape[:2]
        x1 = max(0, x1 - margin)
        y1 = max(0, y1 - margin)
        x2 = min(w, x2 + margin)
        y2 = min(h, y2 + margin)
        if x2 <= x1 or y2 <= y1:
            return None
        crop = frame[y1:y2, x1:x2]
        return crop if crop.size > 0 else None
