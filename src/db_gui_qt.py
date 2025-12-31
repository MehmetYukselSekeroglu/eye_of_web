#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import cv2
import numpy as np
import hashlib
import base64
import psycopg2
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QLabel, QLineEdit, QPushButton, QRadioButton, QCheckBox,
                           QFileDialog, QMessageBox, QListWidget, QGroupBox, QFormLayout,
                           QButtonGroup, QScrollArea, QSizePolicy)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, pyqtSlot
from lib.init_insightface import initilate_insightface
from lib.load_config import load_config_from_file

class DatabaseUploaderGUI(QMainWindow):
    """Yüz Veritabanı Yükleme Aracı GUI - Qt versiyonu"""
    
    def __init__(self):
        super().__init__()
        
        # Pencere başlığı ve boyutu
        self.setWindowTitle("EyeOfWeb - Veritabanı Yükleme Aracı (Qt)")
        self.setGeometry(100, 100, 1000, 800)
        
        # Yapılandırma ve InsightFace yükleme
        self.config = None
        self.face_analyzer = None
        self.load_config_and_analyzer()
        
        # Veritabanı bağlantısını oluştur
        self.db_conn = None
        self.connect_to_database()
        
        # Görüntü dosyası ve yüz verisi 
        self.image_path = None
        self.image_data = None
        self.image_hash = None
        self.detected_faces = []
        self.selected_face_idx = -1  # Seçili yüz indeksi
        
        # UI bileşenlerini oluştur
        self._create_ui()
        
        # UI durumunu güncelle
        self.update_ui_state()
        
    def load_config_and_analyzer(self):
        """Yapılandırma ve InsightFace yükle"""
        try:
            # Yapılandırmayı yükle
            config_data = load_config_from_file()
            if not config_data[0]:
                QMessageBox.critical(self, "Hata", f"Yapılandırma yüklenemedi: {config_data[1]}")
                sys.exit(1)
            
            self.config = config_data[1]
            
            # InsightFace modeli yükle
            self.face_analyzer = initilate_insightface(config_data)
            if self.face_analyzer is None:
                QMessageBox.critical(self, "Hata", "InsightFace modeli yüklenemedi!")
                sys.exit(1)
                
            print("InsightFace modeli başarıyla yüklendi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yapılandırma ve model yükleme hatası: {str(e)}")
            sys.exit(1)
            
    def connect_to_database(self):
        """Veritabanına bağlan"""
        try:
            if not self.config or "database_config" not in self.config:
                QMessageBox.critical(self, "Hata", "Veritabanı yapılandırması bulunamadı!")
                return
                
            db_config = self.config["database_config"]
            self.db_conn = psycopg2.connect(
                host=db_config["host"],
                port=db_config["port"],
                database=db_config["database"],
                user=db_config["user"],
                password=db_config["password"]
            )
            
            print("Veritabanına başarıyla bağlandı.")
        except Exception as e:
            QMessageBox.critical(self, "Veritabanı Hatası", f"Veritabanına bağlanılamadı: {str(e)}")
            
    def _create_ui(self):
        """Ana UI oluştur"""
        # Ana widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Ana layout
        main_layout = QHBoxLayout(central_widget)
        
        # Sol panel (resim ve yüz seçim)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Sağ panel (form ve gönderim)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Panelleri ana layout'a ekle
        main_layout.addWidget(left_panel, 3)  # Solda daha geniş
        main_layout.addWidget(right_panel, 2)
        
        # ----- SOL PANEL -----
        # Resim seçme butonu
        self.browse_button = QPushButton("Resim Seç")
        self.browse_button.clicked.connect(self.browse_image)
        left_layout.addWidget(self.browse_button)
        
        # Görsel gösterimi için grup kutusu
        image_group = QGroupBox("Görüntü")
        image_layout = QVBoxLayout(image_group)
        
        # Scroll alan içinde resim etiketi
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 300)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        scroll_area.setWidget(self.image_label)
        image_layout.addWidget(scroll_area)
        
        left_layout.addWidget(image_group)
        
        # Tespit edilen yüzler listesi
        faces_group = QGroupBox("Tespit Edilen Yüzler")
        faces_layout = QVBoxLayout(faces_group)
        
        self.faces_list = QListWidget()
        self.faces_list.currentRowChanged.connect(self.on_face_select)
        faces_layout.addWidget(self.faces_list)
        
        left_layout.addWidget(faces_group)
        
        # ----- SAĞ PANEL -----
        # Veritabanı seçim grubu
        db_group = QGroupBox("Veritabanı")
        db_layout = QVBoxLayout(db_group)
        
        self.db_group = QButtonGroup(self)
        
        # Veritabanı radio butonları
        self.egm_radio = QRadioButton("EGM Arananlar")
        self.whitelist_radio = QRadioButton("Whitelist")
        self.custom_radio = QRadioButton("Custom Face Storage")
        self.external_radio = QRadioButton("External Face Storage")
        
        self.custom_radio.setChecked(True)  # Varsayılan seçim
        
        self.db_group.addButton(self.egm_radio, 1)
        self.db_group.addButton(self.whitelist_radio, 2)
        self.db_group.addButton(self.custom_radio, 3)
        self.db_group.addButton(self.external_radio, 4)
        
        self.db_group.buttonClicked.connect(self.update_form_fields)
        
        db_layout.addWidget(self.egm_radio)
        db_layout.addWidget(self.whitelist_radio)
        db_layout.addWidget(self.custom_radio)
        db_layout.addWidget(self.external_radio)
        
        right_layout.addWidget(db_group)
        
        # Form grubu
        form_group = QGroupBox("Yüz Bilgileri")
        self.form_layout = QFormLayout(form_group)
        
        # Temel form alanları
        self.face_name_edit = QLineEdit()
        self.face_desc_edit = QLineEdit()
        
        self.form_layout.addRow("Yüz Adı:", self.face_name_edit)
        self.form_layout.addRow("Açıklama:", self.face_desc_edit)
        
        # EGM için özel alanlar
        self.organizer_edit = QLineEdit()
        self.level_edit = QLineEdit()
        self.birth_edit = QLineEdit()
        
        # ExternalFaceStorage için özel alan
        self.alarm_check = QCheckBox()
        
        right_layout.addWidget(form_group)
        
        # Yüz tespit bilgileri grup kutusu
        info_group = QGroupBox("Tespit Bilgileri")
        info_layout = QVBoxLayout(info_group)
        
        self.score_label = QLabel("Tespit Skoru: -")
        self.gender_label = QLabel("Cinsiyet: -")
        self.age_label = QLabel("Yaş: -")
        
        info_layout.addWidget(self.score_label)
        info_layout.addWidget(self.gender_label)
        info_layout.addWidget(self.age_label)
        
        right_layout.addWidget(info_group)
        
        # Kaydet butonu
        self.save_button = QPushButton("Veritabanına Kaydet")
        self.save_button.clicked.connect(self.save_to_database)
        right_layout.addWidget(self.save_button)
        
        # Formu başlangıçta güncelle
        self.update_form_fields()
        
    def browse_image(self):
        """Görüntü dosyası seç"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Resim Dosyası Seç", 
            "", 
            "Resim Dosyaları (*.jpg *.jpeg *.png *.bmp *.JPG *.JPEG *.PNG *.BMP)"
        )
        
        if not file_path:
            return
            
        self.image_path = file_path
        
        try:
            # Resmi oku
            with open(file_path, 'rb') as f:
                image_bytes = f.read()
                
            # Hash hesapla
            self.image_hash = hashlib.sha1(image_bytes).hexdigest()
            
            # OpenCV formatına dönüştür
            nparr = np.frombuffer(image_bytes, np.uint8)
            self.image_data = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Resmi ekranda göster
            self.display_image()
            
            # Yüzleri tespit et
            self.detect_faces()
            
            # UI durumunu güncelle
            self.update_ui_state()
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Resim yüklenirken hata oluştu: {str(e)}")
            
    def display_image(self):
        """Görüntüyü UI'da göster"""
        if self.image_data is None:
            return
            
        # Görüntüyü BGR'den RGB'ye dönüştür
        image_rgb = cv2.cvtColor(self.image_data, cv2.COLOR_BGR2RGB)
        
        # QImage'e dönüştür
        h, w, ch = image_rgb.shape
        bytes_per_line = ch * w
        q_image = QImage(image_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # QPixmap'e dönüştür ve görüntü etiketine ayarla
        pixmap = QPixmap.fromImage(q_image)
        
        # Boyutları yeniden hesapla
        label_size = self.image_label.size()
        scaled_pixmap = pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        self.image_label.setPixmap(scaled_pixmap)
        
    def detect_faces(self):
        """Yüklenen görseldeki yüzleri tespit et"""
        if self.image_data is None or self.face_analyzer is None:
            return
            
        try:
            # Yüzleri tespit et
            self.detected_faces = self.face_analyzer.get(self.image_data)
            
            # Liste widget'ını temizle
            self.faces_list.clear()
            self.selected_face_idx = -1
            
            if not self.detected_faces or len(self.detected_faces) == 0:
                self.faces_list.addItem("Yüz tespit edilemedi!")
                return
                
            # Tespit edilen yüzleri listele
            for i, face in enumerate(self.detected_faces):
                gender = "Erkek" if face.sex == 1 else "Kadın" if face.sex == 0 else "Bilinmiyor"
                age = int(face.age) if hasattr(face, 'age') else "?"
                score = round(float(face.det_score), 2)
                
                self.faces_list.addItem(f"Yüz #{i+1} - {gender}, Yaş: {age}, Skor: {score}")
                
            # Yüz kutularını çiz
            self.draw_face_boxes()
            
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yüz tespiti sırasında hata: {str(e)}")
            
    def draw_face_boxes(self):
        """Tespit edilen yüzlerin kutularını çiz"""
        if self.image_data is None or not self.detected_faces:
            return
            
        # Orijinal görüntüyü kopyala
        img_with_boxes = self.image_data.copy()
        
        # Her yüz için kutu çiz
        for i, face in enumerate(self.detected_faces):
            bbox = face.bbox.astype(int)
            color = (0, 255, 0)  # BGR - Yeşil
            
            # Seçili yüzü farklı renkle işaretle
            if i == self.selected_face_idx:
                color = (0, 0, 255)  # BGR - Kırmızı
                
            # Kutu çiz
            cv2.rectangle(
                img_with_boxes, 
                (bbox[0], bbox[1]), 
                (bbox[2], bbox[3]), 
                color, 
                2
            )
            
            # ID'yi yaz
            cv2.putText(
                img_with_boxes,
                f"#{i+1}",
                (bbox[0], bbox[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2
            )
            
        # Ekranda göster
        image_rgb = cv2.cvtColor(img_with_boxes, cv2.COLOR_BGR2RGB)
        h, w, ch = image_rgb.shape
        bytes_per_line = ch * w
        q_image = QImage(image_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        pixmap = QPixmap.fromImage(q_image)
        
        # Boyutları yeniden hesapla
        label_size = self.image_label.size()
        scaled_pixmap = pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        self.image_label.setPixmap(scaled_pixmap)
        
    @pyqtSlot(int)
    def on_face_select(self, row):
        """Liste widget'ından yüz seçildiğinde"""
        if row < 0 or not self.detected_faces or row >= len(self.detected_faces):
            return
            
        self.selected_face_idx = row
        
        # Seçilen yüzü göster
        self.draw_face_boxes()
        
        # Yüz bilgilerini göster
        face = self.detected_faces[row]
        
        # Tespit skoru
        self.score_label.setText(f"Tespit Skoru: {face.det_score:.2f}")
        
        # Cinsiyet
        gender_text = "Erkek" if face.sex == 1 else "Kadın" if face.sex == 0 else "Bilinmiyor"
        self.gender_label.setText(f"Cinsiyet: {gender_text}")
        
        # Yaş
        age = int(face.age) if hasattr(face, 'age') else "?"
        self.age_label.setText(f"Yaş: {age}")
        
        # UI durumunu güncelle
        self.update_ui_state()
        
    def update_form_fields(self):
        """Seçilen veritabanına göre form alanlarını güncelle"""
        # Önce varolan özel alanları temizle
        for i in range(self.form_layout.rowCount() - 1, 1, -1):
            self.form_layout.removeRow(i)
            
        # Seçilen veritabanı türüne göre gerekli alanları ekle
        selected_button = self.db_group.checkedButton()
        
        if selected_button == self.egm_radio:
            # EGM için özel alanlar
            self.form_layout.addRow("Örgüt:", self.organizer_edit)
            self.form_layout.addRow("Seviye:", self.level_edit)
            self.form_layout.addRow("Doğum Yeri/Tarihi:", self.birth_edit)
            
        elif selected_button == self.external_radio:
            # External için özel alan
            self.form_layout.addRow("Alarm:", self.alarm_check)
            
    def save_to_database(self):
        """Seçili yüzü veritabanına kaydet"""
        if not self.db_conn:
            QMessageBox.critical(self, "Hata", "Veritabanı bağlantısı yok!")
            return
            
        if self.image_data is None:
            QMessageBox.critical(self, "Hata", "Lütfen önce bir resim yükleyin!")
            return
            
        if self.selected_face_idx < 0 or self.selected_face_idx >= len(self.detected_faces):
            QMessageBox.critical(self, "Hata", "Lütfen bir yüz seçin!")
            return
            
        # Form verilerini doğrula
        face_name = self.face_name_edit.text().strip()
        if not face_name:
            QMessageBox.critical(self, "Hata", "Yüz adı zorunludur!")
            return
            
        # Seçili yüzü al
        face = self.detected_faces[self.selected_face_idx]
        
        try:
            # Seçilen veritabanı türünü belirle
            selected_button = self.db_group.checkedButton()
            
            if selected_button == self.egm_radio:
                db_type = "EgmArananlar"
            elif selected_button == self.whitelist_radio:
                db_type = "WhiteListFaces"
            elif selected_button == self.custom_radio:
                db_type = "CustomFaceStorage"
            elif selected_button == self.external_radio:
                db_type = "ExternalFaceStorage"
            else:
                QMessageBox.critical(self, "Hata", "Lütfen bir veritabanı türü seçin!")
                return
                
            cursor = self.db_conn.cursor()
            
            # Resmi bytes olarak kodla
            _, img_bytes = cv2.imencode('.jpg', self.image_data)
            image_binary = img_bytes.tobytes()
            
            # Temel parametreler (tüm tablolarda ortak)
            face_desc = self.face_desc_edit.text().strip()
            
            # Yüz verilerini hazırla
            face_emb = face.embedding
            landmarks = face.landmark_2d_106
            facebox = face.bbox
            det_score = float(face.det_score)
            gender = False if face.sex == 0 else True if face.sex == 1 else None
            age = int(face.age) if hasattr(face, 'age') else None
            
            if db_type == "EgmArananlar":
                # EGM için özel alanları kontrol et
                organizer = self.organizer_edit.text().strip()
                level = self.level_edit.text().strip()
                birth = self.birth_edit.text().strip()
                
                if not organizer or not level or not birth:
                    QMessageBox.critical(self, "Hata", "Örgüt, seviye ve doğum bilgileri zorunludur!")
                    return
                
                # EGM Arananlar tablosuna ekle
                cursor.execute("""
                    INSERT INTO "EgmArananlar" 
                    ("ImageData", "ImageHash", "FaceName", "Organizer", "OrganizerLevel", 
                    "BirthDateAndLocation", "FaceEmbeddingData", "Landmarks2d", "FaceBox", 
                    "DetectionScore", "FaceGender", "FaceAge")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    psycopg2.Binary(image_binary),
                    self.image_hash,
                    face_name,
                    organizer,
                    level,
                    birth,
                    psycopg2.Binary(face_emb),
                    psycopg2.Binary(landmarks),
                    psycopg2.Binary(facebox),
                    det_score,
                    gender,
                    age
                ))
                
            elif db_type == "WhiteListFaces":
                # Whitelist tablosuna ekle
                cursor.execute("""
                    INSERT INTO "WhiteListFaces" 
                    ("FaceName", "FaceDescription", "FaceImage", "FaceImageHash",
                    "FaceEmbeddingData", "Landmarks2d", "FaceBox", "DetectionScore", "FaceGender", "FaceAge")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    face_name,
                    face_desc,
                    psycopg2.Binary(image_binary),
                    self.image_hash,
                    psycopg2.Binary(face_emb),
                    psycopg2.Binary(landmarks),
                    psycopg2.Binary(facebox),
                    det_score,
                    gender,
                    age
                ))
                
            elif db_type == "CustomFaceStorage":
                # Custom Face Storage tablosuna ekle
                cursor.execute("""
                    INSERT INTO "CustomFaceStorage" 
                    ("FaceName", "FaceDescription", "FaceImage", "FaceImageHash",
                    "FaceEmbeddingData", "Landmarks2d", "FaceBox", "DetectionScore", "FaceGender", "FaceAge")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    face_name,
                    face_desc,
                    psycopg2.Binary(image_binary),
                    self.image_hash,
                    psycopg2.Binary(face_emb),
                    psycopg2.Binary(landmarks),
                    psycopg2.Binary(facebox),
                    det_score,
                    gender,
                    age
                ))
                
            elif db_type == "ExternalFaceStorage":
                # External Face Storage tablosuna ekle
                alarm = self.alarm_check.isChecked()
                
                cursor.execute("""
                    INSERT INTO "ExternalFaceStorage" 
                    ("ImageData", "ImageHash", "FaceName", "FaceDescription",
                    "FaceEmbeddingData", "Landmarks2d", "FaceBox", "DetectionScore", 
                    "FaceGender", "FaceAge", "Alarm")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    psycopg2.Binary(image_binary),
                    self.image_hash,
                    face_name,
                    face_desc,
                    psycopg2.Binary(face_emb),
                    psycopg2.Binary(landmarks),
                    psycopg2.Binary(facebox),
                    det_score,
                    gender,
                    age,
                    alarm
                ))
                
            # Değişiklikleri kaydet
            self.db_conn.commit()
            QMessageBox.information(self, "Başarılı", f"Yüz verisi '{db_type}' tablosuna başarıyla kaydedildi!")
            
            # Formları temizle
            self.clear_form()
            
        except Exception as e:
            # Hata durumunda geri al
            if self.db_conn:
                self.db_conn.rollback()
            QMessageBox.critical(self, "Veritabanı Hatası", f"Yüz kaydedilirken hata oluştu: {str(e)}")
            
    def clear_form(self):
        """Form alanlarını temizle"""
        self.face_name_edit.clear()
        self.face_desc_edit.clear()
        self.organizer_edit.clear()
        self.level_edit.clear()
        self.birth_edit.clear()
        self.alarm_check.setChecked(False)
        
    def update_ui_state(self):
        """UI durumunu güncelle (aktif/pasif)"""
        has_image = self.image_data is not None
        has_faces = len(self.detected_faces) > 0
        has_selected_face = 0 <= self.selected_face_idx < len(self.detected_faces)
        
        # Kaydet butonu sadece görsel, yüz ve seçim varsa aktif
        self.save_button.setEnabled(has_image and has_faces and has_selected_face)
        
    def resizeEvent(self, event):
        """Pencere boyutu değiştiğinde resmi yeniden ölçeklendir"""
        super().resizeEvent(event)
        if hasattr(self, 'image_data') and self.image_data is not None:
            self.draw_face_boxes()  # Yeniden çiz
            
    def closeEvent(self, event):
        """Uygulama kapatılırken temizlik işlemleri"""
        if self.db_conn:
            self.db_conn.close()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DatabaseUploaderGUI()
    window.show()
    sys.exit(app.exec_()) 