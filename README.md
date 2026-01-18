
<div align="center">
  <img src="img/logo.png" alt="EyeOfWeb Logo" width="300" onError="this.style.display='none'"/>

  # 👁️ EyeOfWeb

  ### Gelişmiş Web Tabanlı Yüz İstihbarat ve Güvenlik Analiz Platformu
  ### Advanced Web-Based Facial Intelligence & Security Analysis Platform

  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  ![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
  ![Framework](https://img.shields.io/badge/flask-2.0+-green.svg)
  ![Database](https://img.shields.io/badge/PostgreSQL-13+-336791.svg)
  ![Vector DB](https://img.shields.io/badge/Milvus-2.3+-00a1ea.svg)
  ![AI Model](https://img.shields.io/badge/InsightFace-AntelopeV2-orange.svg)
  ![Status](https://img.shields.io/badge/Status-Active%20Development-green)

  ---

  **[🇹🇷 Türkçe Dokümantasyon](#-türkçe-dokümantasyon)** | **[🇬🇧 English Documentation](#-english-documentation)** | **[🇷🇺 Russian Documentation](README_RU.md)** | **[🇨🇳 Chinese Documentation](README_CN.md)**

</div>

---

> [!IMPORTANT]
> ## 📜 YASAL UYARI / LEGAL DISCLAIMER
>
> ### 🇹🇷 Türkçe
> **EyeOfWeb**, akademik araştırma, eğitim ve yasal güvenlik simülasyonları amacıyla geliştirilmiştir. Bu yazılımın gerçek kişiler üzerinde rızaları olmadan kullanılması, kişisel verilerin izinsiz toplanması veya saklanması; **6698 sayılı Kişisel Verilerin Korunması Kanunu (KVKK)**, Avrupa Birliği **Genel Veri Koruma Tüzüğü (GDPR)** ve diğer ulusal/uluslararası gizlilik yasalarına aykırılık teşkil edebilir ve ciddi yasal yaptırımlara yol açabilir.
>
> Proje geliştiricileri, yazılımın herhangi bir şekilde yasa dışı veya etik olmayan kullanımından kaynaklanan doğrudan ya da dolaylı hiçbir hukuki, mali veya cezai sorumluluğu kabul etmez. **Tüm yasal ve etik sorumluluk, yazılımı kullanan son kullanıcıya aittir.**
>
> ### 🇬🇧 English
> **EyeOfWeb** has been developed strictly for academic research, education, and legal security simulations. Unauthorized use, collection, or storage of personal data on real individuals may violate **KVKK** (Turkish Data Protection Law), **GDPR**, and other international privacy laws, resulting in serious legal penalties.
>
> The developers assume no direct or indirect legal, financial, or criminal liability for any illegal or unethical use of the software. **The end-user bears full legal and ethical responsibility.**

---

## 🇹🇷 Türkçe Dokümantasyon

---

### 📋 İçindekiler (Table of Contents)

1.  [🐳 Docker ile Hızlı Başlangıç](#-docker-ile-hızlı-başlangıç--quick-start-with-docker)
2.  [Yönetici Özeti](#-yönetici-özeti)
3.  [Temel Özellikler](#-temel-özellikler-ve-yetenekler)
4.  [Teknik Mimari](#-teknik-mimari)
5.  [Teknoloji Yığıtı (Tech Stack)](#-teknoloji-yığıtı-tech-stack)
6.  [Proje Yapısı](#-proje-yapısı)
7.  [Kurulum Rehberi](#️-kurulum-rehberi)
8.  [Yapılandırma Seçenekleri](#️-yapılandırma-seçenekleri)
9.  [Lisans](#-lisans)
10. [Teşekkür ve Katkıda Bulunanlar](#-teşekkür-ve-katkıda-bulunanlar)

---

### 📚 Detaylı Dokümantasyon / Detailed Documentation

| Dosya / File | Açıklama / Description |
|--------------|------------------------|
| [doc/DOCKER.md](doc/DOCKER.md) | 🐳 Docker kurulum ve yönetim rehberi |
| [doc/CRAWLER.md](doc/CRAWLER.md) | 🕷️ Crawler kullanım kılavuzu (Türkçe) |
| [doc/CRAWLER_EN.md](doc/CRAWLER_EN.md) | 🕷️ Crawler user guide (English) |
| [doc/CHANGELOG.md](doc/CHANGELOG.md) | 📝 Değişiklik günlüğü / Changelog |

---

### 🐳 Docker ile Hızlı Başlangıç / Quick Start with Docker

> [!TIP]
> **En hızlı kurulum yöntemi Docker kullanmaktır!**  
> **Docker is the fastest way to get started!**
>
> **Not / Note:** Docker imajı, boyut tasarrufu için varsayılan olarak **Torch CPU** versiyonunu kullanır. GPU kullanımı için `src/Dockerfile` içerisindeki Torch kurulumunu değiştirmeniz gerekebilir.
> **Note:** The Docker image uses the **Torch CPU** version by default to save space. You may need to modify the Torch installation in `src/Dockerfile` for GPU usage.

#### 🇹🇷 Türkçe

```bash
# 1. Projeyi klonlayın
git clone https://github.com/MehmetYukselSekeroglu/eye_of_web.git
cd eye_of_web/src

# 2. Docker Compose ile başlatın
sudo docker compose up -d --build

# 3. Logları takip edin
sudo docker compose logs -f web
```

**Erişim:** http://localhost:5000  
**Varsayılan Admin:** `admin` / `admin123_changeme`

#### 🇬🇧 English

```bash
# 1. Clone the repository
git clone https://github.com/MehmetYukselSekeroglu/eye_of_web.git
cd eye_of_web/src

# 2. Start with Docker Compose
sudo docker compose up -d --build

# 3. Follow the logs
sudo docker compose logs -f web
```

**Access:** http://localhost:5000  
**Default Admin:** `admin` / `admin123_changeme`

#### Servisler / Services

| Servis / Service | Port | Açıklama / Description |
|------------------|------|------------------------|
| Web Uygulaması | 5000 | Ana web arayüzü / Main web interface |
| PostgreSQL | 5432 | İlişkisel veritabanı / Relational database |
| Milvus | 19530 | Vektör veritabanı / Vector database |
| Crawler Worker | - | Arka plan tarayıcı / Background crawler |

> 📖 **Detaylı kurulum için:** [doc/DOCKER.md](doc/DOCKER.md)

---

### ⚠️ Önemli Yapılandırma Değişiklikleri / Important Configuration Changes

#### InsightFace Detection Threshold (v2.1.0+)

🇹🇷 **Türkçe:**
- `det_thresh` değeri **0.5 → 0.75** olarak artırıldı
- Sadece yüksek güvenilirlikli yüzler algılanır (%75+)
- Düşük kaliteli/bulanık yüzlerden oluşan bozuk embedding'ler önlenir
- False positive oranı önemli ölçüde azaltılır

🇬🇧 **English:**
- `det_thresh` value increased from **0.5 → 0.75**
- Only high-confidence faces are detected (75%+)
- Prevents bad embeddings from low-quality/blurry faces
- Significantly reduces false positive rate

```python
# lib/init_insightface.py
default_det_thresh = 0.75  # Artırıldı / Increased
```

#### Playwright Crawler Integration (v2.2.0+)

🇹🇷 **Türkçe:**
- Google Search ve Facebook tarayıcıları için **Playwright** desteği eklendi.
- **10x performans artışı** ve asenkron (async) multi-tab desteği.
- `--backend playwright` parametresi ile aktif edilir.

🇬🇧 **English:**
- Added **Playwright** support for Google Search and Facebook crawlers.
- **10x performance boost** and asynchronous multi-tab support.
- Activated via `--backend playwright` argument.

---

### 📄 Yönetici Özeti

**EyeOfWeb**, Açık Kaynak İstihbaratı (Open Source Intelligence - OSINT) metodolojilerini, en son nesil derin öğrenme tabanlı biyometrik analiz teknolojileriyle birleştiren kapsamlı ve profesyonel bir güvenlik istihbarat platformudur.

Sistem, internet üzerindeki çeşitli kaynaklardan (haber portalları, bloglar, RSS beslemeleri ve benzeri) görsel verileri otonom olarak tarar, bu görsellerde bulunan yüzleri tespit eder, her bir yüz için benzersiz bir matematiksel vektör (embedding) oluşturur ve bu vektörleri yüksek performanslı bir vektör veritabanında (Milvus) indeksler. Paralel olarak, yüzlerin tespit edildiği kaynak, tarih, risk seviyesi gibi meta veriler ilişkisel bir veritabanında (PostgreSQL) saklanır.

Bu "hibrit veritabanı mimarisi" sayesinde EyeOfWeb, milyarlarca yüz verisi arasında **milisaniyeler içinde** 1:N kimlik arama, 1:1 yüz karşılaştırma, sosyal ilişki ağı/birliktelik analizi ve kişi profilleme gibi gelişmiş analizleri gerçekleştirebilir.

---

### 🎥 Örnek Kullanım ve Analiz Videoları (Example Usage & Analysis Videos)

#### 1. Genel Kullanım Örneği (General Usage Example)
[![EyeOfWeb Usage Example](https://img.youtube.com/vi/s_Ak0tiq1f4/0.jpg)](https://www.youtube.com/watch?v=s_Ak0tiq1f4)

#### 2. Kapsamlı Kişi Analizi (Comprehensive Person Analysis)
[![EyeOfWeb Comprehensive Analysis](https://img.youtube.com/vi/gdoNdIjJr5E/0.jpg)](https://www.youtube.com/watch?v=gdoNdIjJr5E)

---

### 🚀 Temel Özellikler ve Yetenekler

Aşağıda EyeOfWeb'in `src/app/routes/web.py` modülünde tanımlanan ve kullanıcı arayüzü/API aracılığıyla erişilebilen tüm temel özellikleri detaylı olarak açıklanmaktadır.

---

#### 1. Kapsamlı Kişi Analizi (Comprehensive Person Analysis)

Bu, EyeOfWeb'in en güçlü ve sofistike analiz aracıdır. Belirli bir kişinin fotoğrafları üzerinden kapsamlı bir sosyometrik analiz gerçekleştirir.

**Rota:** `/comprehensive_person_analysis/<face_id>`

**Çalışma Mantığı:**
1.  **Hedef ve Çevre Belirleme:** Seçilen yüz (`face_id`) ve onunla aynı karede bulunan tüm yüzler teknik detaylarına inilmeden toplanır.
2.  **Cluster All (Herkesi Kümele):** Hedef kişi dahil toplanan tüm yüzler, gelişmiş "Cluster All" stratejisi ile kümelenir. Bu işlem, hedef kişi ile ona benzeyen ancak farklı olan kişileri (look-alike) kusursuzca ayrıştırır.
3.  **Hedef Kümesi Tespiti:** Oluşan kümeler arasından hangisinin "Hedef Kişi"ye ait olduğu, orijinal yüz verisi ve embedding benzerliği ile belirlenir.
4.  **İlişki Analizi:** Sadece "Hedef Kümesi"nden bir yüz ile "Farklı Bir Küme"den bir yüzün aynı görselde yan yana geldiği durumlar tespit edilir ve sayılır.
5.  **Sonuçlar:** Bu yöntem, **yanlış pozitifleri (false positives)** ve **kendisiyle eşleşme (self-matching)** sorunlarını ortadan kaldırarak en doğru sosyometrik analizi sunar.

**Kullanım Senaryoları:**
*   Bir kişinin sosyal çevresinin haritalanması.
*   Bir kişinin hangi ortamlarda, kimlerle bir arada bulunduğunun analizi.
*   Bağlantı kalıplarının (network patterns) ortaya çıkarılması.

**Çıktılar:**
*   İlişkili kişilerin listesi (temsilci yüz görseli ile birlikte).
*   Her ilişkili kişi için birlikte görülme sayısı ve grup büyüklüğü.
*   Analiz istatistikleri (toplam işlenen yüz sayısı, benzersiz görsel sayısı vb.).
*   İndirilebilir PDF raporu (`/download/comprehensive_analysis_report`).

---

#### 2. Derin İlişki Analizi (Deep Insight)

Belirli bir yüzün, sistemde kayıtlı diğer yüzlerle ne sıklıkla aynı fotoğrafta göründüğünü analiz eder. Kapsamlı Kişi Analizi'ne göre daha hızlı bir alternatif sunar, ancak benzerlik tabanlı gruplama yapmaz.

**Rota:** `/deep_insight/<face_id>`

**Çalışma Mantığı:**
1.  Hedef yüzün (`face_id`) bulunduğu tüm görseller PostgreSQL'den (`ImageBasedMain` tablosu) çekilir.
2.  Bu görsellerde hedef yüzle birlikte bulunan diğer tüm yüzler listelenir.
3.  Her bir diğer yüzün, hedef yüzle kaç farklı görselde birlikte göründüğü sayılır (`Counter` ile).
4.  En sık birlikte görülen ilk 10 yüz, detaylı bilgileriyle (cinsiyet, yaş, risk seviyesi, kaynak domain, görsel URL) birlikte listelenir.

**Kullanım Senaryoları:**
*   Hızlı bir birliktelik taraması.
*   Bir kişinin en yakın çevresinin tespiti.
*   Belirli yüzlerin sürekli olarak birlikte görülüp görülmediğinin kontrolü.

---

#### 3. Birden Fazla Arama Modu

EyeOfWeb, farklı ihtiyaçları karşılamak üzere çeşitli arama modları sunar.

##### a) Görsel ile Arama (Search by Image)
**Rota:** `/search/image`, `/search/upload`

Kullanıcının yüklediği bir fotoğraftaki yüzü, veritabanındaki tüm kayıtlarla karşılaştırır.
*   Yüklenen görsel, `validate_and_sanitize_image` fonksiyonuyla güvenlik kontrolünden geçirilir.
*   Görsel, NumPy dizisine dönüştürülür ve InsightFace modeline beslenilerek 512 boyutlu bir vektör elde edilir.
*   Bu vektör, Milvus veritabanında `Cosine Similarity` algoritmasıyla aranır.
*   Kullanıcının belirlediği benzerlik eşiğinin (varsayılan: 0.6) üzerindeki sonuçlar listelenir.
*   Sonuçlar görsel olarak veritabanından çekilen Base64 formatındaki yüz kesimleriyle birlikte gösterilir.

##### b) Metin/Filtre ile Arama (Text/Filter Search)
**Rota:** `/search`, `/search/text`

PostgreSQL üzerinde yapısal veriler (meta data) üzerinden arama yapar.
*   `domain`: Belirli bir web sitesinden gelen sonuçları filtreler.
*   `start_date` / `end_date`: Tespit tarihine göre aralık filtresi.
*   `risk_level`: Risk seviyesine göre filtreleme (düşük, orta, yüksek, kritik).
*   `category`: Web sitesi kategorisine göre filtreleme.
*   `search_text`: Görsel başlığında (`ImageTitleID`) Türkçe metin araması yapar.
*   Sayfalama (Pagination) desteği mevcuttur (`page`, `per_page` parametreleri).

##### c) Benzer Yüz Arama (Search Similar Faces)
**Rota:** `/search/similar/<face_id>`

Veritabanında zaten kayıtlı olan bir yüzü (`face_id`) kullanarak, ona benzer diğer yüzleri arar.
*   `g.db_tools.get_embedding_by_id(target_face_id)` ile hedef yüzün Milvus vektörü alınır.
*   `g.db_tools.findSimilarFacesWithImages(...)` fonksiyonu ile benzer yüzler bulunur.
*   Sonuçlar, hem veritabanından çekilen Base64 görsel verileriyle hem de kaynak URL'leriyle birlikte sunulur.
*   PDF raporu indirilebilir (`/download/similar_search_report`).

##### d) Yüz Benzerlik ve Birliktelik Analizi (Face Similarity Pairs)
**Rota:** `/face_similarity_analysis/<face_id>`

Hedef yüzün bulunduğu görsellerdeki tüm yüz çiftleri arasındaki benzerliği hesaplar ve belirlenen eşiğin üzerindeki çiftleri, birlikte görülme sayısına göre listeler.
*   Bu özellik, ilişki ağlarındaki potansiyel "aynı kişi" veya "yakın çevre" tespiti için kullanılabilir.
*   `min_cooccurrence` parametresi ile minimum birlikte görülme sayısı belirlenebilir.

---

#### 4. Yüz Tespiti ve Karşılaştırma

##### a) Yüz Tespiti (Face Detection)
**Rota:** `/face/detection`

Yüklenen herhangi bir görseldeki tüm yüzleri tespit eder.
*   InsightFace modeli kullanılarak görseldeki yüzler, bounding box'ları, cinsiyet, yaş ve algılama skorlarıyla birlikte listelenir.
*   Tespit edilen yüzler, görselin üzerine çizilen kutucuklarla (bounding boxes) görselleştirilir.
*   Sonuçlar PDF raporu olarak indirilebilir (`/download/detection_report`).

##### b) Yüz Karşılaştırma (Face Comparison)
**Rota:** `/face/comparison`

İki farklı görsel yüklenerek, her birindeki ilk yüzün birbirine benzip benzemediği analiz edilir (1:1 Karşılaştırma).
*   Kosinüs benzerliği hesaplanır ve kullanıcının belirlediği eşikle karşılaştırılır.
*   "Eşleşme Bulundu" veya "Eşleşme Bulunamadı" sonucu döndürülür.
*   Her iki görsel için de yüz bölgeleri kırpılarak gösterilir.
*   Sonuçlar PDF raporu olarak indirilebilir (`/download/comparison_report`).

---

#### 5. Birden Fazla Veritabanı Koleksiyonu

EyeOfWeb, farklı veri kaynaklarını yönetmek için birden fazla Milvus koleksiyonu ve PostgreSQL tablosunu destekler.

| Koleksiyon / Tablo Adı           | Açıklama                                                                 |
| :------------------------------- | :----------------------------------------------------------------------- |
| `EyeOfWebFaceDataMilvus`         | Sistemin web taraması ile topladığı ana yüz vektörü koleksiyonu.        |
| `WhiteListFacesMilvus`           | Manuel olarak eklenen "tanınan" veya "izin verilen" yüzlerin koleksiyonu.|
| `ExternalFaceStorageMilvus`      | Dış kaynaklardan (API vb.) aktarılan yüzler.                             |
| `CustomFaceStorageMilvus`        | Kullanıcı tanımlı özel koleksiyon.                                       |

Her koleksiyon için özelleştirilmiş arama rotaları mevcuttur:
*   `/whitelist`: Beyaz liste araması.
*   `/whitelist_upload`: Görsel yükleyerek beyaz listede arama.
*   `/whitelist/yuzara/<face_id>`: Beyaz listedeki bir yüze benzer yüzleri arama.
*   `/external`: Dış yüz deposu araması.
---

#### 6. Yönetici Paneli (Dashboard)

**Rota:** `/dashboard` (Yalnızca admin kullanıcılar erişebilir)

Sistem genelindeki istatistikleri ve sağlık durumunu gösteren merkezi bir yönetim ekranı.

**Sunulan İstatistikler:**
*   `total_faces`: Toplam yüz kaydı sayısı.
*   `total_domains`: Taranan benzersiz domain sayısı.
*   `total_images`: Toplam görsel sayısı.
*   `high_risk`: Yüksek riskli olarak işaretlenen yüz sayısı.
*   `risk_levels_chart`: Risk seviyesi dağılımı (pasta veya çubuk grafik için veri).
*   `categories_chart`: Website kategorisi dağılımı (pasta veya çubuk grafik için veri).
*   `table_stats`: Tüm PostgreSQL tablolarının kayıt sayıları.
*   `table_sizes`: Tüm tabloların disk boyutları.
*   `db_size`: Toplam veritabanı boyutu.
*   `recent_scans`: En son taranan domainler ve bulunan yüz sayıları.

---

#### 7. PDF Raporlama Sistemi

EyeOfWeb, gerçekleştirilen tüm analizler için profesyonel formatta PDF raporu üretebilir. Bu raporlar zaman damgası, kullanıcı bilgisi ve kaynak URL'leri içerir.

**Desteklenen Raporlar:**
*   **Görsel Arama Raporu:** `/download/image_search_report`
*   **Benzer Yüz Arama Raporu:** `/download/similar_search_report`
*   **Kapsamlı Kişi Analizi Raporu:** `/download/comprehensive_analysis_report`
*   **Yüz Tespiti Raporu:** `session['last_detection_report_data']` üzerinden.
*   **Yüz Karşılaştırma Raporu:** `session['last_comparison_report_data']` üzerinden.

Raporlar `lib/pdf_generator.py` modülü tarafından `generate_pdf_report()` fonksiyonu ile oluşturulur. Her rapor şunları içerir:
*   Rapor başlığı ve tipi.
*   Raporu oluşturan kullanıcı adı.
*   Tarih ve saat damgası.
*   Her yüz için: Görsel (Base64 veya URL), Kaynak URL, Hash, Cinsiyet, Yaş, Skor, Benzerlik oranı, FaceBox koordinatları.

---

### 🏛️ Teknik Mimari

---

#### Hibrit Veritabanı Sistemi (PostgreSQL + Milvus)

EyeOfWeb, yapısal/ilişkisel verileri (relational data) ve yüksek boyutlu vektör verilerini (high-dimensional vector data) ayrı ayrı işleyen bir hibrit mimari kullanır.

| Bileşen       | Veritabanı   | Saklanan Veri                                                                 | Kullanım Amacı                                               |
| :------------ | :----------- | :---------------------------------------------------------------------------- | :----------------------------------------------------------- |
| **Bellek**    | PostgreSQL   | Kullanıcılar, URL bileşenleri, başlıklar, hash'ler, tarihler, risk seviyeleri | SQL sorguları, filtreleme, birleştirme (`JOIN`), meta veri   |
| **Beyin**     | Milvus       | 512-d Yüz Vektörleri, 212-d Landmark Vektörleri, 4-d FaceBox Koordinatları    | ANN araması (HNSW), Benzerlik hesaplama (`Cosine Similarity`)|

**Senkronizasyon Mekanizması:**
*   PostgreSQL'deki `EyeOfWebFaceID` tablosundaki her kayıt, Milvus'taki `EyeOfWebFaceDataMilvus` koleksiyonundaki bir kayıtla `pg_face_id` alanı üzerinden ilişkilendirilir.
*   Arama işlemleri önce Milvus'ta gerçekleştirilir, ardından dönen ID'ler PostgreSQL'de detay sorgularında kullanılır.
*   `g.db_tools` (DatabaseTools) sınıfı, her iki veritabanına da erişim sağlayan merkezi bir API sunar (örn. `connect()`, `get_milvus_face_attributes()`, `find_similar_face_ids_in_milvus()`, `getImageBinaryByID()`, `executeQuery()`).

---

#### Yapay Zeka Motoru: InsightFace & AntelopeV2

EyeOfWeb, yüz tespiti ve tanıma işlemleri için endüstri standardı **InsightFace** kütüphanesinin **AntelopeV2** modelini kullanır.

**Model Özellikleri:**
| Özellik                     | Değer                                                                 |
| :-------------------------- | :-------------------------------------------------------------------- |
| Yüz Algılama (Detection)    | RetinaFace tabanlı, çoklu ölçek desteği                               |
| Landmark Tespiti            | 106 noktalı yüz işaretçisi (göz, kaş, burun, dudak, çene hattı vb.)   |
| Vektör Embedding Boyutu     | 512 boyutlu (float32)                                                 |
| Cinsiyet Tahmini            | Binary (Erkek: True, Kadın: False)                                    |
| Yaş Tahmini                 | Sürekli değer (integer)                                               |
| Algılama Skoru              | 0.0 - 1.0 arası güven değeri                                          |

**Donanım Hızlandırma:**
Sistem, `src/config/config.json` ve `src/config/cpu_config.json` dosyaları aracılığıyla GPU veya CPU modunda çalışacak şekilde yapılandırılabilir.
*   **GPU Modu (`CUDAExecutionProvider`):** NVIDIA CUDA destekli GPU'larda yüksek performans. `ctx_id: 0` (ilk GPU).
*   **CPU Modu (`CPUExecutionProvider`):** GPU olmayan sistemler için. `ctx_id: -1`. Düşük çözünürlük ayarları (`det_size: [160, 160]`) ile bellek kullanımı optimize edilebilir.

---

#### Güvenlik Alt Yapısı

EyeOfWeb, kurumsal düzeyde güvenlik mekanizmalarıyla donatılmıştır.

| Bileşen                     | Teknoloji / Yöntem             | Açıklama                                                                                     |
| :-------------------------- | :----------------------------- | :------------------------------------------------------------------------------------------- |
| **Kimlik Doğrulama**        | Flask-JWT-Extended             | Tüm API ve web arayüzü için JSON Web Token tabanlı güvenli erişim.                           |
| **Oturum Yönetimi**         | Flask-Session (Server-Side)   | Oturum verileri sunucu tarafında saklanır. Token'lar HttpOnly ve SameSite cookie'lerde tutulur. |
| **Şifreleme**               | Flask-Bcrypt                   | Kullanıcı şifreleri, bcrypt algoritmasıyla hash'lenerek saklanır.                            |
| **CSRF Koruması**           | Flask-WTF                      | Form gönderimleri, Cross-Site Request Forgery saldırılarına karşı korunur.                   |
| **Rate Limiting**           | Flask-Limiter                  | IP bazlı istek sınırlandırması (örn. `/search/image` için `10/minute`).                      |
| **Giriş Doğrulama**         | `html.escape()`, `secure_filename()`, `validate_and_sanitize_image()` | XSS, path traversal ve zararlı dosya yükleme saldırılarına karşı koruma. |
| **Yetkilendirme**           | `@login_required` Dekoratörü   | Oturum açmamış kullanıcıların korunan rotalara erişimini engeller.                           |
| **Admin Kontrolü**          | `session.get('is_admin')`     | Dashboard gibi hassas sayfalara yalnızca admin kullanıcıların erişmesini sağlar.             |

---

#### Görüntü İşleme Hattı (Image Sanitization Pipeline)

Sisteme yüklenen veya dış kaynaklardan alınan tüm görseller, `validate_and_sanitize_image()` fonksiyonuyla kapsamlı bir güvenlik ve doğrulama sürecinden geçirilir.

**Adımlar:**
1.  **Dosya Adı Güvenliği:** `werkzeug.utils.secure_filename()` ile zararlı karakterler temizlenir.
2.  **Uzantı Kontrolü:** İzin verilen uzantılar: `png`, `jpg`, `jpeg`, `gif`, `webp`.
3.  **Dosya Boyutu Kontrolü:** Maksimum 5 MB (yapılandırılabilir).
4.  **Pillow Doğrulama:** `Image.open()` ve `Image.verify()` ile dosyanın geçerli bir görsel olup olmadığı kontrol edilir.
5.  **Format Doğrulama:** `img.format` değeri, izin verilen formatlarla karşılaştırılır.
6.  **Yeniden Kodlama (Re-encoding):** Görsel, bellekte (`io.BytesIO()`) yeniden işlenerek potansiyel steganografik yükler veya exploit payload'ları etkisiz hale getirilir.
7.  **Renk Modu Dönüşümü:** Görsel, işleme hattı için uygun bir modda (genellikle RGB veya RGBA) standartlaştırılır.

**Çıktı:** Temizlenmiş PIL Image nesnesi ve güvenli dosya adı.

---

### 🛠️ Teknoloji Yığıtı (Tech Stack)

| Katman               | Teknoloji                                  | Versiyon / Notlar             |
| :------------------- | :----------------------------------------- | :---------------------------- |
| **Dil**              | Python                                     | 3.8+                          |
| **Web Framework**    | Flask                                      | 2.0+                          |
| **WSGI Server**      | Gunicorn / Waitress (Önerilen)             | Production için               |
| **İlişkisel DB**     | PostgreSQL                                 | 13+                           |
| **Vektör DB**        | Milvus                                     | 2.3+                          |
| **DB Adapter**       | Psycopg2, PyMilvus                         |                               |
| **ML / AI**          | InsightFace (ONNX Runtime), NumPy, SciPy  | AntelopeV2 modeli             |
| **Görüntü İşleme**   | OpenCV (cv2), Pillow (PIL)                 |                               |
| **Güvenlik**         | Flask-JWT-Extended, Flask-Bcrypt, Flask-WTF, Flask-Limiter, Flask-Session |                               |
| **Veri Ayrıştırma**  | feedparser (RSS/Atom)                      |                               |
| **Web Crawling**     | Selenium, Playwright                       | Async/Multi-tab Support       |
| **Raporlama**        | ReportLab veya benzeri (lib/pdf_generator) | PDF oluşturma                 |
| **Frontend**         | HTML5, CSS3, JavaScript, Jinja2            | Responsive UI                 |
| **Konteyner**        | Docker, Docker Compose                     | Milvus dağıtımı için          |

---

### 📁 Proje Yapısı

```
eye_of_web/
├── .git/                           # Git versiyon kontrol
├── .gitignore                      # Git tarafından yoksayılan dosyalar
├── LICENSE                         # MIT Lisansı
├── README.md                       # Bu dokümantasyon dosyası
├── img/                            # Statik görseller (logo vb.)
│   └── logo.png
│
└── src/                            # Ana kaynak kod dizini
    ├── run.py                      # Flask uygulamasını başlatma betiği
    ├── requirements.txt            # Python bağımlılıkları
    │
    ├── app/                        # Flask Uygulama Modülü (MVC Mimarisi)
    │   ├── __init__.py             # Flask uygulama fabrikası (Application Factory)
    │   ├── config/                 # Uygulama yapılandırma dosyaları (DB bağlantıları vb.)
    │   ├── controllers/            # İş mantığı katmanı (Search, User, vb.)
    │   │   └── search_controller.py
    │   ├── models/                 # Veritabanı modelleri / ORM
    │   ├── routes/                 # URL yönlendirme ve endpoint tanımları (Blueprints)
    │   │   ├── auth.py             # Kimlik doğrulama rotaları (login, logout)
    │   │   ├── api.py              # RESTful API endpoint'leri
    │   │   └── web.py              # Web arayüzü rotaları (Bu dosya, ~4000 satır)
    │   ├── static/                 # Statik dosyalar (CSS, JS, images)
    │   └── templates/              # Jinja2 HTML şablonları
    │       ├── base.html
    │       ├── index.html
    │       ├── search.html
    │       ├── search_results.html
    │       ├── image_search.html
    │       ├── image_search_results.html
    │       ├── face_details.html
    │       ├── face_similarity.html
    │       ├── face_detection.html
    │       ├── face_comparison.html
    │       ├── deep_insight.html
    │       ├── comprehensive_analysis.html
    │       ├── dashboard.html
    │       ├── whitelist_search.html
    │       └── ... (diğer şablonlar)
    │
    ├── config/                     # Sistem yapılandırma dosyaları
    │   ├── config.json             # GPU modu yapılandırması
    │   └── cpu_config.json         # CPU modu yapılandırması
    │
    ├── lib/                        # Yardımcı kütüphaneler ve araçlar
    │   ├── database_tools.py       # PostgreSQL & Milvus işlemleri
    │   ├── init_insightface.py     # InsightFace model başlatma
    │   ├── load_config.py          # Yapılandırma dosyası yükleme
    │   ├── url_image_download.py   # URL'den güvenli görsel indirme
    │   ├── draw_utils.py           # Görsel üzerine çizim araçları
    │   ├── compress_tools.py       # Görsel sıkıştırma/açma
    │   └── pdf_generator.py        # PDF rapor oluşturma
    │
    ├── sql/                        # SQL şema ve sorgu dosyaları
    │
    ├── MILVUS_SCHEMA_GENERATOR.py  # Milvus koleksiyon şemalarını oluşturma betiği
    ├── migration_to_milvus.py      # PostgreSQL'den Milvus'a veri göçü betiği
    └── general_whitelist_loader.py # Beyaz liste yükleme aracı
```

---

### ⚙️ Kurulum Rehberi

#### Sistem Gereksinimleri

| Bileşen       | Minimum                        | Önerilen                             |
| :------------ | :----------------------------- | :----------------------------------- |
| **OS**        | Ubuntu 18.04+ / Windows 10 WSL2 | Ubuntu 20.04+ / Debian 11+          |
| **CPU**       | 4 Çekirdek (x86_64)            | 8+ Çekirdek (AVX2 destekli)          |
| **RAM**       | 8 GB                           | 16 GB veya daha fazla                |
| **Depolama**  | 100 GB (SSD önerilir)          | 250 GB+ SSD                          |
| **GPU**       | Opsiyonel                      | NVIDIA GPU (CUDA 11.x+), 4GB+ VRAM   |
| **Ağ**        | Sürekli internet bağlantısı    | Kararlı, yüksek bant genişliği       |

#### Adım Adım Kurulum

**1. Sistem Bağımlılıkları (Ubuntu/Debian):**
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3-dev python3-pip python3-venv git \
    postgresql postgresql-contrib libpq-dev \
    build-essential libssl-dev libffi-dev \
    docker.io docker-compose
sudo systemctl enable docker && sudo systemctl start docker
```

**2. Kaynak Kodunu Klonlayın:**
```bash
git clone https://github.com/MehmetYukselSekeroglu/eye_of_web.git
cd eye_of_web
```

**3. Python Sanal Ortamını Oluşturun:**
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r src/requirements.txt
```
*GPU kullanacaksanız:*
```bash
pip install onnxruntime-gpu
```

**4. Milvus Veritabanını Başlatın (Docker):**
```bash
# Standalone Milvus için docker-compose dosyasını indirin
wget https://github.com/milvus-io/milvus/releases/download/v2.3.0/milvus-standalone-docker-compose.yml -O docker-compose.yml

# Milvus'u arka planda başlatın
sudo docker-compose up -d

# Durumu kontrol edin
sudo docker-compose ps
```

**5. PostgreSQL Veritabanını Yapılandırın:**
```bash
# PostgreSQL servisini başlatın
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Veritabanı ve kullanıcı oluşturun
sudo -u postgres psql << EOF
CREATE DATABASE eyeofweb;
CREATE USER eyeofwebuser WITH ENCRYPTED PASSWORD 'guclu_sifre_buraya';
GRANT ALL PRIVILEGES ON DATABASE eyeofweb TO eyeofwebuser;
\q
EOF
```
Ardından `src/app/config/` altındaki veritabanı bağlantı ayarlarını güncelleyin.

**6. Veritabanı Şemalarını Oluşturun:**
```bash
# Milvus koleksiyonlarını oluştur
python src/MILVUS_SCHEMA_GENERATOR.py

# PostgreSQL tablolarını oluşturmak için SQL dosyalarını çalıştırın.
# (Örnek: psql -d eyeofweb -U eyeofwebuser -f src/sql/schema.sql)
```

**7. Uygulamayı Başlatın:**
```bash
# Geliştirme modu
python src/run.py

# Production için (örnek - Gunicorn)
# gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```
Tarayıcınızda `http://localhost:5000` adresine gidin.

---

### ⚙️ Yapılandırma Seçenekleri

#### InsightFace (GPU/CPU) Yapılandırması

**`src/config/config.json` (GPU Modu):**
```json
{
  "insightface": {
    "prepare": {
      "ctx_id": 0,
      "det_thresh": 0.6,
      "det_size": [640, 640]
    },
    "main": {
      "providers": ["CUDAExecutionProvider"],
      "name": "antelopev2"
    }
  }
}
```

**`src/config/cpu_config.json` (CPU Modu):**
```json
{
  "insightface": {
    "prepare": {
      "ctx_id": -1,
      "det_thresh": 0.5,
      "det_size": [160, 160]
    },
    "main": {
      "providers": ["CPUExecutionProvider"],
      "name": "antelopev2"
    }
  }
}
```
*CPU modunda düşük `det_size` ve `det_thresh` değerleri, bellek kullanımını azaltır ancak algılama hassasiyetini düşürebilir.*

#### Milvus Bağlantı Parametreleri
```python
# lib/database_tools.py veya config dosyasında
MILVUS_HOST = "127.0.0.1"      # Milvus sunucu adresi
MILVUS_PORT = "19530"          # Milvus sunucu portu
MILVUS_CONNECTION_ALIAS = "default"
```

---

### 📄 Lisans

Bu proje, **MIT Lisansı** altında lisanslanmıştır.

Özet:
*   Yazılımı ticari veya ticari olmayan amaçlarla özgürce kullanabilirsiniz.
*   Kaynak kodunu değiştirebilir ve dağıtabilirsiniz.
*   Lisans ve telif hakkı bildirimini korumanız gerekir.
*   **HİÇBİR GARANTİ SAĞLANMAZ.** Yazılım "OLDUĞU GİBİ" sunulmaktadır.

Lisansın tam metni için proje kök dizinindeki `LICENSE` dosyasına bakınız.

---

### 🙏 Teşekkür ve Katkıda Bulunanlar

Bu projenin hayata geçirilmesinde emeği geçen kişilere teşekkürlerimizi sunarız.

---

#### Danışman / Öğretim Görevlisi

| | |
|---|---|
| **İsim** | **Uğur POLAT** |
| **Katkı** | Akademik Rehberlik, Proje Yönetimi, Mimari Vizyon ve Teknik Danışmanlık |

---

#### Güvenlik Araştırmacısı / Security Research

| | |
|---|---|
| **İsim** | **Enes Ülker** |
| **Katkı** | Siber Güvenlik Araştırmacısı / Cyber Security Researcher |

---

#### Proje Sahibi / Baş Geliştirici

| | |
|---|---|
| **İsim** | **Mehmet Yüksel ŞEKEROĞLU** |
| **Katkı** | Full-stack Geliştirme, Yapay Zeka Model Entegrasyonu, Veritabanı Tasarımı, Sistem Mimarisi ve Dokümantasyon |

---

---

## 🇬🇧 English Documentation

---

### 📋 Table of Contents

1.  [🐳 Quick Start with Docker](#-quick-start-with-docker)
2.  [Executive Summary](#-executive-summary)
3.  [Core Features and Capabilities](#-core-features-and-capabilities)
4.  [Technical Architecture](#️-technical-architecture)
5.  [Technology Stack](#️-technology-stack-1)
6.  [Project Structure](#-project-structure)
7.  [Installation Guide](#️-installation-guide)
8.  [Configuration Options](#️-configuration-options)
9.  [License](#-license-1)
10. [Acknowledgements](#-acknowledgements)

---

### 🐳 Quick Start with Docker

```bash
# 1. Clone the repository
git clone https://github.com/MehmetYukselSekeroglu/eye_of_web.git
cd eye_of_web/src

# 2. Start with Docker Compose
sudo docker compose up -d --build

# 3. Follow the logs
sudo docker compose logs -f web
```

**Access:** http://localhost:5000  
**Default Admin:** `admin` / `admin123_changeme`

> 📖 **For detailed installation:** [doc/DOCKER.md](doc/DOCKER.md)

---

### 📄 Executive Summary

**EyeOfWeb** is a comprehensive and professional security intelligence platform that combines Open Source Intelligence (OSINT) methodologies with next-generation deep learning-based biometric analysis technologies.

The system autonomously crawls visual data from various sources on the internet (news portals, blogs, RSS feeds, etc.), detects faces in these images, creates a unique mathematical vector (embedding) for each face, and indexes these vectors in a high-performance vector database (Milvus). In parallel, metadata such as source, date, and risk level of detected faces is stored in a relational database (PostgreSQL).

Thanks to this **hybrid database architecture**, EyeOfWeb can perform advanced analyses such as 1:N identity search, 1:1 face comparison, social relationship network/association analysis, and person profiling among billions of face data in **milliseconds**.

---

### 🚀 Core Features and Capabilities

Below are all the core features defined in the `src/app/routes/web.py` module and accessible via the user interface/API explained in detail.

---

#### 1. Comprehensive Person Analysis

This is EyeOfWeb's most powerful and sophisticated analysis tool. It performs a comprehensive sociometric analysis based on photographs of a specific person.

**Route:** `/comprehensive_person_analysis/<face_id>`

**How It Works:**
1.  **Target & Context Collection:** The target face (`face_id`) and ALL other faces appearing in the same frames are collected.
2.  **Cluster All Strategy:** All collected faces (including the target) are clustered together using an advanced greedy clustering algorithm. This perfectly separates the target person from look-alikes or false detections.
3.  **Target Cluster Identification:** The cluster belonging to the "Target Person" is identified using the original face data and embedding similarity.
4.  **Relationship Analysis:** Only instances where a face from the "Target Cluster" appears in the same image as a face from a "Different Cluster" are counted.
5.  **Results:** This method eliminates **false positives** and **self-matching** issues, providing the most accurate sociometric analysis.

**Use Cases:**
*   Mapping a person's social circle.
*   Analyzing in which environments and with whom a person is present.
*   Revealing network patterns.

---

#### 2. Deep Insight (Deep Relationship Analysis)

Analyzes how often a specific face appears in the same photo with other faces registered in the system. Provides a faster alternative to Comprehensive Person Analysis but does not perform similarity-based grouping.

**Route:** `/deep_insight/<face_id>`

**How It Works:**
1.  All images containing the target face (`face_id`) are retrieved from PostgreSQL (`ImageBasedMain` table).
2.  All other faces found together with the target face in these images are listed.
3.  How many different images each other face appears with the target face is counted (`Counter`).
4.  The top 10 most frequently co-occurring faces are listed with detailed information (gender, age, risk level, source domain, image URL).

---

#### 3. Multiple Search Modes

EyeOfWeb offers various search modes to meet different needs.

##### a) Image Search
**Route:** `/search/image`, `/search/upload`

Compares the face in a photo uploaded by the user with all records in the database.
*   Uploaded image passes security check with `validate_and_sanitize_image` function.
*   Image is converted to NumPy array and fed to InsightFace model to obtain a 512-dimensional vector.
*   This vector is searched in Milvus database with `Cosine Similarity` algorithm.
*   Results above the user-defined similarity threshold (default: 0.6) are listed.

##### b) Text/Filter Search
**Route:** `/search`, `/search/text`

Searches on structural data (metadata) over PostgreSQL.
*   `domain`: Filters results from a specific website.
*   `start_date` / `end_date`: Range filter by detection date.
*   `risk_level`: Filtering by risk level (low, medium, high, critical).
*   `category`: Filtering by website category.
*   Pagination support is available (`page`, `per_page` parameters).

##### c) Similar Face Search
**Route:** `/search/similar/<face_id>`

Searches for other faces similar to a face already registered in the database (`face_id`).

---

#### 4. Face Detection and Comparison

##### a) Face Detection
**Route:** `/face/detection`

Detects all faces in any uploaded image.
*   Faces in the image are listed with bounding boxes, gender, age, and detection scores using InsightFace model.
*   Detected faces are visualized with boxes drawn on the image.
*   Results can be downloaded as PDF report.

##### b) Face Comparison
**Route:** `/face/comparison`

Analyzes whether the first face in each of two different uploaded images matches (1:1 Comparison).
*   Cosine similarity is calculated and compared with user-defined threshold.
*   Returns "Match Found" or "No Match Found" result.
*   Results can be downloaded as PDF report.

---

#### 5. Multiple Database Collections

EyeOfWeb supports multiple Milvus collections and PostgreSQL tables to manage different data sources.

| Collection / Table Name           | Description                                                                 |
| :------------------------------- | :----------------------------------------------------------------------- |
| `EyeOfWebFaceDataMilvus`         | Main face vector collection collected by system's web crawling.        |
| `WhiteListFacesMilvus`           | Collection of manually added "recognized" or "allowed" faces.|
| `ExternalFaceStorageMilvus`      | Faces transferred from external sources (API, etc.).                             |
| `CustomFaceStorageMilvus`        | User-defined custom collection.                                       |

---

#### 6. Admin Dashboard

**Route:** `/dashboard` (Admin users only)

A central management screen showing system-wide statistics and health status.

**Statistics Provided:**
*   `total_faces`: Total face record count.
*   `total_domains`: Number of unique scanned domains.
*   `total_images`: Total image count.
*   `high_risk`: Number of faces marked as high risk.
*   `risk_levels_chart`: Risk level distribution.
*   `categories_chart`: Website category distribution.

---

#### 7. PDF Reporting System

EyeOfWeb can produce professional format PDF reports for all analyses performed.

**Supported Reports:**
*   **Image Search Report:** `/download/image_search_report`
*   **Similar Face Search Report:** `/download/similar_search_report`
*   **Comprehensive Person Analysis Report:** `/download/comprehensive_analysis_report`
*   **Face Detection Report**
*   **Face Comparison Report**

---

### 🏛️ Technical Architecture

#### Hybrid Database System (PostgreSQL + Milvus)

EyeOfWeb uses a hybrid architecture that separately processes structural/relational data and high-dimensional vector data.

| Component       | Database   | Stored Data                                                                 | Usage Purpose                                               |
| :------------ | :----------- | :---------------------------------------------------------------------------- | :----------------------------------------------------------- |
| **Memory**    | PostgreSQL   | Users, URL components, titles, hashes, dates, risk levels | SQL queries, filtering, JOIN, metadata   |
| **Brain**     | Milvus       | 512-d Face Vectors, 212-d Landmark Vectors, 4-d FaceBox Coordinates    | ANN search (HNSW), Similarity calculation (`Cosine Similarity`)|

---

#### AI Engine: InsightFace & AntelopeV2

EyeOfWeb uses the industry-standard **InsightFace** library's **AntelopeV2** model for face detection and recognition.

**Model Features:**
| Feature                     | Value                                                                 |
| :-------------------------- | :-------------------------------------------------------------------- |
| Face Detection    | RetinaFace based, multi-scale support                               |
| Landmark Detection            | 106-point face markers (eyes, eyebrows, nose, lips, jawline, etc.)   |
| Vector Embedding Size     | 512 dimensions (float32)                                                 |
| Gender Prediction            | Binary (Male: True, Female: False)                                    |
| Age Prediction                 | Continuous value (integer)                                               |
| Detection Score              | Confidence value between 0.0 - 1.0                                          |

---

#### Security Infrastructure

EyeOfWeb is equipped with enterprise-grade security mechanisms.

| Component                     | Technology / Method             | Description                                                                                     |
| :-------------------------- | :----------------------------- | :------------------------------------------------------------------------------------------- |
| **Authentication**        | Flask-JWT-Extended             | Secure access based on JSON Web Token for all API and web interface.                           |
| **Session Management**         | Flask-Session (Server-Side)   | Session data is stored server-side. Tokens are kept in HttpOnly and SameSite cookies. |
| **Encryption**               | Flask-Bcrypt                   | User passwords are hashed and stored with bcrypt algorithm.                            |
| **CSRF Protection**           | Flask-WTF                      | Form submissions are protected against Cross-Site Request Forgery attacks.                   |
| **Rate Limiting**           | Flask-Limiter                  | IP-based request limiting (e.g., `10/minute` for `/search/image`).                      |

---

### 🛠️ Technology Stack

| Layer               | Technology                                  | Version / Notes             |
| :------------------- | :----------------------------------------- | :---------------------------- |
| **Language**              | Python                                     | 3.8+                          |
| **Web Framework**    | Flask                                      | 2.0+                          |
| **WSGI Server**      | Gunicorn / Waitress (Recommended)             | For Production               |
| **Relational DB**     | PostgreSQL                                 | 13+                           |
| **Vector DB**        | Milvus                                     | 2.3+                          |
| **DB Adapter**       | Psycopg2, PyMilvus                         |                               |
| **ML / AI**          | InsightFace (ONNX Runtime), NumPy, SciPy  | AntelopeV2 model             |
| **Image Processing**   | OpenCV (cv2), Pillow (PIL)                 |                               |
| **Security**         | Flask-JWT-Extended, Flask-Bcrypt, Flask-WTF, Flask-Limiter, Flask-Session |                               |
| **Data Parsing**  | feedparser (RSS/Atom)                      |                               |
| **Web Crawling**     | Selenium, Playwright                       | Async/Multi-tab Support       |
| **Reporting**        | ReportLab or similar (lib/pdf_generator) | PDF generation                 |
| **Frontend**         | HTML5, CSS3, JavaScript, Jinja2            | Responsive UI                 |
| **Container**        | Docker, Docker Compose                     | For Milvus deployment          |

---

### 📁 Project Structure

```
eye_of_web/
├── .git/                           # Git version control
├── .gitignore                      # Files ignored by Git
├── LICENSE                         # MIT License
├── README.md                       # This documentation file
├── img/                            # Static images (logo, etc.)
│   └── logo.png
│
└── src/                            # Main source code directory
    ├── run.py                      # Flask application startup script
    ├── requirements.txt            # Python dependencies
    │
    ├── app/                        # Flask Application Module (MVC Architecture)
    │   ├── __init__.py             # Flask application factory
    │   ├── config/                 # Application configuration files
    │   ├── controllers/            # Business logic layer
    │   ├── models/                 # Database models / ORM
    │   ├── routes/                 # URL routing and endpoint definitions (Blueprints)
    │   ├── static/                 # Static files (CSS, JS, images)
    │   └── templates/              # Jinja2 HTML templates
    │
    ├── config/                     # System configuration files
    │   ├── config.json             # GPU mode configuration
    │   └── cpu_config.json         # CPU mode configuration
    │
    ├── lib/                        # Helper libraries and tools
    │   ├── database_tools.py       # PostgreSQL & Milvus operations
    │   ├── init_insightface.py     # InsightFace model initialization
    │   └── pdf_generator.py        # PDF report generation
    │
    └── sql/                        # SQL schema and query files
```

---

### ⚙️ Installation Guide

#### System Requirements

| Component       | Minimum                        | Recommended                             |
| :------------ | :----------------------------- | :----------------------------------- |
| **OS**        | Ubuntu 18.04+ / Windows 10 WSL2 | Ubuntu 20.04+ / Debian 11+          |
| **CPU**       | 4 Cores (x86_64)            | 8+ Cores (AVX2 supported)          |
| **RAM**       | 8 GB                           | 16 GB or more                |
| **Storage**  | 100 GB (SSD recommended)          | 250 GB+ SSD                          |
| **GPU**       | Optional                      | NVIDIA GPU (CUDA 11.x+), 4GB+ VRAM   |
| **Network**        | Continuous internet connection    | Stable, high bandwidth       |

#### Step-by-Step Installation

**1. System Dependencies (Ubuntu/Debian):**
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3-dev python3-pip python3-venv git \
    postgresql postgresql-contrib libpq-dev \
    build-essential libssl-dev libffi-dev \
    docker.io docker-compose
sudo systemctl enable docker && sudo systemctl start docker
```

**2. Clone the Source Code:**
```bash
git clone https://github.com/MehmetYukselSekeroglu/eye_of_web.git
cd eye_of_web
```

**3. Create Python Virtual Environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r src/requirements.txt
```
*If using GPU:*
```bash
pip install onnxruntime-gpu
```

**4. Start Milvus Database (Docker):**
```bash
wget https://github.com/milvus-io/milvus/releases/download/v2.3.0/milvus-standalone-docker-compose.yml -O docker-compose.yml
sudo docker-compose up -d
sudo docker-compose ps
```

**5. Configure PostgreSQL Database:**
```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql

sudo -u postgres psql << EOF
CREATE DATABASE eyeofweb;
CREATE USER eyeofwebuser WITH ENCRYPTED PASSWORD 'strong_password_here';
GRANT ALL PRIVILEGES ON DATABASE eyeofweb TO eyeofwebuser;
\q
EOF
```

**6. Create Database Schemas:**
```bash
python src/MILVUS_SCHEMA_GENERATOR.py
```

**7. Start the Application:**
```bash
python src/run.py
```
Navigate to `http://localhost:5000` in your browser.

---

### ⚙️ Configuration Options

#### InsightFace (GPU/CPU) Configuration

**`src/config/config.json` (GPU Mode):**
```json
{
  "insightface": {
    "prepare": {
      "ctx_id": 0,
      "det_thresh": 0.6,
      "det_size": [640, 640]
    },
    "main": {
      "providers": ["CUDAExecutionProvider"],
      "name": "antelopev2"
    }
  }
}
```

**`src/config/cpu_config.json` (CPU Mode):**
```json
{
  "insightface": {
    "prepare": {
      "ctx_id": -1,
      "det_thresh": 0.5,
      "det_size": [160, 160]
    },
    "main": {
      "providers": ["CPUExecutionProvider"],
      "name": "antelopev2"
    }
  }
}
```

---

### 📄 License

This project is licensed under the **MIT License**.

Summary:
*   You can freely use the software for commercial or non-commercial purposes.
*   You can modify and distribute the source code.
*   You must keep the license and copyright notice.
*   **NO WARRANTY IS PROVIDED.** The software is provided "AS IS".

See the `LICENSE` file in the project root directory for the full license text.

---

### 🙏 Acknowledgements

We would like to thank everyone who contributed to the realization of this project.

---

#### Advisor / Instructor

| | |
|---|---|
| **Name** | **Uğur POLAT** |
| **Contribution** | Academic Guidance, Project Management, Architectural Vision and Technical Consulting |

---

#### Project Owner / Lead Developer

| | |
|---|---|
| **Name** | **Mehmet Yüksel ŞEKEROĞLU** |
| **Contribution** | Full-stack Development, AI Model Integration, Database Design, System Architecture and Documentation |

---

---

## 📸 User Interface Screenshots / Kullanıcı Arayüzü Ekran Görüntüleri

---

### 🇹🇷 Türkçe

| Ekran | Görüntü |
|-------|---------|
| **Karşılama Ekranı** | ![Welcome Screen](img/welcome_screen.png) |
| **Metin Araması Girişi** | ![Text Search Input](img/text_search_input.png) |
| **Metin Araması Sonuçları** | ![Text Search Results](img/text_search_results.png) |
| **Yüz Araması - Resim Ekleme** | ![Face Search Add Picture](img/face_serch_move_1_add_picture.png) |
| **Yüz Araması - Sonuçlar** | ![Face Search Results](img/face_search_move_2_results.png) |
| **Yüz Araması - Gelişmiş Sonuçlar** | ![Face Search Advanced Results](img/face_search_move_3_advanced_results.png) |
| **Yüz Tespiti** | ![Face Detection](img/face_detection.png) |
| **Yüz Karşılaştırma** | ![Face Comparison](img/face_comparsion.png) |

---

### 🇬🇧 English

| Screen | Image |
|--------|-------|
| **Welcome Screen** | ![Welcome Screen](img/welcome_screen.png) |
| **Text Search Input** | ![Text Search Input](img/text_search_input.png) |
| **Text Search Results** | ![Text Search Results](img/text_search_results.png) |
| **Face Search - Add Picture** | ![Face Search Add Picture](img/face_serch_move_1_add_picture.png) |
| **Face Search - Results** | ![Face Search Results](img/face_search_move_2_results.png) |
| **Face Search - Advanced Results** | ![Face Search Advanced Results](img/face_search_move_3_advanced_results.png) |
| **Face Detection** | ![Face Detection](img/face_detection.png) |
| **Face Comparison** | ![Face Comparison](img/face_comparsion.png) |

---

<div align="center">

  ---

  <sub>Designed & Developed with ❤️ by **Mehmet Yüksel Şekeroğlu**</sub>

  <sub>© 2024-2026 EyeOfWeb Project. All rights reserved under MIT License.</sub>

</div>