# EyeOfWeb Crawler Kullanım Kılavuzu

Bu döküman, EyeOfWeb sistemindeki tüm crawler'ların detaylı kullanımını açıklamaktadır.

## 📋 İçindekiler

- [Crawler Türleri](#crawler-türleri)
- [Gereksinimler](#gereksinimler)
- [Crawler Detayları](#crawler-detayları)
  - [Single Domain Crawler](#1-single-domain-crawler)
  - [RSS Crawler](#2-rss-crawler)
  - [Google Search Crawler](#3-google-search-crawler)
  - [Google Images Crawler](#4-google-images-crawler)
  - [Twitter Crawler (File Based)](#5-twitter-crawler-file-based)
  - [Twitter Crawler (Google Based)](#6-twitter-crawler-google-based)
  - [Facebook Crawler](#7-facebook-crawler)
  - [Telegram Crawler (Pyrogram)](#8-telegram-crawler-pyrogram)
  - [Telegram Crawler (Telethon)](#9-telegram-crawler-telethon)
  - [Flickr Crawler](#10-flickr-crawler)
- [Docker vs Ana OS](#docker-vs-ana-os)
- [Ortak Parametreler](#ortak-parametreler)

---

## Crawler Türleri

| Crawler | Selenium | Docker | Açıklama |
|---------|----------|--------|----------|
| `single_domain.py` | ❌ | ✅ | Tek domain/URL tarama |
| `rss_crawler.py` | ❌ | ✅ | RSS/Atom feed tarama |
| `google_search_crawler.py` | ❌ | ✅ | Google/DuckDuckGo arama sonuçları |
| `google_images_crawler.py` | ✅ | ❌ | Google Görseller tarama |
| `twitter_crawler_file_based.py` | ✅ | ❌ | Twitter profil tarama (dosyadan) |
| `twitter_crawler_google_based.py` | ✅ | ❌ | Twitter profil tarama (Google'dan) |
| `facebook_crawler.py` | ✅ | ❌ | Facebook profil tarama |
| `pyrogram_telegram_crawler_main.py` | ❌ | ✅ | Telegram tarama (Pyrogram API) |
| `telethon_telegram_crawler_main.py` | ❌ | ✅ | Telegram tarama (Telethon API) |
| `flicker_crawler.py` | ✅ | ❌ | Flickr görsel tarama |

---

## Gereksinimler

### Docker Ortamı (Selenium gerektirmeyenler)
```bash
pip install -r docker_crawler_requirements.txt
```

### Ana OS (Selenium gerektirenler)
```bash
pip install -r crawler_requirements.txt
# + Chrome/Firefox tarayıcısı kurulu olmalı
```

### Tüm Crawler'lar İçin
- `config/config.json` dosyası (Docker'da otomatik oluşturulur)
- PostgreSQL ve Milvus bağlantısı
- InsightFace modeli (buffalo_l veya antelopev2)

---

## Crawler Detayları

### 1. Single Domain Crawler

**Dosya:** `single_domain.py`

Tek bir web sitesini veya URL listesini tarar, görsellerdeki yüzleri tespit eder.

#### Parametreler

| Parametre | Zorunlu | Varsayılan | Açıklama |
|-----------|---------|------------|----------|
| `--url` | * | - | Taranacak tek URL |
| `--file` | * | - | URL listesi içeren dosya |
| `--max-depth` | ✅ | - | Maksimum tarama derinliği |
| `--risk-level` | ❌ | - | Risk seviyesi (low/medium/high) |
| `--category` | ❌ | - | Kategori etiketi |
| `--ignore-db` | ❌ | 0 | Veritabanı kontrolünü atla (1/0) |
| `--ignore-content` | ❌ | 0 | İçerik kontrolünü atla (1/0) |
| `--save-image` | ❌ | False | Görselleri kaydet |

> `*` = `--url` veya `--file` parametrelerinden biri zorunludur

#### Kullanım Örnekleri

```bash
# Tek URL tarama
python single_domain.py --url "https://example.com" --max-depth 3

# Dosyadan URL listesi tarama
python single_domain.py --file urls.txt --max-depth 2 --risk-level high

# Derinlemesine tarama (tüm seçenekler)
python single_domain.py \
    --url "https://example.com" \
    --max-depth 5 \
    --risk-level medium \
    --category "haber" \
    --ignore-db 0 \
    --save-image
```

#### URL Dosyası Formatı
```
https://example1.com
https://example2.com/page
https://example3.com/category/article
```

---

### 2. RSS Crawler

**Dosya:** `rss_crawler.py`

RSS/Atom feed'lerini sürekli olarak tarar ve haberlerdeki yüzleri tespit eder.

#### Parametreler

| Parametre | Zorunlu | Varsayılan | Açıklama |
|-----------|---------|------------|----------|
| `--rss` | ❌ | rss.txt | RSS URL'leri dosyası |
| `--risk-level` | ✅ | - | Risk seviyesi |
| `--category` | ✅ | - | Kategori etiketi |

#### Kullanım Örnekleri

```bash
# Varsayılan rss.txt dosyasını kullan
python rss_crawler.py --risk-level low --category "haber"

# Özel RSS dosyası
python rss_crawler.py --rss my_feeds.txt --risk-level medium --category "teknoloji"
```

#### RSS Dosyası Formatı (rss.txt)
```
https://feeds.bbci.co.uk/turkce/rss.xml
https://www.hurriyet.com.tr/rss/gundem
https://www.ntv.com.tr/gundem.rss
```

#### Çalışma Mantığı
1. RSS dosyasından URL'leri okur
2. Her feed'i feedparser ile parse eder
3. Her haber makalesini SingleNewsCrawler ile tarar
4. 1 saat bekler ve tekrar başlar (sonsuz döngü)

> **Not:** CTRL+C ile durdurulabilir

---

### 3. Google Search Crawler

**Dosya:** `google_search_crawler.py`

Google/DuckDuckGo arama sonuçlarındaki siteleri tarar.

#### Parametreler

| Parametre | Zorunlu | Varsayılan | Açıklama |
|-----------|---------|------------|----------|
| `--query` | ✅ | - | Arama sorgusu |
| `--num-results` | ❌ | 10 | Sonuç sayısı |
| `--backend` | ❌ | playwright | Tarayıcı altyapısı (`playwright` veya `selenium`) |
| `--risk-level` | ❌ | - | Risk seviyesi |
| `--category` | ❌ | - | Kategori |

#### Playwright Backend Özellikleri (`--backend playwright`)
- **Hız:** Selenium'a göre 10 kata kadar daha hızlı.
- **Paralel Tarama:** Arama sonuçları için multi-tab (varsayılan 3 sekme) ile eşzamanlı sayfa taraması yapar.
- **Facebook Entegrasyonu:** Facebook profil ve arama sonuçlarını özel optimize edilmiş crawler ile çok hızlı tarar.
- **Gizlilik:** Daha gelişmiş anti-bot önlemleri içerir.

#### Kullanım Örnekleri


```bash
# Basit arama
python google_search_crawler.py --query "örnek arama"

# Detaylı arama
python google_search_crawler.py \
    --query "site:example.com inurl:profile" \
    --num-results 50 \
    --risk-level high
```

---

### 4. Google Images Crawler

**Dosya:** `google_images_crawler.py`

> ⚠️ **Selenium gerektirir - Docker'da çalışmaz**

Google Görseller'den görsel arar ve yüz tespiti yapar.

#### Parametreler

| Parametre | Zorunlu | Varsayılan | Açıklama |
|-----------|---------|------------|----------|
| `--keyword` | ✅ | - | Arama kelimesi |
| `--scroll_count` | ✅ | - | Sayfa kaydırma sayısı |

#### Kullanım Örnekleri

```bash
python google_images_crawler.py --keyword "kişi adı" --scroll_count 10
```

---

### 5. Twitter Crawler (File Based)

**Dosya:** `twitter_crawler_file_based.py`

> ⚠️ **Selenium gerektirir - Docker'da çalışmaz**

Dosyadan Twitter/X profil URL'lerini okur ve tarar.

#### Parametreler

| Parametre | Zorunlu | Varsayılan | Açıklama |
|-----------|---------|------------|----------|
| `--file` | ✅ | - | Twitter URL/kullanıcı adı dosyası |
| `--threads` | ❌ | 3 | Thread sayısı (max 3) |
| `--headless` | ❌ | True | Başlıksız mod |
| `--driver_path` | ❌ | - | ChromeDriver yolu |
| `--temp_folder` | ❌ | temp | Geçici klasör |

#### Kullanım Örnekleri

```bash
python twitter_crawler_file_based.py --file twitter_users.txt

python twitter_crawler_file_based.py \
    --file twitter_users.txt \
    --threads 2 \
    --headless
```

#### Twitter Dosyası Formatı
```
https://twitter.com/kullanici1
https://x.com/kullanici2
@kullanici3
kullanici4
```

---

### 6. Twitter Crawler (Google Based)

**Dosya:** `twitter_crawler_google_based.py`

> ⚠️ **Selenium gerektirir - Docker'da çalışmaz**

Google arama sonuçlarından Twitter profilleri bulur ve tarar.

#### Kullanım
```bash
python twitter_crawler_google_based.py
```

---

### 7. Facebook Crawler

**Dosya:** `facebook_crawler.py`

> ⚠️ **Selenium gerektirir - Docker'da çalışmaz**

Facebook'ta kişi/profil arar ve profil fotoğraflarını tarar.

#### Parametreler

| Parametre | Zorunlu | Varsayılan | Açıklama |
|-----------|---------|------------|----------|
| `--keyword` | * | - | Arama kelimesi |
| `--file` | * | - | Anahtar kelime dosyası |
| `--scroll_count` | ❌ | 5 | Kaydırma sayısı |
| `--scroll_pause_time` | ❌ | 2 | Kaydırma bekleme süresi (sn) |
| `--headless` | ❌ | True | Başlıksız mod |
| `--driver_path` | ❌ | - | ChromeDriver yolu |
| `--temp_folder` | ❌ | temp | Geçici klasör |
| `--backend` | ❌ | selenium | Tarayıcı altyapısı (`selenium` veya `playwright`) |

> `*` = `--keyword` veya `--file` parametrelerinden biri zorunludur

#### Kullanım Örnekleri

```bash
# Tek anahtar kelime
python facebook_crawler.py --keyword "Ahmet Yılmaz"

# Birden fazla anahtar kelime (virgülle ayrılmış)
python facebook_crawler.py --keyword "Ali Veli,Mehmet Demir"

# Dosyadan anahtar kelimeler
python facebook_crawler.py --file keywords.txt --scroll_count 10
```

---

### 8. Telegram Crawler (Pyrogram)

**Dosya:** `pyrogram_telegram_crawler_main.py`

Telegram grupları ve kanallarını Pyrogram API ile tarar.

#### Gereksinimler
- Telegram API ID ve API Hash ([my.telegram.org](https://my.telegram.org))
- `config/config.json` dosyasında Telegram ayarları

#### Yapılandırma

Dosya içinde şu değişkenleri düzenleyin:
```python
API_ID = 12345              # Telegram API ID
API_HASH = 'your_api_hash'  # Telegram API Hash
SESSION_NAME = 'session'    # Session dosya adı
```

#### Kullanım
```bash
python pyrogram_telegram_crawler_main.py
```

#### Çalışma Mantığı
1. Telegram'a bağlanır (ilk seferinde telefon ve kod ister)
2. Tüm grupları ve kanalları listeler
3. Mesajlardaki görselleri ve profil fotoğraflarını indirir
4. InsightFace ile yüz tespiti yapar
5. Veritabanına kaydeder

---

### 9. Telegram Crawler (Telethon)

**Dosya:** `telethon_telegram_crawler_main.py`

Telegram grupları ve kanallarını Telethon API ile tarar. Pyrogram'a alternatif olarak kullanılabilir.

#### Yapılandırma

Dosya içinde şu değişkenleri düzenleyin:
```python
API_ID = 12345              # Telegram API ID
API_HASH = 'your_api_hash'  # Telegram API Hash
SESSION_NAME = 'session'    # Session dosya adı
```

#### Modlar

```python
PROCESS_REALTIME_MESSAGES = True   # Gerçek zamanlı mesajları işle
PROCESS_ONLY_SENDER_PROFILES = True # Sadece gönderen profillerini işle
```

#### Kullanım
```bash
python telethon_telegram_crawler_main.py
```

---

### 10. Flickr Crawler

**Dosya:** `flicker_crawler.py`

> ⚠️ **Selenium gerektirir - Docker'da çalışmaz**

Flickr'dan görsel arar ve yüz tespiti yapar.

#### Kullanım
```bash
python flicker_crawler.py --keyword "arama kelimesi"
```

---

## Docker vs Ana OS

### Docker Container'da Çalıştırma

```bash
# Container'a bağlan
sudo docker exec -it eyeofweb_crawler bash

# Selenium GEREKTIRMEYEN crawler'ları çalıştır
python single_domain.py --url "https://example.com" --max-depth 3
python rss_crawler.py --risk-level low --category "haber"
python google_search_crawler.py --query "arama terimi"
python pyrogram_telegram_crawler_main.py
```

### Ana OS'da Çalıştırma

```bash
# Virtual environment
python3 -m venv crawler_venv
source crawler_venv/bin/activate

# Bağımlılıkları kur
pip install -r crawler_requirements.txt

# Selenium gerektiren crawler'ları çalıştır
python twitter_crawler_file_based.py --file users.txt
python google_images_crawler.py --keyword "arama" --scroll_count 5
python facebook_crawler.py --keyword "kişi adı"
```

---

## Ortak Parametreler

Tüm crawler'larda ortak olarak kullanılan kavramlar:

### Risk Seviyesi (`--risk-level`)
- `low` - Düşük risk
- `medium` - Orta risk
- `high` - Yüksek risk
- `critical` - Kritik risk

### Kategori (`--category`)
Özel kategoriler tanımlanabilir:
- `haber`
- `sosyal_medya`
- `teknoloji`
- `spor`
- vb.

### Headless Mod
Selenium tabanlı crawler'larda tarayıcı görünmez modda çalışır. Hata ayıklama için `--no-headless` kullanılabilir.

---

## Sorun Giderme

### Config Dosyası Hatası
```
Failed To Load Config File: config/config.json
```
**Çözüm:** `python generate_config.py` komutunu çalıştırın veya Docker container'ını yeniden başlatın.

### Selenium Hatası
```
WebDriverException: chromedriver not found
```
**Çözüm:** 
```bash
pip install webdriver-manager
# veya ChromeDriver'ı manuel indirin
```

### InsightFace Model Hatası
```
Model not found: buffalo_l
```
**Çözüm:** Model otomatik indirilir, internet bağlantısını kontrol edin.

---

**EyeOfWeb Crawler Suite** - Powered by InsightFace, Selenium & Telegram API 🕸️
