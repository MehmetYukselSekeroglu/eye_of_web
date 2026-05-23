# Face Security V3

Çoklu kameralı yüz tanıma ve ALPR (otomatik plaka tanıma) tabanlı yerel
güvenlik gözetim sistemi. 25 RTSP kameraya kadar destekler, tanınan/tanınmayan
yüzleri loglar, Telegram üzerinden bildirim gönderir, isteğe bağlı plaka
tanıma sekmesi içerir.

## Özellikler

- **Yüz tanıma:** InsightFace `buffalo_s` modeli ile gerçek zamanlı yüz tespiti
  ve embedding tabanlı tanıma (kosinüs benzerliği)
- **Çoklu kamera:** 25 IP kameraya kadar destek (RTSP), aktif kamera UI'dan
  seçilir, otomatik devriye (patrol) modu mevcut
- **Plaka tanıma (ALPR):** Ayrı sekmede YOLO + EasyOCR + 3 OCR pipeline +
  oylama tabanlı plaka tanıma
- **Bildirim:** Telegram bot entegrasyonu (text + foto), uzaktan komut desteği
- **Yerel-öncelikli:** Tüm veriler yerel diskte tutulur, bulut gönderimi
  yoktur (sadece kullanıcının kendi Telegram bot'una)
- **Snapshot yönetimi:** Otomatik temizleme (yaş + dosya sayısı limiti)

## Sistem Gereksinimleri

- **OS:** Linux (Mint/Ubuntu üzerinde test edildi)
- **Python:** 3.10+ (3.12 önerilir)
- **Disk:** ~4 GB (model dosyaları + bağımlılıklar dahil)
- **RAM:** 4 GB minimum, 8 GB önerilir (InsightFace + YOLO yüklü iken)
- **GPU:** Opsiyonel — `onnxruntime-gpu` ile CUDA hızlandırma desteklenir
  (NVIDIA only, requirements.txt yorum satırından aktif edilir)
- **Kameralar:** RTSP destekli IP kameralar (Hikvision, Dahua, ZKTeco, vs.)

## Kurulum

### 1. Bağımlılıklar

Uygulamanın kendisi sistem Python'ında çalışır:

    sudo apt install python3 python3-pip python3-tk
    pip install --user -r requirements.txt

`python3-tk` Tkinter UI için gereklidir (bazı dağıtımlarda ayrı paket).

GPU desteği için `requirements.txt` içindeki `onnxruntime-gpu` satırını
aktif edin (yorumu kaldırın).

### 2. Yapılandırma

    cp .env.example .env

`.env` dosyasını düzenleyin:

| Bölüm | Değişkenler | Açıklama |
|-------|-------------|----------|
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | BotFather'dan alın; boş bırakılırsa Telegram devre dışı kalır |
| Kameralar | `CAM_01_URL` ... `CAM_25_URL` | RTSP URL'leri. Kullanılmayan kameraları boş bırakın |
| Plaka kamerası | `PLATE_CAM_URL` | Plaka tanıma sekmesinin kullanacağı RTSP URL |
| Eşik değerleri | `THRESHOLD`, `INFERENCE_FPS`, `SNAPSHOT_COOLDOWN`, vb. | Varsayılanlar çoğu kullanım için uygundur |
| Yollar | `DATABASE_PATH`, `KNOWN_PATH`, `UNKNOWN_PATH`, `LOG_DIR` | Boş bırakılırsa proje kök dizinine göre varsayılan göreceli yollar kullanılır |

Tam değişken listesi için `.env.example` dosyasına bakın.

### 3. Bilinen Yüzler Veritabanı

Sistem **dosya tabanlı** bir veritabanı kullanır — SQL yoktur. Tanınmasını
istediğiniz kişilerin fotoğraflarını `database/` klasörüne yerleştirin.

Örnek dizin yapısı:

    database/
    |-- ahmet.jpg
    |-- ayse_1.jpg          (aynı kişiye ait birden fazla fotoğraf)
    |-- ayse_2.jpg          (otomatik olarak ortalama embedding alınır)
    `-- mehmet.jpg

İsimlendirme kuralı: `{isim}.jpg` veya `{isim}_{sayı}.jpg`. Aynı isimle
başlayan fotoğraflar tek kişi olarak gruplanır ve embedding'leri ortalanır.

> **Önemli:** `database/` klasöründeki yüz fotoğrafları **versiyon
> kontrolüne dahil edilmez** (`.gitignore` bunu kapsar). Yüz verileri
> kişisel veridir (KVKK/GDPR kapsamında biyometrik özel veri);
> commit'lenmesi yasal risk doğurur. Her geliştirici/kullanıcı kendi
> `database/` klasörünü lokal olarak doldurur.

İlk çalıştırmada `embeddings_cache.pkl` otomatik oluşturulur. Fotoğraf
ekleyip/silince UI üzerinden "Veritabanını Yenile" yapabilir veya uygulamayı
yeniden başlatabilirsiniz (MD5 değişimi otomatik tespit edilir).

### 4. Plaka Tanıma Modeli (Opsiyonel)

Plaka tanıma özelliğini kullanmak isterseniz, YOLO tabanlı plaka tespit
modelini `models/` klasörüne yerleştirin:

    models/
    `-- license_plate_detector.pt

Bu model GitHub veya HuggingFace üzerinde halka açık olarak bulunabilir.
Aramak için: "license plate detector yolov8" anahtar kelimeleri.

Model dosyası repo'ya dahil değildir (boyut nedeniyle). `.env` içinde
`PLATE_YOLO_MODEL` değişkeni varsayılan olarak `models/license_plate_detector.pt`
yolunu işaret eder.

Plaka tanıma kullanmıyorsanız `.env` içindeki `PLATE_YOLO_MODEL` satırını
boş bırakın — sistem ultralytics yolov8n modelini otomatik indirir
(araç tespiti çalışır, plaka OCR çalışmaz).

### 5. Çalıştırma

    ./launch.sh

Veya doğrudan:

    python3 main.py

İlk açılışta:

- **PIN istemi gelir.** İlk çalıştırmada `auth_config.json` yoksa varsayılan
  PIN **`1234`** ile dosya oluşturulur.
- **Kurulumdan sonra mutlaka PIN'i değiştirin.** UI üzerinden ayarlanabilir.

## İlk Açılış Sonrası Önemli Adımlar

1. **PIN'i değiştirin** — varsayılan `1234` güvensizdir
2. **Kamera başına benzersiz şifre** kullanın — birden fazla kamera aynı
   şifreyi paylaşırsa bir kameranın ele geçirilmesi diğerlerini de tehlikeye
   atar
3. **`.env` dosyasını asla versiyon kontrolüne eklemeyin** — `.gitignore`
   bunu zaten kapsar
4. **Telegram bot token'ını gizli tutun** — sızdığında BotFather üzerinden
   `/revoke` ile iptal edip yeniden alabilirsiniz

## Geliştirici Ortamı

Geliştirme araçları (pre-commit, detect-secrets) izole bir venv'de tutulur.
Bu venv runtime için **gerekli değildir** — sadece commit öncesi güvenlik
kontrolleri için kurulur.

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements-dev.txt
    pre-commit install

Pre-commit hook'ları her commit öncesi otomatik çalışır. Manuel test:

    pre-commit run --all-files

Test çalıştırma:

    pip install pytest
    pytest tests/

## Mimari

Detaylı mimari, modül haritası, veri akışı ve threading modeli için
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) dosyasına bakın.

Özet:

- **Tek-aktif-kamera modeli:** 25 kamera tanımlı olsa da aynı anda sadece
  1 RTSP akışı decode edilir. Patrol modunda kameralar sırayla değiştirilir.
- **Threading:** Tkinter UI ana thread, kamera/inference/patrol/Telegram
  ayrı daemon thread'lerde
- **GUI:** Tkinter (stdlib) — başka GUI framework bağımlılığı yok
- **Notification:** Telegram Bot HTTP API (raw `requests`, blocking — ayrı
  thread'lerde)

## Sorun Giderme

### Kamera bağlantısı kopuyor / "Stream timeout 30000ms"

Bilinen sınırlama: OpenCV varsayılan timeout'u (30 sn) kullanılır, otomatik
yeniden bağlanma yoktur. Çözümler:

- Kamera sağlığını ağ üzerinden kontrol edin (`ping`, VLC ile RTSP test)
- Aynı ağda 25 kamera varsa switch/router doygunluğu olabilir
- Kamera UI'dan başka bir kameraya geçin, sonra geri dönün (manuel reconnect)

### "BİLİNMEYEN ŞAHIS" tüm tespitlerde görünüyor

Sebepler:

1. `database/` klasörü boş veya yetersiz fotoğraf var
2. Eşik değeri çok düşük (`THRESHOLD=0.45` varsayılan, daha sıkı için
   yükseltin)
3. Fotoğraf kalitesi düşük (yüz açıkça görünmüyor, çok küçük, çok karanlık)

### Telegram bot çalışmıyor

- `.env` içinde `TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` doğru mu?
- Bot'a önce Telegram'dan `/start` mesajı gönderdiniz mi?
- BotFather'da bot aktif mi (`/mybots`)?
- Loglarda `notifications` seviyesinde hata var mı?

### Tkinter "no display" hatası

    sudo apt install python3-tk

Headless sunucularda çalıştırılamaz — uygulama GUI bağımlılığı içerir.

## Güvenlik Notları

- PIN, bcrypt ile hash'lenir (legacy SHA256 desteği geçiş döneminde mevcuttur)
- `auth_config.json`, `.env`, `embeddings_cache.pkl`, `snapshots/`, `logs/`
  versiyon kontrolüne dahil edilmez
- Kaynak kodda hardcoded credential yoktur — her şey `.env` üzerinden
- `embeddings_cache.pkl` pickle formatındadır — sadece güvenilir kaynaktan
  yüklenmesi gerekir (lokal kullanım için sorun değil, ama dosyayı
  başkalarıyla paylaşmayın)

## Lisans

[lisans bilgisi - TODO]

## Sürüm

v3 — Face Security V2'den göç edenler için `migrate_from_v2.py` scripti
mevcuttur.
