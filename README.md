# EyeOfWeb Anti-Terör Sistemi

<div align="center">
  <img src="img/logo.png" alt="EyeOfWeb Logo" width="300" />
</div>

## Proje Açıklaması

EyeOfWeb Anti-Terör Sistemi, web sitelerinden toplanan görüntülerde tespit edilen yüzleri arama ve analiz etmeye yönelik geliştirilmiş güçlü bir web uygulaması ve API'dir. Sistem, terörizm faaliyetlerini izlemek ve tespit etmek amacıyla tasarlanmış olup, gelişmiş görsel analizi ve derin öğrenme tabanlı yüz tanıma teknolojilerini kullanarak kapsamlı tarama ve arama yetenekleri sunmaktadır.

Proje, çeşitli web sitelerini otomatik olarak tarayarak içerdikleri görüntüleri toplar, bu görüntülerde bulunan yüzleri tespit eder, analiz eder ve veritabanında saklar. Kullanıcılar, web arayüzü veya API aracılığıyla bu veritabanında metin bazlı veya görsel bazlı aramalar gerçekleştirebilir, sonuçları filtreleyebilir ve detaylı raporlar alabilirler.

## Teknolojiler ve Kütüphaneler

### Backend Teknolojileri
- **Python 3.8+**: Tüm backend işlemleri için ana programlama dili olarak kullanılmaktadır. Python'un zengin kütüphane ekosistemi ve veri işleme yetenekleri projenin temelini oluşturur.
- **Flask**: Hafif ve esnek web framework olarak tercih edilmiştir. Modüler yapısı sayesinde projenin farklı bileşenlerinin entegrasyonunu kolaylaştırır.
- **PostgreSQL**: İlişkisel veritabanı sistemi olarak kullanılmaktadır. Yapılandırılmış veri, kullanıcı bilgileri ve meta veriler gibi yapılandırılmış veri saklanması için kullanılır.
- **Milvus**: Vektör veritabanı olarak yüz vektörlerinin verimli saklanması ve benzerlik aramaları için kullanılır. Yüksek performanslı vektör aramaları yapabilen dağıtık mimari sağlar.
- **InsightFace + AntelopeV2**: En son teknoloji derin öğrenme modeli olan AntelopeV2, yüz tespiti, özellik çıkarımı ve yüz eşleştirme işlemlerini gerçekleştirir. 106 noktalı yüz landmark tespiti, 512 boyutlu yüz vektörü ve gelişmiş yüz analizi sağlar.
- **OpenCV**: Güçlü bir bilgisayarlı görü kütüphanesi olarak görüntü işleme, ön işleme ve analiz için kullanılmaktadır.
- **NumPy/SciPy**: Bilimsel hesaplamalar, vektör işlemleri ve matematiksel analizler için kullanılan temel kütüphanelerdir.
- **ONNX Runtime**: Farklı derin öğrenme çerçevelerinde eğitilmiş modellerin optimize edilmiş çalıştırma ortamını sağlar. InsightFace modellerinin verimli çalıştırılmasını sağlar.

### Güvenlik Altyapısı
- **Flask-JWT-Extended**: JSON Web Token (JWT) tabanlı kimlik doğrulama sistemi. Güvenli API erişimi ve oturum yönetimi sağlar.
- **Flask-Bcrypt**: Şifre şifreleme ve doğrulama için kullanılan güçlü kriptografik kütüphane. Kullanıcı şifrelerinin güvenli bir şekilde saklanmasını sağlar.
- **Flask-Limiter**: API rate limiting mekanizması. Brute force ve DDoS saldırılarına karşı koruma sağlar ve sistem kaynaklarının adil kullanımını garantiler.
- **Flask-Session**: Sunucu taraflı oturum yönetimi. Oturum verilerinin güvenli saklanması ve yönetilmesini sağlar.
- **Flask-WTF**: CSRF (Cross-Site Request Forgery) koruması ve form doğrulama araçları sağlar.

### Veri İşleme ve İntegrasyon
- **Flask-CORS**: Cross-Origin Resource Sharing desteği ile farklı kaynaklardan gelen isteklerin güvenli bir şekilde işlenmesini sağlar.
- **feedparser**: RSS ve Atom beslemelerini okumak için kullanılan güçlü kütüphane. Haber siteleri ve blog içeriklerinin otomatik taranmasını mümkün kılar.
- **Pillow**: Gelişmiş görüntü işleme yetenekleri sunan Python kütüphanesi. Görüntü formatı dönüşümleri, yeniden boyutlandırma ve ön işleme için kullanılır.

## Sistem Mimarisi ve Veri Akışı

EyeOfWeb sistemi, birbirleriyle entegre çalışan çeşitli modüllerden oluşan katmanlı bir mimariye sahiptir:

1. **Veri Toplama Katmanı**:
   - Web tarayıcıları ve RSS okuyucuları
   - Görüntü çıkarıcılar ve indirme işlemcileri
   - URL sıralayıcılar ve öncelik belirleyiciler

2. **Veri İşleme Katmanı**:
   - Görüntü ön işleme ve normalizasyon
   - Yüz algılama ve özellik çıkarma (AntelopeV2 modeli kullanılarak)
   - Vektör eşleştirme ve benzerlik hesaplama

3. **Veritabanı Katmanı**:
   - İlişkisel veritabanı (PostgreSQL) ile meta veri depolama
   - Vektör veritabanı (Milvus) ile yüz vektörlerinin depolanması ve hızlı benzerlik aramaları
   - İndeksleme ve vektör arama yapıları (HNSW indeks)

4. **Uygulama Katmanı**:
   - RESTful API servisleri
   - Web arayüzü ve kullanıcı paneli
   - Kimlik doğrulama ve yetkilendirme sistemi

5. **Analiz Katmanı**:
   - İstatistik ve raporlama araçları
   - Veri görselleştirme bileşenleri
   - Trend analizi ve örüntü tespiti

## Yüz Vektörü Depolama ve Arama: Milvus Entegrasyonu

Sistemin en kritik bileşenlerinden biri, yüz vektörlerinin verimli şekilde saklanması ve aranmasıdır. Bu amaçla, Milvus vektör veritabanı kullanılmaktadır:

### Milvus Koleksiyonları
Sistem içinde aşağıdaki Milvus koleksiyonları kullanılmaktadır:

1. **CustomFaceStorageMilvus**: Kullanıcı tarafından eklenen yüzlerin vektör verilerini saklar
2. **WhiteListFacesMilvus**: Beyaz listeye alınan yüzlerin vektörlerini saklar
3. **ExternalFaceStorageMilvus**: Dış kaynaklardan alınan yüzlerin vektörlerini saklar
4. **EgmArananlarMilvus**: EGM arananlar listesindeki yüzlerin vektörlerini saklar
5. **EyeOfWebFaceDataMilvus**: Sistem tarafından toplanan yüz verileri için kullanılır

### Vektör İndeksleme ve Arama
- **HNSW (Hierarchical Navigable Small World)** indeksleme algoritması kullanılarak yüksek performanslı yaklaşık en yakın komşu aramaları yapılır
- **Kosinüs Benzerliği**: Yüz vektörleri arasındaki benzerlik kosinüs metriği kullanılarak hesaplanır
- **Vektör Boyutları**: 
  - Yüz embeddingler: 512 boyutlu vektörler
  - Landmark vektörleri: 106 noktalı, 212 boyutlu düzleştirilmiş vektörler
  - Yüz kutuları: 4 boyutlu vektörler (x, y, genişlik, yükseklik)

## InsightFace AntelopeV2 Modeli

Sistem, yüz tanıma işlemleri için InsightFace kütüphanesinin AntelopeV2 modelini kullanmaktadır. Bu model, önceki Buffalo_L modeline göre daha ileri özelliklere sahiptir:

### AntelopeV2 Özellikleri
- **Yüksek Doğruluk**: En son teknoloji yüz algılama ve tanıma algoritmaları
- **106 Noktalı Landmark Tespiti**: Daha ayrıntılı yüz özelliklerinin yakalanması
- **512 Boyutlu Yüz Vektörleri**: Zengin yüz özellik temsili
- **Gelişmiş Yaş ve Cinsiyet Analizi**: Daha doğru demografik öznitelik çıkarımı
- **GPU/CPU Desteği**: CUDA ve CPU ExecutionProvider desteğiyle esnek çalışma

### Model Yapılandırması
Sistem iki farklı çalışma modu sunmaktadır:
- **GPU Modu**: CUDA desteği ile yüksek performanslı işleme (config.json)
- **CPU Modu**: GPU olmayan sistemler için optimize edilmiş işleme (cpu_config.json)

## Proje Yapısı ve Bileşenler

```
/
├── img/                       # Görsel dosyaları (logo vb.)
├── src/                       # Kaynak kod
│   ├── app/                   # Flask web uygulaması
│   │   ├── config/            # Uygulama yapılandırma dosyaları
│   │   ├── controllers/       # İşlem kontrolcüleri
│   │   ├── models/            # Veritabanı modelleri
│   │   ├── routes/            # API ve web rotaları
│   │   ├── static/            # Statik dosyalar
│   │   ├── templates/         # HTML şablonları
│   │   └── __init__.py        # Flask uygulama factory
│   ├── config/                # Sistem yapılandırma dosyaları
│   │   ├── config.json        # GPU yapılandırması
│   │   └── cpu_config.json    # CPU yapılandırması
│   ├── lib/                   # Yardımcı kütüphaneler
│   │   ├── database_tools.py  # Veritabanı işlemleri
│   │   ├── init_insightface.py# InsightFace başlatma
│   │   └── load_config.py     # Yapılandırma yükleme
│   ├── sql/                   # SQL sorgu dosyaları
│   ├── MILVUS_SCHEMA_GENERATOR.py # Milvus şema oluşturma
│   ├── migration_to_milvus.py # PostgreSQL'den Milvus'a veri aktarımı
│   ├── egm_loader.py          # EGM veri yükleme işlemleri
│   ├── general_whitelist_loader.py # Beyaz liste yükleme
│   ├── requirements.txt       # Python bağımlılıkları
│   └── run.py                 # Ana uygulama başlatma betiği
└── backups/                   # Yedekleme dosyaları
```

## Temel Özellikler ve Detaylı Açıklamaları

### 1. Yüz Tanıma ve Arama (Milvus + AntelopeV2)
   - **InsightFace AntelopeV2 Entegrasyonu**: 106 noktalı yüz landmark tespiti, 512 boyutlu yüz vektörü çıkarımı ve gelişmiş cinsiyet/yaş analizi yetenekleri
   - **Milvus Vektör Araması**: Kosinüs benzerliği ve HNSW indeksleme ile milisaniyeler içinde milyonlarca yüz vektörü arasında arama yapabilme
   - **Çoklu Koleksiyon Araması**: Tek sorguda farklı veri kaynaklarında (normal veritabanı, beyaz liste, EGM listesi) paralel aramalar yapabilme
   - **Dinamik Benzerlik Eşiği**: Arama hassasiyetini kontrol etmek için ayarlanabilir benzerlik eşiği

### 2. PostgreSQL ve Milvus Hibrit Veritabanı Yapısı
   - **Meta Veri Depolama**: PostgreSQL'de yüz görüntüleri, açıklamalar ve ilişkisel veriler saklanır
   - **Vektör Depolama**: Milvus'ta yüz vektörleri, landmark vektörleri ve yüz kutuları saklanır
   - **Referans Bütünlüğü**: PostgreSQL kayıtları Milvus koleksiyonlarına MilvusID alanı ile bağlanır
   - **Paralel Sorgulama**: Metin bazlı sorgular PostgreSQL'de, benzerlik aramaları Milvus'ta gerçekleştirilir

### 3. Web Tarama ve İçerik Toplama
   - **Domain Bazlı Tarama**: Belirli bir internet alanının tamamı veya alt bölümleri derinlemesine taranabilir
   - **RSS Besleme Takibi**: Yüzlerce haber sitesi ve blog düzenli olarak taranarak yeni içerikler tespit edilir
   - **Öncelikli Tarama**: Önemli kaynaklar daha sık taranır
   - **İçerik Analizi**: Metin ve görseller analiz edilerek ilgili bilgiler çıkarılır

### 4. Güvenli Kullanıcı Yönetimi
   - **JWT Kimlik Doğrulama**: Hem web hem API için güvenli erişim
   - **Rol Tabanlı Erişim**: Farklı kullanıcı yetkilendirme seviyeleri
   - **Oturum Yönetimi**: Sunucu taraflı güvenli oturum kontrolü
   - **İşlem Kaydı**: Tüm kullanıcı aktiviteleri loglanır

### 5. RESTful API ve Entegrasyon
   - **Kapsamlı API**: Tüm özelliklere programatik erişim
   - **Rate Limiting**: API istekleri sınırlandırılır
   - **Webhook Desteği**: Önemli olaylar için bildirimler
   - **Batch İşlemler**: Toplu veri işleme desteği

## Milvus Veritabanına Geçiş

Sistemde yapılan en önemli güncellemelerden biri, yüz vektörlerinin PostgreSQL'den Milvus'a taşınmasıdır. Bu geçiş aşağıdaki avantajları sağlar:

1. **Performans Artışı**: 
   - PostgreSQL'de vektör aramaları yavaş ve kaynak yoğun iken, Milvus özel vektör indeksleri sayesinde çok daha hızlı benzerlik aramaları sağlar
   - Yüz vektörlerinin 512 boyutlu karmaşık yapısında Milvus, optimum performans sunar

2. **Ölçeklenebilirlik**:
   - Milvus, dağıtık mimarisi sayesinde veri hacmi arttıkça ölçeklenebilir
   - Yüksek boyutlu vektörler için özel olarak tasarlanmış indeksleme yapıları (HNSW) kullanır

3. **Veri Göçü**:
   - `migration_to_milvus.py` betiği ile verilerin PostgreSQL'den Milvus'a taşınması otomatikleştirilmiştir
   - Orijinal PostgreSQL tabloları MilvusID referansları ile korunarak hibrit yapı sağlanmıştır

4. **Hibrit Sorgulama**:
   - Metin bazlı aramalar hala PostgreSQL üzerinden yapılırken, benzerlik aramaları Milvus üzerinden gerçekleştirilir
   - Her iki veritabanının güçlü yanları birleştirilmiştir

## Kurulum ve Konfigürasyon

### Sistem Gereksinimleri
- **İşletim Sistemi**: Linux (Ubuntu 18.04+, Debian 10+)
- **CPU**: En az 4 çekirdekli modern işlemci (Intel i5/i7 7. nesil veya daha yeni, AMD Ryzen 5/7)
- **RAM**: Minimum 8GB, önerilen 16GB veya daha fazla
- **Depolama**: En az 100GB boş alan (SSD önerilir)
- **GPU (opsiyonel)**: NVIDIA GPU (CUDA 11.2+ destekli) yüz tanıma işlemlerini hızlandırır
- **Ağ**: Sürekli ve kararlı internet bağlantısı

### Kurulum Adımları

1. **Sistem Bağımlılıklarının Kurulumu**:
   ```bash
   # Ubuntu/Debian için
   sudo apt-get update
   sudo apt-get install -y python3-dev python3-pip postgresql postgresql-contrib libpq-dev build-essential libssl-dev libffi-dev
   ```

2. **PostgreSQL Veritabanı Kurulumu**:
   ```bash
   # PostgreSQL servisini başlat
   sudo systemctl start postgresql
   sudo systemctl enable postgresql
   
   # Veritabanı ve kullanıcı oluştur
   sudo -u postgres psql -c "CREATE DATABASE eyeofwebmilvus;"
   sudo -u postgres psql -c "CREATE USER eyeofwebuser WITH PASSWORD 'secure_password';"
   sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE eyeofwebmilvus TO eyeofwebuser;"
   ```

3. **Milvus Kurulumu (Docker ile)**:
   ```bash
   # Docker ve Docker Compose kurun
   sudo apt-get install -y docker.io docker-compose
   
   # Milvus Docker Compose yapılandırması indirin
   wget https://github.com/milvus-io/milvus/releases/download/v2.3.0/milvus-standalone-docker-compose.yml -O docker-compose.yml
   
   # Milvus'u başlatın
   sudo docker-compose up -d
   ```

4. **Python Bağımlılıklarının Kurulumu**:
   ```bash
   pip install -r src/requirements.txt
   
   # CUDA destekli InsightFace için (GPU varsa)
   pip install onnxruntime-gpu
   ```

5. **Milvus Şemasını Oluşturma**:
   ```bash
   python src/MILVUS_SCHEMA_GENERATOR.py
   ```

6. **Uygulama Başlatma**:
   ```bash
   python src/run.py
   ```

### Yapılandırma Seçenekleri

Sistem, yapılandırma dosyaları aracılığıyla özelleştirilebilir:

#### 1. Milvus ve AntelopeV2 Yapılandırması:

- GPU Kullanımı (`src/config/config.json`):
  ```json
  "insightface": {
      "prepare": {
          "ctx_id": 0,  // 0: ilk GPU, -1: CPU kullanımı
          "det_thresh": 0.6,
          "det_size": [640, 640]
      },
      "main": {
          "providers": ["CUDAExecutionProvider"],
          "name": "antelopev2"
      }
  }
  ```

- CPU Kullanımı (`src/config/cpu_config.json`):
  ```json
  "insightface": {
      "prepare": {
          "ctx_id": -1,  // CPU kullanımı
          "det_thresh": 0.5,
          "det_size": [160, 160]  // Düşük çözünürlük, daha az bellek kullanımı
      },
      "main": {
          "providers": ["CPUExecutionProvider"],
          "name": "antelopev2"
      }
  }
  ```

#### 2. Milvus Bağlantı Yapılandırması:

```python
# Milvus bağlantı parametreleri
MILVUS_HOST = "127.0.0.1"  # Milvus sunucu adresi
MILVUS_PORT = "19530"      # Milvus sunucu portu
MILVUS_CONNECTION_ALIAS = "default"
```

## Güvenlik Önlemleri ve En İyi Uygulamalar

- **Veritabanı Güvenliği**: PostgreSQL ve Milvus erişimi güçlü parolalar ve kısıtlı erişim hakları ile korunmalıdır
- **API Güvenliği**: Tüm API istekleri JWT ile doğrulanmalı ve rate limiting uygulanmalıdır
- **HTTPS Kullanımı**: Production ortamında HTTPS kullanılması zorunludur
- **Düzenli Yedekleme**: PostgreSQL veritabanı ve Milvus verileri düzenli olarak yedeklenmelidir
- **Milvus Veritabanı Bakımı**: Milvus koleksiyonları için düzenli bakım işlemleri yapılmalıdır

## Notlar ve Öneriler

- **Yüksek Performans**: AntelopeV2 modeli GPU üzerinde önemli ölçüde hız artışı sağlar
- **Milvus Ölçeklendirme**: Veri hacmi arttıkça Milvus, çok düğümlü çalışma moduna geçirilebilir
- **Veritabanı Yedekleme**: PostgreSQL ve Milvus için ayrı yedekleme stratejileri uygulanmalıdır
- **Yasal Uyumluluk**: Veri toplama ve işleme süreçleri, ilgili kanun ve yönetmeliklere uygun olmalıdır 