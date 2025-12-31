/**
 * Göz Tarama Sistemi - Ana JavaScript
 */

// Sayfa yükleme işlevi
function init() {
    console.log('Initializing page...');
    
    // Flash mesajlarını otomatik gizleme
    setupFlashMessages();
    
    // Tarih seçiciler için otomatik ayar
    setupDatePickers();
    
    // Form validasyonu
    setupFormValidation();
    
    // Landmark göster/gizle düğmeleri için event listener ekle
    setupLandmarkToggleButtons();
    
    console.log('Page initialization complete');
}

// Sayfa yüklendiğinde çalışacak kod
$(document).ready(function() {
    console.log('DOM fully loaded');
    
    setTimeout(function() {
        init();
    }, 500); // Sayfa tam yüklendikten 500ms sonra başlat (DOM'un tamamen hazır olması için)
});

// Alternatif yükleme metodu
window.onload = function() {
    console.log('Window fully loaded');
};

/**
 * Flash mesajlarını 5 saniye sonra otomatik gizleme
 */
function setupFlashMessages() {
    const flashMessages = document.querySelectorAll('.alert');
    flashMessages.forEach(function(message) {
        setTimeout(function() {
            // Bootstrap alert'in kapatma metodunu kullan
            const closeButton = message.querySelector('.btn-close');
            if (closeButton) {
                closeButton.click();
            } else {
                message.style.display = 'none';
            }
        }, 5000);
    });
}

/**
 * Form validasyonu ayarları
 */
function setupFormValidation() {
    const forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
}

/**
 * Tarih seçicileri ayarlama (flatpickr kullanılıyorsa)
 */
function setupDatePickers() {
    if (typeof flatpickr !== 'undefined') {
        const datePickers = document.querySelectorAll('.datepicker');
        if (datePickers.length > 0) {
            flatpickr(datePickers, {
                dateFormat: "Y-m-d",
                locale: "tr",
                allowInput: true,
                maxDate: "today"
            });
        }
    }
}

/**
 * Görsel önizleme oluşturma
 * @param {HTMLElement} input - Dosya input elementi
 * @param {HTMLElement} previewElement - Önizleme gösterilecek element
 */
function createImagePreview(input, previewElement) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            previewElement.src = e.target.result;
            previewElement.style.display = 'block';
        };
        reader.readAsDataURL(input.files[0]);
    }
}

/**
 * AJAX istek gönderme yardımcı fonksiyonu
 * @param {string} url - İstek URL'i
 * @param {string} method - İstek metodu (GET, POST vb.)
 * @param {object} data - Gönderilecek veri objesi
 * @param {function} callback - Başarılı yanıt için geri çağırma fonksiyonu
 */
function sendAjaxRequest(url, method, data, callback) {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    
    // CSRF token ekle
    const token = document.querySelector('meta[name="csrf-token"]');
    if (token) {
        xhr.setRequestHeader('X-CSRFToken', token.content);
    }
    
    xhr.onload = function() {
        if (xhr.status >= 200 && xhr.status < 300) {
            const response = JSON.parse(xhr.responseText);
            callback(response);
        } else {
            console.error('İstek hatası:', xhr.status, xhr.statusText);
        }
    };
    
    xhr.onerror = function() {
        console.error('Bağlantı hatası');
    };
    
    xhr.send(JSON.stringify(data));
}

/**
 * Face ID'sine göre landmark verilerini çek ve canvas'a çiz
 * @param {string} faceId - Yüz kimliği
 * @param {string} source - Veri kaynağı (egm/whitelist)
 * @param {HTMLCanvasElement} canvas - Çizim yapılacak canvas
 */
function fetchAndDrawLandmarks(faceId, source, canvas) {
    console.log('Fetching landmarks for face ID:', faceId, 'from source:', source);
    
    // Canvas'ı görünür yap
    canvas.style.display = 'block';
    
    // Endpoint belirleme
    let endpoint;
    if (source === 'whitelist') {
        endpoint = `/api/whitelist/face/${faceId}/landmarks`;
        console.log('Using whitelist endpoint');
    } else if (source === 'egm') {
        endpoint = `/api/egm/face/${faceId}/landmarks`;
        console.log('Using EGM endpoint');
    } else if (source === 'original') {
        // Aranan yüz için endpoint (face_id "original" olarak belirlendi)
        endpoint = '/api/face/query/landmarks';
        console.log('Using original face endpoint');
    } else if (source === 'query') {
        // Query yüzü için endpoint (aramada kullanılan yüz)
        endpoint = '/api/face/query/landmarks';
        console.log('Using query face endpoint');
    } else {
        console.error('Unknown source:', source);
        alert('Bilinmeyen kaynak: ' + source);
        return;
    }
    
    console.log('Fetching landmarks from endpoint:', endpoint);
    
    // JWT token'ı almak için meta etiketini kontrol et
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    const jwtToken = document.querySelector('meta[name="jwt-token"]')?.getAttribute('content');
    
    // Fetch isteği için başlıkları hazırla
    const headers = {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
    };
    
    // CSRF token varsa ekle
    if (csrfToken) {
        headers['X-CSRFToken'] = csrfToken;
    }
    
    // JWT token varsa ekle
    if (jwtToken) {
        headers['Authorization'] = `Bearer ${jwtToken}`;
    }
    
    // Fetch istek seçeneklerini oluştur
    const fetchOptions = {
        method: 'GET',
        headers: headers,
        credentials: 'same-origin' // Cookie'leri de gönder
    };
    
    fetch(endpoint, fetchOptions)
        .then(response => {
            console.log('Landmark API response status:', response.status);
            if (!response.ok) {
                if (response.status === 401) {
                    console.error('Authentication error: 401 Unauthorized');
                    // Kullanıcıya daha özel bir mesaj
                    throw new Error('Yetkilendirme hatası: Oturum süreniz dolmuş olabilir, lütfen sayfayı yenileyip tekrar giriş yapın.');
                }
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Landmark data received:', data);
            
            if (!data.landmarks || !Array.isArray(data.landmarks) || data.landmarks.length === 0) {
                console.error('No landmark data received or invalid format:', data);
                alert('Bu yüz için landmark verileri bulunamadı veya format geçersiz.');
                return;
            }
            
            // Canvas'a landmark noktalarını çiz
            drawLandmarksOnCanvas(data.landmarks, canvas);
        })
        .catch(error => {
            console.error('Error fetching landmark data:', error);
            alert('Landmark verileri alınırken hata oluştu: ' + error.message);
        });
}

/**
 * Landmark görünürlük butonlarını ayarla
 */
function setupLandmarkToggleButtons() {
    // Landmark gösterme özelliği devre dışı bırakılmıştır
    console.log('Landmark gösterme özelliği devre dışı bırakılmıştır');
    
    // Tüm landmark canvas'larını gizle
    document.querySelectorAll('.landmark-canvas').forEach(canvas => {
        canvas.style.display = 'none';
        canvas.classList.add('d-none');
    });
    
    // Tüm landmark butonlarını gizle
    document.querySelectorAll('.toggle-landmarks-btn').forEach(button => {
        button.style.display = 'none';
        button.classList.add('d-none');
    });
}

/**
 * Landmark noktalarını canvas üzerine çiz
 * @param {Array} landmarks - Landmark koordinatları [[x1,y1], [x2,y2], ...]
 * @param {HTMLCanvasElement} canvas - Çizim yapılacak canvas
 */
function drawLandmarksOnCanvas(landmarks, canvas) {
    // Landmark gösterme özelliği devre dışı bırakılmıştır
    console.log('Landmark çizme özelliği devre dışı bırakılmıştır');
    return;
    
    console.log('Drawing landmarks on canvas with', landmarks.length, 'points');
    
    try {
        // Referans görsel elementini bul
        const container = canvas.closest('.position-relative');
        let img;
        
        if (container) {
            img = container.querySelector('img');
        } else {
            // Container bulunamadıysa daha geniş alanda ara
            const card = canvas.closest('.card') || canvas.closest('.col') || canvas.closest('.row');
            if (card) {
                img = card.querySelector('img');
            }
            
            // Hala bulunamadıysa, document içinde ara
            if (!img) {
                const parentWithImage = canvas.parentElement;
                if (parentWithImage) {
                    img = parentWithImage.querySelector('img');
                }
            }
        }
        
        if (!img) {
            console.error('Landmark çizimi için referans görsel bulunamadı');
            return;
        }
        
        console.log('Referans görsel boyutları:', img.width, 'x', img.height);
        
        // Görsel henüz yüklenmediyse bekle
        if (img.width === 0 || img.height === 0) {
            console.warn('Görsel henüz yüklenmemiş, yüklendikten sonra tekrar deneyeceğiz');
            img.onload = function() {
                drawLandmarksOnCanvas(landmarks, canvas);
            };
            return;
        }
        
        // Canvas boyutlarını resim ile tam eşleştir
        canvas.width = img.width;
        canvas.height = img.height;
        
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Landmark veri formatını kontrol et
        if (!Array.isArray(landmarks) || landmarks.length === 0) {
            console.error('Geçersiz landmark verisi:', landmarks);
            return;
        }
        
        // Normalizasyon kontrolü - 0-1 aralığında mı yoksa piksel değerleri mi?
        const isNormalized = landmarks.every(point => 
            Array.isArray(point) && point.length >= 2 && 
            point[0] >= 0 && point[0] <= 1 && 
            point[1] >= 0 && point[1] <= 1
        );
        
        console.log('Landmark normalizasyon durumu:', isNormalized ? 'Normalize edilmiş (0-1)' : 'Piksel değerleri');
        
        // Standart face model tespiti (yaklaşık 68 nokta)
        const isStandardFaceModel = landmarks.length >= 60 && landmarks.length <= 70;
        console.log('Standart yüz modeli mi:', isStandardFaceModel ? 'Evet' : 'Hayır');
        
        // Çizim stilleri
        ctx.lineWidth = 1.5;
        const pointRadius = Math.max(2, Math.min(img.width, img.height) / 150); // Resim boyutuna göre ayarlanan nokta boyutu
        
        // ADIM 1: Tüm noktaları çiz
        landmarks.forEach((point, index) => {
            if (!Array.isArray(point) || point.length < 2) {
                console.warn('Geçersiz landmark noktası, indeks:', index);
                return;
            }
            
            // Koordinatları ayarla
            let x, y;
            if (isNormalized) {
                x = point[0] * canvas.width;
                y = point[1] * canvas.height;
            } else {
                // Piksel değerleri - resmin boyutuna göre ölçeklendirme kontrol et
                const scaleX = canvas.width / img.naturalWidth;
                const scaleY = canvas.height / img.naturalHeight;
                
                if (scaleX !== 1 || scaleY !== 1) {
                    x = point[0] * scaleX;
                    y = point[1] * scaleY;
                } else {
                    x = point[0];
                    y = point[1];
                }
            }
            
            // Noktayı çiz
            ctx.fillStyle = 'rgba(255, 255, 0, 0.8)'; // Parlak sarı
            ctx.beginPath();
            ctx.arc(x, y, pointRadius, 0, 2 * Math.PI);
            ctx.fill();
            
            // Debug için nokta numarasını göster - geliştirme amaçlı
            if (false) { // Gerektiğinde aktif et
                ctx.fillStyle = 'white';
                ctx.font = '8px Arial';
                ctx.fillText(index.toString(), x + 3, y);
            }
        });
        
        // ADIM 2: Standart 68-noktalı yüz modeli için özel çizim
        if (isStandardFaceModel) {
            // Yüz bölgelerini tanımla
            const faceRegions = [
                { name: 'jawline', range: [0, 16], color: 'rgba(255, 0, 0, 0.7)', closed: false },
                { name: 'eyebrow_right', range: [17, 21], color: 'rgba(255, 170, 0, 0.7)', closed: false },
                { name: 'eyebrow_left', range: [22, 26], color: 'rgba(255, 170, 0, 0.7)', closed: false },
                { name: 'nose_bridge', range: [27, 30], color: 'rgba(0, 0, 255, 0.7)', closed: false },
                { name: 'nose_bottom', range: [31, 35], color: 'rgba(0, 0, 255, 0.7)', closed: true },
                { name: 'eye_right', range: [36, 41], color: 'rgba(0, 255, 0, 0.7)', closed: true },
                { name: 'eye_left', range: [42, 47], color: 'rgba(0, 255, 0, 0.7)', closed: true },
                { name: 'mouth_outer', range: [48, 59], color: 'rgba(255, 0, 255, 0.7)', closed: true },
                { name: 'mouth_inner', range: [60, 67], color: 'rgba(255, 0, 255, 0.7)', closed: true }
            ];
            
            // Her yüz bölgesini çiz
            faceRegions.forEach(region => {
                drawFaceRegion(ctx, landmarks, region.range[0], region.range[1], canvas, isNormalized, region.color, region.closed);
            });
        } 
        // ADIM 3: Standart model değilse, noktaları basitçe birleştir
        else {
            ctx.strokeStyle = 'rgba(255, 0, 0, 0.7)';
            ctx.beginPath();
            
            landmarks.forEach((point, index) => {
                if (!Array.isArray(point) || point.length < 2) return;
                
                // Koordinatları hesapla
                let x, y;
                if (isNormalized) {
                    x = point[0] * canvas.width;
                    y = point[1] * canvas.height;
                } else {
                    const scaleX = canvas.width / img.naturalWidth;
                    const scaleY = canvas.height / img.naturalHeight;
                    
                    if (scaleX !== 1 || scaleY !== 1) {
                        x = point[0] * scaleX;
                        y = point[1] * scaleY;
                    } else {
                        x = point[0];
                        y = point[1];
                    }
                }
                
                if (index === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            });
            
            ctx.stroke();
        }
        
        console.log('Landmark çizimi başarıyla tamamlandı');
    } catch (error) {
        console.error('Landmark çizimi sırasında hata:', error);
    }
}

/**
 * Yüz bölgesi çizimi - belirli bir landmark aralığı için
 * @param {CanvasRenderingContext2D} ctx - Canvas çizim bağlamı
 * @param {Array} landmarks - Tüm landmark noktaları
 * @param {Number} startIdx - Başlangıç indeksi
 * @param {Number} endIdx - Bitiş indeksi
 * @param {HTMLCanvasElement} canvas - Canvas elementi
 * @param {Boolean} isNormalized - Koordinatlar normalize edilmiş mi
 * @param {String} color - Çizgi rengi
 * @param {Boolean} closePath - Path kapatılsın mı
 */
function drawFaceRegion(ctx, landmarks, startIdx, endIdx, canvas, isNormalized, color, closePath) {
    try {
        if (startIdx < 0 || endIdx >= landmarks.length || startIdx > endIdx) {
            console.warn('Geçersiz bölge indeksleri:', startIdx, endIdx);
            return;
        }
        
        ctx.strokeStyle = color || 'rgba(255, 0, 0, 0.7)';
        ctx.beginPath();
        
        // Bölge noktalarını dolaş
        for (let i = startIdx; i <= endIdx; i++) {
            const point = landmarks[i];
            if (!Array.isArray(point) || point.length < 2) continue;
            
            // Koordinatları hesapla
            let x, y;
            if (isNormalized) {
                x = point[0] * canvas.width;
                y = point[1] * canvas.height;
            } else {
                const scaleX = canvas.width / canvas.width;
                const scaleY = canvas.height / canvas.height;
                
                if (scaleX !== 1 || scaleY !== 1) {
                    x = point[0] * scaleX;
                    y = point[1] * scaleY;
                } else {
                    x = point[0];
                    y = point[1];
                }
            }
            
            if (i === startIdx) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        
        // Yolu kapat (opsiyonel)
        if (closePath) {
            ctx.closePath();
        }
        
        ctx.stroke();
    } catch (error) {
        console.error('Yüz bölgesi çizimi sırasında hata:', error);
    }
} 