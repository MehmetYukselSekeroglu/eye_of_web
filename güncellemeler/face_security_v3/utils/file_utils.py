"""
Dosya işlemleri — güvenli dosya adı oluşturma ve path traversal koruması.
"""
import re
import time
from pathlib import Path


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """
    Kullanıcıdan gelen dosya adını güvenli hale getirir.
    - Yalnızca küçük harf, rakam, alt çizgi ve tire'ye izin verir
    - Path traversal karakterlerini temizler
    - Boş sonuç durumunda zaman damgalı ad üretir
    """
    cleaned = name.strip().lower()
    # Türkçe karakter dönüşümü
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")
    cleaned = cleaned.translate(tr_map)
    # Yalnızca izin verilen karakterleri koru
    cleaned = re.sub(r"[^\w\-]", "_", cleaned)
    # Path traversal: nokta-nokta dizilerini temizle
    cleaned = re.sub(r"\.{2,}", "", cleaned)
    # Baştaki/sondaki alt çizgileri ve tireleri temizle
    cleaned = cleaned.strip("_-")
    # Boş kalırsa zaman damgalı ad üret
    if not cleaned:
        cleaned = f"person_{int(time.time())}"
    return cleaned[:max_length]


def safe_save_path(base_dir: str | Path, filename: str) -> Path:
    """
    Hedef dosya yolunun base_dir içinde kaldığını doğrular.
    Dışarı çıkmaya çalışan yollarda ValueError fırlatır.
    """
    base = Path(base_dir).resolve()
    target = (base / filename).resolve()
    if not str(target).startswith(str(base) + "/"):
        raise ValueError(f"Geçersiz dosya yolu: {filename!r} base_dir dışına çıkıyor.")
    return target


def ensure_dirs(*dirs: str) -> None:
    """Belirtilen dizinleri oluşturur, varsa geçer."""
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
