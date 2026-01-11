#!/usr/bin/env python3
"""
Docker container başlatıldığında environment variable'lardan config.json oluşturur.
Bu sayede hassas bilgiler (şifreler vs.) docker-compose.yml'da tutulur,
config.json ise runtime'da oluşturulur.
"""
import os
import json


def generate_config():
    """Environment variable'lardan config.json oluşturur."""

    config = {
        "name": os.environ.get("NAME", "EyeOfWeb"),
        "vendor": os.environ.get("VENDOR", "WeKnow Developer Team"),
        "version": os.environ.get("VERSION", "2.1.0"),
        "database_config": {
            "host": os.environ.get("DB_HOST", "localhost"),
            "port": os.environ.get("DB_PORT", "5432"),
            "user": os.environ.get("DB_USER", "postgres"),
            "password": os.environ.get("DB_PASSWORD", "postgres"),
            "database": os.environ.get("DB_NAME", "EyeOfWeb"),
        },
        "milvus_config": {
            "host": os.environ.get("MILVUS_HOST", "localhost"),
            "port": os.environ.get("MILVUS_PORT", "19530"),
            "user": os.environ.get("MILVUS_USER", ""),
            "password": os.environ.get("MILVUS_PASSWORD", ""),
        },
        "insightface": {
            "main": {
                "name": os.environ.get("INSIGHTFACE_MODEL", "buffalo_l"),
                "providers": (
                    ["CUDAExecutionProvider", "CPUExecutionProvider"]
                    if os.environ.get("USE_CUDA", "false").lower() == "true"
                    else ["CPUExecutionProvider"]
                ),
            },
            "prepare": {
                # Detection threshold: 0.75 = sadece yüksek güvenilirlikli yüzleri algıla
                "det_thresh": float(os.environ.get("INSIGHTFACE_DET_THRESH", "0.75")),
                "det_size": [
                    int(os.environ.get("INSIGHTFACE_DET_SIZE_W", "640")),
                    int(os.environ.get("INSIGHTFACE_DET_SIZE_H", "640")),
                ],
                "ctx_id": int(os.environ.get("INSIGHTFACE_CTX_ID", "0")),
            },
        },
        "initial_admin_user": {
            "username": os.environ.get("ADMIN_USERNAME", "admin"),
            "password": os.environ.get("ADMIN_PASSWORD", "admin123"),
        },
        "app_settings": {
            "secret_key": os.environ.get("SECRET_KEY", "change-me-in-production"),
            "debug": os.environ.get("FLASK_ENV", "production") == "development",
        },
        "service": {"thread": 4},
    }

    return config


def save_config(config, path="config/config.json"):
    """Config'i dosyaya kaydeder."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"[CONFIG] Config dosyası oluşturuldu: {path}")


if __name__ == "__main__":
    config = generate_config()
    save_config(config)
