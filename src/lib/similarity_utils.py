# lib/similarity_utils.py
import numpy as np

try:
    from numba import jit, float64, int64 # Tipleri import edelim
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    # Numba yoksa boş bir dekoratör tanımla
    class FakeNumba:
        def jit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        # Diğer Numba tipleri için de sahte tanımlar eklenebilir
        float64 = float
        int64 = int
    numba = FakeNumba()
    jit = numba.jit
    float64 = numba.float64
    print("Uyarı: Numba kütüphanesi bulunamadı. Benzerlik hesaplamaları için Numba hızlandırması kullanılamayacak.")

# YENİ: PyTorch import
try:
    import torch
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    print("Uyarı: PyTorch kütüphanesi bulunamadı. CUDA benzerlik hesaplaması yapılamayacak.")

# --- Numba Hızlandırılmış Hesaplamalar ---
@jit('float64(float64[:], float64[:])', nopython=True, fastmath=True)
def cosine_similarity_numba(vec1: np.ndarray, vec2: np.ndarray) -> np.float64:
    """İki NumPy vektörü arasında Numba ile hızlandırılmış kosinüs benzerliğini hesaplar."""
    # Vektörlerin float olduğundan emin ol (Numba bazen tip konusunda katı olabilir)
    # Bu adım genellikle gereksizdir eğer gelen veriler zaten float ise, ancak güvenlik için kalabilir.
    # vec1 = vec1.astype(np.float64)
    # vec2 = vec2.astype(np.float64)

    # Sıfır vektör kontrolü (norm hesaplamadan önce)
    norm_vec1 = np.linalg.norm(vec1)
    norm_vec2 = np.linalg.norm(vec2)

    # Eğer herhangi bir vektörün normu sıfır veya çok küçükse, benzerlik 0'dır.
    if norm_vec1 < 1e-10 or norm_vec2 < 1e-10:
        return np.float64(0.0)

    dot_product = np.dot(vec1, vec2)

    # Benzerliği hesapla
    similarity = dot_product / (norm_vec1 * norm_vec2)

    # Kırpma işlemini manuel olarak yap (np.clip skalerlerde nopython modunda sorun çıkarıyor)
    if similarity > 1.0:
        return np.float64(1.0)
    elif similarity < -1.0:
        return np.float64(-1.0)
    else:
        # Zaten float64 döndürmesini bekliyoruz, ancak emin olmak için cast edelim
        return np.float64(similarity)

@jit('float64(float64[:], float64[:])', nopython=True, fastmath=True)
def euclidean_similarity_numba(vec1: np.ndarray, vec2: np.ndarray) -> np.float64:
    """İki NumPy vektörü arasında Numba ile hızlandırılmış Öklid benzerliğini hesaplar."""
    return np.linalg.norm(vec1 - vec2)

@jit('float64(float64[:], float64[:])', nopython=True, fastmath=True)
def manhattan_similarity_numba(vec1: np.ndarray, vec2: np.ndarray) -> np.float64:
    """İki NumPy vektörü arasında Numba ile hızlandırılmış Manhattan benzerliğini hesaplar (1 / (1 + mesafe))."""
    distance = np.sum(np.abs(vec1 - vec2))
    similarity_score = np.float64(0.0) # Default
    if distance < 1e-10:
        similarity_score = np.float64(1.0)
    else:
        similarity_score = np.float64(1.0 / (1.0 + distance))

    # <<< YENİ LOGLAMA (Sadece test için, Numba nopython modunda print çalışmaz, ama jit dışı testte işe yarar) >>>
    # Numba nopython=True modunda print çalışmayacağı için bu logları doğrudan göremeyebiliriz.
    # Ancak kodun mantığını test etmek için buraya ekliyorum.
    # Gerçek değerleri görmek için bu fonksiyonu Python'da ayrı test etmek gerekebilir.
    # print(f"  [Manhattan] Mesafe: {distance:.4f}, Benzerlik: {similarity_score:.4f}")
    # <<< ----------- >>>

    return similarity_score

# Desteklenen algoritmalar ve Numba fonksiyonları eşleştirmesi
SIMILARITY_FUNCTIONS_NUMBA = {
    'cosine': cosine_similarity_numba,
    'euclidean': euclidean_similarity_numba,
    'manhattan': manhattan_similarity_numba,
}

# --- CUDA Hızlandırılmış Hesaplamalar (PyTorch ile) ---
def cosine_similarity_cuda(vec1_tensor: torch.Tensor, vec2_tensor: torch.Tensor) -> float:
    """İki PyTorch tensörü arasında kosinüs benzerliğini CUDA üzerinde hesaplar."""
    # Vektörleri normalize et (opsiyonel, F.cosine_similarity zaten yapar)
    # vec1_norm = F.normalize(vec1_tensor, p=2, dim=0)
    # vec2_norm = F.normalize(vec2_tensor, p=2, dim=0)
    # return torch.dot(vec1_norm, vec2_norm).item()
    # F.cosine_similarity 1D tensörler için (batch_size=1 gibi düşün) unsqueeze(0) gerektirir
    return F.cosine_similarity(vec1_tensor.unsqueeze(0), vec2_tensor.unsqueeze(0)).item()

def euclidean_similarity_cuda(vec1_tensor: torch.Tensor, vec2_tensor: torch.Tensor) -> float:
    """İki PyTorch tensörü arasında Öklid benzerliğini CUDA üzerinde hesaplar."""
    distance = torch.dist(vec1_tensor, vec2_tensor, p=2).item()
    if distance < 1e-10:
        return 1.0
    return 1.0 / (1.0 + distance)

def manhattan_similarity_cuda(vec1_tensor: torch.Tensor, vec2_tensor: torch.Tensor) -> float:
    """İki PyTorch tensörü arasında Manhattan benzerliğini CUDA üzerinde hesaplar."""
    distance = torch.dist(vec1_tensor, vec2_tensor, p=1).item() # p=1 Manhattan mesafesidir
    if distance < 1e-10:
        return 1.0
    return 1.0 / (1.0 + distance)

SIMILARITY_FUNCTIONS_CUDA = {
    'cosine': cosine_similarity_cuda,
    'euclidean': euclidean_similarity_cuda,
    'manhattan': manhattan_similarity_cuda
}

# --- Genel Hesaplama Fonksiyonu ---
def calculate_similarity(vec1: np.ndarray, vec2: np.ndarray, algorithm: str = 'cosine', use_cuda: bool = False) -> float:
    """
    İki vektör arasında belirtilen algoritma ile benzerliği hesaplar.
    Gerçek CUDA kullanımı `current_app.config['USE_CUDA']` değerine bağlıdır.

    Args:
        vec1: Birinci yüz vektörü (NumPy array).
        vec2: İkinci yüz vektörü (NumPy array).
        algorithm: Kullanılacak benzerlik algoritması ('cosine', 'euclidean', 'manhattan').
        use_cuda: CUDA (GPU) hızlandırması denenip denenmeyeceği (config True ise).

    Returns:
        Hesaplanan benzerlik skoru (float).

    Raises:
        ValueError: Desteklenmeyen bir algoritma adı verilirse.
        NotImplementedError: İstenen algoritma için CUDA implementasyonu yoksa.
    """
    # print(f"--- calculate_similarity çağrıldı: algorithm='{algorithm}', use_cuda_request={use_cuda} ---")

    # Flask context'i dışındaysak (örn. testler) current_app kullanılamaz.
    # Bu durumda use_cuda'nın False olduğunu varsayalım veya farklı bir kontrol mekanizması kullanalım.
    try:
        from flask import current_app
        actual_use_cuda = current_app.config.get('USE_CUDA', False)
        pytorch_available_runtime = current_app.config.get('PYTORCH_AVAILABLE', False)
    except RuntimeError:
        print("--- Uyarı: Flask context dışında çalışılıyor, CUDA kullanılamayacak. ---")
        actual_use_cuda = False
        pytorch_available_runtime = PYTORCH_AVAILABLE # Global kontrolü kullan

    # print(f"--- Gerçek CUDA Durumu (config): {actual_use_cuda}, PyTorch Durumu: {pytorch_available_runtime} ---")

    # Vektörlerin NumPy array olduğundan emin ol 
    if not isinstance(vec1, np.ndarray):
        vec1 = np.array(vec1, dtype=np.float32)
    if not isinstance(vec2, np.ndarray):
        vec2 = np.array(vec2, dtype=np.float32)

    if vec1.shape != vec2.shape:
        raise ValueError(f"Vektör boyutları eşleşmiyor: {vec1.shape} vs {vec2.shape}")

    selected_algorithm = algorithm.lower()

    # CUDA Kullanımı Denemesi (Eğer istendi ve Mümkünse)
    if use_cuda and actual_use_cuda and pytorch_available_runtime:
        # print(f"--- CUDA ile hesaplama deneniyor ({selected_algorithm})... ---")
        cuda_func = SIMILARITY_FUNCTIONS_CUDA.get(selected_algorithm)
        if cuda_func:
            try:
                # NumPy array'lerini PyTorch tensorlerine çevir ve GPU'ya gönder
                # .cuda() yerine .to('cuda') daha modern bir yaklaşımdır.
                # Float32 kullandığımızdan emin olalım
                t1 = torch.from_numpy(vec1.astype(np.float32)).to('cuda')
                t2 = torch.from_numpy(vec2.astype(np.float32)).to('cuda')
                
                result = cuda_func(t1, t2)
                # print(f"--- CUDA hesaplaması başarılı ({selected_algorithm}). Sonuç: {result:.4f} ---")
                return float(result)
            except NotImplementedError:
                 print(f"--- UYARI: '{selected_algorithm}' için CUDA implementasyonu yok. Numba'ya fallback yapılıyor. ---") # Uyarı kalsın
            except Exception as cuda_err:
                print(f"--- HATA: CUDA hesaplaması sırasında hata: {cuda_err}. Numba'ya fallback yapılıyor. ---") # Hata mesajı kalsın
                # CUDA hatasında Numba'ya düşebiliriz.
        else:
            print(f"--- UYARI: '{selected_algorithm}' için CUDA fonksiyonu bulunamadı. Numba'ya fallback yapılıyor. ---") # Uyarı kalsın

    # Numba (veya NumPy) Fallback
    # print(f"--- Numba/NumPy ile hesaplama yapılıyor ({selected_algorithm})... ---")
    numba_func = SIMILARITY_FUNCTIONS_NUMBA.get(selected_algorithm)
    if numba_func and NUMBA_AVAILABLE:
        # print(f"--- Numba fonksiyonu kullanılıyor: {numba_func.__name__} ---")
        vec1_f64 = vec1.astype(np.float64)
        vec2_f64 = vec2.astype(np.float64)
        result = numba_func(vec1_f64, vec2_f64)
        return float(result)
    elif numba_func: # Numba kurulu değilse NumPy'ı manuel kullanalım (calculate_similarity içindeki eski kod)
        # print(f"--- Numba mevcut değil, NumPy kullanılıyor: {selected_algorithm} ---")
        if selected_algorithm == 'cosine':
            dot = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            if norm1 < 1e-10 or norm2 < 1e-10: return 0.0
            similarity = dot / (norm1 * norm2)
            return float(np.clip(similarity, -1.0, 1.0))
        elif selected_algorithm == 'euclidean':
            distance = np.linalg.norm(vec1 - vec2)
            if distance < 1e-10: return 1.0
            return 1.0 / (1.0 + distance)
        elif selected_algorithm == 'manhattan':
            distance = np.sum(np.abs(vec1 - vec2))
            if distance < 1e-10: return 1.0
            return 1.0 / (1.0 + distance)
        else: # Bu durum aslında yaşanmamalı ama güvenlik için ekleyelim
            raise ValueError(f"Desteklenmeyen algoritma: '{selected_algorithm}'")
    else:
        # print(f"--- HATA: Desteklenmeyen algoritma '{selected_algorithm}', ValueError yükseltilecek. ---") # Hata zaten yükseltiliyor.
        raise ValueError(f"Desteklenmeyen benzerlik algoritması: '{algorithm}'. Seçenekler: {list(SIMILARITY_FUNCTIONS_NUMBA.keys())}")

# Test bloğu
if __name__ == '__main__':
    vec_a = np.array([1.0, 0.5, 0.2], dtype=np.float64)
    vec_b = np.array([0.8, 0.6, 0.1], dtype=np.float64)
    vec_c = np.array([-1.0, -0.5, -0.2], dtype=np.float64)
    vec_zero = np.array([0.0, 0.0, 0.0], dtype=np.float64)

    print(f"Numba Kullanılabilir: {NUMBA_AVAILABLE}")

    print("--- Kosinüs Benzerliği --- ")
    print(f"Benzerlik (A, B): {calculate_similarity(vec_a, vec_b, algorithm='cosine')}")
    print(f"Benzerlik (A, A): {calculate_similarity(vec_a, vec_a, algorithm='cosine')}")
    print(f"Benzerlik (A, C): {calculate_similarity(vec_a, vec_c, algorithm='cosine')}")

    print("--- Öklid Benzerliği --- ")
    print(f"Benzerlik (A, B): {calculate_similarity(vec_a, vec_b, algorithm='euclidean')}")
    print(f"Benzerlik (A, A): {calculate_similarity(vec_a, vec_a, algorithm='euclidean')}")
    print(f"Benzerlik (A, C): {calculate_similarity(vec_a, vec_c, algorithm='euclidean')}")

    print("--- Manhattan Benzerliği --- ")
    print(f"Benzerlik (A, B): {calculate_similarity(vec_a, vec_b, algorithm='manhattan')}")
    print(f"Benzerlik (A, A): {calculate_similarity(vec_a, vec_a, algorithm='manhattan')}")
    print(f"Benzerlik (A, C): {calculate_similarity(vec_a, vec_c, algorithm='manhattan')}")

    print("--- Sıfır Vektör Testleri --- ")
    print(f"Kosinüs (A, Zero): {calculate_similarity(vec_a, vec_zero, algorithm='cosine')}")
    print(f"Öklid (A, Zero): {calculate_similarity(vec_a, vec_zero, algorithm='euclidean')}")
    print(f"Manhattan (A, Zero): {calculate_similarity(vec_a, vec_zero, algorithm='manhattan')}") 