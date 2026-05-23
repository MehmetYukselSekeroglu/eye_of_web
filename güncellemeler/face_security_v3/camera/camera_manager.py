"""
Kamera yöneticisi — kamera geçişi ve otomatik devriye mantığı.
"""
import logging
import threading
import time
from typing import Callable

import config
from camera.stream_handler import StreamHandler

logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(self, stream_handler: StreamHandler):
        self.stream = stream_handler
        self.active_cam_id: int | None = None

        self._patrol_active = False
        self._patrol_thread: threading.Thread | None = None
        self._patrol_lock = threading.Lock()

        # Seçili kameralar (devriyede kullanılır)
        self.selected_cams: set[int] = set()

        # UI güncelleme callback'leri
        self.on_camera_switch: Callable[[int], None] | None = None

    # ── Kamera Geçişi ────────────────────────────────────────────────────────

    def switch(self, cam_id: int, log: bool = True) -> bool:
        if cam_id not in config.CAMERAS:
            logger.warning("Geçersiz kamera: %d", cam_id)
            return False
        if self.active_cam_id == cam_id:
            return True

        self.active_cam_id = cam_id
        self.stream.switch(cam_id, config.CAMERAS[cam_id])
        self.stream.face_detected_event.clear()

        if log:
            logger.info("Kamera: %s", config.CAMERA_NAMES.get(cam_id, cam_id))

        if self.on_camera_switch:
            self.on_camera_switch(cam_id)

        return True

    # ── Devriye ──────────────────────────────────────────────────────────────

    def start_patrol(self) -> bool:
        if self._patrol_active:
            return False
        if not self.selected_cams:
            logger.warning("Devriye için seçili kamera yok.")
            return False

        self._patrol_active = True
        self._patrol_thread = threading.Thread(target=self._patrol_loop, daemon=True)
        self._patrol_thread.start()
        logger.info("Devriye başlatıldı.")
        return True

    def stop(self) -> None:
        self._patrol_active = False
        self.stream.stop()
        logger.info("Tüm taramalar durduruldu.")

    def _patrol_loop(self) -> None:
        with self._patrol_lock:
            while self._patrol_active:
                cams = sorted(
                    c for c in self.selected_cams if c in config.CAMERAS
                )
                if not cams:
                    self._patrol_active = False
                    break

                for cam_id in cams:
                    if not self._patrol_active:
                        break

                    self.stream.face_detected_event.clear()
                    self.switch(cam_id, log=False)

                    # Tarama süresi: yüz bulunursa bekleme uygula
                    scan_start = time.time()
                    while time.time() - scan_start < config.PATROL_SCAN_SECONDS:
                        if not self._patrol_active:
                            break
                        if self.stream.face_detected_event.is_set():
                            logger.info(
                                "Yüz tespit edildi → %s bekletiliyor",
                                config.CAMERA_NAMES.get(cam_id, cam_id),
                            )
                            hold_start = time.time()
                            while time.time() - hold_start < config.PATROL_HOLD_SECONDS:
                                if not self._patrol_active:
                                    break
                                time.sleep(0.2)
                            self.stream.face_detected_event.clear()
                            break
                        time.sleep(0.5)
