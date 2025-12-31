#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Blueprint, request, jsonify, current_app, g, session
from app.controllers.search_controller import SearchController
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import limiter
import os
import time
import io
from PIL import Image
import numpy as np
from app.routes.web import login_required
import cv2
import base64
import traceback

api_bp = Blueprint('api', __name__)

# Tüm API rotaları için JWT doğrulaması gerekli
@api_bp.before_request
@jwt_required(optional=True)
def check_authentication():
    """API isteği öncesi kimlik doğrulama kontrolü"""
    # JWT token olmadan erişilebilir rotalar
    public_routes = ['/api/status']
    
    # Eğer route public değilse ve kullanıcı kimliği yoksa erişimi reddet
    if request.path not in public_routes and get_jwt_identity() is None:
        return jsonify({
            'success': False,
            'message': 'Kimlik doğrulama gerekli'
        }), 401

# Flask-WTF CSRF koruması için whitelist (JWT ile koruma yeterli)
@api_bp.before_request
def csrf_exempt_for_api():
    """Flask-WTF CSRF korumasını API rotaları için bypass et"""
    if request.endpoint and request.endpoint.startswith('api.'):
        # CSRF koruması için geçici olarak exempt işaretle
        request.csrf_exempt = True

# Landmark endpointleri için devre dışı bırakma kontrolü
@api_bp.before_request
def check_landmark_endpoints():
    """Landmark endpointlerini devre dışı bırak"""
    # Landmark ile ilgili tüm rotaları engelle
    if '/landmarks' in request.path:
        return jsonify({
            'success': False,
            'message': 'Landmark özelliği devre dışı bırakılmıştır'
        }), 403

@api_bp.route('/status')
def api_status():
    """API durumunu kontrol eder"""
    return jsonify({
        'success': True,
        'message': 'API çalışıyor',
        'version': '1.0.0',
        'timestamp': int(time.time())
    })

@api_bp.route('/search', methods=['POST'])
@limiter.limit("30/minute")
def search_faces():
    """Yüz arama API'si"""
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': 'Geçersiz istek formatı'
        }), 400
    
    # Arama sonuçlarını al
    success, message, results = SearchController.search_faces(data)
    
    # Sonuçları döndür
    return jsonify({
        'success': success,
        'message': message,
        'results': results
    }), 200 if success else 400

@api_bp.route('/search/upload', methods=['POST'])
@limiter.limit("10/minute")
def search_by_image():
    """Yüklenen görsele göre arama API'si"""
    # Dosya kontrolü
    if 'image' not in request.files:
        return jsonify({
            'success': False,
            'message': 'Görsel dosyası gerekli'
        }), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({
            'success': False,
            'message': 'Dosya seçilmedi'
        }), 400
    
    # Eşik değeri parametresi (isteğe bağlı)
    threshold = float(request.form.get('threshold', 0.6))
    
    # Arama yapılacak kaynakları belirle
    search_whitelist = request.form.get('search_whitelist', 'false').lower() in ['true', '1', 'yes', 'y']
    search_egm = request.form.get('search_egm', 'false').lower() in ['true', '1', 'yes', 'y']
    
    try:
        # Dosyayı PIL Image olarak aç
        img = Image.open(io.BytesIO(file.read()))
        
        # NumPy dizisine dönüştür (RGB)
        img_array = np.array(img.convert('RGB'))
        
        # Arama işlemini gerçekleştir
        success, message, results = SearchController.search_by_image(
            img_array, 
            threshold=threshold,
            search_whitelist=search_whitelist,
            search_egm=search_egm
        )
        
        # Sonuçları döndür
        return jsonify({
            'success': success,
            'message': message,
            'results': results
        }), 200 if success else 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Görsel işleme hatası: {str(e)}'
        }), 500

@api_bp.route('/face/<face_id>')
def get_face_details(face_id):
    """Belirli bir yüz ID'sine göre detay bilgileri API'si"""
    success, message, face_details = SearchController.get_face_details(face_id)
    
    return jsonify({
        'success': success,
        'message': message,
        'face': face_details
    }), 200 if success else 404

@api_bp.route('/domains')
def get_domains():
    """Tüm domainleri getirir"""
    success, message, domains = SearchController.get_domains()
    
    return jsonify({
        'success': success,
        'message': message,
        'domains': domains
    }), 200 if success else 500

@api_bp.route('/risk-levels')
def get_risk_levels():
    """Tüm risk seviyelerini getirir"""
    success, message, risk_levels = SearchController.get_risk_levels()
    
    return jsonify({
        'success': success,
        'message': message,
        'risk_levels': risk_levels
    }), 200 if success else 500

@api_bp.route('/categories')
def get_categories():
    """Tüm kategorileri getirir"""
    success, message, categories = SearchController.get_categories()
    
    return jsonify({
        'success': success,
        'message': message,
        'categories': categories
    }), 200 if success else 500

@api_bp.route('/search/whitelist', methods=['POST'])
@limiter.limit("20/minute")
def search_whitelist_faces():
    """Beyaz liste yüzlerini arama API'si"""
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': 'Geçersiz istek formatı'
        }), 400
    
    # Arama sonuçlarını al
    success, message, results = SearchController.search_whitelist_faces(data)
    
    # Sonuçları döndür
    return jsonify({
        'success': success,
        'message': message,
        'results': results
    }), 200 if success else 400

@api_bp.route('/search/external', methods=['POST'])
@limiter.limit("20/minute")
def search_external_faces():
    """Dış yüz deposundaki yüzleri arama API'si"""
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': 'Geçersiz istek formatı'
        }), 400
    
    # Arama sonuçlarını al
    success, message, results = SearchController.search_external_faces(data)
    
    # Sonuçları döndür
    return jsonify({
        'success': success,
        'message': message,
        'results': results
    }), 200 if success else 400
    
@api_bp.route('/search/egm', methods=['POST'])
@limiter.limit("20/minute")
def search_egm_arananlar():
    """EGM arananlar listesindeki yüzleri arama API'si"""
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': 'Geçersiz istek formatı'
        }), 400
    
    # Arama sonuçlarını al
    success, message, results = SearchController.search_egm_arananlar(data)
    
    # Sonuçları döndür
    return jsonify({
        'success': success,
        'message': message,
        'results': results
    }), 200 if success else 400

@api_bp.route('/face/query/landmarks', methods=['GET'])
@limiter.limit("60/minute")
def get_query_face_landmarks():
    """
    EyeOfWeb Anti Terror - Aranan yüz (query face) için landmark verilerini getir
    ---
    Bu özellik devre dışı bırakılmıştır
    """
    return jsonify({
        'success': False,
        'message': 'Landmark özelliği devre dışı bırakılmıştır'
    }), 403

# Diğer landmark endpointleri için genel devre dışı bırakma
@api_bp.route('/whitelist/face/<face_id>/landmarks', methods=['GET'])
@api_bp.route('/egm/face/<face_id>/landmarks', methods=['GET'])
def disabled_landmark_endpoints(face_id=None):
    """
    Devre dışı bırakılmış landmark endpointleri
    ---
    Bu özellik güvenlik nedeniyle devre dışı bırakılmıştır
    """
    return jsonify({
        'success': False,
        'message': 'Landmark özelliği devre dışı bırakılmıştır'
    }), 403

@api_bp.route('/face/<face_id>/bbox', methods=['GET'])
@limiter.limit("60/minute")
def get_face_bbox(face_id):
    """
    Yüz ID'sine göre sınırlayıcı kutu (bounding box) verilerini getir
    ---
    Bu endpoint, verilen yüz ID'sine ait sınırlayıcı kutu verilerini döndürür.
    """
    try:
        from lib.database_tools import DatabaseTools
        db = DatabaseTools()
        
        # Yüz detaylarını al
        face_details = db.getFaceDetailsWithImage(face_id)
        
        if not face_details:
            return jsonify({
                'success': False,
                'message': f'Yüz bulunamadı: {face_id}'
            }), 404
        
        # Sınırlayıcı kutu verileri
        facebox = face_details.get('facebox')
        
        if not facebox:
            return jsonify({
                'success': False,
                'message': 'Bu yüz için sınırlayıcı kutu verisi bulunmuyor'
            }), 404
        
        return jsonify({
            'success': True,
            'face_id': face_id,
            'facebox': facebox,
            'message': 'Sınırlayıcı kutu verileri başarıyla alındı'
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Hata: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'Sınırlayıcı kutu verileri alınırken hata oluştu: {str(e)}'
        }), 500

@api_bp.route('/face/<face_id>/draw_bbox', methods=['GET'])
@limiter.limit("30/minute")
def draw_face_bbox(face_id):
    """
    Yüz ID'sine göre sınırlayıcı kutu çizilmiş görüntüyü getir
    ---
    Bu endpoint, verilen yüz ID'sine ait görüntü üzerine sınırlayıcı kutu çizilmiş halini döndürür.
    """
    try:
        from lib.database_tools import DatabaseTools
        from lib.draw_utils import landmarks_rectangle, base64_to_bbox, base64_image_to_opencv, opencv_to_base64
        import requests
        import os
        
        db = DatabaseTools()
        
        # Yüz detaylarını al
        face_details = db.getFaceDetailsWithImage(face_id)
        
        if not face_details:
            return jsonify({
                'success': False,
                'message': f'Yüz bulunamadı: {face_id}'
            }), 404
        
        # Sınırlayıcı kutu verileri
        facebox = face_details.get('facebox')
        
        if not facebox:
            return jsonify({
                'success': False,
                'message': 'Bu yüz için sınırlayıcı kutu verisi bulunmuyor'
            }), 404
        
        # Görüntü URL'sini al
        image_url = face_details.get('full_image_url')
        
        if not image_url:
            return jsonify({
                'success': False,
                'message': 'Bu yüz için görüntü URL\'si bulunmuyor'
            }), 404
        
        try:
            # Görüntüyü indir
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            # OpenCV formatına dönüştür
            nparr = np.frombuffer(response.content, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return jsonify({
                    'success': False,
                    'message': 'Görüntü işlenemedi'
                }), 400
            
            # Sınırlayıcı kutuyu çiz
            img_with_bbox = landmarks_rectangle(img, facebox)
            
            # Base64 formatına dönüştür
            img_base64 = opencv_to_base64(img_with_bbox)
            
            return jsonify({
                'success': True,
                'face_id': face_id,
                'facebox': facebox,
                'image_data': img_base64,
                'message': 'Sınırlayıcı kutu çizilmiş görüntü başarıyla oluşturuldu'
            }), 200
            
        except requests.exceptions.RequestException as req_err:
            return jsonify({
                'success': False,
                'message': f'Görüntü indirme hatası: {str(req_err)}'
            }), 500
        
    except Exception as e:
        current_app.logger.error(f"Hata: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'Sınırlayıcı kutu çizilirken hata oluştu: {str(e)}'
        }), 500 