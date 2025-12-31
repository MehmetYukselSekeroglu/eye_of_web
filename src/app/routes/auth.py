#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Blueprint, request, jsonify, session, redirect, url_for, render_template, flash
from app.controllers.user_controller import UserController
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app import limiter
from functools import wraps

auth_bp = Blueprint('auth', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Bu sayfaya erişmek için lütfen giriş yapın.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if not session.get('is_admin'):
            flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
            return redirect(url_for('web.index'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10/minute")
def login():
    """Kullanıcı giriş işlemi"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Yönlendirme için 'next' parametresini al
        next_url = request.args.get('next')

        if not username or not password:
            flash('Kullanıcı adı ve şifre gerekli', 'danger')
            return render_template('auth/login.html', next=next_url)
        
        success, result = UserController.authenticate(username, password)
        
        if not success:
            flash(f'Giriş başarısız: {result}', 'danger')
            return render_template('auth/login.html', next=next_url)
        
        # YENİ: Başarılı kimlik doğrulamasından sonra eski oturumu tamamen temizle
        # Bu, session fixation saldırılarını önlemeye yardımcı olur ve
        # eski oturumla ilişkili CSRF token'ını geçersiz kılar.
        session.clear()
        
        # Kullanıcı doğrulandı, YENİ oturum bilgilerini ayarla
        user_info = result 
        session['logged_in'] = True
        session['user_id'] = user_info['id'] 
        session['username'] = user_info['username'] 
        session['is_admin'] = user_info.get('is_admin', False) 
        session['is_owner'] = user_info.get('is_owner', False) 
        
        # Oturum yeniden oluşturulduktan sonra, Flask-WTF genellikle yeni bir CSRF token'ı
        # bir sonraki yanıtla (template render edildiğinde) ilişkilendirir.
        # Gerekirse, `flask_wtf.csrf.generate_csrf()` çağrılabilir ancak bu genellikle template tarafında halledilir.

        flash('Giriş başarılı!', 'success')
        
        # Kaydedilmiş 'next' URL varsa oraya, yoksa ana sayfaya yönlendir
        if next_url:
            return redirect(next_url)
        return redirect(url_for('web.index'))
    
    # GET isteği için 'next' parametresini template'e ilet
    next_url = request.args.get('next')
    return render_template('auth/login.html', next=next_url)

@auth_bp.route('/logout')
def logout():
    """Kullanıcı çıkış işlemi"""
    session.clear()
    flash('Başarıyla çıkış yapıldı', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/api/login', methods=['POST'])
@limiter.limit("5/minute")
def api_login():
    """API üzerinden giriş (JWT token döndürür)"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'message': 'Geçersiz istek formatı'
        }), 400
    
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({
            'success': False,
            'message': 'Kullanıcı adı ve şifre gerekli'
        }), 400
    
    success, result = UserController.authenticate(username, password)
    
    if not success:
        return jsonify({
            'success': False,
            'message': f'Giriş başarısız: {result}'
        }), 401
    
    user_info = result # result artık bir sözlük
    # JWT token oluştururken user_info (sözlük) kullanılıyor, UserController.generate_jwt_token zaten sözlük bekliyor
    access_token = UserController.generate_jwt_token(user_info)
    
    # user.to_dict() yerine user_info içindeki to_dict lambda'sını kullan
    user_display_info = user_info['to_dict']() if 'to_dict' in user_info and callable(user_info['to_dict']) else user_info
    
    return jsonify({
        'success': True,
        'message': 'Giriş başarılı',
        'access_token': access_token,
        'user': user_display_info # user.to_dict() yerine güncellenmiş user_info
    }), 200

@auth_bp.route('/api/check-token')
@jwt_required()
def check_token():
    """JWT token geçerliliğini kontrol eder"""
    current_user_id = get_jwt_identity()
    
    return jsonify({
        'success': True,
        'message': 'Token geçerli',
        'user_id': current_user_id
    }), 200

def is_logged_in():
    """Kullanıcının oturum açmış olup olmadığını kontrol eder"""
    return session.get('logged_in', False) 