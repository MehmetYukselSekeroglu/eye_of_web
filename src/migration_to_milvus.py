import psycopg2
import psycopg2.extras # For executemany
from pymilvus import connections, Collection, utility
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import datetime
import numpy as np  # PostgreSQL vector tip dönüşümleri için

# --- Yapılandırma ---
# Kaynak PostgreSQL Bağlantı Bilgileri (ESKİ ŞEMANIN OLDUĞU VERİTABANI)
PG_SOURCE_HOST = "localhost"
PG_SOURCE_PORT = "5432"
PG_SOURCE_USER = "postgres"  # PostgreSQL kullanıcı adınız
PG_SOURCE_PASSWORD = "password"  # PostgreSQL şifreniz
PG_SOURCE_DB = "EyeOfWeb"  # Eski şemanın bulunduğu veritabanı adı

# Hedef PostgreSQL Bağlantı Bilgileri (YENİ ŞEMANIN OLDUĞU VERİTABANI)
PG_TARGET_HOST = "localhost"
PG_TARGET_PORT = "5432"
PG_TARGET_USER = "postgres"  # PostgreSQL kullanıcı adınız
PG_TARGET_PASSWORD = "password"  # PostgreSQL şifreniz
PG_TARGET_DB = "EyeOfWebMilvus"  # Yeni şemanın bulunduğu veritabanı adı

# Milvus Bağlantı Bilgileri
MILVUS_HOST = "localhost"
MILVUS_PORT = "19530"
MILVUS_CONNECTION_ALIAS = "migration_alias" # Betik için özel bir bağlantı alias'ı

# İşlem Parametreleri
MAX_THREADS = 10
BATCH_SIZE = 100  # Tek seferde işlenecek kayıt sayısı

# --- Tablo ve Koleksiyon Eşleme Yapılandırması ---
# Her bir sözlük bir tablonun migrasyonunu tanımlar:
# - "sql_table": PostgreSQL'deki kaynak tablo adı (eski şemada).
# - "sql_select_fields": SQL'den okunacak sütunlar (ilk sütun her zaman tablonun birincil anahtarı olmalı).
# - "milvus_collection_name": Hedef Milvus koleksiyon adı.
# - "milvus_fields_to_insert": Milvus'a eklenecek alan adları (transform_func'ın döndürdüğü sırayla).
# - "sql_id_column": SQL tablosundaki orijinal birincil anahtar sütununun adı.
# - "sql_milvus_id_column": SQL tablosuna eklenecek/güncellenecek Milvus ID sütununun adı.
# - "drop_sql_columns": SQL tablosundan silinecek sütunların listesi.
# - "transform_func": SQL satırını (sözlük olarak) Milvus'a eklenecek veri listesine dönüştüren fonksiyon.
MIGRATION_CONFIG = [
    {
        "sql_table": "CustomFaceStorage", # Kaynak DB'deki tablo adı
        "sql_select_fields": ["ID", "FaceEmbeddingData", "Landmarks2d", "FaceBox", "DetectionScore", "FaceGender", "FaceAge", "DetectionDate", "FaceName", "FaceDescription", "FaceImage", "FaceImageHash"], # FaceDescription ve FaceImage eklendi
        "milvus_collection_name": "CustomFaceStorageMilvus",
        "milvus_fields_to_insert": ["face_embedding_data", "landmarks_2d", "face_box", "detection_score", "face_gender", "face_age", "detection_date_ts", "face_name", "face_image_hash"],
        "sql_id_column": "ID", # Kaynak tablodaki PK
        "sql_milvus_id_column": "MilvusID", # Kaynak tablodaki işleme/Milvus ID işaretleyici sütunu
        "transform_func_milvus_dict": lambda r, m_fields: { # Milvus için veri hazırlar
            m_fields[0]: r["FaceEmbeddingData"].tolist() if hasattr(r["FaceEmbeddingData"], 'tolist') else r["FaceEmbeddingData"],
            m_fields[1]: r["Landmarks2d"].tolist() if hasattr(r["Landmarks2d"], 'tolist') else r["Landmarks2d"],
            m_fields[2]: r["FaceBox"].tolist() if hasattr(r["FaceBox"], 'tolist') else r["FaceBox"],
            m_fields[3]: float(r["DetectionScore"]),
            m_fields[4]: bool(r["FaceGender"]) if r["FaceGender"] is not None else False,
            m_fields[5]: int(r["FaceAge"]) if r["FaceAge"] is not None else 0,
            m_fields[6]: int(r["DetectionDate"].timestamp()) if r["DetectionDate"] is not None else 0,
            m_fields[7]: str(r["FaceName"]),
            m_fields[8]: str(r["FaceImageHash"])
        },
        "sql_target_table_name": "CustomFaceStorage", # Hedef DB'deki tablo adı
        "sql_target_insert_columns": ["MilvusID", "FaceName", "FaceDescription", "FaceImage", "FaceImageHash", "DetectionDate"], # Hedef tabloya eklenecek sütunlar (PK hariç)
        "transform_func_sql_target_tuple": lambda r_source, milvus_id: (
            milvus_id,
            str(r_source["FaceName"]),
            r_source["FaceDescription"],
            r_source["FaceImage"], # BYTEA
            str(r_source["FaceImageHash"]),
            r_source["DetectionDate"]
        )
    },
    {
        "sql_table": "WhiteListFaces",
        "sql_select_fields": ["ID", "FaceEmbeddingData", "Landmarks2d", "FaceBox", "DetectionScore", "FaceGender", "FaceAge", "DetectionDate", "FaceName", "FaceDescription", "FaceImage", "FaceImageHash"],
        "milvus_collection_name": "WhiteListFacesMilvus",
        "milvus_fields_to_insert": ["face_embedding_data", "landmarks_2d", "face_box", "detection_score", "face_gender", "face_age", "detection_date_ts", "face_name", "face_image_hash"],
        "sql_id_column": "ID",
        "sql_milvus_id_column": "MilvusID",
        "transform_func_milvus_dict": lambda r, m_fields: { # Milvus için veri hazırlar
            m_fields[0]: r["FaceEmbeddingData"].tolist() if hasattr(r["FaceEmbeddingData"], 'tolist') else r["FaceEmbeddingData"],
            m_fields[1]: r["Landmarks2d"].tolist() if hasattr(r["Landmarks2d"], 'tolist') else r["Landmarks2d"],
            m_fields[2]: r["FaceBox"].tolist() if hasattr(r["FaceBox"], 'tolist') else r["FaceBox"],
            m_fields[3]: float(r["DetectionScore"]),
            m_fields[4]: bool(r["FaceGender"]) if r["FaceGender"] is not None else False,
            m_fields[5]: int(r["FaceAge"]) if r["FaceAge"] is not None else 0,
            m_fields[6]: int(r["DetectionDate"].timestamp()) if r["DetectionDate"] is not None else 0,
            m_fields[7]: str(r["FaceName"]),
            m_fields[8]: str(r["FaceImageHash"])
        },
        "sql_target_table_name": "WhiteListFaces",
        "sql_target_insert_columns": ["MilvusID", "FaceName", "FaceDescription", "FaceImage", "FaceImageHash", "DetectionDate"],
        "transform_func_sql_target_tuple": lambda r_source, milvus_id: (
            milvus_id,
            str(r_source["FaceName"]),
            r_source["FaceDescription"],
            r_source["FaceImage"],
            str(r_source["FaceImageHash"]),
            r_source["DetectionDate"]
        )
    },
    {
        "sql_table": "ExternalFaceStorage",
        "sql_select_fields": ["ID", "FaceEmbeddingData", "Landmarks2d", "FaceBox", "DetectionScore", "FaceGender", "FaceAge", "Alarm", "DetectionDate", "FaceName", "FaceDescription", "ImageData", "ImageHash"], # ImageData, FaceDescription eklendi
        "milvus_collection_name": "ExternalFaceStorageMilvus",
        "milvus_fields_to_insert": ["face_embedding_data", "landmarks_2d", "face_box", "detection_score", "face_gender", "face_age", "alarm", "detection_date_ts", "face_name", "image_hash"],
        "sql_id_column": "ID",
        "sql_milvus_id_column": "MilvusID",
        "transform_func_milvus_dict": lambda r, m_fields: { # Milvus için veri hazırlar
            m_fields[0]: r["FaceEmbeddingData"].tolist() if hasattr(r["FaceEmbeddingData"], 'tolist') else r["FaceEmbeddingData"],
            m_fields[1]: r["Landmarks2d"].tolist() if hasattr(r["Landmarks2d"], 'tolist') else r["Landmarks2d"],
            m_fields[2]: r["FaceBox"].tolist() if hasattr(r["FaceBox"], 'tolist') else r["FaceBox"],
            m_fields[3]: float(r["DetectionScore"]),
            m_fields[4]: bool(r["FaceGender"]) if r["FaceGender"] is not None else False,
            m_fields[5]: int(r["FaceAge"]) if r["FaceAge"] is not None else 0,
            m_fields[6]: bool(r["Alarm"]) if r["Alarm"] is not None else False,
            m_fields[7]: int(r["DetectionDate"].timestamp()) if r["DetectionDate"] is not None else 0,
            m_fields[8]: str(r["FaceName"]),
            m_fields[9]: str(r["ImageHash"])
        },
        "sql_target_table_name": "ExternalFaceStorage",
        "sql_target_insert_columns": ["MilvusID", "ImageData", "ImageHash", "FaceName", "FaceDescription", "Alarm", "DetectionDate"],
        "transform_func_sql_target_tuple": lambda r_source, milvus_id: (
            milvus_id,
            r_source["ImageData"],
            str(r_source["ImageHash"]),
            str(r_source["FaceName"]),
            r_source["FaceDescription"],
            bool(r_source["Alarm"]) if r_source["Alarm"] is not None else False,
            r_source["DetectionDate"]
        )
    },
    {
        "sql_table": "EgmArananlar",
        "sql_select_fields": ["ID", "FaceEmbeddingData", "Landmarks2d", "FaceBox", "DetectionScore", "FaceGender", "FaceAge", "DetectionDate", "FaceName", "Organizer", "OrganizerLevel", "BirthDateAndLocation", "ImageData", "ImageHash"], # ImageData eklendi
        "milvus_collection_name": "EgmArananlarMilvus",
        "milvus_fields_to_insert": ["face_embedding_data", "landmarks_2d", "face_box", "detection_score", "face_gender", "face_age", "detection_date_ts", "face_name", "organizer", "organizer_level", "birth_date_and_location", "image_hash"],
        "sql_id_column": "ID",
        "sql_milvus_id_column": "MilvusID",
        "transform_func_milvus_dict": lambda r, m_fields: { # Milvus için veri hazırlar
            m_fields[0]: r["FaceEmbeddingData"].tolist() if hasattr(r["FaceEmbeddingData"], 'tolist') else r["FaceEmbeddingData"],
            m_fields[1]: r["Landmarks2d"].tolist() if hasattr(r["Landmarks2d"], 'tolist') else r["Landmarks2d"],
            m_fields[2]: r["FaceBox"].tolist() if hasattr(r["FaceBox"], 'tolist') else r["FaceBox"],
            m_fields[3]: float(r["DetectionScore"]),
            m_fields[4]: bool(r["FaceGender"]) if r["FaceGender"] is not None else False,
            m_fields[5]: int(r["FaceAge"]) if r["FaceAge"] is not None else 0,
            m_fields[6]: int(r["DetectionDate"].timestamp()) if r["DetectionDate"] is not None else 0,
            m_fields[7]: str(r["FaceName"]),
            m_fields[8]: str(r["Organizer"]),
            m_fields[9]: str(r["OrganizerLevel"]),
            m_fields[10]: str(r["BirthDateAndLocation"]),
            m_fields[11]: str(r["ImageHash"])
        },
        "sql_target_table_name": "EgmArananlar",
        "sql_target_insert_columns": ["MilvusID", "ImageData", "ImageHash", "FaceName", "Organizer", "OrganizerLevel", "BirthDateAndLocation", "DetectionDate"],
        "transform_func_sql_target_tuple": lambda r_source, milvus_id: (
            milvus_id,
            r_source["ImageData"],
            str(r_source["ImageHash"]),
            str(r_source["FaceName"]),
            str(r_source["Organizer"]),
            str(r_source["OrganizerLevel"]),
            str(r_source["BirthDateAndLocation"]),
            r_source["DetectionDate"]
        )
    },
    {
        "sql_table": "EyeOfWebFaceID", # Kaynak
        "sql_select_fields": ["ID", "FaceEmbeddingData", "Landmarks2d", "FaceBox", "DetectionScore", "FaceGender", "FaceAge", "DetectionDate"],
        "milvus_collection_name": "EyeOfWebFaceDataMilvus",
        "milvus_fields_to_insert": ["face_embedding_data", "landmarks_2d", "face_box", "detection_score", "face_gender", "face_age", "detection_date_ts"],
        "sql_id_column": "ID", # Kaynak tablodaki PK
        "sql_milvus_id_column": "MilvusRefID", # Kaynak tablodaki işleme/Milvus ID işaretleyici sütunu
        "transform_func_milvus_dict": lambda r, m_fields: { # Milvus için veri hazırlar
            m_fields[0]: r["FaceEmbeddingData"].tolist() if hasattr(r["FaceEmbeddingData"], 'tolist') else r["FaceEmbeddingData"],
            m_fields[1]: r["Landmarks2d"].tolist() if hasattr(r["Landmarks2d"], 'tolist') else r["Landmarks2d"],
            m_fields[2]: r["FaceBox"].tolist() if hasattr(r["FaceBox"], 'tolist') else r["FaceBox"],
            m_fields[3]: float(r["DetectionScore"]),
            m_fields[4]: bool(r["FaceGender"]) if r["FaceGender"] is not None else False,
            m_fields[5]: int(r["FaceAge"]) if r["FaceAge"] is not None else 0,
            m_fields[6]: int(r["DetectionDate"].timestamp()) if r["DetectionDate"] is not None else 0
        },
        "sql_target_table_name": "EyeOfWebFaceID", # Hedef DB'deki tablo adı
        "sql_target_insert_columns": ["MilvusRefID", "DetectionDate"], # Hedef tabloya eklenecek sütunlar
        "transform_func_sql_target_tuple": lambda r_source, milvus_id: (
            milvus_id,
            r_source["DetectionDate"]
        )
    }
]

# --- Helper Function to Connect and Manage Collections ---
def get_milvus_collection(collection_name):
    """Helper function to get a Milvus collection object."""
    if not utility.has_collection(collection_name, using=MILVUS_CONNECTION_ALIAS):
        # This script assumes collections are already created by MILVUS_SCHEMA_GENERATOR.py
        raise Exception(f"Milvus collection '{collection_name}' does not exist. Please run the schema generator first.")
    collection = Collection(collection_name, using=MILVUS_CONNECTION_ALIAS)
    collection.load() # Ensure collection is loaded for search/insert
    return collection

# PostgreSQL vector tipini işlemek için adaptör
class VectorAdapter:
    def __init__(self):
        self._adapters = {}

    def register(self, conn):
        try:
            # PostgreSQL'de pgvector kullanıldığını varsayıyoruz
            cur = conn.cursor()
            cur.execute("SELECT NULL::vector")
            vector_oid = cur.description[0][1]
            self._adapters[vector_oid] = lambda x: self._cast(x)
            psycopg2.extensions.register_type(
                psycopg2.extensions.new_type(
                    (vector_oid,), "VECTOR", lambda value, cur: self._cast(value)
                ),
                conn
            )
            cur.close()
            print("PostgreSQL vector tipi adaptörü başarıyla kaydedildi.")
        except Exception as e:
            print(f"PostgreSQL vector tipi adaptörü kaydedilirken hata: {e}")

    def _cast(self, value):
        if value is None:
            return None
        # PostgreSQL vector formatını numpy array'ine çevir
        if value.startswith('[') and value.endswith(']'):
            # Bracket'li format
            values = value[1:-1].split(',')
            return np.array([float(v) for v in values], dtype=float)
        else:
            # Alternatif format
            values = value.split(',')
            return np.array([float(v) for v in values], dtype=float)

def migrate_table_data(table_config):
    """Migrates data for a single table configuration."""
    source_table_name = table_config["sql_table"]
    target_table_name = table_config["sql_target_table_name"]
    sql_select_cols = table_config["sql_select_fields"]
    select_fields_str = ", ".join([f'"{col}"' for col in sql_select_cols])
    sql_id_col_name = table_config["sql_id_column"]
    sql_milvus_id_marker_col_name = table_config["sql_milvus_id_column"]
    target_insert_cols = table_config["sql_target_insert_columns"]
    target_insert_cols_str = ", ".join([f'"{col}"' for col in target_insert_cols])
    target_insert_placeholders = ", ".join(["%s"] * len(target_insert_cols))

    stats = {"table": source_table_name, "read_from_source": 0, "milvus_inserts_attempted": 0, "milvus_inserts_succeeded": 0, "target_db_inserts": 0, "source_db_updates_marked": 0, "errors": 0}
    start_time = time.time()
    print(f"[{source_table_name} -> {target_table_name}] Migrasyon başlıyor...")

    pg_source_conn_read = None  # Okuma için ayrı bağlantı
    pg_source_conn_write = None # Yazma (işaretleme) için ayrı bağlantı
    pg_target_conn = None
    try:
        # Kaynak ve Hedef DB bağlantıları
        pg_source_conn_read = psycopg2.connect(host=PG_SOURCE_HOST, port=PG_SOURCE_PORT, dbname=PG_SOURCE_DB, user=PG_SOURCE_USER, password=PG_SOURCE_PASSWORD)
        pg_source_conn_write = psycopg2.connect(host=PG_SOURCE_HOST, port=PG_SOURCE_PORT, dbname=PG_SOURCE_DB, user=PG_SOURCE_USER, password=PG_SOURCE_PASSWORD)
        pg_target_conn = psycopg2.connect(host=PG_TARGET_HOST, port=PG_TARGET_PORT, dbname=PG_TARGET_DB, user=PG_TARGET_USER, password=PG_TARGET_PASSWORD)
        pg_target_conn.autocommit = False

        # Kaynak DB okuma bağlantısı için vektör adaptörünü kaydet
        vector_adapter = VectorAdapter()
        vector_adapter.register(pg_source_conn_read)

        # Kaynak DB'de işaretleme sütununun varlığını kontrol et (yazma bağlantısı üzerinden)
        with pg_source_conn_write.cursor() as cursor_check:
            cursor_check.execute(f"""
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s AND column_name = %s;
            """, (source_table_name, sql_milvus_id_marker_col_name))
            if cursor_check.fetchone() is None:
                print(f"[{source_table_name}] UYARI: Kaynak tabloda işaretleme sütunu '{sql_milvus_id_marker_col_name}' bulunamadı!")
            else:
                print(f"[{source_table_name}] Kaynak tabloda işaretleme sütunu '{sql_milvus_id_marker_col_name}' mevcut.")

        milvus_collection = get_milvus_collection(table_config["milvus_collection_name"])

        # İşlenmemiş verileri Kaynak DB'den çek (OKUMA BAĞLANTISI ile)
        with pg_source_conn_read.cursor(name=f"{source_table_name}_migration_cursor", cursor_factory=psycopg2.extras.RealDictCursor) as source_cursor:
            source_cursor.execute(f'SELECT {select_fields_str} FROM "{source_table_name}" WHERE "{sql_milvus_id_marker_col_name}" IS NULL ORDER BY "{sql_id_col_name}";')

            while True:
                source_sql_batch_dicts = source_cursor.fetchmany(BATCH_SIZE)
                if not source_sql_batch_dicts:
                    break

                stats["read_from_source"] += len(source_sql_batch_dicts)
                milvus_data_to_insert = []
                sql_target_data_to_insert = []
                original_source_sql_ids_batch = []
                processed_mappings = {} # sql_id -> milvus_id

                # 1. Verileri Milvus için hazırla
                for row_dict in source_sql_batch_dicts:
                    try:
                        data_for_milvus = table_config["transform_func_milvus_dict"](row_dict, table_config["milvus_fields_to_insert"])
                        milvus_data_to_insert.append(data_for_milvus)
                        original_source_sql_ids_batch.append(row_dict[sql_id_col_name])
                    except Exception as e:
                        stats["errors"] += 1
                        print(f"[{source_table_name}] Milvus için veri dönüştürme hatası (Kaynak SQL ID: {row_dict.get(sql_id_col_name, 'N/A')}): {e}")
                        continue # Bu satırı atla

                if not milvus_data_to_insert:
                    if len(source_sql_batch_dicts) > 0:
                         print(f"[{source_table_name}] Batch'teki {len(source_sql_batch_dicts)} satırın hiçbiri Milvus için hazırlanamadı.")
                    continue # Sonraki batch'e geç

                # 2. Milvus'a Ekle
                inserted_milvus_ids = []
                try:
                    stats["milvus_inserts_attempted"] += len(milvus_data_to_insert)
                    mutation_result = milvus_collection.insert(milvus_data_to_insert)
                    inserted_milvus_ids = mutation_result.primary_keys
                    stats["milvus_inserts_succeeded"] += len(inserted_milvus_ids)

                    # Başarılı eklenen Milvus ID'lerini orijinal SQL ID'leri ile eşle
                    # Insert sırasının korunduğunu varsayıyoruz
                    if len(inserted_milvus_ids) == len(original_source_sql_ids_batch):
                        for i in range(len(inserted_milvus_ids)):
                            processed_mappings[original_source_sql_ids_batch[i]] = inserted_milvus_ids[i]
                    else:
                         # Eğer sayılar eşleşmezse (Milvus tarafında kısmi hata?), logla ve devam etme
                         print(f"[{source_table_name}] UYARI: Milvus ID sayısı ({len(inserted_milvus_ids)}) ile Kaynak SQL ID sayısı ({len(original_source_sql_ids_batch)}) eşleşmiyor! Bu batch için SQL Target insert ve Source update atlanacak.")
                         stats["errors"] += len(original_source_sql_ids_batch) # Hata olarak say
                         # Bu batch'i burada durdurmak en güvenlisi olabilir
                         continue # Sonraki batch'e geç

                except Exception as e:
                    stats["errors"] += len(milvus_data_to_insert) # Başarısız insert denemesi olarak say
                    print(f"[{source_table_name}] Milvus'a ekleme hatası (batch): {e}")
                    # Bu batch işlenemedi, sonraki batch'e geç
                    continue

                if not processed_mappings: # Eğer Milvus'a hiçbir şey eklenemediyse veya eşleme yapılamadıysa
                    continue # Sonraki batch'e geç

                # 3. Verileri Hedef SQL DB için hazırla
                sql_target_tuples_to_insert = []
                sql_ids_to_update_in_source = []
                milvus_ids_for_source_update = []

                for row_dict in source_sql_batch_dicts:
                    original_sql_id = row_dict[sql_id_col_name]
                    if original_sql_id in processed_mappings:
                        milvus_id = processed_mappings[original_sql_id]
                        try:
                            data_for_target_sql = table_config["transform_func_sql_target_tuple"](row_dict, milvus_id)
                            sql_target_tuples_to_insert.append(data_for_target_sql)
                            # Kaynak DB'yi güncellemek için ID'leri sakla
                            sql_ids_to_update_in_source.append(original_sql_id)
                            milvus_ids_for_source_update.append(milvus_id)
                        except Exception as e:
                            stats["errors"] += 1
                            print(f"[{source_table_name}] Hedef SQL için veri dönüştürme hatası (Kaynak SQL ID: {original_sql_id}): {e}")
                            # Bu satır hedef DB'ye eklenemeyecek, kaynakta güncellenmeyecek
                            continue

                if not sql_target_tuples_to_insert:
                    print(f"[{source_table_name}] Milvus'a eklenen veriler ({len(inserted_milvus_ids)}) hedef SQL için hazırlanamadı.")
                    continue # Sonraki batch'e geç

                # 4. Hedef DB'ye Ekle ve Kaynak DB'yi Güncelle (Transaction İçinde)
                target_inserted_count = 0
                source_updated_count = 0
                try:
                    # Hedef DB'ye ekle (pg_target_conn ile)
                    with pg_target_conn.cursor() as target_cursor:
                        insert_query = f'INSERT INTO "{target_table_name}" ({target_insert_cols_str}) VALUES ({target_insert_placeholders});'
                        psycopg2.extras.execute_batch(target_cursor, insert_query, sql_target_tuples_to_insert)
                        target_inserted_count = len(sql_target_tuples_to_insert)
                        stats["target_db_inserts"] += target_inserted_count

                    # Hedef'e ekleme başarılıysa, Kaynak DB'deki satırları işaretle (YAZMA BAĞLANTISI ile)
                    if target_inserted_count > 0:
                        source_update_values = list(zip(milvus_ids_for_source_update, sql_ids_to_update_in_source))
                        if source_update_values:
                             with pg_source_conn_write.cursor() as source_update_cursor: # Yazma bağlantısı cursor'ı
                                 update_query = f'UPDATE "{source_table_name}" SET "{sql_milvus_id_marker_col_name}" = %s WHERE "{sql_id_col_name}" = %s;'
                                 psycopg2.extras.execute_batch(source_update_cursor, update_query, source_update_values)
                             pg_source_conn_write.commit() # Kaynak DB yazma bağlantısını commit et
                             source_updated_count = len(source_update_values)
                             stats["source_db_updates_marked"] += source_updated_count

                    pg_target_conn.commit() # Hedef DB eklemesini commit et

                    print(f"[{source_table_name} -> {target_table_name}] {stats['read_from_source']} satır okundu. Batch Milvus Ekleme: {len(inserted_milvus_ids)}, Hedef DB Ekleme: {target_inserted_count}, Kaynak DB İşaretleme: {source_updated_count}")

                except Exception as e:
                    stats["errors"] += len(sql_target_tuples_to_insert) # Başarısız hedef insert veya kaynak update denemesi
                    if pg_target_conn and not pg_target_conn.closed:
                        try: pg_target_conn.rollback()
                        except psycopg2.Error: pass # Ignore rollback errors
                    if pg_source_conn_write and not pg_source_conn_write.closed: # Yazma bağlantısını rollback et
                        try: pg_source_conn_write.rollback()
                        except psycopg2.Error: pass # Ignore rollback errors
                    print(f"[{source_table_name} -> {target_table_name}] Hedef DB ekleme VEYA Kaynak DB işaretleme hatası (batch): {e}")
                    break # Hata sonrası bu tablonun işlenmesini durdur

    except (Exception, psycopg2.Error) as error:
        stats["errors"] += 1
        print(f"[{source_table_name} -> {target_table_name}] Ana migrasyon döngüsünde ciddi bir hata oluştu: {error}")
        # Ana hata durumunda rollback işlemleri, hedef ve HER İKİ kaynak bağlantısı için
        # Bağlantıların None olup olmadığını ve kapalı olup olmadığını kontrol et
        if pg_target_conn and not pg_target_conn.closed:
            try:
                pg_target_conn.rollback()
                print(f"[{target_table_name}] Hedef DB (Ana Hata) rollback denendi.")
            except psycopg2.Error as rb_err:
                print(f"[{target_table_name}] Hedef DB (Ana Hata) rollback sırasında hata: {rb_err}")
        if pg_source_conn_read and not pg_source_conn_read.closed:
            try:
                pg_source_conn_read.rollback()
                print(f"[{source_table_name}] Kaynak Okuma DB (Ana Hata) rollback denendi.")
            except psycopg2.Error as rb_err:
                print(f"[{source_table_name}] Kaynak Okuma DB (Ana Hata) rollback sırasında hata: {rb_err}")
        if pg_source_conn_write and not pg_source_conn_write.closed:
            try:
                pg_source_conn_write.rollback()
                print(f"[{source_table_name}] Kaynak Yazma DB (Ana Hata) rollback denendi.")
            except psycopg2.Error as rb_err:
                print(f"[{source_table_name}] Kaynak Yazma DB (Ana Hata) rollback sırasında hata: {rb_err}")
    finally:
        # Tüm bağlantıları kapat
        if pg_source_conn_read:
            try:
                pg_source_conn_read.close()
            except psycopg2.Error as close_err:
                 print(f"[{source_table_name}] Kaynak Okuma DB kapatılırken hata: {close_err}")
        if pg_source_conn_write:
            try:
                pg_source_conn_write.close()
            except psycopg2.Error as close_err:
                 print(f"[{source_table_name}] Kaynak Yazma DB kapatılırken hata: {close_err}")
        if pg_target_conn:
            try:
                pg_target_conn.close()
            except psycopg2.Error as close_err:
                 print(f"[{target_table_name}] Hedef DB kapatılırken hata: {close_err}")
        end_time = time.time()
        print(f"[{source_table_name} -> {target_table_name}] Migrasyon tamamlandı. Süre: {end_time - start_time:.2f} saniye. İstatistikler: {stats}")
    return stats

if __name__ == "__main__":
    overall_start_time = time.time()
    print("Milvus migrasyon betiği başlatılıyor...")
    print(f"Kaynak PostgreSQL: {PG_SOURCE_HOST}:{PG_SOURCE_PORT}, DB: {PG_SOURCE_DB}")
    print(f"Hedef PostgreSQL: {PG_TARGET_HOST}:{PG_TARGET_PORT}, DB: {PG_TARGET_DB}")
    print(f"Milvus: {MILVUS_HOST}:{MILVUS_PORT}")
    print(f"Max Threads: {MAX_THREADS}, Batch Size: {BATCH_SIZE}")

    # Milvus'a bir kez bağlan
    try:
        if not connections.has_connection(MILVUS_CONNECTION_ALIAS):
            connections.connect(
                alias=MILVUS_CONNECTION_ALIAS,
                host=MILVUS_HOST,
                port=MILVUS_PORT
            )
        print(f"Milvus'a '{MILVUS_CONNECTION_ALIAS}' alias'ı ile bağlanıldı.")
        # Milvus bağlantısını kontrol et
        if not utility.has_collection(MIGRATION_CONFIG[0]["milvus_collection_name"], using=MILVUS_CONNECTION_ALIAS): # Örnek bir koleksiyonu kontrol et
             print(f"UYARI: Milvus koleksiyonu '{MIGRATION_CONFIG[0]['milvus_collection_name']}' bulunamadı. Lütfen MILVUS_SCHEMA_GENERATOR.py betiğini çalıştırdığınızdan emin olun.")
             # Scriptin devam etmesine izin verilebilir, migrate_table_data içinde kontrol var.
    except Exception as e:
        print(f"Milvus'a bağlanırken hata oluştu: {e}. Betik durduruluyor.")
        exit(1)

    all_stats = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_config = {executor.submit(migrate_table_data, config): config for config in MIGRATION_CONFIG}
        for future in as_completed(future_to_config):
            config = future_to_config[future]
            try:
                stats = future.result()
                all_stats.append(stats)
            except Exception as exc:
                print(f"'{config['sql_table']}' tablosu için migrasyon iş parçacığında hata: {exc}")
                all_stats.append({"table": config['sql_table'], "errors": "Thread execution error", "exception": str(exc)})

    overall_end_time = time.time()
    print("\n--- Genel Migrasyon Sonuçları ---")
    total_read = 0
    total_milvus_attempted = 0
    total_milvus_succeeded = 0
    total_target_db_inserts = 0
    total_source_db_updates = 0
    total_errors = 0

    for s in all_stats:
        print(f"Tablo (Kaynak): {s.get('table', 'N/A')}")
        print(f"  SQL Kaynaktan Okunan: {s.get('read_from_source', 0)}")
        print(f"  Milvus Ekleme Denemesi: {s.get('milvus_inserts_attempted', 0)}")
        print(f"  Milvus Başarılı Ekleme: {s.get('milvus_inserts_succeeded', 0)}")
        print(f"  Hedef DB Ekleme: {s.get('target_db_inserts', 0)}")
        print(f"  Kaynak DB İşaretleme: {s.get('source_db_updates_marked', 0)}")
        print(f"  Hatalar: {s.get('errors', 0)}")
        if "exception" in s:
            print(f"  İstisna: {s['exception']}")
        
        total_read += s.get('read_from_source', 0)
        total_milvus_attempted += s.get('milvus_inserts_attempted', 0)
        total_milvus_succeeded += s.get('milvus_inserts_succeeded', 0)
        total_target_db_inserts += s.get('target_db_inserts', 0)
        total_source_db_updates += s.get('source_db_updates_marked', 0)
        total_errors += s.get('errors', 0)
        print("-" * 30)

    print("\n--- Toplam İstatistikler ---")
    print(f"Toplam SQL Kaynaktan Okunan: {total_read}")
    print(f"Toplam Milvus Ekleme Denemesi: {total_milvus_attempted}")
    print(f"Toplam Milvus Başarılı Ekleme: {total_milvus_succeeded}")
    print(f"Toplam Hedef DB Ekleme: {total_target_db_inserts}")
    print(f"Toplam Kaynak DB İşaretleme: {total_source_db_updates}")
    print(f"Toplam Hata: {total_errors}")
    print(f"Toplam Migrasyon Süresi: {overall_end_time - overall_start_time:.2f} saniye")

    # Milvus bağlantısını kapat
    if connections.has_connection(MILVUS_CONNECTION_ALIAS):
        connections.disconnect(MILVUS_CONNECTION_ALIAS)
        print(f"Milvus bağlantısı ('{MILVUS_CONNECTION_ALIAS}') kapatıldı.")

    print("Milvus migrasyon betiği tamamlandı.") 