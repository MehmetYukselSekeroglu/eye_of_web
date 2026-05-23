"""
Ana güvenlik paneli arayüzü (Tkinter).
Tüm iş mantığı ayrı modüllerde; bu dosya yalnızca UI'dan sorumludur.

Yapı:
  - ttk.Notebook → Tab 1: YÜZ TANIMA (toggle ile aktif/pasif)
                 → Tab 2: PLAKA TANIMA (PlateTab)

Başlangıç durumu: Her iki sekme KAPALI — kamera stream'i ve analiz thread'i yok.
"""
import json
import logging
import os
import platform
import queue
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from tkinter import *
from tkinter import messagebox, ttk

import cv2
from PIL import Image, ImageTk

import config
from auth.auth_manager import AuthManager
from camera.camera_manager import CameraManager
from camera.stream_handler import DetectionResult
from database.db_manager import DatabaseManager
from detection.log_throttle import LogThrottle
from notifications.telegram_bot import TelegramBot
from ui.plate_tab import PlateTab
from ui.settings_tab import SettingsTab

logger = logging.getLogger(__name__)


class SecurityPanelApp:
    """
    Face Security v3 — Ana Uygulama Sınıfı.
    Başlangıçta tüm kameralar kapalıdır; toggle butonlarıyla aktif edilir.
    """

    def __init__(
        self,
        root: Tk,
        auth: AuthManager,
        cam_manager: CameraManager,
        db_manager: DatabaseManager,
        telegram: TelegramBot | None,
        result_queue: queue.Queue,
        img_queue: queue.Queue,
    ):
        self.root = root
        self.auth = auth
        self.cam_manager = cam_manager
        self.db = db_manager
        self.telegram = telegram
        self.result_queue = result_queue
        self.img_queue = img_queue

        self.throttle = LogThrottle(cooldown_seconds=config.LOG_THROTTLE_SECONDS)

        # UI state
        self._cam_buttons: dict[int, Button] = {}
        self._cam_vars: dict[int, BooleanVar] = {}
        self._startup_vars: dict[int, BooleanVar] = {}
        self._last_unknown_crop: object = None

        self._scanning_active = False
        self._search_target: str | None = None

        # Yüz tanıma aktif/pasif durumu
        self._face_active = False

        self._log_file = Path(config.LOG_DIR) / f"detection_log_{datetime.now().strftime('%Y-%m-%d')}.txt"

        self._plate_tab: PlateTab | None = None
        self._plate_notify_throttle: float = 0.0
        self._plate_history: list = []

        self._build_ui()

        # Plaka callback'lerini _build_ui'den sonra kur (_plate_tab artık hazır)
        if self._plate_tab is not None:
            self._plate_tab.set_notification_callback(self._on_plate_event)
            self._plate_tab.set_toggle_callback(self._on_plate_toggled)

        self._load_cam_settings()
        self._setup_telegram_commands()

        # Kamera geçişi UI geri bildirimi
        self.cam_manager.on_camera_switch = self._on_cam_switch

        self.root.after(100, self._process_results)
        self.root.after(10, self._update_video)

    # ═════════════════════════════════════════════════════════════════════════
    # UI İNŞAAT
    # ═════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        self.root.title("AI SECURITY STATION v3.0")
        self.root.geometry("1650x970")
        self.root.configure(bg="#0d1117")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── ttk Notebook stili ────────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TNotebook",
            background="#0d1117",
            borderwidth=0,
            tabmargins=[0, 0, 0, 0],
        )
        style.configure(
            "TNotebook.Tab",
            background="#1a2a1a",
            foreground="#00aa28",
            font=("Consolas", 11, "bold"),
            padding=[18, 7],
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#0d2b0d"), ("active", "#1f3f1f")],
            foreground=[("selected", "#00ff41"), ("active", "#00dd35")],
        )

        # ── Notebook ──────────────────────────────────────────────────────
        self._notebook = ttk.Notebook(self.root)
        self._notebook.pack(fill=BOTH, expand=True)

        # ── Tab 1: Yüz Tanıma ─────────────────────────────────────────────
        self._face_frame = Frame(self._notebook, bg="#121212")
        self._notebook.add(self._face_frame, text="  ◈  YÜZ TANIMA  ")

        self._build_face_toggle()
        self._build_video_panel()
        self._build_log_box()
        self._build_folder_buttons()
        self._build_face_panels()
        self._build_patrol_buttons()
        self._build_camera_list()

        # ── Tab 2: Plaka Tanıma ───────────────────────────────────────────
        self._plate_frame = Frame(self._notebook, bg="#0d1117")
        self._notebook.add(self._plate_frame, text="  ◈  PLAKA TANIMA  ")
        self._plate_tab = PlateTab(self._plate_frame, self.root)

        # ── Tab 3: Kamera Ayarları ────────────────────────────────────────
        self._settings_frame = Frame(self._notebook, bg="#0d1117")
        self._notebook.add(self._settings_frame, text="  ◈  KAMERA AYARLARI  ")
        self._settings_tab = SettingsTab(
            self._settings_frame, on_urls_saved=self._on_cam_urls_saved,
        )

    # ── Yüz tanıma toggle butonu ──────────────────────────────────────────

    def _build_face_toggle(self) -> None:
        """Sekmenin en üstünde büyük aktif/pasif toggle butonu."""
        self._face_toggle_btn = Button(
            self._face_frame,
            text="  ▶  YÜZ TANIMAYI AKTİF ET  ",
            bg="#44ff44", fg="#000000",
            font=("Consolas", 13, "bold"),
            cursor="hand2",
            activebackground="#66ff66",
            activeforeground="#000",
            relief="raised", bd=2,
            command=self._toggle_face_system,
        )
        self._face_toggle_btn.place(x=20, y=5, width=1600, height=46)

    def _build_video_panel(self) -> None:
        # y=62 (toggle 5+46=51 → +11 boşluk = 62)
        self._camera_label = Label(self._face_frame, bg="black")
        self._camera_label.place(x=20, y=62, width=config.DISPLAY_W, height=config.DISPLAY_H)

        # "Sistem Pasif" overlay — başlangıçta üstte
        self._face_overlay = Label(
            self._face_frame,
            text="⬡  Sistem Pasif\nAktif etmek için butona basın",
            bg="#0d1117", fg="#444444",
            font=("Consolas", 15), justify=CENTER,
        )
        self._face_overlay.place(x=20, y=62, width=config.DISPLAY_W, height=config.DISPLAY_H)
        self._face_overlay.lift()

    def _build_log_box(self) -> None:
        self._log_box = Text(self._face_frame, bg="#000", fg="white", font=("Consolas", 10))
        self._log_box.place(x=940, y=62, width=400, height=300)
        for color, fg in [
            ("green",  "#00ff00"),
            ("red",    "#ff3333"),
            ("blue",   "#3399ff"),
            ("orange", "#ffcc00"),
            ("white",  "white"),
        ]:
            self._log_box.tag_config(f"color_{color}", foreground=fg)

    def _build_folder_buttons(self) -> None:
        for label, path, bg, x in [
            ("📂 KNOWN",   config.KNOWN_PATH,   "#27ae60", 940),
            ("📂 UNKNOWN", config.UNKNOWN_PATH,  "#c0392b", 1075),
            ("📂 LOGS",    config.LOG_DIR,       "#34495e", 1210),
        ]:
            Button(
                self._face_frame, text=label, bg=bg, fg="white",
                font=("Arial", 10, "bold"),
                command=lambda p=path: self._open_folder(p),
            ).place(x=x, y=372, width=130, height=40)

    def _build_face_panels(self) -> None:
        # +42 shift from original (530 → 572, 555 → 597, 810 → 852)
        y_label, y_panel, y_ctrl = 572, 597, 852

        # Tanınan
        Label(self._face_frame, text="SON TANINAN", bg="#121212", fg="#27ae60",
              font=("Arial", 10, "bold")).place(x=20, y=y_label)
        self._known_panel = Label(self._face_frame, bg="#222")
        self._known_panel.place(x=20, y=y_panel, width=200, height=250)
        self._known_name_label = Label(self._face_frame, text="İSİM: ---",
                                       bg="#121212", fg="white")
        self._known_name_label.place(x=20, y=y_ctrl)

        # Bilinmeyen
        Label(self._face_frame, text="YABANCI ŞAHIS", bg="#121212", fg="#c0392b",
              font=("Arial", 10, "bold")).place(x=240, y=y_label)
        self._unknown_panel = Label(self._face_frame, bg="#222")
        self._unknown_panel.place(x=240, y=y_panel, width=200, height=250)
        self._name_entry = Entry(self._face_frame, bg="#333", fg="white",
                                 font=("Arial", 11))
        self._name_entry.place(x=240, y=y_ctrl, width=200, height=30)
        Button(self._face_frame, text="SİSTEME KAYDET", bg="#2980b9", fg="white",
               command=self._save_unknown).place(x=240, y=887, width=200, height=30)

        # Manuel arama
        Label(self._face_frame, text="MANUEL ARAMA", bg="#121212", fg="#f1c40f",
              font=("Arial", 10, "bold")).place(x=460, y=y_label)
        self._search_ref_panel = Label(self._face_frame, bg="#222")
        self._search_ref_panel.place(x=460, y=y_panel, width=200, height=250)
        self._search_entry = Entry(self._face_frame, bg="#333", fg="white",
                                   font=("Arial", 11))
        self._search_entry.place(x=460, y=y_ctrl, width=200, height=30)
        Button(self._face_frame, text="İSİM ARA / TARA", bg="#e67e22", fg="white",
               command=self._start_search).place(x=460, y=887, width=200, height=30)
        Button(self._face_frame, text="TARAMAYI DURDUR", bg="#c0392b", fg="white",
               font=("Arial", 9, "bold"),
               command=self._stop_all).place(x=460, y=922, width=200, height=30)

        # Tespit edilen
        Label(self._face_frame, text="TESPİT EDİLEN", bg="#121212", fg="#3498db",
              font=("Arial", 10, "bold")).place(x=680, y=y_label)
        self._found_panel = Label(self._face_frame, bg="#222")
        self._found_panel.place(x=680, y=y_panel, width=200, height=250)
        self._found_label = Label(
            self._face_frame, text="DURUM: BEKLENİYOR", bg="#121212", fg="#3498db",
            font=("Arial", 9, "bold"), justify=CENTER,
        )
        self._found_label.place(x=680, y=y_ctrl, width=200, height=40)

    def _build_patrol_buttons(self) -> None:
        Label(self._face_frame, text="OTOMATİK DEVRİYE", bg="#121212", fg="#9b59b6",
              font=("Arial", 10, "bold")).place(x=900, y=572)
        Button(self._face_frame, text="DEVRİYE BAŞLAT", bg="#8e44ad", fg="white",
               font=("Arial", 10, "bold"),
               command=self._start_patrol).place(x=900, y=597, width=200, height=40)
        Button(self._face_frame, text="DURDUR", bg="#c0392b", fg="white",
               font=("Arial", 9, "bold"),
               command=self._stop_all).place(x=900, y=647, width=200, height=30)

    def _build_camera_list(self) -> None:
        for i in range(1, 26):
            y = 47 + (i - 1) * 36

            var = BooleanVar(value=True)
            var.trace_add("write", lambda *_: self._save_cam_settings())
            self._cam_vars[i] = var

            Checkbutton(
                self._face_frame, variable=var, bg="#121212", selectcolor="#27ae60",
                activebackground="#121212", borderwidth=0, highlightthickness=0,
            ).place(x=1345, y=y + 5)

            btn = Button(
                self._face_frame, text=config.CAMERA_NAMES[i], bg="#2c3e50", fg="white",
                font=("Arial", 8, "bold"), anchor="w", padx=10,
                command=lambda c=i: self._switch_cam(c),
            )
            btn.place(x=1370, y=y, width=200, height=32)
            self._cam_buttons[i] = btn

            s_var = BooleanVar(value=False)
            self._startup_vars[i] = s_var
            Checkbutton(
                self._face_frame, variable=s_var, bg="#121212", selectcolor="#e67e22",
                activebackground="#121212", borderwidth=0, highlightthickness=0,
                command=lambda c=i: self._set_startup_cam(c),
            ).place(x=1575, y=y + 5)

    # ═════════════════════════════════════════════════════════════════════════
    # YÜZ TANIMA TOGGLE
    # ═════════════════════════════════════════════════════════════════════════

    def _toggle_face_system(self) -> None:
        """Yüz tanıma sistemini aktif/pasif yap."""
        ts = datetime.now().strftime("%H:%M:%S")
        if self._face_active:
            # → Pasif
            self._face_active = False
            self._stop_all()
            self._face_toggle_btn.config(
                text="  ▶  YÜZ TANIMAYI AKTİF ET  ",
                bg="#44ff44", fg="#000000",
                activebackground="#66ff66",
            )
            self._face_overlay.lift()
            self._log(
                f"[{ts}] [SİSTEM] Yüz tanıma sistemi PASİF edildi.",
                "orange", save=True,
            )
        else:
            # → Aktif
            self._face_active = True
            self._face_toggle_btn.config(
                text="  ⏹  YÜZ TANIMAYI KAPAT  ",
                bg="#ff4444", fg="white",
                activebackground="#ff6666",
            )
            self._face_overlay.lower()
            self._log(
                f"[{ts}] [SİSTEM] Yüz tanıma sistemi AKTİF edildi.",
                "green", save=True,
            )
            self._start_default_camera()

    def _start_default_camera(self) -> None:
        """Kayıtlı başlangıç kamerasını veya ilk aktif kamerayı başlatır."""
        startup_id = None
        try:
            data = json.loads(Path("startup_config.json").read_text(encoding="utf-8"))
            startup_id = data.get("startup_id")
        except Exception:
            pass

        if startup_id and startup_id in config.CAMERAS:
            self._switch_cam(startup_id)
            return
        for i in range(1, 26):
            if self._cam_vars.get(i) and self._cam_vars[i].get() and i in config.CAMERAS:
                self._switch_cam(i)
                break

    # ═════════════════════════════════════════════════════════════════════════
    # KAMERA KONTROLÜ
    # ═════════════════════════════════════════════════════════════════════════

    def _switch_cam(self, cam_id: int, log: bool = True) -> None:
        self.cam_manager.selected_cams = {
            c for c, v in self._cam_vars.items() if v.get()
        }
        self.cam_manager.switch(cam_id, log=log)

    def _on_cam_switch(self, cam_id: int) -> None:
        for cid, btn in self._cam_buttons.items():
            btn.config(bg="#27ae60" if cid == cam_id else "#2c3e50")

    def _start_patrol(self) -> None:
        if not self._face_active:
            self._log("⚠️ Sistem pasif — önce yüz tanımayı aktif edin.", "orange")
            return
        self.cam_manager.selected_cams = {
            c for c, v in self._cam_vars.items() if v.get()
        }
        ok = self.cam_manager.start_patrol()
        if ok:
            self._log("🚀 DEVRİYE BAŞLATILDI", "orange", save=True)
        else:
            self._log("⚠️ Devriye başlatılamadı — seçili kamera yok.", "red")

    def _stop_all(self) -> None:
        self._scanning_active = False
        self._search_target = None
        self.cam_manager.stop()
        self._log("🛑 Tüm taramalar durduruldu.", "orange")
        try:
            self._found_label.config(text="TARAMA DURDU", fg="#c0392b")
        except Exception:
            pass

    def _start_search(self) -> None:
        if not self._face_active:
            self._log("⚠️ Sistem pasif — önce yüz tanımayı aktif edin.", "orange")
            return
        target = self._search_entry.get().strip().lower()
        if not target:
            self._log("⚠️ Aranacak isim girilmedi!", "red")
            return
        if not self.db.person_exists(target):
            self._log(f"⚠️ {target.upper()} veritabanında yok!", "red")
            return

        self._search_target = target
        self._scanning_active = True
        self._load_search_ref(target)
        self._log(f"🔍 ARA: {target.upper()} başlatıldı.", "orange", save=True)

        self.cam_manager.selected_cams = {
            c for c, v in self._cam_vars.items() if v.get()
        }
        self.cam_manager.start_patrol()

    def _load_search_ref(self, name: str) -> None:
        for ext in (".jpg", ".png", ".jpeg"):
            p = Path(config.DATABASE_PATH) / f"{name}{ext}"
            if p.exists():
                img = cv2.imread(str(p))
                if img is not None:
                    ref = cv2.resize(img, (200, 250))
                    tk_img = ImageTk.PhotoImage(
                        Image.fromarray(cv2.cvtColor(ref, cv2.COLOR_BGR2RGB))
                    )
                    self._search_ref_panel.configure(image=tk_img)
                    self._search_ref_panel.image = tk_img
                    return

    # ═════════════════════════════════════════════════════════════════════════
    # SONUÇ İŞLEME (ana döngü)
    # ═════════════════════════════════════════════════════════════════════════

    def _process_results(self) -> None:
        try:
            while True:
                result: DetectionResult = self.result_queue.get_nowait()
                self._handle_detection(result)
        except queue.Empty:
            pass
        self.root.after(50, self._process_results)

    def _handle_detection(self, r: DetectionResult) -> None:
        name = r.name
        who = name.upper() if name != "unknown" else "BİLİNMEYEN ŞAHIS"

        if self.throttle.should_log(name):
            color = "green" if name != "unknown" else "red"
            self._log(f"👤 TESPİT: {who} ({r.cam_name})", color, save=True)

        preview = cv2.resize(r.crop, (200, 250))

        if name == "unknown":
            self._last_unknown_crop = r.crop
            self._update_panel(self._unknown_panel, preview)
        else:
            self._update_panel(self._known_panel, preview)
            self._known_name_label.config(text=f"İSİM: {name.upper()}")

            if self._scanning_active and name == self._search_target:
                found_text = f"HEDEF BULUNDU\n{name.upper()}\n{r.cam_name}"
                self._update_panel(self._found_panel, preview)
                self._found_label.config(text=found_text, fg="#27ae60")
                if self.telegram:
                    snap_path = getattr(r, "snap_path", None)
                    if snap_path:
                        self.telegram.send_photo(
                            snap_path,
                            f"🔍 HEDEF BULUNDU: {name.upper()}\n📹 {r.cam_name}",
                        )

        # Telegram uyarısı (unknown için)
        if name == "unknown" and self.telegram:
            snap_path = getattr(r, "snap_path", None)
            if snap_path and self.throttle.should_log("unknown_tg"):
                self.telegram.send_photo(snap_path, f"❓ BİLİNMEYEN ŞAHIS\n📹 {r.cam_name}")

    # ═════════════════════════════════════════════════════════════════════════
    # VİDEO GÜNCELLEMESI
    # ═════════════════════════════════════════════════════════════════════════

    def _update_video(self) -> None:
        try:
            latest = None
            while not self.img_queue.empty():
                latest = self.img_queue.get_nowait()
            if latest is not None:
                tk_img = ImageTk.PhotoImage(
                    Image.fromarray(cv2.cvtColor(latest, cv2.COLOR_BGR2RGB))
                )
                self._camera_label.configure(image=tk_img)
                self._camera_label.image = tk_img
        except Exception:
            pass
        self.root.after(10, self._update_video)

    # ═════════════════════════════════════════════════════════════════════════
    # KAYIT
    # ═════════════════════════════════════════════════════════════════════════

    def _save_unknown(self) -> None:
        name = self._name_entry.get().strip()
        if not name:
            messagebox.showwarning("Uyarı", "İsim girilmedi.")
            return
        if self._last_unknown_crop is None:
            messagebox.showwarning("Uyarı", "Kaydedilecek bilinmeyen yüz bulunmuyor.")
            return

        ok, safe_name = self.db.save_person(name, self._last_unknown_crop)
        if ok:
            self._log(f"💾 Yeni Kayıt: {safe_name.upper()}", "blue", save=True)
            self.throttle.reset(safe_name)
            messagebox.showinfo("Başarılı", f"{safe_name.upper()} sisteme kaydedildi.")
        else:
            messagebox.showerror("Hata", "Kayıt yapılamadı. İsimde geçersiz karakter olabilir.")

    # ═════════════════════════════════════════════════════════════════════════
    # AYARLAR
    # ═════════════════════════════════════════════════════════════════════════

    def _load_cam_settings(self) -> None:
        cfg_file     = Path(config.CONFIG_FILE if hasattr(config, "CONFIG_FILE") else "camera_config.json")
        startup_file = Path(config.STARTUP_CONFIG if hasattr(config, "STARTUP_CONFIG") else "startup_config.json")

        saved: dict = {}
        if cfg_file.exists():
            try:
                saved = json.loads(cfg_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        startup_id: int | None = None
        if startup_file.exists():
            try:
                startup_id = json.loads(startup_file.read_text(encoding="utf-8")).get("startup_id")
            except Exception:
                pass

        for i in range(1, 26):
            val = saved.get(str(i), True)
            self._cam_vars[i].set(bool(val))
            if startup_id == i:
                self._startup_vars[i].set(True)

    def _save_cam_settings(self) -> None:
        settings = {str(k): bool(v.get()) for k, v in self._cam_vars.items()}
        try:
            Path("camera_config.json").write_text(
                json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass

    def _on_cam_urls_saved(self, changed: dict[int, str]) -> None:
        """
        SettingsTab .env'i güncelledikten sonra çağrılır.
        Aktif kamera URL'si değiştiyse o akışı yeniden başlat.
        """
        ts = datetime.now().strftime("%H:%M:%S")
        self._log(
            f"[{ts}] [AYAR] {len(changed)} kamera URL'si güncellendi.",
            "blue", save=True,
        )
        active = self.cam_manager.active_cam_id
        if active in changed and self._face_active:
            self.cam_manager.active_cam_id = None  # switch idempotent kontrolünü atla
            self._switch_cam(active)
            self._log(
                f"[{ts}] [AYAR] {config.CAMERA_NAMES.get(active, active)} yeniden bağlandı.",
                "orange",
            )

    def _set_startup_cam(self, selected_id: int) -> None:
        for cid, v in self._startup_vars.items():
            if cid != selected_id:
                v.set(False)
        try:
            val = selected_id if self._startup_vars[selected_id].get() else None
            Path("startup_config.json").write_text(
                json.dumps({"startup_id": val}, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    # ═════════════════════════════════════════════════════════════════════════
    # YARDIMCILAR
    # ═════════════════════════════════════════════════════════════════════════

    def _log(self, msg: str, color: str = "white", save: bool = False) -> None:
        t = datetime.now().strftime("%H:%M:%S")
        line = f"[{t}] {msg}\n"
        try:
            self._log_box.insert(END, line, f"color_{color}")
            self._log_box.see(END)
        except Exception:
            pass
        if save:
            try:
                with self._log_file.open("a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
            except Exception:
                pass

    def thread_log(self, msg: str, color: str = "white", save: bool = False) -> None:
        self.root.after(0, lambda m=msg, c=color, s=save: self._log(m, c, s))

    @staticmethod
    def _update_panel(panel: Label, cv_img) -> None:
        try:
            tk_img = ImageTk.PhotoImage(
                Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
            )
            panel.configure(image=tk_img)
            panel.image = tk_img
        except Exception:
            pass

    @staticmethod
    def _open_folder(path: str) -> None:
        abs_path = os.path.abspath(path)
        try:
            if platform.system() == "Windows":
                os.startfile(abs_path)
            else:
                subprocess.Popen(["xdg-open", abs_path])
        except Exception as e:
            logger.error("Klasör açılamadı: %s", e)

    def _on_plate_event(self, plate: str, frame) -> None:
        """Plaka onaylandığında GUI thread'den çağrılır. 30s mükerrer önleme."""
        now = datetime.now().timestamp()
        if now - self._plate_notify_throttle < 30.0:
            return
        self._plate_notify_throttle = now

        ts = datetime.now().strftime("%H:%M:%S")
        self._plate_history.append({"plate": plate, "time": ts})
        if len(self._plate_history) > 10:
            self._plate_history.pop(0)

        if self.telegram:
            caption = f"🚗 PLAKA TESPİT\n🔢 {plate}\n🕐 {ts}"
            if frame is not None:
                self.telegram.send_photo_cv2(frame, caption)
            else:
                self.telegram.send_message(caption)

    def _on_plate_toggled(self, active: bool) -> None:
        """Plaka sistemi açılıp kapandığında Telegram bildirimi gönderir."""
        if self.telegram:
            state = "AKTİF ✅" if active else "PASİF ⛔"
            self.telegram.send_message(f"🚗 Plaka tanıma sistemi {state}")

    def _on_close(self) -> None:
        if self._plate_tab is not None:
            self._plate_tab.stop()
        self.cam_manager.stop()
        self.root.destroy()

    # ═════════════════════════════════════════════════════════════════════════
    # TELEGRAM KOMUTLARI
    # ═════════════════════════════════════════════════════════════════════════

    def _setup_telegram_commands(self) -> None:
        if not self.telegram:
            return

        def _status(_args: str) -> None:
            cam_name = config.CAMERA_NAMES.get(self.cam_manager.active_cam_id, "Kapalı")
            face_state = "AKTİF" if self._face_active else "PASİF"
            plate_state = "AKTİF" if (self._plate_tab and self._plate_tab._active) else "PASİF"
            text = (
                "🛡️ SİSTEM DURUMU\n"
                f"Yüz Tanıma: {face_state}\n"
                f"Plaka Tanıma: {plate_state}\n"
                f"Mod: {'Devriye' if self.cam_manager._patrol_active else 'Sabit'}\n"
                f"Aktif Kamera: {cam_name}\n"
                f"Aranan Hedef: {self._search_target.upper() if self._search_target else '-'}\n"
                f"Veritabanı: {len(self.db.db_manager.face_processor.known_faces)} kişi"
            )
            self.telegram.send_message(text)

        def _photo(_args: str) -> None:
            with self.cam_manager.stream.frame_lock:
                frame = self.cam_manager.stream.last_frame_raw
                if frame is not None:
                    frame = frame.copy()
            if frame is None:
                self.telegram.send_message("❌ Kamera görüntüsü alınamıyor.")
                return
            tmp = Path(config.LOG_DIR) / "tel_snap.jpg"
            cv2.imwrite(str(tmp), frame)
            cam_name = config.CAMERA_NAMES.get(self.cam_manager.active_cam_id, "Kapalı")
            self.telegram.send_photo(tmp, f"📸 Manuel İstek\n📹 {cam_name}")

        def _switch_cam(args: str) -> None:
            try:
                cid = int(args.strip())
                self.root.after(0, lambda: self._switch_cam(cid))
                self.telegram.send_message(f"📹 Kamera: {config.CAMERA_NAMES.get(cid, cid)}")
            except ValueError:
                self.telegram.send_message("❌ Kullanım: /kamera 5")

        def _patrol_start(_args: str) -> None:
            self.root.after(0, self._start_patrol)
            self.telegram.send_message("🚀 Devriye başlatılıyor.")

        def _patrol_stop(_args: str) -> None:
            self.root.after(0, self._stop_all)
            self.telegram.send_message("🛑 Taramalar durduruldu.")

        def _search(args: str) -> None:
            target = args.strip().lower()
            if not target:
                self.telegram.send_message("❌ Kullanım: /tara isim")
                return
            if not self.db.person_exists(target):
                self.telegram.send_message(f"❌ {target.upper()} veritabanında yok.")
                return
            self._search_target = target
            self._scanning_active = True
            self.root.after(0, lambda: self._load_search_ref(target))
            self.root.after(0, self._start_patrol)
            self.telegram.send_message(f"🔍 {target.upper()} için tarama başlatıldı.")

        def _reload_db(_args: str) -> None:
            count = self.db.reload()
            self.telegram.send_message(f"🔄 Veritabanı yenilendi. Kişi sayısı: {count}")

        def _plate_on(_args: str) -> None:
            if self._plate_tab is None:
                self.telegram.send_message("❌ Plaka sekmesi yüklenemedi.")
                return
            if self._plate_tab._active:
                self.telegram.send_message("ℹ️ Plaka tanıma zaten aktif.")
                return
            self._plate_tab.enqueue_command("activate")
            self.telegram.send_message("🚗 Plaka tanıma aktifleştiriliyor...")

        def _plate_off(_args: str) -> None:
            if self._plate_tab is None:
                self.telegram.send_message("❌ Plaka sekmesi yüklenemedi.")
                return
            if not self._plate_tab._active:
                self.telegram.send_message("ℹ️ Plaka tanıma zaten pasif.")
                return
            self._plate_tab.enqueue_command("deactivate")
            self.telegram.send_message("🛑 Plaka tanıma durduruluyor...")

        def _son_plakalar(_args: str) -> None:
            if not self._plate_history:
                self.telegram.send_message("📋 Henüz plaka tespit edilmedi.")
                return
            lines = ["🚗 SON TESPİT EDİLEN PLAKALAR"]
            for entry in reversed(self._plate_history[-10:]):
                lines.append(f"🔢 {entry['plate']}  🕐 {entry['time']}")
            self.telegram.send_message("\n".join(lines))

        def _help(_args: str) -> None:
            self.telegram.send_message(
                "🤖 TELEGRAM KOMUTLARI\n"
                "/yardim — Bu listeyi göster\n"
                "/durum — Sistem durumu (yüz + plaka)\n"
                "/foto — Anlık görüntü\n"
                "/kameralar — Kamera listesi\n"
                "/kamera 5 — Kamera geç\n"
                "/devriye_baslat — Devriye başlat\n"
                "/devriye_durdur — Devriyeyi durdur\n"
                "/tara isim — Kişi ara\n"
                "/ara_durdur — Aramayı durdur\n"
                "/yeniledb — Veritabanını yenile\n"
                "/plaka_ac — Plaka tanımayı başlat\n"
                "/plaka_kapat — Plaka tanımayı durdur\n"
                "/son_plakalar — Son tespit edilen plakalar"
            )

        def _cam_list(_args: str) -> None:
            lines = ["📹 KAMERA LİSTESİ"]
            for cid in sorted(config.CAMERA_NAMES):
                mark = "✅" if self._cam_vars.get(cid) and self._cam_vars[cid].get() else "⬜"
                active = " 🔴AKTİF" if cid == self.cam_manager.active_cam_id else ""
                lines.append(f"{mark} {cid} — {config.CAMERA_NAMES[cid]}{active}")
            self.telegram.send_message("\n".join(lines))

        self.telegram.register("/start",           lambda _: self.telegram.send_message("✅ Bot aktif. /yardim"))
        self.telegram.register("/yardim",          _help)
        self.telegram.register("/durum",           _status)
        self.telegram.register("/foto",            _photo)
        self.telegram.register("/kameralar",       _cam_list)
        self.telegram.register("/kamera",          _switch_cam)
        self.telegram.register("/devriye_baslat",  _patrol_start)
        self.telegram.register("/devriye_durdur",  _patrol_stop)
        self.telegram.register("/tara",            _search)
        self.telegram.register("/ara_durdur",      _patrol_stop)
        self.telegram.register("/yeniledb",        _reload_db)
        self.telegram.register("/plaka_ac",        _plate_on)
        self.telegram.register("/plaka_kapat",     _plate_off)
        self.telegram.register("/son_plakalar",    _son_plakalar)

    # ═════════════════════════════════════════════════════════════════════════
    # OTO BAŞLANGIÇ — devre dışı (toggle butonu kullanılır)
    # ═════════════════════════════════════════════════════════════════════════

    def auto_start(self) -> None:
        """
        Başlangıçta kamera otomatik açılmaz.
        Kullanıcı 'YÜZ TANIMAYI AKTİF ET' butonuna basmalıdır.
        """
        ts = datetime.now().strftime("%H:%M:%S")
        self._log(
            f"[{ts}] [SİSTEM] Sistem hazır. Başlatmak için toggle butonuna basın.",
            "blue",
        )
