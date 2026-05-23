"""
ALPR Pipeline — Araç Tespiti + Çok-Frame Plaka OCR

Akış:
  1. YOLOv8 → araç bbox (car / truck / bus / motorcycle)
  2. Her araç için alt %40 kırpılır (plaka bölgesi)
  3. Kırpı Laplacian netliğiyle değerlendirilip buffer'a eklenir
  4. 10 frame toplandığında (ya da 5 sn timeout) en keskin 5 crop seçilir
  5. Her crop → 3 görüntü pipeline → EasyOCR (conf ≥ 0.4)
  6. Oylama: 5 okumada 3+ eşleşme → onaylı plaka
  7. Throttle: aynı plaka 10 saniyede bir tekrar loglanmaz
"""
import os
import re
import time
import logging
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from detection.plate_whitelist import load_whitelist, match_plate

logger = logging.getLogger(__name__)

# ── Sabitler ──────────────────────────────────────────────────────────────────

# COCO sınıfları — sadece _vehicle_yolo (motion gate) için.
# Plaka detector tek-class olduğu için filter gerekmez.
_VEHICLE_CLASSES: set[int] = {2, 3, 5, 7}   # COCO: car, motorcycle, bus, truck

# Türk plaka regex — boşluk olmadan: 34ABC1234
_PLATE_RE = re.compile(
    r'^(0[1-9]|[1-7][0-9]|8[01])([A-Z]{1,3})(\d{1,4})$'
)

_OCR_ALLOWLIST       = '0123456789ABCDEFGHIJKLMNOPRSTUVYZ'
_MIN_CONF            = 0.10   # Regex doğrulama yanlışları zaten filtreler
_COLLECT_FRAMES      = 10     # Buffer bu kadar dolduğunda OCR tetiklenir
_TOP_CROPS           = 5      # En keskin kaç crop OCR'a gönderilsin
_COLLECTION_TIMEOUT  = 5.0    # Saniye — buffer dolmasa bile bu süreden sonra OCR tetiklenir

# Benzer karakter düzeltme — yalnızca konum bazlı uygulanır
_TR_NORM: dict[str, str] = {
    'İ': 'I', 'Ş': 'S', 'Ğ': 'G', 'Ü': 'U', 'Ö': 'O', 'Ç': 'C',
    'ı': 'I', 'ş': 'S', 'ğ': 'G', 'ü': 'U', 'ö': 'O', 'ç': 'C',
}
_LETTER_TO_DIGIT: dict[str, str] = {
    'O': '0', 'I': '1', 'S': '5', 'B': '8', 'Z': '2', 'G': '6',
}
_DIGIT_TO_LETTER: dict[str, str] = {
    '0': 'O', '1': 'I', '5': 'S', '8': 'B', '2': 'Z', '6': 'G',
}


# ── Metin normalize + doğrulama ───────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Türkçe karakterleri Latinleştir, büyük harf yap, özel karakterleri sil."""
    text = text.upper().strip()
    for src, dst in _TR_NORM.items():
        text = text.replace(src, dst)
    return re.sub(r'[^A-Z0-9]', '', text)


def _validate_plate(raw: str) -> Optional[str]:
    """
    OCR çıktısını Türk plaka formatına doğrula.

    Strateji (basit ve agresif olmayan):
      1. Normalize et.
      2. Regex ile doğrudan eşleştir → döndür.
      3. Şehir kodu (ilk 2 char) rakam olmak zorunda → harf→rakam düzelt.
      4. Kalan kısımda harf/rakam sınırını dene (1-3 harf, 1-4 rakam).
         Her deneme için sadece OCR hatası olabilecek benzer karakterleri düzelt.
      5. Eşleşme yoksa None döndür — kesinlikle uydurmaya çalışma.
    """
    text = _normalize(raw)
    if not text or len(text) < 6 or len(text) > 9:
        return None

    # PLAKA-2.F: Yapısal minimum gereksinim — saf rakam veya saf harf dizilerini reddet
    # Türk plakası: XX (rakam) + 1-3 harf + 1-4 rakam = en az 1 harf, en az 4 rakam
    # Saf rakam '5211086' → mapping ile zorla 'I' eklenmesini önle (yanlış pozitif)
    _letter_count = sum(1 for c in text if c.isalpha())
    _digit_count  = sum(1 for c in text if c.isdigit())
    if _letter_count < 1:
        return None
    if _digit_count < 4:
        return None

    # 1. Direkt eşleşme
    m = _PLATE_RE.match(text)
    if m:
        return m.group(1) + m.group(2) + m.group(3)

    # 2. Şehir kodu düzelt (sadece ilk 2 char)
    city = ''.join(_LETTER_TO_DIGIT.get(c, c) for c in text[:2])
    rest = text[2:]

    # 3. Harf+rakam bölünme noktasını dene
    for split in range(1, min(4, len(rest))):
        tail_len = len(rest) - split
        if tail_len < 1 or tail_len > 4:
            continue
        letters = ''.join(_DIGIT_TO_LETTER.get(c, c) for c in rest[:split])
        digits  = ''.join(_LETTER_TO_DIGIT.get(c, c)  for c in rest[split:])
        candidate = city + letters + digits
        m = _PLATE_RE.match(candidate)
        if m:
            return m.group(1) + m.group(2) + m.group(3)

    return None


# ── Görüntü pipeline'ları (numpy — CLAHE/bilateralFilter UMat desteklemez) ──────
# NOT: OpenCL hızlandırma kamera stream'de kullanılır.
# OCR pipeline'ları numpy array bekler; UMat burada kasıtlı olarak kullanılmıyor.

def _upscale(gray: np.ndarray) -> np.ndarray:
    """4× büyüt — küçük plaka crop'larında OCR doğruluğunu artırır."""
    return cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)


def _normalize_width(gray: np.ndarray, target_w: int = 500) -> np.ndarray:
    """Genişliği target_w'ye normalize et — zaten büyükse dokunma."""
    h, w = gray.shape[:2]
    if w >= target_w:
        return gray
    scale = target_w / w
    return cv2.resize(gray, (target_w, max(1, int(h * scale))),
                      interpolation=cv2.INTER_LANCZOS4)


# Debug crop dizini
_DEBUG_CROP_DIR = Path("logs/debug_crops")
_DEBUG_CROP_MAX = 10


def _pipe_a(gray: np.ndarray) -> np.ndarray:
    """Pipeline A: CLAHE → Adaptif Gaussian threshold."""
    clahe    = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    return cv2.adaptiveThreshold(
        enhanced, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2,
    )


def _pipe_b(gray: np.ndarray) -> np.ndarray:
    """Pipeline B: Bilateral filter → Otsu threshold."""
    filtered = cv2.bilateralFilter(gray, 9, 75, 75)
    _, thresh = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def _pipe_c(gray: np.ndarray) -> np.ndarray:
    """Pipeline C: Sharpen → Otsu threshold (sabit eşik yerine adaptif)."""
    kernel    = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]], dtype=np.float32)
    sharpened = cv2.filter2D(gray, -1, kernel)
    _, thresh = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return thresh


_PIPELINES = [_pipe_a, _pipe_b, _pipe_c]


# ── Ana sınıf ──────────────────────────────────────────────────────────────────

class PlateProcessor:
    """
    ALPR motoru: çok-frame toplama + OCR + oylama.

    process_frame() her çağrıda araç tespiti yapar ve plaka crop'unu buffer'a
    ekler. Buffer dolduğunda (veya timeout'ta) en keskin crop'lara OCR uygular.
    """

    def __init__(
        self,
        vote_count:           int   = 5,
        vote_threshold:       int   = 3,
        throttle_secs:        int   = 10,
        yolo_model_path:      str   = "",     # plaka detector
        yolo_conf:            float = 0.25,   # COCO/vehicle gate conf
        vehicle_model_path:   str   = "",     # COCO model path (boş = yolov8n.pt auto)
        detector_conf:        float = 0.25,   # plaka detector conf
        use_contour_fallback: bool  = False,  # plaka YOLO 0 tespit → kontur'a düş?
        unknown_plate_callback=None,          # PLAKA-2.I-3: sol panel history
    ) -> None:
        self.vote_count             = vote_count
        self.vote_threshold         = vote_threshold
        self.throttle_secs          = throttle_secs
        self._yolo_path             = yolo_model_path
        self._yolo_conf             = yolo_conf
        self._vehicle_path          = vehicle_model_path
        self._detector_conf         = detector_conf
        self._use_contour_fallback  = use_contour_fallback
        self._unknown_plate_callback = unknown_plate_callback

        self._yolo:         object           = None   # plaka detector (yeni rol)
        self._vehicle_yolo: object           = None   # COCO motion gate
        self._reader:       object           = None
        self._initialized:  bool             = False
        self._error:        Optional[str]    = None

        self._vote_buffer: deque[str]        = deque(maxlen=vote_count)
        self._last_logged: dict[str, float]  = {}

        # Çok-frame toplama
        self._crop_buffer:      list[np.ndarray] = []
        self._collection_start: float            = 0.0

        # Son YOLO debug satırı — plate_tab analiz thread'i okuyup log'a koyar
        self._last_yolo_log: str = ""
        # OCR/oylama debug satırları — plate_tab okur, her OCR turunda birikir
        self._debug_logs: list[str] = []

        # Debug crop kaydetme
        self._debug_crop_idx: int = 0

        # ── PLAKA-2.H: Whitelist + bilinmeyen plaka ──────────────────────────
        self._whitelist_path = os.environ.get(
            'PLATE_WHITELIST_PATH', 'config/plate_whitelist.txt',
        )
        self._whitelist: list[str] = load_whitelist(self._whitelist_path)
        self._whitelist_active: bool = len(self._whitelist) > 0

        self._unknown_save_dir = Path(
            os.environ.get('PLATE_UNKNOWN_SAVE_DIR', 'unknown_plates')
        )
        self._unknown_throttle_seconds = float(
            os.environ.get('PLATE_UNKNOWN_THROTTLE_SECONDS', '30')
        )
        self._unknown_last_save: dict[str, float] = {}

        if self._whitelist_active:
            logger.info(
                "[Whitelist] AKTİF — %d plaka, dosya=%s",
                len(self._whitelist), self._whitelist_path,
            )
        else:
            logger.info(
                "[Whitelist] DEVRE DIŞI — dosya yok veya boş (%s) — mevcut davranış aktif",
                self._whitelist_path,
            )

    # ── Başlatma ──────────────────────────────────────────────────────────────

    def initialize(self) -> bool:
        """COCO Vehicle YOLO + Plaka YOLO + EasyOCR modellerini yükle."""
        errors: list[str] = []

        # 1) COCO Vehicle YOLO (motion gate — araç var mı?)
        try:
            from ultralytics import YOLO
            veh_path = self._vehicle_path or "yolov8n.pt"
            self._vehicle_yolo = YOLO(veh_path)
            logger.info("Vehicle YOLO yüklendi: %s | %d sınıf",
                        veh_path, len(self._vehicle_yolo.names))
            # Araç sınıflarını logla — hangi cls id'lerin eşleştiğini doğrula
            vehicle_names = {
                cls: self._vehicle_yolo.names[cls]
                for cls in _VEHICLE_CLASSES
                if cls in self._vehicle_yolo.names
            }
            logger.info("Araç sınıfları (filtre): %s", vehicle_names)
        except Exception as exc:
            errors.append(f"Vehicle YOLO: {exc}")
            logger.warning("Vehicle YOLO yüklenemedi (%s) — araç tespiti çalışmaz.", exc)

        # 2) Plaka detector YOLO (tek-class, fine-tune'lu)
        try:
            from ultralytics import YOLO
            plate_path = self._yolo_path or "models/license_plate_detector.pt"
            if not Path(plate_path).exists():
                raise FileNotFoundError(f"Plaka detector bulunamadı: {plate_path}")
            self._yolo = YOLO(plate_path)
            logger.info("Plaka YOLO yüklendi: %s | Sınıflar: %s",
                        plate_path, self._yolo.names)
        except Exception as exc:
            self._use_contour_fallback = True   # auto-graceful
            logger.warning(
                "Plaka YOLO yüklenemedi (%s) — kontur fallback otomatik aktive edildi.",
                exc,
            )
            errors.append(
                "Plaka detector modeli yüklenemedi - eski kontur yöntemine düştü. "
                "models/license_plate_detector.pt dosyasını kontrol edin."
            )

        # GPU (EasyOCR için)
        try:
            import torch
            use_gpu = torch.cuda.is_available()
        except ImportError:
            use_gpu = False
        logger.info("EasyOCR GPU=%s ile başlatılıyor.", use_gpu)

        # EasyOCR
        try:
            import easyocr
            self._reader = easyocr.Reader(['en'], gpu=use_gpu, verbose=False)
            logger.info("EasyOCR hazır.")
        except Exception as exc:
            errors.append(f"EasyOCR: {exc}")
            self._error = " | ".join(errors)
            logger.error("EasyOCR başlatılamadı: %s", exc)
            return False

        self._initialized = True
        if errors:
            logger.warning("Kısmi başlatma — hatalar: %s", errors)
        if cv2.ocl.useOpenCL():
            logger.info("OpenCL aktif — görüntü ön-işleme GPU'da çalışacak.")
        return True

    @property
    def ready(self) -> bool:
        return self._initialized and self._reader is not None

    @property
    def error(self) -> Optional[str]:
        return self._error

    @property
    def collection_progress(self) -> int:
        """Mevcut buffer doluluk sayısı — UI için."""
        return len(self._crop_buffer)

    # ── Ana pipeline ──────────────────────────────────────────────────────────

    def process_frame(
        self, frame: np.ndarray
    ) -> tuple[Optional[str], list[tuple[int, int, int, int]], Optional[np.ndarray]]:
        """
        Her çağrıda:
          1. YOLO ile araç/plaka bölgesi bul.
          2. En keskin crop'u buffer'a ekle.
          3. Buffer dolunca (10 frame) veya timeout'ta OCR çalıştır.

        Returns:
            (onaylı_plaka | None,
             araç_bboxları [(x1,y1,x2,y2), ...],
             display_crop | None)
        """
        if not self.ready:
            return None, [], None

        # ── Araç tespiti + plaka crop ─────────────────────────────────────
        vehicle_boxes, plate_crops = self._detect_regions(frame)

        display_crop: Optional[np.ndarray] = None

        if plate_crops:
            # Bu frame'in en net plaka bölgesini seç
            best = max(plate_crops, key=self._sharpness)
            if self._collection_start == 0.0:
                self._collection_start = time.time()
            self._crop_buffer.append(best)
            display_crop = best

        # ── OCR tetikleme koşulları ───────────────────────────────────────
        now         = time.time()
        buf_full    = len(self._crop_buffer) >= _COLLECT_FRAMES
        timed_out   = (bool(self._crop_buffer) and
                       now - self._collection_start >= _COLLECTION_TIMEOUT)

        confirmed: Optional[str] = None

        if buf_full or timed_out:
            n_buf = len(self._crop_buffer)
            n_top = min(n_buf, _TOP_CROPS)
            ocr_trigger_msg = (
                f"[ANALİZ] OCR tetiklendi: {n_buf} crop, "
                f"en keskin {n_top} tanesi işlenecek "
                f"({'buffer doldu' if buf_full else 'timeout'})"
            )
            logger.info(ocr_trigger_msg)
            self._debug_logs.clear()           # Yeni OCR turu — önceki logları temizle
            self._debug_logs.append(ocr_trigger_msg)

            top_crops = self._pick_top(self._crop_buffer, _TOP_CROPS)
            self._crop_buffer.clear()
            self._collection_start = 0.0

            for crop in top_crops:
                text, conf = self._ocr_best(crop)
                if text and conf >= _MIN_CONF:
                    # PLAKA-2.H: Whitelist filtreleme — vote'tan önce
                    if self._whitelist_active:
                        matched = match_plate(text, self._whitelist)
                        if matched:
                            logger.info(
                                "[PLAKA-2.H] Whitelist eşleşme: ham=%r → %s (vote'a gider)",
                                text, matched,
                            )
                            text_for_vote: Optional[str] = matched
                        else:
                            logger.info(
                                "[PLAKA-2.H] Whitelist YOK eşleşme: ham=%r — bilinmeyen, kaydediliyor",
                                text,
                            )
                            self._save_unknown_plate(frame, crop, text, conf)
                            text_for_vote = None
                    else:
                        text_for_vote = text

                    if text_for_vote:
                        voted = self._vote(text_for_vote)
                        if voted and self._should_log(voted):
                            confirmed = voted

            # Preview için en keskin crop'u kullan
            if top_crops:
                display_crop = top_crops[0]

        elif display_crop is None and self._crop_buffer:
            display_crop = self._crop_buffer[-1]

        return confirmed, vehicle_boxes, display_crop

    # ── YOLO araç + plaka bölgesi tespiti ────────────────────────────────────

    def _detect_regions(
        self, frame: np.ndarray
    ) -> tuple[list[tuple[int, int, int, int]], list[np.ndarray]]:
        """
        Hibrit pipeline:
          1. COCO Vehicle YOLO ile araç bbox bul (motion gate).
          2. Her araç crop'unda Plaka detector YOLO ile plaka bbox bul.
          3. Plaka YOLO 0 tespit + USE_CONTOUR_FALLBACK=True ise kontur'a düş.
          4. Bulunan plaka kırpıkını 500px genişliğe normalize et.
        Her çağrıda _last_yolo_log UI debug için güncellenir.
        """
        fh, fw = frame.shape[:2]

        if self._vehicle_yolo is None:
            self._last_yolo_log = (
                f"[DEBUG] Vehicle YOLO yok — araç tespiti yapılamıyor. Frame:{fw}×{fh}"
            )
            return [], []

        vehicle_boxes: list[tuple[int, int, int, int]] = []
        plate_crops:   list[np.ndarray]                = []
        plate_count = 0

        try:
            veh_results = self._vehicle_yolo(frame, verbose=False, conf=self._yolo_conf)
            veh_dets    = veh_results[0].boxes
        except Exception as exc:
            logger.debug("Vehicle YOLO tespit hatası: %s", exc)
            self._last_yolo_log = f"[DEBUG] Vehicle YOLO hata: {exc}"
            return [], []

        # ── Vehicle YOLO debug satırı ─────────────────────────────────────
        det_details: list[str] = []
        for det in veh_dets:
            cls   = int(det.cls[0])
            conf  = float(det.conf[0])
            cname = self._vehicle_yolo.names[cls] if cls in self._vehicle_yolo.names else str(cls)
            mark  = "✓" if cls in _VEHICLE_CLASSES else "✗"
            det_details.append(f"{mark}{cname}({cls}):{conf:.2f}")

        # ── Araç filtreleme + plaka tespiti ───────────────────────────────
        for det in veh_dets:
            cls = int(det.cls[0])
            # COCO filter — motion gate (yalnız vehicle classes)
            if cls not in _VEHICLE_CLASSES:
                continue

            x1, y1, x2, y2 = map(int, det.xyxy[0])
            x1 = max(0, x1); y1 = max(0, y1)
            x2 = min(fw, x2); y2 = min(fh, y2)
            vehicle_boxes.append((x1, y1, x2, y2))

            # Tam araç crop (eski alt-%30 kaldırıldı; plate detector kendi bulur)
            veh_crop = frame[y1:y2, x1:x2]
            if veh_crop.size == 0 or (y2 - y1) < 40 or (x2 - x1) < 40:
                continue

            # 1) Plaka detector YOLO — araç crop'unda plaka ara
            plate_crop_candidate: Optional[np.ndarray] = None

            if self._yolo is not None:
                try:
                    pl_results = self._yolo(
                        veh_crop, verbose=False, conf=self._detector_conf
                    )
                    pl_dets = pl_results[0].boxes
                    # ── DIAG-2D-pre BAŞLANGIÇ (PLAKA-2.D fix sonrası kaldırılacak) ─────
                    _pl_count = len(pl_dets) if pl_dets is not None else 0
                    try:
                        _pl_confs = [float(c) for c in pl_dets.conf] if _pl_count > 0 else []
                    except Exception:
                        _pl_confs = ["?"]
                    logger.info(
                        "[DIAG-2D] Plate YOLO output: count=%d confs=%s",
                        _pl_count,
                        [f"{c:.3f}" if isinstance(c, float) else c for c in _pl_confs],
                    )
                    # ── DIAG-2D-pre SONU ────────────────────────────────────────────────
                    if len(pl_dets) > 0:
                        # En yüksek conf'lu plaka
                        best_idx = int(pl_dets.conf.argmax())
                        px1, py1, px2, py2 = map(int, pl_dets.xyxy[best_idx])
                        pw_box = px2 - px1
                        ph_box = py2 - py1
                        # ── PLAKA-2.D: BBox kalite filtresi ──────────────────────────────────
                        # D.1: Min boyut — OCR için absolute minimum (mikro yansıma/gürültü eler)
                        # D.3: Raw aspect — kareye yakın veya aşırı dar şerit bbox'ları eler
                        #      (gerçek plaka raw aspect ~1.5-2.0 gözlendi; eşik gevşek tutuluyor
                        #       çünkü farklı mesafelerde bbox aspect değişebilir)
                        _raw_aspect = pw_box / max(ph_box, 1)
                        _bbox_rejected = False
                        _reject_reason = ""

                        if pw_box < 30:
                            _bbox_rejected = True
                            _reject_reason = f"pw_box={pw_box}<30 (çok dar)"
                        elif ph_box < 10:
                            _bbox_rejected = True
                            _reject_reason = f"ph_box={ph_box}<10 (çok yassı)"
                        elif _raw_aspect < 1.2:
                            _bbox_rejected = True
                            _reject_reason = f"aspect={_raw_aspect:.2f}<1.2 (kareye yakın)"
                        elif _raw_aspect > 7.0:
                            _bbox_rejected = True
                            _reject_reason = f"aspect={_raw_aspect:.2f}>7.0 (aşırı dar şerit)"

                        if _bbox_rejected:
                            logger.info(
                                "[PLAKA-2.D] BBox reddedildi: %s | "
                                "px1=%d py1=%d px2=%d py2=%d w=%d h=%d conf=%.3f",
                                _reject_reason, px1, py1, px2, py2, pw_box, ph_box,
                                float(pl_dets.conf[best_idx]),
                            )
                            # plate_crop_candidate None kalır (line 425 init);
                            # kontur fallback opsiyon olarak çalışabilir
                        else:
                            # Hafif padding (%5 x, %10 y)
                            pad_x  = max(2, int(pw_box * 0.05))
                            pad_y  = max(2, int(ph_box * 0.10))
                            cx1 = max(0, px1 - pad_x)
                            cy1 = max(0, py1 - pad_y)
                            cx2 = min(veh_crop.shape[1], px2 + pad_x)
                            cy2 = min(veh_crop.shape[0], py2 + pad_y)
                            # ── DIAG-2D-pre BAŞLANGIÇ (PLAKA-2.D fix sonrası kaldırılacak) ─────
                            _pl_conf = float(pl_dets.conf[best_idx])
                            logger.info(
                                "[DIAG-2D] BBox (RAW): px1=%d py1=%d px2=%d py2=%d "
                                "w=%d h=%d aspect=%.2f conf=%.3f",
                                px1, py1, px2, py2, pw_box, ph_box, _raw_aspect, _pl_conf,
                            )
                            _bbox_w = cx2 - cx1
                            _bbox_h = cy2 - cy1
                            _aspect = _bbox_w / max(_bbox_h, 1)
                            logger.info(
                                "[DIAG-2D] BBox (padding sonrası): cx1=%d cy1=%d cx2=%d cy2=%d "
                                "w=%d h=%d aspect=%.2f conf=%.3f",
                                cx1, cy1, cx2, cy2, _bbox_w, _bbox_h, _aspect, _pl_conf,
                            )
                            # ── DIAG-2D-pre SONU ────────────────────────────────────────────────
                            plate_crop_candidate = veh_crop[cy1:cy2, cx1:cx2]
                            # ── DIAG-2D-pre BAŞLANGIÇ (PLAKA-2.D fix sonrası kaldırılacak) ─────
                            import os as _diag_os
                            _diag_dir = "/tmp/plaka_diag_2d"
                            _diag_os.makedirs(_diag_dir, exist_ok=True)
                            _diag_ts = int(time.time() * 1000)
                            _diag_path = (
                                f"{_diag_dir}/crop_{_diag_ts}_{_bbox_w}x{_bbox_h}"
                                f"_aspect{_aspect:.2f}_conf{_pl_conf:.2f}.jpg"
                            )
                            try:
                                cv2.imwrite(_diag_path, plate_crop_candidate)
                                logger.info("[DIAG-2D] Ham crop kaydedildi: %s", _diag_path)
                            except Exception as _e:
                                logger.warning("[DIAG-2D] Ham crop kaydedilemedi: %s", _e)
                            # ── DIAG-2D-pre SONU ────────────────────────────────────────────────
                        # ── PLAKA-2.D SONU ──────────────────────────────────────────────────
                except Exception as exc:
                    logger.debug("Plate YOLO hata: %s", exc)

            # 2) Plaka YOLO 0 tespit + flag açık → kontur fallback
            if plate_crop_candidate is None and self._use_contour_fallback:
                bh, bw  = veh_crop.shape[:2]
                sub_y1  = max(0, bh - int(bh * 0.30))
                sub_x1  = int(bw * 0.10)
                sub_x2  = bw - int(bw * 0.10)
                sub_crop = veh_crop[sub_y1:bh, sub_x1:sub_x2]
                kontur_region = self._find_plate_region(sub_crop)
                if kontur_region is not None and kontur_region.size > 0:
                    plate_crop_candidate = kontur_region

            if plate_crop_candidate is None:
                continue   # Bu araçta plaka bulunamadı → buffer'a girmez

            crop = plate_crop_candidate
            ch, cw = crop.shape[:2]
            if crop.size == 0 or ch < 8 or cw < 20:
                continue

            # Genişliği 500px'e normalize et (oran koruyarak, LANCZOS4)
            if cw < 500:
                scale = 500 / cw
                crop  = cv2.resize(crop, (500, max(1, int(ch * scale))),
                                   interpolation=cv2.INTER_LANCZOS4)

            plate_crops.append(crop)
            plate_count += 1

        # ── Konsolide debug log ───────────────────────────────────────────
        fallback_tag = " | KONTUR_FALLBACK" if self._use_contour_fallback else ""
        self._last_yolo_log = (
            f"[DEBUG] Frame:{fw}×{fh} veh_conf≥{self._yolo_conf} "
            f"plate_conf≥{self._detector_conf} | "
            + (", ".join(det_details) if det_details else "vehicle:tespit yok")
            + f" | Araç:{len(vehicle_boxes)} | Plaka:{plate_count}{fallback_tag}"
        )

        return vehicle_boxes, plate_crops

    # ── Netlik skorlama ───────────────────────────────────────────────────────

    @staticmethod
    def _sharpness(img: np.ndarray) -> float:
        """Laplacian variance — yüksek değer = daha net görüntü."""
        if img.ndim == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    @staticmethod
    def _pick_top(crops: list[np.ndarray], n: int) -> list[np.ndarray]:
        """Netlik skoruna göre en iyi n crop'u seç."""
        scored = sorted(crops, key=PlateProcessor._sharpness, reverse=True)
        return scored[:n]

    # ── Kontur bazlı plaka izolasyonu ────────────────────────────────────────

    def _find_plate_region(self, crop: np.ndarray) -> Optional[np.ndarray]:
        """
        Kontur analizi ile crop içindeki plaka dikdörtgenini izole eder.
        Türk plakası: en-boy oranı 2.5-6, alan %1-40.
        Uygun bölge bulunursa %15 padding ile döndürür; bulunamazsa None.
        """
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop

        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h_img, w_img = gray.shape[:2]
        best = None
        best_score = 0

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect = w / max(h, 1)
            area = w * h
            area_ratio = area / (h_img * w_img)

            # Türk plakası: en-boy oranı 2.0-7.0, alan %1-40 arası
            if 2.0 <= aspect <= 7.0 and 0.01 <= area_ratio <= 0.4 and h >= 15 and w >= 60:
                score = area  # En büyük uygun dikdörtgeni seç
                if score > best_score:
                    best_score = score
                    pad_x = int(w * 0.15)
                    pad_y = int(h * 0.2)
                    best = (max(0, x - pad_x), max(0, y - pad_y),
                            min(w_img, x + w + pad_x), min(h_img, y + h + pad_y))

        if best:
            x1, y1, x2, y2 = best
            return crop[y1:y2, x1:x2]
        return None

    # ── Çoklu pipeline OCR ────────────────────────────────────────────────────

    def _ocr_best(
        self, region: np.ndarray
    ) -> tuple[Optional[str], float]:
        """
        Tek plaka crop'una kontur izolasyonu + 3 ön-işleme pipeline'ı uygular.
        1. Kontur bazlı plaka bölgesi tespiti (birincil).
        2. 4x büyütme + min 400px genişlik.
        3. Her pipeline sonucu x koordinatına göre sıralı metin birleştirme (ikincil).

        Returns:
            (doğrulanmış_plaka | None, en yüksek confidence)
        """
        if region.size == 0:
            return None, 0.0

        h, w = region.shape[:2]
        if h < 8 or w < 20:
            return None, 0.0

        # ── DIAG-2D-pre BAŞLANGIÇ (PLAKA-2.D fix sonrası kaldırılacak) ─────
        _crop_h, _crop_w = region.shape[:2] if hasattr(region, 'shape') else (-1, -1)
        logger.info(
            "[DIAG-2D] _ocr_best girdi: region=%dx%d (HxW), upscale_factor=4, "
            "mag_ratio=2.0, efektif_upscale=8x, beklenen_processed=%dx%d (HxW)",
            _crop_h, _crop_w, _crop_h * 4, _crop_w * 4,
        )
        # ── DIAG-2D-pre SONU ────────────────────────────────────────────────

        # _detect_regions zaten plaka kırpımı verdi (plate YOLO veya kontur fallback).
        # Burada tekrar kontur araması yapmıyoruz — region doğrudan OCR'a gider.
        ocr_region = region

        # ── Debug crop kaydet ─────────────────────────────────────────────
        self._save_debug_crop(ocr_region)

        # ── Numpy grayscale + AKILLI upscale + min 400px + kontrast ─────
        # CLAHE ve bilateralFilter UMat desteklemez — numpy zorunlu
        if ocr_region.ndim == 3:
            gray = cv2.cvtColor(ocr_region, cv2.COLOR_BGR2GRAY)
        else:
            gray = ocr_region.copy()
        # PLAKA-2.E: Akıllı upscale — region zaten yeterince büyükse upscale azalt.
        # Mevcut sabit 4× plaka detayını bozar (yapay büyütme + DBNet yavaş).
        # Hedef: processed_w yaklaşık 600-800 piksel (DBNet için ideal).
        _orig_h, _orig_w = gray.shape[:2]
        if _orig_w >= 400:
            _upscale_factor = 1   # zaten yeterli, upscale gerekmez
        elif _orig_w >= 200:
            _upscale_factor = 2   # orta seviye upscale
        else:
            _upscale_factor = 4   # küçük region için yapay büyütme şart
        logger.info(
            "[PLAKA-2.E] Akıllı upscale: orig=%dx%d, upscale=%dx → processed=%dx%d",
            _orig_w, _orig_h, _upscale_factor,
            _orig_w * _upscale_factor, _orig_h * _upscale_factor,
        )
        if _upscale_factor > 1:
            gray = cv2.resize(
                gray, None, fx=_upscale_factor, fy=_upscale_factor,
                interpolation=cv2.INTER_CUBIC,
            )
        if gray.shape[1] < 400:
            gray = _normalize_width(gray, 400)
        gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=30)  # kontrast artır

        best_text: Optional[str] = None
        best_conf: float         = 0.0
        pipe_names = ["A (CLAHE+Adaptive)", "B (Bilateral+Otsu)", "C (Sharpen+Otsu)"]
        any_result = False
        all_results: list[tuple] = []  # Tüm pipeline sonuçları — metin birleştirme için

        for pipe, pname in zip(_PIPELINES, pipe_names):
            # ── DIAG-2D-pre BAŞLANGIÇ (PLAKA-2.D fix sonrası kaldırılacak) ─────
            _pipe_start = time.perf_counter()
            _preprocess_start = time.perf_counter()
            _fallback_ran = False
            # ── DIAG-2D-pre SONU ────────────────────────────────────────────────
            # ── Görüntü işleme ────────────────────────────────────────────
            try:
                processed = pipe(gray)
            except Exception as exc:
                logger.warning("[OCR] Pipeline %s görüntü hatası: %s", pname, exc)
                self._debug_logs.append(f"[OCR] Pipeline {pname} görüntü hatası: {exc}")
                continue

            # ── DIAG-2D-pre BAŞLANGIÇ (PLAKA-2.D fix sonrası kaldırılacak) ─────
            _preprocess_ms = (time.perf_counter() - _preprocess_start) * 1000
            _processed_h, _processed_w = (
                processed.shape[:2] if hasattr(processed, 'shape') else (-1, -1)
            )
            _ocr_start = time.perf_counter()
            logger.info(
                "[DIAG-2D] %s: preprocess=%.1fms processed_size=%dx%d (HxW)",
                pname, _preprocess_ms, _processed_h, _processed_w,
            )
            # ── DIAG-2D-pre SONU ────────────────────────────────────────────────

            ph, pw = processed.shape[:2]

            # ── EasyOCR — önce allowlist ile dene ────────────────────────
            try:
                results = self._reader.readtext(
                    processed,
                    detail=1,
                    allowlist=_OCR_ALLOWLIST,
                    paragraph=False,
                    width_ths=0.5,
                    mag_ratio=2.0,
                    text_threshold=0.3,
                    low_text=0.3,
                    decoder='greedy',
                    batch_size=1,
                )
            except Exception as exc:
                logger.warning("[OCR] Pipeline %s OCR hatası: %s", pname, exc)
                self._debug_logs.append(f"[OCR] Pipeline {pname} OCR hatası: {exc}")
                continue

            # ── DIAG-2D-pre BAŞLANGIÇ (PLAKA-2.D fix sonrası kaldırılacak) ─────
            _ocr_allowlist_ms = (time.perf_counter() - _ocr_start) * 1000
            logger.info(
                "[DIAG-2D] %s: ocr_allowlist=%.1fms results=%d",
                pname, _ocr_allowlist_ms, len(results) if results else 0,
            )
            # ── DIAG-2D-pre SONU ────────────────────────────────────────────────

            # Allowlist'li OCR boş döndüyse allowlist kaldırarak tekrar dene
            if not results:
                # ── DIAG-2D-pre BAŞLANGIÇ (PLAKA-2.D fix sonrası kaldırılacak) ─────
                _ocr_fallback_start = time.perf_counter()
                _fallback_ran = True
                # ── DIAG-2D-pre SONU ────────────────────────────────────────────────
                try:
                    results = self._reader.readtext(
                        processed,
                        detail=1,
                        paragraph=False,
                        mag_ratio=2.0,
                        text_threshold=0.3,
                        low_text=0.3,
                        decoder='greedy',
                        batch_size=1,
                    )
                except Exception:
                    results = []
                # ── DIAG-2D-pre BAŞLANGIÇ (PLAKA-2.D fix sonrası kaldırılacak) ─────
                _ocr_fallback_ms = (time.perf_counter() - _ocr_fallback_start) * 1000
                logger.info(
                    "[DIAG-2D] %s: ocr_fallback=%.1fms results_after_fallback=%d",
                    pname, _ocr_fallback_ms, len(results) if results else 0,
                )
                # ── DIAG-2D-pre SONU ────────────────────────────────────────────────

            logger.info(
                "[OCR] Pipeline %s: crop=%dx%d → %d sonuç | ham: %s",
                pname, pw, ph, len(results),
                [(t, f"{c:.2f}") for (_, t, c) in results[:3]],
            )
            self._debug_logs.append(
                f"[OCR] Pipeline {pname} ({pw}×{ph}): "
                + (", ".join(f"{t!r}({c:.2f})" for (_, t, c) in results[:3]) or "boş")
            )

            if not results:
                continue

            # PLAKA-2.G: pname ile birlikte sakla, per-pipeline concat için
            all_results.extend([(*r, pname) for r in results])

            for (_, text, conf) in results:
                any_result = True
                fixed = _validate_plate(str(text))
                ok_mark = "✓" if fixed else "✗"
                msg = (
                    f"[OCR] {pname}: ham={text!r} conf={conf:.2f} "
                    f"→ {fixed if fixed else 'None'} {ok_mark}"
                )
                logger.info(msg)
                self._debug_logs.append(msg)

                if conf >= _MIN_CONF and fixed and conf > best_conf:
                    best_text = fixed
                    best_conf = conf

            # ── DIAG-2D-pre BAŞLANGIÇ (PLAKA-2.D fix sonrası kaldırılacak) ─────
            _pipe_total_ms = (time.perf_counter() - _pipe_start) * 1000
            logger.info(
                "[DIAG-2D] %s: pipe_total=%.1fms fallback_used=%s",
                pname, _pipe_total_ms, _fallback_ran,
            )
            # ── DIAG-2D-pre SONU ────────────────────────────────────────────────

        # ── PLAKA-2.G: Per-pipeline concat ─────────────────────────────────
        # Cross-pipeline merge mutant string'ler üretebiliyor (örn '34NNF34MNF012012').
        # Her pipeline kendi içinde concat edilirse, plakanın tam string'i tek pipeline'da
        # kalmış olabilir (örn Pipeline B: '34NNF' + '012' = '34NNF012' ✓).
        _per_pipeline_results = []  # (pname, joined_plate, joined_conf)
        for _pname in pipe_names:
            _frags = [r for r in all_results if r[3] == _pname]
            if not _frags:
                continue
            _sorted_pipe = sorted(_frags, key=lambda r: r[0][0][0])
            _joined_pipe = ''.join(r[1] for r in _sorted_pipe if r[2] > 0.05)
            if not _joined_pipe:
                continue
            _joined_plate_pipe = _validate_plate(_joined_pipe)
            if _joined_plate_pipe:
                _per_conf = max((r[2] for r in _sorted_pipe if r[2] > 0.05), default=0.0)
                _per_pipeline_results.append((_pname, _joined_plate_pipe, _per_conf))
                logger.info(
                    "[PLAKA-2.G] %s per-pipeline: ham=%r → %s ✓ (conf=%.2f)",
                    _pname, _joined_pipe, _joined_plate_pipe, _per_conf,
                )
            else:
                logger.info(
                    "[PLAKA-2.G] %s per-pipeline: ham=%r → geçersiz ✗",
                    _pname, _joined_pipe,
                )

        if _per_pipeline_results:
            _best_per = max(_per_pipeline_results, key=lambda x: x[2])
            _best_pname, _best_plate, _best_per_conf = _best_per
            logger.info(
                "[PLAKA-2.G] Per-pipeline en iyi: %s → %s (conf=%.2f)",
                _best_pname, _best_plate, _best_per_conf,
            )
            if best_text is None or _best_per_conf > best_conf:
                best_text = _best_plate
                best_conf = _best_per_conf
        # Per-pipeline başarısız veya yetersizse, aşağıdaki cross-pipeline merge fallback olur
        # ── PLAKA-2.G SONU ──────────────────────────────────────────────────

        # ── Birleştirilmiş metin dene (ikincil yöntem) ───────────────────
        # Tüm OCR parçalarını x koordinatına göre sırala ve birleştir:
        # örn. '34' + 'MNF' + '012' → '34MNF012'
        if all_results:
            sorted_results = sorted(all_results, key=lambda r: r[0][0][0])
            joined = ''.join(
                text for (_, text, conf, _pname) in sorted_results if conf > 0.05
            )
            joined_plate = _validate_plate(joined)
            if joined_plate:
                valid_confs = [conf for (_, _, conf, _) in sorted_results if conf > 0.05]
                joined_conf = max(valid_confs) if valid_confs else 0.0
                msg = f"[BİRLEŞTİRME] ham={joined!r} → {joined_plate} ✓ (conf={joined_conf:.2f})"
                logger.info(msg)
                self._debug_logs.append(msg)
                if best_text is None or joined_conf > best_conf:
                    best_text = joined_plate
                    best_conf = joined_conf
            else:
                msg = f"[BİRLEŞTİRME] ham={joined!r} → geçersiz ✗"
                logger.info(msg)
                self._debug_logs.append(msg)

        if not any_result:
            gh, gw = gray.shape[:2]
            msg = f"[OCR] Crop:{gw}×{gh} — 3 pipeline denendi, hiç metin bulunamadı"
            logger.info(msg)
            self._debug_logs.append(msg)

        return best_text, best_conf

    def _save_debug_crop(self, crop: np.ndarray) -> None:
        """Her OCR çağrısında crop'u debug_crops/ klasörüne kaydeder (max 10 dosya)."""
        try:
            _DEBUG_CROP_DIR.mkdir(parents=True, exist_ok=True)
            idx  = self._debug_crop_idx % _DEBUG_CROP_MAX
            path = _DEBUG_CROP_DIR / f"debug_crop_{idx:03d}.jpg"
            cv2.imwrite(str(path), crop)
            self._debug_crop_idx += 1
        except Exception as exc:
            logger.debug("debug crop kaydedilemedi: %s", exc)

    # ── PLAKA-2.H: Bilinmeyen plaka kaydı ────────────────────────────────────

    def _save_unknown_plate(
        self,
        frame: np.ndarray,
        crop: Optional[np.ndarray],
        ham_plate: str,
        conf: float,
    ) -> None:
        """
        Bilinmeyen (whitelist'te olmayan) plakayı dosyaya kaydet.

        Klasör yapısı: unknown_plates/YYYY-MM-DD/
        Dosyalar:
          - HH-MM-SS_crop_<ham>_conf<X>.jpg
          - HH-MM-SS_frame_<ham>.jpg

        Throttle: aynı ham_plate son N saniye içinde kaydedildiyse atla.
        """
        now = time.time()
        last_save = self._unknown_last_save.get(ham_plate, 0)
        if now - last_save < self._unknown_throttle_seconds:
            logger.debug(
                "[Bilinmeyen] %r throttle (%.1fs içinde tekrar) — atlandı",
                ham_plate, now - last_save,
            )
            return

        try:
            dt = datetime.now()
            day_dir = self._unknown_save_dir / dt.strftime('%Y-%m-%d')
            day_dir.mkdir(parents=True, exist_ok=True)

            time_prefix = dt.strftime('%H-%M-%S')
            safe_ham = re.sub(r'[^A-Z0-9]', '', ham_plate)

            if crop is not None and crop.size > 0:
                crop_path = day_dir / f"{time_prefix}_crop_{safe_ham}_conf{conf:.2f}.jpg"
                cv2.imwrite(str(crop_path), crop)

            frame_path = day_dir / f"{time_prefix}_frame_{safe_ham}.jpg"
            cv2.imwrite(str(frame_path), frame)

            self._unknown_last_save[ham_plate] = now

            logger.info(
                "[Bilinmeyen] Kaydedildi: ham=%r conf=%.2f → %s/",
                ham_plate, conf, day_dir,
            )

            if self._unknown_plate_callback is not None:
                try:
                    self._unknown_plate_callback(ham_plate)
                except Exception as cb_exc:
                    logger.error("[Bilinmeyen] Callback hatası: %s", cb_exc)
        except Exception as e:
            logger.error("[Bilinmeyen] Kayıt hatası: %s", e)

    # ── Oylama ───────────────────────────────────────────────────────────────

    def _vote(self, candidate: str) -> Optional[str]:
        """vote_count okumada vote_threshold+ eşleşme gerekir."""
        self._vote_buffer.append(candidate)
        buf_list = list(self._vote_buffer)

        if len(buf_list) < self.vote_count:
            msg = (
                f"[OYLAMA] Buffer: {buf_list} — "
                f"henüz yeterli değil ({len(buf_list)}/{self.vote_count})"
            )
            logger.info(msg)
            self._debug_logs.append(msg)
            return None

        counts: dict[str, int] = {}
        for p in buf_list:
            counts[p] = counts.get(p, 0) + 1

        for plate, cnt in counts.items():
            if cnt >= self.vote_threshold:
                self._vote_buffer.clear()
                msg = (
                    f"[OYLAMA] Buffer: {buf_list} — "
                    f"sonuç: {plate} ✓ ({cnt}/{self.vote_count} eşleşme)"
                )
                logger.info(msg)
                self._debug_logs.append(msg)
                return plate

        msg = (
            f"[OYLAMA] Buffer: {buf_list} — "
            f"eşleşme yok (gerekli: {self.vote_threshold}/{self.vote_count})"
        )
        logger.info(msg)
        self._debug_logs.append(msg)
        return None

    # ── Log throttle ─────────────────────────────────────────────────────────

    def _should_log(self, plate: str) -> bool:
        now = time.time()
        if now - self._last_logged.get(plate, 0.0) >= self.throttle_secs:
            self._last_logged[plate] = now
            return True
        return False

    # ── Sıfırlama ────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Buffer ve oylama sıfırla — sistem durdurulduğunda çağrılır."""
        self._vote_buffer.clear()
        self._last_logged.clear()
        self._crop_buffer.clear()
        self._collection_start = 0.0
        self._debug_logs.clear()

    # ── PLAKA-2.I: Whitelist hot-reload ──────────────────────────────────────

    def reload_whitelist(self) -> int:
        """
        Whitelist dosyasını yeniden yükle (UI değişiklik sonrası).

        Liste referans değişimi GIL ile atomic — process_frame worker thread'i
        match_plate çağrısında ya eski ya yeni listeye bakar, ikisi de geçerli.

        Returns:
            Yüklenen plaka sayısı
        """
        new_whitelist = load_whitelist(self._whitelist_path)
        self._whitelist = new_whitelist
        self._whitelist_active = len(new_whitelist) > 0

        if self._whitelist_active:
            logger.info(
                "[Whitelist] Hot-reload — %d plaka aktif",
                len(new_whitelist),
            )
        else:
            logger.info("[Whitelist] Hot-reload — DEVRE DIŞI (dosya boş veya yok)")

        return len(new_whitelist)
