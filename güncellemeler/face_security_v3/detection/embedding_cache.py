"""
Yüz embedding önbelleği.
Veritabanı görüntülerinin MD5 hash'ini izler; değişmeyen dosyaları
yeniden işlemez. Önbellek pickle ile diske kaydedilir.
"""
import hashlib
import logging
import pickle
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

CACHE_FILE = "embeddings_cache.pkl"
SUPPORTED_EXT = {".jpg", ".jpeg", ".png"}


class EmbeddingCache:
    def __init__(self, db_path: str, face_app, cache_file: str = CACHE_FILE):
        self.db_path = Path(db_path)
        self.face_app = face_app
        self.cache_file = Path(cache_file)
        self._cache: dict = self._load_disk_cache()

    # ── Disk I/O ─────────────────────────────────────────────────────────────

    def _load_disk_cache(self) -> dict:
        if self.cache_file.exists():
            try:
                with self.cache_file.open("rb") as f:
                    data = pickle.load(f)
                logger.info("Embedding önbelleği yüklendi (%d kayıt)", len(data.get("embeddings", {})))
                return data
            except Exception as e:
                logger.warning("Önbellek okunamadı, sıfırlanıyor: %s", e)
        return {"file_hashes": {}, "embeddings": {}}

    def _save_disk_cache(self) -> None:
        try:
            with self.cache_file.open("wb") as f:
                pickle.dump(self._cache, f)
        except Exception as e:
            logger.error("Önbellek kaydedilemedi: %s", e)

    # ── Yardımcılar ──────────────────────────────────────────────────────────

    @staticmethod
    def _file_hash(path: Path) -> str:
        return hashlib.md5(path.read_bytes()).hexdigest()

    def _compute_embedding(self, img_path: Path) -> np.ndarray | None:
        """InsightFace ile tek görüntüden embedding hesaplar."""
        import cv2
        img = cv2.imread(str(img_path))
        if img is None:
            return None
        try:
            faces = self.face_app.get(img)
        except Exception as e:
            logger.debug("InsightFace hatası (%s): %s", img_path.name, e)
            return None
        if not faces:
            return None
        emb = faces[0].embedding
        norm = np.linalg.norm(emb)
        return (emb / norm) if norm > 0 else None

    # ── Ana API ──────────────────────────────────────────────────────────────

    def build(self) -> dict[str, np.ndarray]:
        """
        Veritabanındaki tüm görüntüleri tara.
        Değişen veya yeni dosyalar yeniden işlenir.
        Sonuç: {name: ortalama_embedding} sözlüğü.
        """
        updated = False
        raw: dict[str, list[np.ndarray]] = {}

        for img_path in self.db_path.iterdir():
            if img_path.suffix.lower() not in SUPPORTED_EXT:
                continue
            if not img_path.stat().st_size:
                continue

            current_hash = self._file_hash(img_path)
            cached_hash = self._cache["file_hashes"].get(str(img_path))

            if current_hash != cached_hash:
                emb = self._compute_embedding(img_path)
                if emb is not None:
                    self._cache["embeddings"][str(img_path)] = emb
                    self._cache["file_hashes"][str(img_path)] = current_hash
                    updated = True
                    logger.debug("İşlendi: %s", img_path.name)
                else:
                    logger.debug("Yüz bulunamadı: %s", img_path.name)
            # Silinen dosyaların önbellekten temizlenmesi
        stale_keys = [k for k in self._cache["embeddings"] if not Path(k).exists()]
        for k in stale_keys:
            del self._cache["embeddings"][k]
            self._cache["file_hashes"].pop(k, None)
            updated = True

        if updated:
            self._save_disk_cache()

        # İsim bazında ortalama embedding hesapla
        for key, emb in self._cache["embeddings"].items():
            name = Path(key).stem.lower()
            # "ahmet_1", "ahmet_2" → "ahmet" normalizasyonu
            base_name = name.rsplit("_", 1)[0] if name[-1].isdigit() else name
            raw.setdefault(base_name, []).append(emb)

        result: dict[str, np.ndarray] = {}
        for name, emb_list in raw.items():
            mean_emb = np.mean(np.vstack(emb_list), axis=0)
            norm = np.linalg.norm(mean_emb)
            result[name] = mean_emb / norm if norm > 0 else mean_emb

        logger.info("Veritabanı hazır: %d kişi", len(result))
        return result

    def invalidate(self) -> None:
        """Önbelleği temizler, sonraki build() tam yeniden hesaplar."""
        self._cache = {"file_hashes": {}, "embeddings": {}}
        if self.cache_file.exists():
            self.cache_file.unlink()
