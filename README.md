
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

  **[🇹🇷 Türkçe Dokümantasyon](#-türkçe-dokümantasyon)** | **[🇬🇧 English Documentation](#-english-documentation)**

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

1.  [Yönetici Özeti](#-yönetici-özeti)
2.  [Temel Özellikler](#-temel-özellikler-ve-yetenekler)
    *   [Kapsamlı Kişi Analizi](#1-kapsamlı-kişi-analizi-comprehensive-person-analysis)
    *   [Derin İlişki Analizi (Deep Insight)](#2-derin-i̇lişki-analizi-deep-insight)
    *   [Birden Fazla Arama Modu](#3-birden-fazla-arama-modu)
    *   [Yüz Tespiti ve Karşılaştırma](#4-yüz-tespiti-ve-karşılaştırma)
    *   [Birden Fazla Veritabanı Koleksiyonu](#5-birden-fazla-veritabanı-koleksiyonu)
    *   [Yönetici Paneli (Dashboard)](#6-yönetici-paneli-dashboard)
    *   [PDF Raporlama Sistemi](#7-pdf-raporlama-sistemi)
3.  [Teknik Mimari](#-teknik-mimari)
    *   [Hibrit Veritabanı Sistemi](#hibrit-veritabanı-sistemi-postgresql--milvus)
    *   [Yapay Zeka Motoru (InsightFace)](#yapay-zeka-motoru-insightface--antelopev2)
    *   [Güvenlik Alt Yapısı](#güvenlik-alt-yapısı)
    *   [Görüntü İşleme Hattı](#görüntü-i̇şleme-hattı-image-sanitization-pipeline)
4.  [Teknoloji Yığıtı (Tech Stack)](#-teknoloji-yığıtı-tech-stack)
5.  [Proje Yapısı](#-proje-yapısı)
6.  [Kurulum Rehberi](#️-kurulum-rehberi)
7.  [Yapılandırma Seçenekleri](#️-yapılandırma-seçenekleri)
8.  [Lisans](#-lisans)
9.  [Teşekkür ve Katkıda Bulunanlar](#-teşekkür-ve-katkıda-bulunanlar)

---

### 📄 Yönetici Özeti

**EyeOfWeb**, Açık Kaynak İstihbaratı (Open Source Intelligence - OSINT) metodolojilerini, en son nesil derin öğrenme tabanlı biyometrik analiz teknolojileriyle birleştiren kapsamlı ve profesyonel bir güvenlik istihbarat platformudur.

Sistem, internet üzerindeki çeşitli kaynaklardan (haber portalları, bloglar, RSS beslemeleri ve benzeri) görsel verileri otonom olarak tarar, bu görsellerde bulunan yüzleri tespit eder, her bir yüz için benzersiz bir matematiksel vektör (embedding) oluşturur ve bu vektörleri yüksek performanslı bir vektör veritabanında (Milvus) indeksler. Paralel olarak, yüzlerin tespit edildiği kaynak, tarih, risk seviyesi gibi meta veriler ilişkisel bir veritabanında (PostgreSQL) saklanır.

Bu "hibrit veritabanı mimarisi" sayesinde EyeOfWeb, milyarlarca yüz verisi arasında **milisaniyeler içinde** 1:N kimlik arama, 1:1 yüz karşılaştırma, sosyal ilişki ağı/birliktelik analizi ve kişi profilleme gibi gelişmiş analizleri gerçekleştirebilir.

---

### 🚀 Temel Özellikler ve Yetenekler

Aşağıda EyeOfWeb'in `src/app/routes/web.py` modülünde tanımlanan ve kullanıcı arayüzü/API aracılığıyla erişilebilen tüm temel özellikleri detaylı olarak açıklanmaktadır.

---

#### 1. Kapsamlı Kişi Analizi (Comprehensive Person Analysis)

Bu, EyeOfWeb'in en güçlü ve sofistike analiz aracıdır. Belirli bir kişinin fotoğrafları üzerinden kapsamlı bir sosyometrik analiz gerçekleştirir.

**Rota:** `/comprehensive_person_analysis/<face_id>`

**Çalışma Mantığı:**
1.  **Hedef Kişi Belirleme:** Seçilen yüz ID'si (`face_id`) hedef kişi olarak belirlenir.
2.  **Benzer Yüzlerin Toplanması (Aynı Kişinin Farklı Fotoğrafları):** Milvus vektör veritabanında hedef kişinin yüz vektörüne benzer tüm yüzler bulunur. Belirlenen benzerlik eşiğini (varsayılan: 0.45) aşan vektörler "aynı kişi" olarak kabul edilir ve bir grup oluşturulur.
3.  **İlgili Tüm Görsellerin Bulunması:** Hedef kişi grubundaki herhangi bir yüzü içeren tüm görseller PostgreSQL'den çekilir. Bu aşamada görüntülerin benzersizliğini sağlamak için `ImageHash` (görsel özet/fingerprint) tabanlı tekilleştirme yapılır. Böylece aynı görselin farklı kaynaklardan çekilmiş kopyaları tekrar tekrar işlenmez.
4.  **İlişkili Yüzlerin Çıkarılması:** Bulunan görsellerdeki hedef kişi dışındaki tüm yüzler toplanır.
5.  **İlişkili Yüzlerin Gruplanması:** Bu "diğer" yüzler de kendi aralarında benzerlik eşiğine göre gruplanır. Böylece, hedef kişiyle görülmüş olan her farklı kişi için bir grup oluşturulmuş olur.
6.  **Birlikte Görülme Sayısının Hesaplanması:** Her bir "ilişkili kişi" grubunun, hedef kişiyle kaç farklı görselde birlikte göründüğü hesaplanır.
7.  **Sonuçların Sunulması:** Sonuçlar, birlikte görülme sayısına göre sıralanarak sunulur. Bu, hedef kişiyle en sık etkileşimde bulunan kişilerin belirlenmesini sağlar.

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
| **Raporlama**        | ReportLab veya benzeri (lib/pdf_generator) | PDF oluşturma                 |
| **Frontend**         | HTML5, CSS3, JavaScript, Jinja2            | Responsive UI                 |
| **Konteyner**        | Docker, Docker Compose                     | Milvus dağıtımı için          |

---

### 📁 Proje Yapısı

```
EyeOfWeb/
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
git clone https://github.com/MehmetYukselSekeroglu/EyeOfWeb.git
cd EyeOfWeb
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

1.  [Executive Summary](#-executive-summary)
2.  [Core Features](#-core-features)
3.  [Technical Architecture](#️-technical-architecture-overview)
4.  [Technology Stack](#-technology-stack)
5.  [Installation](#️-installation-summary)
6.  [License](#-license-1)
7.  [Acknowledgements](#-acknowledgements)

---

### 📄 Executive Summary

**EyeOfWeb** is a state-of-the-art **Facial Intelligence & Security Analysis Platform** designed for OSINT (Open Source Intelligence) operations. It leverages cutting-edge deep learning models to autonomously crawl web sources, detect faces, generate unique mathematical vectors (embeddings), and index them in a high-performance vector database (Milvus).

The system's **hybrid database architecture** (PostgreSQL for relational metadata + Milvus for vector embeddings) enables it to perform complex queries—such as 1:N identity searches, social network analysis, and person profiling—across billions of face vectors in **milliseconds**.

---

### 🚀 Core Features

*   **Comprehensive Person Analysis:** Identifies all images containing a target individual (and their look-alikes), then analyzes co-occurrence patterns with other faces to map their social network.
*   **Deep Insight (Co-occurrence Analysis):** Quickly identifies which other faces appear most frequently in the same images as a target face.
*   **Multiple Search Modes:**
    *   Image-based search (upload a photo to find matches).
    *   Text/Filter-based search (filter by domain, date range, risk level, category).
    *   Similarity search (find faces similar to an existing database entry).
*   **Face Detection & Comparison:** Detect all faces in an uploaded image or compare two faces 1:1.
*   **Multiple Database Collections:** Separate collections for main data, whitelists, external data, and watchlists (e.g., EGM format).
*   **Admin Dashboard:** Real-time statistics on total faces, domains, images, risk distribution, and database health.
*   **PDF Reporting:** Generate professional, timestamp-verified PDF reports for all analysis types.
*   **Enterprise-Grade Security:** JWT authentication, server-side sessions, bcrypt password hashing, CSRF protection, rate limiting, and robust image sanitization.

---

### 🏛️ Technical Architecture Overview

| Component         | Technology         | Purpose                                                     |
| :---------------- | :----------------- | :---------------------------------------------------------- |
| **Relational DB** | PostgreSQL         | Stores metadata: URLs, timestamps, risk levels, user data.  |
| **Vector DB**     | Milvus             | Stores and indexes 512-dim face embeddings for ANN search.  |
| **AI Engine**     | InsightFace (AntelopeV2) | Face detection, 106-point landmark, embedding extraction. |
| **Web Framework** | Flask              | Handles HTTP requests, routing, and templating.             |
| **Image Processing** | OpenCV, Pillow  | Image manipulation, sanitization, and format conversion.    |

---

### 🛠️ Technology Stack

*   **Backend:** Python 3.8+, Flask
*   **Databases:** PostgreSQL, Milvus
*   **AI/ML:** InsightFace, ONNX Runtime, NumPy, SciPy
*   **Security:** Flask-JWT-Extended, Flask-Bcrypt, Flask-WTF, Flask-Limiter
*   **Image Processing:** OpenCV, Pillow
*   **Frontend:** HTML5, CSS3, JavaScript, Jinja2

---

### ⚙️ Installation Summary

1.  **Setup Infrastructure:** Deploy Milvus via Docker, configure PostgreSQL.
2.  **Clone Repository:** `git clone <repo_url>`
3.  **Install Dependencies:** `pip install -r src/requirements.txt`
4.  **Configure:** Update database connection settings and InsightFace mode (GPU/CPU) in config files.
5.  **Initialize Schemas:** Run `python src/MILVUS_SCHEMA_GENERATOR.py` and PostgreSQL SQL scripts.
6.  **Run:** `python src/run.py`

---

### 📄 License

This project is licensed under the **MIT License**. See the `LICENSE` file for details.

---

### 🙏 Acknowledgements

*   **Advisor / Instructor:** **Uğur POLAT**
*   **Project Owner / Lead Developer:** **Mehmet Yüksel ŞEKEROĞLU**

---

<div align="center">

  ---

  <sub>Designed & Developed with ❤️ by **Mehmet Yüksel Şekeroğlu**</sub>

  <sub>© 2024-2026 EyeOfWeb Project. All rights reserved under MIT License.</sub>

</div>