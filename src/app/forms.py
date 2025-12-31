#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, EmailField, DateTimeLocalField
from wtforms.validators import DataRequired, Length, Email, EqualTo, Optional, ValidationError
import datetime

# Kullanıcı Formu
class UserForm(FlaskForm):
    username = StringField('Kullanıcı Adı', validators=[DataRequired(message="Kullanıcı adı zorunludur."), Length(min=3, max=80)])
    email = EmailField('E-posta', validators=[Optional(), Email(message="Geçerli bir e-posta adresi girin."), Length(max=120)])
    name = StringField('Ad Soyad', validators=[Optional(), Length(max=100)])
    # Yeni kullanıcı için parola zorunlu, düzenleme için opsiyonel
    password = PasswordField('Parola', validators=[Optional(), Length(min=6, message="Parola en az 6 karakter olmalı.")])
    confirm_password = PasswordField('Parola Doğrula', validators=[Optional(), EqualTo('password', message='Parolalar eşleşmiyor.')])
    
    is_active = BooleanField('Hesap Aktif', default=True)
    is_admin = BooleanField('Admin Yetkisi')
    is_owner = BooleanField('Sahip Yetkisi')
    is_demo = BooleanField('Demo Kullanıcısı')
    
    demo_start = DateTimeLocalField('Demo Başlangıç', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    demo_end = DateTimeLocalField('Demo Bitiş', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    subscription_start_date = DateTimeLocalField('Abonelik Başlangıç', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    subscription_end_date = DateTimeLocalField('Abonelik Bitiş', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    
    submit = SubmitField('Kaydet')

    # --- Özel Doğrulama: Demo ve Abonelik Çakışması --- 
    def validate(self, extra_validators=None):
        # Standart validasyonları çalıştır
        initial_validation = super(UserForm, self).validate(extra_validators)
        if not initial_validation:
            return False

        # Çakışma kontrolü
        if self.is_demo.data and (self.subscription_start_date.data or self.subscription_end_date.data):
            self.is_demo.errors.append("Demo kullanıcıları için abonelik tarihleri belirtilemez.")
            # Tarih alanlarına da hata ekleyebiliriz
            # self.subscription_start_date.errors.append("Demo seçiliyken boş olmalı.")
            # self.subscription_end_date.errors.append("Demo seçiliyken boş olmalı.")
            return False
            
        if (self.subscription_start_date.data or self.subscription_end_date.data) and self.is_demo.data:
              # Bu kontrol yukarıdakiyle aynı, ama explicit olması iyi
              pass # Zaten yukarıda kontrol edildi

        # Tarih sıralama kontrolü
        if self.demo_start.data and self.demo_end.data and self.demo_end.data <= self.demo_start.data:
            self.demo_end.errors.append("Demo bitiş tarihi, başlangıç tarihinden sonra olmalıdır.")
            return False
            
        if self.subscription_start_date.data and self.subscription_end_date.data and self.subscription_end_date.data <= self.subscription_start_date.data:
            self.subscription_end_date.errors.append("Abonelik bitiş tarihi, başlangıç tarihinden sonra olmalıdır.")
            return False

        return True

    # Düzenleme sırasında parola kontrolü için (opsiyonel)
    # def validate_password(self, field):
    #     if self.id.data and not field.data:
    #         # Düzenleme modunda ve parola boşsa validasyonu atla
    #         pass
    #     elif not self.id.data and not field.data:
    #          raise ValidationError('Yeni kullanıcı için parola zorunludur.')

# --- Yeni: Abonelik Formu ---
class SubscriptionForm(FlaskForm):
    user_id = StringField('Kullanıcı ID', validators=[DataRequired(message="Kullanıcı ID zorunludur.")]) 
    # Gelecekte bu alan, kullanıcıları listeleyen bir SelectField olabilir.
    plan_name = StringField('Plan Adı', validators=[DataRequired(message="Plan adı zorunludur."), Length(min=3, max=100)])
    start_date = DateTimeLocalField('Başlangıç Tarihi', format='%Y-%m-%dT%H:%M', validators=[DataRequired(message="Başlangıç tarihi zorunludur.")])
    end_date = DateTimeLocalField('Bitiş Tarihi', format='%Y-%m-%dT%H:%M', validators=[DataRequired(message="Bitiş tarihi zorunludur.")])
    is_active = BooleanField('Aktif Abonelik', default=True)
    submit = SubmitField('Abonelik Ekle')

    def validate_end_date(self, field):
        if self.start_date.data and field.data:
            if field.data <= self.start_date.data:
                raise ValidationError("Bitiş tarihi, başlangıç tarihinden sonra olmalıdır.")

        