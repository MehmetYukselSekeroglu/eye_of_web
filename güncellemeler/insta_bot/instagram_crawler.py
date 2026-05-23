#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EyeOfWeb Instagram Bot — Dashboard Entry Point

Konum: güncellemeler/insta_bot/instagram_crawler.py
`yeni_dashboard/backend/server.js` içindeki `/api/scan/instagram-bot`
endpoint'i tarafından `python3 instagram_crawler.py --targets ...`
formatında çağrılır. Standart EyeOfWeb argparse paterni.

Bu dosya bir wrapper — gerçek scraping aynı dizindeki `worker.py`'dadır.

Kullanım örnekleri:
    python3 instagram_crawler.py --targets "natgeo,nasa" --headless
    python3 instagram_crawler.py --targets-file instagram_hedefler.txt
    python3 instagram_crawler.py --targets "@bbcnews" --max-per-target 50
"""
import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description="EyeOfWeb Instagram Followers Crawler",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--targets",
        type=str,
        default=None,
        help="Virgül/yeni satır/noktalı virgül ile ayrılmış kullanıcı listesi.",
    )
    parser.add_argument(
        "--targets-file",
        type=str,
        default=None,
        help="Hedef kullanıcı adlarını içeren dosya yolu (her satır bir kullanıcı).",
    )
    parser.add_argument(
        "--max-per-target",
        type=int,
        default=int(os.environ.get("INSTA_MAX_PER_TARGET", "20")),
        help="Hedef başına çekilecek max yeni takipçi sayısı.",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "instagram_takipciler.txt"),
        help="Toplanan takipçilerin yazılacağı dosya (append).",
    )
    parser.add_argument(
        "--cookies-file",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "cookies.pkl"),
        help="Önceden kayıtlı Instagram oturum cookies'i.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Tarayıcıyı headless aç (default visible).",
    )
    parser.add_argument(
        "--allow-manual-login",
        action="store_true",
        help="Cookies başarısızsa terminalde manuel login için bekle.",
    )

    args = parser.parse_args()

    # lib/insta_bot worker'ı çağırmak için sys.argv yeniden inşa
    # (worker.py'ı subprocess yerine in-process çalıştırıyoruz; tek context).
    worker_argv = ["worker.py"]
    if args.targets:
        worker_argv += ["--targets", args.targets]
    if args.targets_file:
        worker_argv += ["--targets-file", args.targets_file]
    worker_argv += ["--max-per-target", str(args.max_per_target)]
    worker_argv += ["--output-file", args.output_file]
    if args.cookies_file:
        worker_argv += ["--cookies-file", args.cookies_file]
    if args.headless:
        worker_argv += ["--headless"]
    if args.allow_manual_login:
        worker_argv += ["--allow-manual-login"]

    # worker.py ile co-located → kendi dizinini sys.path'a ekle
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # In-process invoke (worker'ın main() argparse'ı sys.argv okuyor)
    sys.argv = worker_argv
    from worker import main as worker_main
    worker_main()


if __name__ == "__main__":
    main()
