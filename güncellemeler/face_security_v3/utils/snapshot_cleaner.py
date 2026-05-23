"""
Snapshot otomatik temizleme modülü.
Eski veya fazla snapshot dosyalarını siler.
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class SnapshotCleaner:
    def __init__(self, max_age_days: int = 7, max_files: int = 500):
        self.max_age = timedelta(days=max_age_days)
        self.max_files = max_files

    def clean(self, directory: str) -> int:
        """
        Dizindeki eski veya fazla snapshot'ları siler.
        Silinen dosya sayısını döner.
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            return 0

        # Dosyaları değiştirilme zamanına göre eskiden yeniye sırala
        files = sorted(
            [f for f in dir_path.glob("*.jpg") if f.is_file()],
            key=lambda f: f.stat().st_mtime,
        )

        now = datetime.now()
        deleted = 0

        for f in files:
            file_age = now - datetime.fromtimestamp(f.stat().st_mtime)
            remaining = len(files) - deleted

            # Çok eski veya toplam sayı sınırı aşıldıysa sil
            if file_age > self.max_age or remaining > self.max_files:
                try:
                    f.unlink()
                    deleted += 1
                except OSError as e:
                    logger.warning("Snapshot silinemedi %s: %s", f, e)

        if deleted:
            logger.info("Temizlik: %d dosya silindi — %s", deleted, directory)

        return deleted

    def clean_all(self, *directories: str) -> int:
        """Birden fazla dizini temizler, toplam silinen sayıyı döner."""
        return sum(self.clean(d) for d in directories)
