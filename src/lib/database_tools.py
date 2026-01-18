#! /usr/bin/env python3
#! -*- coding: utf-8 -*-
#! author: Wesker

import psycopg2
import psycopg2.extensions
import psycopg2.pool
import psycopg2.extras
import re
import typing
import numpy
import cv2
from psycopg2.extras import DictCursor
import base64
from . import url_parser
from .output.consolePrint import p_info, p_error, p_warn, p_log
import traceback
import datetime
from lib.similarity_utils import calculate_similarity, NUMBA_AVAILABLE
from flask import current_app  # use_cuda bilgisi için
import numpy as np
from lib.compress_tools import compress_image, decompress_image
from psycopg2.extensions import register_adapter, AsIs
import ast
from sklearn.preprocessing import normalize as l2_normalize

# Milvus imports
from pymilvus import connections, utility, Collection
from pymilvus.exceptions import MilvusException, CollectionNotExistException

# <<< YENİ: Milvus Yapılandırması >>>
import os

# <<< YENİ: Milvus Yapılandırması >>>
MILVUS_HOST = os.environ.get("MILVUS_HOST", "localhost")
MILVUS_PORT = os.environ.get("MILVUS_PORT", "19530")
MILVUS_ALIAS_APP = os.environ.get("MILVUS_ALIAS_APP", "eow_milvus_app")
MILVUS_PASSWORD = os.environ.get(
    "MILVUS_PASSWORD", ""
)  # Default empty or fetch from secure env
MILVUS_USER = os.environ.get("MILVUS_USER", "")

# <<< YENİ: Milvus Koleksiyon Adları >>>
EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME = "EyeOfWebFaceDataMilvus"
CUSTOM_FACE_MILVUS_COLLECTION_NAME = "CustomFaceStorageMilvus"
WHITE_LIST_FACES_MILVUS_COLLECTION_NAME = "WhiteListFacesMilvus"
EXTERNAL_FACE_STORAGE_MILVUS_COLLECTION_NAME = "ExternalFaceStorageMilvus"
EGM_ARANANLAR_MILVUS_COLLECTION_NAME = "EgmArananlarMilvus"


# <<< GÜNCELLEME: Varsayılan DB Yeni DB >>>
def get_default_db_config():
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": os.environ.get("DB_PORT", "5432"),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", "postgres"),
        "database": os.environ.get("DB_NAME", "EyeOfWeb"),
    }


# <<< YENİ: Milvus Bağlantı Fonksiyonu >>>
def connect_to_milvus(alias=MILVUS_ALIAS_APP):
    try:
        if not connections.has_connection(alias):
            p_info(
                f"Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT} under alias '{alias}'..."
            )
            connections.connect(
                alias=alias,
                host=MILVUS_HOST,
                port=MILVUS_PORT,
                user=MILVUS_USER,
                password=MILVUS_PASSWORD,
            )
            p_log(f"Connected to Milvus alias '{alias}' successfully.")
        return True
    except MilvusException as e:
        p_error(f"Failed to connect to Milvus: {e}")
        return False


# <<< DÜZELTİLMİŞ: Milvus Koleksiyon Nesnesi Alma Fonksiyonu >>>
def get_milvus_collection(
    collection_name: str, alias: str = MILVUS_ALIAS_APP
) -> typing.Optional[Collection]:
    """
    Gets a loaded Milvus collection object.
    Returns None if connection or collection access/load fails.
    """
    if not connections.has_connection(alias):
        if not connect_to_milvus(alias):
            p_error(f"Failed to establish Milvus connection with alias '{alias}'.")
            return None

    try:
        if not utility.has_collection(collection_name, using=alias):
            p_error(
                f"Milvus collection '{collection_name}' does not exist under alias '{alias}'."
            )
            return None

        collection = Collection(collection_name, using=alias)

        # Yükleme durumunu al
        raw_current_load_state = utility.load_state(collection_name, using=alias)
        # String'e çevirip başında/sonunda olabilecek boşlukları temizle
        current_load_state_str = str(raw_current_load_state).strip()

        p_log(
            f"Collection '{collection_name}': Initial raw_load_state='{raw_current_load_state}', "
            f"processed_state='{current_load_state_str}', type='{type(raw_current_load_state)}'"
        )

        # İdeal olarak, PyMilvus'un LoadState enum'unu kullanın (eğer varsa ve sürümünüz destekliyorsa)
        # from pymilvus.client.constants import LoadState
        # expected_loaded_state_enum = LoadState.Loaded
        # is_currently_loaded = (raw_current_load_state == expected_loaded_state_enum)

        # String tabanlı kontrol (logdaki "Loaded" ifadesine dayanarak)
        # Bu, enum karşılaştırması mümkün değilse veya state string olarak geliyorsa kullanılır.
        is_currently_loaded = current_load_state_str == "Loaded"

        if not is_currently_loaded:
            p_warn(
                f"Collection '{collection_name}' is not fully loaded (State: '{current_load_state_str}'). Attempting to load..."
            )
            try:
                fields_to_load = []
                # Bu koleksiyonlar için belirli alanları yükle
                # Bu liste, MILVUS_SCHEMA_GENERATOR.py'deki indekslenmiş vektör alanlarıyla tutarlı olmalı
                if collection_name in [
                    EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME,
                    CUSTOM_FACE_MILVUS_COLLECTION_NAME,
                    WHITE_LIST_FACES_MILVUS_COLLECTION_NAME,
                    EXTERNAL_FACE_STORAGE_MILVUS_COLLECTION_NAME,
                    EGM_ARANANLAR_MILVUS_COLLECTION_NAME,
                ]:
                    # Bu alanlar, sağladığınız şema üreticisindeki tüm bu koleksiyonlar için ortaktır.
                    fields_to_load = ["face_embedding_data", "landmarks_2d", "face_box"]
                    p_info(
                        f"Attempting to load collection '{collection_name}' for specific vector fields: {fields_to_load}"
                    )
                    collection.load(
                        field_names=fields_to_load, _async=False
                    )  # _async=False senkron yükleme için
                else:
                    # Bilinmeyen veya farklı yapıdaki koleksiyonlar için genel yükleme
                    p_info(
                        f"Attempting a generic load for collection '{collection_name}'."
                    )
                    collection.load(_async=False)  # _async=False senkron yükleme için

                # Yükleme sonrası durumu tekrar kontrol et
                utility.wait_for_loading_complete(
                    collection_name, using=alias
                )  # Yüklemenin bitmesini bekle
                raw_final_load_state = utility.load_state(collection_name, using=alias)
                final_load_state_str = str(raw_final_load_state).strip()

                p_log(
                    f"Collection '{collection_name}': Post-load attempt raw_load_state='{raw_final_load_state}', "
                    f"processed_state='{final_load_state_str}', type='{type(raw_final_load_state)}'"
                )

                # is_finally_loaded = (raw_final_load_state == expected_loaded_state_enum) # Enum ile kontrol
                is_finally_loaded = (
                    final_load_state_str == "Loaded"
                )  # String ile kontrol

                if is_finally_loaded:
                    p_log(f"Collection '{collection_name}' successfully loaded.")
                else:
                    # Logdaki hata mesajı bu bloğa girildiğini gösteriyor, ANCAK final_load_state_str "Loaded" olarak loglanıyor.
                    # Bu, is_finally_loaded koşulunun False olduğu, yani final_load_state_str'ın "Loaded" olmadığı anlamına gelir
                    # (veya enum karşılaştırması başarısız oldu).
                    # Bu durum, str() dönüşümü ile doğrudan enum/string değeri arasında bir fark olduğunu gösterir.
                    p_error(
                        f"Failed to load Milvus collection '{collection_name}'. "
                        f"Final processed state: '{final_load_state_str}'. "
                        f"Raw state: '{raw_final_load_state}'. Type: '{type(raw_final_load_state)}'"
                    )

                    # Logdaki çelişkiyi gidermek için geçici bir ek kontrol:
                    # Eğer işlenmiş string "Loaded" içeriyorsa ama yukarıdaki eşitlik başarısızsa,
                    # bu bir enum-string uyumsuzluğu veya benzeri bir durum olabilir.
                    if "Loaded" in final_load_state_str and not is_finally_loaded:
                        p_warn(
                            f"WORKAROUND: Collection '{collection_name}' reported as '{final_load_state_str}' "
                            f"which contains 'Loaded', but strict equality failed. "
                            f"Proceeding as if loaded due to log discrepancy."
                        )
                        # Bu durumda koleksiyonu döndürmeyi deneyebiliriz, ancak bu ideal bir çözüm değildir.
                    else:
                        return None  # Yükleme başarısız olduysa None dön

            except MilvusException as load_err:
                p_error(
                    f"MilvusException during load attempt for '{collection_name}': {load_err}"
                )
                traceback.print_exc()
                return None
            except Exception as e:
                p_error(
                    f"Unexpected error during load attempt for '{collection_name}': {e}"
                )
                traceback.print_exc()
                return None
        else:
            p_log(
                f"Collection '{collection_name}' is already loaded (State: '{current_load_state_str}')."
            )

        return collection

    except (
        CollectionNotExistException
    ):  # pymilvus.exceptions altından import edildiğinden emin olun
        p_error(
            f"Milvus collection '{collection_name}' does not exist (caught by CollectionNotExistException)."
        )
        return None
    except MilvusException as e:
        p_error(f"MilvusException accessing Milvus collection '{collection_name}': {e}")
        traceback.print_exc()
        return None
    except Exception as e:
        p_error(f"Unexpected error getting Milvus collection '{collection_name}': {e}")
        traceback.print_exc()
        return None


# PostgreSQL için numpy array adaptörü (sadece float32 için, database_tools içinde INSERT ederken gerekebilir)
# Vektörleri DB'ye yazmıyorsak bu gereksiz olabilir.
# def addapt_numpy_float32_array(numpy_array):
#     # Vektörleri DB'ye yazmadığımız için buna gerek yok gibi.
#     # Emin olmak için yorumda bırakıyorum.
#     return AsIs("ARRAY[" + ",".join(map(str, numpy_array)) + "]")
# register_adapter(np.ndarray, addapt_numpy_float32_array)


def DirectConnectToDatabase(dbConfig: dict):
    return psycopg2.connect(**dbConfig)


def DirectReleaseConnection(connection: psycopg2.extensions.connection):
    connection.close()


class DatabaseTools:
    def __init__(self, dbConfig: dict = None):
        # Eğer dbConfig verilmezse varsayılanı kullan
        self.dbConfig = dbConfig if dbConfig is not None else get_default_db_config()

        # Milvus koleksiyonları ve bağlantıları için önbellek
        self._milvus_collections_cache = {}
        self._milvus_ref_id_cache = {}  # PG Face ID -> Milvus ID önbelleği

        # Başlangıçta Milvus'a bağlan ve sık kullanılan koleksiyonları yükle
        self._initialize_milvus_connections()

    def _initialize_milvus_connections(self):
        """Milvus bağlantısını başlatır ve sık kullanılan koleksiyonları yükler."""
        try:
            p_info("Milvus bağlantıları ve koleksiyonları başlatılıyor...")

            # Ana Milvus bağlantısını oluştur
            if not connect_to_milvus(MILVUS_ALIAS_APP):
                p_error(
                    "Ana Milvus bağlantısı kurulamadı! Koleksiyonlar yüklenemeyecek."
                )
                return

            # Sık kullanılan koleksiyonlar için ön-yükleme yap
            common_collections = [
                EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME,
                CUSTOM_FACE_MILVUS_COLLECTION_NAME,
                WHITE_LIST_FACES_MILVUS_COLLECTION_NAME,
                EXTERNAL_FACE_STORAGE_MILVUS_COLLECTION_NAME,
                EGM_ARANANLAR_MILVUS_COLLECTION_NAME,
            ]

            for collection_name in common_collections:
                try:
                    # Koleksiyonu yükle ve önbellekte sakla
                    collection = get_milvus_collection(collection_name)
                    if collection:
                        self._milvus_collections_cache[collection_name] = collection
                        p_info(
                            f"Milvus koleksiyonu önbelleğe alındı: {collection_name}"
                        )
                    else:
                        p_warn(f"Milvus koleksiyonu yüklenemedi: {collection_name}")
                except Exception as e:
                    p_error(
                        f"Milvus koleksiyonu {collection_name} önbelleğe alınırken hata: {e}"
                    )

            p_info(
                f"Milvus başlatma tamamlandı. {len(self._milvus_collections_cache)} koleksiyon önbelleğe alındı."
            )
        except Exception as e:
            p_error(f"Milvus bağlantıları başlatılırken hata: {e}")
            traceback.print_exc()

    def _get_cached_milvus_collection(self, collection_name: str) -> Collection:
        """Önbellekteki koleksiyonu döndürür veya yeni koleksiyon alıp önbelleğe kaydeder."""
        if collection_name in self._milvus_collections_cache:
            return self._milvus_collections_cache[collection_name]

        # Önbellekte yoksa yükle ve kaydet
        collection = get_milvus_collection(collection_name)
        if collection:
            self._milvus_collections_cache[collection_name] = collection
            p_log(f"Yeni Milvus koleksiyonu önbelleğe alındı: {collection_name}")
        return collection

    def connect(self) -> typing.Optional[psycopg2.extensions.connection]:
        """Connects to the configured PostgreSQL database."""
        try:
            connection = psycopg2.connect(**self.dbConfig)
            # Vektör adaptörünü burada kaydetme, çünkü yeni şemada vektör yok.
            return connection
        except psycopg2.Error as e:
            p_error(f"Database connection error: {e}")
            return None

    def insert_is_crawled(self, target_url: str) -> bool:
        _connection = self.connect()
        _cursor = _connection.cursor(cursor_factory=DictCursor)
        try:
            p_info(f"Inserting is_crawled for {target_url}")
            parsedUrl = url_parser.prepare_url(target_url=target_url)

            _baseDomainReturnID = None
            _pathReturnID = None
            _etcReturnID = None

            _baseDomain = parsedUrl["base_domain"]
            _protocol = parsedUrl["protocol"]
            _path = parsedUrl["path"]
            _etc = parsedUrl["etc"]

            _baseDomain = str(_baseDomain).lower()
            # _baseDomain = str(_baseDomain).replace("www.", "")

            # print(f"{target_url} -> {_baseDomain} -> {_path} -> {_etc}")

            if len(_etc) == 0:
                _etc = None

            if len(_path) == 0:
                _path = None

            if _protocol != None:
                _protocol = str(_protocol).lower()
            else:
                _protocol = "http"

            STATIC_SQL_COMMAND = (
                """SELECT "ID" FROM "BaseDomainID" WHERE "Domain" = %s"""
            )
            STATIC_DATA_TUPLE = (_baseDomain,)

            _cursor.execute(STATIC_SQL_COMMAND, STATIC_DATA_TUPLE)

            results = _cursor.fetchall()

            # p_error(results)

            if len(results) != 0:
                _baseDomainReturnID = results[0]["ID"]

            else:
                STATIC_SQL_COMMAND = """INSERT INTO "BaseDomainID" ("Domain") VALUES (%s) RETURNING "ID" """
                STATIC_DATA_TUPLE = (_baseDomain,)
                _cursor.execute(STATIC_SQL_COMMAND, STATIC_DATA_TUPLE)
                _connection.commit()
                _baseDomainReturnID = _cursor.fetchall()[0]["ID"]

            # p_info(f"BaseDomainID: {_baseDomainReturnID}")

            if _path != None:
                STATIC_SQL_COMMAND = (
                    """SELECT "ID" FROM "UrlPathID" WHERE "Path" = %s"""
                )
                STATIC_DATA_TUPLE = (_path,)

                _cursor.execute(STATIC_SQL_COMMAND, STATIC_DATA_TUPLE)

                results = _cursor.fetchall()

                if len(results) != 0:
                    _pathReturnID = results[0]["ID"]

                else:
                    STATIC_SQL_COMMAND = """INSERT INTO "UrlPathID" ("Path") VALUES (%s) RETURNING "ID" """
                    STATIC_DATA_TUPLE = (_path,)
                    _cursor.execute(STATIC_SQL_COMMAND, STATIC_DATA_TUPLE)
                    _connection.commit()
                    _pathReturnID = _cursor.fetchall()[0]["ID"]

            if _etc != None:
                STATIC_SQL_COMMAND = """SELECT "ID" FROM "UrlEtcID" WHERE "Etc" = %s"""
                STATIC_DATA_TUPLE = (_etc,)

                _cursor.execute(STATIC_SQL_COMMAND, STATIC_DATA_TUPLE)

                results = _cursor.fetchall()

                if len(results) != 0:
                    _etcReturnID = results[0]["ID"]

                else:
                    STATIC_SQL_COMMAND = (
                        """INSERT INTO "UrlEtcID" ("Etc") VALUES (%s) RETURNING "ID" """
                    )
                    STATIC_DATA_TUPLE = (_etc,)
                    _cursor.execute(STATIC_SQL_COMMAND, STATIC_DATA_TUPLE)
                    _connection.commit()
                    _etcReturnID = _cursor.fetchall()[0]["ID"]

            STATIC_SQL_COMMAND = """
            SELECT "ID","FirstCrawlDate" FROM "CrawledAddress" WHERE "Protocol" = %s AND "BaseDomainID" = %s AND 
            (("BaseUrlPathID" IS NULL AND %s IS NULL) OR "BaseUrlPathID" = %s) AND 
            (("BaseUrlEtcID" IS NULL AND %s IS NULL) OR "BaseUrlEtcID" = %s)
            """

            STATIC_DATA_TUPLE = (
                _protocol,
                _baseDomainReturnID,
                _pathReturnID,
                _pathReturnID,
                _etcReturnID,
                _etcReturnID,
            )

            _cursor.execute(STATIC_SQL_COMMAND, STATIC_DATA_TUPLE)

            results = _cursor.fetchall()

            if len(results) != 0:
                return False

            STATIC_SQL_COMMAND = """
            INSERT INTO "CrawledAddress" ("Protocol","BaseDomainID","BaseUrlPathID","BaseUrlEtcID") VALUES (%s,%s,%s,%s)
            """

            STATIC_DATA_TUPLE = (
                _protocol,
                _baseDomainReturnID,
                _pathReturnID,
                _etcReturnID,
            )

            _cursor.execute(STATIC_SQL_COMMAND, STATIC_DATA_TUPLE)

            _connection.commit()

            return True

        except Exception as e:
            print(f"!!!! Error occurred while inserting crawled URL: {e} !!!!")
            return False
        finally:
            self.releaseConnection(conn=_connection, cursor=_cursor)

    def is_crawled(self, target_url: str) -> bool:
        _connection = self.connect()
        _cursor = _connection.cursor(cursor_factory=DictCursor)
        try:
            parsedUrl = url_parser.prepare_url(target_url=target_url)

            _baseDomainReturnID = None
            _pathReturnID = None
            _etcReturnID = None

            _protocol = parsedUrl["protocol"]
            _baseDomain = parsedUrl["base_domain"]
            _path = parsedUrl["path"]
            _etc = parsedUrl["etc"]

            _baseDomain = str(_baseDomain).lower()
            # _baseDomain = str(_baseDomain).replace("www.", "")

            if len(_etc) == 0:
                _etc = None

            if len(_path) == 0:
                _path = None

            if _protocol != None:
                _protocol = str(_protocol).lower()
            else:
                _protocol = "http"

            STATIC_SQL_COMMAND = """SELECT * FROM "BaseDomainID" WHERE "Domain" = %s """
            STATIC_DATA_TUPLE = (str(_baseDomain).lower(),)

            _cursor.execute(STATIC_SQL_COMMAND, STATIC_DATA_TUPLE)

            results = _cursor.fetchall()

            if len(results) != 0:
                _baseDomainReturnID = results[0]["ID"]

            STATIC_SQL_COMMAND = """SELECT * FROM "UrlPathID" WHERE "Path" = %s  """
            STATIC_DATA_TUPLE = (_path,)

            _cursor.execute(STATIC_SQL_COMMAND, STATIC_DATA_TUPLE)

            results = _cursor.fetchall()

            if len(results) != 0:
                _pathReturnID = results[0]["ID"]

            STATIC_SQL_COMMAND = """SELECT * FROM "UrlEtcID" WHERE "Etc" = %s """
            STATIC_DATA_TUPLE = (_etc,)

            _cursor.execute(STATIC_SQL_COMMAND, STATIC_DATA_TUPLE)

            results = _cursor.fetchall()

            if len(results) != 0:
                _etcReturnID = results[0]["ID"]

            STATIC_SQL_COMMAND = """
            SELECT "ID","FirstCrawlDate" FROM "CrawledAddress" WHERE "Protocol" = %s AND "BaseDomainID" = %s AND 
            (("BaseUrlPathID" IS NULL AND %s IS NULL) OR "BaseUrlPathID" = %s) AND 
            (("BaseUrlEtcID" IS NULL AND %s IS NULL) OR "BaseUrlEtcID" = %s)
            """

            STATIC_DATA_TUPLE = (
                _protocol,
                _baseDomainReturnID,
                _pathReturnID,
                _pathReturnID,
                _etcReturnID,
                _etcReturnID,
            )

            _cursor.execute(STATIC_SQL_COMMAND, STATIC_DATA_TUPLE)

            results = _cursor.fetchall()

            if len(results) != 0:
                return (True, results[0]["FirstCrawlDate"])
            else:
                return (False, None)

        finally:
            self.releaseConnection(conn=_connection, cursor=_cursor)

    def releaseConnection(
        self, conn: psycopg2.extensions.connection, cursor: psycopg2.extensions.cursor
    ):
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    def executeQuery(self, query, params=None):
        """
        Execute a SQL query and return the results

        Args:
            query (str): The SQL query to execute
            params (tuple, optional): Parameters for the query

        Returns:
            list: List of dictionaries containing the query results
        """
        from psycopg2.extras import DictCursor

        connection = self.connect()
        cursor = connection.cursor(cursor_factory=DictCursor)

        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            results = cursor.fetchall()
            return results
        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f"Error executing query: {e}")
            return []
        finally:
            self.releaseConnection(connection, cursor)

    def insertPageBased(
        self,
        protocol: str,
        baseDomain: str,
        urlPath: str = None,
        urlPathEtc: str = None,
        phoneNumber_list: list = None,
        emailAddress_list: list = None,
        categortyNmae: str = None,
    ) -> typing.Tuple[int]:

        baseDomain_return_id = None
        urlPath_return_id = None
        urlPathEtc_return_id = None
        phoneNumber_return_id_LIST = []
        emailAddress_return_id_LIST = []
        categortyNmae_return_id = None

        conn = self.connect()
        cursor = conn.cursor(cursor_factory=DictCursor)
        try:

            if phoneNumber_list == None and emailAddress_list == None:
                return (True, "Not required data")

            if urlPath != None:
                if str(urlPath).startswith("/"):
                    urlPath = urlPath[1:]

            if len(urlPath) < 1 or urlPath.isspace():
                urlPath = None

            if urlPathEtc != None:
                if str(urlPathEtc).startswith("/"):
                    urlPathEtc = urlPathEtc[1:]

            if len(urlPathEtc) < 1 or urlPathEtc.isspace():
                urlPathEtc = None

            # ------------------- Url Path Etc's ---------------------------
            if urlPathEtc != None:
                STATIC_SQL_COMMAND = """SELECT "ID" FROM "UrlEtcID" WHERE "Etc" = %s"""
                cursor.execute(STATIC_SQL_COMMAND, (urlPathEtc,))
                result_is = cursor.fetchall()

                if len(result_is) < 1:
                    STATIC_SQL_COMMAND = (
                        """INSERT INTO "UrlEtcID" ("Etc") VALUES (%s) RETURNING "ID" """
                    )
                    cursor.execute(STATIC_SQL_COMMAND, (urlPathEtc,))
                    result_is = cursor.fetchall()[0]["ID"]
                    conn.commit()

                else:
                    result_is = result_is[0]["ID"]

                urlPathEtc_return_id = result_is

            # ------------------- URL Path's ---------------------------
            if urlPath != None:
                STATIC_SQL_COMMAND = (
                    """SELECT "ID" FROM "UrlPathID" WHERE "Path" = %s"""
                )
                cursor.execute(STATIC_SQL_COMMAND, (urlPath,))
                result_is = cursor.fetchall()

                if len(result_is) < 1:
                    STATIC_SQL_COMMAND = """INSERT INTO "UrlPathID" ("Path") VALUES (%s) RETURNING "ID" """
                    cursor.execute(STATIC_SQL_COMMAND, (urlPath,))
                    result_is = cursor.fetchall()[0]["ID"]
                    conn.commit()

                else:
                    result_is = result_is[0]["ID"]

                urlPath_return_id = result_is

            # ------------------- Base Domain's ---------------------------

            baseDomain = str(baseDomain).lower()
            STATIC_SQL_COMMAND = (
                """SELECT "ID" FROM "BaseDomainID" WHERE "BaseDomain" = %s"""
            )
            cursor.execute(STATIC_SQL_COMMAND, (baseDomain,))
            result_is = cursor.fetchall()

            if len(result_is) < 1:
                STATIC_SQL_COMMAND = """INSERT INTO "BaseDomainID" ("BaseDomain") VALUES (%s) RETURNING "ID" """
                cursor.execute(STATIC_SQL_COMMAND, (baseDomain,))
                result_is = cursor.fetchall()[0]["ID"]
                conn.commit()
            else:
                result_is = result_is[0]["ID"]

            baseDomain_return_id = result_is

            # ------------------- WebSite Category's ---------------------------

            if categortyNmae != None:
                categortyNmae = str(categortyNmae).lower()
                STATIC_SQL_COMMAND = (
                    """SELECT "ID" FROM "WebSiteCategoryID" WHERE "CategoryName" = %s"""
                )
                cursor.execute(STATIC_SQL_COMMAND, (categortyNmae,))
                result_is = cursor.fetchall()

                if len(result_is) < 1:
                    STATIC_SQL_COMMAND = """INSERT INTO "WebSiteCategoryID" ("CategoryName") VALUES (%s) RETURNING "ID" """
                    cursor.execute(STATIC_SQL_COMMAND, (categortyNmae,))
                    result_is = cursor.fetchall()[0]["ID"]
                    conn.commit()

                else:
                    result_is = result_is[0]["ID"]

                categortyNmae_return_id = result_is

            # ------------------- Email Address's ---------------------------

            if emailAddress_list != None:
                emailAddress_list = list(set(emailAddress_list))
                for index, email_address in enumerate(emailAddress_list):
                    email_address = str(email_address)
                    email_address = email_address.lower()  # for unique structure
                    email_address = email_address.strip()
                    email_address = email_address.replace(" ", "")
                    email_address = email_address.replace("/", "")

                    if email_address.startswith("mailto:"):
                        email_address = email_address[7:]

                    if not re.match(
                        r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
                        email_address,
                    ):
                        emailAddress_list.pop(index)
                        continue

                    emailAddress_list[index] = email_address

                for email_address in emailAddress_list:

                    STATIC_SQL_COMMAND = """SELECT "ID" FROM "EmailAddressID" WHERE "EmailAddress" = %s"""
                    cursor.execute(STATIC_SQL_COMMAND, (email_address,))
                    result_is = cursor.fetchall()

                    if len(result_is) < 1:
                        STATIC_SQL_COMMAND = """INSERT INTO "EmailAddressID" ("EmailAddress") VALUES (%s) RETURNING "ID" """
                        cursor.execute(STATIC_SQL_COMMAND, (email_address,))
                        result_is = cursor.fetchall()[0]["ID"]
                        conn.commit()

                    else:
                        result_is = result_is[0]["ID"]

                    emailAddress_return_id_LIST.append(result_is)

            if phoneNumber_list != None:
                phoneNumber_list = list(set(phoneNumber_list))
                for index, phone_num in enumerate(phoneNumber_list):
                    phone_num = str(phone_num)
                    phone_num = phone_num.strip()
                    phone_num = phone_num.replace(" ", "")
                    phone_num = phone_num.replace("/", "")

                    if not phone_num.startswith("+") and not phone_num.startswith("0"):
                        phone_num = "+" + phone_num

                    if not phone_num[1:].isdigit() or len(phone_num) > 15:
                        # remove invalid phone number
                        phoneNumber_list.pop(index)
                        continue

                    phoneNumber_list[index] = phone_num

                for phone_num in phoneNumber_list:

                    STATIC_SQL_COMMAND = (
                        """SELECT "ID" FROM "PhoneNumberID" WHERE "PhoneNumber" = %s"""
                    )
                    cursor.execute(STATIC_SQL_COMMAND, (phone_num,))
                    result_is = cursor.fetchall()

                    if len(result_is) < 1:
                        STATIC_SQL_COMMAND = """INSERT INTO "PhoneNumberID" ("PhoneNumber") VALUES (%s) RETURNING "ID" """
                        cursor.execute(STATIC_SQL_COMMAND, (phone_num,))
                        result_is = cursor.fetchall()[0]["ID"]
                        conn.commit()

                    else:
                        result_is = result_is[0]["ID"]

                    phoneNumber_return_id_LIST.append(result_is)

            STATIC_SQL_COMMAND = """
            SELECT "ID" FROM "PageBasedMain" WHERE "Protocol" = %s AND "BaseDomainID" = %s AND 
            (("UrlPathID" IS NULL AND %s IS NULL) OR "UrlPathID" = %s) AND 
            (("UrlEtcID" IS NULL AND %s IS NULL) OR "UrlEtcID" = %s) AND
            (("CategoryID" IS NULL AND %s IS NULL) OR "CategoryID" = %s)
            """
            cursor.execute(
                STATIC_SQL_COMMAND,
                (
                    protocol,
                    baseDomain_return_id,
                    urlPath_return_id,
                    urlPath_return_id,
                    urlPathEtc_return_id,
                    urlPathEtc_return_id,
                    categortyNmae_return_id,
                    categortyNmae_return_id,
                ),
            )
            result_is = cursor.fetchall()

            if len(result_is) < 1:
                STATIC_SQL_COMMAND = """
                INSERT INTO "PageBasedMain" ("Protocol", "BaseDomainID", "UrlPathID", "UrlEtcID", "CategoryID", "PhoneID", "EmailID")
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING "ID"
                """
                cursor.execute(
                    STATIC_SQL_COMMAND,
                    (
                        protocol,
                        baseDomain_return_id,
                        urlPath_return_id,
                        urlPathEtc_return_id,
                        categortyNmae_return_id,
                        (
                            phoneNumber_return_id_LIST
                            if phoneNumber_return_id_LIST
                            else None
                        ),
                        (
                            emailAddress_return_id_LIST
                            if emailAddress_return_id_LIST
                            else None
                        ),
                    ),
                )
                result_is = cursor.fetchall()[0]["ID"]
                conn.commit()

                return (True, result_is)
            else:
                return (True, result_is[0]["ID"])

        except Exception as e:
            return (False, str(e))

        finally:
            self.releaseConnection(conn, cursor)

    def insertImageBased(
        self,
        protocol: str,
        baseDomain: str,
        urlPath: str = None,
        urlPathEtc: str = None,
        imageProtocol: str = None,
        imageDomain: str = None,
        imagePath: str = None,
        imagePathEtc: str = None,
        imageTitle: str = None,
        imageBinary: bytes = None,
        imageHash: str = None,
        faces: list = None,
        riskLevel: str = None,
        category: str = None,
        save_image: bool = False,
        Source: str = "www",
    ) -> typing.Tuple[bool, str]:

        save_image = True  # Bu satır geliştirme/test amaçlı olabilir, kalıcı olup olmadığına karar verilmeli.

        # Milvus için koleksiyon adları
        # EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME = "EyeOfWebFaceDataMilvus"

        # faces None veya boşsa başlangıçta kontrol etmeyelim, hash kontrolünden sonra bakalım.
        if faces is None or not faces:
            return (False, "Faces are required")

        conn = self.connect()
        if not conn:
            return (False, "Database connection failed")
        cursor = conn.cursor(cursor_factory=DictCursor)

        milvus_face_collection = get_milvus_collection(
            EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME
        )
        if not milvus_face_collection:
            self.releaseConnection(conn, cursor)
            return (False, "Failed to get Milvus collection for faces.")

        try:
            baseDomain_return_id = None
            urlPath_return_id = None
            urlPathEtc_return_id = None
            imageDomain_return_id = None
            imagePath_return_id = None
            imagePathEtc_return_id = None
            imageTitle_return_id = None
            # imageHash_return_id initialize moved down
            category_return_id = None
            image_return_id = None

            # This list will hold the PostgreSQL EyeOfWebFaceID.ID values
            # to be stored in ImageBasedMain.FaceID array.
            # It will be populated either by reused IDs or newly created IDs.
            face_sql_ids_for_imagebasedmain = []
            skip_milvus_insert = False  # Default: do not skip Milvus insert
            imageHash_return_id = None

            current_timestamp_dt = datetime.datetime.now(datetime.timezone.utc)
            current_timestamp_epoch = int(current_timestamp_dt.timestamp())

            if protocol is None or baseDomain is None:
                return (
                    False,
                    "Protocol and BaseDomain are required for the source page.",
                )

            if protocol is not None:
                protocol = str(protocol).lower()

            if imageProtocol is not None:
                imageProtocol = str(imageProtocol).lower()

            # Process BaseDomain (Sayfa Kaynağı)
            if baseDomain is not None:
                baseDomain = str(baseDomain).lower()
                # TODO: "BaseDomainID" tablosunda "Domain" mi "BaseDomain" mi alan adı kontrol edilmeli.
                # Şemada "Domain" olarak görünüyor. Kodda "BaseDomain" kullanılmış. Şemaya göre "Domain" olmalı.
                # Düzeltme: Şemada "BaseDomainID" tablosunda "Domain" sütunu var.
                STATIC_SQL_COMMAND = (
                    """SELECT "ID" FROM "BaseDomainID" WHERE "Domain" = %s"""
                )
                cursor.execute(STATIC_SQL_COMMAND, (baseDomain,))
                result_is = cursor.fetchall()

                if len(result_is) < 1:
                    STATIC_SQL_COMMAND = """INSERT INTO "BaseDomainID" ("Domain") VALUES (%s) RETURNING "ID" """
                    cursor.execute(STATIC_SQL_COMMAND, (baseDomain,))
                    baseDomain_return_id = cursor.fetchall()[0]["ID"]
                    conn.commit()
                else:
                    baseDomain_return_id = result_is[0]["ID"]

            # Process ImageDomain (Resim Kaynağı)
            if imageDomain is not None:
                imageDomain = str(imageDomain).lower()
                # Düzeltme: Şemada "BaseDomainID" tablosunda "Domain" sütunu var.
                STATIC_SQL_COMMAND = (
                    """SELECT "ID" FROM "BaseDomainID" WHERE "Domain" = %s"""
                )
                cursor.execute(STATIC_SQL_COMMAND, (imageDomain,))
                result_is = cursor.fetchall()

                if len(result_is) < 1:
                    STATIC_SQL_COMMAND = """INSERT INTO "BaseDomainID" ("Domain") VALUES (%s) RETURNING "ID" """
                    cursor.execute(STATIC_SQL_COMMAND, (imageDomain,))
                    imageDomain_return_id = cursor.fetchall()[0]["ID"]
                    conn.commit()
                else:
                    imageDomain_return_id = result_is[0]["ID"]

            # Process ImageID (Resim Binary)
            if save_image is True:
                if imageBinary is None:
                    self.releaseConnection(
                        conn, cursor
                    )  # Ensure release before early return
                    return (False, "ImageBinary is required when save_image is True")

                compressed_image = compress_image(imageBinary)

                STATIC_SQL_COMMAND = (
                    """SELECT "ID" FROM "ImageID" WHERE "BinaryImage" = %s"""
                )
                cursor.execute(STATIC_SQL_COMMAND, (psycopg2.Binary(compressed_image),))
                result_is = cursor.fetchall()

                if len(result_is) < 1:
                    STATIC_SQL_COMMAND = """INSERT INTO "ImageID" ("BinaryImage") VALUES (%s) RETURNING "ID" """
                    cursor.execute(
                        STATIC_SQL_COMMAND, (psycopg2.Binary(compressed_image),)
                    )
                    image_return_id = cursor.fetchall()[0]["ID"]
                    conn.commit()
                else:
                    image_return_id = result_is[0]["ID"]

            # Process WebSiteCategoryID
            if category is not None:
                category = str(category).lower()
                # Düzeltme: Şemada "WebSiteCategoryID" tablosunda "Category" sütunu var. Kodda da "Category" kullanılmış, doğru.
                STATIC_SQL_COMMAND = (
                    """SELECT "ID" FROM "WebSiteCategoryID" WHERE "Category" = %s"""
                )
                cursor.execute(STATIC_SQL_COMMAND, (category,))
                result_is = cursor.fetchall()

                if len(result_is) < 1:
                    STATIC_SQL_COMMAND = """INSERT INTO "WebSiteCategoryID" ("Category") VALUES (%s) RETURNING "ID" """
                    cursor.execute(STATIC_SQL_COMMAND, (category,))
                    category_return_id = cursor.fetchall()[0]["ID"]
                    conn.commit()
                else:
                    category_return_id = result_is[0]["ID"]

            # Process ImageHashID
            if imageHash is not None:
                STATIC_SQL_COMMAND = (
                    """SELECT "ID" FROM "ImageHashID" WHERE "ImageHash" = %s"""
                )
                cursor.execute(STATIC_SQL_COMMAND, (imageHash,))
                result_is = cursor.fetchall()

                if len(result_is) < 1:
                    STATIC_SQL_COMMAND = """INSERT INTO "ImageHashID" ("ImageHash") VALUES (%s) RETURNING "ID" """
                    cursor.execute(STATIC_SQL_COMMAND, (imageHash,))
                    imageHash_return_id = cursor.fetchall()[0]["ID"]
                    conn.commit()
                    p_log(
                        f"New image hash {imageHash} (ID: {imageHash_return_id}) inserted."
                    )
                    skip_milvus_insert = (
                        False  # New hash, Milvus insert needed if faces provided
                    )
                else:
                    imageHash_return_id = result_is[0]["ID"]
                    p_log(
                        f"Image hash {imageHash} (ID: {imageHash_return_id}) already exists. Checking for linked faces in ImageBasedMain."
                    )
                    cursor.execute(
                        """
                        SELECT "FaceID" FROM "ImageBasedMain" WHERE "HashID" = %s
                    """,
                        (imageHash_return_id,),
                    )
                    existing_ibm_records_for_hash = cursor.fetchall()

                    current_pg_face_ids_for_hash = set()
                    if existing_ibm_records_for_hash:
                        for rec in existing_ibm_records_for_hash:
                            if rec["FaceID"]:  # FaceID is an array of bigint
                                current_pg_face_ids_for_hash.update(rec["FaceID"])

                    if current_pg_face_ids_for_hash:
                        p_info(
                            f"Found existing PostgreSQL FaceIDs {list(current_pg_face_ids_for_hash)} for hash ID {imageHash_return_id}. These will be used. Milvus insert will be skipped."
                        )
                        face_sql_ids_for_imagebasedmain = list(
                            current_pg_face_ids_for_hash
                        )  # Populate with existing SQL FaceIDs
                        skip_milvus_insert = True
                    else:
                        p_log(
                            f"Image hash ID {imageHash_return_id} exists, but no ImageBasedMain records with faces found for it (or existing records have no faces). Milvus insert will proceed if faces are provided."
                        )
                        skip_milvus_insert = (
                            False  # Ensure Milvus insert happens if faces are given
                        )
            else:
                p_error(
                    "imageHash is None, which is required for ImageBasedMain.HashID."
                )
                self.releaseConnection(conn, cursor)
                return (False, "imageHash is required but was not provided.")

            # --- Face Processing (PostgreSQL'e ID ekle, Milvus'a data ekle) ---
            scale_ratio = 0.5  # Bu değer dışarıdan veya config'den gelmeli idealde
            # current_timestamp_dt and current_timestamp_epoch are already defined

            milvus_insert_payload = []
            # Her yüz için Milvus'a gönderilecek verileri hazırla
            if not skip_milvus_insert and faces:
                p_log(
                    "Preparing face data for new Milvus insertion as skip_milvus_insert is False and faces are provided."
                )
                for face_dict in faces:
                    embedding: np.ndarray = face_dict["embedding"]
                    original_landmark_2d_106: np.ndarray = face_dict["landmark_2d_106"]
                    original_bbox: np.ndarray = face_dict["bbox"]
                    det_score: float = float(face_dict["det_score"])
                    gender: bool = bool(face_dict["gender"])
                    age: int = int(face_dict["age"])

                    # Landmark ve Bbox Ölçeklendirme
                    scaled_landmark_2d_106 = original_landmark_2d_106 * scale_ratio
                    scaled_bbox = original_bbox * scale_ratio

                    # CRITICAL: Normalize embedding for COSINE metric
                    # Ensures consistent similarity calculations
                    embedding_norm = np.linalg.norm(embedding)
                    if embedding_norm > 0:
                        normalized_embedding = embedding / embedding_norm
                    else:
                        p_warn(
                            f"Face embedding has zero norm, using unnormalized embedding."
                        )
                        normalized_embedding = embedding

                    # Milvus'a gönderilecek veri (ID alanı YOK, Milvus kendi üretecek)
                    milvus_data_entry = {
                        # "id": ..., # ID ALANI KALDIRILDI
                        "face_embedding_data": normalized_embedding.tolist(),
                        "landmarks_2d": scaled_landmark_2d_106.flatten().tolist(),
                        "face_box": scaled_bbox.tolist(),
                        "detection_score": det_score,
                        "face_gender": gender,
                        "face_age": age,
                        "detection_date_ts": current_timestamp_epoch,  # Tüm yüzler için aynı DetectionDate
                    }
                    milvus_insert_payload.append(milvus_data_entry)

            elif skip_milvus_insert:
                p_log(
                    f"Milvus insert skipped. Using existing FaceIDs: {face_sql_ids_for_imagebasedmain} for hash ID {imageHash_return_id}."
                )
            elif (
                not faces
            ):  # This case means skip_milvus_insert is False, but no faces were provided.
                p_log(
                    "No faces provided, Milvus insertion skipped. `face_sql_ids_for_imagebasedmain` will be empty unless hash reuse populated it (which it wouldn't if skip_milvus_insert is false)."
                )
                # If faces is None or empty from the start, and we are not skipping Milvus insert,
                # face_sql_ids_for_imagebasedmain will remain empty. This is handled by ImageBasedMain logic later.

            # Toplu Milvus Insert
            # milvus_generated_ids = [] # This was here, but it's better scoped if only used when payload exists
            if (
                milvus_insert_payload
            ):  # This implies not skip_milvus_insert and faces were present and processed
                milvus_generated_ids = []  # Define it here
                try:
                    p_info(
                        f"Attempting to insert {len(milvus_insert_payload)} new faces into Milvus collection '{EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME}'. Milvus will generate IDs."
                    )
                    insert_result = milvus_face_collection.insert(milvus_insert_payload)
                    milvus_generated_ids = insert_result.primary_keys

                    if len(milvus_generated_ids) != len(milvus_insert_payload):
                        p_warn(
                            f"Milvus insert count/ID mismatch. Expected {len(milvus_insert_payload)} IDs, got {len(milvus_generated_ids)}."
                        )
                        conn.rollback()
                        self.releaseConnection(conn, cursor)
                        return (
                            False,
                            "Milvus failed to return matching number of IDs for inserted faces.",
                        )
                    else:
                        p_log(
                            f"Successfully inserted {len(milvus_generated_ids)} new faces into Milvus. Generated PKs from Milvus: {milvus_generated_ids}"
                        )

                except MilvusException as milvus_err:
                    p_error(f"Milvus insert error for new faces: {milvus_err}")
                    traceback.print_exc()
                    conn.rollback()
                    self.releaseConnection(conn, cursor)
                    return (False, f"Milvus insert failed for new faces: {milvus_err}")

                # Link Milvus ID'leri ile PostgreSQL EyeOfWebFaceID tablosuna kayıtları ekle
                # This block only runs if new faces were inserted into Milvus.
                # face_sql_ids_for_imagebasedmain should be populated with these new IDs.
                # If skip_milvus_insert was false, face_sql_ids_for_imagebasedmain was initialized to [].

                newly_created_pg_face_ids_from_milvus = []
                if milvus_generated_ids:
                    for milvus_id in milvus_generated_ids:
                        try:
                            cursor.execute(
                                """ 
                                INSERT INTO "EyeOfWebFaceID" ("MilvusRefID") 
                                VALUES (%s) RETURNING "ID" 
                            """,
                                (milvus_id,),
                            )
                            sql_face_id_result = cursor.fetchone()
                            if sql_face_id_result and sql_face_id_result["ID"]:
                                pg_face_id = sql_face_id_result["ID"]
                                newly_created_pg_face_ids_from_milvus.append(pg_face_id)
                                conn.commit()
                                p_log(
                                    f"Linked new Milvus ID {milvus_id} to new PostgreSQL EyeOfWebFaceID {pg_face_id}"
                                )
                            else:
                                p_error(
                                    f"Failed to retrieve PostgreSQL ID after inserting new MilvusRefID {milvus_id} into EyeOfWebFaceID."
                                )
                                conn.rollback()
                                self.releaseConnection(conn, cursor)
                                return (
                                    False,
                                    "Failed to link new Milvus ID to PostgreSQL EyeOfWebFaceID.",
                                )
                        except psycopg2.Error as db_err:
                            conn.rollback()
                            p_error(
                                f"Database error inserting new MilvusRefID {milvus_id} into EyeOfWebFaceID: {db_err}"
                            )
                            traceback.print_exc()
                            self.releaseConnection(conn, cursor)
                            return (
                                False,
                                "Database error during new Milvus to SQL ID linking.",
                            )

                    # Populate face_sql_ids_for_imagebasedmain with these newly created IDs
                    face_sql_ids_for_imagebasedmain = (
                        newly_created_pg_face_ids_from_milvus
                    )
                    p_log(
                        f"Populated `face_sql_ids_for_imagebasedmain` with newly created PG FaceIDs: {face_sql_ids_for_imagebasedmain}"
                    )

            # Consistency check after all face processing steps.
            # This applies if faces were provided and we did not skip milvus insert (meaning new faces were expected to be processed).
            if faces and not skip_milvus_insert:
                expected_face_count = len(
                    faces
                )  # Or len(milvus_insert_payload) if it was successfully built
                if len(face_sql_ids_for_imagebasedmain) != expected_face_count:
                    p_error(
                        f"CRITICAL: Mismatch for new face processing. Input faces: {expected_face_count}, final linked SQL FaceIDs: {len(face_sql_ids_for_imagebasedmain)}. Data inconsistency. Rolling back."
                    )
                    conn.rollback()
                    self.releaseConnection(conn, cursor)
                    return (
                        False,
                        "Critical error in new face processing linkage. Transaction rolled back.",
                    )

            # If skip_milvus_insert was true, face_sql_ids_for_imagebasedmain holds reused IDs.
            # If skip_milvus_insert was false:
            #   - and faces were provided & processed, it holds new IDs.
            #   - and no faces were provided, it's empty.
            # This is the list of SQL Face IDs that will be used for ImageBasedMain.
            p_log(
                f"Final PostgreSQL FaceIDs to be associated with ImageBasedMain.FaceID: {face_sql_ids_for_imagebasedmain}"
            )

            # --- Face Processing Sonu ---

            if not face_sql_ids_for_imagebasedmain and faces:
                p_warn(
                    "Although faces were provided in the input, no SQL Face IDs ended up in `face_sql_ids_for_imagebasedmain`. This might be due to an issue or if `skip_milvus_insert` was true but no existing faces were found for the hash initially."
                )
                # Depending on strictness, could return False here.
                # For now, we allow ImageBasedMain to be inserted/updated with an empty/None FaceID list.

            # --- Diğer ID'leri Al (UrlPath, UrlEtc, ImageTitle, ImagePath, ImageUrlEtc) ---
            # Bu kısımlar büyük ölçüde aynı kalacak. Sadece null ve boş string kontrolleri eklendi.

            if urlPath is not None and str(urlPath).strip():
                urlPath = str(urlPath).strip()
                if urlPath.startswith("/"):
                    urlPath = urlPath[1:]
                if urlPath:  # Boş string değilse
                    STATIC_SQL_COMMAND = (
                        """SELECT "ID" FROM "UrlPathID" WHERE "Path" = %s"""
                    )
                    cursor.execute(STATIC_SQL_COMMAND, (urlPath,))
                    result_is = cursor.fetchall()
                    if not result_is:
                        STATIC_SQL_COMMAND = """INSERT INTO "UrlPathID" ("Path") VALUES (%s) RETURNING "ID" """
                        cursor.execute(STATIC_SQL_COMMAND, (urlPath,))
                        urlPath_return_id = cursor.fetchall()[0]["ID"]
                        conn.commit()
                    else:
                        urlPath_return_id = result_is[0]["ID"]

            if urlPathEtc is not None and str(urlPathEtc).strip():
                urlPathEtc = str(urlPathEtc).strip()
                # Genellikle '?' ile başlar, ama başında olup olmadığını kontrol etmiyoruz.
                # if urlPathEtc.startswith("?"): urlPathEtc = urlPathEtc[1:] # Gerekirse
                if urlPathEtc:
                    STATIC_SQL_COMMAND = (
                        """SELECT "ID" FROM "UrlEtcID" WHERE "Etc" = %s"""
                    )
                    cursor.execute(STATIC_SQL_COMMAND, (urlPathEtc,))
                    result_is = cursor.fetchall()
                    if not result_is:
                        STATIC_SQL_COMMAND = """INSERT INTO "UrlEtcID" ("Etc") VALUES (%s) RETURNING "ID" """
                        cursor.execute(STATIC_SQL_COMMAND, (urlPathEtc,))
                        urlPathEtc_return_id = cursor.fetchall()[0]["ID"]
                        conn.commit()
                    else:
                        urlPathEtc_return_id = result_is[0]["ID"]

            if imageTitle is not None and str(imageTitle).strip():
                imageTitle = str(imageTitle).strip()
                if imageTitle:
                    STATIC_SQL_COMMAND = (
                        """SELECT "ID" FROM "ImageTitleID" WHERE "Title" = %s"""
                    )
                    cursor.execute(STATIC_SQL_COMMAND, (imageTitle,))
                    result_is = cursor.fetchall()
                    if not result_is:
                        STATIC_SQL_COMMAND = """INSERT INTO "ImageTitleID" ("Title") VALUES (%s) RETURNING "ID" """
                        cursor.execute(STATIC_SQL_COMMAND, (imageTitle,))
                        imageTitle_return_id = cursor.fetchall()[0]["ID"]
                        conn.commit()
                    else:
                        imageTitle_return_id = result_is[0]["ID"]

            if imagePath is not None and str(imagePath).strip():
                imagePath = str(imagePath).strip()
                if imagePath.startswith("/"):
                    imagePath = imagePath[1:]
                if imagePath:
                    # Şemada ImageUrlPathID, kodda ImagePathID. Şemaya uyalım.
                    STATIC_SQL_COMMAND = (
                        """SELECT "ID" FROM "ImageUrlPathID" WHERE "Path" = %s"""
                    )
                    cursor.execute(STATIC_SQL_COMMAND, (imagePath,))
                    result_is = cursor.fetchall()
                    if not result_is:
                        STATIC_SQL_COMMAND = """INSERT INTO "ImageUrlPathID" ("Path") VALUES (%s) RETURNING "ID" """
                        cursor.execute(STATIC_SQL_COMMAND, (imagePath,))
                        imagePath_return_id = cursor.fetchall()[0]["ID"]
                        conn.commit()
                    else:
                        imagePath_return_id = result_is[0]["ID"]

            if imagePathEtc is not None and str(imagePathEtc).strip():
                imagePathEtc = str(imagePathEtc).strip()
                # if imagePathEtc.startswith("?"): imagePathEtc = imagePathEtc[1:] # Gerekirse
                if imagePathEtc:
                    # Şemada ImageUrlEtcID, kodda imagePathEtc_return_id. Şemaya uyalım.
                    STATIC_SQL_COMMAND = (
                        """SELECT "ID" FROM "ImageUrlEtcID" WHERE "Etc" = %s"""
                    )
                    cursor.execute(STATIC_SQL_COMMAND, (imagePathEtc,))
                    result_is = cursor.fetchall()
                    if not result_is:
                        STATIC_SQL_COMMAND = """INSERT INTO "ImageUrlEtcID" ("Etc") VALUES (%s) RETURNING "ID" """
                        cursor.execute(STATIC_SQL_COMMAND, (imagePathEtc,))
                        imagePathEtc_return_id = cursor.fetchall()[0]["ID"]
                        conn.commit()
                    else:
                        imagePathEtc_return_id = result_is[0]["ID"]

            # --- ImageBasedMain Kontrol ve Ekleme/Güncelleme ---
            # NOT NULL alan: BaseDomainID, HashID. Diğerleri NULL olabilir.
            # FaceID artık face_sql_ids_for_imagebasedmain listesi olacak.

            STATIC_CHECK_SQL_COMMAND = """
            SELECT "ID" FROM "ImageBasedMain" 
            WHERE "Protocol" = %s AND "BaseDomainID" = %s 
              AND (("UrlPathID" IS NULL AND %s IS NULL) OR "UrlPathID" = %s)
              AND (("UrlEtcID" IS NULL AND %s IS NULL) OR "UrlEtcID" = %s)
              AND (("ImageProtocol" IS NULL AND %s IS NULL) OR "ImageProtocol" = %s)
              AND (("ImageDomainID" IS NULL AND %s IS NULL) OR "ImageDomainID" = %s)
              AND (("ImagePathID" IS NULL AND %s IS NULL) OR "ImagePathID" = %s)
              AND (("ImageUrlEtcID" IS NULL AND %s IS NULL) OR "ImageUrlEtcID" = %s)
              AND (("ImageTitleID" IS NULL AND %s IS NULL) OR "ImageTitleID" = %s)
              AND (("ImageID" IS NULL AND %s IS NULL) OR "ImageID" = %s) -- Fiziksel resim ID'si
              AND "HashID" = %s -- Resim içeriğinin hash ID'si (NOT NULL)
              -- Kategori ve RiskLevel'e göre de check edilebilir, ancak mevcut kodda yok.
              -- Source'a göre de check edilebilir.
            """
            STATIC_CHECK_DATA_TUPLE = (
                protocol,
                baseDomain_return_id,
                urlPath_return_id,
                urlPath_return_id,
                urlPathEtc_return_id,
                urlPathEtc_return_id,
                imageProtocol,
                imageProtocol,
                imageDomain_return_id,
                imageDomain_return_id,
                imagePath_return_id,
                imagePath_return_id,
                imagePathEtc_return_id,
                imagePathEtc_return_id,
                imageTitle_return_id,
                imageTitle_return_id,
                image_return_id,
                image_return_id,  # Bu ID ImageID tablosundan
                imageHash_return_id,  # Bu ID ImageHashID tablosundan
            )
            cursor.execute(STATIC_CHECK_SQL_COMMAND, STATIC_CHECK_DATA_TUPLE)
            existing_main_record = cursor.fetchone()

            if not existing_main_record:
                STATIC_INSERT_SQL_COMMAND = """
                INSERT INTO "ImageBasedMain" (
                    "Protocol", "BaseDomainID", "UrlPathID", "UrlEtcID", 
                    "ImageProtocol", "ImageDomainID", "ImagePathID", "ImageUrlEtcID", 
                    "ImageTitleID", "ImageID", "FaceID", "RiskLevel", "CategoryID", "HashID", "Source",
                    "DetectionDate" -- Bunu da ekleyelim
                ) 
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, %s) RETURNING "ID"
                """
                # Use face_sql_ids_for_imagebasedmain, which is now correctly populated
                face_ids_to_insert_update = (
                    face_sql_ids_for_imagebasedmain
                    if face_sql_ids_for_imagebasedmain
                    else None
                )

                STATIC_INSERT_DATA_TUPLE = (
                    protocol,
                    baseDomain_return_id,
                    urlPath_return_id,
                    urlPathEtc_return_id,
                    imageProtocol,
                    imageDomain_return_id,
                    imagePath_return_id,
                    imagePathEtc_return_id,
                    imageTitle_return_id,
                    image_return_id,
                    face_ids_to_insert_update,  # PostgreSQL array
                    riskLevel,
                    category_return_id,
                    imageHash_return_id,
                    Source,
                    current_timestamp_dt,  # DetectionDate
                )
                cursor.execute(STATIC_INSERT_SQL_COMMAND, STATIC_INSERT_DATA_TUPLE)
                inserted_main_id = cursor.fetchall()[0]["ID"]
                conn.commit()
                p_log(
                    f"New ImageBasedMain record created with ID: {inserted_main_id} and FaceIDs: {face_ids_to_insert_update}"
                )
                self.releaseConnection(conn, cursor)  # Release connection
                return (
                    True,
                    f"New ImageBasedMain record created with ID: {inserted_main_id}",
                )
            else:
                # Kayıt zaten var. FaceID'yi güncelle.
                existing_main_id = existing_main_record["ID"]
                p_log(
                    f"Existing ImageBasedMain record found with ID: {existing_main_id}."
                )

                # `face_sql_ids_for_imagebasedmain` contains the full list of faces that should be associated
                # with this image (either new or reused from hash).
                # We need to combine these with any *other* faces already linked to this specific ImageBasedMain record,
                # IF this ImageBasedMain record was found through criteria OTHER than just the hash.
                # However, the STATIC_CHECK_SQL_COMMAND includes HashID. So if a record is found, it's for this hash.
                # The goal is to ensure the FaceID array for *this specific ImageBasedMain record* reflects the *latest understanding*
                # of faces for its associated hash.

                cursor.execute(
                    """SELECT "FaceID" FROM "ImageBasedMain" WHERE "ID" = %s""",
                    (existing_main_id,),
                )
                current_face_ids_row = cursor.fetchone()
                # current_face_ids_in_db is what's currently stored for this specific ImageBasedMain row
                current_face_ids_in_db = set(
                    current_face_ids_row["FaceID"]
                    if current_face_ids_row and current_face_ids_row["FaceID"]
                    else []
                )

                # face_sql_ids_for_imagebasedmain represents the "authoritative" list for this hash from this run.
                # For an existing ImageBasedMain record tied to this hash, its FaceID array should become this list.
                # If there were other faces previously associated with this IBM record (e.g. from a different hash, which is unlikely here due to check),
                # this logic would overwrite them if `face_sql_ids_for_imagebasedmain` is different.
                # Given the check includes HashID, this is simpler: the FaceID list for this IBM record should BE `face_sql_ids_for_imagebasedmain`.

                new_authoritative_face_ids_for_record = set(
                    face_sql_ids_for_imagebasedmain
                    if face_sql_ids_for_imagebasedmain
                    else []
                )

                if new_authoritative_face_ids_for_record != current_face_ids_in_db:
                    p_info(
                        f"Updating FaceID for ImageBasedMain ID {existing_main_id}. Old: {current_face_ids_in_db}, New authoritative list: {new_authoritative_face_ids_for_record}"
                    )
                    STATIC_UPDATE_SQL_COMMAND = """
                    UPDATE "ImageBasedMain" SET "FaceID" = %s, "DetectionDate" = %s 
                    WHERE "ID" = %s
                    """
                    # Use list(new_authoritative_face_ids_for_record) or None
                    final_face_ids_for_update = (
                        list(new_authoritative_face_ids_for_record)
                        if new_authoritative_face_ids_for_record
                        else None
                    )
                    cursor.execute(
                        STATIC_UPDATE_SQL_COMMAND,
                        (
                            final_face_ids_for_update,
                            current_timestamp_dt,
                            existing_main_id,
                        ),
                    )
                    conn.commit()
                    self.releaseConnection(conn, cursor)  # Release connection
                    return (
                        True,
                        f"ImageBasedMain record ID {existing_main_id} updated with FaceIDs: {final_face_ids_for_update}.",
                    )
                else:
                    p_log(
                        f"No change needed for FaceID in ImageBasedMain ID {existing_main_id}. FaceIDs remain: {current_face_ids_in_db}"
                    )
                    self.releaseConnection(conn, cursor)  # Release connection
                    return (
                        True,
                        f"ImageBasedMain record ID {existing_main_id} already exists, FaceIDs unchanged.",
                    )

        except psycopg2.Error as db_err:
            conn.rollback()  # SQL hatası olursa geri al
            p_error(f"Database error in insertImageBased: {db_err}")
            traceback.print_exc()
            return (False, str(db_err))
        except MilvusException as milvus_err:
            # Milvus hatası olduysa SQL işlemleri geri alınmalı mı?
            # Eğer yüzler Milvus'a eklenemezse, ImageBasedMain.FaceID'ler boş/hatalı olabilir.
            # conn.rollback() # Belki burada da rollback iyi olur.
            p_error(f"Milvus error in insertImageBased: {milvus_err}")
            traceback.print_exc()
            return (False, str(milvus_err))
        except Exception as e:
            conn.rollback()  # Genel bir hata olursa da SQL'i geri al
            p_error(f"Unexpected error in insertImageBased: {e}")
            traceback.print_exc()
            return (False, str(e))

        finally:
            self.releaseConnection(conn, cursor)

    def getAllDomains(self):
        """Sistemdeki tüm domainleri döndürür"""
        conn = self.connect()
        cursor = conn.cursor(cursor_factory=DictCursor)
        try:
            STATIC_SQL_COMMAND = (
                """SELECT DISTINCT "Domain" FROM "BaseDomainID" ORDER BY "Domain" """
            )
            cursor.execute(STATIC_SQL_COMMAND)
            domains = [record["Domain"] for record in cursor.fetchall()]
            return domains
        except Exception as e:
            print(f"Error getting domains: {str(e)}")
            return []
        finally:
            self.releaseConnection(conn, cursor)

    def getAllCategories(self):
        """Sistemdeki tüm kategorileri döndürür"""
        conn = self.connect()
        cursor = conn.cursor(cursor_factory=DictCursor)
        try:
            STATIC_SQL_COMMAND = """SELECT DISTINCT "Category" FROM "WebSiteCategoryID" ORDER BY "Category" """
            cursor.execute(STATIC_SQL_COMMAND)
            categories = [record["Category"] for record in cursor.fetchall()]
            return categories
        except Exception as e:
            print(f"Error getting categories: {str(e)}")
            return []
        finally:
            self.releaseConnection(conn, cursor)

    def getFaceDetailsWithImage(self, face_id: int):
        """
        Belirli bir PostgreSQL EyeOfWebFaceID.ID'si için yüzün detaylarını,
        Milvus'tan vektör özniteliklerini ve PostgreSQL'den meta verilerini getirir.

        Args:
            face_id: PostgreSQL EyeOfWebFaceID tablosundaki yüz ID'si.

        Returns:
            dict: Yüz ve resim detayları ya da None.
        """
        p_log(f"Fetching details for PostgreSQL FaceID: {face_id}")
        pg_conn = None
        pg_cursor = None
        result_data = {"id": face_id}

        try:
            pg_conn = self.connect()
            if not pg_conn:
                p_error("Database connection failed for getFaceDetailsWithImage.")
                return None
            pg_cursor = pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            pg_cursor.execute(
                'SELECT "MilvusRefID" FROM "EyeOfWebFaceID" WHERE "ID" = %s', (face_id,)
            )
            milvus_ref_record = pg_cursor.fetchone()

            milvus_attributes_fetched = False
            if not milvus_ref_record or not milvus_ref_record["MilvusRefID"]:
                p_warn(
                    f"No MilvusRefID found in EyeOfWebFaceID for PostgreSQL FaceID {face_id}. Cannot fetch from Milvus."
                )
            else:
                milvus_ref_id = milvus_ref_record["MilvusRefID"]
                result_data["milvus_ref_id"] = milvus_ref_id
                p_log(
                    f"Found MilvusRefID: {milvus_ref_id} for PostgreSQL FaceID: {face_id}"
                )

                # 3. Milvus'tan Vektör Özniteliklerini Çek
                milvus_collection = get_milvus_collection(
                    EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME
                )
                if milvus_collection:
                    milvus_query_result = milvus_collection.query(
                        expr=f"id == {milvus_ref_id}",
                        output_fields=[
                            "face_gender",
                            "face_age",
                            "detection_score",
                            "face_box",
                            "landmarks_2d",
                            "face_embedding_data",
                        ],  # face_embedding_data eklendi
                        limit=1,  # ID unique olmalı
                    )
                    if milvus_query_result:
                        milvus_entity = milvus_query_result[0]
                        result_data["gender"] = milvus_entity.get("face_gender")
                        result_data["age"] = milvus_entity.get("face_age")
                        result_data["detection_score"] = milvus_entity.get(
                            "detection_score"
                        )

                        face_box_list = milvus_entity.get("face_box")
                        result_data["facebox"] = face_box_list

                        landmarks_flat_list = milvus_entity.get("landmarks_2d")
                        if landmarks_flat_list and len(landmarks_flat_list) == 212:
                            try:
                                landmarks_2d_np = np.array(
                                    landmarks_flat_list, dtype=np.float32
                                ).reshape((106, 2))
                                result_data["landmarks_2d"] = landmarks_2d_np.tolist()
                            except ValueError as e:
                                p_error(
                                    f"Error reshaping landmarks_2d for MilvusRefID {milvus_ref_id}: {e}"
                                )
                                result_data["landmarks_2d"] = None
                        else:
                            result_data["landmarks_2d"] = None

                        # Yüz embedding vektörünü ekle
                        raw_embedding = milvus_entity.get("face_embedding_data")
                        if raw_embedding:
                            face_embedding_np = np.array(
                                raw_embedding, dtype=np.float32
                            )
                            if face_embedding_np.size == 512:  # Beklenen boyut kontrolü
                                result_data["face_embedding"] = (
                                    face_embedding_np.tolist()
                                )  # veya np array olarak bırakılabilir
                            else:
                                p_warn(
                                    f"Fetched embedding for MilvusRefID {milvus_ref_id} has unexpected size: {face_embedding_np.size}. Expected 512."
                                )
                                result_data["face_embedding"] = None
                        else:
                            result_data["face_embedding"] = None

                        p_log(
                            f"Successfully fetched attributes (including embedding) from Milvus for MilvusRefID {milvus_ref_id}"
                        )
                        milvus_attributes_fetched = True
                    else:
                        p_warn(
                            f"No data found in Milvus for MilvusRefID {milvus_ref_id} (linked to PostgreSQL FaceID {face_id})."
                        )
                else:
                    p_warn(
                        f"Failed to get Milvus collection for MilvusRefID {milvus_ref_id}. Skipping Milvus attribute fetch."
                    )

            # 4. PostgreSQL'den ImageBasedMain ve Diğer Meta Verileri Çek
            sql_meta_details = """
            SELECT
                m."ImageID" as image_id,      
                m."Protocol" as source_protocol,
                bd."Domain" as source_domain,
                up."Path" as source_url_path, 
                ue."Etc" as source_url_etc,   
                m."ImageProtocol" as image_protocol,
                id_img."Domain" as image_domain,
                ip."Path" as image_path,
                ie."Etc" as image_etc,
                it."Title" as image_title,
                wc."Category" as category,
                m."RiskLevel" as risk_level,
                m."DetectionDate" as detection_date,
                m."Source" as source_table_name
            FROM "ImageBasedMain" m
            LEFT JOIN "BaseDomainID" bd ON m."BaseDomainID" = bd."ID"
            LEFT JOIN "UrlPathID" up ON m."UrlPathID" = up."ID"
            LEFT JOIN "UrlEtcID" ue ON m."UrlEtcID" = ue."ID"
            LEFT JOIN "BaseDomainID" id_img ON m."ImageDomainID" = id_img."ID"
            LEFT JOIN "ImageUrlPathID" ip ON m."ImagePathID" = ip."ID"
            LEFT JOIN "ImageUrlEtcID" ie ON m."ImageUrlEtcID" = ie."ID"
            LEFT JOIN "ImageTitleID" it ON m."ImageTitleID" = it."ID"
            LEFT JOIN "WebSiteCategoryID" wc ON m."CategoryID" = wc."ID"
            WHERE %s = ANY(m."FaceID")
            ORDER BY m."DetectionDate" DESC NULLS LAST
            LIMIT 1
            """
            pg_cursor.execute(sql_meta_details, (face_id,))
            meta_details_row = pg_cursor.fetchone()

            sql_metadata_fetched = False
            if meta_details_row:
                p_log(
                    f"Successfully fetched metadata from PostgreSQL for FaceID {face_id}"
                )
                sql_metadata_fetched = True
                result_data["image_id"] = meta_details_row.get("image_id")
                result_data["domain"] = meta_details_row.get("source_domain")
                result_data["url_path"] = meta_details_row.get("source_url_path")
                result_data["url_etc"] = meta_details_row.get("source_url_etc")
                result_data["protocol"] = meta_details_row.get("source_protocol")
                result_data["image_protocol"] = meta_details_row.get("image_protocol")
                result_data["image_domain"] = meta_details_row.get("image_domain")
                result_data["image_path"] = meta_details_row.get("image_path")
                result_data["image_etc"] = meta_details_row.get("image_etc")
                result_data["image_title"] = meta_details_row.get("image_title")
                result_data["detection_date"] = (
                    meta_details_row.get("detection_date").isoformat()
                    if meta_details_row.get("detection_date")
                    else None
                )
                result_data["risk_level"] = meta_details_row.get("risk_level")
                result_data["category"] = meta_details_row.get("category")
                result_data["source_table"] = meta_details_row.get("source_table_name")

                source_url = None
                if result_data.get("protocol") and result_data.get("domain"):
                    source_url = f'{result_data["protocol"]}://{result_data["domain"]}'
                    if result_data.get("url_path"):
                        source_url += f'/{result_data["url_path"]}'
                    if result_data.get("url_etc"):
                        source_url += f'{result_data["url_etc"]}'
                result_data["source_url"] = source_url

                full_image_url = None
                if result_data.get("image_protocol") and result_data.get(
                    "image_domain"
                ):
                    full_image_url = f'{result_data["image_protocol"]}://{result_data["image_domain"]}'
                    if result_data.get("image_path"):
                        full_image_url += f'/{result_data["image_path"]}'
                    if result_data.get("image_etc"):
                        full_image_url += f'{result_data["image_etc"]}'
                result_data["full_image_url"] = full_image_url
            else:
                p_warn(
                    f"No ImageBasedMain metadata found for PostgreSQL FaceID {face_id}."
                )

            if not milvus_attributes_fetched and not sql_metadata_fetched:
                p_error(
                    f"No data found for FaceID {face_id} from either Milvus or PostgreSQL."
                )
                return None

            return result_data

        except MilvusException as me:
            p_error(
                f"MilvusException in getFaceDetailsWithImage (FaceID: {face_id}): {me}\n{traceback.format_exc()}"
            )
            return None
        except psycopg2.Error as pe:
            p_error(
                f"Post psycopg2.Error in getFaceDetailsWithImage (FaceID: {face_id}): {pe}\n{traceback.format_exc()}"
            )
            if pg_conn:
                pg_conn.rollback()  # Normalde SELECT için rollback gerekmez ama emin olmak için.
            return None
        except Exception as e:
            p_error(
                f"Unexpected error in getFaceDetailsWithImage (FaceID: {face_id}): {e}\n{traceback.format_exc()}"
            )
            if pg_conn:
                pg_conn.rollback()
            return None
        finally:
            if pg_cursor:
                pg_cursor.close()
            if pg_conn:
                pg_conn.close()

    def searchWhiteListFaces(
        self,
        face_name=None,
        institution=None,
        category=None,
        start_date=None,
        end_date=None,
    ):
        """
        WhiteListFaces tablosunda SQL filtreleri ile arama yapar.
        Sadece SQL'de bulunan meta verileri ve base64 resmi döndürür.
        Vektör araması veya Milvus öznitelikleri içermez.

        Args:
            face_name: İsime göre filtreleme (ILIKE)
            institution: Kuruma göre filtreleme (ILIKE) - Şemada varsa
            category: Kategoriye göre filtreleme (ILIKE) - Şemada varsa
            start_date: Başlangıç tarihi (YYYY-MM-DD)
            end_date: Bitiş tarihi (YYYY-MM-DD)

        Returns:
            list: Eşleşen yüzlerin listesi (SQL meta verileri ve resim ile)
        """
        p_log(
            f"Searching WhiteListFaces (SQL only) with criteria: name={face_name}, inst={institution}, cat={category}, start={start_date}, end={end_date}"
        )
        conn = self.connect()
        if not conn:
            p_error("Database connection failed for searchWhiteListFaces.")
            return []
        cursor = conn.cursor(cursor_factory=DictCursor)
        results = []
        img_cursor = None

        try:
            # SQL Sorgusu: Vektör alanları hariç
            # Şemaya göre `Institution` ve `Category` yok, `FaceDescription` var.
            query = """
            SELECT "ID", "MilvusID", "FaceName", "FaceDescription", "FaceImageHash", "DetectionDate"
            FROM "WhiteListFaces"
            WHERE 1=1
            """

            params = []
            where_clauses = []

            if face_name:
                where_clauses.append('"FaceName" ILIKE %s')
                params.append(f"%{face_name}%")
            # Şemaya göre bu alanlar yok, FaceDescription eklenebilir.
            # if institution:
            #     where_clauses.append('"Institution" ILIKE %s')
            #     params.append(f"%{institution}%")
            # if category:
            #     where_clauses.append('"Category" ILIKE %s')
            #     params.append(f"%{category}%")
            if start_date:
                try:
                    datetime.datetime.strptime(start_date, "%Y-%m-%d")
                    where_clauses.append('"DetectionDate"::date >= %s::date')
                    params.append(start_date)
                except ValueError:
                    p_warn(
                        f"Invalid start date format for searchWhiteListFaces: {start_date}"
                    )
            if end_date:
                try:
                    datetime.datetime.strptime(end_date, "%Y-%m-%d")
                    where_clauses.append('"DetectionDate"::date <= %s::date')
                    params.append(end_date)
                except ValueError:
                    p_warn(
                        f"Invalid end date format for searchWhiteListFaces: {end_date}"
                    )

            if where_clauses:
                query += " AND " + " AND ".join(where_clauses)

            query += ' ORDER BY "DetectionDate" DESC'

            cursor.execute(query, tuple(params))
            faces = cursor.fetchall()

            img_cursor = conn.cursor(cursor_factory=DictCursor)
            try:
                for face in faces:
                    image_data = None
                    pg_face_id = face["ID"]
                    try:
                        # SQL şemasında WhiteListFaces.FaceImage var.
                        img_query = (
                            'SELECT "FaceImage" FROM "WhiteListFaces" WHERE "ID" = %s'
                        )
                        img_cursor.execute(img_query, (pg_face_id,))
                        image_result = img_cursor.fetchone()
                        if image_result and image_result["FaceImage"]:
                            image_data = base64.b64encode(
                                image_result["FaceImage"]
                            ).decode("utf-8")
                    except Exception as img_err:
                        p_error(
                            f"Whitelist FaceImage fetch/encode error (ID: {pg_face_id}): {str(img_err)}"
                        )

                    # Yaş, cinsiyet, skor gibi bilgiler Milvus'ta olduğu için burada None/varsayılan döndürülür.
                    results.append(
                        {
                            "id": pg_face_id,
                            "milvus_id": face.get("MilvusID"),
                            "face_name": face.get("FaceName"),
                            "face_description": face.get(
                                "FaceDescription"
                            ),  # Şemaya eklendi varsayımıyla
                            # "institution": None, # Şemada yok
                            # "category": None,    # Şemada yok
                            # "gender": None, # Milvus'ta
                            # "age": None,    # Milvus'ta
                            # "detection_score": None, # Milvus'ta
                            "detection_date": (
                                face.get("DetectionDate").isoformat()
                                if face.get("DetectionDate")
                                else None
                            ),
                            "image_hash": face.get("FaceImageHash"),
                            "image_data": image_data,
                            "source": "whitelist",
                        }
                    )
            finally:
                if img_cursor:
                    img_cursor.close()

            p_log(
                f"searchWhiteListFaces (SQL only) finished. Found {len(results)} faces."
            )
            return results

        except psycopg2.Error as pe:
            p_error(
                f"Post psycopg2.Error in searchWhiteListFaces: {pe}\n{traceback.format_exc()}"
            )
            if conn:
                conn.rollback()
            return []
        except Exception as e:
            p_error(
                f"Unexpected error in searchWhiteListFaces: {e}\n{traceback.format_exc()}"
            )
            if conn:
                conn.rollback()
            return []
        finally:
            # Ana cursor ve bağlantı kapatma
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def searchExternalFaces(
        self, face_name=None, start_date=None, end_date=None, alarm=None
    ):
        """
        ExternalFaceStorage tablosunda SQL filtreleri ile yüz arama.
        Sadece SQL'de bulunan meta verileri ve base64 resmi döndürür.
        Vektör araması veya Milvus öznitelikleri içermez.

        Args:
            face_name: Yüz ismine göre filtreleme (ILIKE).
            start_date: Başlangıç tarihi filtreleme (YYYY-MM-DD).
            end_date: Bitiş tarihi filtreleme (YYYY-MM-DD).
            alarm: Alarm durumuna göre filtreleme (boolean).

        Returns:
            list: Eşleşen yüzlerin listesi (SQL meta verileri ve resim ile).
        """
        p_log(
            f"Searching ExternalFaceStorage (SQL only) with criteria: name={face_name}, start={start_date}, end={end_date}, alarm={alarm}"
        )
        conn = self.connect()
        if not conn:
            p_error("Database connection failed for searchExternalFaces.")
            return []
        cursor = conn.cursor(cursor_factory=DictCursor)
        results = []
        img_cursor = None

        try:
            # SQL Sorgusu: Vektör alanları hariç
            query = """
            SELECT "ID", "MilvusID", "ImageHash", "FaceName", "FaceDescription", "Alarm", "DetectionDate"
            FROM "ExternalFaceStorage"
            WHERE 1=1
            """

            params = []
            where_clauses = []

            if face_name:
                where_clauses.append('"FaceName" ILIKE %s')
                params.append(f"%{face_name}%")
            if start_date:
                try:
                    datetime.datetime.strptime(start_date, "%Y-%m-%d")
                    where_clauses.append('"DetectionDate"::date >= %s::date')
                    params.append(start_date)
                except ValueError:
                    p_warn(
                        f"Invalid start date format for searchExternalFaces: {start_date}"
                    )
            if end_date:
                try:
                    datetime.datetime.strptime(end_date, "%Y-%m-%d")
                    where_clauses.append('"DetectionDate"::date <= %s::date')
                    params.append(end_date)
                except ValueError:
                    p_warn(
                        f"Invalid end date format for searchExternalFaces: {end_date}"
                    )
            if alarm is not None:
                # Ensure alarm is boolean
                if isinstance(alarm, bool):
                    where_clauses.append('"Alarm" = %s')
                    params.append(alarm)
                else:
                    p_warn(
                        f"Invalid type for alarm filter (expected bool): {type(alarm)}"
                    )

            if where_clauses:
                query += " AND " + " AND ".join(where_clauses)

            query += ' ORDER BY "DetectionDate" DESC'

            cursor.execute(query, tuple(params))
            faces = cursor.fetchall()

            img_cursor = conn.cursor(cursor_factory=DictCursor)
            try:
                for face in faces:
                    image_data = None
                    pg_face_id = face["ID"]
                    try:
                        # SQL şemasında ExternalFaceStorage.ImageData var.
                        img_query = 'SELECT "ImageData" FROM "ExternalFaceStorage" WHERE "ID" = %s'
                        img_cursor.execute(img_query, (pg_face_id,))
                        image_result = img_cursor.fetchone()
                        if image_result and image_result["ImageData"]:
                            image_data = base64.b64encode(
                                image_result["ImageData"]
                            ).decode("utf-8")
                    except Exception as img_err:
                        p_error(
                            f"External ImageData fetch/encode error (ID: {pg_face_id}): {str(img_err)}"
                        )

                    results.append(
                        {
                            "id": pg_face_id,
                            "milvus_id": face.get("MilvusID"),
                            "face_name": face.get("FaceName"),
                            "face_description": face.get("FaceDescription"),
                            "image_hash": face.get("ImageHash"),
                            "detection_date": (
                                face.get("DetectionDate").isoformat()
                                if face.get("DetectionDate")
                                else None
                            ),
                            # "gender": None, # Milvus'ta
                            # "age": None,    # Milvus'ta
                            # "detection_score": None, # Milvus'ta
                            "alarm": face.get("Alarm"),
                            "image_data": image_data,
                            "source": "external",
                        }
                    )
            finally:
                if img_cursor:
                    img_cursor.close()

            p_log(
                f"searchExternalFaces (SQL only) finished. Found {len(results)} faces."
            )
            return results

        except psycopg2.Error as pe:
            p_error(
                f"Post psycopg2.Error in searchExternalFaces: {pe}\n{traceback.format_exc()}"
            )
            if conn:
                conn.rollback()
            return []
        except Exception as e:
            p_error(
                f"Unexpected error in searchExternalFaces: {e}\n{traceback.format_exc()}"
            )
            if conn:
                conn.rollback()
            return []
        finally:
            # Ana cursor ve bağlantı kapatma
            if cursor:
                cursor.close()
            if conn:
                conn.close()
            # img_cursor zaten yukarıda kapatıldı

    def searchEgmArananlar(
        self,
        face_name=None,
        organizer=None,
        organizer_level=None,
        start_date=None,
        end_date=None,
    ):
        """
        EgmArananlar tablosunda yüz arama

        Args:
            face_name: Yüz ismine göre filtreleme
            organizer: Örgüt adına göre filtreleme
            organizer_level: Örgüt seviyesine göre filtreleme
            start_date: Başlangıç tarihi filtreleme
            end_date: Bitiş tarihi filtreleme

        Returns:
            list: Eşleşen yüzlerin listesi
        """
        conn = self.connect()
        cursor = conn.cursor(cursor_factory=DictCursor)
        results = []
        try:
            query = """
            SELECT "ID", "FaceName", "Organizer", "OrganizerLevel", "BirthDateAndLocation", "ImageHash", 
                   "DetectionScore", "FaceGender", "FaceAge", "DetectionDate"
            FROM "EgmArananlar"
            WHERE 1=1
            """

            params = []
            where_clauses = []

            # Filtreleme kriterleri ekle
            if face_name:
                where_clauses.append('"FaceName" ILIKE %s')
                params.append(f"%{face_name}%")

            if organizer:
                where_clauses.append('"Organizer" ILIKE %s')
                params.append(f"%{organizer}%")

            if organizer_level:
                where_clauses.append('"OrganizerLevel" ILIKE %s')
                params.append(f"%{organizer_level}%")

            if start_date:
                where_clauses.append('"DetectionDate" >= %s')
                params.append(start_date)

            if end_date:
                where_clauses.append('"DetectionDate" <= %s')
                params.append(end_date)

            if where_clauses:
                query += " AND" + " AND".join(where_clauses)

            # Tarihe göre sırala
            query += ' ORDER BY "DetectionDate" DESC'

            cursor.execute(query, tuple(params))

            # Sonuçları teker teker işle
            img_cursor = conn.cursor(
                cursor_factory=DictCursor
            )  # Resim için ayrı cursor
            try:
                while True:
                    face = cursor.fetchone()
                    if face is None:
                        break

                    # Base64 resim verisi oluştur
                    image_data = None
                    try:
                        # SQL sorgusunu güncelle ve resim verisini al
                        # ÖNEMLİ: Resim sütununun adı "ImageData" olarak varsayılıyor.
                        img_query = (
                            'SELECT "ImageData" FROM "EgmArananlar" WHERE "ID" = %s'
                        )
                        img_cursor.execute(img_query, (face["ID"],))
                        image_result = img_cursor.fetchone()
                        if image_result and image_result["ImageData"]:
                            image_data = base64.b64encode(
                                image_result["ImageData"]
                            ).decode("utf-8")
                    except Exception as img_err:
                        print(
                            f"EGM Resim verisi alınırken hata (ID: {face['ID']}): {str(img_err)}"
                        )

                    results.append(
                        {
                            "id": face["ID"],
                            "face_name": face["FaceName"],
                            "organizer": face["Organizer"],
                            "organizer_level": face["OrganizerLevel"],
                            "birth_date_location": face["BirthDateAndLocation"],
                            "image_hash": face["ImageHash"],
                            "detection_date": (
                                face["DetectionDate"].isoformat()
                                if face["DetectionDate"]
                                else None
                            ),
                            "gender": face["FaceGender"],
                            "age": face["FaceAge"],
                            "detection_score": float(face["DetectionScore"]),
                            "image_data": image_data,
                            "source": "egm",
                        }
                    )
            finally:
                if img_cursor:
                    img_cursor.close()

            return results

        except Exception as e:
            print(f"findSimilarEgmFaces hata: {str(e)}")  # Orijinal hata yönetimi
            traceback.print_exc()
            return []

        finally:
            self.releaseConnection(conn, cursor)

    def getFaceDetailsWithLandmarks(self, face_id):
        """
        EyeOfWeb Anti Terror - Yüz ID'sine göre landmark ve diğer detayları getirir
        """
        try:
            conn = self.connect()
            cursor = conn.cursor(cursor_factory=DictCursor)

            # Ana yüz verilerini getir
            query = """
                SELECT f.id, f.gender, f.age, f.domain, f.category, 
                       f.risk_level, f.detected_at, f.detection_score,
                       f.face_encoding, f.face_landmarks, f.face_image
                FROM Faces f 
                WHERE f.id = %s
            """
            cursor.execute(query, (face_id,))
            face_data = cursor.fetchone()

            if face_data:
                result = dict(face_data)

                # Landmark verileri varsa, numpy dizisine dönüştür
                if result["face_landmarks"] is not None:
                    result["face_landmarks"] = numpy.frombuffer(
                        result["face_landmarks"], dtype=numpy.float32
                    ).reshape(-1, 2)

                # Face encoding verileri numpy dizisine dönüştür
                if result["face_encoding"] is not None:
                    result["face_encoding"] = numpy.frombuffer(
                        result["face_encoding"], dtype=numpy.float32
                    )

                # Yüz görseli varsa base64 formatına dönüştür
                if result["face_image"] is not None:
                    result["image_data"] = base64.b64encode(
                        result["face_image"]
                    ).decode("utf-8")

                return {"success": True, "face": result}
            else:
                return {"success": False, "message": "Yüz bulunamadı"}
        except Exception as e:
            return {"success": False, "message": f"Hata: {str(e)}"}
        finally:
            self.releaseConnection(conn, cursor)

    def getWhitelistFaceDetailsWithLandmarks(self, face_id):
        """
        EyeOfWeb Anti Terror - Beyaz liste yüz ID'sine göre landmark ve diğer detayları getirir
        """
        try:
            conn = self.connect()
            cursor = conn.cursor(cursor_factory=DictCursor)

            # Beyaz liste yüz verilerini getir
            query = """
                SELECT f.id, f.gender, f.age, f.face_name, f.institution, f.category, 
                       f.detection_score, f.face_encoding, f.face_landmarks, f.face_image
                FROM WhiteListFaces f 
                WHERE f.id = %s
            """
            cursor.execute(query, (face_id,))
            face_data = cursor.fetchone()

            if face_data:
                result = dict(face_data)

                # Landmark verileri varsa, numpy dizisine dönüştür
                if result["face_landmarks"] is not None:
                    result["face_landmarks"] = numpy.frombuffer(
                        result["face_landmarks"], dtype=numpy.float32
                    ).reshape(-1, 2)

                # Face encoding verileri numpy dizisine dönüştür
                if result["face_encoding"] is not None:
                    result["face_encoding"] = numpy.frombuffer(
                        result["face_encoding"], dtype=numpy.float32
                    )

                # Yüz görseli varsa base64 formatına dönüştür
                if result["face_image"] is not None:
                    result["image_data"] = base64.b64encode(
                        result["face_image"]
                    ).decode("utf-8")

                return {"success": True, "face": result}
            else:
                return {"success": False, "message": "Beyaz liste yüzü bulunamadı"}
        except Exception as e:
            return {"success": False, "message": f"Hata: {str(e)}"}
        finally:
            self.releaseConnection(conn, cursor)

    def getEgmFaceDetailsWithLandmarks(self, face_id):
        """
        EyeOfWeb Anti Terror - EGM aranan yüz ID'sine göre landmark ve diğer detayları getirir
        """
        try:
            conn = self.connect()
            cursor = conn.cursor(cursor_factory=DictCursor)

            # EGM aranan yüz verilerini getir
            query = """
                SELECT f.id, f.gender, f.age, f.organizer, f.organizer_level, 
                       f.description, f.risk_level, f.detection_score, 
                       f.face_encoding, f.face_landmarks, f.face_image
                FROM EgmWantedFaces f 
                WHERE f.id = %s
            """
            cursor.execute(query, (face_id,))
            face_data = cursor.fetchone()

            if face_data:
                result = dict(face_data)

                # Landmark verileri varsa, numpy dizisine dönüştür
                if result["face_landmarks"] is not None:
                    result["face_landmarks"] = numpy.frombuffer(
                        result["face_landmarks"], dtype=numpy.float32
                    ).reshape(-1, 2)

                # Face encoding verileri numpy dizisine dönüştür
                if result["face_encoding"] is not None:
                    result["face_encoding"] = numpy.frombuffer(
                        result["face_encoding"], dtype=numpy.float32
                    )

                # Yüz görseli varsa base64 formatına dönüştür
                if result["face_image"] is not None:
                    result["image_data"] = base64.b64encode(
                        result["face_image"]
                    ).decode("utf-8")

                return {"success": True, "face": result}
            else:
                return {"success": False, "message": "EGM aranan yüzü bulunamadı"}
        except Exception as e:
            return {"success": False, "message": f"Hata: {str(e)}"}
        finally:
            self.releaseConnection(conn, cursor)

    def getImageBinaryByID(self, image_id):
        """Verilen ImageID için BinaryImage verisini döndürür."""
        conn = self.connect()
        cursor = conn.cursor(cursor_factory=DictCursor)
        try:
            cursor.execute(
                'SELECT "BinaryImage" FROM "ImageID" WHERE "ID" = %s', (image_id,)
            )
            result = cursor.fetchone()
            if result and result["BinaryImage"]:
                return True, bytes(result["BinaryImage"])  # Ensure it's bytes
            else:
                return False, None
        except Exception as e:
            print(f"Error fetching image binary by ID {image_id}: {e}")
            traceback.print_exc()
            return False, None
        finally:
            self.releaseConnection(conn, cursor)

    def get_embedding_by_id(self, face_id: int) -> np.ndarray | None:
        """
        Verilen PostgreSQL EyeOfWebFaceID.ID'si için Milvus'tan yüz embedding vektörünü alır.

        Args:
            face_id: PostgreSQL EyeOfWebFaceID tablosundaki yüz ID'si.

        Returns:
            NumPy array olarak yüz embedding'i veya bulunamazsa None.
        """
        p_log(f"Attempting to get embedding for PostgreSQL FaceID: {face_id}")
        pg_conn = None
        pg_cursor = None
        embedding_data = None

        try:
            # 1. PostgreSQL'den MilvusReferansID'yi al
            pg_conn = self.connect()
            if not pg_conn:
                p_error(
                    f"Database connection failed for get_embedding_by_id (FaceID: {face_id})."
                )
                return None
            pg_cursor = pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql_get_milvus_ref = (
                'SELECT "MilvusRefID" FROM "EyeOfWebFaceID" WHERE "ID" = %s'
            )
            pg_cursor.execute(sql_get_milvus_ref, (face_id,))
            milvus_ref_record = pg_cursor.fetchone()

            if not milvus_ref_record or milvus_ref_record["MilvusRefID"] is None:
                p_warn(
                    f"No MilvusRefID found in EyeOfWebFaceID for PostgreSQL FaceID {face_id}. Cannot fetch embedding from Milvus."
                )
                return None

            milvus_ref_id = milvus_ref_record["MilvusRefID"]
            p_log(
                f"Found MilvusRefID: {milvus_ref_id} for PostgreSQL FaceID: {face_id}. Querying Milvus."
            )

            # 2. Milvus'tan embedding verisini çek
            milvus_collection = get_milvus_collection(
                EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME
            )
            if not milvus_collection:
                p_error(
                    f"Failed to get Milvus collection '{EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME}' for FaceID: {face_id} (MilvusRefID: {milvus_ref_id})."
                )
                return None

            # Milvus sorgusu: id == milvus_ref_id
            # output_fields sadece embedding'i içermeli
            query_expr = f"id == {milvus_ref_id}"
            milvus_results = milvus_collection.query(
                expr=query_expr,
                output_fields=["face_embedding_data"],  # Sadece embedding vektörünü çek
                limit=1,  # ID unique olmalı
            )

            if milvus_results:
                # milvus_results bir liste döner, ilk elemanı alıyoruz
                milvus_entity = milvus_results[0]
                raw_embedding = milvus_entity.get("face_embedding_data")
                if raw_embedding:
                    embedding_data = np.array(raw_embedding, dtype=np.float32)
                    if embedding_data.size == 512:  # Beklenen boyut kontrolü
                        p_log(
                            f"Successfully fetched embedding from Milvus for MilvusRefID: {milvus_ref_id}"
                        )
                    else:
                        p_warn(
                            f"Fetched embedding for MilvusRefID {milvus_ref_id} has unexpected size: {embedding_data.size}. Expected 512."
                        )
                        embedding_data = None  # Boyut yanlışsa None döndür
                else:
                    p_warn(
                        f"'face_embedding_data' field not found or is null in Milvus for MilvusRefID: {milvus_ref_id}."
                    )
            else:
                p_warn(
                    f"No data found in Milvus for MilvusRefID {milvus_ref_id} (linked to PostgreSQL FaceID {face_id})."
                )

        except MilvusException as me:
            p_error(
                f"MilvusException in get_embedding_by_id (FaceID: {face_id}, MilvusRefID: {milvus_ref_id if 'milvus_ref_id' in locals() else 'N/A'}): {me}"
            )
            traceback.print_exc()
            embedding_data = None
        except psycopg2.Error as pe:
            p_error(
                f"PostgreSQL error in get_embedding_by_id (FaceID: {face_id}): {pe}"
            )
            traceback.print_exc()
            if pg_conn:
                pg_conn.rollback()  # Genelde SELECT için gerekmez ama hata durumunda.
            embedding_data = None
        except Exception as e:
            p_error(f"Unexpected error in get_embedding_by_id (FaceID: {face_id}): {e}")
            traceback.print_exc()
            embedding_data = None

        finally:
            if pg_cursor:
                pg_cursor.close()
            if pg_conn:
                pg_conn.close()  # self.releaseConnection yerine doğrudan close kullanılabilir.

        return embedding_data

    def searchFaces(
        self,
        domain=None,
        risk_level=None,
        category=None,
        start_date=None,
        end_date=None,
        page=1,
        per_page=50,
    ):
        """
        Veritabanında yüzleri arar (search.html kriterlerine göre) ve sayfalar.
        Milvus'tan yüz özniteliklerini (landmark, bbox dahil) alır.

        Args:
            domain (str, optional): Aranacak domain.
            risk_level (str, optional): Aranacak risk seviyesi.
            category (str, optional): Aranacak kategori.
            start_date (str, optional): Başlangıç tarihi (YYYY-MM-DD).
            end_date (str, optional): Bitiş tarihi (YYYY-MM-DD).
            page (int, optional): Sayfa numarası.
            per_page (int, optional): Sayfa başına sonuç sayısı.

        Returns:
            tuple: (list: Bulunan yüzlerin listesi (mevcut sayfa için), int: Toplam eşleşen yüz sayısı)
        """
        p_log(
            f"Searching faces with criteria: domain={domain}, risk={risk_level}, cat={category}, start={start_date}, end={end_date}, page={page}, per_page={per_page}"
        )
        results = []
        total_count = 0
        pg_conn = None
        pg_cursor = None

        try:
            pg_conn = self.connect()
            if not pg_conn:
                p_error("Database connection failed for searchFaces.")
                return [], 0
            pg_cursor = pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # 1. SQL Filtrelerini ve Parametrelerini Oluştur
            params = []
            filter_conditions = []
            joins = """
                FROM "EyeOfWebFaceID" f
                JOIN "ImageBasedMain" m ON f."ID" = ANY(m."FaceID")
                LEFT JOIN "BaseDomainID" bd ON m."BaseDomainID" = bd."ID"
                LEFT JOIN "WebSiteCategoryID" wc ON m."CategoryID" = wc."ID" 
            """
            # Not: UrlPathID, UrlEtcID, ImageUrlPathID, ImageUrlEtcID joinleri
            #      sadece çıktı için gerekiyorsa SELECT kısmına eklenebilir, filtrelemede kullanılmıyor.

            if domain:
                filter_conditions.append('bd."Domain" = %s')
                params.append(domain)
            if risk_level:
                filter_conditions.append('m."RiskLevel" = %s')
                params.append(risk_level)
            if category:
                filter_conditions.append('wc."Category" = %s')
                params.append(category)
            if start_date:
                try:
                    datetime.datetime.strptime(start_date, "%Y-%m-%d")
                    filter_conditions.append('m."DetectionDate"::date >= %s::date')
                    params.append(start_date)
                except ValueError:
                    p_warn(
                        f"Geçersiz başlangıç tarihi formatı: {start_date}. Filtre uygulanmayacak."
                    )
            if end_date:
                try:
                    datetime.datetime.strptime(end_date, "%Y-%m-%d")
                    filter_conditions.append('m."DetectionDate"::date <= %s::date')
                    params.append(end_date)
                except ValueError:
                    p_warn(
                        f"Geçersiz bitiş tarihi formatı: {end_date}. Filtre uygulanmayacak."
                    )

            where_clause = (
                " AND ".join(filter_conditions) if filter_conditions else "1=1"
            )
            base_params = tuple(params)

            # 2. Toplam Sayıyı Al (DISTINCT f."ID" önemli)
            count_query = f"""SELECT COUNT(DISTINCT f."ID") as total_count {joins} WHERE {where_clause}"""
            pg_cursor.execute(count_query, base_params)
            count_result = pg_cursor.fetchone()
            total_count = count_result["total_count"] if count_result else 0
            p_log(f"Total matching face records found (SQL count): {total_count}")

            if total_count == 0:
                return [], 0

            # 3. Sayfalama için OFFSET Hesapla
            try:
                page = int(page)
                per_page = int(per_page)
                if page < 1:
                    page = 1
                if per_page < 1:
                    per_page = 10  # Min per_page
                if per_page > 100:
                    per_page = 100  # Max per_page (isteğe bağlı)
            except (ValueError, TypeError):
                page = 1
                per_page = 10  # Varsayılan
            offset = (page - 1) * per_page

            # 4. Mevcut Sayfa için Ana SQL Sorgusu (pg_face_id ve MilvusRefID al)
            #    Ayrıca ImageBasedMain'den de gerekli temel bilgileri alalım.
            main_sql_query = f"""
            SELECT DISTINCT ON (f."ID") 
                f."ID" as pg_face_id, 
                f."MilvusRefID" as milvus_ref_id,
                m."ImageID" as image_id,      
                m."Protocol" as source_protocol,
                bd."Domain" as source_domain,
                up."Path" as source_url_path, 
                ue."Etc" as source_url_etc,   
                m."ImageProtocol" as image_protocol,
                id_img."Domain" as image_domain,
                ip."Path" as image_path,
                ie."Etc" as image_etc,
                it."Title" as image_title,
                wc."Category" as category_name, -- category zaten parametre adı, karışmasın
                m."RiskLevel" as risk_level_val, -- risk_level zaten parametre adı
                m."DetectionDate" as detection_date,
                m."Source" as source_table_name
            {joins}
            LEFT JOIN "UrlPathID" up ON m."UrlPathID" = up."ID"
            LEFT JOIN "UrlEtcID" ue ON m."UrlEtcID" = ue."ID"
            LEFT JOIN "BaseDomainID" id_img ON m."ImageDomainID" = id_img."ID" 
            LEFT JOIN "ImageUrlPathID" ip ON m."ImagePathID" = ip."ID"
            LEFT JOIN "ImageUrlEtcID" ie ON m."ImageUrlEtcID" = ie."ID"
            LEFT JOIN "ImageTitleID" it ON m."ImageTitleID" = it."ID"
            WHERE {where_clause}
            ORDER BY f."ID", m."DetectionDate" DESC -- DISTINCT ON için en güncel ImageBasedMain kaydını seçer
            LIMIT %s OFFSET %s
            """

            final_params = base_params + (per_page, offset)
            pg_cursor.execute(main_sql_query, final_params)
            sql_results_for_page = pg_cursor.fetchall()
            p_log(
                f"Fetched {len(sql_results_for_page)} records from SQL for page {page}"
            )

            # HATA AYIKLAMA: İlk birkaç SQL sonucunu kontrol et
            if sql_results_for_page:
                p_log(
                    f"DEBUG: Sample SQL results - First record: pg_face_id={sql_results_for_page[0].get('pg_face_id')}, milvus_ref_id={sql_results_for_page[0].get('milvus_ref_id')}"
                )

            if not sql_results_for_page:
                return [], total_count  # Sayfa boş olabilir ama toplam sayı olabilir

            # 5. Milvus'tan Yüz Özniteliklerini Toplu Çek
            milvus_ref_ids_to_fetch = [
                row["milvus_ref_id"]
                for row in sql_results_for_page
                if row["milvus_ref_id"]
            ]
            milvus_attributes_map = {}

            # HATA AYIKLAMA: MilvusRefID'leri logla
            p_log(
                f"DEBUG: Found {len(milvus_ref_ids_to_fetch)} MilvusRefIDs in SQL results"
            )
            if not milvus_ref_ids_to_fetch:
                p_error(
                    "ERROR: No MilvusRefIDs found in SQL results - this is a critical database synchronization issue!"
                )

            if milvus_ref_ids_to_fetch:
                milvus_collection = get_milvus_collection(
                    EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME
                )
                if milvus_collection:
                    # id'ler int olmalı, string değil Milvus sorgusu için
                    expr_milvus_ids = ",".join(map(str, milvus_ref_ids_to_fetch))
                    p_log(
                        f"Querying Milvus for {len(milvus_ref_ids_to_fetch)} MilvusRefIDs: {expr_milvus_ids[:200]}..."
                    )
                    milvus_query_results = milvus_collection.query(
                        expr=f"id in [{expr_milvus_ids}]",
                        output_fields=[
                            "id",
                            "face_gender",
                            "face_age",
                            "detection_score",
                            "face_box",
                            "landmarks_2d",
                        ],
                    )
                    for item in milvus_query_results:
                        milvus_attributes_map[item["id"]] = (
                            item  # Milvus ID'sine göre map yap
                        )
                    p_log(
                        f"Fetched {len(milvus_attributes_map)} attribute sets from Milvus."
                    )

                    # HATA AYIKLAMA: MilvusRefID'ler ile Milvus sonuçlarını karşılaştır
                    missing_ids = [
                        mid
                        for mid in milvus_ref_ids_to_fetch
                        if mid not in milvus_attributes_map
                    ]
                    if missing_ids:
                        p_error(
                            f"ERROR: {len(missing_ids)} MilvusRefIDs could not be found in Milvus: {missing_ids[:5]}..."
                        )
                else:
                    p_error(
                        "CRITICAL: Failed to get Milvus collection for searchFaces attribute fetch."
                    )

            # 6. Sonuçları Birleştir ve Resimleri Al
            for row in sql_results_for_page:
                pg_face_id = row["pg_face_id"]
                milvus_ref_id = row["milvus_ref_id"]

                face_data = dict(row)  # SQL'den gelen tüm meta veriler
                # Varsayılan olarak ID'yi ayarla
                face_data["id"] = pg_face_id

                # Milvus'tan gelen öznitelikleri ekle
                if milvus_ref_id and milvus_ref_id in milvus_attributes_map:
                    milvus_attrs = milvus_attributes_map[milvus_ref_id]
                    # Boolean gender değerini metin formatına dönüştür
                    gender_value = milvus_attrs.get("face_gender")
                    if gender_value is True:
                        face_data["gender"] = "Erkek"
                    elif gender_value is False:
                        face_data["gender"] = "Kadın"
                    else:
                        face_data["gender"] = "Bilinmiyor"

                    face_data["age"] = milvus_attrs.get("face_age")
                    face_data["detection_score"] = milvus_attrs.get("detection_score")
                    face_data["facebox"] = milvus_attrs.get(
                        "face_box"
                    )  # Liste olarak bekleniyor

                    landmarks_flat = milvus_attrs.get("landmarks_2d")
                    if landmarks_flat and len(landmarks_flat) == 212:
                        try:
                            face_data["landmarks_2d"] = (
                                np.array(landmarks_flat, dtype=np.float32)
                                .reshape((106, 2))
                                .tolist()
                            )
                        except ValueError as e:
                            p_error(
                                f"Error reshaping landmarks for MilvusID {milvus_ref_id} in searchFaces: {e}"
                            )
                            face_data["landmarks_2d"] = None
                    else:
                        face_data["landmarks_2d"] = None
                else:
                    # Milvus'tan öznitelik gelmediyse veya MilvusRefID yoksa alanları varsayılan değerlere ayarla
                    p_warn(
                        f"No Milvus attributes found for face_id={pg_face_id}, milvus_id={milvus_ref_id}"
                    )
                    face_data["gender"] = "Bilinmiyor"
                    face_data["age"] = 0
                    face_data["detection_score"] = 0.0
                    face_data["facebox"] = None
                    face_data["landmarks_2d"] = None

                # URL'leri oluştur
                source_url = None
                if face_data.get("source_protocol") and face_data.get("source_domain"):
                    source_url = (
                        f'{face_data["source_protocol"]}://{face_data["source_domain"]}'
                    )
                    if face_data.get("source_url_path"):
                        source_url += f'/{face_data["source_url_path"]}'
                    if face_data.get("source_url_etc"):
                        source_url += f'{face_data["source_url_etc"]}'
                face_data["source_url"] = source_url

                full_image_url = None
                if face_data.get("image_protocol") and face_data.get("image_domain"):
                    full_image_url = (
                        f'{face_data["image_protocol"]}://{face_data["image_domain"]}'
                    )
                    if face_data.get("image_path"):
                        full_image_url += f'/{face_data["image_path"]}'
                    if face_data.get("image_etc"):
                        full_image_url += f'{face_data["image_etc"]}'
                face_data["full_image_url"] = full_image_url

                # Tarih formatını düzelt
                if face_data.get("detection_date"):
                    face_data["detection_date"] = face_data[
                        "detection_date"
                    ].isoformat()

                # Resim binary verisini alıp base64 olarak ekle
                face_data["image_data_base64"] = None
                face_data["image_data"] = None  # Template'in beklediği format için ekle
                face_data["use_default_image"] = True  # Varsayılan olarak true

                image_content_id = face_data.get(
                    "image_id"
                )  # Bu ImageID tablosunun ID'si
                if image_content_id:
                    success, binary_data = self.getImageBinaryByID(image_content_id)
                    if success and binary_data:
                        try:
                            decompressed_binary = decompress_image(binary_data)
                            if isinstance(decompressed_binary, bytes):
                                image_b64 = base64.b64encode(
                                    decompressed_binary
                                ).decode("utf-8")
                                face_data["image_data_base64"] = image_b64
                                face_data["image_data"] = (
                                    image_b64  # Template için image_data alanı
                                )
                                face_data["use_default_image"] = False  # Resim bulundu
                                face_data["image_mime_type"] = (
                                    "image/png"  # Decompress sonrası PNG
                                )
                        except Exception as encode_err:
                            p_error(
                                f"Error decompressing/encoding image_id {image_content_id} for searchFaces (pg_face_id: {pg_face_id}): {encode_err}"
                            )

                results.append(face_data)

            # HATA AYIKLAMA: Sonuçları logla
            for idx, face_data in enumerate(results[:3]):  # İlk 3 sonuç için
                p_log(
                    f"DEBUG: Result #{idx+1} - id: {face_data.get('id')}, gender: {face_data.get('gender')}, age: {face_data.get('age')}, has_image: {'Evet' if not face_data.get('use_default_image') else 'Hayır'}"
                )

            p_log(
                f"searchFaces finished for page {page}. Returning {len(results)} faces. Total count: {total_count}"
            )
            return results, total_count

        except MilvusException as me:
            p_error(f"MilvusException in searchFaces: {me}\n{traceback.format_exc()}")
            return [], 0
        except psycopg2.Error as pe:
            p_error(
                f"Post psycopg2.Error in searchFaces: {pe}\n{traceback.format_exc()}"
            )
            if pg_conn:
                pg_conn.rollback()
            return [], 0
        except Exception as e:
            p_error(f"Unexpected error in searchFaces: {e}\n{traceback.format_exc()}")
            if pg_conn:
                pg_conn.rollback()
            return [], 0
        finally:
            if pg_cursor:
                pg_cursor.close()
            if pg_conn:
                pg_conn.close()

    def findSimilarWhiteListFaces(
        self, face_embedding, threshold=0.6, algorithm="cosine", use_cuda=False
    ):
        """Beyaz liste içinde benzer yüzleri bul (pgvector kullanarak).
           Sonuçlar sadece temel bilgileri ve base64 resmi içerir.

        Args:
            face_embedding: Aranacak yüz gömme vektörü (numpy array)
            threshold: Benzerlik eşiği (0.0-1.0 arası)
            # algorithm & use_cuda artık kullanılmıyor

        Returns:
            list: Bulunan benzer yüzlerin listesi
        """
        conn = self.connect()
        cursor = conn.cursor(cursor_factory=DictCursor)
        similar_faces = []
        img_cursor = None
        try:
            embedding_str = str(
                face_embedding.tolist()
            )  # <<< YENİ: String formatına çevir
            distance_threshold = 1 - threshold  # Mesafeye çevir

            # 1. Adım: Benzer yüzleri ve temel bilgileri çek
            # Kosinüs mesafesi hesapla, filtrele ve sırala.
            # FaceDescription sütunu eklendi (varsa).
            query = """
            SELECT
                "ID",
                "FaceName",
                "FaceDescription", -- Eklendi
                -- "Institution", -- Şemada yok
                -- "Category",    -- Şemada yok
                "FaceImageHash",
                "DetectionScore",
                "FaceGender",
                "FaceAge",
                "DetectionDate", -- InsertionDate yerine
                "FaceEmbeddingData" <=> %s::vector AS distance, -- <<< YENİ: ::vector ve string parametre
                1 - ("FaceEmbeddingData" <=> %s::vector) AS similarity -- <<< YENİ: ::vector ve string parametre
            FROM "WhiteListFaces"
            WHERE "FaceEmbeddingData" IS NOT NULL AND ("FaceEmbeddingData" <=> %s::vector) < %s -- <<< YENİ: ::vector ve string parametre
            ORDER BY distance ASC
            """
            # Pass embedding_str for vector comparison
            cursor.execute(
                query, (embedding_str, embedding_str, embedding_str, distance_threshold)
            )
            similar_raw = cursor.fetchall()  # Önce benzerleri al

            p_log(
                f"pgvector (Whitelist): Eşik ({threshold} / mesafe < {distance_threshold:.4f}) üzerinde {len(similar_raw)} yüz bulundu."
            )

            # 2. Adım: Resimleri çek ve sonuçları formatla
            img_cursor = conn.cursor(
                cursor_factory=DictCursor
            )  # Resim için ayrı cursor
            try:
                for face in similar_raw:
                    face_id = face["ID"]
                    image_data = None
                    try:
                        # Şemaya göre sütun adı "FaceImage"
                        img_query = (
                            'SELECT "FaceImage" FROM "WhiteListFaces" WHERE "ID" = %s'
                        )
                        img_cursor.execute(img_query, (face_id,))
                        image_result = img_cursor.fetchone()
                        if image_result and image_result["FaceImage"]:
                            # Whitelist resimleri sıkıştırılmış mı? Değilse direkt encode et.
                            # Şimdilik sıkıştırılmadığını varsayıyoruz.
                            image_data = base64.b64encode(
                                image_result["FaceImage"]
                            ).decode("utf-8")
                    except Exception as img_err:
                        p_error(
                            f"Whitelist Resim verisi alınırken/encode edilirken hata (ID: {face_id}): {str(img_err)}"
                        )

                    face_dict = {
                        "id": face_id,
                        "similarity": float(face["similarity"]),
                        "face_name": face["FaceName"],
                        "face_description": face.get(
                            "FaceDescription"
                        ),  # .get() kullan
                        # "institution": face.get("Institution"), # Yok
                        # "category": face.get("Category"),       # Yok
                        "gender": face["FaceGender"],
                        "age": face["FaceAge"],
                        "detection_score": (
                            float(face["DetectionScore"])
                            if face["DetectionScore"] is not None
                            else 0.0
                        ),
                        "insertion_date": (
                            face["DetectionDate"].isoformat()
                            if face["DetectionDate"]
                            else None
                        ),  # Tarih sütunu adı düzeltildi
                        "image_data": image_data,
                        "source": "whitelist",
                    }
                    similar_faces.append(face_dict)
            finally:
                if img_cursor:
                    img_cursor.close()

            # Sıralama SQL'de yapıldı (distance ASC -> similarity DESC)
            return similar_faces

        except Exception as e:
            p_error(f"findSimilarWhiteListFaces (pgvector) hata: {str(e)}")
            traceback.print_exc()
            return []
        finally:
            self.releaseConnection(conn, cursor)  # Ana cursor ve bağlantıyı kapat
            # img_cursor zaten yukarıda kapatıldı

    def findSimilarFacesWithImages(
        self,
        face_embedding: np.ndarray,
        threshold=0.6,
        limit=100,
        algorithm="cosine",
        use_cuda=False,
    ):
        """
        Milvus'ta benzer yüzleri arar ve resim bilgilerini PostgreSQL'den zenginleştirerek döndürür.

        Args:
            face_embedding: Aranacak yüz gömme vektörü (numpy array).
            threshold: Benzerlik eşiği (0.0-1.0 arası). Milvus COSINE distance için 1-threshold kullanılır.
            limit: Milvus'tan istenecek maksimum sonuç sayısı (filtrelenmeden önce).
            # algorithm & use_cuda artık Milvus bağlamında burada doğrudan kullanılmıyor.
            # Metrik tipi Milvus koleksiyonunun indeksinde tanımlıdır.

        Returns:
            list: Bulunan benzer yüzlerin listesi (resim URL'leri veya base64 dahil).
        """
        p_log(
            f"Starting findSimilarFacesWithImages with threshold: {threshold}, Milvus limit: {limit}"
        )
        similar_faces_output = []
        pg_conn = None
        pg_cursor = None

        try:
            # 1. Milvus Bağlantısı ve Koleksiyon Alma
            milvus_collection = get_milvus_collection(
                EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME
            )
            if not milvus_collection:
                p_error(
                    "Failed to get Milvus collection for findSimilarFacesWithImages."
                )
                return []

            # 2. Milvus'ta Benzerlik Araması
            # Embedding'i Milvus'un beklediği formata getir (liste içinde float listesi)
            search_vector = [face_embedding.tolist()]

            # Metrik tipi COSINE ise, distance = 1 - similarity.
            # Arama yaparken distance'a göre filtreleme yapacağız.
            # Milvus search() doğrudan similarity score vermez, distance verir.
            # Biz threshold'u similarity üzerinden alıyoruz.
            # Milvus search genellikle en yakın K sonucu verir, sonra biz filtreleriz.
            # HNSW gibi indeksler için arama parametreleri (örn: ef)
            search_params = {
                "metric_type": "COSINE",
                "params": {
                    "ef": max(1200, limit * 1.2)
                },  # ef değeri limit'ten en az %20 büyük ve minimum 1200 olmalı
            }

            p_info(
                f"Searching Milvus collection '{EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME}' with limit {limit} and ef={search_params['params']['ef']}..."
            )
            milvus_results = milvus_collection.search(
                data=search_vector,
                anns_field="face_embedding_data",  # Şemadaki vektör alanı
                param=search_params,
                limit=limit,  # Milvus'tan kaç sonuç isteneceği
                expr=None,  # Ek filtreleme ifadesi (şimdilik None)
                output_fields=[
                    "id",
                    "face_gender",
                    "face_age",
                    "detection_score",
                    "face_box",
                    "landmarks_2d",
                    "detection_date_ts",
                ],
                consistency_level="Strong",  # Veya uygulamanız için uygun olan
            )
            p_log(
                f"Milvus search returned {len(milvus_results[0]) if milvus_results else 0} raw hits."
            )

            # 3. PostgreSQL Bağlantısı
            pg_conn = self.connect()
            if not pg_conn:
                p_error("Database connection failed for enriching Milvus results.")
                return []  # Veya sadece Milvus sonuçlarını döndür
            pg_cursor = pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # 4. Sonuçları İşle, Filtrele ve Zenginleştir
            processed_face_pg_ids = (
                set()
            )  # Aynı pg_face_id'nin birden fazla Milvus ID'si ile eşleşmesini önlemek için (eğer mümkünse)

            distance_threshold = 1 - threshold  # Eşik değerini mesafeye çevir
            p_log(
                f"Converted similarity threshold {threshold} to distance threshold {distance_threshold:.4f}"
            )

            for hits_for_query in milvus_results:
                for hit in hits_for_query:
                    milvus_id = hit.id
                    distance = hit.distance
                    # similarity_score = 1 - distance # Eski hesaplama
                    similarity_score = distance  # YENİ: Kullanıcı isteği - distance'ı similarity olarak kullan

                    # Filtreleme hala orijinal threshold mantığına göre yapılmalı (distance üzerinden)
                    if similarity_score >= threshold:
                        p_log(
                            f"Milvus Hit: MilvusID={milvus_id}, Distance={distance:.4f} - Below distance threshold {distance_threshold:.4f} (Original Sim Threshold: {threshold})"
                        )

                        # Milvus'tan gelen yüz verileri
                        entity = hit.entity
                        milvus_gender = entity.get("face_gender")
                        milvus_age = entity.get("face_age")
                        milvus_det_score = entity.get("detection_score")
                        milvus_face_box_list = entity.get(
                            "face_box"
                        )  # Liste olarak bekleniyor
                        milvus_landmarks_flat_list = entity.get(
                            "landmarks_2d"
                        )  # Düz liste olarak bekleniyor (212 eleman)
                        # milvus_detection_date_ts = entity.get("detection_date_ts") # Epoch timestamp

                        # landmarks_2d'yi (106, 2) şekline getir
                        landmarks_2d_np = None
                        if (
                            milvus_landmarks_flat_list
                            and len(milvus_landmarks_flat_list) == 212
                        ):
                            try:
                                landmarks_2d_np = np.array(
                                    milvus_landmarks_flat_list, dtype=np.float32
                                ).reshape((106, 2))
                            except ValueError as e:
                                p_error(
                                    f"Error reshaping landmarks_2d for MilvusID {milvus_id}: {e}. Data: {milvus_landmarks_flat_list[:10]}..."
                                )
                                landmarks_2d_np = None

                        facebox_data = milvus_face_box_list  # Zaten liste olmalı

                        # Milvus ID'sini kullanarak PostgreSQL'den EyeOfWebFaceID.ID'yi al
                        pg_cursor.execute(
                            'SELECT "ID" FROM "EyeOfWebFaceID" WHERE "MilvusRefID" = %s',
                            (milvus_id,),
                        )
                        pg_face_record = pg_cursor.fetchone()

                        if not pg_face_record:
                            p_warn(
                                f"No corresponding PostgreSQL EyeOfWebFaceID found for MilvusID {milvus_id}. Skipping."
                            )
                            continue

                        pg_face_id = pg_face_record["ID"]

                        if pg_face_id in processed_face_pg_ids:
                            p_log(
                                f"PostgreSQL FaceID {pg_face_id} (from MilvusID {milvus_id}) already processed. Skipping duplicate enrichment."
                            )
                            continue
                        processed_face_pg_ids.add(pg_face_id)

                        # PostgreSQL'den ImageBasedMain ve diğer detayları çek
                        # Bu sorgu, orijinal koddaki CTE'ye benzer şekilde detayları alır.
                        # FaceID (pg_face_id) ImageBasedMain.FaceID (array) içinde aranır.
                        sql_details = """
                        SELECT
                            m."ImageID" as image_id,
                            m."Protocol" as source_protocol,
                            bd."Domain" as source_domain,
                            up."Path" as source_path,
                            ue."Etc" as source_etc,
                            m."ImageProtocol" as image_protocol,
                            id_img."Domain" as image_domain,
                            ip."Path" as image_path,
                            ie."Etc" as image_etc,
                            it."Title" as image_title,
                            wc."Category" as category,
                            m."RiskLevel" as risk_level,
                            m."DetectionDate" as detection_date,
                            m."Source" as source_table_name 
                        FROM "ImageBasedMain" m
                        LEFT JOIN "BaseDomainID" bd ON m."BaseDomainID" = bd."ID"
                        LEFT JOIN "UrlPathID" up ON m."UrlPathID" = up."ID"
                        LEFT JOIN "UrlEtcID" ue ON m."UrlEtcID" = ue."ID"
                        LEFT JOIN "BaseDomainID" id_img ON m."ImageDomainID" = id_img."ID"
                        LEFT JOIN "ImageUrlPathID" ip ON m."ImagePathID" = ip."ID"
                        LEFT JOIN "ImageUrlEtcID" ie ON m."ImageUrlEtcID" = ie."ID"
                        LEFT JOIN "ImageTitleID" it ON m."ImageTitleID" = it."ID"
                        LEFT JOIN "WebSiteCategoryID" wc ON m."CategoryID" = wc."ID"
                        WHERE %s = ANY(m."FaceID")
                        ORDER BY m."DetectionDate" DESC NULLS LAST
                        LIMIT 1
                        """
                        pg_cursor.execute(sql_details, (pg_face_id,))
                        face_details_row = pg_cursor.fetchone()

                        if not face_details_row:
                            p_warn(
                                f"No ImageBasedMain details found for PostgreSQL FaceID {pg_face_id} (from MilvusID {milvus_id}). Skipping."
                            )
                            continue

                        image_info_dict = {
                            "image_id": face_details_row.get("image_id"),
                            "image_protocol": face_details_row.get("image_protocol"),
                            "image_domain": face_details_row.get("image_domain"),
                            "image_path": face_details_row.get("image_path"),
                            "image_etc": face_details_row.get("image_etc"),
                            "image_title": face_details_row.get("image_title"),
                            "source_protocol": face_details_row.get("source_protocol"),
                            "source_domain": face_details_row.get("source_domain"),
                            "source_path": face_details_row.get("source_path"),
                            "source_etc": face_details_row.get("source_etc"),
                        }

                        similar_faces_output.append(
                            {
                                "id": pg_face_id,  # PostgreSQL EyeOfWebFaceID.ID
                                "milvus_id": milvus_id,  # Milvus'un ID'si
                                "similarity": similarity_score,
                                "image_id": face_details_row.get(
                                    "image_id"
                                ),  # ImageID tablosunun ID'si
                                "domain": face_details_row.get("source_domain"),
                                "gender": milvus_gender,
                                "age": milvus_age,
                                "detection_score": milvus_det_score,
                                "risk_level": face_details_row.get("risk_level"),
                                "category": face_details_row.get("category"),
                                "detection_date": (
                                    face_details_row.get("detection_date").isoformat()
                                    if face_details_row.get("detection_date")
                                    else None
                                ),
                                "facebox": facebox_data,  # Milvus'tan gelen liste
                                "landmarks_2d": (
                                    landmarks_2d_np.tolist()
                                    if landmarks_2d_np is not None
                                    else None
                                ),  # (106,2) formatında liste
                                "image_info": image_info_dict,
                                "source_table": face_details_row.get(
                                    "source_table_name", "EyeOfWebFaceDataMilvus"
                                ),  # Kaynağı belirtmek için
                            }
                        )
                    else:
                        p_log(
                            f"Milvus Hit: MilvusID={milvus_id}, Similarity={similarity_score:.4f} - Below threshold {threshold}. Skipping."
                        )

            # Benzerliğe göre tekrar sırala (Milvus zaten distance'a göre sıralı getirir, bu adım teyit amaçlı)
            similar_faces_output.sort(key=lambda x: x["similarity"], reverse=True)
            p_log(
                f"findSimilarFacesWithImages finished. Returning {len(similar_faces_output)} processed faces."
            )
            return similar_faces_output

        except MilvusException as me:
            p_error(
                f"MilvusException in findSimilarFacesWithImages: {me}\n{traceback.format_exc()}"
            )
            return []
        except psycopg2.Error as pe:
            p_error(
                f"Post psycopg2.Error in findSimilarFacesWithImages: {pe}\n{traceback.format_exc()}"
            )
            if pg_conn:
                pg_conn.rollback()
            return []
        except Exception as e:
            p_error(
                f"Unexpected error in findSimilarFacesWithImages: {e}\n{traceback.format_exc()}"
            )
            if pg_conn:
                pg_conn.rollback()  # Emin olmak için
            return []
        finally:
            if pg_cursor:
                pg_cursor.close()
            if pg_conn:
                pg_conn.close()  # self.releaseConnection yerine doğrudan close

    def findSimilarFaces(
        self,
        face_embedding: np.ndarray,
        threshold=0.6,
        limit=100,
        algorithm="cosine",
        use_cuda=False,
    ):  # Added limit, algorithm/use_cuda are for API compatibility but Milvus handles internally
        """
        Milvus'ta benzer yüzleri arar, ardından PostgreSQL'den ImageBasedMain detaylarıyla zenginleştirir.
        Eski Python döngülü benzerlik hesaplamasının yerini alır.

        Args:
            face_embedding: Aranacak yüz gömme vektörü (numpy array).
            threshold: Benzerlik eşiği (0.0-1.0 arası). Milvus COSINE distance için 1-threshold kullanılır.
            limit: Milvus'tan istenecek maksimum sonuç sayısı (filtrelenmeden önce).
            algorithm: API uyumluluğu için korunur, Milvus'ta metrik tip koleksiyonla tanımlıdır.
            use_cuda: API uyumluluğu için korunur.

        Returns:
            list: Bulunan benzer yüzlerin listesi (Milvus öznitelikleri ve ImageBasedMain detayları ile).
        """
        p_log(
            f"Starting Milvus-based findSimilarFaces with threshold: {threshold}, Milvus search limit: {limit}"
        )
        similar_faces_output = []
        pg_conn = None
        pg_cursor = None
        detail_cursor = None  # For ImageBasedMain details

        try:
            # 1. Milvus Bağlantısı ve Koleksiyon Alma
            milvus_collection = get_milvus_collection(
                EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME
            )
            if not milvus_collection:
                p_error("Failed to get Milvus collection for findSimilarFaces.")
                return []

            # 2. Milvus'ta Benzerlik Araması
            search_vector = [
                np.array(face_embedding, dtype=np.float32).tolist()
            ]  # Ensure correct format for Milvus

            search_params = {
                "metric_type": "COSINE",
                "params": {
                    "ef": max(1200, limit * 1.2)
                },  # ef değeri limit'ten en az %20 büyük ve minimum 1200 olmalı
            }

            p_info(
                f"Searching Milvus collection '{EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME}' with limit {limit} and ef={search_params['params']['ef']}..."
            )
            milvus_results = milvus_collection.search(
                data=search_vector,
                anns_field="face_embedding_data",
                param=search_params,
                limit=limit,
                output_fields=["id", "face_gender", "face_age", "detection_score"],
                consistency_level="Strong",
            )
            p_log(
                f"Milvus search returned {len(milvus_results[0]) if milvus_results and milvus_results[0] else 0} raw hits."
            )

            if not milvus_results or not milvus_results[0]:
                p_log("No hits from Milvus.")
                return []

            # 3. PostgreSQL Bağlantısı
            pg_conn = self.connect()
            if not pg_conn:
                p_error(
                    "Database connection failed for enriching Milvus results in findSimilarFaces."
                )
                return []

            pg_cursor = pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            detail_cursor = pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # 4. Sonuçları İşle, Filtrele ve Zenginleştir
            processed_pg_face_ids = set()

            for hit in milvus_results[0]:
                milvus_id = hit.id
                similarity_score_from_milvus = (
                    hit.distance
                )  # Using Milvus COSINE distance as similarity score per user spec

                if similarity_score_from_milvus >= threshold:
                    p_log(
                        f"Milvus Hit: MilvusID={milvus_id}, Reported Distance (used as Similarity)={similarity_score_from_milvus:.4f} >= threshold {threshold}"
                    )
                    entity = hit.entity

                    pg_cursor.execute(
                        'SELECT "ID" FROM "EyeOfWebFaceID" WHERE "MilvusRefID" = %s',
                        (milvus_id,),
                    )
                    pg_face_record = pg_cursor.fetchone()

                    if not pg_face_record:
                        p_warn(
                            f"No corresponding PostgreSQL EyeOfWebFaceID found for MilvusID {milvus_id}. Skipping."
                        )
                        continue
                    pg_face_id = pg_face_record["ID"]

                    if pg_face_id in processed_pg_face_ids:
                        p_log(
                            f"PostgreSQL FaceID {pg_face_id} (from MilvusID {milvus_id}) already processed. Skipping."
                        )
                        continue
                    processed_pg_face_ids.add(pg_face_id)

                    STATIC_SQL_COMMAND_DETAILS = """
                        SELECT i."Protocol", bd."Domain" as base_domain, up."Path" as url_path,
                               i."ImageProtocol", img_bd."Domain" as image_domain, ip."Path" as image_path,
                               wc."Category", i."RiskLevel", i."DetectionDate"
                        FROM "ImageBasedMain" i
                        LEFT JOIN "BaseDomainID" bd ON i."BaseDomainID" = bd."ID"
                        LEFT JOIN "UrlPathID" up ON i."UrlPathID" = up."ID"
                        LEFT JOIN "BaseDomainID" img_bd ON i."ImageDomainID" = img_bd."ID"
                        LEFT JOIN "ImageUrlPathID" ip ON i."ImagePathID" = ip."ID"
                        LEFT JOIN "WebSiteCategoryID" wc ON i."CategoryID" = wc."ID"
                        WHERE %s = ANY(i."FaceID")
                        ORDER BY i."DetectionDate" DESC NULLS LAST
                        LIMIT 1
                        """
                    detail_cursor.execute(STATIC_SQL_COMMAND_DETAILS, (pg_face_id,))
                    face_details_row = detail_cursor.fetchone()

                    current_face_data = {
                        "id": pg_face_id,
                        "milvus_id": milvus_id,
                        "similarity": float(similarity_score_from_milvus),
                        "gender": entity.get("face_gender"),
                        "age": entity.get("face_age"),
                        "detection_score": (
                            float(entity.get("detection_score"))
                            if entity.get("detection_score") is not None
                            else None
                        ),
                        "domain": None,
                        "detection_date": None,
                        "risk_level": None,
                        "category": None,
                    }
                    if face_details_row:
                        current_face_data.update(
                            {
                                "domain": face_details_row["base_domain"],
                                "detection_date": (
                                    face_details_row["DetectionDate"].isoformat()
                                    if face_details_row["DetectionDate"]
                                    else None
                                ),
                                "risk_level": face_details_row["RiskLevel"],
                                "category": face_details_row["Category"],
                            }
                        )
                    else:
                        p_warn(
                            f"No ImageBasedMain details found for PostgreSQL FaceID {pg_face_id} (from MilvusID {milvus_id})."
                        )
                    similar_faces_output.append(current_face_data)
                else:
                    p_log(
                        f"Milvus Hit: MilvusID={milvus_id}, Reported Distance (used as Similarity)={similarity_score_from_milvus:.4f} < threshold {threshold}. Skipping."
                    )

            similar_faces_output.sort(key=lambda x: x["similarity"], reverse=True)
            p_log(
                f"findSimilarFaces (Milvus-based) finished. Returning {len(similar_faces_output)} faces."
            )
            return similar_faces_output

        except MilvusException as me:
            p_error(
                f"MilvusException in findSimilarFaces: {me}\n{traceback.format_exc()}"
            )
            return []
        except psycopg2.Error as pe:
            p_error(
                f"PostgreSQL error in findSimilarFaces: {pe}\n{traceback.format_exc()}"
            )
            if pg_conn:
                pg_conn.rollback()
            return []
        except Exception as e:
            p_error(
                f"Unexpected error in findSimilarFaces: {e}\n{traceback.format_exc()}"
            )
            if pg_conn:
                pg_conn.rollback()
            return []
        finally:
            if pg_cursor:
                pg_cursor.close()
            if detail_cursor:
                detail_cursor.close()
            if pg_conn:
                pg_conn.close()

    def get_milvus_face_attributes(self, collection_name: str, pg_face_id: int) -> dict:
        """
        PostgreSQL FaceID (EyeOfWebFaceID.ID) kullanarak Milvus'tan yüz özniteliklerini getirir.

        Args:
            collection_name: Milvus koleksiyon adı (örn. EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME)
            pg_face_id: PostgreSQL EyeOfWebFaceID tablosundaki ID

        Returns:
            dict: Milvus'tan gelen yüz öznitelikleri (embedding, facebox vb.) veya None
        """
        p_log(
            f"Retrieving Milvus attributes for PostgreSQL FaceID: {pg_face_id} from collection: {collection_name}"
        )
        pg_conn = None
        pg_cursor = None

        try:
            # 1. PostgreSQL'den MilvusRefID'yi al (önbellekten kontrol et)
            cache_key = f"{pg_face_id}"
            milvus_ref_id = self._milvus_ref_id_cache.get(cache_key)

            if milvus_ref_id is None:
                # Önbellekte yoksa PostgreSQL'den al
                pg_conn = self.connect()
                if not pg_conn:
                    p_error(
                        f"Database connection failed for get_milvus_face_attributes (FaceID: {pg_face_id})."
                    )
                    return None
                pg_cursor = pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

                sql_get_milvus_ref = (
                    'SELECT "MilvusRefID" FROM "EyeOfWebFaceID" WHERE "ID" = %s'
                )
                pg_cursor.execute(sql_get_milvus_ref, (pg_face_id,))
                milvus_ref_record = pg_cursor.fetchone()

                if not milvus_ref_record or milvus_ref_record["MilvusRefID"] is None:
                    p_warn(
                        f"No MilvusRefID found in EyeOfWebFaceID for PostgreSQL FaceID {pg_face_id}."
                    )
                    return None

                milvus_ref_id = milvus_ref_record["MilvusRefID"]
                # Önbelleğe ekle
                self._milvus_ref_id_cache[cache_key] = milvus_ref_id

            p_log(
                f"Found MilvusRefID: {milvus_ref_id} for PostgreSQL FaceID: {pg_face_id}. Querying Milvus."
            )

            # 2. Milvus'tan veri çek (önbellekten koleksiyon al)
            milvus_collection = self._get_cached_milvus_collection(collection_name)
            if not milvus_collection:
                p_error(
                    f"Failed to get Milvus collection '{collection_name}' for FaceID: {pg_face_id} (MilvusRefID: {milvus_ref_id})."
                )
                return None

            # 3. Vektör ve diğer verileri çek
            query_expr = f"id == {milvus_ref_id}"
            milvus_results = milvus_collection.query(
                expr=query_expr,
                output_fields=[
                    "face_embedding_data",
                    "face_box",
                    "landmarks_2d",
                    "face_gender",
                    "face_age",
                    "detection_score",
                    "detection_date_ts",
                ],
                limit=1,  # ID unique olmalı
            )

            if not milvus_results:
                p_warn(
                    f"No data found in Milvus (collection: {collection_name}) for MilvusRefID: {milvus_ref_id}"
                )
                return None

            # 4. Sonuçları formatla ve döndür
            milvus_entity = milvus_results[0]
            attributes = {
                "pg_face_id": pg_face_id,
                "milvus_id": milvus_ref_id,
                "face_embedding_data": milvus_entity.get("face_embedding_data"),
                "face_box": milvus_entity.get("face_box"),
                "landmarks_2d": milvus_entity.get("landmarks_2d"),
                "face_gender": milvus_entity.get("face_gender"),
                "face_age": milvus_entity.get("face_age"),
                "detection_score": milvus_entity.get("detection_score"),
                "detection_date_ts": milvus_entity.get("detection_date_ts"),
            }

            p_log(
                f"Successfully retrieved Milvus attributes for FaceID: {pg_face_id} (MilvusRefID: {milvus_ref_id})."
            )
            return attributes

        except MilvusException as me:
            p_error(
                f"MilvusException in get_milvus_face_attributes (FaceID: {pg_face_id}): {me}"
            )
            traceback.print_exc()
            return None
        except psycopg2.Error as pe:
            p_error(
                f"PostgreSQL error in get_milvus_face_attributes (FaceID: {pg_face_id}): {pe}"
            )
            traceback.print_exc()
            if pg_conn:
                pg_conn.rollback()
            return None
        except Exception as e:
            p_error(
                f"Unexpected error in get_milvus_face_attributes (FaceID: {pg_face_id}): {e}"
            )
            traceback.print_exc()
            return None
        finally:
            if pg_cursor:
                pg_cursor.close()
            if pg_conn:
                pg_conn.close()

    def find_similar_face_ids_in_milvus(
        self,
        collection_name: str,
        target_vector: list,
        distance_threshold: float,
        exclude_id: int = None,
        limit: int = 1000,
    ) -> list:
        """
        Milvus'ta verilen vektöre benzer yüzleri arar ve PostgreSQL FaceID'leri döndürür.

        Args:
            collection_name: Milvus koleksiyon adı (örn. EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME)
            target_vector: Hedef vektör (liste formatında)
            distance_threshold: Maksimum mesafe değeri (0.0-1.0 arası, COSINE için)
            exclude_id: Aramadan hariç tutulacak PostgreSQL FaceID
            limit: Maksimum sonuç sayısı

        Returns:
            list: Bulunan benzer yüzlerin PostgreSQL FaceID'lerinin listesi
        """
        p_log(
            f"Searching Milvus for similar faces with distance threshold: {distance_threshold}, limit: {limit}"
        )
        pg_conn = None
        pg_cursor = None
        similar_pg_face_ids = []

        try:
            # 1. Milvus'a bağlan (önbellekten koleksiyon al)
            milvus_collection = self._get_cached_milvus_collection(collection_name)
            if not milvus_collection:
                p_error(
                    f"Failed to get Milvus collection '{collection_name}' for similarity search."
                )
                return []

            # Exclude_id için Milvus ID'yi bul (varsa) - önbellekten kontrol et
            exclude_milvus_id = None
            if exclude_id is not None:
                cache_key = f"{exclude_id}"
                exclude_milvus_id = self._milvus_ref_id_cache.get(cache_key)

                if exclude_milvus_id is None:
                    # Önbellekte yoksa PostgreSQL'den al
                    pg_conn = self.connect()
                    if not pg_conn:
                        p_error(
                            f"Database connection failed for find_similar_face_ids_in_milvus."
                        )
                        return []
                    pg_cursor = pg_conn.cursor(
                        cursor_factory=psycopg2.extras.DictCursor
                    )

                    pg_cursor.execute(
                        'SELECT "MilvusRefID" FROM "EyeOfWebFaceID" WHERE "ID" = %s',
                        (exclude_id,),
                    )
                    exclude_record = pg_cursor.fetchone()
                    if exclude_record and exclude_record["MilvusRefID"]:
                        exclude_milvus_id = exclude_record["MilvusRefID"]
                        # Önbelleğe ekle
                        self._milvus_ref_id_cache[cache_key] = exclude_milvus_id

                if exclude_milvus_id:
                    p_log(
                        f"Will exclude MilvusID: {exclude_milvus_id} (PostgreSQL FaceID: {exclude_id}) from search results."
                    )

            # 2. Benzerlik araması yap
            search_params = {
                "metric_type": "COSINE",
                "params": {
                    "ef": max(1200, limit * 1.2)
                },  # ef değeri limit'ten en az %20 büyük ve minimum 1200 olmalı
            }

            # CRITICAL: Normalize vector for COSINE metric
            # COSINE similarity requires normalized vectors for accurate distance calculation
            target_vector_np = np.array(target_vector, dtype=np.float32)
            vector_norm = np.linalg.norm(target_vector_np)
            if vector_norm == 0:
                p_warn(
                    "Target vector has zero norm, cannot normalize. Skipping search."
                )
                return []
            target_vector_normalized = (target_vector_np / vector_norm).tolist()

            search_vector = [
                target_vector_normalized
            ]  # Milvus search_vector formatı: liste içinde liste
            p_log(
                f"Searching in Milvus collection '{collection_name}' with limit {limit} and ef={search_params['params']['ef']} (vector normalized)..."
            )

            milvus_results = milvus_collection.search(
                data=search_vector,
                anns_field="face_embedding_data",
                param=search_params,
                limit=limit,
                output_fields=["id"],
                consistency_level="Strong",
            )

            if not milvus_results or not milvus_results[0]:
                p_log("No hits from Milvus.")
                return []

            # 3. Sonuçları filtrele ve PostgreSQL IDs'ye dönüştür
            milvus_ids_to_convert = []
            accepted_count = 0
            rejected_count = 0

            p_log(f"\n=== MILVUS SIMILARITY FILTERING ===")
            p_log(
                f"Distance threshold: {distance_threshold} (similarity threshold: {1.0 - distance_threshold})"
            )
            p_log(f"Processing {len(milvus_results[0])} Milvus results...\n")

            for hit in milvus_results[0]:
                milvus_id = hit.id
                distance = hit.distance
                similarity = 1.0 - distance  # Convert COSINE distance to similarity

                # CRITICAL FIX: For COSINE metric, distance represents dissimilarity (0=identical, 1=different)
                # We want faces with LOW distance (HIGH similarity)
                # distance_threshold = 1 - similarity_threshold
                # So: distance <= distance_threshold means similarity >= similarity_threshold
                if distance <= distance_threshold:
                    # exclude_milvus_id varsa filtrele
                    if exclude_milvus_id is None or milvus_id != exclude_milvus_id:
                        milvus_ids_to_convert.append(milvus_id)
                        accepted_count += 1
                        p_log(
                            f"✓ ACCEPTED - MilvusID {milvus_id}: distance={distance:.4f}, similarity={similarity:.4f} (>= {1.0-distance_threshold:.4f})"
                        )
                    else:
                        p_log(
                            f"✗ EXCLUDED - MilvusID {milvus_id} matches exclude_id ({exclude_id})"
                        )
                else:
                    rejected_count += 1
                    p_log(
                        f"✗ REJECTED - MilvusID {milvus_id}: distance={distance:.4f}, similarity={similarity:.4f} (< {1.0-distance_threshold:.4f})"
                    )

            p_log(f"\n=== FILTERING RESULTS ===")
            p_log(f"Accepted: {accepted_count}, Rejected: {rejected_count}")
            p_log(f"Total faces passing threshold: {len(milvus_ids_to_convert)}\n")

            if not milvus_ids_to_convert:
                p_log("No Milvus IDs passed filtering criteria.")
                return []

            # 4. Milvus ID'leri PostgreSQL ID'lerine dönüştür
            if pg_conn is None or pg_cursor is None:
                pg_conn = self.connect()
                if not pg_conn:
                    p_error(
                        "Database connection failed for Milvus ID to PostgreSQL ID conversion."
                    )
                    return []
                pg_cursor = pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # IN operatörü için tuple oluştur
            placeholders = ",".join(["%s"] * len(milvus_ids_to_convert))
            query = f'SELECT "ID", "MilvusRefID" FROM "EyeOfWebFaceID" WHERE "MilvusRefID" IN ({placeholders})'

            pg_cursor.execute(query, tuple(milvus_ids_to_convert))
            pg_face_records = pg_cursor.fetchall()

            # Sonuçları çıkar ve aynı zamanda önbelleğe ekle
            for record in pg_face_records:
                pg_face_id = record["ID"]
                milvus_id = record["MilvusRefID"]

                # ID'leri önbelleğe ekle
                if milvus_id:
                    self._milvus_ref_id_cache[f"{pg_face_id}"] = milvus_id

                if exclude_id is None or pg_face_id != exclude_id:
                    similar_pg_face_ids.append(pg_face_id)

            p_log(f"Found {len(similar_pg_face_ids)} similar PostgreSQL FaceIDs.")
            return similar_pg_face_ids

        except MilvusException as me:
            p_error(f"MilvusException in find_similar_face_ids_in_milvus: {me}")
            traceback.print_exc()
            return []
        except psycopg2.Error as pe:
            p_error(f"PostgreSQL error in find_similar_face_ids_in_milvus: {pe}")
            traceback.print_exc()
            if pg_conn:
                pg_conn.rollback()
            return []
        except Exception as e:
            p_error(f"Unexpected error in find_similar_face_ids_in_milvus: {e}")
            traceback.print_exc()
            return []
        finally:
            if pg_cursor:
                pg_cursor.close()
            if pg_conn:
                pg_conn.close()

    def get_batch_milvus_face_attributes(
        self, collection_name: str, pg_face_ids: list
    ) -> dict:
        """
        Birden fazla PostgreSQL FaceID için Milvus özniteliklerini toplu şekilde getirir.

        Args:
            collection_name: Milvus koleksiyon adı
            pg_face_ids: PostgreSQL FaceID listesi

        Returns:
            dict: PG FaceID -> Milvus öznitelikleri sözlüğü
        """
        if not pg_face_ids:
            return {}

        p_info(f"Toplu Milvus öznitelikleri getiriliyor: {len(pg_face_ids)} yüz")

        pg_conn = None
        pg_cursor = None
        results = {}

        try:
            # 1. Önce MilvusRefID'leri toplu çek
            pg_conn = self.connect()
            if not pg_conn:
                p_error("Veritabanı bağlantısı başarısız oldu.")
                return {}

            pg_cursor = pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # Önbellekte olmayan FaceID'leri bul
            missing_ids = []
            for face_id in pg_face_ids:
                cache_key = f"{face_id}"
                if cache_key not in self._milvus_ref_id_cache:
                    missing_ids.append(face_id)

            # Eksik olanları PostgreSQL'den toplu al
            if missing_ids:
                p_log(
                    f"Önbellekte bulunmayan {len(missing_ids)} FaceID için MilvusRefID'leri alınıyor..."
                )
                placeholders = ",".join(["%s"] * len(missing_ids))
                query = f'SELECT "ID", "MilvusRefID" FROM "EyeOfWebFaceID" WHERE "ID" IN ({placeholders})'
                pg_cursor.execute(query, tuple(missing_ids))

                for row in pg_cursor.fetchall():
                    face_id = row["ID"]
                    milvus_ref_id = row["MilvusRefID"]
                    if milvus_ref_id:
                        self._milvus_ref_id_cache[f"{face_id}"] = milvus_ref_id

            # 2. Şimdi Milvus koleksiyonunu al
            milvus_collection = self._get_cached_milvus_collection(collection_name)
            if not milvus_collection:
                p_error(f"Milvus koleksiyonu alınamadı: {collection_name}")
                return {}

            # 3. Her FaceID için Milvus verilerini al (önbellekten MilvusRefID kullan)
            for face_id in pg_face_ids:
                cache_key = f"{face_id}"
                milvus_ref_id = self._milvus_ref_id_cache.get(cache_key)

                if not milvus_ref_id:
                    p_warn(f"FaceID {face_id} için MilvusRefID bulunamadı.")
                    continue

                # Milvus'tan sorgula
                query_expr = f"id == {milvus_ref_id}"
                milvus_results = milvus_collection.query(
                    expr=query_expr,
                    output_fields=[
                        "face_embedding_data",
                        "face_box",
                        "landmarks_2d",
                        "face_gender",
                        "face_age",
                        "detection_score",
                    ],
                    limit=1,
                )

                if milvus_results:
                    milvus_entity = milvus_results[0]
                    results[face_id] = {
                        "pg_face_id": face_id,
                        "milvus_id": milvus_ref_id,
                        "face_embedding_data": milvus_entity.get("face_embedding_data"),
                        "face_box": milvus_entity.get("face_box"),
                        "landmarks_2d": milvus_entity.get("landmarks_2d"),
                        "face_gender": milvus_entity.get("face_gender"),
                        "face_age": milvus_entity.get("face_age"),
                        "detection_score": milvus_entity.get("detection_score"),
                    }
                else:
                    p_warn(
                        f"FaceID {face_id} (MilvusRefID {milvus_ref_id}) için Milvus'ta veri bulunamadı."
                    )

            p_info(
                f"Toplu Milvus verileri başarıyla alındı: {len(results)}/{len(pg_face_ids)} yüz"
            )
            return results

        except Exception as e:
            p_error(f"Toplu Milvus verileri alınırken hata: {e}")
            traceback.print_exc()
            return results
        finally:
            if pg_cursor:
                pg_cursor.close()
            if pg_conn:
                pg_conn.close()
