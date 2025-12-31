#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import cv2
import numpy as np
import hashlib
import base64
import psycopg2
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from lib.init_insightface import initilate_insightface
from lib.load_config import load_config_from_file

class DatabaseUploaderGUI:
    """Yüz Veritabanı Yükleme Aracı GUI"""
    
    def __init__(self, root):
        # Ana pencere konfigürasyonu
        self.root = root
        self.root.title("EyeOfWeb - Veritabanı Yükleme Aracı")
        self.root.geometry("900x750")
        self.root.resizable(True, True)
        
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
        
        # GUI bileşenlerini oluştur
        self.create_widgets()
        
        # İlk arayüz güncelleme
        self.update_ui_state()
        
    def load_config_and_analyzer(self):
        """Yapılandırma ve InsightFace yükle"""
        try:
            # Yapılandırmayı yükle
            config_data = load_config_from_file()
            if not config_data[0]:
                messagebox.showerror("Hata", f"Yapılandırma yüklenemedi: {config_data[1]}")
                sys.exit(1)
            
            self.config = config_data[1]
            
            # InsightFace modeli yükle
            self.face_analyzer = initilate_insightface(config_data)
            if self.face_analyzer is None:
                messagebox.showerror("Hata", "InsightFace modeli yüklenemedi!")
                sys.exit(1)
                
            print("InsightFace modeli başarıyla yüklendi.")
        except Exception as e:
            messagebox.showerror("Hata", f"Yapılandırma ve model yükleme hatası: {str(e)}")
            sys.exit(1)
            
    def connect_to_database(self):
        """Veritabanına bağlan"""
        try:
            if not self.config or "database_config" not in self.config:
                messagebox.showerror("Hata", "Veritabanı yapılandırması bulunamadı!")
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
            messagebox.showerror("Veritabanı Hatası", f"Veritabanına bağlanılamadı: {str(e)}")
            
    def create_widgets(self):
        """GUI bileşenlerini oluştur"""
        # Ana frame
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Sol panel (resim ve yüz analizi)
        left_panel = ttk.Frame(main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Sağ panel (form ve gönderim)
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # ---- SOL PANEL ----
        # Resim seçme butonu
        self.browse_button = ttk.Button(left_panel, text="Resim Seç", command=self.browse_image)
        self.browse_button.pack(fill=tk.X, pady=5)
        
        # Görüntü gösterimi için canvas
        self.image_frame = ttk.LabelFrame(left_panel, text="Görüntü", padding=5)
        self.image_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.canvas = tk.Canvas(self.image_frame, bg="lightgray")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Tespit edilen yüzler listesi
        self.faces_frame = ttk.LabelFrame(left_panel, text="Tespit Edilen Yüzler", padding=5)
        self.faces_frame.pack(fill=tk.X, pady=5)
        
        self.faces_listbox = tk.Listbox(self.faces_frame, height=5)
        self.faces_listbox.pack(fill=tk.X)
        self.faces_listbox.bind('<<ListboxSelect>>', self.on_face_select)
        
        # ---- SAĞ PANEL ----
        # Veritabanı seçimi
        db_frame = ttk.LabelFrame(right_panel, text="Veritabanı", padding=5)
        db_frame.pack(fill=tk.X, pady=5)
        
        self.db_var = tk.StringVar(value="CustomFaceStorage")
        ttk.Radiobutton(db_frame, text="EGM Arananlar", variable=self.db_var, 
                       value="EgmArananlar", command=self.update_form_fields).pack(anchor=tk.W)
        ttk.Radiobutton(db_frame, text="Whitelist", variable=self.db_var, 
                       value="WhiteListFaces", command=self.update_form_fields).pack(anchor=tk.W)
        ttk.Radiobutton(db_frame, text="Custom Face Storage", variable=self.db_var, 
                       value="CustomFaceStorage", command=self.update_form_fields).pack(anchor=tk.W)
        ttk.Radiobutton(db_frame, text="External Face Storage", variable=self.db_var, 
                       value="ExternalFaceStorage", command=self.update_form_fields).pack(anchor=tk.W)
        
        # Form alanları
        self.form_frame = ttk.LabelFrame(right_panel, text="Yüz Bilgileri", padding=5)
        self.form_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Form alanları için grid düzeni
        row = 0
        
        # Yüz Adı
        ttk.Label(self.form_frame, text="Yüz Adı:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.face_name_var = tk.StringVar()
        ttk.Entry(self.form_frame, textvariable=self.face_name_var).grid(row=row, column=1, sticky=tk.EW, pady=2)
        row += 1
        
        # Yüz Açıklaması
        ttk.Label(self.form_frame, text="Açıklama:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.face_desc_var = tk.StringVar()
        ttk.Entry(self.form_frame, textvariable=self.face_desc_var).grid(row=row, column=1, sticky=tk.EW, pady=2)
        row += 1
        
        # EGM için özel alanlar
        self.organizer_label = ttk.Label(self.form_frame, text="Örgüt:")
        self.organizer_var = tk.StringVar()
        self.organizer_entry = ttk.Entry(self.form_frame, textvariable=self.organizer_var)
        
        self.level_label = ttk.Label(self.form_frame, text="Seviye:")
        self.level_var = tk.StringVar()
        self.level_entry = ttk.Entry(self.form_frame, textvariable=self.level_var)
        
        self.birth_label = ttk.Label(self.form_frame, text="Doğum Yeri/Tarihi:")
        self.birth_var = tk.StringVar()
        self.birth_entry = ttk.Entry(self.form_frame, textvariable=self.birth_var)
        
        # External için özel alan
        self.alarm_label = ttk.Label(self.form_frame, text="Alarm:")
        self.alarm_var = tk.BooleanVar(value=False)
        self.alarm_check = ttk.Checkbutton(self.form_frame, variable=self.alarm_var)
        
        # Yüz özellik bilgileri (sadece görüntüleme)
        self.info_frame = ttk.LabelFrame(right_panel, text="Tespit Bilgileri", padding=5)
        self.info_frame.pack(fill=tk.X, pady=5)
        
        self.score_label = ttk.Label(self.info_frame, text="Tespit Skoru: -")
        self.score_label.pack(anchor=tk.W)
        
        self.gender_label = ttk.Label(self.info_frame, text="Cinsiyet: -")
        self.gender_label.pack(anchor=tk.W)
        
        self.age_label = ttk.Label(self.info_frame, text="Yaş: -")
        self.age_label.pack(anchor=tk.W)
        
        # Kaydet butonu
        self.save_button = ttk.Button(right_panel, text="Veritabanına Kaydet", 
                                     command=self.save_to_database)
        self.save_button.pack(fill=tk.X, pady=10)
        
        # Formu ilk başta güncelle
        self.update_form_fields()
        
    def update_form_fields(self):
        """Seçilen veritabanına göre formu güncelle"""
        # Önce tüm özel alanları gizle
        for widget in [self.organizer_label, self.organizer_entry, 
                      self.level_label, self.level_entry,
                      self.birth_label, self.birth_entry,
                      self.alarm_label, self.alarm_check]:
            widget.grid_forget()
        
        # Seçilen veritabanına göre ilgili alanları göster
        db_type = self.db_var.get()
        row = 2  # İlk iki alan sabit (isim ve açıklama)
        
        if db_type == "EgmArananlar":
            # Örgüt
            self.organizer_label.grid(row=row, column=0, sticky=tk.W, pady=2)
            self.organizer_entry.grid(row=row, column=1, sticky=tk.EW, pady=2)
            row += 1
            
            # Seviye
            self.level_label.grid(row=row, column=0, sticky=tk.W, pady=2)
            self.level_entry.grid(row=row, column=1, sticky=tk.EW, pady=2)
            row += 1
            
            # Doğum Yeri/Tarihi
            self.birth_label.grid(row=row, column=0, sticky=tk.W, pady=2)
            self.birth_entry.grid(row=row, column=1, sticky=tk.EW, pady=2)
            
        elif db_type == "ExternalFaceStorage":
            # Alarm
            self.alarm_label.grid(row=row, column=0, sticky=tk.W, pady=2)
            self.alarm_check.grid(row=row, column=1, sticky=tk.W, pady=2)
            
    def browse_image(self):
        """Görüntü dosyası seç"""
        file_path = filedialog.askopenfilename(
            title="Resim Dosyası Seç",
            filetypes=[("Resim Dosyaları", "*.jpg;*.jpeg;*.png;*.bmp;*.JPG;*.JPEG;*.PNG;*.BMP")]
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
            
            # Resmi canvas'a yükle
            self.display_image()
            
            # Yüzleri tespit et
            self.detect_faces()
            
        except Exception as e:
            messagebox.showerror("Hata", f"Resim yüklenirken hata oluştu: {str(e)}")
            
    def display_image(self):
        """Görüntüyü canvas'ta göster"""
        if self.image_data is None:
            return
            
        # Resmi PIL formatına dönüştür (RGB)
        image_rgb = cv2.cvtColor(self.image_data, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(image_rgb)
        
        # Canvas boyutlarına göre ölçeklendir
        canvas_width = self.canvas.winfo_width() or 400
        canvas_height = self.canvas.winfo_height() or 400
        
        img_width, img_height = pil_img.size
        scale = min(canvas_width/img_width, canvas_height/img_height)
        
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        
        resized_img = pil_img.resize((new_width, new_height), Image.LANCZOS)
        
        # Tkinter PhotoImage nesnesine dönüştür
        self.tk_image = ImageTk.PhotoImage(resized_img)
        
        # Canvas içeriğini temizle ve yeni resmi göster
        self.canvas.delete("all")
        self.canvas.create_image(
            canvas_width/2, canvas_height/2,
            image=self.tk_image, anchor=tk.CENTER)
            
    def detect_faces(self):
        """Yüklenen görseldeki yüzleri tespit et"""
        if self.image_data is None or self.face_analyzer is None:
            return
            
        try:
            # Yüzleri tespit et
            self.detected_faces = self.face_analyzer.get(self.image_data)
            
            # Listbox'ı güncelle
            self.faces_listbox.delete(0, tk.END)
            
            if not self.detected_faces or len(self.detected_faces) == 0:
                self.faces_listbox.insert(tk.END, "Yüz tespit edilemedi!")
                return
                
            # Tespit edilen yüzleri listele
            for i, face in enumerate(self.detected_faces):
                gender = "Erkek" if face.sex == 1 else "Kadın" if face.sex == 0 else "Bilinmiyor"
                age = int(face.age) if hasattr(face, 'age') else "?"
                score = round(float(face.det_score), 2)
                
                self.faces_listbox.insert(
                    tk.END, 
                    f"Yüz #{i+1} - {gender}, Yaş: {age}, Skor: {score}"
                )
                
            # Görüntüye yüz kutularını çiz
            self.draw_face_boxes()
            
        except Exception as e:
            messagebox.showerror("Hata", f"Yüz tespiti sırasında hata: {str(e)}")
            
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
            
        # Kutu çizilmiş resmi göster
        image_rgb = cv2.cvtColor(img_with_boxes, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(image_rgb)
        
        # Canvas boyutlarına göre ölçeklendir
        canvas_width = self.canvas.winfo_width() or 400
        canvas_height = self.canvas.winfo_height() or 400
        
        img_width, img_height = pil_img.size
        scale = min(canvas_width/img_width, canvas_height/img_height)
        
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)
        
        resized_img = pil_img.resize((new_width, new_height), Image.LANCZOS)
        
        # Tkinter PhotoImage nesnesine dönüştür
        self.tk_image = ImageTk.PhotoImage(resized_img)
        
        # Canvas içeriğini temizle ve yeni resmi göster
        self.canvas.delete("all")
        self.canvas.create_image(
            canvas_width/2, canvas_height/2,
            image=self.tk_image, anchor=tk.CENTER)
            
    def on_face_select(self, event):
        """Listbox'tan yüz seçildiğinde"""
        if not self.detected_faces:
            return
            
        selection = self.faces_listbox.curselection()
        if not selection:
            return
            
        # Seçilen yüz indeksini kaydet
        self.selected_face_idx = selection[0]
        
        # Seçili yüzü göster
        self.draw_face_boxes()
        
        # Seçili yüzün detaylarını güncelle
        if 0 <= self.selected_face_idx < len(self.detected_faces):
            face = self.detected_faces[self.selected_face_idx]
            
            # Tespit bilgilerini göster
            self.score_label.config(text=f"Tespit Skoru: {face.det_score:.2f}")
            
            gender_text = "Erkek" if face.sex == 1 else "Kadın" if face.sex == 0 else "Bilinmiyor"
            self.gender_label.config(text=f"Cinsiyet: {gender_text}")
            
            age = int(face.age) if hasattr(face, 'age') else "?"
            self.age_label.config(text=f"Yaş: {age}")
            
    def save_to_database(self):
        """Seçili yüzü veritabanına kaydet"""
        if not self.db_conn:
            messagebox.showerror("Hata", "Veritabanı bağlantısı yok!")
            return
            
        if self.image_data is None:
            messagebox.showerror("Hata", "Lütfen önce bir resim yükleyin!")
            return
            
        if self.selected_face_idx < 0 or self.selected_face_idx >= len(self.detected_faces):
            messagebox.showerror("Hata", "Lütfen bir yüz seçin!")
            return
            
        # Form verilerini doğrula
        face_name = self.face_name_var.get().strip()
        if not face_name:
            messagebox.showerror("Hata", "Yüz adı zorunludur!")
            return
            
        # Seçili yüzü al
        face = self.detected_faces[self.selected_face_idx]
        
        try:
            # Veritabanı türünü al
            db_type = self.db_var.get()
            cursor = self.db_conn.cursor()
            
            # Resmi bytes olarak kodla
            _, img_bytes = cv2.imencode('.jpg', self.image_data)
            image_binary = img_bytes.tobytes()
            
            # Temel parametreler (tüm tablolarda ortak)
            face_desc = self.face_desc_var.get().strip()
            
            # Yüz verilerini hazırla
            face_emb = face.embedding
            landmarks = face.landmark_2d_106
            facebox = face.bbox
            det_score = float(face.det_score)
            gender = False if face.sex == 0 else True if face.sex == 1 else None
            age = int(face.age) if hasattr(face, 'age') else None
            
            if db_type == "EgmArananlar":
                # EGM için özel alanları kontrol et
                organizer = self.organizer_var.get().strip()
                level = self.level_var.get().strip()
                birth = self.birth_var.get().strip()
                
                if not organizer or not level or not birth:
                    messagebox.showerror("Hata", "Örgüt, seviye ve doğum bilgileri zorunludur!")
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
                alarm = self.alarm_var.get()
                
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
            messagebox.showinfo("Başarılı", f"Yüz verisi '{db_type}' tablosuna başarıyla kaydedildi!")
            
            # Formları temizle
            self.clear_form()
            
        except Exception as e:
            # Hata durumunda geri al
            self.db_conn.rollback()
            messagebox.showerror("Veritabanı Hatası", f"Yüz kaydedilirken hata oluştu: {str(e)}")
            
    def clear_form(self):
        """Form alanlarını temizle"""
        self.face_name_var.set("")
        self.face_desc_var.set("")
        self.organizer_var.set("")
        self.level_var.set("")
        self.birth_var.set("")
        self.alarm_var.set(False)
        
    def update_ui_state(self):
        """UI durumunu güncelle (aktif/pasif)"""
        has_image = self.image_data is not None
        has_faces = len(self.detected_faces) > 0
        has_selected_face = self.selected_face_idx >= 0
        
        # Kaydet butonu sadece görsel, yüz ve seçim varsa aktif
        self.save_button["state"] = "normal" if has_image and has_faces and has_selected_face else "disabled"
        
    def __del__(self):
        """Temizlik işlemleri"""
        if self.db_conn:
            self.db_conn.close()

if __name__ == "__main__":
    # Ana pencereyi oluştur
    root = tk.Tk()
    app = DatabaseUploaderGUI(root)
    
    # UI yeniden boyutlandırıldığında resmi güncelle
    def on_resize(event):
        if hasattr(app, 'image_data') and app.image_data is not None:
            # 100ms bekleyerek sürekli güncellemeden kaçın
            root.after(100, app.draw_face_boxes)
            
    root.bind("<Configure>", on_resize)
    
    # Ana döngüyü başlat
    root.mainloop() 