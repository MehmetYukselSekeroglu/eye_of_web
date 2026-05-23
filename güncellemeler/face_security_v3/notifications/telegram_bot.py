"""
Telegram Bot — mesaj ve fotoğraf gönderimi + komut dinleyici.
Token ve chat_id ortam değişkenlerinden gelir; kaynak kodda değil.
"""
import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable

import requests

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, token: str, chat_id: str):
        if not token or not chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID .env dosyasında tanımlanmalı.")
        self.token = token
        self.chat_id = str(chat_id).strip()
        self._base = f"https://api.telegram.org/bot{self.token}"
        self._handlers: dict[str, Callable] = {}
        self._running = False

    # ── Komut kaydı ──────────────────────────────────────────────────────────

    def register(self, command: str, handler: Callable) -> None:
        """
        Telegram komutunu bir fonksiyona bağlar.
        handler(args: str) imzasında çağrılır.
        """
        self._handlers[command.lower()] = handler

    # ── Gönderim ─────────────────────────────────────────────────────────────

    def send_message(self, text: str) -> bool:
        try:
            r = requests.post(
                f"{self._base}/sendMessage",
                data={"chat_id": self.chat_id, "text": text},
                timeout=15,
            )
            data = r.json()
            if not data.get("ok"):
                logger.warning("sendMessage hatası: %s", data)
                return False
            return True
        except Exception as e:
            logger.error("send_message exception: %s", e)
            return False

    def send_photo(self, img_path: str | Path, caption: str = "") -> None:
        """Fotoğrafı arka plan thread'inde gönderir (bloke etmez)."""
        def _send():
            path = Path(img_path)
            if not path.exists():
                logger.warning("Foto yolu bulunamadı: %s", img_path)
                return
            try:
                with path.open("rb") as photo:
                    r = requests.post(
                        f"{self._base}/sendPhoto",
                        data={"chat_id": self.chat_id, "caption": caption},
                        files={"photo": photo},
                        timeout=20,
                    )
                data = r.json()
                if not data.get("ok"):
                    logger.warning("sendPhoto hatası: %s", data)
                else:
                    logger.info("Foto gönderildi.")
            except Exception as e:
                logger.error("send_photo exception: %s", e)

        threading.Thread(target=_send, daemon=True).start()

    def send_photo_cv2(self, frame, caption: str = "") -> None:
        """NumPy BGR frame'i Telegram'a gönderir (cv2.imencode, dosya yazmadan)."""
        import cv2 as _cv2

        def _send():
            try:
                ok, buf = _cv2.imencode(".jpg", frame)
                if not ok:
                    logger.warning("imencode başarısız.")
                    return
                r = requests.post(
                    f"{self._base}/sendPhoto",
                    data={"chat_id": self.chat_id, "caption": caption},
                    files={"photo": ("plate_snap.jpg", buf.tobytes(), "image/jpeg")},
                    timeout=20,
                )
                data = r.json()
                if not data.get("ok"):
                    logger.warning("sendPhoto (cv2) hatası: %s", data)
                else:
                    logger.info("Plaka fotoğrafı gönderildi.")
            except Exception as e:
                logger.error("send_photo_cv2 exception: %s", e)

        threading.Thread(target=_send, daemon=True).start()

    # ── Polling ──────────────────────────────────────────────────────────────

    def start_polling(self) -> None:
        """Telegram komutlarını dinleyen thread'i başlatır."""
        self._running = True
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()

    def stop(self) -> None:
        self._running = False

    def _poll_loop(self) -> None:
        logger.info("Telegram bot başlatılıyor...")
        try:
            r = requests.get(f"{self._base}/deleteWebhook", timeout=15)
            logger.debug("deleteWebhook: %s", r.json())
        except Exception as e:
            logger.warning("deleteWebhook hatası: %s", e)

        try:
            me = requests.get(f"{self._base}/getMe", timeout=15).json()
            if me.get("ok"):
                logger.info("Bot hazır: @%s", me["result"].get("username"))
            else:
                logger.error("Token hatalı: %s", me)
                return
        except Exception as e:
            logger.error("getMe hatası: %s", e)
            return

        last_update_id = 0

        while self._running:
            try:
                r = requests.get(
                    f"{self._base}/getUpdates",
                    params={"offset": last_update_id + 1, "timeout": 20},
                    timeout=30,
                )
                data = r.json()

                if not data.get("ok"):
                    logger.warning("getUpdates hatası: %s", data)
                    time.sleep(3)
                    continue

                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    msg = update.get("message")
                    if not msg:
                        continue

                    incoming_chat = str(msg.get("chat", {}).get("id", "")).strip()
                    from_user = msg.get("from", {}).get("username", "unknown")
                    text = msg.get("text", "").strip()

                    logger.debug("Mesaj | chat=%s user=%s text=%s", incoming_chat, from_user, text)

                    if incoming_chat != self.chat_id:
                        logger.warning("Yetkisiz chat_id: %s", incoming_chat)
                        continue

                    self._dispatch(text)

            except Exception as e:
                logger.error("Polling hatası: %s", e)

            time.sleep(1)

    def _dispatch(self, text: str) -> None:
        """Gelen komutu kayıtlı handler'a yönlendirir."""
        parts = text.strip().split(maxsplit=1)
        if not parts:
            return
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handler = self._handlers.get(command)
        if handler:
            try:
                handler(args)
            except Exception as e:
                logger.error("Handler hatası (%s): %s", command, e)
                self.send_message(f"❌ Komut işlenirken hata: {e}")
        else:
            logger.debug("Bilinmeyen komut: %s", command)
            self.send_message("❓ Bilinmeyen komut. /yardim yaz.")
