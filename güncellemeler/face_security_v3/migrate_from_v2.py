"""
Face Security v2 → v3 Geçiş Betiği

Yapar:
  1. v2 security_panel.py dosyasından kamera URL'lerini ve Telegram
     bilgilerini ayıklar
  2. .env dosyasını otomatik oluşturur (varsa dokunmaz)
  3. v2 veritabanı, snapshot ve log dizinlerini v3'e sembolik bağ veya
     kopyayla bağlar
  4. Veritabanı dosya adlarındaki tutarsızlıkları raporlar

Kullanım:
  python migrate_from_v2.py --v2-dir ../face_security_v2
"""
import argparse
import re
import shutil
import sys
from pathlib import Path


V2_DEFAULT = Path(__file__).parent.parent / "face_security_v2"


def extract_credentials(v2_panel: Path) -> dict:
    """v2 security_panel.py'den kimlik bilgilerini ayıkla."""
    text = v2_panel.read_text(encoding="utf-8")
    creds: dict = {}

    # Telegram
    tg_token = re.search(r'TELEGRAM_TOKEN\s*=\s*["\']([^"\']+)["\']', text)
    tg_chat = re.search(r'TELEGRAM_CHAT_ID\s*=\s*["\']([^"\']+)["\']', text)
    if tg_token:
        creds["TELEGRAM_BOT_TOKEN"] = tg_token.group(1)
    if tg_chat:
        creds["TELEGRAM_CHAT_ID"] = tg_chat.group(1)

    # Kamera URL'leri
    cam_pattern = re.findall(
        r'(\d+):\s*["\']?(rtsp://[^"\',$\s]+)["\']?', text
    )
    for cam_id, url in cam_pattern:
        cid = int(cam_id)
        if 1 <= cid <= 25:
            creds[f"CAM_{cid:02d}_URL"] = url

    return creds


def write_env(creds: dict, env_path: Path) -> None:
    if env_path.exists():
        print(f"⚠️  .env dosyası zaten mevcut, dokunulmadı: {env_path}")
        return

    lines = [
        "# Face Security v3 — Ortam Değişkenleri",
        "# Bu dosya migrate_from_v2.py tarafından oluşturuldu.",
        "# .env dosyasını ASLA Git'e eklemeyin!\n",
        "# --- Telegram ---",
        f"TELEGRAM_BOT_TOKEN={creds.get('TELEGRAM_BOT_TOKEN', 'DEGISTIR')}",
        f"TELEGRAM_CHAT_ID={creds.get('TELEGRAM_CHAT_ID', 'DEGISTIR')}",
        "",
        "# --- Kamera URL'leri ---",
    ]
    for i in range(1, 26):
        key = f"CAM_{i:02d}_URL"
        url = creds.get(key, "")
        lines.append(f"{key}={url}")

    lines += [
        "",
        "# --- Dizinler (v2'den paylaşımlı) ---",
        "DATABASE_PATH=database",
        "KNOWN_PATH=snapshots/known",
        "UNKNOWN_PATH=snapshots/unknown",
        "LOG_DIR=logs",
        "",
        "# --- Parametreler ---",
        "THRESHOLD=0.45",
        "INFERENCE_FPS=4",
        "SNAPSHOT_COOLDOWN=20",
        "PATROL_SCAN_SECONDS=10",
        "PATROL_HOLD_SECONDS=20",
        "LOG_THROTTLE_SECONDS=30",
        "SNAPSHOT_MAX_AGE_DAYS=7",
        "SNAPSHOT_MAX_FILES=500",
    ]

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✅ .env oluşturuldu: {env_path}")


def link_or_copy_dir(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        print(f"   ↳ Mevcut: {dst.name}")
        return
    if src.exists():
        dst.symlink_to(src.resolve())
        print(f"   ↳ Bağlandı: {dst.name} → {src}")
    else:
        dst.mkdir(parents=True, exist_ok=True)
        print(f"   ↳ Oluşturuldu: {dst.name}")


def report_db_naming(db_path: Path) -> None:
    print("\n📋 Veritabanı İsimlendirme Raporu:")
    uppercase_files = []
    for f in sorted(db_path.iterdir()):
        if f.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            if any(c.isupper() or c == " " for c in f.stem):
                uppercase_files.append(f.name)

    if uppercase_files:
        print(f"  ⚠️  Standart dışı isimli {len(uppercase_files)} dosya bulundu:")
        for name in uppercase_files[:10]:
            print(f"      • {name}")
        if len(uppercase_files) > 10:
            print(f"      ... ve {len(uppercase_files) - 10} dosya daha")
        print("  💡 Tüm dosyaları küçük harfe çevirmek için:")
        print("     python migrate_from_v2.py --normalize-db")
    else:
        print("  ✅ Tüm dosya adları standarda uygun.")


def normalize_db(db_path: Path, dry_run: bool = True) -> None:
    """Büyük harfli ve boşluklu dosyaları standart isme dönüştür."""
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")

    renamed = 0
    for f in sorted(db_path.iterdir()):
        if f.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        new_stem = f.stem.lower().translate(tr_map)
        new_stem = re.sub(r"[^\w\-]", "_", new_stem).strip("_")
        new_name = f"{new_stem}{f.suffix.lower()}"
        if new_name != f.name:
            target = f.parent / new_name
            if dry_run:
                print(f"  [DRY-RUN] {f.name} → {new_name}")
            else:
                if not target.exists():
                    f.rename(target)
                    print(f"  ✓ {f.name} → {new_name}")
                else:
                    print(f"  ⚠️  Hedef mevcut, atlandı: {new_name}")
            renamed += 1

    if dry_run and renamed:
        print(f"\n  Toplam {renamed} dosya yeniden adlandırılacak.")
        print("  Onaylamak için: python migrate_from_v2.py --normalize-db --apply")


def main() -> None:
    parser = argparse.ArgumentParser(description="Face Security v2 → v3 Geçiş Aracı")
    parser.add_argument("--v2-dir", type=Path, default=V2_DEFAULT)
    parser.add_argument("--normalize-db", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Yeniden adlandırmayı uygula")
    args = parser.parse_args()

    v2_dir = args.v2_dir.resolve()
    v3_dir = Path(__file__).parent.resolve()

    print(f"\n🚀 Face Security v2 → v3 Geçiş")
    print(f"   v2: {v2_dir}")
    print(f"   v3: {v3_dir}\n")

    if not v2_dir.exists():
        print(f"❌ v2 dizini bulunamadı: {v2_dir}")
        sys.exit(1)

    v2_panel = v2_dir / "security_panel.py"

    # Sadece normalize işlemi
    if args.normalize_db:
        db_path = v2_dir / "database"
        normalize_db(db_path, dry_run=not args.apply)
        return

    # .env oluştur
    if v2_panel.exists():
        print("1️⃣  Kimlik bilgileri ayıklanıyor...")
        creds = extract_credentials(v2_panel)
        print(f"   {len([k for k in creds if 'CAM' in k])} kamera URL'si bulundu.")
        write_env(creds, v3_dir / ".env")
    else:
        print("⚠️  security_panel.py bulunamadı — .env manuel oluşturulmalı.")

    # Dizinleri bağla
    print("\n2️⃣  Dizinler bağlanıyor...")
    for dir_name in ["database", "snapshots", "logs"]:
        link_or_copy_dir(v2_dir / dir_name, v3_dir / dir_name)

    # Config dosyalarını kopyala
    print("\n3️⃣  Yapılandırma dosyaları kopyalanıyor...")
    for cfg in ["camera_config.json", "startup_config.json"]:
        src = v2_dir / cfg
        dst = v3_dir / cfg
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            print(f"   ✅ {cfg}")

    # DB isimlendirme raporu
    db_path = v2_dir / "database"
    if db_path.exists():
        report_db_naming(db_path)

    print("\n✅ Geçiş tamamlandı!")
    print("\n📋 Sonraki Adımlar:")
    print("  1. .env dosyasını açıp bilgileri doğrulayın")
    print("  2. pip install -r requirements.txt")
    print("  3. python main.py")


if __name__ == "__main__":
    main()
