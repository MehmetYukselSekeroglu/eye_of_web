/**
 * Yüz Kutusu ve Landmark Çizim Yardımcı Fonksiyonları
 */

/**
 * Yüz kutusunu (bbox) resme çizer
 * @param {Image} imgElement - Görsel HTML elementi
 * @param {Array} bboxCoords - Koordinatlar [left, top, right, bottom]
 * @param {String} color - Kutu rengi (varsayılan: '#00ff00')
 * @param {Number} lineWidth - Çizgi kalınlığı (varsayılan: 3)
 */
function drawFaceBoundingBox(imgElement, bboxCoords, color = '#00ff00', lineWidth = 3) {
    if (!imgElement || !bboxCoords || bboxCoords.length !== 4) {
        console.error('Geçersiz görsel veya bbox verileri');
        return;
    }
    
    // Canvas oluştur
    const canvas = document.createElement('canvas');
    canvas.width = imgElement.naturalWidth || imgElement.width;
    canvas.height = imgElement.naturalHeight || imgElement.height;
    
    // Görselin boyutlarına göre ölçeklendirme faktörleri
    const scaleX = canvas.width / imgElement.width;
    const scaleY = canvas.height / imgElement.height;
    
    // Canvas üzerine görseli çiz
    const ctx = canvas.getContext('2d');
    ctx.drawImage(imgElement, 0, 0, canvas.width, canvas.height);
    
    // Bbox koordinatlarını ölçeklendir
    const [left, top, right, bottom] = bboxCoords.map((coord, index) => {
        return Math.round(coord * (index % 2 === 0 ? scaleX : scaleY));
    });
    
    // Kutu çiz
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.strokeRect(left, top, right - left, bottom - top);
    
    // Canvas'ı base64 olarak dönüştür
    return canvas.toDataURL('image/jpeg');
}

/**
 * 2D Landmark noktalarını resme çizer
 * @param {Image} imgElement - Görsel HTML elementi
 * @param {Array} landmarkPoints - Landmark noktaları [[x1,y1], [x2,y2], ...]
 * @param {String} color - Nokta rengi (varsayılan: '#00ff00')
 * @param {Number} pointRadius - Nokta yarıçapı (varsayılan: 2)
 */
function drawFaceLandmarks(imgElement, landmarkPoints, color = '#00ff00', pointRadius = 2) {
    if (!imgElement || !landmarkPoints || !Array.isArray(landmarkPoints) || landmarkPoints.length === 0) {
        console.error('Geçersiz görsel veya landmark verileri');
        return;
    }
    
    // Canvas oluştur
    const canvas = document.createElement('canvas');
    canvas.width = imgElement.naturalWidth || imgElement.width;
    canvas.height = imgElement.naturalHeight || imgElement.height;
    
    // Görselin boyutlarına göre ölçeklendirme faktörleri
    const scaleX = canvas.width / imgElement.width;
    const scaleY = canvas.height / imgElement.height;
    
    // Canvas üzerine görseli çiz
    const ctx = canvas.getContext('2d');
    ctx.drawImage(imgElement, 0, 0, canvas.width, canvas.height);
    
    // Landmarks normalize edilmiş mi (0-1 aralığında) kontrol et
    const isNormalized = landmarkPoints.every(point => 
        Array.isArray(point) && point.length >= 2 && 
        point[0] >= 0 && point[0] <= 1 && 
        point[1] >= 0 && point[1] <= 1
    );
    
    // Her landmark noktası için daire çiz
    ctx.fillStyle = color;
    landmarkPoints.forEach(point => {
        if (Array.isArray(point) && point.length >= 2) {
            let x, y;
            if (isNormalized) {
                // Normalize edilmiş koordinatları (0-1) piksel koordinatlarına dönüştür
                x = Math.round(point[0] * canvas.width);
                y = Math.round(point[1] * canvas.height);
            } else {
                // Piksel koordinatlarını ölçeklendir
                x = Math.round(point[0] * scaleX);
                y = Math.round(point[1] * scaleY);
            }
            
            ctx.beginPath();
            ctx.arc(x, y, pointRadius, 0, 2 * Math.PI);
            ctx.fill();
        }
    });
    
    // Canvas'ı base64 olarak dönüştür
    return canvas.toDataURL('image/jpeg');
}

/**
 * NumPy float32 dizisini JavaScript dizisine dönüştürür
 * Base64 formatındaki numpy verisi
 * @param {String} base64Data - Veritabanından gelen base64 formatındaki binary veri
 * @param {String} dataType - Verinin türü: 'bbox' (4 değer) veya 'landmarks' (n×2 dizisi)
 * @returns {Array} - JavaScript dizisi olarak veri
 */
function parseNumPyData(base64Data, dataType = 'bbox') {
    if (!base64Data) {
        return null;
    }
    
    try {
        // Base64'ü binary'e dönüştür
        const binaryString = atob(base64Data);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        
        // Float32 dizisi oluştur
        const floatArray = new Float32Array(bytes.buffer);
        
        if (dataType === 'bbox') {
            // BBox: [left, top, right, bottom]
            return Array.from(floatArray);
        } else if (dataType === 'landmarks') {
            // Landmarks: [[x1,y1], [x2,y2], ...]
            const landmarks = [];
            for (let i = 0; i < floatArray.length; i += 2) {
                if (i + 1 < floatArray.length) {
                    landmarks.push([floatArray[i], floatArray[i + 1]]);
                }
            }
            return landmarks;
        }
        
        return Array.from(floatArray);
    } catch (error) {
        console.error('NumPy verisi ayrıştırılamadı:', error);
        return null;
    }
} 