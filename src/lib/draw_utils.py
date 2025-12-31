import cv2
import numpy as np
import base64
import io
from PIL import Image

def landmarks_rectangle(img, box, color=(0, 255, 0), thickness=2):
    """
    Görüntüye dikdörtgen sınırlayıcı kutu çizer
    
    Args:
        img: numpy.ndarray - OpenCV görüntüsü
        box: list/tuple/array - [x1, y1, x2, y2] formatında sınırlayıcı kutu koordinatları
        color: tuple - BGR renk formatında (varsayılan: yeşil)
        thickness: int - Çizgi kalınlığı
    
    Returns:
        numpy.ndarray - Üzerine kutu çizilmiş görüntü
    """
    if img is None or box is None:
        return img
    
    # box koordinatlarını integer'a dönüştür
    box = [int(round(coord)) for coord in box]
    x1, y1, x2, y2 = box
    
    # Kutuyu görüntüye çiz
    return cv2.rectangle(img.copy(), (x1, y1), (x2, y2), color, thickness)

def landmarks_rectangle_2d(img, landmarks, radius=2, color=(0, 255, 0), thickness=-1):
    """
    Görüntüye 2D landmark noktalarını çizer
    
    Args:
        img: numpy.ndarray - OpenCV görüntüsü
        landmarks: numpy.ndarray - Şekli (n, 2) olan landmark noktaları
        radius: int - Nokta yarıçapı
        color: tuple - BGR renk formatında (varsayılan: yeşil)
        thickness: int - Çizgi kalınlığı (negatif değerler dolgu için)
    
    Returns:
        numpy.ndarray - Üzerine landmark noktaları çizilmiş görüntü
    """
    if img is None or landmarks is None:
        return img
    
    img_copy = img.copy()
    
    # Landmark verisinin şeklini kontrol et
    landmarks = np.array(landmarks)
    if len(landmarks.shape) != 2 or landmarks.shape[1] != 2:
        print(f"Uyarı: Geçersiz landmark şekli {landmarks.shape}. Beklenen: (n, 2)")
        if len(landmarks.shape) == 1 and landmarks.size % 2 == 0:
            # 1D diziyi (n, 2) şekline dönüştür
            landmarks = landmarks.reshape(-1, 2)
        else:
            return img_copy
    
    # Landmark noktalarının normalize edilmiş olup olmadığını kontrol et (0-1 aralığı)
    is_normalized = np.all((landmarks >= 0) & (landmarks <= 1))
    
    height, width = img.shape[:2]
    
    for i in range(landmarks.shape[0]):
        x, y = landmarks[i]
        
        # Eğer noktalar normalize edilmişse (0-1 aralığında), görüntü boyutuna ölçeklendir
        if is_normalized:
            x = int(round(x * width))
            y = int(round(y * height))
        else:
            x = int(round(x))
            y = int(round(y))
        
        # Koordinatlar görüntü sınırları içindeyse nokta çiz
        if 0 <= x < width and 0 <= y < height:
            cv2.circle(img_copy, (x, y), radius, color, thickness)
    
    return img_copy

def base64_to_numpy(base64_str):
    """
    Base64 formatındaki veriyi numpy dizisine dönüştürür
    
    Args:
        base64_str: str - Base64 formatındaki veri
    
    Returns:
        numpy.ndarray - Çözümlenmiş numpy dizisi
    """
    try:
        # Base64 formatını düzelt (varsa header'ı kaldır)
        if ',' in base64_str:
            base64_str = base64_str.split(',')[1]
        
        # Base64'ten binary'ye dönüştür
        binary_data = base64.b64decode(base64_str)
        
        # NumPy dizisi oluştur (float32 tipinde)
        if len(binary_data) % 4 == 0:  # Float32 için 4 byte kontrol
            return np.frombuffer(binary_data, dtype=np.float32)
        else:
            print(f"Uyarı: Veri boyutu float32 için uygun değil: {len(binary_data)} byte")
            return None
    except Exception as e:
        print(f"Base64 veri dönüşüm hatası: {str(e)}")
        return None

def base64_to_bbox(base64_str):
    """
    Base64 formatındaki bbox verisini [x1, y1, x2, y2] formatına dönüştürür
    
    Args:
        base64_str: str - Base64 formatındaki bbox verisi
    
    Returns:
        list - [x1, y1, x2, y2] formatında bbox koordinatları
    """
    np_array = base64_to_numpy(base64_str)
    if np_array is not None and len(np_array) == 4:
        return np_array.tolist()
    return None

def base64_to_landmarks(base64_str):
    """
    Base64 formatındaki landmark verisini (n, 2) numpy dizisine dönüştürür
    
    Args:
        base64_str: str - Base64 formatındaki landmark verisi
    
    Returns:
        numpy.ndarray - Şekli (n, 2) olan landmark noktaları
    """
    np_array = base64_to_numpy(base64_str)
    if np_array is not None and len(np_array) % 2 == 0:
        return np_array.reshape(-1, 2)
    return None

def base64_image_to_opencv(base64_image):
    """
    Base64 formatındaki görüntüyü OpenCV formatına dönüştürür
    
    Args:
        base64_image: str - Base64 formatındaki görüntü
    
    Returns:
        numpy.ndarray - OpenCV formatında görüntü (BGR)
    """
    try:
        # Base64 formatını düzelt (varsa header'ı kaldır)
        if ',' in base64_image:
            base64_image = base64_image.split(',')[1]
        
        # Base64'ten binary'ye dönüştür
        img_data = base64.b64decode(base64_image)
        
        # Binary'yi OpenCV görüntüsüne dönüştür
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        return img
    except Exception as e:
        print(f"Base64 görüntü dönüşüm hatası: {str(e)}")
        return None

def opencv_to_base64(img):
    """
    OpenCV görüntüsünü Base64 formatına dönüştürür
    
    Args:
        img: numpy.ndarray - OpenCV formatında görüntü
    
    Returns:
        str - Base64 formatında görüntü
    """
    try:
        # OpenCV görüntüsünü JPEG formatına dönüştür
        _, buffer = cv2.imencode('.jpg', img)
        
        # JPEG'i Base64'e dönüştür
        base64_str = base64.b64encode(buffer).decode('utf-8')
        
        return f"data:image/jpeg;base64,{base64_str}"
    except Exception as e:
        print(f"OpenCV görüntü dönüşüm hatası: {str(e)}")
        return None 