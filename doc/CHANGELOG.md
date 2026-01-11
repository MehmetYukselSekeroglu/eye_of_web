# Changelog / Değişiklik Günlüğü

Tüm önemli değişiklikler bu dosyada belgelenir.  
All notable changes are documented in this file.

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
