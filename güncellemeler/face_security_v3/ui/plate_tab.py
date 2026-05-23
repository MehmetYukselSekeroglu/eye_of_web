"""
Plaka Tanıma Sekmesi — Tkinter UI  (YOLO + Çoklu Pipeline EasyOCR)

Başlangıç: Sistem KAPALI — kamera ve OCR başlamaz.
Toggle butonuyla AKTİF/PASİF yapılır.

Layout:
  Üst (y=5..55):    Büyük toggle butonu (tam genişlik)
  Sol (x=20..880):  Kamera görüntüsü 854×480 — YOLO bbox'ları üst üste
  Sağ (x=900..):    Durum · SON TESPİT · plaka kırpımı · terminal log

Threading mimarisi:
  _camera_loop  → hızlı frame okuma; hareket algılama; OCR yapmaz
  _analysis_loop→ _analysis_queue'dan frame alır, OCR çalıştırır, _result_queue'ya koyar
  _update_gui   → hareket yoksa 100ms, hareketteyse 33ms'de tetiklenir

CPU optimizasyonları:
  • Hareket algılama (160×90 fark): hareket yoksa OCR hiç çalışmaz
  • Analiz en az _ANALYSIS_INTERVAL saniyede bir — sürekli kuyruklama yok
  • _camera_loop'ta frame.copy() kaldırıldı; resize zaten yeni array yaratır
  • Idle'da GUI güncelleme 10fps'e düşer (30fps yerine)
"""
import logging
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import *
from tkinter import messagebox

import cv2
import numpy as np
from PIL import Image, ImageTk

import config
from detection.plate_processor import PlateProcessor
from detection.plate_whitelist import get_ui_plates, save_whitelist, normalize_plate

logger = logging.getLogger(__name__)

CAM_W, CAM_H             = 854, 480
PREVIEW_W, PREVIEW_H     = 280, 80    # Tespit edilen plaka kırpımı
_Y_OFFSET                = 55         # Toggle (h=45) + 10px boşluk
# PLAKA-2.E: 1280×720 (HD) — kamera 1920×1080 verir, 640×480 aspect bozar (4:3
# vs 16:9, ~%25 yatay sıkışma). 1280×720 doğru aspect (16:9) ve plaka detayını
# korur. CPU yükü i5-10400F için rahat (YOLO ~150ms, %50 inference budget).
_ANALYSIS_W, _ANALYSIS_H = 1280, 720   # Analize gönderilen frame boyutu

# ── Hareket algılama sabitleri ─────────────────────────────────────────────
_MOTION_W, _MOTION_H  = 160, 90   # Fark hesabı çok küçük boyutta → hafif CPU
_MOTION_THRESHOLD     = 25        # Piksel farkı eşiği (0-255)
_MOTION_MIN_PIXELS    = 500       # Bu kadar piksel değişmezse hareket yok sayılır
_MOTION_REF_INTERVAL  = 2.0       # Referans frame güncelleme süresi (sn)

# ── Analiz hız sınırı ─────────────────────────────────────────────────────
# Hareket algılandığında her 0.3 sn'de bir frame gönder → 10 frame ~3 sn'de dolur.
# Hareket yoksa her 2 sn'de bir gönder → sabit araçlar da tespit edilir.
_ANALYSIS_INTERVAL    = 0.3       # Harekette: ardışık frame gönderimleri arasındaki süre (sn)
_STATIC_INTERVAL      = 2.0       # Hareket olmasa bile bu kadar süreden fazla beklenirse gönder


class PlateTab:
    """
    Plaka tanıma sekmesi — YOLO araç tespiti + 3-pipeline EasyOCR.

    Model yüklenene kadar toggle butonu DISABLED kalır (yeşil → aktif olunca kırmızı).
    """

    def __init__(self, parent: Frame, root: Tk) -> None:
        self._parent = parent
        self.root    = root

        self._active     = False
        self._running    = False
        self._cam_thread:  threading.Thread | None = None
        self._anal_thread: threading.Thread | None = None

        # Kamera frame'ini kamera→GUI thread arasında paylaşmak için
        self._frame_lock    = threading.Lock()
        self._current_frame: object = None

        # Son analiz sonucu — GUI thread'de tutulur, bbox çizmek için
        self._last_result: dict | None = None

        # Hareket algılama durumu (camera thread yazar, GUI thread okur — GIL korumalı)
        self._motion_detected:   bool              = False
        self._prev_gray:         object            = None   # np.ndarray | None
        self._motion_ref_time:   float             = 0.0
        self._last_analysis_time: float            = 0.0

        # OCR motoru (Vehicle YOLO + Plaka YOLO + EasyOCR) — initialize() ayrı thread'de çağrılır
        self._processor = PlateProcessor(
            vote_count           = getattr(config, "PLATE_VOTE_COUNT",         5),
            vote_threshold       = getattr(config, "PLATE_VOTE_THRESHOLD",     3),
            throttle_secs        = getattr(config, "PLATE_DUPLICATE_SECONDS", 10),
            yolo_model_path      = getattr(config, "PLATE_YOLO_MODEL",        ""),
            yolo_conf            = getattr(config, "PLATE_YOLO_CONF",       0.25),
            vehicle_model_path   = "",  # default = yolov8n.pt auto-download
            detector_conf        = getattr(config, "PLATE_DETECTOR_CONF",  0.25),
            use_contour_fallback = getattr(config, "USE_CONTOUR_FALLBACK", False),
            unknown_plate_callback = self._on_unknown_plate,
        )

        # Telegram callback'leri ve komut kuyruğu
        self._notify_callback = None   # Callable[[str, np.ndarray | None], None]
        self._toggle_callback = None   # Callable[[bool], None]
        self._plate_cmd_queue: queue.Queue = queue.Queue()

        # Kuyruklar
        self._log_queue:      queue.Queue = queue.Queue()
        # maxsize=2: 0.3s interval ile gelen frame'ler; YOLO süresi ~50ms olduğu için
        # 2 frame buffer yeterli — analiz meşgulken fazlasını at
        self._analysis_queue: queue.Queue = queue.Queue(maxsize=2)
        # maxsize=5: GUI thread yavaşsa sonuçlar birikir ama fazla bellek yenmez
        self._result_queue:   queue.Queue = queue.Queue(maxsize=5)

        log_dir = Path(getattr(config, "LOG_DIR", "logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = log_dir / "kapi_giris_log.txt"

        self._build_ui()
        threading.Thread(target=self._init_model, daemon=True).start()
        self._update_gui()

    # ═════════════════════════════════════════════════════════════════════════
    # UI İNŞAAT
    # ═════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        f  = self._parent
        yo = _Y_OFFSET

        # ── Toggle (tam genişlik, en üstte) ──────────────────────────────
        self._toggle_btn = Button(
            f,
            text  = "  ▶  PLAKA TANIMAYI AKTİF ET  ",
            bg="#44ff44", fg="#000000",
            font=("Consolas", 13, "bold"),
            state=DISABLED,
            cursor="hand2",
            activebackground="#66ff66", activeforeground="#000",
            relief="raised", bd=2,
            command=self._toggle_system,
        )
        self._toggle_btn.place(x=20, y=5, width=1220, height=45)

        # ── PLAKA-2.I-2: Whitelist yönetim butonu (üst satır sağ) ───────
        self._whitelist_btn = Button(
            f,
            text="  ⚙  WHITELIST YÖNET  ",
            bg="#3399ff", fg="white",
            font=("Consolas", 11, "bold"),
            cursor="hand2",
            activebackground="#5fb3ff", activeforeground="white",
            relief="raised", bd=2,
            command=self._open_whitelist_dialog,
        )
        self._whitelist_btn.place(x=1250, y=5, width=370, height=45)

        # ── Kamera görüntüsü ──────────────────────────────────────────────
        self._cam_label = Label(f, bg="black", relief="sunken", bd=1)
        self._cam_label.place(x=20, y=yo, width=CAM_W, height=CAM_H)

        # Sistem pasif / bağlanıyor overlay
        self._cam_overlay = Label(
            f,
            text="⬡  Sistem Pasif\nAktif etmek için butona basın",
            bg="#0d1117", fg="#444444",
            font=("Consolas", 14), justify=CENTER,
        )
        self._cam_overlay.place(x=20, y=yo, width=CAM_W, height=CAM_H)
        self._cam_overlay.lift()

        # Araç sayacı (kamera görüntüsü altında)
        self._vehicle_count_lbl = Label(
            f,
            text="Tespit edilen araç: —",
            bg="#0d1117", fg="#3399ff",
            font=("Consolas", 10),
        )
        self._vehicle_count_lbl.place(x=20, y=yo + CAM_H + 5)

        # ── PLAKA-2.I-3: SON OKUMALAR (sol panel, vehicle label altında) ──
        Label(
            f, text="SON OKUMALAR",
            bg="#0d1117", fg="#00ff41",
            font=("Consolas", 11, "bold"),
        ).place(x=20, y=yo + CAM_H + 30, width=200, height=20)

        self._history_text = Text(
            f,
            bg="#000", fg="#aaa",
            font=("Consolas", 10),
            height=10, width=50,
            state="disabled",
            wrap="none",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#444",
        )
        self._history_text.place(x=20, y=yo + CAM_H + 55, width=800, height=180)

        self._history_text.tag_configure("known",     foreground="#44ff44")
        self._history_text.tag_configure("unknown",   foreground="#ffcc00")
        self._history_text.tag_configure("timestamp", foreground="#888")

        # ── Sağ: başlık + durum ───────────────────────────────────────────
        Label(
            f, text="⬡  PLAKA TANIMA SİSTEMİ",
            bg="#0d1117", fg="#00ff41", font=("Consolas", 13, "bold"),
        ).place(x=900, y=yo, width=728)

        self._status_lbl = Label(
            f, text="MODEL YÜKLENİYOR...",
            bg="#0d1117", fg="#ffcc00", font=("Consolas", 10),
        )
        self._status_lbl.place(x=900, y=yo + 28, width=728)

        # Pipeline durumu
        self._pipeline_lbl = Label(
            f, text="Pipeline: —",
            bg="#0d1117", fg="#888888", font=("Consolas", 9),
        )
        self._pipeline_lbl.place(x=900, y=yo + 50, width=728)

        # ── Son tespit plakası ────────────────────────────────────────────
        Label(f, text="SON TESPİT:", bg="#0d1117", fg="#00ff41",
              font=("Consolas", 10, "bold")).place(x=900, y=yo + 78)

        self._plate_lbl = Label(
            f, text="---", bg="#000", fg="#00ff41",
            font=("Consolas", 26, "bold"), relief="groove", bd=2,
        )
        self._plate_lbl.place(x=900, y=yo + 100, width=360, height=56)

        self._time_lbl = Label(
            f, text="", bg="#0d1117", fg="#888888", font=("Consolas", 9),
        )
        self._time_lbl.place(x=900, y=yo + 160)

        # ── Plaka kırpımı önizlemesi ──────────────────────────────────────
        Label(f, text="TESPİT KİRPIMI:", bg="#0d1117", fg="#3399ff",
              font=("Consolas", 9, "bold")).place(x=1276, y=yo + 78)

        self._preview_lbl = Label(f, bg="#111", relief="sunken", bd=1)
        self._preview_lbl.place(x=1276, y=yo + 100, width=PREVIEW_W, height=PREVIEW_H)

        # ── Terminal log ──────────────────────────────────────────────────
        Label(f, text="TERMINAL LOG", bg="#0d1117", fg="#00ff41",
              font=("Consolas", 9, "bold")).place(x=900, y=yo + 192)

        log_outer = Frame(f, bg="#000", bd=1, relief="sunken")
        log_outer.place(x=900, y=yo + 212, width=728, height=698)

        self._log_box = Text(
            log_outer, bg="#000", fg="#00ff41",
            font=("Consolas", 10), wrap=WORD,
            insertbackground="#00ff41", bd=0,
        )
        for tag, color in [
            ("plate",  "#00ff41"),
            ("warn",   "#ffcc00"),
            ("error",  "#ff3333"),
            ("info",   "#3399ff"),
            ("system", "#888888"),
        ]:
            self._log_box.tag_config(tag, foreground=color)

        sb = Scrollbar(log_outer, command=self._log_box.yview,
                       bg="#1a1a1a", troughcolor="#111")
        self._log_box.config(yscrollcommand=sb.set)
        sb.pack(side=RIGHT, fill=Y)
        self._log_box.pack(side=LEFT, fill=BOTH, expand=True)

    # ═════════════════════════════════════════════════════════════════════════
    # MODEL BAŞLATMA
    # ═════════════════════════════════════════════════════════════════════════

    def _init_model(self) -> None:
        self._log_queue.put(
            ("[SİSTEM] YOLO + EasyOCR yükleniyor, lütfen bekleyin...", "system")
        )
        ok = self._processor.initialize()
        if ok:
            self._log_queue.put(
                ("[SİSTEM] Model hazır. 'PLAKA TANIMAYI AKTİF ET' butonuna basın.", "info")
            )
            self.root.after(0, lambda: self._toggle_btn.config(state=NORMAL))
            self.root.after(0, lambda: self._status_lbl.config(
                text="SİSTEM HAZIR — Pasif", fg="#00ff41"))
            self.root.after(0, lambda: self._pipeline_lbl.config(
                text="Pipeline: A (CLAHE+Adaptive)  B (Bilateral+Otsu)  C (Sharpen+BinaryInv) | 10 frame → top-5 Laplacian → OCR"))
        else:
            err = self._processor.error or "Bilinmeyen hata"
            self._log_queue.put((f"[HATA] Model yüklenemedi: {err}", "error"))
            self.root.after(0, lambda: self._status_lbl.config(
                text=f"MODEL HATASI: {err[:70]}", fg="#ff3333"))

    # ═════════════════════════════════════════════════════════════════════════
    # TOGGLE
    # ═════════════════════════════════════════════════════════════════════════

    def _toggle_system(self) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        if self._active:
            self._active = False
            self._stop_camera()
            self._toggle_btn.config(
                text="  ▶  PLAKA TANIMAYI AKTİF ET  ",
                bg="#44ff44", fg="#000000", activebackground="#66ff66",
            )
            self._status_lbl.config(text="SİSTEM HAZIR — Pasif", fg="#00ff41")
            self._log_queue.put(
                (f"[{ts}] [SİSTEM] Plaka tanıma sistemi PASİF edildi.", "warn")
            )
        else:
            self._active = True
            self._toggle_btn.config(
                text="  ⏹  PLAKA TANIMAYI KAPAT  ",
                bg="#ff4444", fg="white", activebackground="#ff6666",
            )
            self._status_lbl.config(text="SİSTEM AKTİF", fg="#00ff41")
            self._log_queue.put(
                (f"[{ts}] [SİSTEM] Plaka tanıma sistemi AKTİF edildi.", "plate")
            )
            self._start_camera()

        if self._toggle_callback:
            try:
                self._toggle_callback(self._active)
            except Exception as exc:
                logger.error("toggle_callback hatası: %s", exc)

    # ═════════════════════════════════════════════════════════════════════════
    # PLAKA-2.I-2: WHITELIST YÖNETIM DIALOG'U
    # ═════════════════════════════════════════════════════════════════════════

    def _open_whitelist_dialog(self) -> None:
        """Whitelist yönetim dialog'unu aç (modal Toplevel)."""
        try:
            WhitelistDialog(parent=self.root, processor=self._processor)
        except Exception as exc:
            logger.error("Whitelist dialog hatası: %s", exc)
            messagebox.showerror("Hata", f"Whitelist dialog açılamadı: {exc}")

    # ═════════════════════════════════════════════════════════════════════════
    # KAMERA KONTROLÜ
    # ═════════════════════════════════════════════════════════════════════════

    def _start_camera(self) -> None:
        url = getattr(config, "PLATE_CAM_URL", "")
        if not url:
            self._log_queue.put(
                ("[HATA] .env dosyasında PLATE_CAM_URL tanımlı değil!", "error")
            )
            return
        self._running = True
        self._last_result     = None
        self._prev_gray       = None    # hareket algılama sıfırla
        self._motion_ref_time = 0.0
        self._last_analysis_time = 0.0
        self._motion_detected = False
        self._cam_overlay.config(text="⬡  BAĞLANIYOR...", fg="#ffcc00")
        self._cam_overlay.lift()

        self._cam_thread = threading.Thread(
            target=self._camera_loop, args=(url,), daemon=True
        )
        self._cam_thread.start()

        self._anal_thread = threading.Thread(
            target=self._analysis_loop, daemon=True
        )
        self._anal_thread.start()

        ts = datetime.now().strftime("%H:%M:%S")
        self._log_queue.put(
            (f"[{ts}] [SİSTEM] Kamera başlatıldı: {url[:55]}...", "info")
        )

    def _stop_camera(self) -> None:
        self._running = False
        self._processor.reset()   # toplama buffer + oylama sıfırla
        with self._frame_lock:
            self._current_frame = None
        self._cam_overlay.config(
            text="⬡  Sistem Pasif\nAktif etmek için butona basın", fg="#444444"
        )
        self._cam_overlay.lift()
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_queue.put((f"[{ts}] [SİSTEM] Kamera durduruldu.", "warn"))

    # ═════════════════════════════════════════════════════════════════════════
    # KAMERA DÖNGÜSÜ — sadece frame okur, OCR yapmaz
    # ═════════════════════════════════════════════════════════════════════════

    def _camera_loop(self, url: str) -> None:
        cap = cv2.VideoCapture(url)
        # Eski frame'lerin birikimini önle
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            ts = datetime.now().strftime("%H:%M:%S")
            self._log_queue.put(
                (f"[{ts}] [HATA] Kamera bağlantısı kurulamadı!", "error")
            )
            self.root.after(0, lambda: self._cam_overlay.config(
                text="⬡  BAĞLANTI HATASI", fg="#ff3333"
            ))
            self._running = False
            self._active  = False
            self.root.after(0, lambda: self._toggle_btn.config(
                text="  ▶  PLAKA TANIMAYI AKTİF ET  ",
                bg="#44ff44", fg="#000000",
            ))
            return

        self.root.after(0, self._cam_overlay.lower)
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_queue.put((f"[{ts}] [SİSTEM] Kamera bağlandı.", "info"))

        while self._running:
            # grab() ile buffer'daki eski kareleri at, sadece en yeni kareyi al
            cap.grab()
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            now = time.time()

            # ── Frame'i GPU'ya bir kez yükle; hareket algılama ve display
            #    resize bu UMat üzerinde çalışır — CPU↔GPU transfer sayısı azalır
            u_frame = cv2.UMat(frame)

            # ── Hareket algılama — GPU'da 160×90 grayscale fark ───────────
            u_small_gray = cv2.resize(
                cv2.cvtColor(u_frame, cv2.COLOR_BGR2GRAY),
                (_MOTION_W, _MOTION_H),
            )
            if self._prev_gray is not None:
                u_diff        = cv2.absdiff(self._prev_gray, u_small_gray)
                _, u_mask     = cv2.threshold(u_diff, _MOTION_THRESHOLD, 255,
                                              cv2.THRESH_BINARY)
                motion_pixels = cv2.countNonZero(u_mask)
                has_motion    = motion_pixels > _MOTION_MIN_PIXELS
            else:
                has_motion = False

            # Referans frame'i UMat olarak sakla (GPU'da kalır)
            if now - self._motion_ref_time >= _MOTION_REF_INTERVAL:
                self._prev_gray       = u_small_gray
                self._motion_ref_time = now

            self._motion_detected = has_motion

            # ── Display resize GPU'da, .get() ile numpy'a indir ──────────
            display = cv2.resize(u_frame, (CAM_W, CAM_H)).get()
            with self._frame_lock:
                self._current_frame = display

            # ── Analiz kuyruğu ─────────────────────────────────────────────
            # Hareketteyse 0.3 sn'de bir (hızlı toplama),
            # hareket yoksa 2 sn'de bir (sabit araç desteği).
            interval = _ANALYSIS_INTERVAL if has_motion else _STATIC_INTERVAL
            if (now - self._last_analysis_time) >= interval:
                self._last_analysis_time = now
                try:
                    self._analysis_queue.put_nowait(frame)
                except queue.Full:
                    pass  # Analiz hâlâ meşgul, bu frame'i atla

        cap.release()

    # ═════════════════════════════════════════════════════════════════════════
    # ANALİZ DÖNGÜSÜ — OCR burада, kamera thread'inden bağımsız
    # ═════════════════════════════════════════════════════════════════════════

    def _analysis_loop(self) -> None:
        """
        YOLO tespiti + OCR bu thread'de çalışır.
        Her frame'de YOLO (~50ms) çalışır; OCR yalnızca 10 frame dolunca tetiklenir.
        Kamera ve GUI thread'lerini hiç bloke etmez.
        """
        while self._running:
            try:
                frame = self._analysis_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # Analiz çözünürlüğüne küçült
            small = cv2.resize(frame, (_ANALYSIS_W, _ANALYSIS_H))

            # process_frame: her çağrıda YOLO + crop toplama.
            # Buffer dolduğunda OCR tetiklenir (~3 sn'de bir).
            plate, boxes, crop = self._processor.process_frame(small)

            # YOLO debug logu — her frame'de güncellenir
            yolo_log = getattr(self._processor, '_last_yolo_log', '')
            if yolo_log:
                self._log_queue.put((yolo_log, "system"))
                self._processor._last_yolo_log = ""

            # OCR / oylama debug logları — her OCR turunda biriken liste
            dbg_logs = getattr(self._processor, '_debug_logs', [])
            if dbg_logs:
                for _msg in list(dbg_logs):
                    self._log_queue.put((_msg, "info"))
                dbg_logs.clear()

            # Toplama ilerlemesini log'a yaz
            n = self._processor.collection_progress
            if n > 0 and n % 5 == 0:   # 5. ve 10. frame'de log
                ts = datetime.now().strftime("%H:%M:%S")
                self._log_queue.put(
                    (f"[{ts}] [ANALİZ] Frame toplama: {n}/10", "system")
                )

            # Sonucu GUI kuyruğuna koy (doluysa eskisini at)
            result = {'plate': plate, 'boxes': boxes, 'crop': crop}
            try:
                self._result_queue.put_nowait(result)
            except queue.Full:
                try:
                    self._result_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._result_queue.put_nowait(result)
                except queue.Full:
                    pass

    # ═════════════════════════════════════════════════════════════════════════
    # PLAKA TESPİT
    # ═════════════════════════════════════════════════════════════════════════

    def _on_plate_detected(self, plate: str) -> None:
        """_update_gui (ana thread) tarafından çağrılır."""
        now     = datetime.now()
        ts      = now.strftime("%H:%M:%S")
        full_ts = now.strftime("%Y-%m-%d %H:%M:%S")

        self._log_queue.put((f"[{ts}] ✅ PLAKA TESPİT: {plate}", "plate"))
        self._update_plate_display(plate, ts)
        self._add_reading_to_history(plate, "whitelist")

        try:
            with self._log_file.open("a", encoding="utf-8") as fh:
                fh.write(f"[{full_ts}] PLAKA: {plate}\n")
        except Exception as exc:
            logger.error("Log yazılamadı: %s", exc)

        if self._notify_callback:
            with self._frame_lock:
                frame = self._current_frame.copy() if self._current_frame is not None else None
            try:
                self._notify_callback(plate, frame)
            except Exception as exc:
                logger.error("notify_callback hatası: %s", exc)

    def _update_plate_display(self, plate: str, ts: str) -> None:
        try:
            self._plate_lbl.config(text=plate)
            self._time_lbl.config(text=f"Saat: {ts}")
        except Exception:
            pass

    # ── PLAKA-2.I-3: SON OKUMALAR widget yardımcıları ────────────────────────

    def _add_reading_to_history(self, plate: str, source: str) -> None:
        """
        Sol panel SON OKUMALAR widget'ına yeni satır ekle.
        Sadece ana thread'den çağrılmalı.

        Args:
            plate:  Plaka string (örn. "34NNF012")
            source: "whitelist" veya "bilinmeyen"
        """
        try:
            ts = datetime.now().strftime("%H:%M:%S")

            if source == "whitelist":
                icon, tag, desc = "✓", "known",   "(whitelist)"
            else:
                icon, tag, desc = "✗", "unknown", "(bilinmeyen)"

            line = f"[{ts}] {icon} {plate} {desc}\n"

            self._history_text.config(state="normal")
            self._history_text.insert("1.0", line)
            self._history_text.tag_add(tag, "1.0", "1.end")

            total_lines = int(self._history_text.index("end-1c").split(".")[0])
            if total_lines > 10:
                self._history_text.delete("11.0", "end")

            self._history_text.config(state="disabled")
        except Exception as exc:
            logger.error("History ekleme hatası: %s", exc)

    def _on_unknown_plate(self, ham_plate: str) -> None:
        """
        Bilinmeyen plaka kaydedildiğinde processor'dan çağrılır.
        Worker thread'inden gelebilir — UI thread'e after(0,...) ile yönlendir.
        """
        try:
            self.root.after(0, lambda p=ham_plate: self._add_reading_to_history(p, "bilinmeyen"))
        except Exception as exc:
            logger.error("_on_unknown_plate yönlendirme hatası: %s", exc)

    # ═════════════════════════════════════════════════════════════════════════
    # GUI DÖNGÜSÜ — tüm widget güncellemeleri burada, ana thread'de
    # ═════════════════════════════════════════════════════════════════════════

    def _update_gui(self) -> None:
        # ── Telegram komut kuyruğunu işle (GUI thread'de güvenli) ────────
        try:
            while True:
                cmd = self._plate_cmd_queue.get_nowait()
                if cmd == "activate" and not self._active:
                    if str(self._toggle_btn["state"]) != "disabled":
                        self._toggle_system()
                elif cmd == "deactivate" and self._active:
                    self._toggle_system()
        except queue.Empty:
            pass

        # ── Log kuyruğunu boşalt ─────────────────────────────────────────
        try:
            while True:
                msg, tag = self._log_queue.get_nowait()
                self._add_log(msg, tag)
        except queue.Empty:
            pass

        # ── Durum etiketi: idle ↔ toplama ↔ OCR ─────────────────────────
        if self._active:
            n = self._processor.collection_progress
            if n > 0:
                self._status_lbl.config(
                    text=f"ANALİZ — Frame toplama: {n}/10  (en keskin 5 → OCR)",
                    fg="#ffcc00",
                )
            elif self._motion_detected:
                self._status_lbl.config(
                    text="SİSTEM AKTİF — Hareket algılandı, araç bekleniyor",
                    fg="#00ff41",
                )
            else:
                self._status_lbl.config(
                    text="SİSTEM AKTİF — İdle (hareket bekleniyor)",
                    fg="#888888",
                )

        # ── Analiz sonuçlarını işle ───────────────────────────────────────
        try:
            while True:
                result = self._result_queue.get_nowait()
                self._last_result = result

                # Araç sayacı
                cnt = len(result.get('boxes', []))
                self._vehicle_count_lbl.config(text=f"Tespit edilen araç: {cnt}")

                # Plaka kırpımı önizlemesi
                crop = result.get('crop')
                if crop is not None:
                    try:
                        pr     = cv2.resize(crop, (PREVIEW_W, PREVIEW_H))
                        pil    = Image.fromarray(cv2.cvtColor(pr, cv2.COLOR_BGR2RGB))
                        tk_img = ImageTk.PhotoImage(pil)
                        self._set_preview(tk_img)
                    except Exception:
                        pass

                # Onaylı plaka
                plate = result.get('plate')
                if plate:
                    self._on_plate_detected(plate)
        except queue.Empty:
            pass

        # ── Kamera karesini göster ────────────────────────────────────────
        with self._frame_lock:
            frame = self._current_frame

        if frame is not None:
            try:
                # Orijinal frame'i bozmamak için kopya al; bbox çizimi burada yapılır
                display = frame.copy()

                # Son analiz sonucundaki araç bbox'larını çiz
                # (Analiz 640×480 üzerinde yapıldı → display 854×480 ölçeğine çevir)
                if self._last_result:
                    boxes = self._last_result.get('boxes', [])
                    for (x1, y1, x2, y2) in boxes:
                        rx1 = int(x1 * CAM_W / _ANALYSIS_W)
                        ry1 = int(y1 * CAM_H / _ANALYSIS_H)
                        rx2 = int(x2 * CAM_W / _ANALYSIS_W)
                        ry2 = int(y2 * CAM_H / _ANALYSIS_H)
                        cv2.rectangle(display, (rx1, ry1), (rx2, ry2), (0, 180, 255), 2)
                        cv2.putText(
                            display, "ARAÇ", (rx1, max(0, ry1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 180, 255), 1,
                        )

                pil    = Image.fromarray(cv2.cvtColor(display, cv2.COLOR_BGR2RGB))
                tk_img = ImageTk.PhotoImage(pil)
                self._cam_label.config(image=tk_img)
                self._cam_label.image = tk_img
            except Exception:
                pass

        # Idle'da GUI yenileme 10fps, harekette 30fps — gereksiz render CPU'su önlenir
        next_ms = 33 if self._motion_detected else 100
        self.root.after(next_ms, self._update_gui)

    # ═════════════════════════════════════════════════════════════════════════
    # YARDIMCILAR
    # ═════════════════════════════════════════════════════════════════════════

    def _set_preview(self, tk_img) -> None:
        try:
            self._preview_lbl.config(image=tk_img)
            self._preview_lbl.image = tk_img
        except Exception:
            pass

    def _add_log(self, msg: str, tag: str = "system") -> None:
        try:
            self._log_box.insert(END, msg + "\n", tag)
            self._log_box.see(END)
        except Exception:
            pass

    # ═════════════════════════════════════════════════════════════════════════
    # TELEGRAM ENTEGRASYONU — callback + komut kuyruğu
    # ═════════════════════════════════════════════════════════════════════════

    def set_notification_callback(self, cb) -> None:
        """Plaka onaylandığında cb(plate: str, frame: np.ndarray | None) çağrılır."""
        self._notify_callback = cb

    def set_toggle_callback(self, cb) -> None:
        """Sistem açılıp kapandığında cb(active: bool) çağrılır."""
        self._toggle_callback = cb

    def enqueue_command(self, cmd: str) -> None:
        """
        Telegram thread'inden GUI thread'ine komut gönderir.
        Desteklenen değerler: 'activate', 'deactivate'
        """
        try:
            self._plate_cmd_queue.put_nowait(cmd)
        except queue.Full:
            pass

    def stop(self) -> None:
        self._running = False
        self._active  = False


# ═════════════════════════════════════════════════════════════════════════════
# PLAKA-2.I-2: Whitelist Yönetim Dialog'u
# ═════════════════════════════════════════════════════════════════════════════

class WhitelistDialog(Toplevel):
    """
    Whitelist yönetim dialog'u (modal Toplevel).

    UI bölümündeki plakaları listeler, ekle/sil/kaydet sunar.
    Kaydet → save_whitelist() + processor.reload_whitelist() (hot-reload).
    İptal/kapatma → kaydedilmemiş değişiklik varsa onay sorulur.
    """

    DIALOG_W = 560
    DIALOG_H = 540

    BG = "#0d1117"
    FG = "#00ff41"
    ENTRY_BG = "#333"
    ENTRY_FG = "white"
    HINT_FG = "#888"
    STATUS_FG = "#aaa"

    def __init__(self, parent: Tk, processor: PlateProcessor) -> None:
        super().__init__(parent)
        self._processor = processor
        self._whitelist_path = processor._whitelist_path
        self._dirty = False

        self.title("Plaka Beyaz Listesi — Yönetim")
        self.configure(bg=self.BG)
        self.resizable(False, False)

        self._center_window()

        self.transient(parent)
        self.grab_set()
        self.focus_force()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self._setup_widgets()
        self._load_existing()

        # Modal bekle — dialog kapanana dek caller bloklanır
        self.wait_window(self)

    def _center_window(self) -> None:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - self.DIALOG_W) // 2
        y = (sh - self.DIALOG_H) // 2
        self.geometry(f"{self.DIALOG_W}x{self.DIALOG_H}+{x}+{y}")

    def _setup_widgets(self) -> None:
        Label(
            self, text="UI Yönetimli Plakalar",
            bg=self.BG, fg=self.FG,
            font=("Consolas", 13, "bold"),
        ).pack(pady=(15, 5))

        Label(
            self,
            text="(Dosyadaki manuel yorumlu plakalar burada gözükmez)",
            bg=self.BG, fg=self.HINT_FG,
            font=("Consolas", 9),
        ).pack(pady=(0, 10))

        self._listbox = Listbox(
            self,
            selectmode=SINGLE,
            bg="#000", fg=self.FG,
            font=("Consolas", 11),
            width=50, height=12,
            highlightthickness=1,
            highlightbackground="#444",
            selectbackground="#003366",
        )
        self._listbox.pack(padx=20, pady=5)

        # Plaka entry satırı
        plate_row = Frame(self, bg=self.BG)
        plate_row.pack(pady=(15, 0), padx=20, fill="x")

        Label(plate_row, text="Plaka:", bg=self.BG, fg=self.FG,
              font=("Consolas", 11)).pack(side="left")

        self._plate_var = StringVar()
        self._plate_entry = Entry(
            plate_row, textvariable=self._plate_var,
            bg=self.ENTRY_BG, fg=self.ENTRY_FG,
            font=("Consolas", 12), width=20,
            insertbackground="white",
        )
        self._plate_entry.pack(side="left", padx=(10, 5))

        Label(plate_row, text="(34NNF012 — boşluksuz)",
              bg=self.BG, fg=self.HINT_FG,
              font=("Consolas", 9)).pack(side="left")

        # Yorum entry satırı
        comment_row = Frame(self, bg=self.BG)
        comment_row.pack(pady=(8, 0), padx=20, fill="x")

        Label(comment_row, text="Yorum:", bg=self.BG, fg=self.FG,
              font=("Consolas", 11)).pack(side="left")

        self._comment_var = StringVar()
        self._comment_entry = Entry(
            comment_row, textvariable=self._comment_var,
            bg=self.ENTRY_BG, fg=self.ENTRY_FG,
            font=("Consolas", 12), width=20,
            insertbackground="white",
        )
        self._comment_entry.pack(side="left", padx=(8, 5))

        Label(comment_row, text="(opsiyonel — anne araba, vb.)",
              bg=self.BG, fg=self.HINT_FG,
              font=("Consolas", 9)).pack(side="left")

        # Ekle / Sil
        action_row = Frame(self, bg=self.BG)
        action_row.pack(pady=15)

        Button(action_row, text="  + EKLE  ",
               bg="#44ff44", fg="black",
               font=("Consolas", 11, "bold"),
               cursor="hand2",
               command=self._on_add).pack(side="left", padx=5)

        Button(action_row, text="  - SEÇİLENİ SİL  ",
               bg="#ffcc00", fg="black",
               font=("Consolas", 11, "bold"),
               cursor="hand2",
               command=self._on_delete).pack(side="left", padx=5)

        # Status
        self._status_var = StringVar(value="Hazır")
        Label(
            self, textvariable=self._status_var,
            bg=self.BG, fg=self.STATUS_FG,
            font=("Consolas", 10),
        ).pack(pady=(10, 5))

        # Kaydet / İptal
        save_row = Frame(self, bg=self.BG)
        save_row.pack(pady=10)

        Button(save_row, text="  💾 KAYDET  ",
               bg="#3399ff", fg="white",
               font=("Consolas", 12, "bold"),
               cursor="hand2",
               command=self._on_save).pack(side="left", padx=10)

        Button(save_row, text="  ✗ İPTAL  ",
               bg="#666", fg="white",
               font=("Consolas", 12, "bold"),
               cursor="hand2",
               command=self._on_cancel).pack(side="left", padx=10)

        # Enter ile EKLE shortcut
        self._plate_entry.bind("<Return>", lambda e: self._on_add())
        self._comment_entry.bind("<Return>", lambda e: self._on_add())

    def _load_existing(self) -> None:
        """Dosyadan UI plakalarını yükle."""
        try:
            plates = get_ui_plates(self._whitelist_path)
            self._listbox.delete(0, END)
            for plate, comment in plates:
                display = f"{plate}    # {comment}" if comment else plate
                self._listbox.insert(END, display)
            self._update_status()
        except Exception as e:
            messagebox.showerror("Hata", f"Whitelist okuma hatası: {e}", parent=self)

    def _get_current_plates(self) -> list:
        """Listbox'taki satırları (plate, comment) tuple listesine çevir."""
        result = []
        for i in range(self._listbox.size()):
            line = self._listbox.get(i)
            if "#" in line:
                plate_part, _, comment_part = line.partition("#")
                plate = plate_part.strip()
                comment = comment_part.strip()
            else:
                plate = line.strip()
                comment = ""
            if plate:
                result.append((plate, comment))
        return result

    def _update_status(self) -> None:
        count = self._listbox.size()
        dirty_mark = " ✏ (kaydedilmemiş)" if self._dirty else ""
        self._status_var.set(f"Liste: {count} plaka{dirty_mark}")

    def _on_add(self) -> None:
        plate_raw = self._plate_var.get().strip()
        if not plate_raw:
            messagebox.showwarning("Eksik", "Plaka girin", parent=self)
            return

        plate = normalize_plate(plate_raw)
        if len(plate) < 5 or len(plate) > 9:
            messagebox.showwarning(
                "Geçersiz Format",
                f"Plaka uzunluğu 5-9 karakter olmalı (girilen: '{plate}', {len(plate)} char)",
                parent=self,
            )
            return

        existing = [p for p, _ in self._get_current_plates()]
        if plate in existing:
            messagebox.showwarning("Zaten Var", f"'{plate}' zaten listede", parent=self)
            return

        comment = self._comment_var.get().strip()
        display = f"{plate}    # {comment}" if comment else plate
        self._listbox.insert(END, display)

        self._plate_var.set("")
        self._comment_var.set("")
        self._plate_entry.focus()

        self._dirty = True
        self._update_status()

    def _on_delete(self) -> None:
        sel = self._listbox.curselection()
        if not sel:
            messagebox.showinfo("Seçim yok", "Silinecek plakayı listeden seçin", parent=self)
            return
        idx = sel[0]
        line = self._listbox.get(idx)
        if not messagebox.askyesno(
            "Sil?",
            f"Bu satırı silmek istiyor musunuz?\n\n{line}",
            parent=self,
        ):
            return
        self._listbox.delete(idx)
        self._dirty = True
        self._update_status()

    def _on_save(self) -> None:
        try:
            plates = self._get_current_plates()
            ok = save_whitelist(self._whitelist_path, plates)
            if not ok:
                messagebox.showerror("Hata", "Dosya yazma başarısız", parent=self)
                return

            count = self._processor.reload_whitelist()

            self._dirty = False
            self._status_var.set(f"✓ Kaydedildi — {count} plaka aktif (hot-reload)")

            # 1.5 saniye sonra dialog kapan
            self.after(1500, self.destroy)
        except Exception as e:
            messagebox.showerror("Hata", f"Kayıt hatası: {e}", parent=self)

    def _on_cancel(self) -> None:
        if self._dirty:
            if not messagebox.askyesno(
                "Kaydedilmemiş Değişiklik",
                "Kaydedilmemiş değişiklikler var.\nÇıkmak istiyor musunuz?",
                parent=self,
            ):
                return
        self.destroy()
