#!/usr/bin/env python3
# -*- coding: utf-8 -*-
    
import os
import secrets

class Config:
    """Ana yapılandırma sınıfı"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or secrets.token_hex(32)
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'admin'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'golfalfa'  # Varsayılan güvenlik kodu
    
    # Veritabanı ayarları - Çevre değişkenlerinden veya varsayılan değerlerden al
    DATABASE_CONFIG = {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': os.environ.get('DB_PORT', '5432'),
        'user': os.environ.get('DB_USER', 'postgres'),
        'password': os.environ.get('DB_PASSWORD', 'postgres'),
        'dbname': os.environ.get('DB_NAME', 'EyeOfWeb')
    }
    
    # API kısıtlamaları
    RATE_LIMIT = '100/hour'  # Saat başına izin verilen istek sayısı
    
    # Oturum yönetimi
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = 3600  # 1 saat
    SESSION_COOKIE_SAMESITE = 'Lax'

class DevelopmentConfig(Config):
    """Geliştirme ortamı yapılandırması"""
    DEBUG = True
    TESTING = False
    ENV = 'development'
    PREFERRED_URL_SCHEME = 'https'  # HTTPS zorunlu
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True

class ProductionConfig(Config):
    """Üretim ortamı yapılandırması"""
    DEBUG = False
    TESTING = False
    ENV = 'production'
    
    # Üretimde daha güçlü güvenlik önlemleri
    PREFERRED_URL_SCHEME = 'https'  # HTTPS zorunlu
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True


class TestingConfig(Config):
    """Test ortamı yapılandırması"""
    DEBUG = True
    TESTING = True
    ENV = 'testing'

# Ortam değişkenine göre yapılandırma seçimi
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Uygun yapılandırmayı döndürür"""
    config_name = os.environ.get('FLASK_ENV', 'default')
    return config.get(config_name, config['default']) 
