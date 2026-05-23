"""
Tek seferlik script: auth_config.json içindeki tuzsuz SHA256 PIN hash'ini
bcrypt'e migrate eder.

Kullanım:
    python3 migrate_pin_to_bcrypt.py

Çalışma:
1. Mevcut auth_config.json'u okur
2. Hash zaten bcrypt formatındaysa ($2 ile başlar) çıkar
3. Kullanıcıdan PIN ister (eski hash ile doğrulamak için)
4. PIN doğru ise bcrypt ile yeniden hash'ler ve dosyayı atomik olarak yazar

Geriye dönük: Bu script tek seferlik. Migration sonrası
auth_manager.py'deki SHA256 fallback kodu kaldırılabilir (ama acil değil).
"""
import getpass
import hashlib
import json
import sys
from pathlib import Path

try:
    import bcrypt
except ImportError:
    print("HATA: bcrypt kurulu değil.")
    print("Kurulum: pip install bcrypt")
    sys.exit(1)

AUTH_FILE = Path("auth_config.json")
BACKUP_FILE = Path("auth_config.json.pre-bcrypt-backup")


def main() -> int:
    if not AUTH_FILE.exists():
        print(f"HATA: {AUTH_FILE} bulunamadı")
        print("Bu script proje kök dizininden çalıştırılmalı.")
        return 1

    with AUTH_FILE.open() as f:
        config = json.load(f)

    old_hash = config.get("pin_hash", "")
    if not old_hash:
        print("HATA: pin_hash alanı yok veya boş")
        return 1

    # Zaten bcrypt mi?
    if old_hash.startswith("$2"):
        print("PIN zaten bcrypt formatında.")
        print("Migration gerekmiyor — çıkılıyor.")
        return 0

    print("Mevcut PIN tuzsuz SHA256 ile hash'lenmiş.")
    print("Bcrypt'e migrate edilecek.")
    print()
    print("Doğrulama için mevcut PIN'i girin.")
    print("(PIN ekrana yazılmayacak - güvenli giriş)")
    print()

    try:
        pin = getpass.getpass("PIN: ")
    except (KeyboardInterrupt, EOFError):
        print("\nİptal edildi.")
        return 1

    if not pin:
        print("HATA: PIN boş olamaz")
        return 1

    # Eski yöntemle doğrula
    sha = hashlib.sha256(pin.encode("utf-8")).hexdigest()
    if sha != old_hash:
        print("HATA: Girilen PIN mevcut hash ile eşleşmiyor.")
        print("PIN doğru mu? Caps Lock açık mı?")
        return 1

    print()
    print("PIN doğrulandı. Bcrypt hash hesaplanıyor...")

    # Yeni bcrypt hash
    new_hash = bcrypt.hashpw(
        pin.encode("utf-8"),
        bcrypt.gensalt(rounds=12)
    )

    # Yedek al
    BACKUP_FILE.write_text(json.dumps(config, indent=2))
    print(f"Yedek alındı: {BACKUP_FILE}")

    # Yeni config
    config["pin_hash"] = new_hash.decode("utf-8")
    config["pin_hash_algo"] = "bcrypt"  # versiyon belirteci

    # Atomic write (önce tmp, sonra rename)
    tmp = AUTH_FILE.with_suffix(".json.tmp")
    with tmp.open("w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")  # POSIX-friendly trailing newline
    tmp.replace(AUTH_FILE)

    print()
    print("=" * 50)
    print("PIN başarıyla bcrypt'e migrate edildi.")
    print("=" * 50)
    print()
    print("Sonraki adımlar:")
    print("1. Uygulamayı başlat ve PIN ile giriş yapabildiğini doğrula")
    print("2. Doğrulama tamamsa yedeği silebilirsin:")
    print(f"   rm {BACKUP_FILE}")
    print()
    print("PIN'i değiştirmek istersen UI üzerinden yapabilirsin.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
