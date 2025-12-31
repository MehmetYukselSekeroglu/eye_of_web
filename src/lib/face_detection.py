#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cv2
import numpy as np
import base64
import traceback

def extract_and_encode_faces(image):
    """
    Bir görüntüden yüzleri algılar ve kodlar
    
    Args:
        image: Numpy dizisi olarak görüntü
        
    Returns:
        list: Algılanan yüzlerin listesi (embedding vektörleri)
    """
    # Bu fonksiyon proje ihtiyaçlarına göre doldurulabilir
    # Şu an için boş bir şekilde tanımlanmıştır
    return []

def draw_face_box(image_data, facebox, color=(0, 255, 0), thickness=4):
    """
    Görsel üzerine yüz kutusu çizer
    
    Args:
        image_data: NumPy dizisi olarak görsel verisi (OpenCV formatında)
        facebox: Yüz kutusu koordinatları [x1, y1, x2, y2]
        color: BGR renk değeri, varsayılan yeşil
        thickness: Çizgi kalınlığı
        
    Returns:
        str: Yüz kutusu çizilmiş görselin base64 kodlanmış JPEG verisi
    """
    try:
        # NumPy dizisi kontrolü
        if image_data is None or image_data.size == 0 or not facebox:
            print("draw_face_box: Geçersiz girdi (görsel veya facebox yok)")
            # Geçersiz durumda ne döndürmeli? Belki None veya Exception?
            # Şimdilik None döndürelim, çağıran yer kontrol etsin.
            return None
            
        # Gelen verinin zaten NumPy dizisi olduğunu varsayıyoruz
        img = image_data
        
        # Görüntü boyutları
        height, width = img.shape[:2]
        
        # Facebox koordinatlarını hassas bir şekilde al
        # Tam sayı değerlere dönüştürme yöntemini iyileştiriyoruz
        x1, y1, x2, y2 = [float(coord) for coord in facebox]
        
        # Koordinatları görüntü boyutuna göre oranla
        # Burada orijinal koordinatların oranını koruyoruz
        x1 = max(0, min(int(round(x1)), width - 1))
        y1 = max(0, min(int(round(y1)), height - 1))
        x2 = max(0, min(int(round(x2)), width - 1))
        y2 = max(0, min(int(round(y2)), height - 1))
        
        # Yüz kutusunu çiz
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
        
        # Tekrar base64'e dönüştür - kaliteyi artırabiliriz
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, 95]
        success, buffer = cv2.imencode('.jpg', img, encode_params)
        if not success:
            print("draw_face_box: JPEG encode edilemedi")
            return None # Hata durumunda None dön
            
        new_image_data = base64.b64encode(buffer).decode('utf-8')
        return new_image_data
        
    except Exception as e:
        print(f"Yüz kutusu çizme hatası: {str(e)}")
        traceback.print_exc()
        # Hata durumunda orijinal görseli döndür
        return None # Hata durumunda None dön

    return None # Hata durumunda None dön 