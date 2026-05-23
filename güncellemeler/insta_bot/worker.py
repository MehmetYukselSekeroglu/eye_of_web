"""
EyeOfWeb — Instagram Followers Scraper (non-interactive)

Orijinal `~/insta_bot/worker.py` üzerinden uyarlandı:
- Tkinter GUI bağımlılığı yok (panel.py'dan ayrı).
- `input()` ile bekleme yerine: önce `cookies.pkl` yüklenir; yoksa
  `--allow-manual-login` bayrağı varsa headed Chrome ile el-ile login,
  yoksa derhal hata döner (non-interactive default).
- `hedefler.txt` zorunluluğu YOK — `--targets "user1,user2,..."`
  CLI argümanı kabul eder; ya da `--targets-file path.txt` ile dosyadan.
- Çıktı satır-satır flush'lı `print(...)` ile stdout'a verilir;
  EyeOfWeb dashboard backend'i (server.js) spawn'da pipe'layıp canlı
  log paneline akıtır.
- Sonuçlar `--output-file` ile belirtilen yola eklenir
  (default: `takipciler.txt` cwd altında).

CLI Örnek:
    python3 worker.py --targets "instagram,natgeo" --max-per-target 20 \\
        --headless --cookies-file lib/insta_bot/cookies.pkl
"""
import argparse
import os
import pickle
import sys
import time
from typing import List, Optional


def _emit(msg: str) -> None:
    """stdout'a flush'lı log basar; subprocess pipe için kritik."""
    print(msg, flush=True)


def load_targets_from_file(path: str) -> List[str]:
    if not os.path.exists(path):
        _emit(f"[ERR] Hedef dosyası bulunamadı: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip()]


def parse_targets_arg(targets_arg: Optional[str]) -> List[str]:
    if not targets_arg:
        return []
    raw = targets_arg.replace("\n", ",").replace(";", ",")
    return [t.strip().lstrip("@") for t in raw.split(",") if t.strip()]


def _build_driver(headless: bool, user_data_dir: Optional[str] = None):
    """Selenium Chrome driver başlatır; lazy import (Selenium opsiyonel)."""
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    try:
        from webdriver_manager.chrome import ChromeDriverManager
    except Exception:
        ChromeDriverManager = None

    opts = Options()
    if headless:
        # Yeni headless modu; eski headless çoğu IG sayfasında bloklanıyor
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    if user_data_dir:
        opts.add_argument(f"--user-data-dir={user_data_dir}")

    if ChromeDriverManager is not None:
        service = Service(ChromeDriverManager().install())
    else:
        service = Service()  # PATH'teki chromedriver'a düş
    driver = webdriver.Chrome(service=service, options=opts)
    return driver


def _load_cookies(driver, cookies_path: str) -> bool:
    if not cookies_path or not os.path.exists(cookies_path):
        return False
    try:
        # Cookie eklemeden önce alan adına git
        driver.get("https://www.instagram.com/")
        time.sleep(2)
        with open(cookies_path, "rb") as f:
            cookies = pickle.load(f)
        if not isinstance(cookies, list):
            _emit(f"[WARN] cookies.pkl beklenmedik format: {type(cookies).__name__}")
            return False
        added = 0
        for c in cookies:
            try:
                driver.add_cookie(c)
                added += 1
            except Exception as ce:
                _emit(f"[WARN] cookie ekleme atlandı: {ce}")
        _emit(f"[INFO] {added}/{len(cookies)} cookie yüklendi: {cookies_path}")
        driver.get("https://www.instagram.com/")
        time.sleep(3)
        return added > 0
    except Exception as e:
        _emit(f"[WARN] cookies yüklenemedi: {e}")
        return False


def scrape_target(driver, target: str, max_per_target: int, output_file: str) -> int:
    """Tek hedef profilden takipçi listesini sıyırır. Eklenen yeni kayıt sayısını döner."""
    from selenium.webdriver.common.by import By

    # Mevcut listeyi oku (tekrar yazımı önlemek için)
    existing = set()
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            existing = {x.strip() for x in f if x.strip()}

    _emit(f"[STEP] Hedef açılıyor: {target}")
    driver.get(f"https://www.instagram.com/{target}/")
    time.sleep(5)

    try:
        btn = driver.find_element(By.XPATH, "//a[contains(@href,'followers')]")
        btn.click()
    except Exception as e:
        _emit(f"[ERR] Takipçi listesi açılmadı ({target}): {e}")
        return 0
    time.sleep(6)

    try:
        scroll = driver.find_element(
            By.XPATH, "//div[@role='dialog']//div[contains(@style,'overflow')]"
        )
    except Exception as e:
        _emit(f"[ERR] Scroll konteyneri bulunamadı ({target}): {e}")
        return 0

    new_added = 0
    stagnant_rounds = 0
    last_size = 0
    while new_added < max_per_target and stagnant_rounds < 5:
        elems = driver.find_elements(By.XPATH, "//div[@role='dialog']//a")
        for e in elems:
            try:
                link = e.get_attribute("href")
            except Exception:
                continue
            if not link or "/" not in link:
                continue
            user = link.split("/")[-2]
            if not user or user in existing:
                continue
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(user + "\n")
            existing.add(user)
            new_added += 1
            _emit(f"[HIT] {target} -> {user}  ({new_added}/{max_per_target})")
            if new_added >= max_per_target:
                break

        driver.execute_script(
            "arguments[0].scrollTop = arguments[0].scrollHeight", scroll
        )
        time.sleep(2)

        if len(existing) == last_size:
            stagnant_rounds += 1
        else:
            stagnant_rounds = 0
        last_size = len(existing)

    _emit(f"[DONE] {target}: {new_added} yeni takipçi eklendi.")
    return new_added


def main():
    p = argparse.ArgumentParser(description="EyeOfWeb Instagram Followers Scraper")
    p.add_argument(
        "--targets",
        type=str,
        default=None,
        help="Virgülle ayrılmış kullanıcı listesi (örn: 'natgeo,nasa'). "
        "Yeni satır / noktalı virgül de ayraç kabul edilir.",
    )
    p.add_argument(
        "--targets-file",
        type=str,
        default=None,
        help="Hedef listesini dosyadan oku (her satır bir kullanıcı).",
    )
    p.add_argument(
        "--max-per-target",
        type=int,
        default=int(os.environ.get("INSTA_MAX_PER_TARGET", "20")),
        help="Hedef başına max yeni takipçi (default 20)",
    )
    p.add_argument(
        "--output-file",
        type=str,
        default="takipciler.txt",
        help="Toplanan takipçilerin yazılacağı dosya (append).",
    )
    p.add_argument(
        "--cookies-file",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "cookies.pkl"),
        help="Selenium oturum cookies'i (pickle).",
    )
    p.add_argument(
        "--user-data-dir",
        type=str,
        default=None,
        help="Chrome profil dizini (cookies kalıcılığı için).",
    )
    p.add_argument("--headless", action="store_true", help="Tarayıcıyı headless aç.")
    p.add_argument(
        "--allow-manual-login",
        action="store_true",
        help="Cookies başarısızsa interaktif manuel login bekle "
        "(stdin'den ENTER beklenir; sadece terminal modunda).",
    )
    args = p.parse_args()

    targets = parse_targets_arg(args.targets)
    if args.targets_file:
        targets.extend(load_targets_from_file(args.targets_file))
    # tekilleştirme + sıra koru
    targets = list(dict.fromkeys(targets))

    if not targets:
        _emit("[ERR] Hedef yok. --targets veya --targets-file kullanın.")
        sys.exit(2)

    _emit(f"[INIT] {len(targets)} hedef: {', '.join(targets)}")
    _emit(f"[INIT] Output: {os.path.abspath(args.output_file)}")
    _emit(f"[INIT] Max per target: {args.max_per_target} | Headless: {args.headless}")

    try:
        driver = _build_driver(headless=args.headless, user_data_dir=args.user_data_dir)
    except Exception as e:
        _emit(f"[FATAL] Chrome driver başlatılamadı: {e}")
        sys.exit(3)

    try:
        # Önce cookies dene
        logged_in = _load_cookies(driver, args.cookies_file)

        if not logged_in:
            if args.allow_manual_login and sys.stdin.isatty():
                _emit(
                    "[STEP] Cookies yüklenemedi. Manuel login modu — "
                    "tarayıcıda giriş yapın, sonra terminale ENTER basın."
                )
                driver.get("https://www.instagram.com/")
                try:
                    input(">>> ENTER bas <<< ")
                except EOFError:
                    _emit("[ERR] Stdin kapalı, manuel login mümkün değil.")
                    sys.exit(4)
            else:
                _emit(
                    "[FATAL] Cookies yüklenemedi ve manuel login devre dışı. "
                    "Çözüm: --allow-manual-login (terminalde) veya geçerli "
                    "cookies.pkl sağlayın."
                )
                sys.exit(4)

        total = 0
        for t in targets:
            try:
                total += scrape_target(
                    driver=driver,
                    target=t,
                    max_per_target=args.max_per_target,
                    output_file=args.output_file,
                )
            except Exception as e:
                _emit(f"[ERR] {t} işlenirken hata: {e}")

        _emit(f"[SUMMARY] Toplam {total} yeni takipçi kaydedildi -> {args.output_file}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
