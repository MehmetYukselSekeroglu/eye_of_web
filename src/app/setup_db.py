#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Veritabanı bağlantı bilgilerini test eden ve yapılandıran yardımcı script.
Bu script, config.py dosyasındaki veritabanı ayarlarını test eder ve 
doğru bilgileri yapılandırmanıza yardımcı olur.

Kullanım:
    python setup_db.py

"""

import os
import sys
import getpass
import psycopg2
from app.config.config import get_config

def test_connection(db_config):
    """Veritabanı bağlantısını test eder"""
    try:
        print(f"Bağlantı test ediliyor: {db_config['host']}:{db_config['port']}, kullanıcı: {db_config['user']}, veritabanı: {db_config['dbname']}")
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute('SELECT version();')
        version = cursor.fetchone()
        conn.close()
        print(f"Bağlantı başarılı! PostgreSQL versiyonu: {version[0]}")
        return True
    except Exception as e:
        print(f"Bağlantı hatası: {str(e)}")
        return False

def setup_config():
    """Veritabanı yapılandırmasını ayarlar"""
    config = get_config()
    db_config = config.DATABASE_CONFIG.copy()
    
    print("Mevcut veritabanı yapılandırması:")
    for k, v in db_config.items():
        print(f"  {k}: {v}")
    
    # Bağlantıyı test et
    if test_connection(db_config):
        return
    
    # Kullanıcıdan yeni bilgiler al
    print("\nVeri tabanı bağlantı bilgilerini güncelleme:")
    db_config['host'] = input(f"Host [{db_config['host']}]: ") or db_config['host']
    db_config['port'] = input(f"Port [{db_config['port']}]: ") or db_config['port']
    db_config['user'] = input(f"Kullanıcı adı [{db_config['user']}]: ") or db_config['user']
    db_config['password'] = getpass.getpass(f"Şifre [******]: ") or db_config['password']
    db_config['dbname'] = input(f"Veritabanı adı [{db_config['dbname']}]: ") or db_config['dbname']
    
    # Bağlantıyı test et
    if test_connection(db_config):
        # Çevre değişkenlerini ayarla
        print("\nÇevre değişkenlerini ayarlama:")
        print("Bu ayarları .env dosyasına veya sisteminize kalıcı olarak eklemeniz önerilir.")
        print("Geçici olarak bu oturumda ayarlamak için aşağıdaki komutları kullanabilirsiniz:")
        
        print("\nBash/Zsh için:")
        for k, v in db_config.items():
            print(f"export DB_{k.upper()}='{v}'")
        
        print("\nWindows CMD için:")
        for k, v in db_config.items():
            print(f"set DB_{k.upper()}={v}")
        
        print("\nPowershell için:")
        for k, v in db_config.items():
            print(f"$env:DB_{k.upper()}='{v}'")
        
        # Geçici olarak çevre değişkenlerini ayarla
        for k, v in db_config.items():
            os.environ[f"DB_{k.upper()}"] = str(v)
        
        print("\nBu oturum için çevre değişkenleri ayarlandı.")
    else:
        print("Bağlantı kurulamadı. Lütfen bilgileri kontrol edin ve tekrar deneyin.")

if __name__ == "__main__":
    setup_config() 