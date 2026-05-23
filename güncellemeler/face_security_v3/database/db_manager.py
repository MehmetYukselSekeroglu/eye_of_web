"""
Veritabanı yönetimi — bilinen yüz kayıtlarını yönetir.
"""
import logging
from pathlib import Path

import cv2
import numpy as np

from utils.file_utils import sanitize_filename, safe_save_path

logger = logging.getLogger(__name__)

SUPPORTED_EXT = {".jpg", ".jpeg", ".png"}


class DatabaseManager:
    def __init__(self, db_path: str, face_processor, embedding_cache):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.face_processor = face_processor
        self.cache = embedding_cache

    # ── Yükleme ──────────────────────────────────────────────────────────────

    def reload(self) -> int:
        """
        Embedding önbelleğini yeniden derler ve FaceProcessor'a yükler.
        Tanınan kişi sayısını döner.
        """
        embeddings = self.cache.build()
        self.face_processor.load_embeddings(embeddings)
        return len(embeddings)

    # ── Kayıt ────────────────────────────────────────────────────────────────

    def save_person(self, name: str, crop: np.ndarray) -> tuple[bool, str]:
        """
        Bilinmeyen kişi görüntüsünü veritabanına kaydeder.
        Güvenli dosya adı üretir; path traversal'a karşı doğrular.
        Döner: (success, safe_name)
        """
        safe_name = sanitize_filename(name)
        if not safe_name:
            return False, ""

        try:
            target = safe_save_path(self.db_path, f"{safe_name}.jpg")
        except ValueError as e:
            logger.warning("Güvensiz yol engellendi: %s", e)
            return False, ""

        ok = cv2.imwrite(str(target), crop)
        if ok:
            # Önbelleği geçersiz kıl, sadece yeni dosya işlensin
            self.cache.invalidate()
            self.reload()
            logger.info("Yeni kişi kaydedildi: %s", safe_name)
        return ok, safe_name

    # ── Listeleme ────────────────────────────────────────────────────────────

    def list_people(self) -> list[str]:
        """Veritabanındaki benzersiz kişi adlarını döner."""
        names = set()
        for f in self.db_path.iterdir():
            if f.suffix.lower() in SUPPORTED_EXT:
                stem = f.stem.lower()
                base = stem.rsplit("_", 1)[0] if stem[-1:].isdigit() else stem
                names.add(base)
        return sorted(names)

    def person_exists(self, name: str) -> bool:
        return name.lower() in self.face_processor.known_faces
