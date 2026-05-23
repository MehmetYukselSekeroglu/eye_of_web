"""
Kamera Ayarları Sekmesi — RTSP URL'lerini UI üzerinden düzenle.

Kullanıcı 25 kameranın RTSP URL'sini tek tek girer, [T] ile test eder,
[KAYDET] ile .env'e yazar. Aktif kamera URL'si değiştiyse otomatik
yeniden bağlanır.

Kaydetme:
  - .env atomik yazılır (önce .env.tmp → rename)
  - .env.bak yedeği oluşturulur
  - Yalnızca CAM_NN_URL satırları değiştirilir; diğer key'ler korunur
"""
import logging
import re
import threading
from pathlib import Path
from tkinter import (
    BOTH, BOTTOM, END, LEFT, RIGHT, VERTICAL, X, Y, Button, Canvas,
    Entry, Frame, Label, Scrollbar, StringVar, messagebox,
)
from typing import Callable

import cv2

import config

logger = logging.getLogger(__name__)

_ENV_PATH = Path(".env")
_ENV_BAK  = Path(".env.bak")
_ENV_TMP  = Path(".env.tmp")

_CAM_URL_RE = re.compile(r"^CAM_(\d{2})_URL=")


class SettingsTab(Frame):
    """
    Kamera RTSP URL düzenleme sekmesi.

    on_urls_saved: kaydetme başarılı olunca {cam_id: new_url} ile çağrılır.
    """

    BG       = "#0d1117"
    ROW_BG   = "#121212"
    ENTRY_BG = "#1a1a1a"
    ENTRY_FG = "white"
    LABEL_FG = "#00ff41"
    HINT_FG  = "#888"

    def __init__(
        self,
        parent: Frame,
        on_urls_saved: Callable[[dict[int, str]], None] | None = None,
    ) -> None:
        super().__init__(parent, bg=self.BG)
        self.pack(fill=BOTH, expand=True)

        self._on_urls_saved = on_urls_saved
        self._url_vars: dict[int, StringVar] = {}
        self._test_buttons: dict[int, Button] = {}

        self._build_ui()
        self._load_current_urls()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Başlık
        Label(
            self, text="◈  KAMERA RTSP URL AYARLARI",
            bg=self.BG, fg=self.LABEL_FG,
            font=("Consolas", 14, "bold"),
        ).pack(pady=(15, 5))

        Label(
            self,
            text="IP değiştiğinde RTSP URL'yi düzenleyip KAYDET'e basın. "
                 "[T] ile bağlantı testi yapabilirsiniz.",
            bg=self.BG, fg=self.HINT_FG,
            font=("Consolas", 10),
        ).pack(pady=(0, 10))

        # Alt aksiyon barı — önce paketle ki canvas tüm kalan alanı alsın
        action_bar = Frame(self, bg=self.BG)
        action_bar.pack(side=BOTTOM, fill=X, pady=10)

        Button(
            action_bar, text="  💾 KAYDET  ",
            bg="#3399ff", fg="white",
            font=("Consolas", 12, "bold"), cursor="hand2",
            command=self._on_save,
        ).pack(side=LEFT, padx=20)

        Button(
            action_bar, text="  ↺ GERİ AL  ",
            bg="#666", fg="white",
            font=("Consolas", 12, "bold"), cursor="hand2",
            command=self._on_reload,
        ).pack(side=LEFT, padx=5)

        self._status_var = StringVar(value="")
        Label(
            action_bar, textvariable=self._status_var,
            bg=self.BG, fg=self.HINT_FG,
            font=("Consolas", 10),
        ).pack(side=LEFT, padx=20)

        # Scrollable container — Canvas + inner Frame + Scrollbar
        outer = Frame(self, bg=self.BG)
        outer.pack(fill=BOTH, expand=True, padx=20)

        canvas = Canvas(outer, bg=self.BG, highlightthickness=0)
        scrollbar = Scrollbar(outer, orient=VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)

        inner = Frame(canvas, bg=self.BG)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        # Fare tekerleği ile scroll
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        # Linux: Button-4/5
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        # Sütun başlıkları
        header = Frame(inner, bg=self.BG)
        header.pack(fill=X, pady=(0, 5))
        Label(header, text="#",    bg=self.BG, fg=self.HINT_FG,
              font=("Consolas", 10, "bold"), width=3).pack(side=LEFT)
        Label(header, text="İsim", bg=self.BG, fg=self.HINT_FG,
              font=("Consolas", 10, "bold"), width=22, anchor="w").pack(side=LEFT, padx=5)
        Label(header, text="RTSP URL", bg=self.BG, fg=self.HINT_FG,
              font=("Consolas", 10, "bold"), anchor="w").pack(side=LEFT, padx=5)

        # 25 satır
        for cam_id in range(1, 26):
            self._build_row(inner, cam_id)

    def _build_row(self, parent: Frame, cam_id: int) -> None:
        row = Frame(parent, bg=self.ROW_BG)
        row.pack(fill=X, pady=1)

        Label(
            row, text=str(cam_id), bg=self.ROW_BG, fg=self.LABEL_FG,
            font=("Consolas", 10, "bold"), width=3,
        ).pack(side=LEFT, padx=(5, 0), pady=3)

        Label(
            row, text=config.CAMERA_NAMES.get(cam_id, f"Kamera {cam_id}"),
            bg=self.ROW_BG, fg="white",
            font=("Consolas", 10), width=22, anchor="w",
        ).pack(side=LEFT, padx=5)

        var = StringVar()
        self._url_vars[cam_id] = var

        entry = Entry(
            row, textvariable=var,
            bg=self.ENTRY_BG, fg=self.ENTRY_FG,
            font=("Consolas", 9), insertbackground="white",
            relief="flat",
        )
        entry.pack(side=LEFT, padx=5, fill=X, expand=True, pady=3)

        test_btn = Button(
            row, text="  T  ",
            bg="#ffcc00", fg="black",
            font=("Consolas", 9, "bold"), cursor="hand2",
            command=lambda c=cam_id: self._on_test(c),
        )
        test_btn.pack(side=LEFT, padx=(5, 10), pady=3)
        self._test_buttons[cam_id] = test_btn

    # ── Veri yükleme ─────────────────────────────────────────────────────────

    def _load_current_urls(self) -> None:
        """config.CAMERAS'tan mevcut URL'leri Entry'lere yaz."""
        for cam_id, var in self._url_vars.items():
            var.set(config.CAMERAS.get(cam_id, ""))
        # Test butonlarını sıfırla
        for btn in self._test_buttons.values():
            btn.config(text="  T  ", bg="#ffcc00", fg="black")
        self._status_var.set(".env'den yüklendi")

    def _on_reload(self) -> None:
        """.env'i yeniden okuyup mevcut değerleri tazele."""
        # config.CAMERAS modül yüklenirken oluşur; tekrar oku
        from dotenv import load_dotenv
        load_dotenv(override=True)
        for cam_id in range(1, 26):
            url = self._read_env_var(f"CAM_{cam_id:02d}_URL")
            if url is not None:
                config.CAMERAS[cam_id] = url
        self._load_current_urls()

    @staticmethod
    def _read_env_var(key: str) -> str | None:
        try:
            for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1]
        except Exception:
            return None
        return None

    # ── Test ─────────────────────────────────────────────────────────────────

    def _on_test(self, cam_id: int) -> None:
        url = self._url_vars[cam_id].get().strip()
        btn = self._test_buttons[cam_id]

        if not url:
            btn.config(text="  ✗  ", bg="#c0392b", fg="white")
            return

        btn.config(text=" .. ", bg="#666", fg="white")

        def probe():
            ok = False
            try:
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                try:
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000)
                    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000)
                except Exception:
                    pass
                if cap.isOpened():
                    ret, _ = cap.read()
                    ok = bool(ret)
                cap.release()
            except Exception as e:
                logger.warning("RTSP test hatası %d: %s", cam_id, e)
                ok = False
            self.after(0, lambda: btn.config(
                text="  ✓  " if ok else "  ✗  ",
                bg="#27ae60" if ok else "#c0392b",
                fg="white",
            ))

        threading.Thread(target=probe, daemon=True).start()

    # ── Kaydet ───────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        # Boş URL kabul edilmez (kameranın kullanılmayacağı varsayımına gitmiyoruz —
        # boş bırakmak yerine kullanıcı checkbox'tan kapatabilir)
        new_urls: dict[int, str] = {}
        for cam_id, var in self._url_vars.items():
            url = var.get().strip()
            new_urls[cam_id] = url

        # Sadece değişenleri bul
        changed = {
            cid: u for cid, u in new_urls.items()
            if u != config.CAMERAS.get(cid, "")
        }

        if not changed:
            self._status_var.set("Değişiklik yok.")
            return

        try:
            self._write_env(new_urls)
        except Exception as e:
            logger.exception("Ayar kaydı başarısız")
            messagebox.showerror("Hata", f".env kaydedilemedi:\n{e}", parent=self)
            return

        # Runtime CAMERAS güncellemesi
        for cam_id, url in new_urls.items():
            if url:
                config.CAMERAS[cam_id] = url
            else:
                config.CAMERAS.pop(cam_id, None)

        self._status_var.set(f"Kaydedildi: {len(changed)} kamera güncellendi.")

        if self._on_urls_saved:
            try:
                self._on_urls_saved(changed)
            except Exception:
                logger.exception("on_urls_saved callback hatası")

    @staticmethod
    def _write_env(new_urls: dict[int, str]) -> None:
        """
        .env'i atomik yaz. CAM_NN_URL satırlarını güncelle, diğerlerine dokunma.
        Hiç olmayan CAM_NN_URL varsa sona ekle.
        """
        if not _ENV_PATH.exists():
            raise FileNotFoundError(".env bulunamadı")

        original = _ENV_PATH.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)

        seen: set[int] = set()
        out_lines: list[str] = []
        for line in lines:
            m = _CAM_URL_RE.match(line)
            if m:
                cid = int(m.group(1))
                if cid in new_urls:
                    seen.add(cid)
                    # Satır sonu karakteri korunur
                    eol = "\n" if line.endswith("\n") else ""
                    out_lines.append(f"CAM_{cid:02d}_URL={new_urls[cid]}{eol}")
                    continue
            out_lines.append(line)

        # .env'de hiç olmayan CAM_NN_URL'leri (eğer içerik boş değilse) sona ekle
        missing = [cid for cid in sorted(new_urls) if cid not in seen and new_urls[cid]]
        if missing:
            if out_lines and not out_lines[-1].endswith("\n"):
                out_lines[-1] = out_lines[-1] + "\n"
            for cid in missing:
                out_lines.append(f"CAM_{cid:02d}_URL={new_urls[cid]}\n")

        # Backup
        _ENV_BAK.write_text(original, encoding="utf-8")

        # Atomik yazım
        _ENV_TMP.write_text("".join(out_lines), encoding="utf-8")
        _ENV_TMP.replace(_ENV_PATH)
