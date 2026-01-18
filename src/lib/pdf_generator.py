#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fpdf import FPDF
from datetime import datetime
import os
import requests
import io
import traceback
from fpdf.drawing import DeviceGray, DeviceRGB  # Renk sınıfları import edildi
from urllib.parse import urlparse, parse_qs  # URL işleme için eklendi
from PIL import Image, ImageDraw  # Pillow importları eklendi
import base64
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

# Sabitler
LOGO_PATH = "static/EyeOfWebLogo.png"
FONT_FAMILY = "DejaVu"  # Türkçe karakterler için Unicode destekli font
MAX_IMAGE_WIDTH = 55  # Resim genişliğini biraz azaltıyoruz (metin alanı için)
MAX_IMAGE_HEIGHT = 60  # Yüksekliği koruyoruz
IMAGE_TEXT_GAP = 4  # Resim ve metin arasındaki boşluğu azaltıyoruz
LINE_HEIGHT = 5  # Satır yüksekliği
DETAIL_LABEL_WIDTH = 35  # Etiket genişliğini biraz azaltıyoruz (değer alanı için)
URL_FONT_SIZE = 8  # URL'ler için daha küçük font boyutu
FACE_CUTOUT_SIZE = 40  # Size for side-by-side face cutouts


class PDFReport(FPDF):
    def header(self):
        # Logo
        logo_y_pos = 8
        logo_height = 20  # Logo yüksekliğini ayarladık
        logo_width = 35  # Logo genişliğini biraz küçülttük

        if os.path.exists(LOGO_PATH):
            try:
                self.image(
                    LOGO_PATH,
                    x=self.l_margin,
                    y=logo_y_pos,
                    w=logo_width,
                    h=logo_height,
                )
            except Exception as e:
                # Hata durumunda loglama ve hücre boyutu ayarlama
                print(f"PDF Başlığına logo eklenirken hata: {e}")
                self.set_y(logo_y_pos)  # Y pozisyonunu ayarla
                self.set_font(FONT_FAMILY, "B", 10)
                self.cell(
                    logo_width, 10, "Logo Yok", 1, 0, "C"
                )  # Hata durumunda çerçeveli hücre
                logo_height = 10
        else:
            # Logo yoksa yer tutucu hücre
            self.set_y(logo_y_pos)
            self.set_font(FONT_FAMILY, "B", 10)
            self.cell(logo_width, 10, "Logo Yok", 1, 0, "C")
            logo_height = 10

        # Firma Adı - Ortalamak için logo genişliğini kullan
        title_y_pos = logo_y_pos + 2  # Başlığı biraz daha yukarıya aldık
        self.set_y(title_y_pos)
        # Kalan genişliği hesapla
        available_width = (
            self.w - self.l_margin - self.r_margin - logo_width - 5
        )  # 5mm boşluk
        self.set_x(self.l_margin + logo_width + 5)
        self.set_font(FONT_FAMILY, "B", 16)  # Başlık fontunu küçülttük
        self.cell(available_width, 8, "WeKnow Devoloper Team", 0, 0, "C")

        # Başlığın altına çizgi
        header_bottom_y = max(
            logo_y_pos + logo_height + 2, title_y_pos + 10
        )  # Çizgiyi daha yukarı çektik
        self.set_y(header_bottom_y)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(6)  # Çizgiden sonra daha az boşluk

    def footer(self):
        # Sayfa numarası
        self.set_y(-20)  # Powered by için yer açmak amacıyla biraz yukarı aldık
        self.set_font(FONT_FAMILY, "", 8)
        self.cell(0, 10, f"Sayfa {self.page_no()}/{{nb}}", 0, 0, "C")

        # Powered By metni
        self.set_y(-15)  # Sayfa numarasının altına
        self.set_font(FONT_FAMILY, "", 7)  # Daha küçük font
        self.cell(0, 10, "Powered By WeKnow Devoloper Team", 0, 0, "C")

    def add_watermark(self, text=""):
        # Mevcut fontu ve rengi sakla
        original_font_family = self.font_family
        original_font_style = self.font_style
        original_font_size = self.font_size_pt

        # Küçük ve açık gri bir font ayarla
        self.set_font(FONT_FAMILY, "B", 12)  # Filigranı biraz büyüttük
        self.set_text_color(200, 200, 200)  # Daha açık bir gri tonu

        # Pozisyon ayarları - sayfanın ortasında olacak şekilde
        x = self.w / 2
        y = self.h / 2

        # Metnin genişliğini al
        text_width = self.get_string_width(text)

        # Döndürme ve yazdırma
        self.rotate(45, x=x, y=y)
        self.text(x - text_width / 2, y, text)
        self.rotate(0)

        # Orijinal fontları geri yükle
        self.set_font(original_font_family, original_font_style, original_font_size)
        self.set_text_color(0, 0, 0)  # Siyaha geri dön

    def create_table_cell(self, label, value, x_position, label_width, value_width):
        """Tablo benzeri hizalı hücre çifti (etiket-değer) oluştur"""
        y_start = self.get_y()

        # Etiket hücresi
        self.set_xy(x_position, y_start)
        self.set_font(FONT_FAMILY, "B", 9)
        self.cell(label_width, 6, f"{label}:", 0, 0, "L")

        # Değer hücresi - cell kullanıyoruz çünkü tek satır değerler için daha düzgün hizalama sağlar
        self.set_xy(x_position + label_width, y_start)
        self.set_font(FONT_FAMILY, "", 9)
        self.cell(value_width, 6, str(value), 0, 1, "L")

        return self.get_y() - y_start  # Hücre yüksekliğini döndür

    def create_table_cell_multiline(
        self, label, value, x_position, label_width, value_width
    ):
        """Çok satırlı değerleri destekleyen tablo benzeri hücre çifti"""
        y_start = self.get_y()

        # Önce değeri bir stringe çevir ve çok satırlı olup olmadığını kontrol et
        value_str = str(value)

        # URL etiketleri için her zaman çok satırlı kabul et ve URL formatını koru
        is_url = label in ["Resim URL", "Kaynak URL"] and value_str != "N/A"
        # Diğer uzun içerikler veya satır içi \n olan içerikler için
        is_multiline = (
            "\n" in value_str or len(value_str) > 45 or is_url
        )  # Eşiği düşürdük

        # Etiket hücresi
        self.set_xy(x_position, y_start)
        self.set_font(FONT_FAMILY, "B", 9)
        self.cell(label_width, 6, f"{label}:", 0, 0, "L")

        # Değer hücresi - eğer çok satırlıysa multi_cell kullan
        self.set_xy(x_position + label_width, y_start)
        self.set_font(FONT_FAMILY, "", 9)

        if is_multiline:
            # URL değerleri için satır yüksekliğini azalt ve tam metin göster
            line_height = (
                3.5 if is_url else 5
            )  # URL için satır yüksekliğini daha da azalttık
            # URL için renk değişikliği - okumayı kolaylaştırmak için
            if is_url and value_str != "N/A":
                self.set_text_color(0, 0, 200)  # Mavi
            self.multi_cell(value_width, line_height, value_str, 0, "L")
            # Rengi geri al
            if is_url and value_str != "N/A":
                self.set_text_color(0, 0, 0)  # Siyah

            value_height = self.get_y() - y_start
            # Sonraki satır için pozisyonları ayarla
            self.set_y(y_start + value_height)
        else:
            self.cell(value_width, 6, value_str, 0, 1, "L")
            value_height = 6  # Standart yükseklik

        return value_height  # Hücre yüksekliğini döndür

    def chapter_title(self, title):
        self.set_font(FONT_FAMILY, "B", 12)
        # Daha belirgin bölüm başlığı
        self.cell(0, 8, title, border="B", ln=1, align="L")
        self.ln(4)

    def chapter_body(self, body):
        self.set_font(FONT_FAMILY, "", 10)
        self.multi_cell(0, LINE_HEIGHT, body)
        self.ln()

    def add_search_info(self, search_type, username):
        self.set_font(FONT_FAMILY, "", 10)

        # Arama bilgilerini tablo formatında göster
        now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        # 1. satır: Arama Tipi
        x_start = self.l_margin
        self.create_table_cell("Arama Tipi", search_type, x_start, 35, 150)

        # 2. satır: Arama Tarihi
        self.create_table_cell("Arama Tarihi", now, x_start, 35, 150)

        # 3. satır: Aramayı Yapan
        self.create_table_cell("Aramayı Yapan", username, x_start, 35, 150)

        self.ln(8)  # Bilgilerden sonra boşluk

    def add_comparison_info(self, comparison_info):
        if not comparison_info or not isinstance(comparison_info, dict):
            return

        self.ln(2)  # Add some space before this section
        self.set_font(FONT_FAMILY, "B", 11)
        self.cell(0, 7, "Karşılaştırma Sonucu", border="B", ln=1, align="L")
        self.ln(3)

        x_start = self.l_margin
        label_width = 35
        value_width = self.w - self.l_margin - self.r_margin - label_width

        # Comparison Message
        message = comparison_info.get("message", "N/A")
        self.create_table_cell_multiline(
            "Sonuç", message, x_start, label_width, value_width
        )
        self.ln(1)

        # Similarity Score
        score = comparison_info.get("score")
        if score is not None:
            try:
                score_str = f"{float(score):.4f}"
                # Make score bold and slightly larger
                self.set_font(FONT_FAMILY, "B", 10)
            except (ValueError, TypeError):
                score_str = str(score)
                self.set_font(FONT_FAMILY, "", 9)  # Reset font if error
            self.create_table_cell(
                "Benzerlik Skoru", score_str, x_start, label_width, value_width
            )
            self.set_font(FONT_FAMILY, "", 9)  # Reset font after cell
            self.ln(1)

        # Threshold Used
        threshold = comparison_info.get("threshold")
        if threshold is not None:
            try:
                threshold_str = f"{float(threshold):.2f}"
            except (ValueError, TypeError):
                threshold_str = str(threshold)
            self.create_table_cell(
                "Kullanılan Eşik", threshold_str, x_start, label_width, value_width
            )

        self.ln(8)  # Space after the section

    def add_side_by_side_faces(self, face1_b64, face2_b64):
        if not face1_b64 or not face2_b64:
            return  # Cannot display if one is missing

        self.ln(2)
        self.set_font(FONT_FAMILY, "B", 11)
        self.cell(
            0, 7, "Karşılaştırılan Yüzler", border="B", ln=1, align="C"
        )  # Centered title
        self.ln(3)

        page_width = self.w - self.l_margin - self.r_margin
        gap = 10  # Gap between faces
        total_width = (FACE_CUTOUT_SIZE * 2) + gap
        start_x = self.l_margin + (page_width - total_width) / 2
        current_y = self.get_y()

        try:
            # Face 1
            img_bytes1 = base64.b64decode(face1_b64)
            img_stream1 = io.BytesIO(img_bytes1)
            self.image(
                img_stream1,
                x=start_x,
                y=current_y,
                w=FACE_CUTOUT_SIZE,
                h=FACE_CUTOUT_SIZE,
                type="JPEG",
            )
            self.set_xy(start_x, current_y + FACE_CUTOUT_SIZE + 1)
            self.set_font(FONT_FAMILY, "", 8)
            self.cell(FACE_CUTOUT_SIZE, 5, "Yüz 1", 0, 0, "C")
        except Exception as e:
            print(f"Error adding face 1 cutout to PDF: {e}")
            self.set_xy(start_x, current_y)
            self.cell(FACE_CUTOUT_SIZE, FACE_CUTOUT_SIZE, "Hata", 1, 0, "C")
            self.set_xy(start_x, current_y + FACE_CUTOUT_SIZE + 1)
            self.set_font(FONT_FAMILY, "", 8)
            self.cell(FACE_CUTOUT_SIZE, 5, "Yüz 1", 0, 0, "C")

        try:
            # Face 2
            img_bytes2 = base64.b64decode(face2_b64)
            img_stream2 = io.BytesIO(img_bytes2)
            self.image(
                img_stream2,
                x=start_x + FACE_CUTOUT_SIZE + gap,
                y=current_y,
                w=FACE_CUTOUT_SIZE,
                h=FACE_CUTOUT_SIZE,
                type="JPEG",
            )
            self.set_xy(
                start_x + FACE_CUTOUT_SIZE + gap, current_y + FACE_CUTOUT_SIZE + 1
            )
            self.set_font(FONT_FAMILY, "", 8)
            self.cell(FACE_CUTOUT_SIZE, 5, "Yüz 2", 0, 0, "C")
        except Exception as e:
            print(f"Error adding face 2 cutout to PDF: {e}")
            self.set_xy(start_x + FACE_CUTOUT_SIZE + gap, current_y)
            self.cell(FACE_CUTOUT_SIZE, FACE_CUTOUT_SIZE, "Hata", 1, 0, "C")
            self.set_xy(
                start_x + FACE_CUTOUT_SIZE + gap, current_y + FACE_CUTOUT_SIZE + 1
            )
            self.set_font(FONT_FAMILY, "", 8)
            self.cell(FACE_CUTOUT_SIZE, 5, "Yüz 2", 0, 0, "C")

        # Move below the side-by-side section
        self.set_y(current_y + FACE_CUTOUT_SIZE + 10)
        self.ln(5)

    def add_comparison_face_detail(self, face_data):
        face_cropped_b64 = face_data.get("face_cropped_b64")
        title = face_data.get("title", "N/A")

        # Check page break possibility
        # Estimate height: Cropped face + title + details table + spacing
        estimated_height = FACE_CUTOUT_SIZE + 8 + (4 * 6) + 15  # Approximation
        if self.get_y() + estimated_height > self.page_break_trigger:
            self.add_page()
            self.add_watermark()

        block_start_y = self.get_y()
        self.set_font(FONT_FAMILY, "B", 11)
        self.cell(0, 8, title, border="B", ln=1, align="L")
        self.ln(4)

        image_x = self.l_margin
        text_x = self.l_margin + FACE_CUTOUT_SIZE + IMAGE_TEXT_GAP
        text_width = self.w - text_x - self.r_margin - 2
        current_y = self.get_y()

        # Add Cropped Face Image
        if face_cropped_b64:
            try:
                img_bytes = base64.b64decode(face_cropped_b64)
                img_stream = io.BytesIO(img_bytes)
                self.image(
                    img_stream,
                    x=image_x,
                    y=current_y,
                    w=FACE_CUTOUT_SIZE,
                    h=FACE_CUTOUT_SIZE,
                    type="JPEG",
                )
            except Exception as e:
                print(f"Error adding cropped face detail image to PDF: {e}")
                self.set_xy(image_x, current_y)
                self.cell(FACE_CUTOUT_SIZE, FACE_CUTOUT_SIZE, "Hata", 1, 0, "C")
        else:
            self.set_xy(image_x, current_y)
            self.cell(FACE_CUTOUT_SIZE, FACE_CUTOUT_SIZE, "Resim Yok", 1, 0, "C")

        # Add Details Table
        self.set_y(current_y)  # Reset Y to align table with image top
        label_width = 30  # Slightly smaller label width
        value_width = text_width - label_width

        details_to_show = [
            {
                "label": "Kaynak Dosya",
                "value": face_data.get("title", "N/A").split("(")[-1].replace(")", ""),
            },  # Extract filename
            {
                "label": "Tespit Skoru",
                "value": (
                    f"{face_data.get('score'):.2f}"
                    if face_data.get("score") is not None
                    else "N/A"
                ),
            },
            {"label": "Cinsiyet", "value": face_data.get("gender", "N/A")},
            {
                "label": "Yaş",
                "value": (
                    face_data.get("age") if face_data.get("age") is not None else "N/A"
                ),
            },
        ]

        for detail in details_to_show:
            self.create_table_cell(
                detail["label"], detail["value"], text_x, label_width, value_width
            )
            self.ln(0.5)  # Small gap between rows

        # Move below the block
        final_y = max(self.get_y(), current_y + FACE_CUTOUT_SIZE)
        self.set_y(final_y + 8)  # Space after block
        # Add a separator line if needed (optional)
        # self.line(self.l_margin, self.get_y() - 4, self.w - self.r_margin, self.get_y() - 4)
        # self.ln(5)

    def add_image_details(self, image_data, is_pre_boxed=False):
        image_added = False
        image_load_error = None
        original_image_url = image_data.get("image_url")
        image_data_b64 = image_data.get(
            "image_data_b64"
        )  # Base64 verisi için yeni alan
        facebox = image_data.get("facebox")

        # --- URL veya Base64'ten Resmi İşle ---
        img_stream = None
        img_pil = None
        content_type_for_fpdf = None

        if image_data_b64:
            # Base64 veriden resmi yükle
            try:
                image_bytes = base64.b64decode(image_data_b64)
                img_pil = Image.open(io.BytesIO(image_bytes))
                img_pil = img_pil.convert("RGB")  # RGB'ye çevir
                img_stream = io.BytesIO()
                # Determine format for saving to stream (assume JPEG if not obvious)
                # For comparison reports, it's already JPEG encoded in the route
                save_format = "JPEG"
                try:
                    # Check Pillow's format if available
                    if hasattr(img_pil, "format") and img_pil.format in ["JPEG", "PNG"]:
                        save_format = img_pil.format
                except:
                    pass  # Ignore errors in format detection

                img_pil.save(img_stream, format=save_format)
                img_stream.seek(0)
                content_type_for_fpdf = save_format
                image_load_error = None
                # print("Resim base64 veriden başarıyla yüklendi.") # Reduce noise
            except Exception as b64_err:
                image_load_error = f"Base64 işleme hatası: {b64_err}"
                print(f"{image_load_error}")
                img_pil = None
                img_stream = None
        elif original_image_url:
            # --- URL'yi Analiz Et ve İndirmeyi Dene (Existing Logic) ---
            # ?u= parametresini kontrol et
            parsed_original_url = None
            u_param_url = None
            image_url_to_try = original_image_url

            if original_image_url:
                try:
                    parsed_original_url = urlparse(original_image_url)
                    query_params = parse_qs(parsed_original_url.query)
                    if "u" in query_params and query_params["u"]:
                        u_param_url = query_params["u"][0]
                        image_url_to_try = u_param_url
                except Exception as parse_err:
                    print(
                        f"URL ayrıştırılırken hata: {original_image_url} - {parse_err}"
                    )
                    image_url_to_try = original_image_url

            urls_to_attempt = []
            if image_url_to_try:
                urls_to_attempt.append(image_url_to_try)
            if u_param_url and original_image_url and u_param_url != original_image_url:
                urls_to_attempt.append(original_image_url)
            elif not u_param_url and original_image_url:
                if original_image_url not in urls_to_attempt:
                    urls_to_attempt.append(original_image_url)

            if not urls_to_attempt:
                image_load_error = "Resim URL'si yok veya geçersiz"
            else:
                for attempt_url in urls_to_attempt:
                    if not attempt_url:
                        continue
                    try:
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                        }
                        response = requests.get(
                            attempt_url, stream=True, timeout=10, headers=headers
                        )
                        response.raise_for_status()
                        content_type = response.headers.get("content-type")
                        if content_type and content_type.lower() in [
                            "image/jpeg",
                            "image/png",
                            "image/gif",
                        ]:
                            try:
                                img_pil = Image.open(io.BytesIO(response.content))
                                img_pil = img_pil.convert("RGB")
                                img_stream = io.BytesIO()
                                img_format = (
                                    "JPEG"
                                    if content_type.lower() == "image/jpeg"
                                    else "PNG"
                                )
                                img_pil.save(img_stream, format=img_format)
                                img_stream.seek(0)
                                content_type_for_fpdf = img_format
                                image_load_error = None
                                break
                            except Exception as pil_err:
                                current_error = f"Pillow işleme hatası: {pil_err}"
                                if image_load_error is None:
                                    image_load_error = current_error
                                img_pil = None
                                img_stream = None
                                continue
                        else:
                            current_error = f"Desteklenmeyen format ({content_type})"
                            if image_load_error is None:
                                image_load_error = current_error
                    except requests.exceptions.HTTPError as http_err:
                        current_error = f"İndirme Hatası: {http_err.response.status_code} {http_err.response.reason}"
                        if image_load_error is None:
                            image_load_error = current_error
                    except requests.exceptions.RequestException as req_err:
                        current_error = f"Bağlantı Hatası: {req_err}"
                        if image_load_error is None:
                            image_load_error = current_error
                    except Exception as e:
                        current_error = f"Bilinmeyen Hata: {e}"
                        if image_load_error is None:
                            image_load_error = current_error

                if img_stream is None and image_load_error is None:
                    image_load_error = "URL denemeleri başarısız oldu (detay yok)"
        else:
            # Ne URL ne de Base64 veri yoksa hata ver
            image_load_error = (
                "Görüntülenecek resim verisi (URL veya Base64) sağlanmadı."
            )

        # --- İçerik Bloğu Oluşturma ---
        # Sayfa sonu kontrolü
        if (
            self.get_y() + MAX_IMAGE_HEIGHT + 20 > self.page_break_trigger
        ):  # 20mm güvenlik payı
            self.add_page()
            self.add_watermark()

        # İçerik bloğunu başlat
        block_start_y = self.get_y()
        self.set_draw_color(220, 220, 220)  # Açık gri

        # Resim ve metin alanını ayarla - Maksimum genişlik kullanımı için
        image_x = self.l_margin
        text_x = self.l_margin + MAX_IMAGE_WIDTH + IMAGE_TEXT_GAP
        text_width = self.w - text_x - self.r_margin - 2  # 2mm güvenlik payı

        # --- MODIFIED: Skip facebox drawing if is_pre_boxed is True ---
        if (
            not is_pre_boxed
            and img_pil
            and facebox
            and isinstance(facebox, (list, tuple))
            and len(facebox) == 4
        ):
            try:
                draw = ImageDraw.Draw(img_pil)
                x1, y1, x2, y2 = map(int, facebox)
                draw.rectangle([x1, y1, x2, y2], outline="lime", width=3)
                # Resave to stream after drawing
                img_stream = io.BytesIO()
                img_pil.save(img_stream, format=content_type_for_fpdf)
                img_stream.seek(0)
            except Exception as draw_err:
                print(f"Facebox çizilirken hata: {draw_err}")

        # --- Resmi PDF'e Ekle ---
        if img_stream and content_type_for_fpdf:
            try:
                self.image(
                    img_stream,
                    x=image_x,
                    y=block_start_y,
                    w=MAX_IMAGE_WIDTH,
                    h=MAX_IMAGE_HEIGHT,
                    type=content_type_for_fpdf,
                )
                image_added = True
            except Exception as img_add_err:
                print(f"PDF'e resim eklenirken hata: {img_add_err}")
                image_load_error = f"PDF'e eklenemedi: {img_add_err}"

        # --- Metin Bilgilerini Ekle ---
        # Başlık (her zaman aynı pozisyonda)
        title_y = block_start_y
        self.set_xy(text_x, title_y)
        self.set_font(FONT_FAMILY, "B", 11)
        title_text = f"Başlık: {image_data.get('title', 'N/A')}"
        self.cell(text_width, 8, title_text, 0, 1, "L")

        # Resim yükleme hatası
        current_y = self.get_y()
        if not image_added and image_load_error:
            self.set_xy(text_x, current_y)
            self.set_text_color(255, 0, 0)  # Kırmızı
            self.set_font(FONT_FAMILY, "", 9)
            self.multi_cell(text_width, 5, f"Resim Yüklenemedi: {image_load_error}")
            self.set_text_color(0, 0, 0)  # Siyah
            current_y = self.get_y() + 2

        # --- Detaylar Tablosu ---
        # Sabit genişlikler belirle - Değer alanına daha fazla yer
        label_width = DETAIL_LABEL_WIDTH
        value_width = text_width - label_width + 3  # Biraz daha alan ekle

        # Detay bilgilerini düzenli bir tabloda göster
        # URL değerlerini formatlama işlevi - tam URL gösterimi
        def format_url(url):
            if not url or url == "N/A":
                return "N/A"
            # URL'yi tamamen koruyoruz
            return url.strip()  # Boşlukları kaldır

        details = [
            # Resim URL'sini sadece URL ile geldiyse gösterelim
            {
                "label": "Resim Kaynağı",
                "value": (
                    original_image_url
                    if original_image_url
                    else ("Base64 Veri" if image_data_b64 else "N/A")
                ),
                "is_url": bool(original_image_url),
            },
            {
                "label": "Kaynak URL",
                "value": format_url(image_data.get("source_url", "N/A")),
                "is_url": True,
            },
            {"label": "Hash", "value": image_data.get("hash", "N/A")},
            {"label": "Görülme Sayısı", "value": image_data.get("count", "N/A")},
        ]

        if "score" in image_data and image_data.get("score") is not None:
            details.append(
                {"label": "Tespit Skoru", "value": f"{image_data.get('score'):.2f}"}
            )

        if ("gender" in image_data and image_data.get("gender") is not None) and (
            "age" in image_data and image_data.get("age") is not None
        ):
            details.append(
                {
                    "label": "Cinsiyet/Yaş",
                    "value": f"{image_data.get('gender')} / {image_data.get('age')}",
                }
            )

        # Detayları yazdır - tümü için aynı metod kullan
        self.set_y(current_y)
        for detail in details:
            # URL'ler için daha küçük font kullan
            if detail.get("is_url", False):
                current_font_size = self.font_size_pt
                self.set_font_size(URL_FONT_SIZE)

            cell_height = self.create_table_cell_multiline(
                detail["label"], detail["value"], text_x, label_width, value_width
            )

            # Font boyutunu eski haline getir
            if detail.get("is_url", False):
                self.set_font_size(current_font_size)

            # Bir sonraki satır için küçük boşluk bırak
            self.ln(1)

        # --- Benzerlik/Kapsamlı Bilgi ---
        if "similarity" in image_data and image_data["similarity"]:
            sim = image_data["similarity"]
            self.create_table_cell_multiline(
                "Benzerlik",
                f"{sim.get('name', 'N/A')} (%{sim.get('rate', 0)*100:.2f})",
                text_x,
                label_width,
                value_width,
            )
            self.ln(1)
        elif "comprehensive_info" in image_data and image_data["comprehensive_info"]:
            comp_info = image_data["comprehensive_info"]
            self.create_table_cell(
                "Kaps. Gör. Oranı",
                f"%{comp_info.get('view_rate', 0)*100:.2f}",
                text_x,
                label_width,
                value_width,
            )
            if "location" in comp_info:
                self.create_table_cell(
                    "Konum",
                    f"{comp_info.get('location', 'N/A')}",
                    text_x,
                    label_width,
                    value_width,
                )

        # --- İçerik Bloğu Sonu ---
        # Bloğun yüksekliğini hesapla ve bir sonraki blok için yer bırak
        block_end_y = self.get_y()
        block_height = max(
            block_end_y - block_start_y, MAX_IMAGE_HEIGHT if image_added else 0
        )
        self.set_y(block_start_y + block_height + 10)  # 10mm boşluk

        # Ayırıcı çizgi - Daha belirgin bir ayraç için
        self.set_draw_color(180, 180, 180)  # Biraz daha koyu gri
        self.line(
            self.l_margin, self.get_y() - 5, self.w - self.r_margin, self.get_y() - 5
        )
        self.ln(5)  # Çizgiden sonra boşluk

    def cover_page(self, title, subtitle, date_str):
        self.add_page()
        self.add_watermark()

        # Logo (Centered and Large)
        if os.path.exists(LOGO_PATH):
            self.image(LOGO_PATH, x=(self.w - 60) / 2, y=60, w=60)

        self.set_y(130)
        self.set_font(FONT_FAMILY, "B", 24)
        self.cell(0, 10, title, 0, 1, "C")

        self.ln(10)
        self.set_font(FONT_FAMILY, "", 16)
        self.cell(0, 10, subtitle, 0, 1, "C")

        self.set_y(-50)
        self.set_font(FONT_FAMILY, "", 10)
        self.cell(0, 10, f"Rapor Tarihi: {date_str}", 0, 1, "C")
        self.cell(0, 10, "Gizli ve Özelleştirilmiş Rapor", 0, 1, "C")

    def add_network_graph(self, graph_image_stream):
        if not graph_image_stream:
            return

        self.add_page()
        self.add_watermark()

        self.chapter_title("İlişki Ağı Analizi")
        self.chapter_body(
            "Aşağıdaki grafik, hedef kişi ile tespit edilen diğer kişiler arasındaki bağlantıları görselleştirmektedir. Yeşil düğüm hedef kişiyi, kırmızı düğümler ise hedefle birlikte görülen ilişkili kişileri temsil etmektedir."
        )

        try:
            # Görüntüyü ortala
            img_width = 150  # mm
            x = (self.w - img_width) / 2
            y = self.get_y() + 10

            self.image(graph_image_stream, x=x, y=y, w=img_width)
            self.set_y(y + 110)  # Resim yüksekliğine göre ayarla (tahmini)
        except Exception as e:
            print(f"Grafik PDF'e eklenirken hata: {e}")
            self.chapter_body("Grafik oluşturulurken bir hata meydana geldi.")


def generate_network_graph_image(graph_data):
    """NetworkX ve Matplotlib kullanarak statik ağ grafiği oluşturur."""
    if not graph_data or "nodes" not in graph_data or not graph_data["nodes"]:
        return None

    try:
        G = nx.Graph()

        # Renk ve boyut haritaları
        node_colors = []
        node_sizes = []
        labels = {}

        # Düğümleri ekle
        # Node ID'lerinin string olması gerekebilir
        for node in graph_data["nodes"]:
            node_id = str(node["id"])
            G.add_node(node_id)
            labels[node_id] = node_id

            if node.get("group") == "target":
                node_colors.append("#1cc88a")  # Yeşil (Hedef)
                node_sizes.append(1500)
            else:
                node_colors.append("#e74a3b")  # Kırmızı (İlişkili)
                node_sizes.append(800)

        # Kenarları ekle
        edge_colors = []
        for edge in graph_data["edges"]:
            G.add_edge(
                str(edge["from"]), str(edge["to"]), weight=float(edge.get("value", 1))
            )
            edge_colors.append("#b7b9cc")

        # Çizim
        plt.figure(figsize=(10, 8))

        # Layout (Spring layout genellikle iyidir)
        pos = nx.spring_layout(G, k=0.6, seed=42)

        # Düğümleri çiz
        nx.draw_networkx_nodes(
            G,
            pos,
            node_color=node_colors,
            node_size=node_sizes,
            alpha=0.9,
            edgecolors="gray",
        )

        # Kenarları çiz
        nx.draw_networkx_edges(G, pos, width=1.5, alpha=0.5, edge_color=edge_colors)

        # Etiketleri çiz
        nx.draw_networkx_labels(
            G,
            pos,
            labels,
            font_size=9,
            font_color="white",
            font_weight="bold",
            font_family="sans-serif",
        )

        plt.axis("off")
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, transparent=True, bbox_inches="tight")
        plt.close()
        buf.seek(0)
        return buf

    except Exception as e:
        print(f"Graph generation error: {e}")
        return None


def generate_pdf_report(
    search_type, username, search_results, comparison_info=None, graph_data=None
):
    """
    Arama veya karşılaştırma sonuçları için PDF raporu oluşturur.
    Args:
        search_type (str): Arama tipi (Örn: "Normal Arama", "Kapsamlı Kişi Arama").
        username (str): Aramayı yapan kullanıcının adı.
        search_results (list): Arama sonuçlarının listesi. Her öğe bir dict olmalı
                               ve 'add_image_details' fonksiyonunun beklediği anahtarları içermelidir.
        comparison_info (dict, optional): Karşılaştırma sonucu bilgilerini içeren dict.
                                           Keys: 'message', 'score', 'threshold'.
    Returns:
        bytes: Oluşturulan PDF dosyasının byte içeriği veya Hata durumunda None.
    """
    try:
        pdf = PDFReport()

        # Font dosyalarının varlığını kontrol et ve ekle
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        font_bold_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font_italic_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"

        if not os.path.exists(font_path):
            print(
                f"Uyarı: Font dosyası bulunamadı: {font_path}. Standart font kullanılacak."
            )
            pdf.set_font("Arial", size=12)
            global FONT_FAMILY
            FONT_FAMILY = "Arial"
        else:
            pdf.add_font("DejaVu", "", font_path, uni=True)
            if os.path.exists(font_bold_path):
                pdf.add_font("DejaVu", "B", font_bold_path, uni=True)
            else:
                print(f"Uyarı: Kalın font dosyası bulunamadı: {font_bold_path}")
            if os.path.exists(font_italic_path):
                pdf.add_font("DejaVu", "", font_italic_path, uni=True)
            else:
                print(f"Uyarı: Eğik font dosyası bulunamadı: {font_italic_path}")

        pdf.set_font(FONT_FAMILY, "", 12)
        pdf.set_auto_page_break(auto=True, margin=15)

        # --- Kapak Sayfası ---
        current_date = datetime.now().strftime("%d %B %Y")
        # Türkçe ay isimleri için basit bir mapping
        months = {
            "January": "Ocak",
            "February": "Şubat",
            "March": "Mart",
            "April": "Nisan",
            "May": "Mayıs",
            "June": "Haziran",
            "July": "Temmuz",
            "August": "Ağustos",
            "September": "Eylül",
            "October": "Ekim",
            "November": "Kasım",
            "December": "Aralık",
        }
        for eng, tr in months.items():
            current_date = current_date.replace(eng, tr)

        pdf.cover_page(
            (
                "KAPSAMLI KİŞİ ANALİZİ RAPORU"
                if "Kapsamlı" in search_type
                else "ARAMA RAPORU"
            ),
            search_type,
            current_date,
        )

        # --- İçindekiler / Başlangıç ---
        pdf.add_page()
        pdf.add_watermark()

        # Arama Bilgileri
        pdf.add_search_info(search_type, username)

        # --- Grafik ---
        if graph_data:
            print("PDF için grafik oluşturuluyor...")
            graph_stream = generate_network_graph_image(graph_data)
            if graph_stream:
                pdf.add_network_graph(graph_stream)
            else:
                print("Grafik stream oluşturulamadı.")

        # Karşılaştırma Bilgileri (varsa)
        if comparison_info:
            pdf.add_comparison_info(comparison_info)

            # Extract cropped faces for side-by-side display
            face1_crop_b64 = (
                search_results[0].get("face_cropped_b64")
                if len(search_results) > 0
                else None
            )
            face2_crop_b64 = (
                search_results[1].get("face_cropped_b64")
                if len(search_results) > 1
                else None
            )
            if face1_crop_b64 and face2_crop_b64:
                pdf.add_side_by_side_faces(face1_crop_b64, face2_crop_b64)

            # Display details for each compared image (using the pre-boxed full image)
            pdf.chapter_title("Görsel Detayları")
            if not search_results or len(search_results) < 2:
                pdf.chapter_body("Karşılaştırma için yeterli görsel verisi bulunamadı.")
            else:
                # Call original add_image_details, passing is_pre_boxed=True
                pdf.add_image_details(search_results[0], is_pre_boxed=True)
                pdf.add_image_details(search_results[1], is_pre_boxed=True)

        else:  # Normal search report flow
            # Resim Detayları / Sonuçlar
            pdf.chapter_title("Detaylar")
            if not search_results:
                pdf.chapter_body("Bu işlem için sonuç bulunamadı.")
            else:
                for result in search_results:
                    # Call original add_image_details normally
                    pdf.add_image_details(
                        result, is_pre_boxed=False
                    )  # is_pre_boxed defaults to False

        return pdf.output()

    except Exception as e:
        print(f"PDF Raporu oluşturulurken hata oluştu: {e}")
        print(traceback.format_exc())
        return None


# Örnek Kullanım (test için):
if __name__ == "__main__":
    # Örnek arama sonuçları (gerçek verilerle değiştirilmeli)
    dummy_results = [
        {
            "title": "Şüpheli 1",
            "image_url": "https://www.gravatar.com/avatar/205e460b479e2e5b48aec07710c08d50?s=80",
            "source_url": "http://example.com/page1",
            "hash": "a1b2c3d4...",
            "count": 3,
            "score": 0.98,
            "gender": "Erkek",
            "age": 35,
            "similarity": {"name": "Ahmet Yılmaz", "rate": 0.92},
            "comprehensive_info": None,
        },
        {
            "title": "Olay Yeri Görüntüsü (Uzun Başlık Denemesi)",
            "image_url": "https://via.placeholder.com/150/0000FF/808080?text=OrnekResim2",
            "source_url": "http://example.com/news/article2/page/subpage/very/long/url",
            "hash": "e5f6g7h8...",
            "count": 1,
            "score": 0.85,
            "gender": "Kadın",
            "age": 28,
            "similarity": None,
            "comprehensive_info": {"view_rate": 0.65, "location": "Ankara"},
        },
        {
            "title": "Resim URL Yok",
            "image_url": None,
            "source_url": "http://example.com/page3",
            "hash": "i9j0k1l2...",
            "count": 5,
            "score": 0.91,
            "gender": "Erkek",
            "age": 42,
            "similarity": {"name": "Mehmet Demir", "rate": 0.78},
            "comprehensive_info": None,
        },
        {
            "title": "Hatalı Resim URL",
            "image_url": "http://invalid-url-that-does-not-exist.xyz/image.jpg",
            "source_url": "http://example.com/page4",
            "hash": "m3n4o5p6...",
            "count": 2,
            "score": None,
            "gender": None,
            "age": None,
            "similarity": None,
            "comprehensive_info": None,
        },
    ]

    pdf_bytes = generate_pdf_report("Normal Arama", "test_kullanici", dummy_results)

    if pdf_bytes:
        try:
            with open("ornek_rapor.pdf", "wb") as f:
                f.write(pdf_bytes)
            print("Örnek rapor 'ornek_rapor.pdf' adıyla oluşturuldu.")
        except Exception as e:
            print(f"PDF dosyası yazılırken hata: {e}")
    else:
        print("PDF raporu oluşturulamadı.")
