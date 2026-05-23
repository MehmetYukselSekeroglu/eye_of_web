#!/bin/bash
# Face Security v3 başlatıcı (WEB MODU)
# Eski Tkinter main.py YERİNE Flask tabanlı web_app.py'i çalıştırır.
# EyeOfWeb React dashboard'unun "YÜZ GÜVENLİĞİ" sekmesi 5007 portuna
# iframe ile bağlanır.
#
# Eski Tkinter entry'sine geri dönmek için:
#   exec env OPENCV_OPENCL_RUNTIME=disabled python3 main.py ...

set -e

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

mkdir -p logs

# Default port 5007 (Vite dev server 5005'i kullandığı için çakışmasın diye);
# .env veya env var ile override edilebilir: FACE_SEC_PORT=5005 ./launch.sh
exec env OPENCV_OPENCL_RUNTIME=disabled \
     FACE_SEC_HOST="${FACE_SEC_HOST:-127.0.0.1}" \
     FACE_SEC_PORT="${FACE_SEC_PORT:-5007}" \
     python3 web_app.py 2>> logs/launch_error.log
