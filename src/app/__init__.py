#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, current_app, g, request
from flask_session import Session
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
import datetime

# YENİ: ProxyFix eklemesi
from werkzeug.middleware.proxy_fix import ProxyFix

# Ana projedeki DatabaseTools kütüphanesini import ediyoruz
from lib.database_tools import DatabaseTools

# Yapılandırma dosyasını import ediyoruz
from app.config.config import get_config

# === Yeni Eklenti ===
# Ortam değişkenlerini import et
import lib.env as env_config
# === === === === ====

# Global uygulamalar
bcrypt = Bcrypt()
jwt = JWTManager()
db_tools = None
limiter = Limiter(key_func=get_remote_address)
sess = Session()
face_app = None  # InsightFace uygulaması için global değişken

def create_app(config_name='default', connection_config: dict = None):
    """Flask uygulamasını oluşturan fabrika fonksiyonu"""
    app = Flask(__name__)
    
    if connection_config is None:
        # hata fırtlat
        raise ValueError("connection_config parametresi None olamaz.")
    
    
    
    # Yapılandırmayı yükle
    config = get_config()
    app.config.from_object(config)
    
    # YENİ: ProxyFix'i uygula (eğer reverse proxy arkasındaysa)
    # x_for=1, x_proto=1, x_host=1, x_prefix=1 ayarları, proxy'nin kaç katmanlı olduğuna göre değişebilir.
    # Genellikle bu varsayılanlar çoğu senaryo için yeterlidir.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
    
    # Eklentileri başlat
    bcrypt.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)
    sess.init_app(app)
    CORS(app, supports_credentials=True)
    
    # Veritabanı bağlantısını kur
    global db_tools
    db_tools = DatabaseTools(dbConfig=connection_config)
    
    # InsightFace özniteliğini hazırla - run.py'de doldurulacak
    app.face_app = None
    app.config['FACE_ANALYZER'] = None
    
    # Global yüz tanıma uygulamasına her istekte erişimi sağla
    @app.before_request
    def before_request():
        # Küresel değişkendeki face_app, g nesnesine kopyalanır
        # Böylece her istek kendi g kapsamında face_app'a erişebilir
        global face_app, db_tools
        g.face_app = face_app if face_app is not None else app.face_app
        g.db_tools = db_tools
    
    # === Yeni Eklenti ===
    # Şablonlara ortam değişkenlerini enjekte et
    @app.context_processor
    def inject_env_variables():
        return dict(env_config=env_config, now=datetime.datetime.utcnow())
    # === === === === ====
    
    # Rotaları kaydet
    register_blueprints(app)
    
    # CSRF koruması
    protect_from_csrf(app)
    
    # Hata yönetimi
    register_error_handlers(app)
    
    return app

def register_blueprints(app):
    """Rotaları Flask uygulamasına ekler"""
    from app.routes.auth import auth_bp
    from app.routes.api import api_bp
    from app.routes.web import web_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(web_bp, url_prefix='/')

    # --- YENİ: Admin Blueprint'ini Kaydet ---
    from app.routes.admin import admin_bp
    app.register_blueprint(admin_bp) # url_prefix zaten admin_bp içinde tanımlı ('/admin')
    # --- Kayıt Bitti ---

def protect_from_csrf(app):
    """CSRF koruması ekler"""
    from flask_wtf.csrf import CSRFProtect
    
    # CSRF korumasını etkinleştir
    csrf = CSRFProtect()
    csrf.init_app(app)
    
    # API rotaları için muafiyet
    # Blueprint'i doğrudan muaf tut
    from app.routes.api import api_bp
    
    # Eskiden gelen csrf.exempt ile Blueprint'i muaf tut
    if hasattr(csrf, 'exempt'):
        csrf.exempt(api_bp)
    
    # Bu basit çözüm çalışmazsa, her istek için CSRF kontrolünü doğrudan yapalım
    @app.before_request
    def csrf_protect():
        # API istekleri için CSRF kontrolünü atla
        if request.path.startswith('/api/'):
            # Bu değer, mevcut isteği CSRF kontrolünden muaf tutar
            # Bu yöntem Flask-WTF'nin birçok versiyonunda çalışır
            g._csrf_exempt = True

def register_error_handlers(app):
    """Hata yöneticilerini kaydeder"""
    @app.errorhandler(404)
    def not_found(error):
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def server_error(error):
        from flask import render_template
        return render_template('errors/500.html'), 500 