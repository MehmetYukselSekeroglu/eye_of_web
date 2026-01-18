# Changelog / Değişiklik Günlüğü

Tüm önemli değişiklikler bu dosyada belgelenir.  
All notable changes are documented in this file.

---

## [2.3.2] - 2026-01-18

### 📚 Documentation & Localization

#### Türkçe
- **Çoklu Dil Desteği**: `README_RU.md` (Rusça) ve `README_CN.md` (Çince) dokümantasyonları eklendi.
- **Teşekkür & Katkılar**: Enes Ülker, "Siber Güvenlik Araştırmacısı" olarak katkıda bulunanlar listesine eklendi.
- **Video İçerikleri**: Kullanım örnekleri ve kapsamlı analiz için video placeholder alanları eklendi.
- **Docker Optimizasyonu**: Docker imajının varsayılan olarak Torch CPU sürümü ile boyut tasarrufu sağladığına dair not eklendi.

#### English
- **Multi-Language Support**: Added `README_RU.md` (Russian) and `README_CN.md` (Chinese) documentation.
- **Acknowledgements**: Added Enes Ülker as "Cyber Security Researcher" to the contributors list.
- **Video Content**: Added video placeholder sections for usage examples and comprehensive analysis.
- **Docker Optimization**: Added note about Docker image using Torch CPU version by default for size optimization.

## [2.3.1] - 2026-01-16

### 🧠 Kapsamlı Kişi Analizi: Cluster All Stratejisi

#### Türkçe
- **Algoritma Tamamen Yenilendi**: "Kapsamlı Kişi Analizi" (`/comprehensive_person_analysis`) fonksiyonu **"Cluster All" (Herkesi Kümele)** stratejisine geçirildi.
  - Eski yöntemdeki "Hedef kişiyi çıkar, kalanları grupla" mantığı terk edildi.
  - **Yeni Yöntem:** Hedef kişinin bulunduğu karelerdeki **hedef dahil tüm yüzler** toplanır ve tek bir havuzda kümelenir.
  - Bu sayede hedef kişi ile ona benzeyen ancak farklı olan kişiler (örn: Belediye Başkanı vs Elon Musk) kusursuz şekilde ayrıştırılır.
  - "Kendisiyle eşleşme" (Self-matching) sorunu çözüldü.
- **Daha Hassas Hedef Tespiti:** Hedef kümesi, sadece orijinal `face_id`'yi içeren veya hedef vektörüne %45+ benzeyen kümeler olarak belirlenir.
- **Yanlış Pozitifler Giderildi:** Aynı karede birden fazla hedef kişi yüzü varsa veya hedef tespit edilememişse algoritma artık hata yapmaz.

#### English
- **Algorithm Completely Overhauled**: "Comprehensive Person Analysis" switched to **"Cluster All"** strategy.
  - Discarded the old "Exclude target, group the rest" logic.
  - **New Method:** **All faces** (including the target) in the relevant frames are collected and clustered in a single pool.
  - This perfectly separates the target person from look-alikes (e.g., Mayor vs. Elon Musk).
  - Solved the "Self-matching" issue.
- **Precise Target Identification:** Target clusters are identified strictly by containing the original `face_id` or matching the target vector by 45%+.
- **False Positives Eliminated:** Robust against missed detections or multiple target faces in the same frame.

### 🎨 Arayüz ve Görselleştirme İyileştirmeleri

#### Türkçe
- **Bounding Box Renkleri Düzeltildi**: `face_relationship_details.html` sayfasında:
  - 🟢 **Yeşil Kutu**: Hedef Kişi (Target)
  - 🔴 **Kırmızı Kutu**: İlişkili Kişi (Related)
  - Renk atamalarındaki mantık hatası giderildi.
- **Grup İçi Benzerlik Genişletmesi**: Temsilci yüz seçimi ve grup genişletme algoritması, Milvus tabanlı doğrulama ile güçlendirildi.

#### English
- **Bounding Box Colors Fixed**: In `face_relationship_details.html`:
  - 🟢 **Green Box**: Target Person
  - 🔴 **Red Box**: Related Person
  - Fixed logic error in color assignment.
- **Intra-Group Similarity Expansion:** Representative face selection and group expansion algorithm verified with Milvus-based validation.

## [2.2.0] - 2026-01-14

### 🕷️ Organic Google Search System (Selenium + Playwright)

#### Türkçe
- **Google Search Crawler Güncellendi**: `googlesearch` kütüphanesi yerine Selenium ve Playwright tabanlı "Organik Arama" sistemi entegre edildi.
  - İnsan davranışlarını taklit eden arama ve sayfalama yapısı (karakter karakter yazım, rastgele gecikmeler)
  - Otomatik cookie kabul mekanizması
  - Step-by-step İngilizce loglama ve kullanıcı bildirimi
- **İki Alternatif Backend**:
  - `--backend selenium`: Selenium tabanlı arama (`src/lib/google_organic_search.py`)
  - `--backend playwright`: Playwright tabanlı arama (`src/lib/google_playwright_search.py`) - **Varsayılan**
- **Yeni Paketler**: `webdriver-manager` ve `playwright` eklendi.

#### English
- **Google Search Crawler Updated**: Integrated Selenium and Playwright-based "Organic Search" system replacing `googlesearch` library.
  - Human-like search behavior (character-by-character typing, random delays)
  - Auto-accept cookie consent mechanism
  - Step-by-step English logging and user notification
- **Two Alternative Backends**:
  - `--backend selenium`: Selenium-based search (`src/lib/google_organic_search.py`)
  - `--backend playwright`: Playwright-based search (`src/lib/google_playwright_search.py`) - **Default**
- **New Packages**: Added `webdriver-manager` and `playwright`.

---

### 🚀 High-Performance Facebook Playwright Crawler

#### Türkçe
- **Yeni Yüksek Performanslı Crawler**: `src/lib/facebook/facebook_playwright_crawler.py`
  - Çoklu tarayıcı ve sekme desteği ile paralel işleme
  - Async/await mimarisi ile non-blocking I/O
  - Gereksiz kaynakları (resimler, CSS, analytics) engelleyerek hız optimizasyonu
  - 4 performans ön ayarı (preset):

| Preset | Tarayıcı | Sekme/Tarayıcı | Eşzamanlı İndirme |
|--------|----------|----------------|-------------------|
| conservative | 1 | 2 | 4 |
| balanced | 2 | 4 | 8 |
| **aggressive** | 3 | 6 | 16 |
| maximum | 4 | 8 | 32 |

**Hız Karşılaştırması (100 profil taraması):**
| Yöntem | Süre | Hız |
|--------|------|-----|
| Selenium (tek thread) | ~300s | 0.33 profil/s |
| Playwright (aggressive) | ~30s | 3.3 profil/s |
| **Hız Artışı** | **10x daha hızlı** | |

#### English
- **New High-Performance Crawler**: `src/lib/facebook/facebook_playwright_crawler.py`
  - Multi-browser and multi-tab parallel processing
  - Async/await architecture for non-blocking I/O
  - Speed optimization by blocking unnecessary resources (images, CSS, analytics)
  - 4 performance presets:

| Preset | Browsers | Tabs/Browser | Concurrent Downloads |
|--------|----------|--------------|---------------------|
| conservative | 1 | 2 | 4 |
| balanced | 2 | 4 | 8 |
| **aggressive** | 3 | 6 | 16 |
| maximum | 4 | 8 | 32 |

**Speed Comparison (100 profile crawl):**
| Method | Duration | Speed |
|--------|----------|-------|
| Selenium (single thread) | ~300s | 0.33 profiles/s |
| Playwright (aggressive) | ~30s | 3.3 profiles/s |
| **Speed Improvement** | **10x faster** | |

---

### 🌐 Playwright Page Crawler (Async Multi-Tab)

#### Türkçe
- **Yeni Sayfa Tarayıcısı**: `src/lib/single_domain_playwright_crawler.py`
  - **Async API** ile gerçek paralel sayfa yükleme
  - `asyncio.Semaphore` ile eşzamanlı tab limiti (varsayılan 3)
  - `asyncio.as_completed()` ile paralel görev takibi
  - Resim işleme için `run_in_executor()` ile thread pool
  - Context manager desteği (`with` bloğu ile otomatik kaynak temizleme)
  - Mevcut veritabanı ve InsightFace entegrasyonu
- **Google Search Crawler Entegrasyonu**:
  - `--backend playwright` seçildiğinde hem arama hem sayfa taraması Playwright ile yapılıyor
  - `--backend selenium` seçildiğinde eski Selenium davranışı korunuyor
- **URL Extraction İyileştirmesi**:
  - JavaScript ile 4 farklı yöntem: `a[jsname]`, `h3` içi linkler, `cite` yakını linkler, yapısal derinlik kontrolü
  - Google class isimlerinden bağımsız, yapısal seçiciler

#### English
- **New Page Crawler**: `src/lib/single_domain_playwright_crawler.py`
  - **Async API** for true parallel page loading
  - `asyncio.Semaphore` for concurrent tab limit (default 3)
  - `asyncio.as_completed()` for parallel task tracking
  - `run_in_executor()` for image processing in thread pool
  - Context manager support (automatic resource cleanup with `with` blocks)
  - Integration with existing database and InsightFace
- **Google Search Crawler Integration**:
  - `--backend playwright` now uses Playwright for both search and page crawling
  - `--backend selenium` maintains legacy Selenium behavior
- **URL Extraction Improvements**:
  - 4 JavaScript methods: `a[jsname]`, links inside `h3`, links near `cite`, structural depth check
  - Structural selectors independent of Google's changing class names

---

### 👤 Facebook Playwright Integration (Full Pipeline)

#### Türkçe
- **Yeni Thread Modülü**: `src/lib/facebook_playwright_thread.py`
  - Tekil profil işlemleri için Playwright tabanlı işleyici
  - Resim indirme, yüz tespiti (InsightFace) ve veritabanı kaydı
- **Tam Entegrasyon (`google_search_crawler.py`)**:
  - `--backend playwright` parametresi ile Facebook işlemleri de Playwright'a devredilir
  - **Facebook Arama**: `PlaywrightFacebookCrawler.crawl_search` ile 10x hızlı, paralel arama sonuçları taraması
  - **Facebook Profil**: `facebook_playwright_thread` ile hızlı profil işleme
- **Selenium Uyumluluğu**:
  - `--backend selenium` kullanıldığında eski `SingleDomainCrawlerSelenium` ve `facebook_thread` kullanılır

#### English
- **New Thread Module**: `src/lib/facebook_playwright_thread.py`
  - Playwright-based handler for single profile operations
  - Image download, face detection (InsightFace), and database recording
- **Full Integration (`google_search_crawler.py`)**:
  - `--backend playwright` parameter delegates Facebook operations to Playwright
  - **Facebook Search**: 10x faster concurrent crawling via `PlaywrightFacebookCrawler.crawl_search`
  - **Facebook Profile**: Fast profile processing via `facebook_playwright_thread`
- **Selenium Compatibility**:
  - Legacy `SingleDomainCrawlerSelenium` and `facebook_thread` used when `--backend selenium` is specified

---

## [2.1.0] - 2026-01-10

### 🐳 Docker Desteği / Docker Support

#### Türkçe
- **Docker ortamı oluşturuldu**: `Dockerfile`, `docker-compose.yml` ve `Dockerfile.crawler` dosyaları eklendi
- **Dinamik config oluşturma**: `generate_config.py` - Container başlarken environment variable'lardan `config/config.json` oluşturur
- **Ayrı crawler container'ı**: Selenium gerektirmeyen crawler'lar için hafif imaj (`docker_crawler_requirements.txt`)
- **Milvus v2.4.0 desteği**: Çoklu vektör alanı desteği için Milvus sürümü yükseltildi
- **PostgreSQL + pgvector**: Vektör veritabanı desteği

#### English
- **Docker environment created**: Added `Dockerfile`, `docker-compose.yml` and `Dockerfile.crawler`
- **Dynamic config generation**: `generate_config.py` - Creates `config/config.json` from environment variables at container startup
- **Separate crawler container**: Lightweight image for non-Selenium crawlers (`docker_crawler_requirements.txt`)
- **Milvus v2.4.0 support**: Upgraded Milvus version for multiple vector field support
- **PostgreSQL + pgvector**: Vector database support

---

### 🔧 InsightFace Yapılandırması / InsightFace Configuration

#### Türkçe
- **Detection threshold artırıldı**: `det_thresh` 0.5 → 0.75 (%75)
  - Sadece yüksek güvenilirlikli yüzler algılanır
  - Düşük kaliteli/bulanık yüzlerden oluşan bozuk embedding'ler önlenir
  - False positive oranı azaltılır
- **Environment variable desteği**: `INSIGHTFACE_DET_THRESH` ile threshold ayarlanabilir
- **Varsayılan model**: `buffalo_l` (Docker için otomatik indirme destekli)

#### English
- **Detection threshold increased**: `det_thresh` 0.5 → 0.75 (75%)
  - Only high-confidence faces are detected
  - Prevents bad embeddings from low-quality/blurry faces
  - Reduces false positive rate
- **Environment variable support**: Threshold configurable via `INSIGHTFACE_DET_THRESH`
- **Default model**: `buffalo_l` (auto-download supported for Docker)

---

### 📊 Kapsamlı Kişi Analizi / Comprehensive Person Analysis

#### Türkçe
- **"Kapsamlı Kişi Analizi" butonu eklendi**: `face_details.html` sayfasına analiz butonları eklendi
- **İlişkili kişi grupları**: Milvus tabanlı benzerlik araması ile ilişkili kişiler gruplanır
- **İstatistikler**: Toplam görsel sayısı, benzersiz yüz sayısı, eşleşme oranları
- **URL parametresi ile threshold ayarı**: `?threshold=0.75` gibi parametrelerle özelleştirilebilir

#### English
- **"Comprehensive Person Analysis" button added**: Analysis buttons added to `face_details.html` page
- **Related person groups**: Related persons grouped using Milvus-based similarity search
- **Statistics**: Total images, unique faces, match rates
- **Threshold customization via URL**: Customizable with parameters like `?threshold=0.75`

---

### 📚 Dokümantasyon / Documentation

#### Türkçe
- **DOCKER.md**: Kapsamlı Docker kurulum ve yönetim rehberi
- **CRAWLER.md**: Türkçe crawler kullanım kılavuzu (tüm crawler'lar için)
- **CRAWLER_EN.md**: İngilizce crawler kullanım kılavuzu
- **Sorun giderme bölümleri**: ContainerConfig hatası, Selenium uyumsuzluğu vb.

#### English
- **DOCKER.md**: Comprehensive Docker setup and management guide
- **CRAWLER.md**: Turkish crawler user guide (for all crawlers)
- **CRAWLER_EN.md**: English crawler user guide
- **Troubleshooting sections**: ContainerConfig error, Selenium incompatibility, etc.

---

### 📦 Bağımlılıklar / Dependencies

#### Türkçe
Yeni requirements dosyaları:
| Dosya | Kullanım |
|-------|----------|
| `requirements.txt` | Ana web uygulaması (PyTorch dahil) |
| `docker_crawler_requirements.txt` | Docker crawler'lar (Selenium yok, hafif) |
| `crawler_requirements.txt` | Ana OS crawler'ları (Selenium dahil) |

Eklenen paketler:
- `Flask-Login` - Kullanıcı oturum yönetimi
- `fpdf2` - PDF rapor oluşturma
- `pyfiglet` - ASCII banner
- `numba` - Hızlandırılmış hesaplama
- `HiveWebCrawler` - Web tarama

#### English
New requirements files:
| File | Usage |
|------|-------|
| `requirements.txt` | Main web app (includes PyTorch) |
| `docker_crawler_requirements.txt` | Docker crawlers (no Selenium, lightweight) |
| `crawler_requirements.txt` | Host OS crawlers (includes Selenium) |

Added packages:
- `Flask-Login` - User session management
- `fpdf2` - PDF report generation
- `pyfiglet` - ASCII banner
- `numba` - Accelerated computing
- `HiveWebCrawler` - Web crawling

---

### 🐛 Hata Düzeltmeleri / Bug Fixes

#### Türkçe
- **Config dosyası hatası düzeltildi**: Config yoksa environment variable'lardan otomatik oluşturma
- **init_insightface.py düzeltildi**: Eksik config durumunda varsayılan değerler kullanılır
- **face_relationship_details hatası düzeltildi**: İki parametre gerektiren route için buton kaldırıldı
- **ContainerConfig hatası için çözüm eklendi**: docker-compose v1 uyumsuzluğu

#### English
- **Config file error fixed**: Auto-generates from environment variables if config missing
- **init_insightface.py fixed**: Uses default values when config is missing
- **face_relationship_details error fixed**: Removed button for route requiring two parameters
- **ContainerConfig error solution added**: docker-compose v1 incompatibility fix

---

### ⚙️ Ortam Değişkenleri / Environment Variables

Docker container'lar için kullanılabilir değişkenler:

| Değişken / Variable | Varsayılan / Default | Açıklama / Description |
|---------------------|----------------------|------------------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_USER` | `postgres` | PostgreSQL kullanıcı / user |
| `DB_PASSWORD` | `postgres` | PostgreSQL şifre / password |
| `DB_NAME` | `EyeOfWeb` | Veritabanı adı / database name |
| `MILVUS_HOST` | `localhost` | Milvus host |
| `MILVUS_PORT` | `19530` | Milvus port |
| `INSIGHTFACE_MODEL` | `buffalo_l` | InsightFace model |
| `INSIGHTFACE_DET_THRESH` | `0.75` | Yüz algılama eşiği / detection threshold |
| `SECRET_KEY` | `change-me...` | Flask secret key |
| `ADMIN_USERNAME` | `admin` | Admin kullanıcı adı / username |
| `ADMIN_PASSWORD` | `admin123` | Admin şifre / password |

---

## Katkıda Bulunanlar / Contributors

- WeKnow Developer Team
