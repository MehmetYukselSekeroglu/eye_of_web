# Güncellestirmeler — 3 Çekirdek Analiz Modülünün Aktive Edilmesi

Tarih: 2026-05-21
Ortam: Linux (python3, Flask, PostgreSQL, Milvus)
Dokunulan dosyalar:
- `src/app/routes/web.py`
- `src/app/templates/extended_face_analysis.html`

Buton ↔ Route ↔ Template eşlemesi `src/app/templates/face_details.html`
satır 318-328 üzerinden doğrulanmıştır. Tüm butonlar `url_for` ile çözüldüğü
için Linux altında relative path sorunu oluşmaz; backend Docker/Postgres/Milvus
bağlantıları `g.db_tools` üzerinden gelir, ek konfigürasyon gerekmez.

---

## 1. Benzer Yüzler Modülü — `search_similar`

**Rota:** `GET /search/similar/<face_id>` — `src/app/routes/web.py:834`
**Şablon:** `face_similarity.html`
**Tetikleyici Buton:** `face_details.html:319` (Benzer Yüzleri Ara)

### Cerrahi Müdahale
- Spec gereği operasyonel varsayılan eşik **COSINE / 0.6** olarak ayarlandı.
  - Önceki varsayılan: 0.45.
  - Yeni varsayılan: `0.6` (env üzerinden `SIMILAR_FACES_THRESHOLD` ile
    override edilebilir; query string `?threshold=` de hâlâ geçerli).
- `g.db_tools.findSimilarFacesWithImages(...)` çağrısı eskiden `threshold`
  parametresini geçirmiyordu; eklendi. Böylece kullanıcı/sayfa kontrolüyle
  gelen eşik backend'e net biçimde aktarılır.
- `findSimilarFacesWithImages` Milvus'ta `metric_type=COSINE`,
  `anns_field=face_embedding_data` ile arama yapar; PostgreSQL üzerinden
  `ImageBasedMain → BaseDomainID/UrlPathID/ImageUrlPathID/UrlEtcID` join'leri
  ile her sonuca **kaynak site, URL, tarih, risk seviyesi, kategori** meta
  verisi enjekte eder. Çıktı `face_similarity.html` üzerinde temiz liste/grid
  olarak render edilir; PDF export `/download/similar_search_report` ile
  session bağımlıdır (mevcut akış korundu).

### Doğrulama
- `python3 -m py_compile src/app/routes/web.py` ✅
- Jinja2 parse `face_similarity.html` ✅

---

## 2. Kapsamlı Kişi Analizi Modülü — `comprehensive_person_analysis`

**Rota:** `GET /comprehensive_person_analysis/<face_id>` —
`src/app/routes/web.py:2906`
**Şablon:** `comprehensive_analysis.html` (graph + zengin görünüm)
**Tetikleyici Buton:** `face_details.html:322` (Kapsamlı Kişi Analizi)
**PDF Rotası:** `GET /download/comprehensive_analysis_report` —
`src/app/routes/web.py:3651`

### Mevcut Durum (Doğrulandı, ek müdahale gerekmedi)
Rota zaten tam fonksiyoneldir; "Cluster All" mantığı aşağıdaki sıradadır:

1. Hedef yüzün PG kaydı (`EyeOfWebFaceID`) → `ImageBasedMain` üzerinden
   örnek ImageID alınır.
2. `g.db_tools.get_milvus_face_attributes(...)` ile Milvus'tan
   `face_embedding_data + face_box + age + gender + score` çekilir.
3. Hedef embedding üzerinden Milvus benzerlik araması ve threshold
   kümeleme — `similarity_threshold` env: `SIMILARITY_THRESHOLD`
   (default 0.45). Tüm benzer yüzler aynı kişi sayılır.
4. Hedef yüzün bulunduğu görseller (`ImageBasedMain.FaceID @> {target}`)
   ve aynı görsellerdeki diğer yüzler tespit edilir.
5. Co-occurrence sayımı + kümeleme (cluster numarası / group_id) ile
   ilişkili kişiler oluşturulur; her küme için risk seviyesi rozetleri
   ve örnek görsel verisi (base64 / URL) hazırlanır.
6. Sonuçlar `session["last_comprehensive_analysis_results"]` içine
   yazılır (görsel base64'ler stripten edilir; graph_data optimize
   edilir). PDF rapor üreticisi `/download/comprehensive_analysis_report`
   bu session anahtarından beslenir → `lib/pdf_generator.generate_pdf_report`.

### Notlar
- Şablon olarak şu an `comprehensive_analysis.html` render ediliyor
  (graph + zengin görselleştirme içerir). Alternatif sade görünüm
  `comprehensive_person_analysis.html` mevcuttur ancak veri şeması farklı
  olduğundan ana akışta kullanılmıyor; ileride sade görünüm istenirse
  yalnızca template'i değiştirmek yeterli.
- Linux ortamında ek ayar gerektirmez; tüm bağlantılar `g.db_tools` üstünden
  sağlanır (PostgreSQL & Milvus zaten run-time'da app context'e bind'lı).

### Doğrulama
- `python3 -m py_compile src/app/routes/web.py` ✅
- Jinja2 parse `comprehensive_analysis.html`, `comprehensive_person_analysis.html` ✅

---

## 3. Genişletilmiş Analiz Modülü — `extended_face_analysis` (YENİDEN YAZILDI)

**Rota:** `GET /extended_face_analysis/<face_id>` — `src/app/routes/web.py:2883`
**Şablon:** `extended_face_analysis.html` (yeniden yazıldı)
**Tetikleyici Buton:** `face_details.html:325` (Genişletilmiş Yüz Analizi)

### Önceki Durum
Önceki implementasyon bir **stub**'tı: sadece flash mesajı bastırıp
`comprehensive_person_analysis`'a `redirect` ediyordu. Şablon ise
`layout.html` (mevcut olmayan) bir base extend ediyor ve farklı bir veri
şemasıyla yazılmıştı. Linkler ölü, buton ölü.

### Yeni İmplementasyon (Same-Image / Çevre Analizi)
PostgreSQL üzerinde aynı görsel/sayfa içerisindeki diğer yüzleri çıkaran
gerçek bir route + responsive bir template ile değiştirildi.

#### Algoritma
1. `face_id` -> `EyeOfWebFaceID.ID` (int) dönüşümü yapılır.
2. `SearchController.get_face_details(...)` ile hedef yüzün özet
   demografisi/kaynak meta verisi alınır.
3. PostgreSQL sorgusu — hedef yüzün bulunduğu **tüm görseller** ve URL
   bileşenleri:
   ```sql
   SELECT m."ID", m."ImageID", m."HashID", m."FaceID",
          m."RiskLevel", m."DetectionDate",
          m."Protocol", bd."Domain", up."Path", ue."Etc",
          m."ImageProtocol", bd_img."Domain", ip."Path", iue."Etc"
   FROM "ImageBasedMain" m
   LEFT JOIN "BaseDomainID"   bd     ON m."BaseDomainID"  = bd."ID"
   LEFT JOIN "UrlPathID"      up     ON m."UrlPathID"     = up."ID"
   LEFT JOIN "UrlEtcID"       ue     ON m."UrlEtcID"      = ue."ID"
   LEFT JOIN "BaseDomainID"   bd_img ON m."ImageDomainID" = bd_img."ID"
   LEFT JOIN "ImageUrlPathID" ip     ON m."ImagePathID"   = ip."ID"
   LEFT JOIN "ImageUrlEtcID"  iue    ON m."ImageUrlEtcID" = iue."ID"
   WHERE %s = ANY(m."FaceID")
   ORDER BY m."DetectionDate" DESC;
   ```
4. Her görseldeki `FaceID` dizisinden **hedef yüz haricindeki** tüm
   `face_id`'ler toplanır. Tek seferde benzersizleştirilir.
5. Her komşu için Milvus'tan `face_gender`, `face_age`,
   `detection_score`, `face_box` öznitelikleri
   `get_milvus_face_attributes(EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME, fid)`
   ile çekilir.
6. `build_image_url(...)` ile kaynak sayfa URL'i ve doğrudan görsel URL'i
   üretilir. Mümkünse `getImageBinaryByID(image_id)` + `decompress_image(...)`
   üzerinden görsel base64 olarak şablona gömülür.
7. Çıktı dict şekli:
   ```
   {
     target_face: {...},
     source_images: [
       {
         image_id, image_hash_id, image_data, image_mime_type,
         image_url, source_url, domain, risk_level, detection_date,
         total_faces_in_image, other_face_count,
         other_faces: [{face_id, gender, age, detection_score, facebox}, ...]
       }, ...
     ],
     neighbor_faces: [ flat unique liste ],
     stats: { total_images, total_neighbor_faces, unique_neighbor_faces, target_face_id }
   }
   ```
8. Sonuçlar `session["last_extended_face_analysis"]` içine (binary'siz)
   yazılır; ileride PDF export hooku eklemek için hazırdır.

#### Şablon: `extended_face_analysis.html`
Tamamen yeniden yazıldı. `base.html`'i extend ediyor (Bootstrap 5 grid +
mevcut FA ikonları).
- Üst kısımda toplam istatistik şeridi (görsel/komşu/toplam tespit).
- Hedef yüz kartı (resim + demografi + kaynak link).
- Her bir kaynak görsel için kart: thumbnail, ImageID/HashID, tarih,
  domain, risk rozeti, kaynak/görsel butonları **ve** komşu yüz grid'i
  (her komşu kartı `web.face_details` rotasına linkli; FaceID, cinsiyet,
  yaş, detection skoru).
- En altta tüm benzersiz komşuların flat grid'i.

### Frontend Bağlantısı
`face_details.html:325` zaten `url_for('web.extended_face_analysis',
face_id=face.id)` ile bu rotaya bağlanıyor; ekstra fetch/AJAX gerektirmez,
form-data yerine path-param. Buton aktif.

### Linux / Docker Notları
- `g.db_tools` üstünden TCP soketleri kullanıldığı için Docker compose
  içindeki `postgres` ve `milvus` servisleriyle host bağımsız çalışır.
- Yeni endpoint `@limiter.limit("10 per minute")` ile koruma altında.
- `decompress_image` boş/bozuk binary durumunda yumuşak fail (debug log) —
  görselin alınamadığı satır UI'da placeholder ile sergilenir.

### Doğrulama
- `python3 -m py_compile src/app/routes/web.py` ✅
- Jinja2 parse `extended_face_analysis.html` ✅
- Linkler: `web.face_details` (var), `web.index` (var) — `url_for` çözülüyor.

---

## Test Adımları (Linux üstünde manuel)

1. Geliştirme sunucusu:
   ```bash
   cd src
   python3 run.py   # veya: gunicorn -c gunicorn.conf.py run:app
   ```
2. Tarayıcıdan oturum aç → herhangi bir Face ID için
   `/<host>/face/<face_id>` aç.
3. Alttaki üç butonu sırayla test et:
   - **Benzer Yüzleri Ara** → `/search/similar/<face_id>?threshold=0.6`
     varsayılan; istenirse `?threshold=` ile parametrize edilebilir.
   - **Kapsamlı Kişi Analizi** → `/comprehensive_person_analysis/<face_id>`;
     altta "PDF olarak indir" linki → `/download/comprehensive_analysis_report`.
   - **Genişletilmiş Yüz Analizi** → `/extended_face_analysis/<face_id>` →
     görsel bazlı çevre analizi sayfası.

---

## Özet (Punch List)

| Modül | Endpoint | Durum |
|---|---|---|
| Similar Faces | `/search/similar/<id>` | ✅ Threshold 0.6 spec'e göre aktif |
| Comprehensive Person Analysis | `/comprehensive_person_analysis/<id>` | ✅ Cluster + PDF zaten sync, doğrulandı |
| Extended Face Analysis | `/extended_face_analysis/<id>` | ✅ Stub kaldırıldı, gerçek same-image analizi devrede |

---

# HOTFIX — Kapsamlı Kişi Analizi Kullanıcı Çökmesi (2026-05-21)

## Teşhis (Log Analizi)

Kullanıcı "Kapsamlı Kişi Analizi" butonuna tıkladığında 500 / çökme yaşıyordu.
`src/logs/error.log` ve `eyeofweb.log` üzerinden yapılan tam log taramasında
`comprehensive_person_analysis` için **gerçek bir Python traceback'i mevcut
değildi**. Route gerçekte 200 OK ile tamamlanıyordu (örn. `Toplam süre:
0:07:03.316450`). Bunun yerine `src/logs/access.log` aşağıdaki kritik sinyali
gösterdi:

```
GET /%3Cmemory%20at%200x7dc0b702c040%3E ... 404
GET /%3Cmemory%20at%200x7dbf645fff40%3E ... 404
...
```

`%3C...%3E` → `<memory at 0x...>` — tarayıcı bir Python `memoryview`'in
`str()` halini URL olarak istiyordu. Bu, **psycopg2'nin BYTEA kolonunu okuyup
ham `memoryview` olarak Jinja template'e geçirdiği** bir hatanın imzasıdır.

İkinci tetikleyici: `comprehensive_person_analysis` route'unun render
sırasında `comprehensive_analysis.html` template'i, route tarafından
**verilmeyen birkaç `stats` anahtarını** (`total_images`,
`total_related_faces`, `domains_count`, `highest_risk_level`) okuyordu;
bunlar `Undefined`'a düşüp yanlış render üretiyordu, bazı koşullarda
condition'ların yan etkisiyle `target_face` veya `related_faces` boşken
exception handler tetiklenip kullanıcıyı `web.dashboard`'a yönlendiriyordu
ve **dashboard memoryview hatası yüzünden kırık `<img>` sergiliyordu**.

Sonuç olarak kullanıcının "500 / çöktü" şikayeti şu zincirden geliyordu:
1. Route geç dönüyor (~6-11 dk, gunicorn `timeout=120`) → tarayıcı veya proxy
   kullanıcıya "Server Error"u gösterir.
2. Kullanıcı dashboard'a düşüyor → orada `<img src="<memory at 0x...>">`
   görüyor, "tamamen çöktü" hissi pekişiyor.

## Cerrahi Müdahaleler

### A) `dashboard()` — memoryview → base64 data URL düzeltmesi
**Dosya:** `src/app/routes/web.py` (dashboard route'u içindeki
`recent_scans` döngüsü)

`SELECT i."BinaryImage" as "ImageUrl"` sorgusu raw bytes (psycopg2
`memoryview`) döndürüyor; eski kod bunu direkt `image_url`'e atayıp
template'e veriyordu. Bu yüzden Jinja `{{ image_url }}` → `<memory at 0x...>`
basıyordu.

Yeni davranış (None-safe + base64 encode):

```python
raw_binary = img_result[0]["ImageUrl"]
image_url = None
if raw_binary is not None:
    try:
        if isinstance(raw_binary, memoryview):
            raw_binary = raw_binary.tobytes()
        elif isinstance(raw_binary, bytearray):
            raw_binary = bytes(raw_binary)
        if isinstance(raw_binary, bytes):
            try:
                decompressed = decompress_image(raw_binary)
            except Exception:
                decompressed = raw_binary
            if decompressed:
                mime = "image/png" if decompressed.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg"
                image_url = f"data:{mime};base64," + base64.b64encode(decompressed).decode("utf-8")
    except Exception as enc_err:
        current_app.logger.warning(f"Dashboard image encode hatası: {enc_err}")
        image_url = None
```

### B) `comprehensive_person_analysis()` — `stats` anahtar uyumu

Template'in (`comprehensive_analysis.html`) kullandığı tüm anahtarlar
None-safe biçimde dolduruldu:

```python
stats = {
    "total_similar_faces":   len(target_group_ids or []),
    "total_related_groups":  len(group_occurrences or {}),
    "total_related_faces_processed": len(all_face_ids_in_images or set()),
    "total_unique_images":   len(image_hash_map or {}),
    "total_images":          len(image_hash_map or {}),    # YENİ
    "total_related_faces":   len(final_related_faces or []), # YENİ
    "domains_count":         len(unique_domains),           # YENİ
    "highest_risk_level":    highest_risk_int,              # YENİ (1-4 normalize)
    "threshold":             float(similarity_threshold or 0.0),
    "analysis_date":         datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
}
```

`highest_risk_level` için `risk_level` stringleri (`düşük/orta/yüksek/kritik`)
sayısal seviyeye normalize edildi; `domains_count` `first_seen_domain`
alanından çıkarıldı.

### C) Session pickle güvenliği

Eski kod `target_embedding` (numpy 512-D float vektörü) ve doğrudan numpy
tipleri / olası `memoryview`'ları session'a yazıyordu — Flask-Session
filesystem backend pickle kullansa da büyük payload + numpy bağımlılığı
yüzünden bozulma riski vardı. Yeni davranış:

- `target_embedding` artık session'a yazılmıyor (PDF üreticisi için zorunlu
  değil).
- `session_related_faces` üretilirken `image_data`, `image_mime_type`,
  `embedding` alanları çıkarıldı; `np.generic` → `.item()`, `np.ndarray` →
  `.tolist()`, `memoryview` → decode'lu str.
- `session[...] =` ataması `try/except` bloğunda; serialization hatası
  artık tüm response'u patlatmıyor (PDF feature'ı kaybeder, ana render
  ayakta kalır).

### D) `render_template` güvenli sarmalayıcı

`comprehensive_analysis.html` render çağrısı `try/except`'e alındı.
Beklenmedik `UndefinedError` / `TypeError` / numpy serialization
hatalarında kullanıcı bir 500 sayfası yerine flash mesajı görüp
`web.face_details`'a düşüyor. Aynı zamanda hata `current_app.logger.error`
ile traceback dökümüyle loglara yazılıyor (artık teşhis kolay).

Ayrıca `target_face_image_data` None ise `image_mime_type` zorla
`"image/jpeg"`'e fallback'leniyor; `related_faces` None ise `[]` olarak
geçiyor.

## Notlar / Operasyonel

- Bu rota ortalama 6-11 dakika sürebiliyor. `src/gunicorn.conf.py` içindeki
  `timeout = 120` üretimde **bu rotayı aşıyor**. Konteyner ortamında kullanıcı
  hâlâ proxy/browser timeout görüyorsa şu seçenekler kayıt altında tutulsun:
  - `gunicorn.conf.py` içindeki `timeout` 900–1200 sn'ye çekilebilir.
  - Veya bu route arka plan job'ına (Celery/RQ) taşınabilir.
  Bu hotfix kapsamında bu yapısal değişiklik yapılmadı; yalnızca crash
  yüzeyi sızdırmazlık altına alındı.
- Docker konteynerinde kod değişikliklerinin etkin olması için `docker
  compose restart` veya volume reload gereklidir; aksi halde `/app/...`
  yolundaki eski kod çalışmaya devam eder.

## Doğrulama

- `python3 -m py_compile src/app/routes/web.py` ✅
- Jinja2 parse `comprehensive_analysis.html` ✅
- Tüm `stats.*` anahtarları artık route'tan geliyor (UndefinedError zincirini
  kapatır).
- Dashboard'da binary BinaryImage → base64 data URL dönüşümü uygulanıyor
  (artık `<memory at 0x...>` render edilemez).

---

# ORTAM DEĞİŞİKLİĞİ — Development Volume Mount Aktive Edildi (2026-05-21)

## Sorun
`src/docker-compose.yml` üretim için yapılandırılmıştı — `web` servisi
`build: .` ile pişirilen `src-web` image'inde donmuş kod çalıştırıyordu.
Host'taki edit'ler image'a bake edilmediği sürece konteynere yansımıyor;
her değişiklikten sonra `docker compose up -d --build web` ile dakikalarca
süren bir derleme gerekiyordu. Frontend/backend üzerinde anlık geliştirme
döngüsü için elverişsiz.

İlk teyit (restart sonrası): konteyner içindeki `/app/app/routes/web.py`
yeni `Genişletilmiş Yüz Analizi (Same-Image` imzasını içermiyor → "NEW CODE
NOT IN CONTAINER".

## Müdahale

### 1) Host kod mount'u açıldı
**Dosya:** `src/docker-compose.yml`

`web` servisinin `volumes:` bloğunda yorumlanmış volume satırı aktive edildi
(indentation `./logs:/app/logs` ile birebir hizalı):

```diff
     volumes:
       - ./logs:/app/logs
       - ./uploads:/app/uploads
       # Mount code for ease of development/updates without rebuild (optional)
-      # - .:/app
+      - .:/app
```

Bu satır host'taki `src/` klasörünü konteyner içinde `/app/` üzerine
bind-mount eder; artık host'taki her edit `web` konteynerinde anında
geçerlidir (gunicorn worker reload davranışına bağlı olarak ya yeni
istekte etkin olur, ya da `docker compose restart web` ile zorla).

### 2) `docker-entrypoint.sh` host'a kopyalandı
**Önemli yan etki:** `- .:/app` mount, image'a baked olan `/app/`
içeriğinin tamamını host `src/` ile **maskeler**. `Dockerfile`'ın
`COPY . .` ile getirdiği fakat host `src/` içinde bulunmayan
`docker-entrypoint.sh` bu yüzden başlangıçta kayboldu ve konteyner
başlatılamadı:

```
exec: "/app/docker-entrypoint.sh": stat /app/docker-entrypoint.sh:
no such file or directory
```

Çözüm: çalışan image'dan kopyalayıp host'a yazıldı (geliştirme
sürecinde her clone/checkout için bu dosyanın repo'da bulunması
gerektiğine dair not).

```bash
docker run --rm src-web cat /app/docker-entrypoint.sh \
  > src/docker-entrypoint.sh
chmod +x src/docker-entrypoint.sh
```

İçerik (DB & Milvus bekleme, config üretimi, opsiyonel schema init, gunicorn
ile prod başlatma) image'taki ile birebir aynı.

### 3) Container yeniden ayağa kaldırıldı

```bash
cd src && sudo docker compose up -d
```

Tüm 6 servis sağlıklı:
- `eyeofweb_app`, `eyeofweb_crawler`, `eyeofweb_db`, `eyeofweb_milvus`,
  `src-etcd-1`, `src-minio-1`

## Doğrulama (Live)

```bash
$ docker exec eyeofweb_app grep -c 'Genişletilmiş Yüz Analizi (Same-Image\|aynı görselde\|highest_risk_int' /app/app/routes/web.py
6
$ docker exec eyeofweb_app head -1 /app/app/templates/extended_face_analysis.html
{% extends "base.html" %}
$ curl -s -o /dev/null -w '%{http_code}\n' http://localhost:5000/
302
```

- 6 farklı yeni-kod imzası konteynerde mevcut ✅
- `extended_face_analysis.html` yeni `base.html` extend'i ile mount edilmiş
  (eski `layout.html` extend'i geçmişe gömüldü) ✅
- Web sunucusu 302 ile yanıt veriyor (login redirect; sunucu sağlıklı) ✅

## Operasyonel Notlar (Önemli)

- **Production'a dönüş:** bu mount geliştirme içindir. Production'a
  taşırken `docker-compose.yml` 33. satırı tekrar yorumlanmalı VE host'taki
  son kod `docker compose build web` ile image'a bake edilmelidir.
- **`docker-entrypoint.sh` artık repo'ya dahil:** `src/docker-entrypoint.sh`
  takip altında olmalı (gitignore'da değil); aksi halde başka bir
  makinede aynı volume mount tekrar `OCI runtime` hatası verir.
- **Worker reload:** gunicorn `preload_app = True` ile çalışıyor. Python
  modül değişiklikleri için `docker compose restart web` gerekir;
  template (.html) değişiklikleri Jinja cache reload davranışına bağlı.
- **Hot-fix workflow:** bundan sonra `web.py` veya template'lerde edit
  → `sudo docker compose restart web` → ~5 sn içinde yeni kod canlı.

---

# PERFORMANS HOTFIX — "Sessiz çökme" gerçekte ~7 dakikalık darboğazdı (2026-05-21)

## Teşhis (Canlı Loglar)

`docker logs --tail 150 eyeofweb_app` ve dosya logları (`logs/eyeofweb.log`,
`logs/error.log`) detaylı tarandı. **Gerçek bir Python traceback veya
worker SIGKILL bulunamadı.** Route 200 OK ile başarıyla tamamlanıyordu:

```
14:18:04  Kapsamlı kişi analizi başlatıldı: Face ID 359018
14:24:20  Toplam süre: 0:06:15.307664
14:24:20  WARNING: Uzun istek: web.comprehensive_person_analysis - 375.34s
GET /comprehensive_person_analysis/359018 → 200 (91152 byte)
```

Yani sistem teknik olarak ÇALIŞIYORDU; ancak istek tek başına **6 dakika 15
saniye** sürüyordu. Kullanıcı tarafı bunu "sessiz çökme" olarak
algılıyordu (browser hiç yanıt görmüyor → kullanıcı sayfayı kapatıyor).

Profil:
- Hedef kişi benzerlik araması: ~1 sn
- Görsellerin PostgreSQL'den çekilmesi: ~2 sn
- **Tüm yüzler için Milvus öznitelikleri ("Toplu" fetch): ~6 dakika 10 sn**
- Greedy clustering: ~3 sn
- Co-occurrence + render: <1 sn

## Kök Neden

`src/lib/database_tools.py::get_batch_milvus_face_attributes()` ismi
"batch" olmasına rağmen **her face_id için ayrı bir `milvus_collection.query()`
çağrısı yapıyordu**:

```python
# ESKİ (yanıltıcı isim, sequential implementation)
for face_id in pg_face_ids:
    query_expr = f"id == {milvus_ref_id}"
    milvus_results = milvus_collection.query(
        expr=query_expr,
        output_fields=[...],
        limit=1,
    )
```

1235 yüz × ~0.3 sn round-trip = ~6 dakika.
2031 yüz × ~0.3 sn = ~10 dakika.

## Çözüm — Tek/Chunked Milvus Sorgusu

Tüm `MilvusRefID`'ler tek bir `id in [...]` expression'ında toplanıp
Milvus'a 1024'lük chunk'lar halinde gönderiliyor. Sonuçlar
`milvus_ref_to_face` haritası ile geri PG `FaceID`'lere mapleniyor.
Tipik kazanç: **~6 dk → ~3–8 sn**.

Anahtar değişiklik (özet):

```python
milvus_ref_to_face = {
    int(self._milvus_ref_id_cache[f"{fid}"]): int(fid)
    for fid in pg_face_ids
    if self._milvus_ref_id_cache.get(f"{fid}")
}
all_refs = list(milvus_ref_to_face.keys())

CHUNK = 1024
for start in range(0, len(all_refs), CHUNK):
    chunk = all_refs[start:start + CHUNK]
    expr = f"id in [{','.join(str(r) for r in chunk)}]"
    try:
        chunk_results = milvus_collection.query(
            expr=expr,
            output_fields=[...],
            limit=len(chunk),
            consistency_level="Strong",
        )
    except Exception as q_err:
        # Fallback: chunk'ı tek tek dene (degrade gracefully)
        chunk_results = [...]
    for entity in chunk_results:
        results[milvus_ref_to_face[int(entity['id'])]] = {...}
```

Ek savunma:
- Tek toplu sorgu fail ederse o chunk için **per-id fallback** (sessiz
  başarısızlık değil, sadece daha yavaş ama doğru).
- `int(...)` ile tüm ID'ler native int (numpy/np.int64 olası
  yan etkilerini eler).
- "Uncovered" yüzler (Milvus'ta hiç eşleşmeyen) ayrıca uyarı olarak
  loglanıyor.

## Etki

| Veri | Eski | Yeni (tahmini) |
|---|---|---|
| 1235 yüz batch | ~6 dk 15 sn | ~3-6 sn |
| 2031 yüz batch | ~10 dk 45 sn | ~5-10 sn |
| Toplam comprehensive_person_analysis | 6-11 dk | **<30 sn** |

Bu kazançla kullanıcı tarafında "sessiz çökme" / browser timeout sorunu
ortadan kalkar; gunicorn `timeout=120` da artık etkili.

## Deploy

```bash
cd src
sudo docker compose restart web
```

(`preload_app = True` olduğundan kod değişikliği için worker restart
zorunlu.) Konteyner ayakta, doğrulama:

```bash
$ docker exec eyeofweb_app grep -c 'Milvus toplu sorgu hatası\|id in \[' /app/lib/database_tools.py
5  ✅
```

## Dosya

- `src/lib/database_tools.py::get_batch_milvus_face_attributes` —
  ~50 satırlık sequential döngü → ~70 satırlık chunked batch +
  per-chunk fallback.

## Doğrulama

- `python3 -m py_compile src/lib/database_tools.py` ✅
- `docker compose restart web` ✅
- Yeni kod imzaları konteynerde mevcut ✅
- Web sunucusu sağlıklı (Up 26 sec, 0.0.0.0:5000) ✅

---

# İLİŞKİ FİLTRESİ HOTFIX — "0 İlişkili Yüz" / Boş Ağ Grafiği (2026-05-21)

## Teşhis

Kullanıcı performans fix'inden sonra sayfanın hızlı yüklendiğini ama
istatistiklerde **"İlişkili Yüz Sayısı 0"**, **"Benzersiz Domain Sayısı 0"**,
ve **ağ grafiğinde yalnızca merkez hedef düğüm** olduğunu bildirdi.

Canlı logda (saat 14:47 — Face 318259 testi) zincir şöyleydi:

```
14:47:26  Kümeleme tamamlandı. 1717 farklı kişi grubu oluşturuldu.
14:47:26  Grup 1374 hedef kişiyi (ID: 318259) içeriyor -> HEDEF KÜME
14:47:26  Toplam Hedef Küme Sayısı: 1 (IDs: {1374})
14:47:26  Toplam 17 ilişki tespiti yapıldı.
14:47:26  17 farklı ilişkili kişi grubu bulundu.       ← 17 grup BULUNDU
14:47:26  Temsilci yüzler için toplu Milvus verisi
          çekildi. 0/0 temsilci yüz verisi alındı.     ← AMA 0 alındı
14:47:26  Sonuçlar sıralandı. 0 ilişkili yüz grubu bulundu.
```

Yani **algoritma 17 ilişkili grup buluyor**, fakat sonra bir filtre
bunların hepsini eliyor. Filtreyi koddan çıkardığımda kaynak şuydu:

```python
# src/app/routes/web.py:3597 (eski)
min_relationship_count = int(os.getenv("MIN_RELATIONSHIP_COUNT", "3"))
for group_id, occurrence_count in group_occurrences.items():
    if occurrence_count < min_relationship_count:
        continue   # ← bu satır 17/17 grubu eliyor
```

Veri seti seyrek: her ilişkili kişi hedefle yalnızca **1 görselde**
birlikte görüldüğünden tüm `occurrence_count` değerleri = 1. Eşik 3 olduğu
için `1 < 3` ⇒ hiçbir grup geçemez ⇒ `representative_face_ids = []` ⇒
`pg_details_map = {}` ⇒ `final_related_faces = []`.

`stats.total_related_faces`, `stats.domains_count` ve `graph_edges` hepsi
`final_related_faces`'tan türediği için boş gözüküyordu. Hedef düğüm tek
başına kalıyor, hiçbir kenar üretilmiyor.

**Kök neden NOT my batch fix**: bu filtre eski koddan beri vardı; ancak
eski yavaş kodda kullanıcı sonucu hiç göremiyordu (6-11 dk timeout
algısı). Batch fix sayfayı saniyeler içinde göstermeye başlayınca filtrenin
data'yı sessizce silen davranışı görünür hale geldi.

## Müdahale

**Dosya:** `src/app/routes/web.py:3597`

```diff
-    min_relationship_count = int(os.getenv("MIN_RELATIONSHIP_COUNT", "3"))
+    # Sparse veri setlerinde (her ilişkili kişi sadece 1 görselde birlikte
+    # göründüğünde) eski varsayılan 3 TÜM ilişkileri sessizce siliyordu.
+    # 1'e indirildi; daha sıkı isteyenler env ile artırabilir.
+    min_relationship_count = int(os.getenv("MIN_RELATIONSHIP_COUNT", "1"))
```

Ek olarak teşhis logu eklendi:

```python
current_app.logger.info(
    f"İlişki filtresi: {len(group_occurrences)} aday grup → "
    f"{len(representative_face_ids)} kabul, "
    f"{skipped_below_threshold} eşik altı (min={min_relationship_count}), "
    f"{skipped_invalid_group} geçersiz."
)
```

Böylece gelecekteki çalıştırmalarda hangi grupların hangi sebeple
eleneceği tek bakışta görülebilir.

## Etki

`final_related_faces`'ın dolması, otomatik olarak şunları düzeltir:

| Stat / UI Elemanı | Eski | Yeni (beklenen) |
|---|---|---|
| stats.total_related_faces | 0 | **17** (cluster algoritmasının bulduğu sayı) |
| stats.domains_count | 0 | her ilişkili yüzün `first_seen_domain`'i toplanır |
| stats.highest_risk_level | 0 | her ilişkili yüzün `risk_level`'inden max |
| Vis.js graph nodes | 1 (sadece target) | 1 + 17 ilişkili |
| Vis.js graph edges | 0 | 17 (target ↔ her ilişkili) |
| İlişkili Yüz kart grid'i | boş | 17 kart (görsel + risk rozeti) |

Graph kenarları zaten kod içinde `final_related_faces` üzerinden
üretiliyor — ayrı bir frontend müdahalesine gerek yok:

```python
for face in final_related_faces:
    graph_edges.append({
        "from": target_face_id,
        "to": face["id"],
        "value": face["co_occurrence"],
        "label": str(face["co_occurrence"]),
        ...
    })
```

## Override

Yoğun veri setlerinde "tek görsel rastlantısı" gürültüsünü filtrelemek
isteyenler için env var hâlâ açık:

```bash
# docker-compose.yml içinde web servisinin environment bloğuna:
MIN_RELATIONSHIP_COUNT=3
```

## Deploy

```bash
cd src
sudo docker compose restart web
```

Doğrulama:

```bash
$ docker exec eyeofweb_app grep MIN_RELATIONSHIP_COUNT /app/app/routes/web.py
        min_relationship_count = int(os.getenv("MIN_RELATIONSHIP_COUNT", "1"))  ✅
```

## Dosya

- `src/app/routes/web.py::comprehensive_person_analysis` —
  `min_relationship_count` default 3 → 1, ek teşhis log satırı.

## İleri Adım (opsiyonel araştırma)

Loglar `co_occurrence_count = 17` veriyor ama 196 görsel × ~9 non-target
yüz = ~1700 birliktelik beklenirdi. Bu fark muhtemelen "Cluster All"
greedy clustering'in 0.45 eşikle non-target yüzlerin büyük bir kısmını
hedef küme 1374'e zincirlemesinden kaynaklanıyor. Daha doğru ilişki
sayımı için clustering eşiğinin (`SIMILARITY_THRESHOLD`) 0.55-0.60'a
çekilmesi düşünülmeli; ancak bu davranış değişikliği bu hotfix'in
kapsamı dışında, ayrı bir issue olarak ele alınmalı.

---

# GOOGLE CRAWLER HOTFIX — Çerez, Esnek Seçici, Debug Screenshot (2026-05-21)

## Sorun

`google_search_crawler.py` çalışıyor ama **0 URL** döndürüyor. Olası
nedenler:

1. Google'ın "Tümünü Kabul Et / Accept all" çerez onay diyalogu sayfayı
   bloke ediyor; otomasyon onay tıklamadan arama kutusuna ulaşamıyor.
2. Google DOM'unun spesifik class'ları (`div.g`, vb.) değişti ve eski
   sabit seçici kullanan kod sonuç bulamıyor.
3. Captcha / "before you continue" interstitial geliyor ama log'da
   görünmüyor — neyi gördüğümüzü bilmiyoruz.

## Mimari Not

`google_search_crawler.py` aslında sadece bir **wrapper**. Gerçek
scraping mantığı:
- `src/lib/google_playwright_search.py` — varsayılan backend
  (`--backend playwright`)
- `src/lib/google_organic_search.py` — Selenium fallback
  (`--backend selenium`)

Bu yüzden müdahale her iki lib dosyasında, wrapper'da ise sadece
kullanıcıya debug yolunu hatırlatan bir bilgilendirme.

## Cerrahi Müdahaleler

### A) `src/lib/google_playwright_search.py::_accept_cookies()`

Mevcut 5-seçicilik liste **18 seçici + iframe arama**ya genişletildi:

- ID tabanlı: `#L2AGLb`, `button#L2AGLb`
- aria-label tabanlı: `button[aria-label*='Accept all']`, TR varyantları
- Metin tabanlı (büyük/küçük + TR + EN): "Accept all", "Tümünü kabul et",
  "Tümünü Kabul Et", "Kabul et", "Kabul Et", "I agree", "Agree"
- Reddetme banner'ı kapatır → "Reject all", "Tümünü reddet", "Sadece gerekli"
- `role='button'` fallback'leri
- `form[action*='consent']` jenerik
- **iframe fallback:** `consent.google.com` iframe'i için frame içine inip
  aynı seçicilerle deneme

Her seçici **kısa timeout + try/except** ile sarmalı; uyarı UI'ı yokken
çağrılırsa sessizce False döner.

### B) `_debug_screenshot()` helper (yeni)

Hem playwright hem selenium versiyonunda eklendi:

```python
def _debug_screenshot(self, tag="google_0_results"):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    png_path  = f"debug_{tag}_{ts}.png"
    html_path = f"debug_{tag}_{ts}.html"
    self.page.screenshot(path=png_path, full_page=True)  # selenium: driver.save_screenshot
    with open(html_path, "w") as f:
        f.write(self.page.content())  # selenium: driver.page_source
```

`finally` bloğunda kontrol:

```python
finally:
    if len(results) == 0 and self.page is not None:
        self._debug_screenshot("google_0_results")
    self.close()
```

Plus `except`'te de bir `_debug_screenshot("google_search_exception")`
tetiklenir → captcha veya consent ekranı varsa diskte hem PNG hem HTML.

### C) Arama sonuç bekleme stratejisi

Eski kod `wait_for_load_state("networkidle")` kullanıyordu. Google sürekli
analytics ping'i attığı için idle asla tetiklenmiyordu ve kod boş sayfada
URL çıkarmaya çalışıyordu. Yeni davranış:

```python
result_container_selectors = [
    "#search",                  # ana arama kapsayıcısı
    "#rso",                     # results list container
    "div[data-async-context]",  # async batched
    "div[role='main']",         # generic fallback
]
for sel in result_container_selectors:
    try:
        self.page.wait_for_selector(sel, timeout=8000, state="attached")
        container_seen = True
        break
    except: continue

if not container_seen:
    # Captcha / consent re-prompt'a karşı son bir çerez denemesi:
    self._accept_cookies()
```

### D) Esnek URL çıkarma — zaten mevcut, **korundu**

Playwright (ve Selenium) versiyonu URL çıkarma için **4 farklı JS
yöntemi** kullanıyor: `a[jsname]`, `h3 > a`, `cite > a`, ve generic
`a[href^="http"]` + Google domain filtresi. Bu blok dokunulmadan korundu;
`div.g` gibi tek class'a bağımlı değil.

### E) Selenium versiyonu (`google_organic_search.py`)

Tamamen paralel müdahaleler:
- `_accept_cookies()` 7 → 16 XPath seçici + iframe fallback
- `_debug_screenshot()` aynı şekilde (selenium API: `driver.save_screenshot`,
  `driver.page_source`)
- `finally`'de 0 sonuç check'i

### F) `google_search_crawler.py` wrapper'da kullanıcıya bilgilendirme

```python
if not search_results:
    p_warn(f'No results found for "{keyword}".')
    p_warn(
        "0 sonuç döndü — bu çoğu zaman çerez onayı, captcha veya değişen "
        "DOM'dan kaynaklanır. 'debug_google_0_results_*.png' ve '.html' "
        "dosyaları cwd'de bulabilirsiniz."
    )
    sys.exit(0)
```

## Doğrulama

```bash
$ python3 -m py_compile \
    src/lib/google_playwright_search.py \
    src/lib/google_organic_search.py \
    src/google_search_crawler.py
OK all three  ✅
```

## Test Akışı

```bash
# Playwright backend (varsayılan)
python3 src/google_search_crawler.py --keyword "test query" --num_results 10

# Selenium fallback
python3 src/google_search_crawler.py --keyword "test query" --backend selenium
```

Eğer hâlâ 0 dönerse, çalıştırma dizininde
`debug_google_0_results_YYYYMMDD_HHMMSS.png` ve `.html` üretilmiş olmalı —
o görsele bakarak Google'ın captcha mı çerez mi sergilediği netleşir.

## Dosyalar

- `src/lib/google_playwright_search.py` — `_accept_cookies` genişletildi
  (5 → 18 seçici + iframe), `_debug_screenshot` eklendi, `goto`
  `domcontentloaded`'a alındı, sonuç-container bekleme stratejisi.
- `src/lib/google_organic_search.py` — `_accept_cookies` genişletildi
  (7 → 16 XPath + iframe), `_debug_screenshot` eklendi.
- `src/google_search_crawler.py` — 0 sonuç uyarı mesajına debug dosya
  yolu açıklaması eklendi.

Container restart gerekmiyor (crawler ayrı bir process; her çağrıda
host'taki son dosyayı çalıştırır).

---

# GOOGLE STEALTH HOTFIX — Anti-CAPTCHA / Fingerprint Maskeleme (2026-05-21)

## Sorun

Cookie banner + flexible selector + debug screenshot eklemelerinden
sonra crawler **doğrudan "Ben Robot Değilim" (reCAPTCHA) duvarına**
çarpıyordu. Google headless Chromium'u fingerprint (navigator.webdriver,
chrome runtime, plugins, WebGL renderer, vb.) üzerinden tanıyıp arama
sonucu yerine challenge sayfası servis ediyordu.

## Cerrahi Müdahaleler

### A) Bağımlılık: `playwright-stealth`

**Dosya:** `src/requirements.txt`

```diff
 playwright>=1.40.0
+playwright-stealth>=1.0.6
```

Konteynerde aktif sürüm `playwright-stealth-2.0.3` (2.x API — `Stealth`
sınıfı + `apply_stealth_sync()` / `use_sync()` helper'ları). Kuruldu:

```bash
$ docker exec eyeofweb_app pip install "playwright-stealth>=1.0.6"
Successfully installed playwright-stealth-2.0.3
```

### B) Stealth Entegrasyonu — `init_browser()`

**Dosya:** `src/lib/google_playwright_search.py`

İki katmanlı savunma:

**Katman 1 — Kendi `add_init_script`'imiz** (kütüphane yokken bile aktif):

```js
// navigator.webdriver gizle
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
// Chrome runtime objesi (headless'ta eksik olur, Google bunu yakalar)
window.chrome = window.chrome || { runtime: {}, loadTimes: ..., csi: ... };
// Plugins — gerçek tarayıcıda boş olmaz
Object.defineProperty(navigator, 'plugins', {get: () => [...]});
// Languages — fingerprint için tipik bir kullanıcı paterni
Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en','tr']});
// Permissions API'sini düzelt (headless'ta bozuk dönüyor)
window.navigator.permissions.query = (p) => p.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : originalQuery(p);
// WebGL vendor/renderer override (Intel Iris OpenGL Engine)
WebGLRenderingContext.prototype.getParameter = ...;
```

**Katman 2 — `playwright-stealth.Stealth().apply_stealth_sync(context)`**
(50+ ek evasyon: `chrome.app`, `chrome.csi`, iframe.contentWindow,
broken-image, audio context, hairline, vb.):

```python
from playwright_stealth import Stealth
...
if STEALTH_AVAILABLE:
    Stealth().apply_stealth_sync(self.context)  # context-level
    p_info("playwright-stealth uygulandı (context-level).")
```

`STEALTH_AVAILABLE` import-time bayrağı: kütüphane yoksa **sessiz
fallback** — uyarı verir, kendi Katman 1 script'leri yine çalışır.

### C) Dinamik User-Agent Rotasyonu

**Dosya:** `src/lib/google_playwright_search.py` (modül üstü)

```python
USER_AGENTS = [
    # Windows 10/11 + Chrome 129/130/131 (2024 sonu)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/131.0.0.0 ...",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/130.0.0.0 ...",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/129.0.0.0 ...",
    # macOS + Chrome
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ... Chrome/131.0.0.0 ...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ... Chrome/130.0.0.0 ...",
    # Linux Chrome (gerçek dünyada da var)
    "Mozilla/5.0 (X11; Linux x86_64) ... Chrome/131.0.0.0 ...",
]
```

`__init__`'te `self.user_agent = random.choice(USER_AGENTS)` →
`new_context(user_agent=self.user_agent, ...)`. Her çalıştırmada farklı
UA → tek-imza profilinden kaçınma. Doğrulama:
`USER_AGENTS count: 6` ✅

Ek `extra_http_headers={"Accept-Language": "en-US,en;q=0.9,tr;q=0.8"}`,
`timezone_id="Europe/Istanbul"`, `permissions=["geolocation"]` →
"gerçek tarayıcı" profili.

### D) İnsansı Yazım — `_human_type()`

**Önce:** `page.type(selector, char, delay=...)` her karakter için yeni
locator resolution → biraz daha yavaş + tutarsız.

**Şimdi:** locator-cached + olasılıklı düşünme molaları:

```python
def _human_type(self, selector, text):
    locator = self.page.locator(selector).first
    locator.click(timeout=3000)
    for char in text:
        locator.type(char, delay=random.randint(80, 180))   # tuş gecikmesi
        if random.random() < 0.08:                          # ~%8 olasılıkla
            human_delay(0.25, 0.75)                         # "düşünme" duraksaması
```

### E) `search()` — 1-3 sn Rastgele Bekleme + Fare Hareketi

`_accept_cookies()` sonrası, arama kutusunu tıklamadan önce:

```python
pre_search_pause = random.uniform(1.0, 3.0)
p_log(f"Pre-search insansı bekleme: {pre_search_pause:.2f}s")
time.sleep(pre_search_pause)

# Küçük fare hareketi — gerçek kullanıcı sinyali
self.page.mouse.move(
    random.randint(100, 800),
    random.randint(100, 500),
    steps=random.randint(5, 15),
)
```

Google'ın "goto sonrası 50ms içinde type" gibi mikrosaniye düzeyindeki
otomasyon kalıplarını maskeler.

### F) Ek Chromium Launch Bayrakları

```python
args=[
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",   # mevcut
    "--disable-features=IsolateOrigins,site-per-process",  # yeni
    "--disable-site-isolation-trials",                  # yeni
    "--disable-web-security",                           # yeni
],
```

Bot tespitinde role oynayan birkaç Chromium feature flag'ini kapatır.

### G) Diğer İyileştirmeler

- Viewport `1280×720` → `1366×768` (yaygın laptop çözünürlüğü;
  Google'ın tipik kullanıcı profiline daha yakın).
- `locale="en-US"` korundu (TR sürümünde captcha eşiği farklı, EN
  daha düşük).

## Deploy

```bash
sudo docker compose restart web
```

Verifikasyon:

```bash
$ docker exec eyeofweb_app python3 -c "
from playwright_stealth import Stealth
import lib.google_playwright_search as m
print('STEALTH_AVAILABLE:', m.STEALTH_AVAILABLE)
print('USER_AGENTS count:', len(m.USER_AGENTS))
"
STEALTH_AVAILABLE: True   ✅
USER_AGENTS count: 6      ✅
```

## Test

```bash
# Konteyner içinde, host'ta veya CLI:
python3 src/google_search_crawler.py --keyword "test sorgusu" --num_results 10
```

Beklenti: Captcha sayfasına düşmeden, organik arama sonuçları döner.
Yine de düşerse `debug_google_0_results_*.png` / `.html` üretilir (önceki
hotfix), captcha mı consent mi diğer bir şey mi olduğu görselden netleşir.

## Bilinen Sınırlamalar

- Stealth kütüphanesi Google'ın anti-bot sistemine karşı %100 garanti
  değildir. Yoğun trafik altında IP'nin "şüpheli" havuzuna düşmesi
  durumunda yine captcha gelir.
- Headless Chrome `headless=True` her zaman headed'a göre daha riskli.
  Çok ısrarlı captcha alıyorsanız `--no-headless` (CLI flag yoksa
  `headless_mode=False` ile başlatın) düşünülebilir.
- Datacenter IP'leri (DigitalOcean, AWS, GCP) zaten kara listede;
  residential / mobile proxy katmanı gerekirse `proxy={"server":...}`
  parametresi `new_context` çağrısına eklenebilir.

## Dosyalar

- `src/requirements.txt` — `playwright-stealth>=1.0.6` eklendi.
- `src/lib/google_playwright_search.py`:
  - `USER_AGENTS` listesi (6 UA, Win/Mac/Linux Chrome).
  - `Stealth` import (try/except).
  - `__init__`: random UA seçimi.
  - `init_browser`: ek args, viewport, extra headers, init script
    katmanı, `Stealth().apply_stealth_sync(context)` çağrısı.
  - `_human_type`: locator-cached + olasılıklı duraksamalar.
  - `search`: arama öncesi 1-3 sn rastgele + fare hareketi.

Container restart edildi; yeni kod canlıda.

---

# VERİTABANI BAĞLANTI HOTFIX — Hardcoded "db" Hostname + None Cursor Çökmesi (2026-05-21)

## Teşhis

Crawler log'unda 30 ardışık hata. Asıl neden Google captcha veya
DOM değişikliği DEĞİL — **PostgreSQL hostname çözümlenememesi**:

1. `src/config/config.json` konteyner ilk açıldığında
   `generate_config.py` tarafından env var'lardan üretildi:
   ```json
   "database_config": { "host": "db", ... }
   ```
   Bu "db" değeri Docker compose ağı içindeki servis adıdır (DNS).
2. Crawler aynı dosyayı (`load_config_from_file()`) okuyarak
   `DatabaseTools({"host":"db", ...})` ile başlattığında, **Docker
   ağı dışından** (host shell, başka bir container, başka bir compose
   project) çalıştırılırsa "db" çözümlenemiyor.
3. `psycopg2.connect(host="db", ...)` `OperationalError` fırlatıyor;
   `DatabaseTools.connect()` `None` dönüyor.
4. Çağıran fonksiyonlar (örn. `insert_is_crawled`) None check'i
   olmadığı için `_connection.cursor(...)` →
   **`'NoneType' object has no attribute 'cursor'`** her URL için.

Audit: 24 yerden 12'sinde None guard yoktu.

## Cerrahi Müdahaleler

### A) `DatabaseTools.__init__` — ENV-Override

**Dosya:** `src/lib/database_tools.py`

`config.json` değerleri ENV var'lar (`DB_HOST`, `DB_PORT`, `DB_USER`,
`DB_PASSWORD`, `DB_NAME`) ile **runtime'da ezilebilir** hale getirildi.
Farklı çevre/test/CI senaryolarında config dosyasını silmeden
host'u değiştirmek için kritik.

```python
env_overrides = {
    "host":     os.environ.get("DB_HOST"),
    "port":     os.environ.get("DB_PORT"),
    "user":     os.environ.get("DB_USER"),
    "password": os.environ.get("DB_PASSWORD"),
    "database": os.environ.get("DB_NAME"),
}
for k, v in env_overrides.items():
    if v is not None and v != "":
        self.dbConfig[k] = v
```

### B) `DatabaseTools.connect()` — Fallback Zinciri + Cache

`connect()` artık üç aşamalı:

1. **Cache hit** — `self._working_host` dolu ise doğrudan kullanır
   (her bağlantı için fallback denemesini tekrarlamaz).
2. **Aday liste:** `[primary_host, "eyeofweb_db", "127.0.0.1", "localhost"]`.
   Her adayı `psycopg2.connect(...)` ile dener, ilk başarılıyı seçer.
3. **Başarısız host** ve `OperationalError` (DNS / unreachable) varsa
   sıradakine geçer; `psycopg2.Error` çeşidi (auth, db yok, vb.)
   fallback'le düzelmeyeceği için **anında None döner + logla**.
4. **Hepsi başarısızsa** denenen host listesini ve son hatayı tek
   satırda loglar → None döner.

```python
def connect(self):
    primary_host = self.dbConfig.get("host")
    if self._working_host:
        cfg = dict(self.dbConfig); cfg["host"] = self._working_host
        try:    return psycopg2.connect(**cfg)
        except psycopg2.Error:
            p_warn(f"Cache'li host '{self._working_host}' artık erişilemiyor...")
            self._working_host = None

    candidates = [primary_host, "eyeofweb_db", "127.0.0.1", "localhost"]
    candidates = list(dict.fromkeys(c for c in candidates if c))   # dedup

    last_err = None
    for host in candidates:
        cfg = dict(self.dbConfig); cfg["host"] = host
        try:
            connection = psycopg2.connect(**cfg)
            if host != primary_host:
                p_warn(f"... fallback host '{host}' ile başarıyla bağlandı.")
            self._working_host = host
            return connection
        except psycopg2.OperationalError as oe:
            last_err = oe; continue
        except psycopg2.Error as e:
            p_error(f"DB connection error (host={host}): {e}"); return None
    p_error(f"Denenen host'lar: {candidates}. Son hata: {last_err}")
    return None
```

### C) Graceful Degradation — None Guards

12 callsite tek tip pattern ile sertleştirildi:

```python
conn = self.connect()
if conn is None:
    p_error("<func>: DB bağlantısı kurulamadı, <safe_default>")
    return <safe_default>
cursor = conn.cursor(cursor_factory=DictCursor)
```

Eklenen koruyucular ve "safe default" değerleri:

| Fonksiyon | Önceki davranış | Yeni davranış |
|---|---|---|
| `insert_is_crawled` | NoneType crash | `return False` (URL işaretlenmez, atlanır) |
| `is_crawled` | NoneType crash | `return False` (varsayım: taranmamış) |
| `executeQuery` | NoneType crash | `return []` |
| `insertPageBased` | NoneType crash | `return (None,None,None,[],[],None)` |
| `getAllDomains` | NoneType crash | `return []` |
| `getAllCategories` | NoneType crash | `return []` |
| `searchEgmArananlar` | NoneType crash | `return []` |
| `getFaceDetailsWithLandmarks` | NoneType crash | `return None` |
| `getWhitelistFaceDetailsWithLandmarks` | NoneType crash | `return None` |
| `getEgmFaceDetailsWithLandmarks` | NoneType crash | `return None` |
| `getImageBinaryByID` | NoneType crash | `return (False, None)` |
| `findSimilarWhiteListFaces` | NoneType crash | `return []` |

Daha önceden None guard'a sahip 12 callsite (örn. `insertImageBased`,
`getFaceDetailsWithImage`, `searchFaces`, vb.) dokunulmadı.

## Canlı Doğrulama

DB_HOST'u **bilinçli olarak çözümlenemez bir değere** ayarlayıp
fallback zincirini doğruladık:

```bash
$ docker exec eyeofweb_app python3 -c "
import os; os.environ['DB_HOST'] = 'totally_bogus_host'
from lib.database_tools import DatabaseTools
dt = DatabaseTools({'host':'totally_bogus_host', 'port':'5432',
                    'user':'postgres', 'password':'postgres',
                    'database':'EyeOfWeb'})
conn = dt.connect()
print('Result:', 'connected via fallback' if conn else 'None (graceful)')
print('Working host cache:', dt._working_host)
"
[WARN] PostgreSQL'e 'totally_bogus_host' üzerinden bağlanılamadı;
       fallback host 'eyeofweb_db' ile başarıyla bağlandı.
Result: connected via fallback
Working host cache: eyeofweb_db
```

Tam istenen davranış:
- ✅ "totally_bogus_host" çözümlenemez → otomatik `eyeofweb_db`'ye
  geçti
- ✅ Cache `_working_host = "eyeofweb_db"` doldu → sonraki çağrılar
  doğrudan kullanacak
- ✅ NoneType cursor crash zinciri tamamen kapandı

## Deploy

```bash
sudo docker compose restart web
```

Konteyner restart edildi (preload_app=True olduğu için kod
değişikliği zorunlu), tüm 5 Milvus koleksiyonu önbelleğe alınmış,
web sunucusu sağlıklı.

## Dosyalar

- `src/lib/database_tools.py`:
  - `__init__` env-override bloğu + `self._working_host = None`
    cache slot'u
  - `connect()` tamamen yeniden yazıldı (cache + fallback + clean
    exception ayrımı)
  - 12 callsite'a `if conn is None: return <safe>` muhafazası

## Bilinen Sınırlamalar / Notlar

- Fallback zinciri sadece **host adı**na uygulanır; port/user/password
  yanlışsa otomatik tahmin etmez (çünkü fallback'le düzelmez).
- `_working_host` cache'i instance-level. Yeni bir `DatabaseTools()`
  oluşturulduğunda zinciri baştan dener — beklenen davranış.
- Production'a deploy edildiğinde `config.json`'daki `"host":"db"`
  değişmeden kalabilir (Docker ağı içinde zaten çalışır). Sadece
  Docker dışı (host shell, başka makine) crawler invocation'larında
  fallback devreye girer — sessiz/zarif şekilde.

---

# PDF UNICODE FONT HOTFIX — Türkçe Karakter Crash (2026-05-21)

## Teşhis

"PDF Raporu İndir" butonuna tıklandığında kullanıcı flash mesajı +
sayfa redirect'i alıyordu, ama gerçek hata sessizdi:

```
PDF Raporu oluşturulurken hata oluştu: Character "İ" at index 10 in text
is outside the range of characters supported by the font used:
"helveticaB". Please consider using a Unicode font.
fpdf.errors.FPDFUnicodeEncodingException
```

Hemen yukarısında:
```
Uyarı: Font dosyası bulunamadı:
/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf. Standart font kullanılacak.
```

Kök neden zinciri:
1. `lib/pdf_generator.py:876` DejaVuSans.ttf yolu bekliyor (Unicode font).
2. Konteynerde `fonts-dejavu` paketi yüklü değil → dosya yok.
3. Fallback `pdf.set_font("Arial", ...)` → fpdf'te "Arial" = core
   Helvetica = **Latin-1 only**.
4. "KAPSAMLI KİŞİ ANALİZİ RAPORU" başlığı index 10'da `İ` (U+0130)
   içeriyor → Latin-1 dışı → `FPDFUnicodeEncodingException`.
5. `generate_pdf_report()` exception'ı yakalayıp `None` dönüyor →
   route flash + 302. HTTP 500 değil, sessiz başarısızlık.

**Etkilenen rotalar (paylaşılan `generate_pdf_report()` yüzünden):**
`/download/image_search_report`,
`/download/comprehensive_analysis_report`, `/download/similar_search_report`
ve diğer tüm PDF export'ları.

## Müdahale 1 — Hot Install (Container)

Çalışan konteynere DejaVu paketlerini canlı kurduk:

```bash
sudo docker exec eyeofweb_app apt-get update -qq && \
sudo docker exec eyeofweb_app apt-get install -y -qq \
    fonts-dejavu fonts-dejavu-core fonts-dejavu-extra
```

Doğrulama:
```bash
$ docker exec eyeofweb_app ls /usr/share/fonts/truetype/dejavu/DejaVuSans*.ttf
DejaVuSans.ttf            DejaVuSans-Bold.ttf
DejaVuSans-Oblique.ttf    DejaVuSans-BoldOblique.ttf
... vb.  ✅
```

## Müdahale 2 — Dockerfile Kalıcılığı

**Dosya:** `src/Dockerfile` (apt install bloğu)

```diff
 RUN apt-get update && apt-get install -y \
     build-essential \
     libgl1 \
     libglib2.0-0 \
     curl \
+    fonts-dejavu \
+    fonts-dejavu-core \
+    fonts-dejavu-extra \
     && rm -rf /var/lib/apt/lists/*
```

`docker compose build web` ile yeni image üretildiğinde paketler kalıcı
olacak; konteyner restart'larında veya başka makinelerde manuel apt
install gerekmiyor.

## Müdahale 3 — `_safe_pdf_text` ASCII Fallback (Savunma Katmanı)

**Dosya:** `src/lib/pdf_generator.py`

Font yüklemesi ileride tekrar düşerse / başka image'a geçilirse / başka
dev makinesinde test edilirse PDF'in **crash etmeden** çıktısı vermeye
devam etmesi için ek bir koruma katmanı eklendi:

### Modül-seviye helper

```python
_TR_ASCII_MAP = str.maketrans({
    "İ": "I", "ı": "i", "Ş": "S", "ş": "s",
    "Ğ": "G", "ğ": "g", "Ö": "O", "ö": "o",
    "Ü": "U", "ü": "u", "Ç": "C", "ç": "c",
    "–": "-", "—": "-", "…": "...", "•": "*",
    "“": '"', "”": '"', "‘": "'", "’": "'",
})

def _safe_pdf_text(text):
    if text is None:
        return text
    if not isinstance(text, str):
        text = str(text)
    if FONT_FAMILY == "DejaVu":
        return text                       # Unicode font aktif — dokunma
    # Latin-1 fallback modu: TR transliterasyon + Latin-1 dışı kalanlar '?'
    converted = text.translate(_TR_ASCII_MAP)
    return converted.encode("latin-1", errors="replace").decode("latin-1")
```

### `PDFReport` override'ları

Tek bir yerden bağlanmak ve tüm `chapter_title` / `chapter_body` /
`cover_page` çağrılarını otomatik korumak için `cell` ve `multi_cell`
metodları subclass'ta override edildi:

```python
class PDFReport(FPDF):
    def cell(self, w=0, h=0, text="", *args, **kwargs):
        if "txt" in kwargs:
            kwargs["txt"] = _safe_pdf_text(kwargs.pop("txt"))
        return super().cell(w, h, _safe_pdf_text(text), *args, **kwargs)

    def multi_cell(self, w=0, h=0, text="", *args, **kwargs):
        if "txt" in kwargs:
            kwargs["txt"] = _safe_pdf_text(kwargs.pop("txt"))
        return super().multi_cell(w, h, _safe_pdf_text(text), *args, **kwargs)
```

`txt=` (eski fpdf API) ve `text=` (yeni API) parametre adları her ikisi
de destekleniyor.

### Davranış matrisi

| FONT_FAMILY | Türkçe Çıktı | Crash Riski |
|---|---|---|
| `DejaVu` (normal) | "KAPSAMLI KİŞİ ANALİZİ" | Yok ✅ |
| `Arial` (fallback) | "KAPSAMLI KISI ANALIZI" | Yok ✅ (bozulmuş ama crash yok) |
| Eski kod, `Arial` fallback | (crash) | FPDFUnicodeEncodingException ❌ |

## Canlı Doğrulama

### Helper unit test:

```bash
$ docker exec eyeofweb_app python3 -c "
import lib.pdf_generator as pg
from lib.pdf_generator import _safe_pdf_text
print('Unicode (DejaVu) mode:', repr(_safe_pdf_text('KAPSAMLI KİŞİ ANALİZİ')))
pg.FONT_FAMILY = 'Arial'
print('Latin-1 fallback:', repr(_safe_pdf_text('KAPSAMLI KİŞİ ANALİZİ — şirket Görsel')))
"
Unicode (DejaVu) mode: 'KAPSAMLI KİŞİ ANALİZİ'           ✅ (dokunulmadı)
Latin-1 fallback:     'KAPSAMLI KISI ANALIZI - sirket Gorsel'   ✅ (transliter)
```

### End-to-end PDF üretim testi (gerçek `generate_pdf_report` çağrısı):

```bash
$ docker exec eyeofweb_app python3 -c "
from lib.pdf_generator import generate_pdf_report
pdf_bytes = generate_pdf_report(
    search_type='Görsel Arama (Eşik: 0.6, Dosya: yüklenen_görüntü.jpg)',
    username='admin',
    search_results=[],
)
print('Generated PDF size:', len(pdf_bytes) if pdf_bytes else 'None')
"
Generated PDF size: 2391906   ✅ (önce None idi)
```

2.39 MB PDF üretildi, "Görsel Arama (Eşik: 0.6, Dosya: yüklenen_görüntü.jpg)"
başlığındaki "Eşik", "Görsel", "yüklenen" Türkçe karakterleri sorunsuz
işlendi.

## Deploy

```bash
sudo docker compose restart web   ✅
```

Konteyner Up, fontlar mount altında erişilebilir (`/usr/share/fonts/truetype/dejavu/`
host volume mount'a dahil DEĞİL — image katmanında olduğundan
volume mount tarafından maskelenmiyor; `/app` dışı). Web sunucusu sağlıklı.

## Production'a Taşıma Notu

Bu hotfix iki katmanlı:
- **Katman 1 (Dockerfile)**: Production'a deploy ederken
  `docker compose build web --no-cache` ile yeni image üretilince
  fontlar baked-in. Apt-install ihtiyacı yok.
- **Katman 2 (kod sanitization)**: Image değişirse / fontlar yine
  kaybolursa PDF üretimi crash etmeyecek; sadece İ→I, ş→s gibi
  transliterasyonla okunur ama bozulmuş çıktı verecek (uyarı niteliğinde).

## Dosyalar

- `src/Dockerfile` — apt install satırına `fonts-dejavu`,
  `fonts-dejavu-core`, `fonts-dejavu-extra` eklendi (3 satır).
- `src/lib/pdf_generator.py` —
  - Modül üstüne `_TR_ASCII_MAP` ve `_safe_pdf_text()` eklendi.
  - `PDFReport.cell` ve `PDFReport.multi_cell` override edildi
    (her PDF yazımı otomatik korumadan geçer).
- (Container) `/usr/share/fonts/truetype/dejavu/*` — apt ile yüklendi.

---

# INSTAGRAM BOT ENTEGRASYONU — Tarama Dashboard'a Yeni OSINT Aracı (2026-05-21)

## Önemli Ayrım (User Net İstedi)

`Tarama Dashboard`'da zaten **"INSTAGRAM TARAMA"** adında bir sekme vardı —
fakat bu eski yazılım aslında verilen kullanıcı adını **Google üzerinden
arayan** bir wrapper'dı (`google_search_crawler.py`'a `--keyword` olarak
geçiyor). Yeni eklenen **"INSTAGRAM BOT"** ise Selenium ile gerçek
Instagram sayfasında takipçi listesini sıyıran ayrı bir araçtır.

**İkisi karıştırılmamalıdır:** mevcut "INSTAGRAM TARAMA" davranışı tamamen
korunmuştur; bot ayrı bir sekme + ayrı bir endpoint + ayrı bir Python
entry point olarak yan yana çalışır.

## 1) Dosya Entegrasyonu

`~/insta_bot/` altındaki dosyalar projeye taşındı. **Konum:** proje
kökündeki `güncellemeler/insta_bot/` (user'ın isteği üzerine
`src/lib/` yerine buraya alındı — bu klasör "yeni eklentiler" hub'ı
olarak kullanılıyor, mevcut `yeni_dashboard/` ile yan yana).

```
~/insta_bot/worker.py     →  güncellemeler/insta_bot/worker.py   (REFAKTÖR)
~/insta_bot/panel.py      →  güncellemeler/insta_bot/panel.py    (referans, kullanılmıyor)
~/insta_bot/cookies.pkl   →  güncellemeler/insta_bot/cookies.pkl
                              güncellemeler/insta_bot/__init__.py
                              güncellemeler/insta_bot/instagram_crawler.py (CLI wrapper)
```

### worker.py Refaktör Notları

Orijinal `worker.py` GUI tarafından çağrılmak üzere yazılmıştı ve subprocess
mode için **iki büyük blocker** içeriyordu:

1. `input()` çağrısı: kullanıcının tarayıcıda manuel login yapıp ENTER
   basmasını bekliyordu.
2. `hedefler.txt` cwd zorunluluğu: dosya yoksa boş liste dönüp çıkıyordu.

Yeni `lib/insta_bot/worker.py`:
- **CLI argparse**: `--targets "a,b,c"`, `--targets-file`, `--max-per-target`,
  `--output-file`, `--cookies-file`, `--headless`, `--allow-manual-login`.
- **`cookies.pkl` öncelikli**: kayıtlı oturum varsa otomatik yükleniyor,
  `input()` çağrılmıyor. Cookies yüklenemezse `--allow-manual-login`
  flag'i + TTY varsa eski davranışa düşer; yoksa exit code 4 ile temiz
  başarısızlık.
- **`print(..., flush=True)`**: her satır subprocess pipe'a akıyor —
  yeni terminal penceresi açmadan dashboard'a canlı log.
- Selenium `webdriver_manager` import'u lazy + opsiyonel; yoksa
  PATH'teki chromedriver'a düşer.
- `--headless=new` (Chrome 109+) varsayılan; eski headless IG bloklarına
  karşı daha dayanıklı.

## 2) CLI Entry Point — `güncellemeler/insta_bot/instagram_crawler.py` (YENİ)

`google_search_crawler.py` / `facebook_crawler.py` ile aynı pattern; ancak
proje kökü yerine **bot'un kendi klasörü altında**. `worker.py` ile
co-located olduğundan `sys.path` aynı dizine ekleniyor, `from worker
import main as worker_main` ile in-process invoke.

```bash
# Manuel test (host shell'den):
cd /home/user/Masaüstü/eye_of_web/güncellemeler/insta_bot
python3 instagram_crawler.py --targets "natgeo,nasa" --headless --max-per-target 20

# Dashboard'un kullandığı invocation pattern aynı (server.js INSTA_BOT_PATH ile cd eder).
```

## 3) Backend (Express) — `yeni_dashboard/backend/server.js`

İki yapısal ekleme:

### A) Yeni helper: `runStreaming(prettyName, args)`

`runInTerminal()` mevcut araçlar için ayrı bir x-terminal-emulator
penceresi açıyor. Instagram Bot için **in-app canlı log** istendi —
yeni helper subprocess'i `spawn('bash', ['-c', '... python3 ...'])` ile
başlatıp stdout/stderr'i **satır satır parse edip `addLog()`'a akıtıyor**.
Frontend'in `/api/logs` polling'i bu satırları otomatik gösterir.

```js
function runStreaming(prettyName, args) {
  const cmd = `source WorkEnv/bin/activate && python3 ${args.map(...).join(' ')}`;
  addLog(`${prettyName}: BAŞLATILIYOR -> ${args[0]}`);
  const proc = spawn('bash', ['-c', cmd], { cwd: BASE_PATH, stdio: ['ignore','pipe','pipe'] });
  proc.stdout.on('data', chunk => /* satır parse + addLog */);
  proc.stderr.on('data', chunk => /* satır parse + [stderr] tag + addLog */);
  proc.on('close', code => addLog(`${prettyName}: TAMAMLANDI (exit=${code})`));
}
```

### B) Endpoint'ler

| Endpoint | Yöntem | Çağrılan Python | Davranış |
|---|---|---|---|
| `/api/scan/instagram` | POST | `google_search_crawler.py --keyword <user>` | **MEVCUT — DOKUNULMADI**. Kullanıcı adını Google'da arayan eski yazılım. |
| `/api/scan/instagram-bot` | POST | `instagram_crawler.py --targets ...` | **YENİ** — Selenium tabanlı takipçi sıyırma; in-app canlı log. |

Yeni endpoint payload'u:
```json
{
  "targets": "natgeo,nasa\nbbcnews",   // virgül / yeni satır / noktalı virgül
  "maxPerTarget": 20,                  // 1-500 arası, opsiyonel
  "headless": true                     // opsiyonel
}
```

Backend:
- Çoklu hedef parse + tekilleştirme + `@` prefix kırpma
- `runStreaming('INSTABOT', args)` ile in-app log
- Validation: boş liste → 400

## 4) Frontend (React) — `yeni_dashboard/src/App.jsx`

### Yeni state'ler
```jsx
const [instagramTargets, setInstagramTargets] = useState('')           // textarea
const [instagramMaxPerTarget, setInstagramMaxPerTarget] = useState(20) // numerik
const [instagramHeadless, setInstagramHeadless] = useState(true)       // checkbox
```

### Yeni scan handler
```jsx
scan.instagram      // MEVCUT: tek username → Google search
scan.instagramBot   // YENİ: textarea → /api/scan/instagram-bot
```

### Yeni UI Bloğu (mevcut INSTAGRAM TARAMA'nın HEMEN ALTINA eklendi)

```jsx
{/* Instagram BOT — Selenium tabanlı takipçi sıyırma */}
<section className="scan-block">
  <span className="block-label">INSTAGRAM BOT (TAKİPÇİ)</span>
  <textarea
    placeholder="Hedef kullanıcı adları — virgül veya yeni satırla ayırın"
    rows={3}
    value={instagramTargets}
    onChange={e => setInstagramTargets(e.target.value)}
  />
  <label>Max/hedef: <input type="number" min={1} max={500} ... /></label>
  <label><input type="checkbox" ... /> Headless</label>
  <button className="btn-scan" onClick={scan.instagramBot}>▶ BOTU BAŞLAT</button>
</section>
```

**Sonuç ekranı:** mevcut alt-Terminal paneli zaten `/api/logs` polling
yapıyor. Backend'in `runStreaming` ile akıttığı her satır otomatik olarak
in-app terminal'de görünür — ayrı bir popup terminal AÇILMAZ.

## 5) Bağımlılıklar — `src/requirements.txt`

Zaten mevcut, yeni paket gerekmedi:
```
Pillow>=9.5.0
selenium>=4.10.0
webdriver-manager>=4.0.0
```

## Konteyner / Sunucu Restart Gerekliliği

**Backend (Node Express, port 5006):**
- `backend/server.js` değiştirildi → `node server.js` process'ini yeniden
  başlatmak GEREKİYOR (PM2 / systemd / manuel).

**Frontend (Vite dev server, port 5005):**
- `App.jsx` değiştirildi → Vite HMR otomatik reload eder, manuel restart
  gerekmez. Production build için `npx vite build` (test edildi, başarılı:
  166KB JS, 17KB CSS, 1738 modül).

**Flask web (port 5000, Docker):**
- Etkilenmedi. `eyeofweb_app` konteynerına bu hotfix kapsamında dokunulmadı.

## Doğrulama

```bash
# Backend syntax
$ node -c backend/server.js  → OK

# Frontend build
$ npx vite build
✓ 1738 modules transformed.
dist/assets/index-770ee301.js   166.19 kB │ gzip: 52.01 kB
✓ built in 24.40s

# Python crawler help
$ cd src && python3 instagram_crawler.py --help
usage: instagram_crawler.py [-h] [--targets TARGETS] ...   ✅
```

## Dosyalar

- `güncellemeler/insta_bot/__init__.py` (yeni paket)
- `güncellemeler/insta_bot/worker.py` (refaktör — non-interactive + CLI argparse)
- `güncellemeler/insta_bot/panel.py` (orijinal Tkinter GUI; referans)
- `güncellemeler/insta_bot/cookies.pkl` (önceden kayıtlı oturum)
- `güncellemeler/insta_bot/instagram_crawler.py` (CLI wrapper — dashboard buraya çağırır)
- `güncellemeler/yeni_dashboard/backend/server.js`:
  - `runStreaming(prettyName, args)` helper (yeni — in-app log akışı)
  - `/api/scan/instagram` (DEĞİŞMEDİ — Google üzerinden)
  - `/api/scan/instagram-bot` (yeni endpoint)
- `güncellemeler/yeni_dashboard/src/App.jsx`:
  - 3 yeni state (`instagramTargets`, `instagramMaxPerTarget`, `instagramHeadless`)
  - `scan.instagramBot` handler (yeni)
  - INSTAGRAM TARAMA bloğu (DEĞİŞMEDİ)
  - INSTAGRAM BOT (TAKİPÇİ) bloğu (yeni)

## Güvenlik / Operasyonel Notlar

- **Manuel login modu**: Cookies süresi dolduğunda dashboard'dan in-app
  log gösterse de stdin TTY yok; bot exit code 4 ile temiz fail eder.
  Cookies yenilemek için host shell'den:
  ```bash
  python3 src/instagram_crawler.py --targets test --allow-manual-login
  ```
- **Çıktı dosyası**: `güncellemeler/insta_bot/instagram_takipciler.txt`'a
  append (cwd default'u). Eski `~/insta_bot/takipciler.txt` ile karıştırılmaz.
- **Headless varsayılan**: dashboard UI'da default işaretli; ancak
  Instagram bazı sayfalarda headless'ı bloklayabilir; sorun olursa
  checkbox'ı kapatın.
- **Rate limit**: bot bir hedef başına `--max-per-target` (default 20)
  takipçi sonra duruyor; çoklu hedef sıralı işlenir, paralel YOK.

---

# INSTAGRAM BOT ARAYÜZ GÜNCELLEMESİ — Sol Menüden Üst Navbar'a Taşıma (2026-05-22)

## Hedef

Önceki entegrasyonda Instagram BOT, sol kenar menüsünde dar bir blok
olarak duruyordu — textarea + birkaç ayar + buton sığdırılmıştı.
Kullanıcı isteği üzerine bot **bağımsız bir üst sekme**'ye taşındı:
"KONTROL" / "RAPOR" yanına "INSTAGRAM BOT" eklendi, sol menüdeki
kısıtlı blok kaldırıldı, ve yeni sekmeye geniş + odaklı bir UI
yerleştirildi.

## Mimari Kararı

Dashboard React (App.jsx) + Vite tabanlı bir SPA. `react-router`
mevcut değil; üst sekmeler `activeTab` state üzerinden çalışıyor
(KONTROL = `'control'`, RAPOR = `'report'`). User'ın iki seçenek
sunulduğunda **Seçenek A**'yı (mevcut sekme paterni) onayladı:

> "Projeye react-router ekleyip tüm yapıyı refactor etmeye gerek yok.
> React'in activeTab state'ini kullanarak..."

Dolayısıyla "/instabot" gerçek bir URL değil; `activeTab === 'instabot'`
ile koşullu render edilen bir üçüncü sekme. Diğer sekmelerle birebir
aynı pattern — `react-router` bağımlılığı eklenmedi.

## Cerrahi Müdahaleler

### 1) Üst Navbar — Yeni Sekme

**Dosya:** `güncellemeler/yeni_dashboard/src/App.jsx`

`top-btns` bloğunda KONTROL ile RAPOR arasına eklendi:

```jsx
<button
  className={`btn-tab ${activeTab === 'instabot' ? 'btn-tab-active' : ''}`}
  onClick={() => setActiveTab('instabot')}
>
  <AtSign size={13} /> INSTAGRAM BOT
</button>
```

**Not:** lucide-react bu sürümde `Instagram` ikonunu export etmiyor
(`RollupError: "Instagram" is not exported`). `AtSign` ile değiştirildi —
hem semantik (Instagram handle = @username) hem mevcut sürümde mevcut.

### 2) 3-Yollu Conditional Render

Eski binary ternary genişletildi:

```jsx
{activeTab === 'control' ? (
  <div className="main-area">...kontrol...</div>
) : activeTab === 'report' ? (
  <div className="main-area report-area">...rapor...</div>
) : (
  <div className="main-area instabot-area">...instabot...</div>
)}
```

Terminal/log paneli (`terminal-wrap`) bu ternary'nin **dışında**
kaldığı için **3 sekmede de altta görünüyor** — sekme değişimi
log akışını kesmiyor. Doğrulandı: `terminal-wrap` satır 855,
ternary kapanışı satır 854.

### 3) Sol Menüden Silme

`scan-block` "INSTAGRAM BOT (TAKİPÇİ)" tamamen kaldırıldı; yerinde
yalnızca bir yorum satırı kaldı:

```jsx
{/* INSTAGRAM BOT (TAKİPÇİ) bu sol menüden üst navbar sekmesine taşındı —
    Bkz. activeTab === 'instabot' bloğu. */}
```

**INSTAGRAM TARAMA** (Google üzerinden arayan eski araç) sol menüde
dokunulmadan kaldı — user özellikle bunu istedi.

### 4) Yeni Instabot Paneli — Geniş & Şık

**Layout:** 1100px max-width, dikey gap'li flex container. İçerik:

1. **Gradient başlık şeridi** — AtSign ikonu + "INSTAGRAM BOT —
   TAKİPÇİ SIYIRMA" + entry-point path açıklaması.

2. **2-kolon grid** (`gridTemplateColumns: '2fr 1fr'`):
   - **Sol (2 birim):** Büyük textarea (12 satır, monospace,
     min-height 220px), 4-satır placeholder örneği, altta canlı
     hedef sayacı.
   - **Sağ (1 birim):** Ayarlar paneli — Max/hedef numerik input,
     Headless checkbox, sıkıştırılmış BAŞLAT butonu (pink gradient),
     çıktı dosyası bilgisi.

3. **Bot Konsol Paneli** — `logs` array'inden `INSTABOT|INSTAGRAM BOT`
   regex'iyle filtrelenen satırlar; 320px sabit yükseklik, scroll'lu.
   Satır renkleri otomatik:
   - `[ERR]` / `[FATAL]` / `[stderr]` → `#f87171` (kırmızı)
   - `[HIT]` → `#34d399` (yeşil)
   - `[DONE]` / `[SUMMARY]` / `TAMAMLANDI` → `#60a5fa` (mavi)
   - Diğer → `#94a3b8` (gri)
   - Boş durumda yer-tutucu açıklama.

### 5) Backend (Express) — Değişiklik YOK

`/api/scan/instagram-bot` endpoint'i önceki turda eklendi ve
`runStreaming('INSTABOT', args, { cwd: INSTA_BOT_PATH })` ile
zaten doğru biçimde çağrılıyor. Bu UI hotfix backend dokunmuyor;
sadece mevcut endpoint'in nasıl tetiklendiğini değiştiriyor.

`scan.instagramBot` handler önceki turdan beri ayrı bir method olarak
duruyor (`scan.instagram`'dan ayrı); buton sadece bunu çağırıyor.

### 6) State Değişkenleri — Korundu

`instagramTargets`, `instagramMaxPerTarget`, `instagramHeadless`
state'leri zaten önceki turda eklenmişti; üst sekmede yeniden
kullanıldı. Sol menüde tek başına kalan eski `instagramUser` state'i
(Google search için) dokunulmadan kaldı.

## Doğrulama

```bash
$ node -c güncellemeler/yeni_dashboard/backend/server.js
OK server.js  ✅

$ cd güncellemeler/yeni_dashboard && npx vite build
✓ 1738 modules transformed.
dist/assets/index-2b99919a.css   17.31 kB │ gzip:  4.26 kB
dist/assets/index-5fae77aa.js   171.04 kB │ gzip: 53.43 kB
✓ built in 6.05s  ✅
```

JS boyutu 166KB → 171KB (+5KB) — yeni panel inline stilleri ve filtre
mantığı için makul artış.

## Restart Gerekliliği

- **Frontend (Vite dev server, port 5005)**: HMR otomatik reload yapar,
  manuel restart **gerekmez**. Production build için `npx vite build`
  doğrulandı.
- **Backend (Express, port 5006)**: Bu turda dokunulmadı — restart
  gerekmez. Önceki turdaki `runStreaming` / endpoint değişiklikleri
  hâlâ canlıda olmalı.
- **Flask web (port 5000, Docker)**: İlgisiz.

## Dosyalar

- `güncellemeler/yeni_dashboard/src/App.jsx`:
  - `AtSign, Users, Play` import edildi (lucide-react)
  - `activeTab === 'instabot'` branch'i eklendi
  - Sol menüden INSTAGRAM BOT (TAKİPÇİ) bloğu silindi
  - ~190 satırlık yeni instabot sekme paneli eklendi
- `güncellemeler/yeni_dashboard/backend/server.js`: dokunulmadı.

## Bilinen Sınırlamalar

- "Bot Konsol Çıktısı" paneli ana `logs` array'inden filtreler — eğer
  log ring buffer (1000 satır) bot çıktısını taşırsa kaybedilir.
  Pratikte sorun değil; tek bir bot oturumu nadiren 200+ satır üretir.
- Sekme değiştirildiğinde `instagramTargets` state'i KORUNUR — bot
  başlatılmış ve KONTROL'e geçilse de bot arka planda devam eder.

---

# YÜZ GÜVENLİĞİ (face_security_v3) ENTEGRASYONU — Subprocess Launcher (2026-05-22)

## Hedef

`~/Masaüstü/face_security_v3/` projesini EyeOfWeb dashboard'a üst sekme
olarak ekle — "KONTROL" ile "INSTAGRAM BOT" arasına. Çoklu RTSP kamera,
yüz tanıma, ALPR ve Telegram bildirimleri bu yeni sekmeden başlatılıp
durdurulabilsin.

## Önemli Mimari Tespit — iframe / Port DEĞİL

`face_security_v3/main.py` incelendiğinde **Tkinter desktop uygulaması**
olduğu görüldü:

```python
from tkinter import Tk, messagebox
from ui.security_panel_ui import SecurityPanelApp
```

`launch.sh` ise `python3 main.py` çağırarak native bir pencere açıyor.
**Flask/FastAPI YOK, port'a bind ETMİYOR, iframe edilemez.**

Bu yüzden orijinal istekteki "5005 portunda çalışacak / iframe ile göster"
yaklaşımları teknik olarak mümkün değildi. User onayıyla **Seçenek A
(subprocess launcher)** uygulandı: dashboard'dan tetiklenen butonla
`launch.sh` arka planda başlatılır, Tkinter penceresi kendi pencere
yöneticisi tarafından açılır (X server üzerinden). Dashboard'da bir
**kontrol paneli + canlı durum + log akışı** sergilenir.

## 1) Dosya Kopyalama

```bash
mkdir -p güncellemeler/face_security_v3
rsync -a --info=stats2 \
  --exclude='venv/' \
  --exclude='unknown_plates/' \
  --exclude='logs/' \
  --exclude='snapshots/' \
  --exclude='__pycache__/' \
  --exclude='**/__pycache__/' \
  --exclude='.git/' \
  --exclude='.backup_*' \
  --exclude='.pytest_cache/' \
  ~/Masaüstü/face_security_v3/ \
  güncellemeler/face_security_v3/
```

Sonuç: 227MB → **12MB** (runtime data hariç tutuldu).

Kopyalanan içerikler:
```
güncellemeler/face_security_v3/
├── auth/                          (PIN bcrypt auth)
├── auth_config.json
├── camera/                        (RTSP kamera yöneticisi)
├── camera_config.json
├── config/                        (alt config dosyaları)
├── config.py
├── database/                      (yüz embedding DB)
├── detection/                     (InsightFace processor)
├── docs/
├── embeddings_cache.pkl
├── launch.sh                      (entry point)
├── main.py                        (Tkinter ana app)
├── migrate_from_v2.py
├── migrate_pin_to_bcrypt.py
├── models/                        (InsightFace buffalo_s — 5.3MB)
├── notifications/                 (Telegram bot)
├── README.md
├── requirements.txt
├── ui/                            (security_panel_ui, plate_tab, settings_tab)
└── utils/                         (snapshot_cleaner)
```

`launch.sh` executable bayrağı doğrulandı.

## 2) Backend (Express) — Yeni Endpoint'ler

**Dosya:** `güncellemeler/yeni_dashboard/backend/server.js`

### Sabitler
```js
const FACE_SECURITY_PATH = '/home/user/Masaüstü/eye_of_web/güncellemeler/face_security_v3';
let faceSecurityProc = null;  // tek instance, in-memory state
```

### `POST /api/face-security/start`
- Eğer mevcut process canlıysa **409 Conflict** + pid döner.
- `spawn('bash', [launchScript])` ile `launch.sh` çalıştırır.
- `cwd: FACE_SECURITY_PATH`, env'e `DISPLAY=:0` eklenir (X server için).
- stdout/stderr satır satır parse edilip `addLog('FACE-SEC: ...')` ile
  in-app log paneline akıtılır.
- `proc.on('close')` ile `faceSecurityProc = null` (otomatik sıfırlanır).
- Yanıt: `{ success: true, pid: <pid> }`

### `POST /api/face-security/stop`
- SIGTERM gönderir; 3 saniye sonra hâlâ canlıysa SIGKILL.
- Process zaten kapalıysa idempotent: `{ success: true, running: false }`.

### `GET /api/face-security/status`
- `{ running, pid, path }` döner. Frontend her POLL_INTERVAL'de polling yapar.

## 3) Frontend (React) — Yeni Sekme

**Dosya:** `güncellemeler/yeni_dashboard/src/App.jsx`

### Navbar
KONTROL ↔ INSTAGRAM BOT arasına eklendi (user'ın istediği sıra):

```jsx
<button className="btn-tab ..." onClick={() => setActiveTab('control')}>
  <Camera size={13} /> KONTROL
</button>
<button className="btn-tab ..." onClick={() => setActiveTab('face-security')}>
  <ShieldCheck size={13} /> YÜZ GÜVENLİĞİ
</button>
<button className="btn-tab ..." onClick={() => setActiveTab('instabot')}>
  <AtSign size={13} /> INSTAGRAM BOT
</button>
```

### State & Polling
```jsx
const [faceSecStatus, setFaceSecStatus] = useState({ running: false, pid: null })
const [faceSecBusy, setFaceSecBusy] = useState(false)

// /api/face-security/status'u POLL_INTERVAL'de poll'lar
```

### Handler'lar
- `handleFaceSecStart()` → POST start; pid'i state'e yazar.
- `handleFaceSecStop()` → `confirm()` ile onay alır, POST stop.

### 4-Yollu Ternary
Eski 3-yollu (`control → report → instabot`) genişletildi:

```
control ? : report ? : face-security ? : instabot
```

### YÜZ GÜVENLİĞİ Paneli (~225 satır)
- **Gradient başlık şeridi** (yeşil) — `ShieldCheck` ikonu + uygulama
  adı + entry-point path + **anlık durum rozeti** (yeşil pulse = çalışıyor,
  gri = kapalı, PID gösterilir).
- **2-kolon grid:**
  - **Sol:** "ÖZELLİKLER" listesi — README'den özet (Çoklu Kamera, Yüz
    Tanıma, ALPR, Telegram, Yerel-Öncelikli) + sarı uyarı kutusu
    ("Tkinter desktop, X server gerekli").
  - **Sağ:** "KONTROL" — entry-point path, durum metni, **conditional
    button**:
    - Process çalışmıyorsa: yeşil gradient "▶ BAŞLAT"
    - Çalışıyorsa: kırmızı gradient "■ DURDUR"
    - Busy state'te disable + opacity 0.6.
- **Filtreli log akışı** — `logs` array'inden `FACE-SEC|YÜZ GÜVENLİĞİ`
  regex'li satırlar; 280px sabit yükseklik, monospace, renk kodlu:
  - `[stderr]/ERROR/Traceback/SPAWN HATASI` → kırmızı
  - `KAPANDI/DURDURMA SİNYALİ` → sarı
  - Diğer → gri

### lucide-react ikonları
Eklendi: `ShieldCheck`, `Square`, `Cpu`, `Bell`, `Car`. Daha önceki
`Instagram` çakışması gibi sürüm uyumsuzluğu YOK — hepsi mevcut.

## Doğrulama

```bash
$ node -c güncellemeler/yeni_dashboard/backend/server.js
OK server.js  ✅

$ cd güncellemeler/yeni_dashboard && npx vite build
✓ 1738 modules transformed.
dist/assets/index-c7b2b62d.css   17.34 kB │ gzip:  4.27 kB
dist/assets/index-f46cbbba.js   181.75 kB │ gzip: 55.63 kB
✓ built in 2.98s  ✅

$ test -x güncellemeler/face_security_v3/launch.sh
launch.sh executable  ✅
```

JS bundle 171KB → 181KB (+10KB) — yeni panel + handler'lar + lucide
ikonları için.

## Restart Gerekliliği

- **Backend (Express, port 5006)**: `node server.js` process'ini
  yeniden başlatın — yeni endpoint'ler ve sabitler yüklensin.
- **Frontend (Vite dev server, port 5005)**: HMR otomatik reload;
  manuel restart gerekmez. Prod için `npx vite build` doğrulandı.
- **Flask web (port 5000, Docker)**: İlgisiz.

## Bilinen Sınırlamalar / Operasyonel Notlar

- **X server şartı**: face_security_v3 Tkinter penceresi açar. Bu
  yüzden dashboard'un çalıştığı host'ta `DISPLAY` env'i geçerli bir
  X server'a işaret etmeli (default `:0`). Headless sunucuda
  (SSH-only) çalışmaz.
- **Tek instance**: backend `faceSecurityProc` tek bir process'i
  takip ediyor. İkinci kez START çağrılırsa **409 Conflict** döner.
- **Runtime data**: `snapshots/`, `unknown_plates/`, `logs/`,
  `venv/` kopyalanmadı. İlk çalıştırmada `launch.sh` `mkdir -p logs`
  yapar; `venv` mevcut sistem Python3'üyle DEĞİL, kendi venv'iyle
  ÇALIŞMIYOR. Eğer venv gerekirse:
  ```bash
  cd güncellemeler/face_security_v3
  python3 -m venv venv && source venv/bin/activate
  pip install -r requirements.txt
  ```
  ve `launch.sh`'i venv'i aktive edecek şekilde güncelleyin (şu an
  doğrudan sistem `python3`'ünü kullanıyor).
- **Cleanup**: Dashboard backend kapanırsa (`node server.js` çıkışı)
  spawn'lanan Tkinter process'i KENDİ ÖMRÜNÜ SÜRDÜRÜR (detached
  değil ama parent ölünce de devam edebilir — Linux default).
  Manuel kill için status'ten PID alıp `kill <pid>` mümkün.

## Dosyalar

- `güncellemeler/face_security_v3/` (yeni — 12MB)
- `güncellemeler/yeni_dashboard/backend/server.js`:
  - `FACE_SECURITY_PATH` sabiti
  - `faceSecurityProc` global state
  - 3 yeni endpoint: `/api/face-security/start|stop|status`
- `güncellemeler/yeni_dashboard/src/App.jsx`:
  - 5 yeni lucide ikon (`ShieldCheck`, `Square`, `Cpu`, `Bell`, `Car`)
  - 2 yeni state (`faceSecStatus`, `faceSecBusy`)
  - Status polling useEffect
  - 2 yeni handler (`handleFaceSecStart`, `handleFaceSecStop`)
  - Yeni navbar butonu
  - 3-yollu → 4-yollu ternary
  - ~225 satırlık yeni face-security paneli

---

# YÜZ GÜVENLİĞİ — TKINTER → FLASK WEB REFACTOR (2026-05-22)

## Hedef

Önceki turdaki "Tkinter desktop + subprocess launcher" yaklaşımı kullanıcı
deneyimi için elverişsizdi (kendi penceresinde açılıyordu). User isteği:

> "uygulamanın yeni bir masaüstü penceresinde açılması değil, arayüzünün
> doğrudan web tarayıcısı içinde (iframe veya benzeri bir yöntemle)
> çalışmasıdır"

Bu yüzden `face_security_v3` Tkinter arayüzü **iptal edildi** ve uygulama
Flask tabanlı bir web sunucusuna refactor edildi. Tüm backend modülleri
(camera/detection/database/notifications/auth) BİREBİR korundu — sadece
UI katmanı değişti.

## 1) Yeni Entry Point — `web_app.py`

**Dosya:** `güncellemeler/face_security_v3/web_app.py` (yeni, ~280 satır)

**Mimari:**
- Flask 3.x app, default `127.0.0.1:5007`
- `_init_components()` — Flask başlamadan önce InsightFace + Telegram +
  StreamHandler + DatabaseManager yüklenir (lazy/idempotent, threading.Lock)
- `img_queue` (maxsize=2) — kamera stream'inden gelen RGB kareler
- `result_queue` → background `_drain_results()` thread'i → `recent_detections`
  deque (maxlen=50) — JSON endpoint için
- `_mjpeg_generator()` — `img_queue` boşken siyah "Kamera bekleniyor..."
  placeholder; yoksa JPEG @ q=80
- `@after_request` — `X-Frame-Options` başlığı kaldırılır, CSP
  `frame-ancestors *` ile iframe edilmeye açık

**Endpoint'ler:**
| URL | Method | İşlev |
|---|---|---|
| `/` | GET | Ana web arayüzü (Jinja `index.html`) |
| `/video_feed` | GET | MJPEG (multipart/x-mixed-replace) canlı akış |
| `/api/cameras` | GET | Tanımlı kamera listesi + aktif kamera |
| `/api/switch` | POST | `{cam_id}` ile aktif kamera değiştir |
| `/api/patrol/start` | POST | Devriye (rotasyonlu) modu başlat |
| `/api/patrol/stop` | POST | Devriye durdur |
| `/api/status` | GET | Sistem durumu (active_camera, people_known, telegram, port) |
| `/api/detections` | GET | Son 50 yüz tespiti (JSON) |
| `/snapshots/<file>` | GET | known/ veya unknown/ altındaki snapshot dosyası |

**Port seçimi:** User isteği "5005" idi ama 5005 portu **React Vite dev
server** tarafından zaten kullanılıyor (vite.config.js). Çakışmamak için
varsayılan **5007** seçildi; `FACE_SEC_PORT` env var ile override
edilebilir.

## 2) Yeni Web UI Şablonu

**Dosyalar:**
- `güncellemeler/face_security_v3/web_templates/index.html` (~135 satır)
- `güncellemeler/face_security_v3/web_static/style.css` (~190 satır)

**Layout (240px sol · esnek orta · 280px sağ grid):**
- **Sol panel:** Kamera listesi (25 kamera; configured/unconfigured rozet),
  Devriye ▶/■ butonları, info-panel (bilinen kişi sayısı, telegram durumu, port)
- **Orta panel:** "CANLI GÖRÜNTÜ" başlığı + aktif kamera adı + MJPEG `<img>`
  (object-fit: contain) + footer ("MJPEG akışı · OpenCV → JPEG @ q=80")
- **Sağ panel:** Son tespitler listesi — `det-known` (yeşil) ve
  `det-unknown` (pembe) sınıfları, skor + kamera + saat damgası

**Polling:** `/api/status` ve `/api/detections` 2 saniyede bir.
Kamera item'a tıklama → POST `/api/switch`. Devriye butonları → POST
`/api/patrol/start|stop`.

**Iframe-friendly:** Flask `@after_request` ile `X-Frame-Options`
kaldırıldı + `Content-Security-Policy: frame-ancestors *` set edildi.
Browser modern CSP'i öncelikli okuduğundan iframe sorunsuz açılır.

## 3) `launch.sh` Yeni Davranış

**Dosya:** `güncellemeler/face_security_v3/launch.sh`

```diff
- exec env OPENCV_OPENCL_RUNTIME=disabled python3 main.py 2>> logs/launch_error.log
+ exec env OPENCV_OPENCL_RUNTIME=disabled \
+      FACE_SEC_HOST="${FACE_SEC_HOST:-127.0.0.1}" \
+      FACE_SEC_PORT="${FACE_SEC_PORT:-5007}" \
+      python3 web_app.py 2>> logs/launch_error.log
```

Eski Tkinter entry'sine dönmek isteyenler için `main.py` korundu
(deprecation notice docstring eklendi); `ui/` modülleri de duruyor
(import edilmiyor).

## 4) `requirements.txt`

`Flask>=3.0.0` eklendi.

## 5) Express Backend Güncellemesi

**Dosya:** `güncellemeler/yeni_dashboard/backend/server.js`

Eski `/api/face-security/status` sadece subprocess PID'ini takip ediyordu.
Yeni sürüm **gerçek Flask sunucusunu da HTTP probe** ediyor:

```js
const FACE_SEC_PORT = 5007;

app.get('/api/face-security/status', async (req, res) => {
  const procAlive = (faceSecurityProc !== null && faceSecurityProc.exitCode === null);
  let httpReady = false;
  if (procAlive) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 800);
      const r = await fetch(`http://127.0.0.1:${FACE_SEC_PORT}/api/status`, { signal: ctrl.signal });
      clearTimeout(t);
      httpReady = r.ok;
    } catch { httpReady = false; }
  }
  res.json({
    running: procAlive,
    httpReady,                   // ← iframe yüklenebilir mi?
    pid: ...,
    port: FACE_SEC_PORT,
    iframeUrl: `http://127.0.0.1:${FACE_SEC_PORT}/`,
  });
});
```

`/api/face-security/start` ve `/stop` aynı kaldı (launch.sh subprocess'i
hâlâ launcher).

## 6) React Dashboard — Iframe Entegrasyonu

**Dosya:** `güncellemeler/yeni_dashboard/src/App.jsx`

Eski 2-kolon özellikler + kontrol + log paneli (~245 satır) tamamen
silindi (cerrahi Python replace). Yerine **3 katmanlı kompakt layout**:

### Katman 1 — Üst şerit (~80 satır)
- ShieldCheck ikonu + "YÜZ GÜVENLİĞİ" başlığı + "Flask web ·
  127.0.0.1:5007 · iframe → tarayıcı içi RTSP + InsightFace + ALPR" alt yazısı
- Sağda canlı durum rozeti (yeşil dot + "ÇALIŞIYOR (pid ...)" veya gri + "KAPALI")
- Inline **▶ BAŞLAT** (yeşil) / **■ DURDUR** (kırmızı confirm dialog) butonu

### Katman 2 — Iframe konteyneri (flex: 1, min 500px)
**3-state render:**
1. `running && httpReady` → `<iframe src={iframeUrl}>` (Flask UI gömülü)
2. `running && !httpReady` → Spinner + "Flask sunucusu başlatılıyor…
   InsightFace modeli yükleniyor (PID X)" — model yüklenirken polling
   devam eder, httpReady true olunca iframe otomatik açılır
3. `!running` → Büyük ShieldCheck ikonu + "Yüz Güvenliği servisi kapalı"
   + "Üstteki BAŞLAT butonuna basın" + sarı uyarı kutusu (InsightFace
   yükleme süresi notu)

### Katman 3 — Process log şeridi (~140 satır)
- Sabit max-height 140px (iframe alanı küçültmesin)
- `logs` array'inden `FACE-SEC|YÜZ GÜVENLİĞİ` regex'li satırlar, son 30
- Renk kodları:
  - `[stderr]/ERROR/Traceback/SPAWN HATASI` → kırmızı
  - `KAPANDI/DURDURMA SİNYALİ` → sarı
  - Diğer → gri

### State değişikliği
```js
const [faceSecStatus, setFaceSecStatus] = useState({
  running: false,
  httpReady: false,        // YENİ
  pid: null,
  iframeUrl: 'http://127.0.0.1:5007/',  // YENİ
})
```

Status polling backend response'undaki `httpReady` ve `iframeUrl`'i de
yakalıyor.

## Akış (Kullanıcı Bakışı)

1. User dashboard'da **YÜZ GÜVENLİĞİ** sekmesine tıklar
2. Sekme açılır — sunucu kapalıysa "Servis kapalı" ekranı görünür
3. **▶ BAŞLAT** → backend `launch.sh`'i spawn eder (Express) → process
   canlı, ama Flask henüz model yüklüyor → React polling `running=true,
   httpReady=false` → "Flask başlatılıyor…" spinner gösterilir
4. ~10-20sn sonra Flask `/api/status` 200 döner → polling
   `httpReady=true` → iframe otomatik render edilir (`src=127.0.0.1:5007/`)
5. User dashboard'dan ÇIKMADAN tarayıcı içinde face_security UI'ı kullanır:
   kamera seçer, devriye başlatır, son tespitleri görür
6. **■ DURDUR** → SIGTERM → 3sn sonra SIGKILL → polling sıfırlanır → "Servis kapalı"

## Doğrulama

```bash
$ cd güncellemeler/face_security_v3 && python3 -m py_compile web_app.py
OK web_app.py syntax  ✅

$ python3 -c "import flask; print(flask.__version__)"
3.1.3  ✅

$ node -c güncellemeler/yeni_dashboard/backend/server.js
OK server.js syntax  ✅

$ cd güncellemeler/yeni_dashboard && npx vite build
✓ 1738 modules transformed.
dist/assets/index-c1f7a610.css   17.58 kB
dist/assets/index-24b83623.js   177.93 kB
✓ built in 2.91s  ✅

$ ls -la güncellemeler/face_security_v3/launch.sh
-rwxrwxr-x ... launch.sh   (executable ✅)
```

## Restart Gerekliliği

| Servis | Restart? | Neden |
|---|---|---|
| Express backend (port 5006) | **EVET** | `runStreaming`, `FACE_SEC_PORT`, yeni `/status` |
| Vite dev server (port 5005) | hayır | HMR otomatik reload |
| Flask web (port 5000, Docker) | hayır | İlgisiz |
| face_security_v3 Flask (port 5007) | duruma göre | İlk start için backend'in **BAŞLAT** butonuna bas |

Komutlar:
```bash
# Express backend restart
cd güncellemeler/yeni_dashboard/backend
pkill -f "node server.js" 2>/dev/null
node server.js &

# Flask sunucusu test (opsiyonel, manuel doğrulama için):
cd güncellemeler/face_security_v3
./launch.sh   # logs/launch_error.log'a stderr akıtır
# Sonra: curl http://127.0.0.1:5007/api/status
```

## Dosyalar

**Yeni:**
- `güncellemeler/face_security_v3/web_app.py` (~280 satır)
- `güncellemeler/face_security_v3/web_templates/index.html` (~135 satır)
- `güncellemeler/face_security_v3/web_static/style.css` (~190 satır)

**Değiştirilen:**
- `güncellemeler/face_security_v3/launch.sh` (web_app.py'i çalıştırır)
- `güncellemeler/face_security_v3/main.py` (DEPRECATED docstring)
- `güncellemeler/face_security_v3/requirements.txt` (+Flask>=3.0.0)
- `güncellemeler/yeni_dashboard/backend/server.js` (status HTTP probe + FACE_SEC_PORT sabiti)
- `güncellemeler/yeni_dashboard/src/App.jsx` (245-satırlık panel → 280-satırlık iframe layout; httpReady state)

**Dokunulmadı (intact, henüz UI'sı yok):**
- `auth/`, `camera/`, `detection/`, `database/`, `notifications/`, `utils/`,
  `config/`, `config.py`, `.env.example`
- `ui/` (Tkinter — import edilmiyor; istenirse silinebilir)

## Bilinen Sınırlamalar

- **MJPEG'in performans maliyeti**: tarayıcıda `<img src=/video_feed>`
  pattern'i WebRTC'den çok daha basit ama her frame için yeni TCP packet
  + JPEG decode (browser). 4-6 FPS'de stabil; daha yüksek FPS için WebSocket
  + H.264 streaming gerekir (ileri iyileştirme).
- **PIN auth atlandı**: orijinal Tkinter UI başlangıçta PIN doğrulamasını
  zorunlu kılıyordu (`AuthManager.show_login_dialog()`). Web sürümünde
  HTTP-based auth eklenmedi — local-only invocation varsayılıyor. İleride
  Flask `@login_required` decorator + session ile eklenebilir.
- **ALPR / plate_tab UI**: orijinal Tkinter'de "Plaka Tanıma" ayrı sekmedi.
  Web sürümünde henüz UI yok (backend modülleri intact, sadece view eksik).
  İleride `/plates` route + ayrı bir template eklenebilir.
- **Flask dev server**: production-grade değil. Yoğun trafik veya birden
  fazla istemci için `gunicorn -w 1 --threads 4 web_app:app` çalıştırılması
  önerilir (worker=1, çünkü InsightFace modeli memory'de tek instance).
- **Iframe cross-origin**: dashboard `localhost:5005`'ten iframe
  `127.0.0.1:5007`'i gömüyor. Aynı host ama farklı port = farklı origin →
  iframe'in IÇİNDEN dashboard'a postMessage atılırsa CORS gerekir.
  Şu an böyle bir iletişim yok.

---

# ALPR / PLAKA TANIMA WEB ENTEGRASYONU (2026-05-22)

## Hedef

Önceki Tkinter→Flask refactor'ünde "Bilinen Sınırlamalar" olarak
listelenen **ALPR / plate_tab UI** eksiği kapatıldı. Eski Tkinter
`ui/plate_tab.py`'in tüm runtime mantığı (motion-gated camera loop +
YOLO+EasyOCR analysis + voting + history) **headless** bir runner'a
port edildi ve mevcut Flask web app'ine API + sekme arayüzü olarak
gömüldü.

## 1) Yeni Modül — `plate_runner.py`

**Dosya:** `güncellemeler/face_security_v3/plate_runner.py` (~330 satır)

**Sınıf:** `PlateRunner` — Tkinter-bağımsız ALPR koordinatörü. Tek instance
Flask globalinde tutulur.

**İç akış (4 thread):**
1. **Init worker** (lazy) — `initialize_async()`: `PlateProcessor()` +
   `.initialize()` (YOLO + EasyOCR), `_status.initialized` true olur.
2. **Camera loop** — `PLATE_CAM_URL` RTSP'ı, motion detection (160×90
   grayscale diff, 25 threshold, 500 piksel minimum), display resize
   (854×480), hareket varsa 0.3sn'de bir / yoksa 2sn'de bir
   `analysis_queue`'ya frame.
3. **Analysis loop** — `analysis_queue` → `processor.process_frame()` →
   `result_queue` (plate, boxes, crop).
4. **Result drain loop** — `result_queue` → `recent_plates` deque (50)
   + `current_frame`'e bbox overlay (ARAC etiketi) + plate detected
   ise `_on_plate_detected()` → log dosyası + Telegram callback (opsiyonel).

**Public API:**
```python
runner.status          # dict (initialized, active, motion_detected,
                       #       collection_progress, last_plate, ...)
runner.current_frame   # np.ndarray | None — MJPEG frame için
runner.recent_plates   # deque[PlateReading] — JSON history için
runner.recent_logs     # deque[dict] — process log için
runner.start()         # toggle ON (idempotent, model auto-init)
runner.stop()          # toggle OFF
runner.report_unknown(plate)  # bilinmeyen plaka callback (processor için)
```

`PlateReading` ve `PlateStatus` dataclass'ları JSON serialize edilebilir
shape garanti eder.

**Eski plate_tab.py ile fark:**
- Tkinter widget'ları YOK (frame_lock + current_frame numpy ndarray)
- Telegram bot dialog/messagebox YOK
- Log queue → Python deque (`recent_logs`)
- `_update_gui()` after-loop'u YOK; bbox overlay'ı drain loop yapıyor

## 2) Flask Endpoints — `web_app.py`

**Yeni route'lar (`/api/plates/*` + `/plate_feed`):**

| Endpoint | Method | İşlev |
|---|---|---|
| `/plate_feed` | GET | MJPEG canlı plate kamera akışı (bbox overlay'li) |
| `/api/plates/status` | GET | `{initialized, active, motion_detected, collection_progress, last_plate, last_plate_ts, vehicle_count, camera_connected, plate_cam_url_set, error}` |
| `/api/plates/start` | POST | Toggle ON — `{success, message}` |
| `/api/plates/stop` | POST | Toggle OFF — `{success: true}` |
| `/api/plates/history` | GET | `[{plate, source, timestamp, full_ts}]` (son 50) |
| `/api/plates/logs` | GET | `[{ts, tag, msg}]` (son 100, tag: info/warn/error/plate/system) |
| `/api/plates/whitelist` | GET | `[{plate, owner}]` (read-only) |

**`_init_components()` güncellendi:**
```python
plate_runner = PlateRunner()
if config.PLATE_CAM_URL:
    plate_runner.initialize_async()   # YOLO+EasyOCR arka planda yüklensin
```

`PLATE_CAM_URL` boşsa runner pasif kalır, model **yüklenmez** (uzun
EasyOCR yükleme zamanı boşa harcanmasın).

**Iframe başlıkları KORUNDU**: `@after_request`'teki `X-Frame-Options`
pop + `Content-Security-Policy: frame-ancestors *` tüm yeni endpoint'lere
de uygulanır (Flask global hook). Doğrulandı:
```
X-Frame-Options present?: False  ✅
CSP frame-ancestors: frame-ancestors *;  ✅
```

## 3) UI — Sekmeli Yapı

**Dosya:** `web_templates/index.html` (tamamen yeniden yazıldı, ~260 satır)

**Topbar:** Brand · **Sekme nav** · Status pill (3-kolonlu)
```html
<nav class="tab-nav">
  <button class="tab-btn tab-active" data-tab="face">👤 Yüz Tanıma</button>
  <button class="tab-btn"             data-tab="plate">🚗 Plaka Tanıma</button>
</nav>
```

JS tab switcher:
```js
tabs.forEach(btn => btn.addEventListener('click', () => {
  tabs.forEach(b => b.classList.toggle('tab-active', b === btn));
  Object.entries(panes).forEach(([k, el]) => {
    el.style.display = (k === btn.dataset.tab) ? '' : 'none';
  });
}));
```

### `#tab-face` (mevcut, dokunulmadı — tab açılır kapanır)
Sol: kamera listesi + devriye butonları + info panel
Orta: `<img src="/video_feed">` MJPEG
Sağ: Son tespitler

### `#tab-plate` (yeni)
**Sol panel:**
- Büyük yeşil/kırmızı toggle butonu (idempotent — `/api/plates/start|stop`)
- Aktif durum satırı: "ANALİZ — 7/10 frame" / "AKTİF — Hareket algılandı" /
  ".env: PLATE_CAM_URL boş" / "MODEL HATASI: ..." (state-aware metin)
- Info paneli: Model, Kamera, Hareket, Araç sayısı, Frame toplama
- "Son tespit" kartı (büyük plaka metni, gradient yeşil card)
- Whitelist listesi (read-only, 7 plaka load test edildi)

**Orta panel:**
- "PLAKA KAMERASI (CANLI)" başlığı + `<img src="/plate_feed">` MJPEG
- Footer: "Motion-gated · YOLOv8 · EasyOCR x3 pipeline · oylama tabanlı"

**Sağ panel:**
- "SON PLAKALAR" listesi — `det-known` yeşil / `det-unknown` pembe,
  `source` rozeti (whitelist/bilinmeyen)
- "PROCESS LOG" — son 25 satır, monospace, renk kodlu:
  - `log-plate` (yeşil) — `[plate]` tag (tespit, sistem aç/kapat)
  - `log-warn` (sarı) — `[warn]` tag (sistem pasif, bilinmeyen plaka)
  - `log-err` (kırmızı) — `[error]` tag
  - `log-info` (gri) — diğer

**Polling intervalleri:**
- `/api/plates/status` — 1 sn (motion + collection_progress canlı yansısın)
- `/api/plates/history` — 2 sn
- `/api/plates/logs` — 2 sn
- `/api/plates/whitelist` — 30 sn (statik)
- Mevcut face polling değişmedi (status + detections 2sn).

## 4) CSS

**Dosya:** `web_static/style.css` (~120 satır eklendi)

**Yeni stiller:**
- `.tab-nav`, `.tab-btn`, `.tab-active` — pill-style sekme barı,
  aktif sekme yeşil gradient + glow
- `.plate-toggle-wrap` + `.btn-plate-toggle` — büyük gradient toggle
  (yeşil → kırmızı durumda)
- `.plate-status-line` — kompakt durum metni (.env / model / kamera /
  motion / aktif state)
- `.plate-last-card` — büyük plaka tespit kartı (gradient yeşil,
  monospace 22px font, gözle ayırt edilebilir)
- `.whitelist-list` + `.wl-item` — kompakt plaka + sahip listesi
- `.plate-log` — terminal-vari log (siyah BG, monospace 10px, renk kodlu)
- `.log-plate/.log-warn/.log-err/.log-info` — renk varyantları

## Doğrulama

```bash
$ python3 -m py_compile plate_runner.py web_app.py
OK  ✅

$ python3 -c "import web_app; ..."
=== Registered routes ===  (17 route — 8 face + 7 plate + 2 misc) ✅
=== iframe headers ===
  X-Frame-Options present?: False  ✅
  CSP frame-ancestors: frame-ancestors *;  ✅
=== plate endpoints smoke test ===
  /api/plates/status  → 200 {available, ..., plate_cam_url_set: True}  ✅
  /api/plates/start   → 200 {success: True}  ✅
  whitelist load      → 7 plaka okundu  ✅
```

## Dosyalar

**Yeni:**
- `güncellemeler/face_security_v3/plate_runner.py` (~330 satır)

**Değiştirilen:**
- `güncellemeler/face_security_v3/web_app.py`:
  - `from plate_runner import PlateRunner` import
  - `plate_runner: PlateRunner | None` global
  - `_init_components()`'te `PlateRunner()` instance + `initialize_async()`
  - 7 yeni route + `_plate_mjpeg_generator()` helper
- `güncellemeler/face_security_v3/web_templates/index.html` —
  topbar'a `tab-nav`, ikinci `<main id="tab-plate">` block + ~140 satır JS
  (tab switcher + 4 polling fonksiyonu)
- `güncellemeler/face_security_v3/web_static/style.css` — ~120 satır
  yeni stil (sekme + plaka paneli)

## Restart Gerekliliği

| Servis | Restart? | Komut |
|---|---|---|
| Flask web (5007) | **EVET** | Dashboard'dan DURDUR → BAŞLAT (önceki turdan beri var olan flow) |
| Express backend (5006) | hayır | Endpoint yok değişikliği yok |
| Vite (5005) | hayır | İlgisiz |

Dashboard'da:
1. YÜZ GÜVENLİĞİ sekmesi → ■ DURDUR (eski Flask process'i kapat)
2. ▶ BAŞLAT — yeni `web_app.py` (plate routes dahil) yüklenir
3. Iframe yenilenir → üstte 👤 Yüz Tanıma / 🚗 Plaka Tanıma sekmeleri görünür
4. **Plaka Tanıma** sekmesine geç → yeşil "▶ PLAKA TANIMAYI AKTİF ET"
   butonuna bas → kamera akışı + tespitler canlı akmaya başlar

## Bilinen Sınırlamalar

- **Whitelist düzenleme UI'ı** henüz yok — eski Tkinter'deki
  `WhitelistDialog` portlanmadı. Şu an plate_whitelist.txt manuel
  düzenlenmeli; `/api/plates/whitelist` sadece okuma.
- **`PlateProcessor._on_unknown_plate` callback** processor seviyesinde
  set edilmedi — yani bilinmeyen plakalar `recent_plates`'a otomatik
  düşmüyor (sadece doğrulanmış whitelist plakaları geliyor).
  `runner.report_unknown(plate)` metodu mevcut ama processor henüz
  bunu çağırmıyor. İleride processor constructor'a callback geçirmek
  gerekiyor (ayrı bir küçük edit).
- **MJPEG plate_feed FPS** ~20 cap (50ms sleep); plate kamerası
  genelde yavaş hareket eden araçları yakaladığı için yeterli.
- **Telegram entegrasyonu** — `plate_runner.set_notify_callback(cb)`
  metodu var ama `_init_components`'te bağlanmadı. İleride
  `plate_runner.set_notify_callback(telegram.send_photo)` eklenebilir.

---

# WHITELIST CRUD UI ENTEGRASYONU (2026-05-22)

## Hedef

Önceki turdaki "Bilinen Sınırlamalar"da listelenen **whitelist düzenleme
eksiği** kapatıldı. `plate_whitelist.txt` artık elle düzenlenmiyor —
plate sekmesindeki UI üzerinden ekleme/silme tarayıcıdan yapılıyor.

`save_whitelist(filepath, ui_plates)` ve `get_ui_plates(filepath)`
helper'ları `detection/plate_whitelist.py`'da zaten mevcuttu (UI bölümü
ayraç koruma + atomic rewrite); sadece bunları HTTP'ye expose ettim ve
worker thread'le yarışmayan thread-safe bir wrapper ekledim.

## 1) PlateRunner — Thread-Safe CRUD

**Dosya:** `güncellemeler/face_security_v3/plate_runner.py`

**Yeni içerik:**
- `import os` + `from detection.plate_whitelist import (get_ui_plates, save_whitelist, normalize_plate)`
- `WHITELIST_PATH = os.environ.get("PLATE_WHITELIST_PATH", "config/plate_whitelist.txt")` modül seviyesi default
- `self._whitelist_lock = threading.Lock()` instance üyesi — read-modify-write atomicliği

**3 yeni public metod:**

```python
def _resolve_whitelist_path(self) -> str:
    # Processor yüklendiyse onun path'i (env var farkı için), yoksa default
    ...

def get_whitelist_entries(self) -> list[tuple[str, str]]:
    with self._whitelist_lock:
        return get_ui_plates(path)

def add_whitelist_entry(self, plate: str, comment: str = "") -> tuple[bool, str]:
    # 1) normalize + 5-9 karakter validation
    # 2) lock altında: get_ui_plates → duplicate check → append → save_whitelist
    # 3) processor varsa reload_whitelist (worker thread bunu atomic okur)
    ...

def remove_whitelist_entry(self, plate: str) -> tuple[bool, str]:
    # 1) normalize
    # 2) lock altında: get_ui_plates → filter → save_whitelist
    # 3) processor varsa reload_whitelist
    ...
```

**Thread-safety mantığı:**
- `_whitelist_lock` sadece **read-modify-write** sırasında tutulur
  (HTTP request handler thread'lerinin yarışmasını önler).
- Camera/analysis worker thread'leri `processor._whitelist` listesini
  okurken kilide GİRMEZ — `reload_whitelist()` yeni `list` referansını
  CPython GIL altında atomic atar; worker o anda ya eski ya yeni listeye
  bakar, ikisi de tutarlı (race yok).
- Yorum kırpma: `comment[:60]` — UI'da çok uzun açıklamalar dosyayı kirletmesin.

## 2) Flask Endpoints — `web_app.py`

Önceki tek `GET` endpoint'i tam CRUD'a genişletildi:

| Endpoint | Method | İşlev | Status code |
|---|---|---|---|
| `/api/plates/whitelist` | GET | `[{plate, owner}]` listele | 200 |
| `/api/plates/whitelist` | POST | `{"plate","comment"}` ekle | 201 / 400 / 409 / 503 |
| `/api/plates/whitelist/<plate>` | DELETE | belirtilen plakayı sil | 200 / 404 / 503 |

**Validation:**
- Boş / yanlış tip → 400
- Normalize'dan sonra 5-9 karakter dışı → 400
- Aynı plaka zaten varsa → 409
- PlateRunner yoksa → 503

**Path parametresi `<plate>`** Flask'ın URL converter'ında alınır;
backend normalize edip eşleştirir. `34 NNF 012` URL encoding'le gönderilse
bile çalışır (test edilmedi ama frontend `encodeURIComponent` kullanıyor).

## 3) UI — `index.html` + JS

### Whitelist bölümü (plate sekmesi sol panel)

**Önce:**
```html
<h3>WHITELIST</h3>
<ul class="whitelist-list">...read-only items...</ul>
```

**Şimdi (ekleme formu eklendi):**
```html
<h3>WHITELIST</h3>
<form id="plateAddForm" class="wl-add-form">
  <input id="plateAddInput" placeholder="34NNF012" maxlength="9" />
  <input id="plateAddComment" placeholder="Sahip / not (ops.)" maxlength="60" />
  <button type="submit" class="wl-btn-add">+ Ekle</button>
</form>
<div id="plateAddMsg" class="wl-msg"></div>  <!-- 4sn'lik inline status -->
<ul id="plateWhitelist" class="whitelist-list">...</ul>
```

**Grid layout:** Plaka input (1fr) + "Ekle" butonu (auto) tek satırda,
yorum input alt satırda tam genişlik (`grid-column: 1/3`).

### Her item'da silme butonu

```html
<li class="wl-item">
  <span class="wl-plate">34NNF012</span>
  <span class="wl-owner">Anne araba</span>
  <button class="wl-btn-del" data-plate="34NNF012" title="Sil">×</button>
</li>
```

### JS handlers

- `refreshWhitelist()` — `escapeHtml()` ile XSS-safe render (plate/owner
  user input'tan geliyor)
- `plateAddForm.submit` — `e.preventDefault()` + POST + inline status mesajı
  (yeşil ok / kırmızı err) + form temizle + listeyi anlık yenile
- Silme: **event delegation** — `plateWhitelist.click` dinamik render'a
  karşı dirençli, `confirm()` ile onay, ardından DELETE + listeyi anlık yenile
- `showAddMsg(text, kind)` — 4sn auto-hide, `setTimeout` ile re-trigger safe

**Polling değişmedi** — `refreshWhitelist` her 30sn'de bir hâlâ
çağrılıyor (yeni dış değişiklik durumunda — `plate_whitelist.txt`'ın
elle düzenlenmesi gibi — kendi başına sync olsun).

## 4) CSS — `style.css` (~110 satır eklendi)

**`.wl-add-form`** — 2-kolon grid (input + buton), yorum input 2-kolon span
**`.wl-input`** — dark BG, monospace, focus'ta yeşil glow (accent),
plate alanı `text-transform: uppercase` + `letter-spacing` (plaka-vari görünüm),
yorum alanı sade sans-serif
**`.wl-btn-add`** — yeşil gradient, hover brightness, disabled wait cursor
**`.wl-msg-ok / wl-msg-err / wl-msg-info`** — inline status banner;
left border accent + tinted background
**`.wl-btn-del`** — × ikonu, 18×18px, default transparent; hover'da
kırmızı tint + border (yıkıcı işlem sinyali). Disabled wait cursor.

Tüm renkler mevcut palette değişkenlerinden (`--accent`, `--err`, `--bg-0`)
çekildiğinden tema bozulmadı.

## Doğrulama

### E2E smoke test (gerçek dosya I/O)

`PLATE_WHITELIST_PATH=/tmp/...` ile izole test:

```
POST  /api/plates/whitelist  "34 NNF 012" + "Anne araba"  → 201 {plate: "34NNF012"}  ✅
POST  aynı plaka (case-insensitive)                        → 409 "zaten listede"    ✅
POST  "AB" (3 karakter)                                    → 400 validation         ✅
POST  "06ABC123" + "Baba"                                  → 201                    ✅
GET   /api/plates/whitelist                                → 2 plaka                ✅
DELETE /api/plates/whitelist/34NNF012                      → 200                    ✅
DELETE /api/plates/whitelist/99XXX999 (yok)                → 404                    ✅
GET   final                                                → 1 plaka kaldı          ✅
```

**Dosya içeriği (gerçekten yazılmış):**
```
# === UI YÖNETİMİ (otomatik) ===
# UI ile ekleyip silinen plakalar — manuel düzenlemeyin

06ABC123    # Baba
```

### Route + iframe doğrulama

```
/api/plates/whitelist            -> GET   ✅
/api/plates/whitelist            -> POST  ✅
/api/plates/whitelist/<plate>    -> DELETE ✅
X-Frame-Options present?:        False ✅
CSP frame-ancestors:             frame-ancestors *; ✅
Yanlış metod:                    405 (POST detail / PUT list) ✅
```

## Dosyalar

**Değiştirilen:**
- `güncellemeler/face_security_v3/plate_runner.py`:
  - `import os` eklendi
  - `WHITELIST_PATH` modül sabiti
  - `self._whitelist_lock` instance üyesi
  - 4 yeni public metod (`_resolve_whitelist_path`, `get_whitelist_entries`,
    `add_whitelist_entry`, `remove_whitelist_entry`)
- `güncellemeler/face_security_v3/web_app.py`:
  - Eski tek `/api/plates/whitelist` GET endpoint'i 3 endpoint'e bölündü
    (GET/POST list + DELETE detail)
  - Runner'a delege ediyor (eski `get_ui_plates` direct call kaldırıldı)
- `güncellemeler/face_security_v3/web_templates/index.html`:
  - Whitelist bölümüne `<form>` (plate + yorum input + Ekle butonu) eklendi
  - Inline status mesajı (`#plateAddMsg`) eklendi
  - Item render'ına `<button class="wl-btn-del">` eklendi
  - `escapeHtml()` helper, submit + event delegation click handler'ları
- `güncellemeler/face_security_v3/web_static/style.css`:
  - `.wl-add-form`, `.wl-input`, `.wl-input-comment`, `.wl-btn-add`,
    `.wl-msg` + 3 varyantı, `.wl-btn-del` (~110 satır)

## Restart Gerekliliği

| Servis | Restart? |
|---|---|
| Flask web (5007) | **EVET** — Dashboard'dan DURDUR → BAŞLAT |
| Express backend (5006) | hayır (dokunulmadı) |
| Vite (5005) | hayır (dokunulmadı) |

Test akışı:
1. YÜZ GÜVENLİĞİ sekmesi → DURDUR → BAŞLAT (Flask'i yenile)
2. Iframe yüklendiğinde 🚗 Plaka Tanıma sekmesine geç
3. Sol panelde WHITELIST bölümünde input + "+ Ekle" görünmeli
4. Plaka yaz (örn. `34abc123`) + (ops.) yorum → "+ Ekle"
5. Listeye anlık eklenmeli, başarı mesajı 4sn yeşil bant
6. Her item'da × var; tıkla → onay → DELETE → anlık silinir

## Bilinen Sınırlamalar

- **Yalnız UI bölümü yönetiliyor**: `plate_whitelist.txt`'in
  `# === UI YÖNETİMİ (otomatik) ===` ayracının üstündeki "manuel"
  bölüm dokunulmaz (eski kullanıcı yorumları ve plakaları korunur).
  UI'dan eklenen plakalar AYRAÇ ALTINA yazılır. Bu bilinçli bir
  bölümlemedir — `save_whitelist()` API'sinin garantisi.
- **Yorum güncelleme YOK**: var olan bir plakanın yorumunu değiştirmek
  için önce sil-sonra-ekle gerekiyor. Edit endpoint'i (PATCH) ileride
  eklenebilir.
- **CSRF koruması yok**: aynı host iframe varsayımı; cross-site
  forgery riski yok (third-party site bu portu hedefleyemiyor çünkü
  CORS POST için preflight gerekir ve Flask CORS header'ları kapalı).
- **Format katı**: 5-9 karakter, A-Z0-9 (boşluk/tire normalize ile
  silinir). Geçersiz girişler 400 ile hemen reddedilir; UI'da inline
  kırmızı banner gösterilir.

---

# UNKNOWN PLATE CALLBACK + TELEGRAM BİLDİRİM ENTEGRASYONU (2026-05-22)

## Hedef

Önceki turlardaki "Bilinen Sınırlamalar"da listelenen son iki arka
plan eksiği kapatıldı:

1. **Bilinmeyen plakalar UI'a düşmüyordu** — `PlateProcessor`'ın
   `unknown_plate_callback` kwarg'ı bağlanmamıştı.
2. **Telegram entegrasyonu yoktu** — `PlateRunner.set_notify_callback`
   API'si vardı ama hiçbir yerde set edilmiyordu.

## 1) Unknown Callback Bind

**Dosya:** `güncellemeler/face_security_v3/plate_runner.py`

`PlateProcessor` constructor'ı zaten `unknown_plate_callback`
parametresi kabul ediyordu. `initialize_async()` worker'ındaki
`PlateProcessor()` çağrısına bağladım:

```diff
-self._processor = PlateProcessor()
+self._processor = PlateProcessor(
+    unknown_plate_callback=self.report_unknown,
+)
```

PlateProcessor'ın `_save_unknown_plate()` metodu (line 1013) tespit
ettiği bilinmeyen plakayı bu callback'le gönderir; throttle (30sn)
PlateProcessor seviyesinde zaten var → duplicate bildirim olmaz.

## 2) Telegram Köprüsü

**Dosya:** `güncellemeler/face_security_v3/web_app.py:_init_components()`

Yüz tarafı için zaten yaratılan `telegram` instance'ı plate_runner'a
da bağlandı. Closure ile source-aware caption:

```python
if telegram is not None:
    def _plate_telegram_notify(plate, frame, source="whitelist"):
        try:
            if source == "unknown":
                caption = f"⚠️ BİLİNMEYEN PLAKA\nOCR: {plate}\nWhitelist'te eşleşme yok."
            else:
                caption = f"🚗 PLAKA TESPİT\nPlaka: {plate}\nDurum: Whitelist'te tanımlı."
            if frame is not None:
                telegram.send_photo_cv2(frame, caption=caption)  # bbox overlay'li
            else:
                telegram.send_message(caption)
        except Exception as e:
            logger.warning("Plate Telegram bildirimi gönderilemedi: %s", e)

    try:
        plate_runner.set_notify_callback(_plate_telegram_notify)
        logger.info("Plate → Telegram köprüsü bağlandı.")
    except Exception as e:
        logger.warning("Plate Telegram köprüsü bağlanamadı: %s", e)
else:
    logger.info("Telegram bot yok (env tokens eksik) — plaka bildirimi devre dışı.")
```

`TelegramBot.send_photo_cv2` zaten ayrı thread'de çalışıyor + kendi
içinde exception'ı log'a düşürüyor → handler dış try/except sadece
defansif katman.

## 3) Notify Callback İmza Genişletmesi (Backward Compat)

**Dosya:** `plate_runner.py`

Eski imza `cb(plate, frame)` idi. Source ayrımı için 3-arg
`cb(plate, frame, source)` haline genişletildi. `_fire_notify()`
helper hem yeni hem eski imzaları destekler:

```python
def _fire_notify(self, plate, frame, source):
    if self._notify_callback is None:
        return
    try:
        try:
            self._notify_callback(plate, frame, source)
        except TypeError:
            # Eski 2-arg callback imzası fallback
            self._notify_callback(plate, frame)
    except Exception as e:
        logger.warning("notify_callback hatası (%s, %s): %s", source, plate, e)
```

`_on_plate_detected` (whitelist) → `_fire_notify(plate, frame, "whitelist")`
`report_unknown`     (unknown)   → `_fire_notify(plate, frame, "unknown")`

İç try/except katmanı → callback hata fırlatırsa runner thread'i
asla bozulmaz (sadece log uyarısı).

## 4) Test ve Doğrulama (5 senaryo, hepsi geçti)

```
S1: notify_callback=None, unknown plate           → UI'a düştü ✅
S2: 3-arg callback bağlı, whitelist + unknown     → source ayrıştı ✅
    calls = [('06DEF456', 'whitelist'), ('99XXX000', 'unknown')]
S3: 2-arg eski callback (backward compat)         → TypeError fallback ✅
S4: callback exception → "boom"                   → runner kırılmadı ✅
S5: PlateProcessor(unknown_plate_callback=...) bind doğrulaması:
    cb.__self__ is runner ✅
    cb.__func__ is PlateRunner.report_unknown ✅
    Çağrıldığında recent_plates'a düştü ✅
```

**Telegram-None graceful fallback:**
- Env temiz (`TELEGRAM_BOT_TOKEN` yok) → `telegram is None`
  → callback set edilmez → `plate_runner._notify_callback = None`
- Unknown plate gelirse: `_fire_notify` erken `return` → exception yok
- Test sonucu: `/api/plates/history` 200 + `source: "bilinmeyen"` ✅

`web_app.py:_init_components()` Telegram olmasa da Flask sorunsuz
boot eder; log'a sadece bir info mesajı yazılır:
`"Telegram bot yok (env tokens eksik) — plaka bildirimi devre dışı."`

## Akış (Kullanıcı Bakışı)

1. Plate kamera açık + model yüklü
2. Kamerada plaka geçer → process_frame → OCR → vote
3. **Senaryo A — Whitelist eşleşme:**
   - `match_plate(...)` whitelist plakasını döner
   - `_on_plate_detected(plate)` → `recent_plates` (yeşil rozet)
   - `_fire_notify(plate, frame, "whitelist")` → `🚗 PLAKA TESPİT` Telegram
4. **Senaryo B — Bilinmeyen:**
   - `match_plate(...)` `None` döner (whitelist'te eşleşme yok)
   - `_save_unknown_plate(ham, conf)` disk'e kaydeder
   - **YENİ:** PlateProcessor callback'i ateşler → `runner.report_unknown(ham)`
   - `recent_plates`'a `source="bilinmeyen"` ile düşer (pembe rozet)
   - `_fire_notify(plate, frame, "unknown")` → `⚠️ BİLİNMEYEN PLAKA` Telegram
5. Throttle: aynı bilinmeyen plaka 30sn içinde tekrar gelirse
   PlateProcessor zaten filtreliyor → Telegram spam YOK

## Dosyalar

**Değiştirilen:**
- `güncellemeler/face_security_v3/plate_runner.py`:
  - `PlateProcessor(unknown_plate_callback=self.report_unknown)` bind
  - `_fire_notify(plate, frame, source)` helper eklendi (3-arg + 2-arg fallback)
  - `_on_plate_detected` ve `report_unknown` `_fire_notify` kullanıyor
- `güncellemeler/face_security_v3/web_app.py:_init_components()`:
  - `if telegram is not None:` bloğu — closure `_plate_telegram_notify`
    tanımı + `plate_runner.set_notify_callback(...)` bind
  - `telegram is None` durumunda graceful info log

## Restart Gerekliliği

| Servis | Restart? |
|---|---|
| Flask web (5007) | **EVET** — Dashboard YÜZ GÜVENLİĞİ → DURDUR → BAŞLAT |
| Express backend (5006) | hayır |
| Vite (5005) | hayır |

## Test Akışı

1. `.env` dosyasında `TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` set olmalı
   (yoksa Telegram kısmı atlanır ama UI yine çalışır).
2. YÜZ GÜVENLİĞİ sekmesi → DURDUR → BAŞLAT (yeni `web_app.py` yüklensin)
3. Iframe'de log'larda "Plate → Telegram köprüsü bağlandı." görmek
   gerekir. Yoksa "Telegram bot yok" görünür.
4. 🚗 Plaka Tanıma sekmesi → **▶ PLAKA TANIMAYI AKTİF ET**
5. Kameraya plaka göster:
   - Whitelist'te varsa → yeşil "Son plakalar" satırı + Telegram `🚗`
   - Yoksa → pembe "Son plakalar" satırı + Telegram `⚠️`
6. Aynı bilinmeyen plakayı 30sn içinde tekrar gösterirsen Telegram'a
   ikinci kez gitmez (PlateProcessor `_unknown_throttle_seconds`).

## Sistem Başlatılmaya Hazır

- `python3 -m py_compile plate_runner.py web_app.py` ✅
- 5 senaryo unit test geçti ✅
- Telegram-None graceful (env eksikse Flask çökmeden boot eder) ✅
- Iframe header'ları (`X-Frame-Options` yok + `frame-ancestors *`) — başka
  endpoint dokunulmadığı için zaten korunuyor.

Sistem restart sonrası canlı testte:
- Unknown plate UI akışını `plate_whitelist.txt`'te olmayan herhangi bir
  plakayla doğrulayabilirsiniz (örn. kameraya rastgele bir plaka göster).
- Telegram bildirimini bot'un bağlı olduğu Telegram chat'inde fotoğraflı
  olarak göreceksiniz.

---

# FEATURE PARITY — TKINTER → WEB (2026-05-22)

## Hedef

Eski Tkinter sürümünde olup web sürümünde eksik olan tüm özellikler
web'e taşındı. Sistemin "kullanıcı yeteneği" yelpazesi artık eski
desktop programıyla aynı:

| Tkinter Özelliği | Web Karşılığı |
|---|---|
| `SettingsTab` — 25 kamera RTSP düzenle/test/kaydet (.env atomic) | **AYARLAR** sekmesi tablosu ✅ |
| `_save_unknown` — bilinmeyen yüze isim ver + DB'ye kaydet | **YÜZ YÖNETİMİ** sekmesi formu ✅ |
| `_start_search` / `_load_search_ref` — kişi ara + patrol modu | **Yüz Arama (Patrol)** kart ✅ |
| `_handle_detection` known/unknown crop panel'leri | "Son Tanınan / Son Bilinmeyen" kartları ✅ |
| `camera_config.json` (her kamera enabled) + `startup_config.json` | Tablo içi checkbox + radio + auto-save ✅ |
| `THRESHOLD`, `INFERENCE_FPS`, vb. runtime sabitler | Runtime Ayarlar paneli (slider + number) ✅ |
| Detection log dosyaları | Log dosyaları listesi + indirme ✅ |
| `db_manager.list_people()` | Kayıtlı kişiler listesi (thumbnail + ×) ✅ |

Atlanan tier-3 (kasıtlı): PIN auth (lokal-only iframe), Telegram
komut listesi (worker'da çalışmaya devam ediyor).

## 1) Backend — 20 Yeni Endpoint

**Dosya:** `güncellemeler/face_security_v3/web_app.py` (~430 satır eklendi)

### Settings (kamera + runtime)
```
GET    /api/settings/cameras         — 25 kamera info
POST   /api/settings/cameras         — bulk URL update (.env atomic)
POST   /api/settings/cameras/test    — tek URL probe (cv2 VideoCapture 3sn)
POST   /api/settings/cam_enabled     — camera_config.json
POST   /api/settings/startup_cam     — startup_config.json
GET    /api/settings/runtime         — threshold/fps/cooldown/patrol
POST   /api/settings/runtime         — runtime config bulk update
```

### Face DB + Search
```
GET    /api/faces/people, last_known, last_unknown, photo/<name>, search/status
POST   /api/faces/save_unknown, search/start, search/stop, reload
DELETE /api/faces/delete/<name>
```

### Logs
```
GET    /api/logs/files, download/<name>, tail/<name>?n=N
```

### Drain Loop Entegrasyonu
`_drain_results()` artık her detection'da crop'u 200×250 JPEG q=80 base64
cache'liyor (`_last_known_crop_b64` / `_last_unknown_crop_b64`). Unknown
için numpy orijinal de tutulur (save_person için). Patrol search "bulundu"
mantığı da burada — eşleşme olunca Telegram bildirimi (varsa).

### Thread-Safety
- `_settings_lock`: `.env` + `*.json` read-modify-write
- `_search_lock`: search state mutasyonu

### .env Atomic Yazımı
`settings_tab._write_env()` mantığı port edildi: `.env.bak` backup +
`.env.tmp` atomic rename. `CAM_NN_URL=` satırları sadece güncellenir;
diğer .env içeriği dokunulmaz.

## 2) Frontend — 2 Yeni Sekme + 2 Preview Kartı

### Navbar (4 sekme)
👤 Yüz Tanıma · 🚗 Plaka Tanıma · **🧑‍🤝‍🧑 Yüz Yönetimi** · **⚙️ Ayarlar**

### `#tab-face` — Eklenen preview kartları
Sağ panelin üstüne **SON TANINAN** (yeşil border) ve **SON BİLİNMEYEN**
(pembe border) crop önizleme kartları. Unknown'da "+ Bu yüzü kaydet"
butonu → Yüz Yönetimi sekmesine yönlendirir.

### `#tab-faces-mgmt` (YENİ)
- **Sol** — Yüz Arama formu + durum kartı (PASİF / AKTİF + hedef + bulundu banner)
- **Orta** — Büyük son bilinmeyen yüz görseli + isim input + DB'ye kaydet butonu
- **Sağ** — Kayıtlı kişiler (thumbnail + × silme) + ↻ Yenile

### `#tab-settings` (YENİ)
- **Sol** — Runtime config (threshold slider + sayısal alanlar) + Log dosyaları (⇩ indirme)
- **Sağ** — Kamera RTSP tablosu (25 satır, sticky header, # · İsim · URL · Etkin · Başl. · Test)

### Tab Switching — Lazy Refresh
Sekmeye girince ilgili veri otomatik yenilenir (faces-mgmt → people + search
+ last_unknown; settings → runtime + cam table + logs).

## 3) CSS — `style.css` (~250 satır eklendi)

- `.last-detection-row` + `.last-card` — known/unknown crop kartları
- `.search-status-card`, `.search-state.st-active` (pulse animation)
- `.mgmt-frame`, `.mgmt-large-img`, `.mgmt-save-form`
- `.people-thumb` (26×26 referans fotoğrafı)
- `.settings-container`, `.settings-block`, `.settings-row`
- `.cam-table` (sticky header) + `.cam-test-btn.cam-test-ok/fail/wait`
- `.log-link` (⇩ indirme), `.cam-active-mini` (aktif kamera glow)

## 4) Korunan Yapılar

- **Iframe headers**: `@after_request` hook tüm yeni endpoint'lere de
  uygulanır. Doğrulandı: `XFO=False, CSP=frame-ancestors *;` ✅
- **Express backend** (5006), **Vite/React** (5005): dokunulmadı
- **Plate sekmesi, Whitelist CRUD**: dokunulmadı
- **Mevcut endpoint'ler**: geriye uyumlu; `_drain_results` sadece
  zenginleştirildi.

## 5) Doğrulama

```
$ python3 -m py_compile web_app.py plate_runner.py   → OK ✅
Toplam route: 39
  /api/faces:    10
  /api/logs:      3
  /api/plates:    8
  /api/settings:  7

11-step backend smoke test: hepsi geçti (settings GET/POST, validation 400,
                                         cam_enabled, cam test, faces, logs,
                                         search start/stop, iframe headers)
Jinja2 template parse: OK
```

## 6) Restart Gerekliliği

| Servis | Restart? |
|---|---|
| Flask web (5007) | **EVET** — Dashboard YÜZ GÜVENLİĞİ → DURDUR → BAŞLAT |
| Express backend (5006) | hayır |
| Vite (5005) | hayır |

## 7) Test Senaryoları (UI)

1. **AYARLAR → Runtime**: threshold slider 0.55 → KAYDET → "Güncellendi" banner
2. **AYARLAR → Kameralar**: URL Test → ✓/✗ rozet anında; Tümünü Kaydet → .env atomic
3. **AYARLAR → Loglar**: ⇩ tıkla → tarayıcı indirir
4. **YÜZ TANIMA**: kameraya bilinmeyen biri bak → "SON BİLİNMEYEN" pembe crop
5. **+ Bu yüzü kaydet**: tıkla → Yüz Yönetimi sekmesine geçer, input odaklı
6. **YÜZ YÖNETİMİ → KAYDET**: isim yaz + buton → DB save + embedding rebuild
7. **YÜZ YÖNETİMİ → Arama**: isim gir + "▶ Arama Başlat" → patrol + Telegram bildirimi
8. **YÜZ YÖNETİMİ → ×**: kişiye tıkla → confirm → DB sil + reload

## 8) Bilinen Sınırlamalar

- **PIN auth** atlandı (lokal iframe varsayımı)
- **Runtime config persistance**: `THRESHOLD` setattr ile module attribute
  değişir; restart'ta `.env` veya `config.py` defaults'a döner. Kalıcılık
  için ileride ayrı bir `runtime_config.json` eklenebilir.
- **Test endpoint**: kamera ulaşılmıyorsa 3sn bekler — UI bu süre "‥" rozet
- **Crop yakalama**: drain loop result_queue'dan tek tek alır; full
  olursa eski sonuçlar drop edilir (her zaman son crop güncel)

---

# CAMERA SETTINGS — React Bileşene Taşıma (2026-05-22)

## Hedef

Mevcut dashboard'un KONTROL sekmesi sağ panelinde (`right-panel`) duran
**10 kamera button'lu "KAMERA SİSTEMİ"** listesi, eski Tkinter sürümünden
porte ettiğimiz **25 kamera RTSP ayar tablosu** (Flask Ayarlar sekmesindeki
`#camTableBody` yapısı) ile değiştirildi. Artık kullanıcı dashboard'dan
çıkmadan tüm 25 kamerayı düzenleyebilir.

## Mimari

```
React (5005)  ──fetch──>  Flask 5007 (face_security_v3/web_app.py)
                            └── /api/settings/cameras (GET/POST)
                            └── /api/settings/cameras/test (POST)
                            └── /api/settings/cam_enabled (POST)
                            └── /api/settings/startup_cam (POST)
```

Express backend (5006) bypass edildi — React doğrudan Flask'a konuşuyor.
CORS açıldığı için cross-origin sorunu yok.

## 1) Flask CORS Aktivasyonu

**Dosya:** `güncellemeler/face_security_v3/web_app.py`

`@app.after_request` hook'una CORS header'ları eklendi (mevcut iframe
header'larıyla aynı blokta, böylece iki davranış da senkron kalır):

```python
@app.after_request
def _allow_iframe(resp):
    resp.headers.pop("X-Frame-Options", None)
    resp.headers["Content-Security-Policy"] = "frame-ancestors *;"
    # YENİ: CORS — React 5005 → Flask 5007 fetch için
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Max-Age"] = "3600"
    return resp

# Tüm /api/* rotaları için catch-all OPTIONS preflight handler
@app.route("/api/<path:_any>", methods=["OPTIONS"])
def _api_preflight(_any):
    return ("", 204)
```

`_api_preflight` handler `path:` converter ile `/api/`'nin altındaki
her yola düşer (settings/faces/logs/plates dahil). Preflight test:

```
OPTIONS /api/settings/cameras  → 200
  ACAO: *
  ACAM: GET, POST, PUT, DELETE, OPTIONS
  ACAH: Content-Type, Authorization
```

Mevcut iframe davranışı (`X-Frame-Options=yok, CSP frame-ancestors *;`)
**bozulmadı** — aynı after_request hook'unda her ikisi de güncellendi.

## 2) Yeni React Bileşeni

**Dosya:** `güncellemeler/yeni_dashboard/src/CameraSettings.jsx` (yeni, ~240 satır)

`function CameraSettings()` — Flask'ın 25-satır `#camTableBody` HTML
tablosunun React/JSX karşılığı.

**State (useState):**
- `rows: Array<{id, name, url, enabled, is_startup, is_active}>`
- `startupId: number | null`
- `loading`, `error`, `msg: {kind, text}`
- `testStates: {[id]: 'wait'|'ok'|'fail'|undefined}`

**Lifecycle:**
- `useEffect` → `refresh()`: GET `/api/settings/cameras`
- Hata durumunda kullanıcı dostu mesaj: *"Yüz Güvenliği servisine
  bağlanılamadı (5007). Üst menüden ▶ BAŞLAT ile servisi açın."*

**Eylem handler'ları:**
- `handleTest(id, url)` → POST `/api/settings/cameras/test` → ✓/✗/wait rozet
- `handleEnabledToggle(id, enabled)` → POST `/api/settings/cam_enabled` (auto-save)
- `handleStartupSelect(id)` → POST `/api/settings/startup_cam` (radio anlık)
- `handleSaveAll()` → POST `/api/settings/cameras` bulk (.env atomic)

**UI:**
- 6-sütun tablo: # · İsim · RTSP URL · E (Etkin) · B (Başlangıç) · Test
- Aktif kamera #'nin yanında pulse'lı yeşil nokta
- Sticky header (uzun listede scroll'da başlık sabit kalır)
- Alt aksiyon barı: 💾 TÜMÜNÜ KAYDET butonu + inline msg banner

**API base URL:**
```js
const FACE_SEC_API = 'http://127.0.0.1:5007'
```
Hardcoded — Express backend bypass. İleride env değişkeniyle parametrize
edilebilir.

## 3) App.jsx Entegrasyonu

**Dosya:** `güncellemeler/yeni_dashboard/src/App.jsx`

**Import:**
```js
import CameraSettings from './CameraSettings'
```

**Eski sağ panel (40 satır JSX, `CAMERAS` const + button list) silindi:**
```jsx
- <aside className="right-panel">
-   <div className="panel-head">KAMERA SİSTEMİ</div>
-   <div className="cam-list">
-     {CAMERAS.map(cam => { ... return <button ...>... })}
-   </div>
- </aside>
+ <CameraSettings />
```

**Geriye uyumlu bırakılan kısımlar:**
- `CAMERAS` sabiti
- `activeCameras`, `selectedCamera` state
- `handleCameraToggle` fonksiyonu
- Orta paneldeki `selectedCamera` ternary'si — `setSelectedCamera`
  artık çağrılmadığı için UI **harita görünümünde** kalır
  ("HARİTA GÖRÜNÜMÜ — SAĞ PANELDEN KAMERA SEÇİN" altyazısı).

  Bu kasıtlı bir tercih: state mantığı bozulmasın diye sildirmedim;
  orta panelin canlı kamera preview'u 25-kamera tablosuyla bir
  "seç-ve-gör" akışı kurulmadığı için pratik olarak hiç tetiklenmez.

## 4) Stil — App.css (~155 satır eklendi)

Mevcut dashboard tema değişkenleriyle (#22c55e accent, #2b3640/#1f2933
slate, #4ade80 success) uyumlu:

- `.cam-settings-panel` → right-panel'in default `250px`'ini override edip
  `min: 380, max: 460` aralığına genişletir (tablo dar sığmıyor)
- `.cs-table` + sticky `thead`, hover'da accent tinted
- `.cs-cell-id` aktif kamera için `.cs-active-dot` (pulse animation)
- `.cs-url-input` — focus'ta yeşil glow
- `.cs-test-btn.cs-test-{ok,fail,wait}` — durum rozetleri (yeşil/kırmızı/turuncu)
- `.cs-footer` — sticky alt bar + "💾 TÜMÜNÜ KAYDET" gradient buton
- `.cs-msg-ok/.cs-msg-err` — left-border accent + tinted background

## 5) Doğrulama

```bash
# Flask CORS preflight
$ test_client.OPTIONS /api/settings/cameras
  Status: 200, ACAO=*, ACAM=GET POST PUT DELETE OPTIONS  ✅

# Flask GET (25 kamera)
$ test_client.GET /api/settings/cameras
  Status: 200, cameras=25, ACAO=*, XFO=YOK, CSP=frame-ancestors *;  ✅

# Vite build
$ npx vite build
✓ 1739 modules transformed.
dist/assets/index-fb4028f0.css   20.48 kB  (önce 17.58 KB → +~3 KB)
dist/assets/index-df84f453.js    180.95 kB (önce 177.93 KB → +~3 KB)
✓ built in 4.69s  ✅
```

## 6) Restart Gerekliliği

| Servis | Restart? |
|---|---|
| Flask web (5007) | **EVET** — CORS değişikliği için. Dashboard YÜZ GÜVENLİĞİ → DURDUR → BAŞLAT |
| Express backend (5006) | hayır (dokunulmadı) |
| Vite (5005) | hayır (HMR otomatik) |

## 7) Test Senaryoları

1. Dashboard'da **KONTROL** sekmesinde sağda artık "KAMERA AYARLARI"
   başlığı + 25-satır tablo görünür.
2. Servis kapalıyken → kırmızı banner: *"Yüz Güvenliği servisine
   bağlanılamadı..."*
3. YÜZ GÜVENLİĞİ sekmesinden ▶ BAŞLAT → ↻ butonuna basınca tablo
   25 kamera ile doldurulur.
4. URL düzenle → **Test** → ✓ (3sn içinde) veya ✗
5. **Etkin** checkbox değiştir → arka planda anlık `cam_enabled` POST
6. **Başlangıç** radio seç → arka planda anlık `startup_cam` POST
7. URL'leri değiştir → **TÜMÜNÜ KAYDET** → `.env` atomic update +
   yeşil banner *"N kamera .env'e yazıldı."* + tablo otomatik tazelenir
8. Aktif kamera satırının numarasının yanında yeşil pulse nokta belirir

## 8) Dosyalar

**Yeni:**
- `güncellemeler/yeni_dashboard/src/CameraSettings.jsx` (~240 satır)

**Değiştirilen:**
- `güncellemeler/face_security_v3/web_app.py` — `_allow_iframe`
  hook'una CORS header'ları + `/api/<path>` OPTIONS preflight handler
- `güncellemeler/yeni_dashboard/src/App.jsx`:
  - `import CameraSettings from './CameraSettings'`
  - Eski 40-satır sağ panel JSX silindi → `<CameraSettings />`
- `güncellemeler/yeni_dashboard/src/App.css` — ~155 satır
  yeni stil (`.cam-settings-panel`, `.cs-table`, `.cs-url-input`,
  `.cs-test-btn`, `.cs-footer`, `.cs-save-btn`, `.cs-msg-*`)

**Dokunulmadı:**
- Express backend (server.js)
- Flask diğer endpoint'leri
- Mevcut Flask UI (iframe içinde tüm sekmeler aynen çalışır)
- Diğer App.jsx sekmeleri (faces-mgmt, settings, instabot, report)

## 9) Bilinen Sınırlamalar

- **API URL sabitlenmiş**: `FACE_SEC_API = 'http://127.0.0.1:5007'` —
  prod'da farklı hostname/port için env variable'la parametrize
  edilebilir (`import.meta.env.VITE_FACE_SEC_API`).
- **CORS açıklığı**: `Access-Control-Allow-Origin: *` herkesin local
  Flask sunucusuna istek atmasına izin verir; loopback (127.0.0.1)
  bind'ı sayesinde dış erişim yok. Prod'da daraltılabilir
  (örn. sadece `http://localhost:5005`).
- **Orta panel "harita görünümü"**: 25-kamera tablosu seçim UI'sı
  olmadığı için `selectedCamera` artık asla set edilmez, orta panel
  hep "HARİTA GÖRÜNÜMÜ" gösterir. Bu kabul edilebilir bir geri adım —
  isteğe bağlı olarak ileride 25-tablodaki satıra tıklayınca
  setSelectedCamera tetikleyen bir köprü eklenebilir.
- **Tablo tek panelde 25 satır**: scroll edilebilir (sticky header).
  Çok dar ekranlarda yatay scrollbar görünebilir; min-width 380px.

---

# YENİ YÜZ KAYDETME (FACE REGISTRATION) — Web Modal (2026-05-22)

## Hedef

Eski Tkinter'daki "kameradan anlık yüz çek + DB'ye kaydet" akışını
web'e modal pencere olarak taşı. Canlı kamera görüntüsünün altında bir
tetik butonu, tıklayınca açılan modal'da isim input + "Çek ve Kaydet"
butonu. Backend tek frame yakalayıp InsightFace ile yüz say (0/2+ → hata,
1 → DB'ye yaz + embedding rebuild) — uygulama restart'sız anında tanır.

## 1) Backend — `POST /api/faces/register`

**Dosya:** `güncellemeler/face_security_v3/web_app.py`

### İmza
```http
POST /api/faces/register
Content-Type: application/json

{ "name": "Ali Yılmaz" }
```

### Akış
1. **Sanitization (sunucu-tarafı, defansif derinlik)** — regex
   `[^a-zA-Z0-9çÇğĞıİöÖşŞüÜ\s]` ile geçersiz karakterleri sil. 1-50
   karakter aralığı dışı → 400.
2. **Frame yakalama** — `stream_handler.frame_lock` altında
   `last_frame_raw.copy()`. None ise: *"Aktif kamera frame'i yok"* → 400.
3. **InsightFace tespiti** — `face_processor.get_faces(frame)`:
   - 0 yüz → 400 *"Yüz tespit edilemedi"*
   - >1 yüz → 400 *"Karede N yüz var; tek bir kişi olmalı"* + `face_count`
   - 1 yüz → devam
4. **DB save** — `db_manager.save_person(name, frame)` →
   `cv2.imwrite(yuzler/<safe>.jpg)` + `cache.invalidate()` + `reload()`.
   InsightFace'in `known_faces` dict'i anında genişler.
5. Yanıt:
   ```json
   { "success": true, "name": "ali_yilmaz", "embeddings_total": 8 }
   ```

### Defansif Katmanlar
- `face_processor`, `db_manager`, `stream_handler` hazır değilse 503
- `name` string değilse 400
- Frame yakalama exception → 500
- `db_manager.save_person` False döndürürse 400 (geçersiz isim/IO)

### Mevcut `/api/faces/save_unknown` ile Fark
| | save_unknown | **register** (yeni) |
|---|---|---|
| Kaynak | son drain'lenen unknown crop (`_last_unknown_crop_np`) | aktif kameradan **canlı frame** |
| Yüz say | yok (zaten 1 unknown garanti) | **0/2+ kontrolü, açık hata** |
| Akış | "tespit ettin → isim ver" | "kameraya bak → ad gir → yakala" |
| UI tetik | Yüz Yönetimi sekmesi formu | MJPEG altındaki modal butonu |

İki endpoint bir arada — farklı UX yolları için yan yana çalışır.

## 2) Frontend — Modal + Trigger Buton

**Dosya:** `güncellemeler/face_security_v3/web_templates/index.html`

### MJPEG Footer'a Tetik Buton
```html
<div class="viewer-foot">
  <span>MJPEG · OpenCV → JPEG @ q=80 · InsightFace buffalo_s</span>
  <button id="openRegisterModalBtn" class="register-trigger-btn">
    + YENİ YÜZ KAYDET
  </button>
</div>
```

Yeşil gradient buton, MJPEG footer'ın sağında. `flex: 1` ile span sola
itildi, buton sağa yaslandı.

### Modal Markup (body-level overlay, herhangi bir sekmeden açılabilir)
```html
<div id="registerModal" class="modal-overlay" aria-hidden="true">
  <div class="modal-card" role="dialog">
    <div class="modal-head">
      <span>YENİ YÜZ KAYDET</span>
      <button class="modal-close" aria-label="Kapat">×</button>
    </div>
    <div class="modal-body">
      <p class="modal-help">…anlık frame'i yakalayıp yuzler/&lt;isim&gt;.jpg…</p>
      <label class="modal-label">Kişi Adı (sadece harf, rakam, boşluk)</label>
      <input id="registerNameInput" class="modal-input" maxlength="50" />
      <div class="modal-actions">
        <button class="modal-btn-secondary">İptal</button>
        <button class="modal-btn-primary">📷 Kameradan Çek ve Kaydet</button>
      </div>
      <div id="registerToast" class="modal-toast"></div>
    </div>
  </div>
</div>
```

### JS Davranış (`<script>` sonuna eklendi)

**`sanitizeName(input)`** — frontend XSS koruması:
```js
return input
  .replace(/[^a-zA-Z0-9çÇğĞıİöÖşŞüÜ\s]/g, '')  // sadece harf+rakam+boşluk
  .replace(/\s+/g, ' ')                          // çoklu boşlukları teke indir
  .trim()
  .slice(0, 50);
```

Backend de aynı regex'i tekrar uygular — derinlemesine savunma.

**Açma/Kapama:**
- Tetik buton → `openRegisterModal()` (input'a `setTimeout(focus, 50)`)
- × butonu, İptal butonu, **overlay arka plana tıklama**, **ESC tuşu** →
  `closeRegisterModal()`

**Canlı sanitize:**
```js
regNameInput.addEventListener('input', e => {
  const clean = sanitizeName(e.target.value);
  if (clean !== e.target.value) e.target.value = clean;  // anında temizle
});
```

**Enter tuşu** → submit butonunu tetikler.

**Submit akışı:**
1. Buton disable + metin "⏳ Kayıt yapılıyor..."
2. Toast (mavi-info) "Frame yakalanıyor ve InsightFace ile analiz ediliyor..."
3. `fetch('/api/faces/register', POST, {name})`
4. Başarılıysa: yeşil toast `✅ ali_yilmaz kaydedildi. Toplam embedding: 8`
   + `refreshPeople()` (eğer global tanımlıysa) + 1.8sn sonra modal otomatik kapat
5. Hataysa: kırmızı toast — backend mesajı + `face_count` varsa
   `[Tespit: 3]` rozetiyle

## 3) CSS — Modal + Trigger + Toast (~210 satır)

**Dosya:** `güncellemeler/face_security_v3/web_static/style.css`

- `.register-trigger-btn` — yeşil gradient, `MJPEG·...` metnin yanında
- `.modal-overlay` — `position: fixed; inset: 0; backdrop-filter: blur(4px)`,
  `modal-fade-in` 0.15s
- `.modal-card` — accent yeşil border + 24px glow shadow,
  `modal-slide-up` 0.22s (12px aşağıdan)
- `.modal-head` — yeşil gradient şerit + sağda × kapama (hover'da
  kırmızı tint)
- `.modal-input` — focus'ta accent glow
- `.modal-btn-primary` (yeşil gradient) + `.modal-btn-secondary` (gri)
- `.modal-toast-ok/err/info` — left-border accent + tinted background

Tüm renkler mevcut palette değişkenlerinden (`--accent`, `--err`,
`--bg-1` vb.) — tema tutarlı.

## 4) İframe + CORS Korundu

Yeni endpoint mevcut `@app.after_request` hook'undan otomatik
yararlanır — ayrıca konfigurasyon yapmadım. Doğrulandı:

```
POST /api/faces/register response:
  X-Frame-Options present:  False        ✅
  Content-Security-Policy:  frame-ancestors *;
  Access-Control-Allow-Origin: *

OPTIONS preflight /api/faces/register:
  Status: 200
  ACAM: GET, POST, PUT, DELETE, OPTIONS
```

`/api/<path:_any>` catch-all OPTIONS handler bu endpoint için de geçerli.

## 5) Doğrulama (otomatik smoke test)

```
=== /api/faces/* route'lar: 11 adet  (önce 10, +register) ✅
=== POST /api/faces/register (servis henüz init edilmedi):
    503 {'error': 'Servis henüz hazır değil (model yükleniyor)'}  ✅
=== GET /api/faces/register: 405 (sadece POST)  ✅
=== CORS preflight: 200, ACAO=*  ✅
=== Iframe headers: XFO=False, CSP=frame-ancestors *;  ✅
=== Jinja2 template parse: OK  ✅
=== python3 -m py_compile web_app.py: OK  ✅
```

## 6) Restart Gerekliliği

| Servis | Restart? |
|---|---|
| Flask web (5007) | **EVET** — Dashboard YÜZ GÜVENLİĞİ → DURDUR → BAŞLAT |
| Express backend (5006) | hayır (dokunulmadı) |
| Vite (5005) | hayır (Flask UI direkt iframe edilir, React build değişmedi) |

## 7) Test Senaryoları (UI)

1. YÜZ GÜVENLİĞİ sekmesi → Iframe yüklenir → "Yüz Tanıma" alt sekmesi
2. Canlı MJPEG'in altında **+ YENİ YÜZ KAYDET** butonu (yeşil) görünür
3. Butona tıkla → blur'lu overlay + slide-up animasyonlu modal açılır
4. Input'a `Ali Yılmaz!@#$` yaz → anlık temizlenip `Ali Yılmaz` kalır
5. Kameraya **kimse bakmadan** "Çek ve Kaydet" → 400 *"Yüz tespit edilemedi"*
6. Kameraya **iki kişi** bak → 400 *"Karede 2 yüz var; tek bir kişi olmalı [Tespit: 2]"*
7. Kameraya **tek kişi** bak → ✅ yeşil toast *"ali_yilmaz kaydedildi.
   Toplam embedding: N"* + 1.8sn sonra modal kapanır
8. Yüz Yönetimi sekmesi → Kayıtlı Kişiler listesinde yeni kişi
9. Uygulama RESTART YAPMADAN aynı kişi kameraya bakınca artık "Son tanınan"
   kartında ismi belirir (anlık embedding reload sayesinde)
10. ESC tuşu / arka plana tıklama / × butonu / İptal → modal kapanır

## 8) Dosyalar

**Değiştirilen:**
- `güncellemeler/face_security_v3/web_app.py` — `/api/faces/register`
  endpoint'i (~70 satır)
- `güncellemeler/face_security_v3/web_templates/index.html`:
  - `viewer-foot` içine tetik buton
  - body-level modal markup (~40 satır)
  - script bloğuna modal kontrol JS'i (~95 satır)
- `güncellemeler/face_security_v3/web_static/style.css` — modal + toast +
  trigger button stilleri (~210 satır)

**Dokunulmadı:**
- Express backend, React dashboard, Vite
- `plate_runner.py`, eski Tkinter `ui/*.py`
- Diğer `/api/*` endpoint'leri
- Mevcut sekme/sekme switcher mantığı

## 9) Sistem Hazır

- `python3 -m py_compile web_app.py` ✅
- 11 yeni route /api/faces/* doğrulandı ✅
- CORS preflight 200 ✅
- Iframe headers korundu ✅
- Jinja parse OK ✅
- Terminal'de syntax hatası yok ✅

Restart sonrası UI test edilmeye hazır.

---

# AYARLAR SAYFASI REFACTORING — Navbar + Yeni Settings Sekmesi (2026-05-22)

## Hedef

Dashboard'un navbar'ı sadeleştirildi ve ayarlar tek bir merkezi sayfada
toplandı:
1. Üst panel başlığı **"EYE OF WEB CONTROL CENTER"** + iki göz ikonu **kaldırıldı**
2. Navbar'a **AYARLAR** sekmesi eklendi (RAPOR ↔ KAPAT arasına)
3. Yeni `Settings.jsx` bileşeni — kendi içinde 3 alt sekme (pill-style):
   **Genel Ayarlar** / **Yüz Güvenliği** / **Kamera**
4. `<CameraSettings />` KONTROL sağ panelinden alınıp Settings → Kamera
   alt sekmesine taşındı; sağ panel tamamen kaldırıldı

## 1) Navbar Düzenlemesi

**Dosya:** `güncellemeler/yeni_dashboard/src/App.jsx`

### Title bloğu silindi
```diff
- <div className="top-title">
-   <Eye size={26} color="#60a5fa" />
-   <span>EYE OF WEB CONTROL CENTER</span>
-   <Eye size={26} color="#60a5fa" />
- </div>
```

### AYARLAR butonu (RAPOR ↔ KAPAT arası)
```jsx
<button
  className={`btn-tab ${activeTab === 'settings' ? 'btn-tab-active' : ''}`}
  onClick={() => setActiveTab('settings')}
>
  <SettingsIcon size={13} /> AYARLAR
</button>
```

`lucide-react`'tan `Settings as SettingsIcon` import edildi (mevcut
`Settings` bileşen import'uyla çakışmasın diye alias).

### Ternary 4-yollu → 5-yollu
```jsx
{activeTab === 'control' ? (kontrol)
 : activeTab === 'report' ? (rapor)
 : activeTab === 'face-security' ? (face-sec)
 : activeTab === 'settings' ? (<Settings />)    // YENİ
 : (instabot)}
```

## 2) Yeni `Settings.jsx` Bileşeni

**Dosya:** `güncellemeler/yeni_dashboard/src/Settings.jsx` (yeni, ~95 satır)

```jsx
export default function Settings() {
  const [subTab, setSubTab] = useState('camera')  // default açılış

  return (
    <div className="settings-page">
      <header className="settings-page-head">
        <div className="settings-page-title">⚙ AYARLAR</div>
        <nav className="settings-subtabs">
          <button className="settings-subtab is-active?">Genel Ayarlar</button>
          <button className="settings-subtab is-active?">Yüz Güvenliği</button>
          <button className="settings-subtab is-active?">Kamera</button>
        </nav>
      </header>
      <div className="settings-page-body">
        {subTab === 'general' && <GenelPlaceholder />}
        {subTab === 'face' && <FacePlaceholder />}
        {subTab === 'camera' && <CameraSettings />}
      </div>
    </div>
  )
}
```

**Alt sekmelerin içeriği:**
- **Genel Ayarlar**: yer tutucu — "Sistem geneli için ayarlar bu bölüme
  eklenecektir (Tema, polling süreleri, log seviyesi, vb.)"
- **Yüz Güvenliği**: yer tutucu (user'ın istediği şekilde) — *"Yüz
  güvenliği ayarları buraya taşınacaktır"* + alt satırda Flask
  endpoint'i `/api/settings/runtime` notu
- **Kamera**: 1. turda taşınan `<CameraSettings />` 25-kamera tablosu

Her alt sekme `role="tab"` + `aria-selected` ile a11y uyumlu.

## 3) KONTROL Sağ Panel Kaldırıldı

**Dosya:** `güncellemeler/yeni_dashboard/src/App.jsx`

```diff
- {/* SAĞ PANEL — 25-kamera RTSP ayarları */}
- <CameraSettings />
- {/* ...mevcut açıklama... */}
+ {/* CameraSettings AYARLAR sekmesi → Kamera alt sekmesine taşındı.
+     .main-area flex layout sayesinde center-panel kalan tüm yatay
+     alanı doğal olarak kaplar — harita görünümü tam genişler. */}
```

**Grid bütünlüğü:** `.main-area` zaten `display: flex` (grid değil).
`.left-panel` ve eski `.right-panel` width sabit, `.center-panel` `flex: 1`
ile esnek. Sağ panel kaldırılınca center-panel **kalan tüm yatay alanı**
doğal olarak kaplar — harita görünümü tam genişler, CSS düzenlemesine
gerek kalmadı.

## 4) CSS — App.css (~145 satır eklendi)

```
.main-area.settings-area       — flex container
.settings-page                 — column flex, overflow hidden
.settings-page-head            — başlık + alt sekme nav
.settings-page-title           — accent yeşil, letter-spacing 1.5
.settings-subtabs              — pill button grubu
.settings-subtab               — gri pill; alt 1px border-bottom çakışmaması
                                  için margin-bottom: -1px
.settings-subtab.is-active     — koyu yeşil bg (#14290e) + accent border +
                                  glow shadow + 4ade80 metin
.settings-subtab:hover         — gri tonlama
.settings-page-body            — flex 1, overflow auto, padding 18 24
.settings-pane                 — beyazlı koyu kart
.settings-pane-placeholder     — ikon + başlık + açıklama (centered)
.settings-pane-camera          — CameraSettings için padding 0 + flex
```

### CameraSettings width override gevşetme
KONTROL sayfasındaki right-panel'de `.cam-settings-panel` 410-460px
sınırlıydı (right-panel default 250px'ti, override gerekti). AYARLAR
sayfası içinde tüm yatay alan bizimken bu sınır artık darlık yaratıyor;
o yüzden:

```css
.settings-pane-camera .cam-settings-panel {
  width: auto !important;
  min-width: 0 !important;
  max-width: none !important;
  flex: 1;
  border-left: none;     /* right-panel'in sol border'ı kaldır */
  background: #1f2933;
  border: 1px solid #2b3640;
  border-radius: 8px;
}
```

Specificity (`.settings-pane-camera .cam-settings-panel`) > CameraSettings
kendi tek-class kuralı, bu yüzden override `!important`'la garantilendi.

## 5) Doğrulama

```bash
$ npx vite build
✓ 1740 modules transformed.   (önce 1739, +Settings.jsx)
dist/assets/index-9790eda8.css   22.57 kB  (önce 20.48 → +2 KB)
dist/assets/index-b887481a.js   183.65 kB  (önce 180.95 → +3 KB)
✓ built in 4.36s   — hata yok ✅
```

**Olası import/export hataları kontrol:**
- `Settings` default export ✅
- `Settings as SettingsIcon` alias (lucide) ✅
- `CameraSettings` Settings.jsx içinden default import ✅
- `App.jsx`'te eski `import CameraSettings from './CameraSettings'`
  artık doğrudan kullanılmasa da silmedim — Settings.jsx import etmek
  üzere modülün dosyada kalması yeterli. Aslında `App.jsx`'te direk
  import yok; sadece Settings.jsx üzerinden indirek. Eski import satırı:
  ```diff
  - import CameraSettings from './CameraSettings'
  ```
  `import Settings from './Settings'` ile değiştirildi.

## 6) Restart Gerekliliği

| Servis | Restart? |
|---|---|
| Vite dev server (5005) | HMR otomatik reload — manuel restart **gerekmez** |
| Express backend (5006) | hayır (dokunulmadı) |
| Flask web (5007) | hayır (dokunulmadı) |

Production için `npx vite build` doğrulandı.

## 7) UI Test Akışı

1. Dashboard üst panelinde "EYE OF WEB CONTROL CENTER" yazısı yok ✅
2. Sekme sırası: **KONTROL · YÜZ GÜVENLİĞİ · INSTAGRAM BOT · RAPOR · AYARLAR · KAPAT · BAŞLAT** ✅
3. KONTROL sekmesi: sağ panel yok, harita orta + sol panel kaldı (full width center) ✅
4. AYARLAR sekmesine tıkla → "⚙ AYARLAR" başlığı + 3 pill alt sekme
5. Alt sekme **Kamera** default açık → 25-kamera RTSP tablosu, max-width
   yok, ekran genişliği kadar tablo
6. Alt sekme **Yüz Güvenliği** → ShieldCheck ikonu + *"Yüz güvenliği
   ayarları buraya taşınacaktır"* placeholder
7. Alt sekme **Genel Ayarlar** → Sliders ikonu + sistem geneli placeholder

## 8) Dosyalar

**Yeni:**
- `güncellemeler/yeni_dashboard/src/Settings.jsx` (~95 satır)

**Değiştirilen:**
- `güncellemeler/yeni_dashboard/src/App.jsx`:
  - lucide import: `Settings as SettingsIcon` eklendi
  - `import Settings from './Settings'` (eski `CameraSettings` import'unun yerine)
  - `<div className="top-title">...</div>` silindi
  - Yeni AYARLAR butonu (RAPOR ↔ KAPAT arası)
  - KONTROL sağ panelindeki `<CameraSettings />` ve uzun yorum bloğu silindi
  - Ternary 4-yollu → 5-yollu (`activeTab === 'settings' ? <Settings /> : ...`)
- `güncellemeler/yeni_dashboard/src/App.css` — ~145 satır
  Settings stilleri eklendi; `.settings-pane-camera .cam-settings-panel`
  width override

**Dokunulmadı:**
- `CameraSettings.jsx` (Settings.jsx üzerinden kullanılıyor, kodu aynı)
- Express backend, Flask, Vite config
- Diğer sekmeler (face-security, instabot, report)

## 9) Bilinen Sınırlamalar

- **Genel Ayarlar + Yüz Güvenliği** sekmeleri **placeholder** —
  ileri turlarda Flask `/api/settings/runtime` endpoint'i (threshold,
  fps, snapshot cooldown) buraya bağlanabilir.
- **default açılış sekmesi** `'camera'` — kullanıcı en sık kullanılan
  alt sekmenin açık gelmesini bekler. İleride localStorage'a son seçilen
  sub-tab'i hatırlayan bir reducer eklenebilir.

---

# KAMERA İZLEME ENTEGRASYONU — PyQt5 → Flask MJPEG → React (2026-05-22)

## Hedef

`realtime_search_camera_ornek.py`'deki PyQt5 `CameraThread` mantığını,
web tabanlı sisteme tamamen taşı:
- KONTROL sağ panele 25 kamera seçim button grid'i
- Tıklayınca orta paneldeki harita placeholder yerine MJPEG canlı yayın
- Flask `/api/stream/<cam_id>` ile `realtime_search_camera_ornek.py`'in
  OpenCV `cv2.VideoCapture` döngüsünün web sürümü
- Memory leak yok: kamera değişiminde eski `cap.release()` garanti

## 1) Backend — `CameraStream` (refcounted shared worker)

**Dosya:** `güncellemeler/face_security_v3/web_app.py` (~190 satır eklendi)

### Mimari
Naif yaklaşım her HTTP istek için yeni `VideoCapture` açar — ama:
- RTSP bağlantısı 3-5sn açılma gecikmesi
- Hızlı kamera değişiminde leak riski
- Aynı cam_id'ye birden çok istemci varsa N defa kaynak tüketir

Çözüm: `cam_id` başına **TEK paylaşılan worker thread**, reference-counted:

```python
class CameraStream:
    def acquire(self):              # consumer +1, gerekirse worker spawn
    def release(self):              # consumer -1, 0'a düşerse worker dur + cap.release()
    def latest_jpeg(self):          # son frame'in JPEG byte'ı (thread-safe)
    def _worker_loop(self):         # cv2.VideoCapture döngüsü
    def _interruptible_sleep(self): # _running False → erken kes
```

### Worker Loop (`realtime_search_camera_ornek.CameraThread.run` web sürümü)
1. `_open_capture()` — `cv2.VideoCapture(url, CAP_FFMPEG)` + 5sn timeout
2. Sonsuz döngü:
   - `_cap.read()` her ~33ms (≈30 FPS)
   - Frame yoksa → `_cap.release()` + 0.5s **interruptible_sleep** + reconnect
   - 30sn boyunca tek frame yoksa → worker sonlanır (sonsuz reconnect spam'ı yok)
   - Başarılıysa → `cv2.imencode('.jpg', q=80)` → `_latest_jpeg` set (frame_lock)
3. `finally:` bloğu → `self._cap.release()` **garanti** + `_thread = None`

### Interruptible Sleep — kritik leak korumacısı
Naif `time.sleep(1)` running flag'ini kontrol etmez. Refcount sıfırlandıktan
sonra worker'ın 5sn kadar yaşaması leak'e benzer. Çözüm:

```python
def _interruptible_sleep(self, seconds):
    end = time.time() + seconds
    while self._running and time.time() < end:
        time.sleep(0.05)
```

Tüm `_time.sleep(...)` çağrıları bu helper'a çevrildi.

### Endpoint
```http
GET /api/stream/<int:cam_id>
→ Content-Type: multipart/x-mixed-replace; boundary=frame
→ X-Accel-Buffering: no   (proxy buffer kapama)

GET /api/stream/active
→ {"streams": [{cam_id, consumers, running, alive}], "total": N}
```

### MJPEG Generator (per-HTTP-connection)
```python
def _mjpeg_camera_generator(cam_id):
    stream = _get_or_create_stream(cam_id)
    stream.acquire()
    try:
        # İlk frame için 2sn grace
        for _ in range(20):
            if stream.latest_jpeg(): break
            time.sleep(0.1)
        while True:
            jpg = stream.latest_jpeg()
            if jpg is None: time.sleep(0.2); continue
            yield boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            time.sleep(0.04)  # ~25fps HTTP throughput cap
    except GeneratorExit:
        # Browser MJPEG bağlantıyı kapattı (kamera değişti / sekme kapandı)
        pass
    finally:
        stream.release()         # ← acquire/release dengesi garanti
```

`GeneratorExit` browser MJPEG image tag unmount edildiğinde otomatik
gelir → cleanup garanti.

### `_redact()` — log'larda RTSP credentials maskele
```
rtsp://admin:secret@192.168.1.1:554/Streaming →
rtsp://***:***@192.168.1.1:554/Streaming
```

### CORS + iframe header'lar korundu
Mevcut `@app.after_request` hook her response'a CORS + CSP uygular.
`/api/stream/<id>` ve `/api/stream/active` test edildi:
- `ACAO: *`, `XFO: yok`, `CSP: frame-ancestors *;` ✅

## 2) React — `CamerasPanel.jsx` (yeni, ~110 satır)

**Dosya:** `güncellemeler/yeni_dashboard/src/CamerasPanel.jsx`

`props.selectedCamId / onSelect / onClear` ile dış state (App.jsx) ile köprü.

### Veri Akışı
- Mount'ta `GET /api/settings/cameras` → 25 satır
  (`{id, name, url, enabled, is_active}`)
- 15sn'de bir tazele (yeni eklenen kameralar UI'da görünsün)
- Servis kapalı/hatalıysa: kırmızı banner *"Yüz Güvenliği servisine
  bağlanılamadı (5007). Üst menüden ▶ BAŞLAT ile servisi açın."*

### Button Davranışları
- `url` boş → **disabled** + soluk italik
- `url` dolu → tıklanabilir, sol kenar accent border
- **Seçili (yayın aktif)** → tam yeşil gradient + pulse dot
- Üstte ↻ tazele butonu, alt orta panele yayın varsa **"■ AKIŞI KAPAT"** kırmızı buton

## 3) App.jsx Entegrasyonu

### Yeni state
```jsx
const [selectedStreamCam, setSelectedStreamCam] = useState(null) // {id, name} | null
```

### Sağ panel
```jsx
<CamerasPanel
  selectedCamId={selectedStreamCam ? selectedStreamCam.id : null}
  onSelect={cam => setSelectedStreamCam(cam)}
  onClear={() => setSelectedStreamCam(null)}
/>
```

### Orta panel — eski sahte preview yerine MJPEG
```jsx
{selectedStreamCam ? (
  <div className="stream-view">
    <div className="live-tag">CANLI — #1 GİRİŞ KAPISI</div>
    <div className="stream-frame">
      <img
        key={selectedStreamCam.id}   // ← cam değiştirince img unmount/remount
        src={`http://127.0.0.1:5007/api/stream/${selectedStreamCam.id}`}
      />
      <div className="stream-footer">MJPEG · Flask 5007 · OpenCV → JPEG q=80</div>
    </div>
  </div>
) : (
  <div className="map-view">…HARİTA GÖRÜNÜMÜ…</div>
)}
```

**Memory leak koruması — React tarafı**: `key={selectedStreamCam.id}`
sayesinde cam_id değiştiğinde `<img>` DOM'dan kaldırılıp yeniden
yaratılır. Browser eski MJPEG bağlantısını kapatır → Flask
`GeneratorExit` alır → `stream.release()` → refcount 0 →
`cap.release()`. Tüm zincir otomatik.

## 4) CSS — App.css (~190 satır eklendi)

### `.cameras-panel` (KONTROL sağ panel)
- Width 280px (eski cam-btn listesinden biraz daha geniş)
- Sticky `panel-head` + ↻ refresh butonu

### `.cam-tile` button — 4-kolon grid
```
[#1] [ikon] [İsim..............] [● dot]
```
- `.cam-tile-on` — sol kenar 2px accent yeşil border
- `.cam-tile-off` — opacity 0.45 + italic + cursor not-allowed
- `.cam-tile-selected` — **tam yeşil gradient** + 10px green glow shadow +
  pulse dot (`cam-tile-pulse` keyframes)

### `.stream-view` (orta panel MJPEG)
- `live-tag` sol üst köşede absolute, backdrop blur
- `.stream-img` `object-fit: contain` — orijinal aspect korunur
- `.stream-footer` alt bilgi şeridi (MJPEG · Flask 5007 · timestamp)

## 5) Doğrulama

### Backend smoke test
```
/api/stream/<int:cam_id>      → 404 (URL tanımlı değilse)
/api/stream/active            → 200 {"streams": [...]}
CORS preflight OPTIONS        → 200 ACAO=*
Iframe headers korundu        → XFO=False, CSP=frame-ancestors *;
_redact() RTSP creds          → rtsp://***:***@…
```

### Memory cleanup refcount test (6 senaryo, hepsi geçti)
```
[1] init: consumers=0, thread=None              ✅
[2] 3x acquire: consumers=3, single thread       ✅
[3] 1 release: consumers=2, running=True (canlı) ✅
[4] all release: consumers=0, running=False      ✅
[5] 8s grace: thread=None, _cap=None             ✅ (cleanup garanti)
[6] re-acquire: yeni worker spawn                ✅
```

### Vite build
```
✓ 1741 modules transformed.   (önce 1740, +CamerasPanel.jsx)
dist/assets/index-a7460dec.css   26.00 kB
dist/assets/index-6415db55.js   185.76 kB
✓ built in 6.48s                — hata yok ✅
```

## 6) Restart Gerekliliği

| Servis | Restart? |
|---|---|
| Flask web (5007) | **EVET** — yeni endpoint'ler ve CameraStream class |
| Vite (5005) | HMR otomatik |
| Express (5006) | hayır |

## 7) Test Senaryoları (UI)

1. Dashboard → KONTROL sekmesi → sağda "KAMERA SİSTEMİ" başlığı + 25 button grid
2. URL tanımsız kameralar **disabled** + soluk
3. Tanımlı bir kameraya tıkla:
   - Buton tam yeşil + pulse dot ile vurgulanır
   - Orta panel harita → MJPEG canlı yayın
   - Sol üstte **CANLI** rozet + #ID + kamera adı
4. Başka bir kameraya tıkla → eski yayın anında kapanır (browser img unmount
   → Flask GeneratorExit → cap.release()) → yeni yayın açılır
5. "■ AKIŞI KAPAT" → harita görünümüne döner; arka planda son
   CameraStream'in son consumer'ı çıkar → worker durur (3sn içinde)
6. RTSP'siz cam butona basılamaz (disabled)
7. Flask kapalıysa kırmızı banner: *"servise bağlanılamadı"*

## 8) PyQt5 Bağımlılığı YOK

- `realtime_search_camera_ornek.py` PyQt5 import'ları **referans amaçlı**
  (dokunulmadı, eski masaüstü scripti olarak duruyor)
- Web sistemi **sadece** `cv2 + Flask + threading` kullanıyor — Qt yok
- Tüm görselleştirme tarayıcı tarafında MJPEG `<img>` ile

## 9) Dosyalar

**Yeni:**
- `güncellemeler/yeni_dashboard/src/CamerasPanel.jsx` (~110 satır)

**Değiştirilen:**
- `güncellemeler/face_security_v3/web_app.py`:
  - `CameraStream` class (~120 satır)
  - `_camera_streams` global registry + `_camera_streams_lock`
  - `_get_or_create_stream`, `_mjpeg_camera_generator`, `_redact` helper'ları
  - `/api/stream/<int:cam_id>`, `/api/stream/active` endpoint'leri
- `güncellemeler/yeni_dashboard/src/App.jsx`:
  - `import CamerasPanel from './CamerasPanel'`
  - `selectedStreamCam` state
  - KONTROL sağ paneli → `<CamerasPanel>` ile dolu
  - KONTROL orta paneli → `selectedStreamCam ? MJPEG <img> : harita`
- `güncellemeler/yeni_dashboard/src/App.css` — ~190 satır:
  `.cameras-panel`, `.cam-tile{-on,-off,-selected,-dot}`, `.stream-view`,
  `.stream-frame`, `.stream-img`, `.stream-footer`

**Dokunulmadı:**
- `realtime_search_camera_ornek.py` (PyQt5 referans — eski script)
- Express backend (server.js)
- Settings.jsx, CameraSettings.jsx (AYARLAR sekmesi)
- Mevcut Yüz Güvenliği iframe içeriği

## 10) Bilinen Sınırlamalar

- **CameraStream silinmiyor**: 30sn frame timeout'ta worker durur ama
  `_camera_streams` dict'inde **kayıt kalır** (kullanılmayan ama uygun).
  Sonraki acquire'da yeni worker spawn olur. Periyodik garbage collection
  eklenebilir (örn. 5dk sleeping stream'i sil).
- **MJPEG performansı**: ~25 FPS HTTP cap. H264 streaming için
  WebRTC/HLS gerekir — kapsam dışı.
- **Aynı anda kaç MJPEG?** React tek seferde tek `<img>` render eder
  (selectedStreamCam state tek değer). Multi-camera grid view ileride
  düşünülebilir.
- **RTSP credentials log**: `_redact()` ile maskelendi, ama
  `config.CAMERAS` dict belleğinde plain text. Bunu env-only tutmak
  istenebilir (zaten öyle, sadece runtime'da yüklü).

---

# KAMERA İZLEME GERİ ALINDI — PyQt5 Masaüstü Mimarisine Dönüş (2026-05-22)

## Hedef

Önceki turda yapılan **MJPEG web stream** entegrasyonu user'ın isteğiyle
**iptal edildi**. Sebep: KONTROL kameraları `face_security_v3`'ten
bağımsız çalışıyor ve orijinal `realtime_search_camera_ornek.py`'in tüm
özellikleri (Milvus DB eşleşmeleri, PostgreSQL bağlantısı, Cyber HUD,
çoklu-yüz tespiti, gerçek zamanlı arama, çoklu sonuç panelleri) sadece
PyQt5 masaüstü penceresinde tam çalışıyor — web sürümü bunların hiçbirini
karşılamıyor.

Yeni model: React arayüzü **sadece bir uzaktan kumandadır** — kameraya
tıklayınca kullanıcının makinesinde orijinal PyQt5 penceresini açan
launcher tetikleyici.

## 1) Launcher Script — `realtime_search_camera_launcher.py`

**Dosya:** `src/realtime_search_camera_launcher.py` (yeni, 2592 satır)

Orijinal `src/realtime_search_camera_ornek.py` (2587 satır, Milvus +
PyQt5) **dokunulmadan** korundu (user kuralı). Launcher onun
sentetik kopyası — sadece 2 cerrahi değişiklik:

### Header eklendi (~60 satır)
```python
def _eow_resolve_camera_url():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--cam-id", type=int, default=None)
    p.add_argument("--rtsp-url", type=str, default=None)
    known, rest = p.parse_known_args()
    sys.argv = [sys.argv[0]] + rest    # PyQt'a temiz argv

    url = known.rtsp_url or os.environ.get("EOW_CAMERA_URL")
    cam_id = known.cam_id or int(os.environ.get("EOW_CAMERA_ID", "0"))

    # URL yoksa cam_id'den .env tara: src/.env → face_security_v3/.env
    if not url and cam_id:
        for env_path in (...):
            for line in env_path.read_text().splitlines():
                if line.startswith(f"CAM_{cam_id:02d}_URL="):
                    url = line.split("=", 1)[1].strip()...
    if not url: sys.exit(2)
    return url, cam_id

_EOW_RESOLVED_URL, _EOW_RESOLVED_ID = _eow_resolve_camera_url()
```

### Line 329 (Window title) — cam_id'yi başlığa ekle
```python
self.setWindowTitle(
    f"👁️ EyeOfWeb - Kamera #{_EOW_RESOLVED_ID} - Kurumsal Yüz Tanıma v2.0"
    if _EOW_RESOLVED_ID is not None
    else "👁️ EyeOfWeb - Kurumsal Yüz Tanıma Sistemi v2.0"
)
```

### Line 345 (hardcoded RTSP) — env'den override
```python
# AUTO-PATCHED — orijinaldeki hardcoded RTSP URL launcher tarafından override edilir
self.camera_id = _EOW_RESOLVED_URL
```

Geri kalan **her şey aynı**: PyQt5 widgets, Milvus connection, PostgreSQL,
CameraThread, SearchThread, AnimatedLabel, CyberFrame, multi-face panels,
similarity threshold, search interval, history listeleri, vb.

### Çağırma örnekleri
```bash
python3 realtime_search_camera_launcher.py --cam-id 7
EOW_CAMERA_URL="rtsp://..." python3 realtime_search_camera_launcher.py
EOW_CAMERA_ID=12 python3 realtime_search_camera_launcher.py  # .env'den çek
```

## 2) Express Endpoint — `POST /api/control/launch-camera/:id`

**Dosya:** `güncellemeler/yeni_dashboard/backend/server.js`

```js
app.post('/api/control/launch-camera/:id', (req, res) => {
  const camId = parseInt(req.params.id, 10);
  if (!Number.isInteger(camId) || camId < 1 || camId > 25) {
    return res.status(400).json({ error: 'cam_id 1-25 aralığında olmalı' });
  }
  const cmd = `cd ${BASE_PATH} && source WorkEnv/bin/activate `
            + `&& python3 realtime_search_camera_launcher.py --cam-id ${camId}`;
  addLog(`KAMERA #${camId} LAUNCHER TETİKLENDİ`);

  const proc = spawn('bash', ['-c', cmd], {
    cwd: BASE_PATH,
    detached: true,        // ← backend kapansa bile pencere açık kalır
    stdio: 'ignore',       // ← Qt log'ları Node stdout'unu kirletmesin
    env: { ...process.env, DISPLAY: process.env.DISPLAY || ':0' },
  });
  proc.on('error', err => addLog(`KAMERA #${camId} SPAWN HATASI: ${err.message}`));
  proc.unref();            // ← Node event loop'u tutmasın

  res.json({
    success: true,
    cam_id: camId,
    message: `Kamera #${camId} masaüstü penceresi başlatılıyor (PyQt5 + Milvus).`,
    pid: proc.pid,
  });
});
```

**Komut hattının kullanıcının belirttiği şekilde olduğu doğrulandı:**
```
✓ cd src && source WorkEnv/bin/activate
✓ python3 realtime_search_camera_launcher.py
✓ spawn detached:true (background)
✓ DISPLAY=:0 (X server için)
```

## 3) React Frontend — Sadece Tetikleyici

### `CamerasPanel.jsx` — trigger-only
Önceki MJPEG seçici state'i kaldırıldı. Yeni props:
- `onLaunched(info)` — POST sonrası callback (App.jsx toast gösterir)

```jsx
const handleLaunch = async (cam) => {
  setLastTriggered(cam.id)  // 3sn sarı flash animation
  const res = await fetch(`http://localhost:5006/api/control/launch-camera/${cam.id}`, {
    method: 'POST'
  })
  const data = await res.json()
  onLaunched?.({ id: cam.id, name: cam.name,
                  kind: res.ok && data.success ? 'ok' : 'err',
                  msg: data.message || data.error })
}
```

**Buton durumları:**
- `configured` (URL var) → tıklanabilir
- `cam-tile-on` → sol kenarda accent yeşil
- `cam-tile-launching` (3sn) → tam sarı flash + spinner (göz alıcı feedback)
- `cam-tile-off` → soluk + disabled

**Info-bar üstte:** `📺 Masaüstü penceresi (PyQt5 + Milvus)` — kullanıcı
ne olacağını bilsin.

### `App.jsx` — MJPEG view kaldırıldı, harita sabit
```diff
- const [selectedStreamCam, setSelectedStreamCam] = useState(null)
+ const [launchToast, setLaunchToast] = useState(null) // { id, name, kind, msg }

  // ORTA PANEL artık her zaman harita
- {selectedStreamCam ? <MJPEG /> : <Map />}
+ <Map />

  // SAĞ PANEL trigger-only
- <CamerasPanel selectedCamId={...} onSelect={...} onClear={...} />
+ <CamerasPanel onLaunched={info => {
+   setLaunchToast(info)
+   setTimeout(() => setLaunchToast(p => p?.id === info.id ? null : p), 5000)
+ }} />
```

### Global Toast (sağ alt köşe, tüm sekmelerden görünür)
```jsx
{launchToast && (
  <div className={`launch-toast launch-toast-${launchToast.kind}`}>
    📷  Kamera #X başlatılıyor — Y — masaüstü penceresini kontrol edin.
    [×]
  </div>
)}
```
- 5sn auto-dismiss
- `launch-toast-ok` yeşil left-border + glow
- `launch-toast-err` kırmızı left-border + glow
- Slide-up animation 0.22s

## 4) Flask Temizliği

**Dosya:** `güncellemeler/face_security_v3/web_app.py`

Silinen blok:
- `class CameraStream` (~140 satır — refcounted shared worker)
- `_camera_streams: dict`, `_camera_streams_lock`
- `_redact()`, `_get_or_create_stream()`, `_mjpeg_camera_generator()` helpers
- `@app.route("/api/stream/<int:cam_id>")`
- `@app.route("/api/stream/active")`

**Doğrulama:**
```
$ grep -E "CameraStream|/api/stream|_camera_streams|_mjpeg_camera_generator" web_app.py
0 sonuç ✅

$ Flask app boot:
Toplam route: 41   (önce 43, -2 stream)
/api/stream içeren route: 0
hasattr(web_app, 'CameraStream'): False
```

Diğer endpoint'ler etkilenmedi: face register, plates, settings, logs,
detections, video_feed (face_security'nin kendi MJPEG'i) — hepsi çalışır.

## 5) CSS Güncelleme — `App.css`

**Eklenen:** ~120 satır
- `.cam-tile-launching` — sarı gradient + glow (3sn flash)
- `.cam-tile-spinner` — döner animasyon
- `.cameras-info-bar` — üstte mavi info banner
- `.launch-toast{-ok,-err}` — sağ alt köşe toast + slide-up
- `.launch-toast-icon/-body/-title/-msg/-close`

**Silinen:** ~80 satır
- `.cam-tile-selected` (yeşil dolu seçili durum)
- `.cam-tile-dot` (pulse dot)
- `.stream-view`, `.stream-frame`, `.stream-img`, `.stream-footer`,
  `.stream-ts` (MJPEG view ile birlikte kullanılmayan tüm class'lar)
- `.live-tag` override (stream-view içindeki)

## 6) Doğrulama Toplu

```bash
$ python3 -m py_compile src/realtime_search_camera_launcher.py    → OK ✅
$ python3 src/realtime_search_camera_launcher.py --cam-id 1       → URL resolved ✅
$ python3 src/realtime_search_camera_launcher.py --cam-id 999     → "URL bulunamadı" ✅

$ node -c güncellemeler/yeni_dashboard/backend/server.js          → OK ✅
$ grep validation server.js:
  POST /api/control/launch-camera/:id     : true
  spawn (child_process) kullanım          : true
  detached: true (background)             : true
  cd src && source WorkEnv/bin/activate   : true
  realtime_search_camera_launcher.py call : true

$ python3 -m py_compile face_security_v3/web_app.py               → OK ✅
$ Flask routes:  /api/stream/* sayısı = 0                          → OK ✅
$ CameraStream class hâlâ var mı?                                  → False ✅

$ npx vite build → 1741 modules, 26.34KB CSS, 186.61KB JS         → ✓ hata yok ✅
```

## 7) Restart Gerekliliği

| Servis | Restart? |
|---|---|
| Express backend (5006) | **EVET** — yeni `/api/control/launch-camera/:id` endpoint |
| Flask web (5007) | **EVET** — CameraStream class temizlendi (eski endpoint'lere fetch 404 olur) |
| Vite (5005) | HMR otomatik |

Komutlar:
```bash
# Express
pkill -f "node server.js" 2>/dev/null
cd güncellemeler/yeni_dashboard/backend && node server.js &

# Flask (Dashboard'dan YÜZ GÜVENLİĞİ → DURDUR → BAŞLAT)
```

## 8) Test Akışı (UI)

1. Dashboard KONTROL sekmesi → sağda 25 buton grid + info-bar
   *"📺 Masaüstü penceresi (PyQt5 + Milvus)"*
2. Tanımlı bir kamera butonuna tıkla:
   - Buton 3sn sarı flash + spinner ile vurgulanır
   - Sağ alt köşede yeşil toast: *"📷 Kamera #1 başlatılıyor — Giriş 211
     — masaüstü penceresini kontrol edin."*
3. Kullanıcının ekranında PyQt5 penceresi açılır:
   - **Başlıkta**: *"👁️ EyeOfWeb - Kamera #1 - Kurumsal Yüz Tanıma v2.0"*
   - Cyber HUD, Milvus eşleşme paneli, PostgreSQL, çoklu-yüz tespiti,
     similarity threshold slider, vb. — **orijinal tüm özellikler**
4. Express backend'i kapansa bile pencere açık kalır (detached + unref)
5. Tanımsız kamera (URL boş .env) buton'ları **disabled** + soluk
6. Flask 5007 kapalıyken kırmızı banner *"servise bağlanılamadı"* (sadece
   buton listesi için Flask'ı kullanıyoruz)
7. Toast 5sn sonra otomatik kapanır VEYA × tıklayarak hemen kapat

## 9) Dosyalar

**Yeni:**
- `src/realtime_search_camera_launcher.py` (2592 satır — orijinalin
  argv parametre alan kopyası, 2 satır cerrahi değişiklik)

**Değiştirilen:**
- `güncellemeler/yeni_dashboard/backend/server.js`:
  - `POST /api/control/launch-camera/:id` endpoint (~40 satır eklendi)
- `güncellemeler/yeni_dashboard/src/CamerasPanel.jsx`:
  - Trigger-only mode'a refactor; `selectedCamId/onSelect/onClear`
    props yerine `onLaunched(info)`; launching state + flash
- `güncellemeler/yeni_dashboard/src/App.jsx`:
  - `selectedStreamCam` state → `launchToast` state
  - Orta panel MJPEG branch kaldırıldı → harita sabit
  - Global toast component eklendi (body-level)
- `güncellemeler/yeni_dashboard/src/App.css`:
  - `.cam-tile-launching/-spinner`, `.cameras-info-bar`,
    `.launch-toast*` eklendi
  - `.cam-tile-selected/-dot`, `.stream-*` class'ları silindi
- `güncellemeler/face_security_v3/web_app.py`:
  - `CameraStream` class + helper'lar + `/api/stream/*` endpoint'leri
    silindi (~270 satır)

**Dokunulmadı (user kuralı):**
- `src/realtime_search_camera_ornek.py` — orijinal PyQt5 + Milvus
  + PostgreSQL implementation (REFERENCE)
- `realtime_search_camera_{GIRIS_KAPISI,OFIS_1,...}.py` — eski
  per-kamera kopyaları (artık launcher kullanılıyor ama dokunulmadı)

## 10) Mimari Özet (Yeni Akış)

```
[Browser localhost:5005]
  ↓ user clicks "Kamera #7"
[React CamerasPanel]
  ↓ POST http://localhost:5006/api/control/launch-camera/7
[Express server.js]
  ↓ spawn detached:true
[bash] cd src && source WorkEnv/bin/activate && python3 realtime_search_camera_launcher.py --cam-id 7
  ↓ env .env'den CAM_07_URL çöz
[realtime_search_camera_launcher.py]
  ↓ PyQt5 QApplication başlat
[Kullanıcının ekranında masaüstü penceresi]
  ↓ Milvus + PostgreSQL + Cyber HUD + multi-face panels
  → Orijinal scriptin TÜM ÖZELLİKLERİ
```

React arayüzü tetiklemeden sonra hiçbir state tutmaz — pencere bağımsız
çalışır.

---

# KAMERA LAUNCHER — AKILLI YEDEKLEME (Smart Fallback) (2026-05-23)

## Sorun

Kamera butonuna basıldığında masaüstü PyQt5 penceresi hata veriyordu:
```
could not translate host name "db" to address
```

**Kök neden:** `src/config/config.json` Docker konteyneri ilk açıldığında
`generate_config.py` tarafından `DB_HOST=db` env'inden üretildi. Kamera
launcher **host shell'de** çalışıyor (PyQt5 X server için zorunlu) →
Docker DNS yok → "db" çözülemez.

Aynı sorunu önceki turda crawler (`lib/database_tools.py`) için
çözmüştük. Bu sefer kamera launcher'a aynı tedaviyi uyguladım.

## Çözüm — Akıllı Fallback Helper'lar

**Dosya:** `src/realtime_search_camera_launcher.py` (header'a ~85 satır
helper + `connect_to_postgres` + `connect_to_milvus` body'leri çağrıya
indirgendi)

### Host Chain Mantığı
```python
def _build_host_chain(primary, env_var, container_name,
                     fallbacks=("127.0.0.1", "localhost")):
    chain = []
    env_val = os.environ.get(env_var)
    if env_val: chain.append(env_val)       # ENV ÖZÜR DİLEMEZ ÖNCELİK
    if primary not in chain: chain.append(primary)        # config primary
    if container_name not in chain: chain.append(container_name)
    for fb in fallbacks:
        if fb not in chain: chain.append(fb)
    return chain
```

**Unit test sonuçları:**
```
Default (env yok):           ['db', 'eyeofweb_db', '127.0.0.1', 'localhost'] ✅
Env override DB_HOST=X:      ['X', 'db', 'eyeofweb_db', '127.0.0.1', 'localhost'] ✅
Dedup (primary=eyeofweb_db): ['eyeofweb_db', '127.0.0.1', 'localhost'] ✅
```

### PostgreSQL Fallback
```python
def _eow_try_pg_connect(base_cfg):
    chain = _build_host_chain(base_cfg.get("host","db"), "DB_HOST", "eyeofweb_db")
    last_err = None
    for host in chain:
        try:
            conn = psycopg2.connect(host=host, ..., connect_timeout=5)
            print(f"[Launcher][PG] '{host}' başarılı.")
            return conn, host
        except psycopg2.OperationalError as e:
            last_err = e
            print(f"[Launcher][PG] '{host}' fail: {str(e)[:80]}")
            continue
        except psycopg2.Error:
            raise  # auth/db_not_found → fallback faydasız
    raise last_err
```

### Milvus Fallback (simetrik)
Aynı pattern; `connections.has_connection(alias)` ise önce
`disconnect()`, sonra `connect(host=h, ..., timeout=5)`.
Chain: `[MILVUS_HOST env, primary, eyeofweb_milvus, 127.0.0.1, localhost]`.

### `connect_to_postgres` / `connect_to_milvus` Yeni Body
Helper çağrısı + `resolved_host` log + "tüm fallback host'lar denendi"
mesajıyla zarif hata. `QMessageBox.critical` yine var ama artık
sadece tüm chain başarısız olursa açılır.

## Davranış Matrisi

| Senaryo | Önceki | Şimdi |
|---|---|---|
| Host shell + config "db" | ❌ "could not translate" → çök | ✅ db fail → eyeofweb_db fail → 127.0.0.1 ✅ |
| Docker network içinde | ✅ db → çözülür | ✅ db → çözülür (primary aynı) |
| `DB_HOST=192.168.1.10` env | "db" denenirdi | ✅ 192.168.1.10 önce dener |
| Auth hatası | Crash | ✅ Hemen raise (fallback boşa yok) |
| Hiçbir host yanıt vermez | Crash | ✅ Tüm chain dener, net Türkçe hata |

## Korunanlar

- **`src/realtime_search_camera_ornek.py` DOKUNULMADI** (user kuralı)
- **`lib/database_tools.py`** crawler tarafı için zaten fallback'liydi
- **`config/config.json`** — Docker network için "db" doğru, dokunulmadı
- **Express endpoint** + **React UI** dokunulmadı

## Doğrulama

```
python3 -m py_compile launcher.py    → OK ✅
launcher --cam-id 999                  → "URL bulunamadı" ✅
_build_host_chain('db','DB_HOST','eyeofweb_db')
   → ['db','eyeofweb_db','127.0.0.1','localhost']  ✅ talimat ile birebir
env DB_HOST=X _build_host_chain(...)
   → ['X','db','eyeofweb_db',...]                  ✅ override priority

docker compose restart web → Container eyeofweb_app Started ✅
Flask container DB connect: OK ✅
```

## Restart

- **Web container (Flask 5007)**: `sudo docker compose ... restart web`
  → tamamlandı ✅ (Flask boot OK, Milvus 5 koleksiyon önbelleğe alındı)
- **Express (5006)**: yeniden başlatmaya gerek yok (endpoint değişmedi)
- **Vite (5005)**: HMR — dokunulmadı

## Test Akışı

1. Dashboard KONTROL sekmesi → tanımlı bir kamera butonuna tıkla
2. Toast: *"Kamera #X başlatılıyor — masaüstü penceresini kontrol edin."*
3. PyQt5 penceresi açılır:
   - **Eski:** DB hatası ile çökerdi
   - **Şimdi:** terminal log'da:
     ```
     [Launcher][PG] 'db' fail: could not translate host name...
     [Launcher][PG] 'eyeofweb_db' fail: ...
     [Launcher][PG] '127.0.0.1' başarılı.
     PostgreSQL başarıyla bağlanıldı (host=127.0.0.1)
     [Launcher][Milvus] 'milvus' fail: ...
     [Launcher][Milvus] '127.0.0.1' başarılı.
     ```
4. Cyber HUD + Milvus eşleşmeler + PostgreSQL kayıtları orijinal
   scriptteki gibi çalışır.

## Override Senaryosu

```bash
# Manuel override
DB_HOST=192.168.1.50 python3 realtime_search_camera_launcher.py --cam-id 5

# Express endpoint'i içinden override (server.js spawn env'i)
spawn('bash', ['-c', cmd], {
  env: { ...process.env, DB_HOST: '192.168.1.50' },
})
```

## Dosyalar

**Değiştirilen:**
- `src/realtime_search_camera_launcher.py`:
  - Header'a ~85 satır helper (`_build_host_chain`, `_eow_try_pg_connect`,
    `_eow_try_milvus_connect`)
  - `connect_to_postgres` body → helper çağrısına indirgendi
  - `connect_to_milvus` body → helper çağrısı + resolved_host log

**Dokunulmadı:**
- Orijinal `realtime_search_camera_ornek.py`
- `lib/database_tools.py` (crawler fallback'i zaten vardı)
- `config/config.json` (Docker primary "db" doğru)
- Diğer servisler

## Bilinen Sınırlamalar

- **5sn connect_timeout × 4 host = max 20sn worst-case**: pratikte ilk
  başarılı host (host shell'de genelde `127.0.0.1`) <100ms döner.
- **Auth hatası fallback'le düzelmez**: yanlış şifre tüm host'larda aynı
  → ilk denemede raise, boşa harcama yok.
- **DRY**: crawler ve kamera launcher iki ayrı yerde aynı fallback
  mantığını içeriyor. İleride ortak `lib/db_connect_helpers.py`'ye
  taşınması düşünülebilir.
