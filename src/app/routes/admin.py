#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, current_app
from app.routes.auth import admin_required # Oluşturduğumuz admin_required dekoratörünü import et
from app.controllers.user_controller import UserController # Kullanıcıları listelemek için
from app.forms import UserForm # Tanımladığımız formu import et
from app.models.user import User # User modelini import et
from wtforms.validators import DataRequired # <<< DataRequired import edildi
import datetime # Tarih işlemleri için

admin_bp = Blueprint('admin', __name__, url_prefix='/admin') # Tüm admin rotaları /admin altında olacak

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin paneli ana sayfası."""
    # Şimdilik basit bir karşılama mesajı veya genel istatistikler olabilir
    # Kontrol paneli (dashboard) zaten web.py altında olduğu için buna admin_home diyelim
    return render_template('admin/admin_home.html', title="Admin Paneli")

@admin_bp.route('/users')
@admin_required
def list_users():
    """Tüm kullanıcıları listeler."""
    success, users_data_raw = UserController.get_all_users()
    users_processed = []
    if success:
        # Veritabanından gelen DictRow listesini User nesnelerine çevir
        users_processed = [User.from_dict(u) for u in users_data_raw]
    else:
        flash("Kullanıcılar getirilirken bir hata oluştu.", "danger")
    return render_template('admin/users_list.html', users=users_processed, title="Kullanıcı Yönetimi")

@admin_bp.route('/user_subscriptions') # Rota adı güncellendi
@admin_required
def list_user_subscriptions(): # Fonksiyon adı güncellendi
    """Kullanıcıları aboneliklerinin kalan gün sayısına göre listeler."""
    success, users_data_raw = UserController.get_all_users()
    
    users_with_subscriptions = []
    if success:
        # Veritabanından gelen DictRow listesini User nesnelerine çevir
        users_objects = [User.from_dict(u) for u in users_data_raw]
        
        # Sadece aktif aboneliği olan veya geçmişte aboneliği olmuş kullanıcıları filtrele (isteğe bağlı)
        # users_with_subscriptions = [u for u in users_objects if u.subscription_start_date]
        users_with_subscriptions = users_objects # Şimdilik tüm kullanıcıları alalım, sıralama halledecek

        # Kalan gün sayısına göre sırala (en az kalan en üstte)
        # None değerleri en sona atmak için bir lambda hilesi:
        # (u.subscription_remaining_days is None, u.subscription_remaining_days)
        # Bu, None olanları (True, None) yapar, diğerlerini (False, gün_sayısı)
        # Python'da True, False'dan büyük olduğu için None'lar sona gider.
        users_with_subscriptions.sort(key=lambda u: (u.subscription_remaining_days is None, u.subscription_remaining_days))
    else:
        flash("Kullanıcı abonelik bilgileri getirilirken bir hata oluştu.", "danger")
        
    return render_template('admin/subscriptions_list.html', 
                           subscriptions=users_with_subscriptions, # Şablona 'subscriptions' yerine 'users' olarak da gönderilebilir
                           title="Kullanıcı Abonelikleri")

@admin_bp.route('/users/add', methods=['GET', 'POST'])
@admin_required
def add_user():
    """Yeni kullanıcı ekleme formu ve işlemi."""
    form = UserForm() # Formu başlat
    
    # Yeni kullanıcı eklerken parola zorunlu
    form.password.validators.insert(0, DataRequired(message="Yeni kullanıcı için parola zorunludur."))
    form.confirm_password.validators.insert(0, DataRequired(message="Parola doğrulaması zorunludur."))

    if form.validate_on_submit(): # Form gönderildi ve geçerli
        # Form verilerini al
        username = form.username.data
        email = form.email.data or None
        name = form.name.data or None
        password = form.password.data # Parola artık formdan geliyor
        is_active = form.is_active.data
        is_admin = form.is_admin.data
        is_owner = form.is_owner.data
        is_demo = form.is_demo.data
        demo_start = form.demo_start.data 
        demo_end = form.demo_end.data
        subscription_start_date = form.subscription_start_date.data
        subscription_end_date = form.subscription_end_date.data
        
        # UserController ile kullanıcıyı oluştur
        success, message_or_data = UserController.create_user(
            username=username, password=password, email=email, name=name, 
            is_active=is_active, is_admin=is_admin, is_owner=is_owner, is_demo=is_demo,
            demo_start=demo_start, demo_end=demo_end, 
            subscription_start_date=subscription_start_date, 
            subscription_end_date=subscription_end_date
        )

        if success:
            flash(f"Kullanıcı '{username}' başarıyla oluşturuldu.", 'success')
            return redirect(url_for('admin.list_users'))
        else:
            flash(f"Kullanıcı oluşturulamadı: {message_or_data}", 'danger')
            # Hata durumunda form tekrar render edilecek (validate_on_submit False döneceği için)

    # GET isteği veya form validasyonu başarısız ise formu göster
    return render_template('admin/user_form.html', 
                           form=form, # Formu şablona gönder
                           form_title="Yeni Kullanıcı Ekle", 
                           form_action_url=url_for('admin.add_user'),
                           submit_button_text="Kullanıcı Oluştur",
                           user=None # Yeni kullanıcı formu için user=None
                           )

# --- YENİ: Kullanıcı Düzenleme Rotası ---
@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Mevcut kullanıcıyı düzenleme formu ve işlemi."""
    user_data_raw = UserController.get_user_by_id(user_id)
    if not user_data_raw:
        flash("Kullanıcı bulunamadı.", "danger")
        return redirect(url_for('admin.list_users'))

    # Veritabanından gelen DictRow'u User model nesnesine çevir (formda objeyi kullanmak için)
    user_object = User.from_dict(user_data_raw)
    form = UserForm(obj=user_object) 

    if form.validate_on_submit():
        # Form verilerini al
        username = form.username.data
        email = form.email.data or None
        name = form.name.data or None
        password = form.password.data # Eğer yeni parola girildiyse alınır
        is_active = form.is_active.data
        is_admin = form.is_admin.data
        is_owner = form.is_owner.data
        is_demo = form.is_demo.data
        demo_start = form.demo_start.data
        demo_end = form.demo_end.data
        subscription_start_date = form.subscription_start_date.data
        subscription_end_date = form.subscription_end_date.data

        # UserController ile kullanıcıyı güncelle (yeni metod gerekecek)
        success, message = UserController.update_user(
            user_id=user_id,
            username=username,
            email=email,
            name=name,
            password=password if password else None, # Sadece yeni parola varsa gönder
            is_active=is_active,
            is_admin=is_admin,
            is_owner=is_owner,
            is_demo=is_demo,
            demo_start=demo_start,
            demo_end=demo_end,
            subscription_start_date=subscription_start_date,
            subscription_end_date=subscription_end_date
        )

        if success:
            flash(f"Kullanıcı '{username}' başarıyla güncellendi.", 'success')
            return redirect(url_for('admin.list_users'))
        else:
            flash(f"Kullanıcı güncellenemedi: {message}", 'danger')
            # Hata durumunda form tekrar render edilecek

    # GET veya validasyon hatası durumunda formu doldurulmuş haliyle göster
    return render_template('admin/user_form.html', 
                           form=form, 
                           form_title="Kullanıcıyı Düzenle", 
                           form_action_url=url_for('admin.edit_user', user_id=user_id),
                           submit_button_text="Değişiklikleri Kaydet",
                           user=user_object # Mevcut kullanıcı bilgilerini de gönderelim (şablonda gerekirse)
                           )
# --- Rota Bitti ---

# --- YENİ: Kullanıcı Silme Rotası ---
@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user_action(user_id):
    """Kullanıcıyı siler (POST isteği ile)."""
    # Kendini silme kontrolü
    if user_id == session.get('user_id'):
        flash("Kendinizi silemezsiniz.", "danger")
        return redirect(url_for('admin.list_users'))

    # Sahibi silme kontrolü (sadece başka bir sahip silebilir?)
    # user_to_delete = UserController.get_user_by_id(user_id)
    # if user_to_delete and user_to_delete.get('is_owner') and not session.get('is_owner'):
    #    flash("Sahip kullanıcıları sadece başka bir sahip silebilir.", "danger")
    #    return redirect(url_for('admin.list_users'))

    # CSRF token doğrulaması (Flask-WTF kullanılıyorsa otomatik yapılır,
    # manuel ise burada token kontrolü yapılmalı)
    # request.form.get('csrf_token') ...

    success, message = UserController.delete_user(user_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    
    return redirect(url_for('admin.list_users'))
# --- Rota Bitti ---

# --- YENİ: Kullanıcı Aktifleştirme/Dondurma Rotası ---
@admin_bp.route('/users/<int:user_id>/toggle_activation', methods=['POST'])
@admin_required
def toggle_user_activation_action(user_id):
    """Kullanıcının aktiflik durumunu değiştirir."""
    # Önce kullanıcının mevcut durumunu al
    user = UserController.get_user_by_id(user_id)
    if not user:
        flash("İşlem yapılacak kullanıcı bulunamadı.", "danger")
        return redirect(url_for('admin.list_users'))

    new_status = not user['is_active'] # Mevcut durumun tersini yap

    # Kendini devre dışı bırakma kontrolü
    if user_id == session.get('user_id') and not new_status:
        flash("Kendinizi devre dışı bırakamazsınız.", "danger")
        return redirect(url_for('admin.list_users'))

    # CSRF token doğrulaması...

    success, message = UserController.set_user_activation(user_id, new_status)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
        
    return redirect(url_for('admin.list_users'))
# --- Rota Bitti --- 