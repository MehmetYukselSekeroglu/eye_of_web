# 🤝 EyeOfWeb — Geliştirme Kuralları

Bu belge, EyeOfWeb projesine katkıda bulunacak tüm geliştiriciler için geçerli olan standartları ve kuralları tanımlar. Projeye katkıda bulunmadan önce lütfen bu belgeyi dikkatlice okuyun.

---

## 📁 Dosya ve Klasör Yapısı

```
eye_of_web/
├── doc/                        # Dokümantasyon dosyaları (.md)
├── img/                        # Proje görselleri (logo, ekran görüntüleri)
└── src/
    ├── app/
    │   ├── config/             # Flask uygulama yapılandırması
    │   ├── controllers/        # İş mantığı katmanı
    │   ├── models/             # Veritabanı modelleri
    │   ├── routes/             # URL rotaları (Blueprint)
    │   ├── static/             # CSS, JS, görseller
    │   └── templates/          # Jinja2 HTML şablonları
    ├── config/                 # Sistem yapılandırma dosyaları (GPU/CPU)
    ├── lib/                    # Yardımcı kütüphaneler
    ├── sql/                    # Veritabanı şema dosyaları
    ├── logs/                   # Log dosyaları (git'e eklenmez)
    ├── temp/                   # Geçici indirilen görseller (git'e eklenmez)
    └── downloaded_profile_pics/ # İndirilen profil fotoğrafları (git'e eklenmez)
```

### Kurallar

- Yeni bir crawler ekleniyorsa `src/` dizinine, `*_crawler.py` uzantısıyla eklenir.
- Yardımcı fonksiyonlar doğrudan script içine yazılmaz; `src/lib/` altına ayrı bir modül olarak eklenir.
- Yeni bir rota ekleniyorsa `src/app/routes/` altına uygun Blueprint'e yerleştirilir; yeni bir domain oluşturuyorsa ayrı dosya açılır.
- HTML şablonlar yalnızca `src/app/templates/` içinde tutulur; inline HTML üretimi yapılmaz.
- Yapılandırma değerleri (IP, port, şifre, API anahtarı) kod içine **yazılmaz**; `src/config/config.json` veya ortam değişkenleri kullanılır.
- `src/temp/`, `src/logs/` ve `src/downloaded_profile_pics/` dizinleri `.gitignore`'da tutulur ve commit'e dahil edilmez.

---

## 🐍 Kod Yazım Standartları

### Genel

- Dil: **Python 3.8+**
- Kod stili: **PEP 8** kurallarına uyulur.
- Maksimum satır uzunluğu: **120 karakter**
- Girinti: **4 boşluk** (tab kullanılmaz)
- Encoding: tüm dosyalar **UTF-8** olmalıdır.

### İsimlendirme

| Tür | Kural | Örnek |
|-----|-------|-------|
| Fonksiyon | `snake_case` | `find_similar_faces()` |
| Değişken | `snake_case` | `face_embedding` |
| Sınıf | `PascalCase` | `DatabaseTools` |
| Sabit | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| Dosya | `snake_case` | `google_search_crawler.py` |

### Fonksiyon ve Sınıflar

- Her fonksiyon tek bir iş yapar (Single Responsibility).
- Fonksiyonlar 50 satırı geçmemeye çalışılır; geçiyorsa parçalanır.
- Tüm public fonksiyonlara **docstring** yazılır:

```python
def find_similar_faces(embedding: list, threshold: float = 0.6) -> list:
    """
    Verilen embedding vektörüne benzer yüzleri Milvus'ta arar.

    Args:
        embedding (list): 512 boyutlu yüz vektörü.
        threshold (float): Minimum benzerlik eşiği (0.0 - 1.0).

    Returns:
        list: Eşleşen yüzlerin face_id listesi.
    """
```

- Tip belirteci (type hint) kullanımı **zorunludur**:

```python
def get_face_by_id(face_id: int) -> dict | None:
```

### Import Sıralaması

```python
# 1. Standart kütüphaneler
import os
import json

# 2. Üçüncü parti kütüphaneler
import numpy as np
from flask import request

# 3. Proje içi modüller
from lib.database_tools import DatabaseTools
```

### Hata Yönetimi

- `except Exception` kullanımından kaçınılır; spesifik exception türleri yakalanır.
- Hatalar sessizce geçilmez; mutlaka loglanır:

```python
try:
    result = db_tools.find_similar_faces(embedding)
except MilvusException as e:
    logger.error(f"Milvus arama hatası: {e}")
    return []
```

### Güvenlik

- Kullanıcıdan gelen tüm girdiler `validate_and_sanitize_image()` veya `html.escape()` ile temizlenir.
- API anahtarları, şifreler ve token'lar **asla** kaynak koda yazılmaz.
- Yeni bir route ekleniyorsa `@login_required` dekoratörü uygulanır.
- Dosya yükleme işlemlerinde `secure_filename()` kullanımı zorunludur.

---

## 🌿 Branch Kuralları

### Branch İsimlendirme

```
<tür>/<kısa-açıklama>
```

| Tür | Kullanım Amacı | Örnek |
|-----|---------------|-------|
| `feature` | Yeni özellik | `feature/instagram-crawler` |
| `fix` | Hata düzeltme | `fix/milvus-connection-timeout` |
| `refactor` | Kod iyileştirme | `refactor/search-controller` |
| `docs` | Dokümantasyon | `docs/crawler-guide` |
| `chore` | Bağımlılık, config | `chore/update-requirements` |
| `hotfix` | Acil production düzeltmesi | `hotfix/auth-bypass` |

### Branch Hiyerarşisi

```
main          ← production (doğrudan push yasak)
└── develop   ← aktif geliştirme dalı
    ├── feature/...
    ├── fix/...
    └── refactor/...
```

- `main` branch'e doğrudan push **yapılmaz**; yalnızca PR ile merge edilir.
- Her yeni geliştirme `develop` üzerinden branch açılır.
- Tamamlanan branch'ler merge sonrası silinir.

---

## 📝 Commit Kuralları

### Format

```
<tür>(<kapsam>): <kısa açıklama>

[isteğe bağlı gövde]

[isteğe bağlı footer]
```

### Commit Türleri

| Tür | Açıklama |
|-----|----------|
| `feat` | Yeni özellik |
| `fix` | Hata düzeltme |
| `refactor` | Davranış değişikliği olmayan kod düzenlemesi |
| `docs` | Sadece dokümantasyon değişikliği |
| `style` | Biçimlendirme (boşluk, virgül vb.) |
| `test` | Test ekleme veya düzenleme |
| `chore` | Build, bağımlılık, CI/CD |
| `perf` | Performans iyileştirmesi |
| `security` | Güvenlik düzeltmesi |

### Örnekler

```bash
feat(crawler): instagram profil fotoğrafı tarayıcısı eklendi
fix(milvus): bağlantı zaman aşımı sorunu giderildi
refactor(search): benzer yüz arama fonksiyonu parçalandı
docs(crawler): Playwright kullanım kılavuzu güncellendi
security(auth): JWT token süresi 24 saatten 8 saate düşürüldü
```

### Commit Kuralları

- Commit mesajları **Türkçe** yazılır.
- Mesajlar emir kipinde, geniş zaman ile yazılır: "eklendi", "düzeltildi", "güncellendi".
- Tek commit'te birden fazla alakasız değişiklik yapılmaz (atomik commit).
- `WIP` commit'leri `develop`'a push edilmeden önce squash'lanır.

---

## 🔀 Pull Request Süreci

### PR Açmadan Önce

- [ ] Kod PEP 8 kurallarına uygun mu?
- [ ] Tüm fonksiyonlara docstring ve tip belirteci eklendi mi?
- [ ] Yeni bir bağımlılık varsa `requirements.txt` güncellendi mi?
- [ ] Güvenlik açığı oluşturabilecek bir değişiklik var mı?
- [ ] `temp/` veya `logs/` gibi geçici dosyalar commit'e dahil değil mi?

### PR Şablonu

```
## Değişiklik Özeti
<!-- Ne yaptın? Neden? -->

## Değişiklik Türü
- [ ] Yeni özellik
- [ ] Hata düzeltme
- [ ] Refactor
- [ ] Dokümantasyon

## Test Edildi mi?
- [ ] Lokal ortamda test edildi
- [ ] Docker ortamında test edildi

## İlgili Issue
Closes #<issue_no>
```

### Merge Kriterleri

- En az **1 onay** (approve) gereklidir.
- Tüm kontroller (lint, test) yeşil olmalıdır.
- Conflict çözümü PR sahibine aittir.
- Merge yöntemi: **Squash and Merge** (geçmişi temiz tutar).

---

## 🕷️ Crawler Geliştirme Kuralları

- Her crawler bağımsız çalışabilir olmalıdır (`if __name__ == "__main__"` bloğu içermeli).
- Crawler'lar `--backend` parametresi ile `selenium` veya `playwright` arasında seçim yapabilmelidir.
- Rate limiting: İstekler arası minimum **1-3 saniye** bekleme uygulanmalıdır.
- İndirilen görseller `src/temp/` altına kaydedilmeli, işlem sonrası temizlenmelidir.
- Crawler logları `src/logs/eyeofweb.log` dosyasına yazılmalıdır.
- Yeni bir platform crawler'ı ekleniyorsa `doc/CRAWLER.md` dosyası güncellenir.

---

## 🔒 Güvenlik Kuralları

- Güvenlik açığı tespit edildiğinde **public issue açılmaz**; doğrudan proje sahibine bildirilir.
- `admin` / `admin123_changeme` varsayılan kimlik bilgileri production ortamında **kesinlikle** değiştirilir.
- Yeni bir endpoint eklenirken rate limit tanımlanır (`Flask-Limiter`).
- Kullanıcı girdisi olan her noktada input validation uygulanır.

---

## 📦 Bağımlılık Yönetimi

- Yeni bir paket ekleniyorsa önce gerekçesi değerlendirilir (alternatif var mı?).
- Paket versiyonları sabitlenir: `flask==2.3.2` (aralık kullanılmaz).
- Crawler'a özel bağımlılıklar `src/crawler_requirements.txt`'e, ana uygulamaya ait olanlar `src/requirements.txt`'e eklenir.
- `pip install` işlemleri daima sanal ortamda (`venv`) yapılır.

---

## 🗄️ Veritabanı Kuralları

> ⚠️ **Bu bölüm projenin en kritik kurallarını içerir. İhlali kabul edilmez.**

### Temel İlke

**Mevcut veritabanı yapısı (PostgreSQL şeması ve Milvus koleksiyonları) hiçbir koşulda bozulamaz, değiştirilemez veya silinemez.**

Tüm geliştirmeler mevcut yapının **üzerine eklenerek** ilerlenir.

### Kesinlikle Yasak Olanlar

- Mevcut bir tablonun adını değiştirmek
- Mevcut bir kolonun adını, tipini veya kısıtlamasını değiştirmek
- Mevcut bir tabloyu veya kolonu silmek
- Mevcut Milvus koleksiyonlarının (`EyeOfWebFaceDataMilvus`, `WhiteListFacesMilvus` vb.) şemasını değiştirmek
- `src/sql/schema.sql` dosyasındaki mevcut tanımları düzenlemek
- Migration olmadan doğrudan production veritabanına `ALTER` veya `DROP` çalıştırmak

### Yeni Ekleme Yapılırken

- Yeni tablo veya kolon ekleniyorsa `src/sql/` altına **yeni bir migration dosyası** açılır:
  ```
  src/sql/migrations/YYYYMMDD_açıklama.sql
  ```
- Migration dosyası yalnızca `CREATE TABLE IF NOT EXISTS` veya `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` içerir.
- Her migration dosyasının başına amaç ve tarih belirtilir:
  ```sql
  -- Migration: 20260410_add_source_type_to_faces
  -- Amaç: Yüz kaydına kaynak türü (crawler tipi) alanı eklendi
  -- Tarih: 2026-04-10
  ```
- Milvus'a yeni koleksiyon ekleniyorsa `src/MILVUS_SCHEMA_GENERATOR.py` güncellenir; mevcut koleksiyonlara dokunulmaz.

### Veritabanı Değişikliği Gerektiren PR'lar

- PR açıklamasında "Veritabanı değişikliği içerir" etiketi açıkça belirtilir.
- İlgili migration dosyası PR'a dahil edilir.
- Değişiklik, `develop` branch'inde test edildikten sonra `main`'e alınır.

---

## 📋 Genel Prensipler

1. **Okunabilirlik** — Çalışan kod kadar okunabilir kod da önemlidir.
2. **Atomiklik** — Her commit, her fonksiyon tek bir iş yapmalıdır.
3. **Güvenlik önce** — Şüpheli durumlarda en kısıtlayıcı yaklaşım benimsenir.
4. **Dokümantasyon** — Yeni özellikler `doc/` altında belgelenir.
5. **Geri uyumluluk** — Mevcut API'leri bozan değişiklikler `CHANGELOG.md`'ye işlenir.

---

*Bu belge, projenin gelişimine paralel olarak güncellenecektir.*  
*Son güncelleme: Nisan 2026*
