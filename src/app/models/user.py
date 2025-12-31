#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
from app import bcrypt
from flask_login import UserMixin
import secrets
import uuid

class User(UserMixin):
    """Kullanıcı modeli"""
    
    def __init__(self, id=None, username=None, password=None, email=None, is_admin=False, 
                 is_active=True, api_key=None, created_at=None, last_login=None,
                 name=None, is_owner=False, is_demo=False, demo_start=None, demo_end=None,
                 subscription_start_date=None, subscription_end_date=None):
        self.id = id or str(uuid.uuid4())
        self.username = username
        self.password_hash = self._hash_password(password) if password else None
        self.email = email
        self.name = name
        self.is_admin = is_admin
        self._is_active = is_active
        self.is_owner = is_owner
        self.is_demo = is_demo
        self.api_key = api_key or self._generate_api_key()

        if isinstance(created_at, str):
            self.created_at = datetime.datetime.fromisoformat(created_at)
        elif created_at is None:
            self.created_at = datetime.datetime.utcnow()
        else:
            self.created_at = created_at
            
        if isinstance(last_login, str):
            self.last_login = datetime.datetime.fromisoformat(last_login)
        else:
            self.last_login = last_login

        if isinstance(demo_start, str):
            self.demo_start = datetime.datetime.fromisoformat(demo_start)
        else:
            self.demo_start = demo_start

        if isinstance(demo_end, str):
            self.demo_end = datetime.datetime.fromisoformat(demo_end)
        else:
            self.demo_end = demo_end

        if isinstance(subscription_start_date, str):
            self.subscription_start_date = datetime.datetime.fromisoformat(subscription_start_date)
        else:
            self.subscription_start_date = subscription_start_date

        if isinstance(subscription_end_date, str):
            self.subscription_end_date = datetime.datetime.fromisoformat(subscription_end_date)
        else:
            self.subscription_end_date = subscription_end_date
    
    @property
    def is_active(self):
        """Kullanıcının aktif olup olmadığını döndürür"""
        return self._is_active
    
    @is_active.setter
    def is_active(self, value):
        """Kullanıcının aktif durumunu ayarlar"""
        self._is_active = value
    
    def _hash_password(self, password):
        """Parolayı hashler"""
        return bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        """Parolayı kontrol eder"""
        if not self.password_hash:
            return False
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def _generate_api_key(self):
        """Benzersiz bir API anahtarı oluşturur"""
        return secrets.token_urlsafe(32)
    
    def update_last_login(self):
        """Son giriş zamanını günceller"""
        self.last_login = datetime.datetime.utcnow()
    
    def to_dict(self):
        """Kullanıcı bilgilerini sözlük olarak döndürür"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'name': self.name,
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'is_owner': self.is_owner,
            'is_demo': self.is_demo,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'demo_start': self.demo_start.isoformat() if self.demo_start else None,
            'demo_end': self.demo_end.isoformat() if self.demo_end else None,
            'subscription_start_date': self.subscription_start_date.isoformat() if self.subscription_start_date else None,
            'subscription_end_date': self.subscription_end_date.isoformat() if self.subscription_end_date else None,
            'is_subscription_active': self.is_subscription_active,
            'subscription_remaining_days': self.subscription_remaining_days
        }
    
    @classmethod
    def from_dict(cls, data):
        """Sözlük verilerinden kullanıcı nesnesi oluşturur"""
        created_at_data = data.get('created_at', data.get('create_date'))

        return cls(
            id=data.get('id'),
            username=data.get('username'),
            password=data.get('password'),
            email=data.get('email'),
            name=data.get('name'),
            is_admin=data.get('is_admin', False),
            is_active=data.get('is_active', True),
            is_owner=data.get('is_owner', False),
            is_demo=data.get('is_demo', False),
            api_key=data.get('api_key'),
            created_at=created_at_data,
            last_login=data.get('last_login'),
            demo_start=data.get('demo_start'),
            demo_end=data.get('demo_end'),
            subscription_start_date=data.get('subscription_start_date'),
            subscription_end_date=data.get('subscription_end_date')
        )
    
    @staticmethod
    def validate_api_key(api_key):
        """API anahtarını doğrular"""
        # Bu işlev veritabanından API anahtarı kontrolü yapacak
        # Şimdilik yapay olarak True dönelim
        from app import db_tools
        # Gerçek uygulamada veritabanından API anahtarı kontrolü yapılacak
        return True 

    @property
    def is_subscription_active(self):
        """Kullanıcının aboneliğinin aktif olup olmadığını kontrol eder."""
        if not self.subscription_start_date or not self.subscription_end_date:
            return False
        
        now = datetime.datetime.now(self.subscription_start_date.tzinfo)

        if self.subscription_start_date > now:
            return False
            
        if self.subscription_end_date < now:
            return False
            
        return True

    @property
    def subscription_remaining_days(self):
        """Aboneliğin bitmesine kalan gün sayısı."""
        if not self.subscription_end_date:
            return None

        now = datetime.datetime.now(self.subscription_end_date.tzinfo)
        
        if self.subscription_end_date < now:
            return 0
            
        remaining = self.subscription_end_date - now
        return remaining.days 