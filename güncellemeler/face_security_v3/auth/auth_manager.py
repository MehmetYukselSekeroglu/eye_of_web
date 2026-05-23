"""
Erişim denetimi — PIN tabanlı kimlik doğrulama.
PIN hash'i auth_config.json dosyasında saklanır (kaynak kodda değil).
"""
import hashlib
import json
import time
from pathlib import Path

import bcrypt
from tkinter import Tk, Toplevel, Label, Entry, Button, StringVar, messagebox


CONFIG_FILE = "auth_config.json"
DEFAULT_PIN = "1234"
AUTO_LOCK_MINUTES = 30


class AuthManager:
    def __init__(self, config_path: str = CONFIG_FILE):
        self.config_path = Path(config_path)
        self.is_authenticated: bool = False
        self._last_auth_time: float = 0.0
        self._config: dict = {}
        self._load_config()

    # ── Yapılandırma ─────────────────────────────────────────────────────────

    def _load_config(self) -> None:
        if self.config_path.exists():
            try:
                self._config = json.loads(self.config_path.read_text(encoding="utf-8"))
                return
            except Exception:
                pass
        # İlk kurulum: varsayılan PIN
        self._config = {
            "pin_hash": self._hash(DEFAULT_PIN),
            "auto_lock_minutes": AUTO_LOCK_MINUTES,
        }
        self._save_config()

    def _save_config(self) -> None:
        self.config_path.write_text(
            json.dumps(self._config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Yardımcılar ──────────────────────────────────────────────────────────

    @staticmethod
    def _hash(pin: str) -> str:
        """Yeni PIN hash'i üret. Bcrypt kullanır.

        Migration döneminde verify_pin legacy SHA256'yı da destekler ama
        yeni yazılan tüm hash'ler bcrypt'tir.
        """
        return bcrypt.hashpw(
            pin.encode("utf-8"),
            bcrypt.gensalt(rounds=12),
        ).decode("utf-8")

    @staticmethod
    def _legacy_sha256(pin: str) -> str:
        """Eski SHA256 hash — sadece migration doğrulaması için."""
        return hashlib.sha256(pin.encode("utf-8")).hexdigest()

    def _is_session_expired(self) -> bool:
        lock_after = self._config.get("auto_lock_minutes", AUTO_LOCK_MINUTES) * 60
        return (time.time() - self._last_auth_time) > lock_after

    # ── Doğrulama ────────────────────────────────────────────────────────────

    def verify_pin(self, pin: str) -> bool:
        """PIN doğrulama. Hem bcrypt (yeni) hem SHA256 (legacy) destekler.

        Migration döneminde geriye uyumluluk için her iki format da kabul
        edilir. Tüm kullanıcılar bcrypt'e geçtikten sonra legacy fallback
        kaldırılabilir.
        """
        if not pin:
            return False

        stored = self._config.get("pin_hash", "")
        if not stored:
            return False

        # Bcrypt formatı: $2a$, $2b$, $2y$ ile başlar
        if stored.startswith("$2"):
            try:
                ok = bcrypt.checkpw(
                    pin.encode("utf-8"),
                    stored.encode("utf-8"),
                )
            except (ValueError, TypeError):
                ok = False
        else:
            # Legacy: tuzsuz SHA256 (sadece migration süresince)
            ok = self._legacy_sha256(pin) == stored

        if ok:
            self.is_authenticated = True
            self._last_auth_time = time.time()
        return ok

    def check_session(self) -> bool:
        if self.is_authenticated and not self._is_session_expired():
            return True
        self.is_authenticated = False
        return False

    def change_pin(self, old_pin: str, new_pin: str) -> bool:
        if not self.verify_pin(old_pin):
            return False
        if len(new_pin) < 4:
            return False
        self._config["pin_hash"] = self._hash(new_pin)
        self._config["pin_hash_algo"] = "bcrypt"
        self._save_config()
        return True

    def logout(self) -> None:
        self.is_authenticated = False
        self._last_auth_time = 0.0

    # ── Tkinter Diyalog ──────────────────────────────────────────────────────

    def show_login_dialog(self, parent=None) -> bool:
        """
        Bağımsız bir Tk penceresi olarak PIN giriş ekranı göster.
        Doğru PIN girilirse True, iptal/hata durumunda False döner.
        parent parametresi geriye dönük uyumluluk için korundu (kullanılmıyor).
        """
        result: dict = {"success": False}

        win = Tk()
        win.title("Güvenlik Girişi")
        win.geometry("320x200")
        win.configure(bg="#121212")
        win.resizable(False, False)

        # Ekranın ortasına konumlandır
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = (sw - 320) // 2
        y = (sh - 200) // 2
        win.geometry(f"320x200+{x}+{y}")

        win.lift()
        win.attributes("-topmost", True)
        win.focus_force()

        Label(
            win,
            text="🔒 FACE SECURITY v3",
            bg="#121212",
            fg="white",
            font=("Arial", 13, "bold"),
        ).pack(pady=(20, 5))

        Label(
            win,
            text="PIN giriniz:",
            bg="#121212",
            fg="#aaa",
            font=("Arial", 10),
        ).pack()

        pin_var = StringVar()
        entry = Entry(
            win,
            textvariable=pin_var,
            show="●",
            bg="#333",
            fg="white",
            font=("Arial", 14),
            justify="center",
            width=12,
        )
        entry.pack(pady=8)
        entry.focus_set()

        error_label = Label(win, text="", bg="#121212", fg="#ff3333", font=("Arial", 9))
        error_label.pack()

        def _attempt():
            pin = pin_var.get().strip()
            if self.verify_pin(pin):
                result["success"] = True
                win.destroy()
            else:
                error_label.config(text="Hatalı PIN. Tekrar deneyin.")
                pin_var.set("")
                entry.focus_set()

        entry.bind("<Return>", lambda _e: _attempt())

        Button(
            win,
            text="GİRİŞ",
            bg="#27ae60",
            fg="white",
            font=("Arial", 10, "bold"),
            width=10,
            command=_attempt,
        ).pack(pady=6)

        win.mainloop()
        return result["success"]
