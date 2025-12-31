#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app import bcrypt # db_tools kaldırıldı, bcrypt burada kalsın
# User modeli artık doğrudan kullanılmayacak, veritabanından dict olarak alacağız.
# from app.models.user import User 
from app.models.user import User # User modelini import et (authenticate için gerekli)
from app.config.config import get_config # Config hala JWT için gerekebilir ama login için değil
import jwt
import datetime
from flask import current_app, g # g yi import et
import psycopg2.extras

class UserController:
    """Kullanıcı işlemlerini yöneten controller"""
    
    @staticmethod
    def create_user(username, password, email=None, name=None, is_active=True, is_admin=False, is_owner=False, is_demo=False, demo_start=None, demo_end=None, subscription_start_date=None, subscription_end_date=None):
        """Yeni kullanıcı oluşturur ve veritabanına kaydeder."""
        if UserController.get_user_by_username(username):
            return False, "Bu kullanıcı adı zaten kullanılıyor"
        
        if email and UserController.get_user_by_email(email): # E-posta kontrolü (eğer get_user_by_email varsa)
             return False, "Bu e-posta adresi zaten kullanılıyor"

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        try:
            conn = g.db_tools.connect()
            cursor = conn.cursor()
            insert_query = """
            INSERT INTO users (username, password, email, name, is_active, is_admin, is_owner, is_demo, 
                               demo_start, demo_end, subscription_start_date, subscription_end_date, create_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
            """
            cursor.execute(insert_query, (
                username, hashed_password, email, name, is_active, is_admin, is_owner, is_demo,
                demo_start, demo_end, subscription_start_date, subscription_end_date, datetime.datetime.now(datetime.timezone.utc)
            ))
            user_id = cursor.fetchone()[0]
            conn.commit()
            
            # Yeni oluşturulan kullanıcı verisini döndür (veya sadece ID)
            new_user_data = {
                'id': user_id, 'username': username, 'email': email, 'name': name, 
                'is_active': is_active, 'is_admin': is_admin, 'is_owner': is_owner, 'is_demo': is_demo
            }
            return True, new_user_data
        except Exception as e:
            if conn:
                try: conn.rollback()
                except: pass
            current_app.logger.error(f"Kullanıcı oluşturma hatası: {e}")
            return False, f"Kullanıcı oluşturulurken bir hata oluştu: {str(e)}"
        finally:
            if conn:
                g.db_tools.releaseConnection(conn, cursor if 'cursor' in locals() else None)

    @staticmethod
    def authenticate(username, password):
        """Kullanıcı kimlik doğrulama işlemi (veritabanı üzerinden)"""
        user_data_raw = UserController.get_user_by_username(username) # Bu metod tüm gerekli alanları getirmeli
        
        if not user_data_raw:
            return False, "Geçersiz kullanıcı adı veya şifre"
        
        if not bcrypt.check_password_hash(user_data_raw['password'], password):
            return False, "Geçersiz kullanıcı adı veya şifre"
        
        if not user_data_raw['is_active']:
            return False, "Kullanıcı hesabı devre dışı"

        # User nesnesi oluşturarak abonelik durumunu kontrol et
        user_object = User.from_dict(user_data_raw)

        # Demo kullanıcılar hariç, abonelik kontrolü yap
        # Admin ve Owner kullanıcılar bu kontrolden muaf olmalı.
        if not user_object.is_demo and not user_object.is_admin and not user_object.is_owner:
            if not user_object.is_subscription_active:
                return False, "Aboneliğiniz aktif değil veya süresi dolmuş."
        
        # Son giriş zamanını güncelle
        try:
            conn = g.db_tools.connect()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET last_login = %s WHERE id = %s", 
                           (datetime.datetime.now(datetime.timezone.utc), user_data_raw['id']))
            conn.commit()
        except Exception as e:
            # Logla ama girişi engelleme
            current_app.logger.error(f"Son giriş zamanı güncellenirken hata (kullanıcı: {username}): {e}")
            if conn:
                try: conn.rollback()
                except: pass
        finally:
            if conn: # conn'in tanımlı olup olmadığını kontrol et
                g.db_tools.releaseConnection(conn, cursor if 'cursor' in locals() else None)
        
        # Oturum için gerekli kullanıcı bilgilerini içeren bir dict döndür
        # Bu, auth.py'nin session['username'] = user.username gibi erişimlerini karşılar
        # Not: 'password' alanını döndürmüyoruz.
        return True, {
            'id': user_data_raw['id'],
            'username': user_data_raw['username'],
            'name': user_data_raw.get('name'), # .get() ile None durumunu yönet
            'email': user_data_raw.get('email'),
            'is_admin': user_data_raw['is_admin'],
            'is_owner': user_data_raw.get('is_owner', False), # Sahip değilse False varsay
            'is_active': user_data_raw['is_active'],
            # API login için to_dict() metodunu taklit edebiliriz
            'to_dict': lambda: {
                'id': user_data_raw['id'], 'username': user_data_raw['username'], 'name': user_data_raw.get('name'),
                'email': user_data_raw.get('email'), 'is_admin': user_data_raw['is_admin'], 
                'is_owner': user_data_raw.get('is_owner', False)
            }
        }

    @staticmethod
    def get_user_by_username(username):
        """Kullanıcı adına göre kullanıcı bilgilerini veritabanından getirir."""
        conn = None
        cursor = None
        try:
            conn = g.db_tools.connect()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            # Abonelik kontrolü için gerekli tüm alanları seçtiğimizden emin olalım
            cursor.execute("""SELECT id, username, password, name, email, is_active, is_admin, is_owner, is_demo,
                                   demo_start, demo_end, subscription_start_date, subscription_end_date,
                                   create_date, last_login 
                               FROM users WHERE username = %s""", (username,))
            user_row = cursor.fetchone()
            return user_row
        except Exception as e:
            current_app.logger.error(f"Kullanıcı ({username}) getirilirken hata: {e}")
            return None
        finally:
            if conn:
                g.db_tools.releaseConnection(conn, cursor)
    
    @staticmethod
    def get_user_by_id(user_id):
        """Kullanıcı ID'sine göre kullanıcı bilgilerini veritabanından getirir."""
        conn = None
        cursor = None
        try:
            conn = g.db_tools.connect()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("""SELECT id, username, name, email, is_active, is_admin, is_owner, is_demo,
                                   demo_start, demo_end, subscription_start_date, subscription_end_date,
                                   create_date, last_login 
                               FROM users WHERE id = %s""", (user_id,))
            user_row = cursor.fetchone()
            return user_row
        except Exception as e:
            current_app.logger.error(f"Kullanıcı ID ({user_id}) ile getirilirken hata: {e}")
            return None
        finally:
            if conn:
                g.db_tools.releaseConnection(conn, cursor)

    @staticmethod
    def get_user_by_email(email): # E-posta ile kullanıcı bulma (opsiyonel, create_user için)
        """E-posta adresine göre kullanıcı bilgilerini getirir."""
        conn = None
        cursor = None
        try:
            conn = g.db_tools.connect()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            return cursor.fetchone()
        except Exception as e:
            current_app.logger.error(f"Kullanıcı e-posta ({email}) ile getirilirken hata: {e}")
            return None
        finally:
            if conn:
                g.db_tools.releaseConnection(conn, cursor)
    
    # JWT token metodları aynı kalabilir, ancak user objesi yerine user_dict alacak şekilde düzenlenmeli
    # Şimdilik olduğu gibi bırakıyorum, API login kısmı test edilirken gerekirse düzenlenir.
    @staticmethod
    def generate_jwt_token(user_dict): # user objesi yerine dict alır
        """JWT token oluşturur"""
        expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        
        payload = {
            'sub': user_dict['id'], # Artık user_dict['id']
            'username': user_dict['username'], # Artık user_dict['username']
            'is_admin': user_dict.get('is_admin', False), # .get() ile güvenli erişim
            'exp': expiration
        }
        
        token = jwt.encode(
            payload,
            current_app.config['JWT_SECRET_KEY'],
            algorithm='HS256'
        )
        return token
    
    @staticmethod
    def verify_jwt_token(token):
        """JWT token doğrular"""
        try:
            payload = jwt.decode(
                token,
                current_app.config['JWT_SECRET_KEY'],
                algorithms=['HS256']
            )
            user_id = payload['sub']
            return True, user_id
        except jwt.ExpiredSignatureError:
            return False, "Token süresi doldu"
        except jwt.InvalidTokenError:
            return False, "Geçersiz token"

    @staticmethod
    def get_all_users():
        """Tüm kullanıcıları (parolaları hariç) veritabanından getirir."""
        conn = None
        cursor = None
        try:
            conn = g.db_tools.connect()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) 
            cursor.execute("""
                SELECT id, username, email, name, is_active, is_admin, is_owner, is_demo, 
                       create_date, last_login, demo_start, demo_end, 
                       subscription_start_date, subscription_end_date 
                FROM users ORDER BY id ASC
            """)
            users = cursor.fetchall()
            return True, users 
        except Exception as e:
            current_app.logger.error(f"Tüm kullanıcılar getirilirken hata: {e}")
            return False, []
        finally:
            if conn:
                g.db_tools.releaseConnection(conn, cursor)

    @staticmethod
    def update_user(user_id, username, email, name, password, is_active, is_admin, is_owner, is_demo, demo_start, demo_end, subscription_start_date, subscription_end_date):
        """Varolan bir kullanıcıyı günceller."""
        # Kullanıcı adının başkası tarafından kullanılıp kullanılmadığını kontrol et
        existing_user = UserController.get_user_by_username(username)
        if existing_user and existing_user['id'] != user_id:
            return False, "Bu kullanıcı adı zaten başka bir kullanıcı tarafından kullanılıyor."
        
        # E-postanın başkası tarafından kullanılıp kullanılmadığını kontrol et (eğer email varsa)
        if email:
            existing_email_user = UserController.get_user_by_email(email)
            if existing_email_user and existing_email_user['id'] != user_id:
                 return False, "Bu e-posta adresi zaten başka bir kullanıcı tarafından kullanılıyor."

        # Güncellenecek alanları ve değerlerini dinamik olarak oluştur
        update_fields = []
        update_values = []
        
        # Alanları ekle
        update_fields.append("username = %s")
        update_values.append(username)
        update_fields.append("email = %s")
        update_values.append(email)
        update_fields.append("name = %s")
        update_values.append(name)
        update_fields.append("is_active = %s")
        update_values.append(is_active)
        update_fields.append("is_admin = %s")
        update_values.append(is_admin)
        update_fields.append("is_owner = %s")
        update_values.append(is_owner)
        update_fields.append("is_demo = %s")
        update_values.append(is_demo)
        update_fields.append("demo_start = %s")
        update_values.append(demo_start)
        update_fields.append("demo_end = %s")
        update_values.append(demo_end)
        update_fields.append("subscription_start_date = %s")
        update_values.append(subscription_start_date)
        update_fields.append("subscription_end_date = %s")
        update_values.append(subscription_end_date)

        if password: # Eğer yeni bir parola girilmişse hash'le ve güncelle
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            update_fields.append("password = %s")
            update_values.append(hashed_password)
        
        update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
        update_values.append(user_id)
        
        conn = None
        try:
            conn = g.db_tools.connect()
            cursor = conn.cursor()
            cursor.execute(update_query, tuple(update_values))
            conn.commit()
            return True, "Kullanıcı başarıyla güncellendi."
        except Exception as e:
            if conn:
                try: conn.rollback()
                except: pass
            current_app.logger.error(f"Kullanıcı ({user_id}) güncellenirken hata: {e}")
            return False, f"Kullanıcı güncellenirken bir hata oluştu: {str(e)}"
        finally:
            if conn:
                g.db_tools.releaseConnection(conn, cursor if 'cursor' in locals() else None)

    # --- YENİ METOD: Kullanıcı Silme ---
    @staticmethod
    def delete_user(user_id):
        """Verilen ID'ye sahip kullanıcıyı veritabanından siler."""
        conn = None
        cursor = None
        try:
            # Önce kullanıcı var mı kontrol et (opsiyonel ama iyi pratik)
            user_to_delete = UserController.get_user_by_id(user_id)
            if not user_to_delete:
                return False, "Silinecek kullanıcı bulunamadı."
            
            # Kendini veya owner'ı silme kontrolü (isteğe bağlı, route tarafında yapılabilir)
            # if user_id == session.get('user_id'): return False, "Kendinizi silemezsiniz."
            # if user_to_delete.get('is_owner'): return False, "Sahip kullanıcı silinemez."

            conn = g.db_tools.connect()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
            
            if cursor.rowcount == 0:
                # Bu durum yukarıdaki kontrol nedeniyle pek olası değil ama yine de ekleyelim
                return False, "Kullanıcı silinemedi (belki zaten silinmişti?)."
                
            return True, "Kullanıcı başarıyla silindi."
        except Exception as e:
            if conn:
                try: conn.rollback()
                except: pass
            current_app.logger.error(f"Kullanıcı ({user_id}) silme hatası: {e}")
            # Detaylı hata mesajı döndürmek yerine genel bir mesaj verilebilir
            # return False, f"Kullanıcı silinirken bir veritabanı hatası oluştu: {str(e)}"
            return False, "Kullanıcı silinirken bir veritabanı hatası oluştu."
        finally:
            if conn:
                g.db_tools.releaseConnection(conn, cursor)
    # --- Metod Bitti --- 

    # --- YENİ METOD: Kullanıcı Aktiflik Durumunu Ayarlama ---
    @staticmethod
    def set_user_activation(user_id, is_active_status: bool):
        """Verilen kullanıcının is_active durumunu günceller."""
        conn = None
        cursor = None
        try:
            # Kendini deaktive etme kontrolü (route tarafında yapılabilir)
            # if user_id == session.get('user_id') and not is_active_status:
            #    return False, "Kendinizi devre dışı bırakamazsınız."

            conn = g.db_tools.connect()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_active = %s WHERE id = %s", (is_active_status, user_id))
            conn.commit()
            
            if cursor.rowcount == 0:
                return False, "Kullanıcı bulunamadı veya durum zaten aynıydı."
            
            action = "aktifleştirildi" if is_active_status else "donduruldu"
            return True, f"Kullanıcı başarıyla {action}."
        except Exception as e:
            if conn:
                try: conn.rollback()
                except: pass
            current_app.logger.error(f"Kullanıcı ({user_id}) aktiflik durumu ayarlanırken hata: {e}")
            return False, "Kullanıcı durumu güncellenirken bir veritabanı hatası oluştu."
        finally:
            if conn:
                g.db_tools.releaseConnection(conn, cursor)
    # --- Metod Bitti --- 