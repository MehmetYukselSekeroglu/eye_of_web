# -*- coding: utf-8 -*-

"""
? WeKnow Developer Team Eye Of Web | Enviroments File ?

! DONT CHANGE IT !

"""

import os

CONFIG_FILE_NAME = "config.json"
APPLICATION_BASE_DIR = os.getcwd().split(os.path.sep)[-1]
CONFIG_FILE_PATH = "config" + os.path.sep + "config.json"
DEFAULT_CHARSET = "utf-8"

# Application Information
APP_NAME = "Eye Of Web"
APP_VERSION = "2.3.1"  # Or your current version
APP_TITLE = f"{APP_NAME} v{APP_VERSION}"

# Vendor Information
VENDOR_NAME = "WeKnow Developer Team"

# --- CUDA Configuration ---
# Set to True to attempt using CUDA if available, False to force CPU.
USE_CUDA = False
# --- End CUDA Configuration ---

# System Titles/Descriptions (Examples)
SYSTEM_DESCRIPTION = "Gelişmiş Yüz Tanıma Sistemi"
LOGIN_TITLE = f"{VENDOR_NAME} - {APP_NAME} Giriş"

# --- Allowed Hosts Configuration ---
# List of allowed hostnames. Example: ["example.com", "www.example.com"]
# If empty or not defined, all hosts are allowed (not recommended for production).
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
# --- End Allowed Hosts Configuration ---
