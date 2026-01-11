#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
    g,
    jsonify,
    send_file,
)
from app.controllers.search_controller import SearchController
from app.routes.auth import is_logged_in
from functools import wraps
from app import limiter
import io
from PIL import Image, UnidentifiedImageError
import numpy as np
import traceback
import cv2
import base64
import html
from flask import current_app
import datetime
import psycopg2
import psycopg2.extras
from lib.url_image_download import downloadImage_defaultSafe
from lib.draw_utils import landmarks_rectangle
from collections import Counter, defaultdict
import itertools  # Kombinasyonlar için
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import pairwise_distances
from scipy import spatial
import json
from lib.pdf_generator import generate_pdf_report  # PDF oluşturucu import edildi
import math  # Import math for ceiling function
from lib.database_tools import DatabaseTools  # DatabaseTools'u import edelim

# from lib.database_tools import DEFAULT_THRESHOLDS # <<< YENİ: Eşik değerlerini import et <<< KALDIRILDI
from lib.compress_tools import decompress_image
import ast
from pymilvus import (
    Collection,
)  # Added for type hinting if g.db_tools uses it, but direct use is avoided

# YENİ EKLENEN IMPORTLAR
from werkzeug.utils import secure_filename
from flask import make_response
import os

EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME = (
    "EyeOfWebFaceDataMilvus"  # Defined in MILVUS_SCHEMA_GENERATOR.py
)

web_bp = Blueprint("web", __name__)

# --- Güvenlik ve Yardımcı Fonksiyonlar ---

# YENİ: Resim doğrulama ve temizleme fonksiyonu
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_IMAGE_SIZE_MB = 5  # Maksimum resim boyutu (MB)
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024


def allowed_file(filename):
    """Dosya uzantısının izin verilenler arasında olup olmadığını kontrol eder."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_and_sanitize_image(file_storage):
    """
    Yüklenen bir resmi doğrular, temizler ve güvenli hale getirir.
    Başarılı olursa (PIL Image nesnesi, güvenli dosya adı), aksi takdirde (None, hata mesajı) döner.
    """
    if not file_storage:
        return None, "Dosya sağlanmadı."

    filename = secure_filename(file_storage.filename)
    if filename == "":
        return None, "Dosya adı geçersiz veya boş."

    if not allowed_file(filename):
        return (
            None,
            f"İzin verilmeyen dosya türü. İzin verilenler: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Dosya boyutu kontrolü
    # file_storage.stream.seek(0, os.SEEK_END) # Bu satır dosyayı tüketebilir, dikkatli kullanılmalı
    # file_size = file_storage.stream.tell()
    # file_storage.stream.seek(0) # Stream'i başa sar
    # current_app.logger.debug(f"Dosya boyutu kontrol ediliyor: {file_size} bytes")
    # if file_size > MAX_IMAGE_SIZE_BYTES:
    #     return None, f"Dosya boyutu çok büyük. Maksimum boyut: {MAX_IMAGE_SIZE_MB} MB."
    # Not: Flask'ta request.content_length ile gelen dosya boyutu kontrol edilebilir veya
    # config'den MAX_CONTENT_LENGTH ayarı kullanılabilir. Şimdilik bu kontrolü basitleştiriyoruz.
    # Güvenlik için bu kontrolün etkinleştirilmesi önemlidir.

    try:
        # Dosyayı PIL Image olarak aç (bu aynı zamanda temel bir doğrulama yapar)
        img = Image.open(file_storage.stream)
        img.verify()  # Pillow'un kendi doğrulama mekanizması (bazı hataları yakalar)

        # Stream'i başa sarıp tekrar açmamız gerekebilir verify sonrası
        file_storage.stream.seek(0)
        img = Image.open(file_storage.stream)

        # MIME türü ve "magic numbers" kontrolü (basit)
        # Gerçek bir "magic numbers" kütüphanesi daha güvenilir olurdu.
        # Pillow formatı algılayamazsa img.format None olur.
        if img.format is None or img.format.lower() not in ALLOWED_EXTENSIONS:
            return None, "Dosya formatı doğrulanamadı veya desteklenmiyor."

        # Resmi yeniden işleyerek (re-saving) potansiyel zararlı kodları temizle
        # Orijinal formatı korumaya çalışalım
        output_format = (
            img.format if img.format in ["JPEG", "PNG", "GIF", "WEBP"] else "PNG"
        )

        # RGB'ye dönüştürme (şeffaflık varsa RGBA yerine)
        if img.mode == "P":  # Paletli ise
            img = img.convert("RGBA" if "transparency" in img.info else "RGB")
        elif img.mode == "RGBA" and output_format != "PNG" and output_format != "WEBP":
            # PNG/WEBP olmayan formatlarda alpha kanalı sorun çıkarabilir, RGB'ye çevir.
            img = img.convert("RGB")
        elif (
            img.mode != "RGB" and img.mode != "L" and img.mode != "RGBA"
        ):  # L = grayscale
            # Diğer modları RGB'ye dönüştür (veya RGBA, eğer destekliyorsa)
            img = img.convert("RGB")

        # In-memory buffer'a kaydet
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format=output_format)
        img_byte_arr.seek(0)

        # Temizlenmiş resmi tekrar PIL Image olarak aç
        sanitized_img = Image.open(img_byte_arr)

        return sanitized_img, filename
    except UnidentifiedImageError:
        current_app.logger.warning(f"Pillow dosyayı tanıyamadı: {filename}")
        return None, "Dosya geçerli bir resim olarak tanınamadı."
    except IOError as e:  # Dosya okuma/yazma hatası veya bozuk dosya
        current_app.logger.error(f"Resim işlenirken G/Ç hatası ({filename}): {e}")
        return None, "Resim dosyası bozuk veya okunamıyor."
    except Exception as e:
        current_app.logger.error(
            f"Resim işleme sırasında beklenmedik hata ({filename}): {e}\n{traceback.format_exc()}"
        )
        return None, "Resim işlenirken beklenmedik bir hata oluştu."


# --- Helper Function ---
def build_image_url(protocol, domain, path, etc):
    """Helper to construct full image URL from components."""
    if not domain or not path:  # Domain veya path yoksa URL oluşturulamaz
        return None
    protocol = protocol or "http"  # Varsayılan protokol
    url = f"{protocol}://{domain}/{path.lstrip('/')}"
    if etc:
        url += f"?{etc}"
    print(f"DEBUG [build_image_url] URL: {url}")
    return url


# Oturum kontrolü için dekoratör
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            flash("Bu sayfaya erişmek için lütfen giriş yapın", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated_function


# Tüm şablonlara JWT token ekleyen fonksiyon
@web_bp.context_processor
def inject_jwt_token():
    """
    Kullanıcı oturumu varsa tüm şablonlara JWT token değişkenini ekler.
    Bu, API isteklerinde kimlik doğrulama için kullanılacak.
    Ayrıca JWT'yi HTTPOnly cookie olarak ayarlar.
    """
    jwt_token_for_template = None
    if "logged_in" in session and session["logged_in"]:
        from flask_jwt_extended import create_access_token

        # Template'e gönderilecek token (JS kullanımı için)
        jwt_token_for_template = create_access_token(identity=session["user_id"])

        # HTTPOnly cookie için token'ı g objesinde sakla, after_request'te kullanılacak
        g.jwt_token_for_cookie = jwt_token_for_template

    return {"jwt_token": jwt_token_for_template}


@web_bp.after_request
def set_jwt_cookie(response):
    """
    Her istekten sonra, eğer g.jwt_token_for_cookie ayarlanmışsa,
    JWT'yi HTTPOnly, Secure (HTTPS ise) ve SameSite=Lax cookie olarak ayarlar.
    """
    if hasattr(g, "jwt_token_for_cookie") and g.jwt_token_for_cookie:
        token = g.jwt_token_for_cookie
        # Cookie'yi ayarla
        # Not: `expires` parametresi ile token'ın süresini ayarlayabilirsiniz.
        # flask_jwt_extended'in token süreleriyle senkronize olmalı.
        # Örnek: expires_delta = current_app.config.get("JWT_ACCESS_TOKEN_EXPIRES")
        # response.set_cookie(...)

        # response'u make_response ile oluşturduğumuzdan emin olalım
        # Ancak, genellikle Flask response objesi zaten set_cookie metoduna sahiptir.
        # Eğer response zaten bir Response objesi değilse (örn. string), bu hataya yol açar.
        # Flask'ın response objeleri genelde `werkzeug.wrappers.Response` tipindedir.
        try:
            # JWT_COOKIE_SECURE yapılandırmasını kontrol et, HTTPS ise True olmalı
            secure_cookie = current_app.config.get("JWT_COOKIE_SECURE", False)
            # JWT_COOKIE_SAMESITE yapılandırmasını kontrol et
            samesite_cookie = current_app.config.get("JWT_COOKIE_SAMESITE", "Lax")

            response.set_cookie(
                key=current_app.config.get(
                    "JWT_ACCESS_COOKIE_NAME", "access_token_cookie"
                ),
                value=token,
                httponly=True,
                secure=secure_cookie,  # Sadece HTTPS üzerinden gönder
                samesite=samesite_cookie,  # CSRF koruması için
                # path=current_app.config.get('JWT_COOKIE_PATH', '/') # Genellikle kök dizin
                # domain=current_app.config.get('JWT_COOKIE_DOMAIN', None) # Belirli bir domain için
            )
            # g objesinden token'ı temizle
            delattr(g, "jwt_token_for_cookie")
            current_app.logger.debug("JWT cookie başarıyla ayarlandı.")
        except Exception as e:
            # Bu hata, response'un beklenmedik bir tipte olması durumunda (örn. string) oluşabilir.
            # Tüm view fonksiyonlarının Response objesi döndürdüğünden emin olun.
            current_app.logger.error(
                f"JWT cookie ayarlanamadı: {e}. Response tipi: {type(response)}"
            )
            # Hata durumunda response'u değiştirmeden döndür
            pass  # Hata durumunda response'ı değiştirmeden devam et

    return response


@web_bp.route("/")
@login_required
def index():
    """Ana sayfa"""
    return render_template("index.html")


PER_PAGE = 50  # Define results per page constant


@web_bp.route("/search", methods=["GET", "POST"])
@login_required
@limiter.limit("30/minute")
def search():
    """Metin bazlı yüz arama sayfası (form ve sonuçlar)."""

    search_params = {
        "domain": request.args.get("domain", default="", type=str),
        "start_date": request.args.get("start_date", default="", type=str),
        "end_date": request.args.get("end_date", default="", type=str),
        "risk_level": request.args.get("risk_level", default="", type=str),
        "category": request.args.get("category", default="", type=str),
    }
    search_performed = any(
        search_params.values()
    )  # Check if any search param is present in GET
    page = request.args.get("page", 1, type=int)

    if request.method == "POST":
        # Extract params from form and redirect to GET with params
        form_params = {
            "domain": request.form.get("domain", ""),
            "start_date": request.form.get("start_date", ""),
            "end_date": request.form.get("end_date", ""),
            "risk_level": request.form.get("risk_level", ""),
            "category": request.form.get("category", ""),
        }
        # Simple validation: ensure at least one param is filled
        if not any(form_params.values()):
            flash("En az bir arama kriteri belirtmelisiniz", "warning")
            # Redirect back to GET version of search page (empty)
            return redirect(url_for("web.search"))

        # Redirect to the GET version of the search route with parameters
        # This makes the URL bookmarkable and pagination easier
        return redirect(url_for("web.search", **form_params))

    # --- Handle GET request (display form AND results if params exist) ---
    results = []
    total = 0
    total_pages = 0

    # ---> ADD LOGGING HERE <---
    print(f"[ROUTE /search GET] Params: {search_params}, Page: {page}")

    if search_performed:
        # Perform search only if parameters are provided via GET
        try:
            success, message, results, total = SearchController.search_faces(
                search_params, page=page, per_page=PER_PAGE
            )

            # ---> ADD LOGGING HERE <---
            print(
                f"[ROUTE /search GET] Controller Result: success={success}, msg='{message}', len(results)={len(results)}, total={total}"
            )

            if not success:
                flash(f"Arama sırasında hata oluştu: {message}", "danger")
                # Fall through to render the template with empty results,
                # but keep search params displayed in the form
            elif total == 0:
                flash("Bu kriterlere uygun sonuç bulunamadı.", "info")
            else:
                # Calculate total pages
                total_pages = math.ceil(total / PER_PAGE)

        except Exception as e:
            error_details = traceback.format_exc()
            print(f"Arama hatası: {error_details}")
            flash(f"Arama işlenirken beklenmedik bir hata oluştu: {str(e)}", "danger")
            # Fall through to render template with empty results

    # Always fetch form data (domains, risks, categories) for GET request
    try:
        _, _, domains = SearchController.get_domains()
        _, _, risk_levels = SearchController.get_risk_levels()
        _, _, categories = SearchController.get_categories()
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Form verisi yükleme hatası: {error_details}")
        flash(f"Form bilgileri yüklenirken hata oluştu: {str(e)}", "danger")
        domains, risk_levels, categories = [], [], []  # Ensure lists exist

    # Render the correct template based on whether a search was performed
    if search_performed:
        # Render results page
        return render_template(
            "search_results.html",
            results=results,
            params=search_params,  # Current search parameters
            search_performed=search_performed,
            # Form data (might still be useful for display)
            domains=domains,
            risk_levels=risk_levels,
            categories=categories,
            # Pagination data
            page=page,
            per_page=PER_PAGE,
            total=total,
            total_pages=total_pages,
        )
    else:
        # Render search form page
        return render_template(
            "search.html",
            # Pass form data for dropdowns
            domains=domains,
            risk_levels=risk_levels,
            categories=categories,
            # Pass current (empty) params so form fields can reflect them if needed
            params=search_params,
            search_performed=search_performed,
        )


@web_bp.route("/search/image", methods=["GET", "POST"])
@login_required
@limiter.limit("10/minute")
def search_by_image():
    """Görsel yükleyerek arama sayfası"""
    if request.method == "POST":
        # Dosya kontrolü (Flask tarafından zaten yapılıyor ama yine de kontrol edelim)
        if "image" not in request.files:
            flash("Lütfen bir görsel dosyası seçin", "warning")
            return redirect(request.url)

        file = request.files["image"]

        # YENİ: Resim doğrulama ve temizleme
        sanitized_img, secure_name = validate_and_sanitize_image(file)

        if sanitized_img is None:  # Hata oluştu
            flash(secure_name, "danger")  # secure_name burada hata mesajını içerir
            return redirect(request.url)

        # Eşik değeri parametresi (isteğe bağlı)
        threshold = float(request.form.get("threshold", 0.6))
        # YENİ: Benzerlik algoritması parametresi
        algorithm = request.form.get("similarity_algorithm", "cosine")

        # YENİ: CUDA kullanılıp kullanılmayacağını config'den al
        use_cuda_backend = current_app.config.get("USE_CUDA", False)
        print(
            f"[ROUTE /search/image POST] Algorithm: {algorithm}, Use CUDA: {use_cuda_backend}"
        )

        # Görsel dosyasını işle
        try:
            # Dosyayı PIL Image olarak aç (ZATEN sanitized_img OLARAK ALINDI)
            # img = Image.open(io.BytesIO(file.read())) # ESKİ KOD
            img = sanitized_img  # YENİ KOD: Temizlenmiş PIL Image'ı kullan

            # NumPy dizisine dönüştür (RGB)
            img_array = np.array(
                img.convert("RGB")
            )  # RGB'ye dönüştürme zaten validate_and_sanitize_image içinde yapılıyor olabilir, ama burada tekrar etmek sorun olmaz.

            # Arama işlemini gerçekleştir (algorithm ve use_cuda parametrelerini ilet)
            success, message, search_results_raw = SearchController.search_by_image(
                img_array,
                threshold=threshold,
                algorithm=algorithm,  # İletilen algoritma
                use_cuda=use_cuda_backend,  # İletilen CUDA bilgisi
            )

            if not success:
                flash(f"Arama sırasında hata oluştu: {message}", "danger")
                return redirect(request.url)

            # ---> MODIFICATION: Process results to include image URL or Base64 data <---
            processed_results = []
            if search_results_raw:
                conn = g.db_tools.connect()
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

                # Query to fetch image details for a given face ID
                # We need ImageID and URL components
                details_query = """
                    SELECT DISTINCT ON (f."ID")
                        f."ID" as face_id, 
                        m."ImageID",
                        m."ImageProtocol",
                        bdi."Domain" as image_domain,
                        pi."Path" as image_path,
                        ei."Etc" as image_etc,
                        img."BinaryImage" as binary_image -- Fetch binary data directly
                    FROM "EyeOfWebFaceID" f
                    JOIN "ImageBasedMain" m ON f."ID" = ANY(m."FaceID")
                    LEFT JOIN "BaseDomainID" bdi ON m."ImageDomainID" = bdi."ID"
                    LEFT JOIN "ImageUrlPathID" pi ON m."ImagePathID" = pi."ID"
                    LEFT JOIN "ImageUrlEtcID" ei ON m."ImageUrlEtcID" = ei."ID"
                    LEFT JOIN "ImageID" img ON m."ImageID" = img."ID" -- Join ImageID table
                    WHERE f."ID" = %s
                    ORDER BY f."ID", m."DetectionDate" DESC -- Get the most recent image for the face
                    LIMIT 1
                """

                for result_item in search_results_raw:
                    face_id = result_item.get("id")
                    if not face_id:
                        current_app.logger.warning(
                            f"Skipping result with missing face ID: {result_item}"
                        )
                        continue

                    image_url = None
                    image_base64 = None
                    image_mime_type = None

                    try:
                        cursor.execute(details_query, (face_id,))
                        db_image_details = cursor.fetchone()

                        if db_image_details:
                            binary_image_data = db_image_details.get("binary_image")
                            image_url = None  # Reset image_url before processing
                            image_base64 = None  # Reset image_base64
                            image_mime_type = None  # Reset mime_type

                            if binary_image_data:
                                try:
                                    decompressed_bytes = decompress_image(
                                        binary_image_data
                                    )
                                    if decompressed_bytes:
                                        image_base64 = base64.b64encode(
                                            decompressed_bytes
                                        ).decode("utf-8")
                                        # Basic MIME type detection
                                        if decompressed_bytes.startswith(
                                            b"\x89PNG\r\n\x1a\n"
                                        ):
                                            image_mime_type = "image/png"
                                        elif decompressed_bytes.startswith(
                                            b"\xff\xd8\xff"
                                        ):
                                            image_mime_type = "image/jpeg"
                                        elif (
                                            decompressed_bytes.startswith(b"RIFF")
                                            and decompressed_bytes[8:12] == b"WEBP"
                                        ):
                                            image_mime_type = "image/webp"
                                        else:
                                            image_mime_type = "application/octet-stream"  # Fallback MIME type
                                        current_app.logger.debug(
                                            f"Successfully generated Base64 for face {face_id} after decompression. MIME: {image_mime_type}"
                                        )
                                    else:
                                        current_app.logger.warning(
                                            f"Decompression failed or returned empty for face {face_id}"
                                        )
                                except Exception as decomp_encode_err:
                                    current_app.logger.error(
                                        f"Error decompressing/encoding DB image for face {face_id}: {decomp_encode_err}"
                                    )
                                    image_base64 = None  # Ensure it's None on error

                            if image_base64 is None:
                                image_url = build_image_url(
                                    db_image_details.get(
                                        "ImageProtocol"
                                    ),  # Use get with default
                                    db_image_details.get("image_domain"),
                                    db_image_details.get("image_path"),
                                    db_image_details.get("image_etc"),
                                )
                                if image_url:
                                    current_app.logger.debug(
                                        f"Using URL for face {face_id} as Base64 is unavailable or failed."
                                    )
                                else:
                                    current_app.logger.warning(
                                        f"Could not generate Base64 or build URL for face {face_id}"
                                    )
                        else:
                            current_app.logger.warning(
                                f"Could not find image details in DB for face ID: {face_id}"
                            )

                    except Exception as detail_err:
                        current_app.logger.error(
                            f"Error fetching details for face ID {face_id}: {detail_err}"
                        )

                    # Add processed data to the result item
                    result_item["image_url"] = image_url
                    result_item["image_base64"] = image_base64
                    result_item["image_mime_type"] = image_mime_type
                    processed_results.append(result_item)

                # Release DB connection
                g.db_tools.releaseConnection(conn, cursor)
            else:
                # Handle case with no results
                processed_results = []

            # Sonuçları session'da saklayalım (PDF indirme için - raw results are enough)
            # Storing raw results might be better for PDF generation consistency
            session["last_image_search_results"] = search_results_raw
            session["last_image_search_threshold"] = threshold
            session["last_image_search_filename"] = secure_name

            return render_template(
                "image_search_results.html",
                results=processed_results,  # Pass processed results to template
                threshold=threshold,
                image_name=secure_name,
            )
        except Exception as e:
            # Ensure connection is closed on general error too
            if "conn" in locals() and conn:
                g.db_tools.releaseConnection(
                    conn, cursor if "cursor" in locals() else None
                )
            flash(
                f"Görsel işlenirken veya sonuçlar hazırlanırken hata oluştu: {str(e)}",
                "danger",
            )
            current_app.logger.error(
                f"Error in search_by_image POST: {traceback.format_exc()}"
            )
            return redirect(request.url)

    # GET isteği - Form sayfasını göster
    # YENİ: CUDA durumunu template'e gönder
    use_cuda_backend = current_app.config.get("USE_CUDA", False)
    return render_template("image_search.html", use_cuda=use_cuda_backend)


# Yeni Rota: Görsel Arama Sonuçları için PDF İndirme
@web_bp.route("/download/image_search_report", methods=["GET"])
@login_required
def download_image_search_report():
    """Son görsel arama sonuçları için PDF raporu oluşturur ve indirir."""

    # Session'dan son arama sonuçlarını al
    search_results = session.get("last_image_search_results")
    threshold = session.get("last_image_search_threshold", 0.6)
    image_name = session.get("last_image_search_filename", "Yüklenen Görsel")

    if not search_results:
        flash(
            "İndirilecek rapor verisi bulunamadı veya oturum süresi doldu.", "warning"
        )
        return redirect(url_for("web.index"))

    # Kullanıcı adını al (session'dan veya g objesinden)
    username = session.get("username", "Bilinmeyen Kullanıcı")
    if hasattr(g, "user") and g.user and "username" in g.user:
        username = g.user["username"]
    elif "username" in session:
        username = session["username"]

    search_type = f"Görsel Arama (Eşik: {threshold}, Dosya: {image_name})"

    # --- PDF Verisi Hazırlama ---
    pdf_data = []
    conn = None
    cursor = None
    try:
        conn = g.db_tools.connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # --- Güncellenmiş SQL Sorgusu ---
        # ImageID'den binary veriyi almak için LEFT JOIN ve SELECT eklendi
        # Yüz öznitelikleri (gender, age, score, facebox) Milvus'tan alınacağı için sorgudan çıkarıldı.
        sql_query = """ 
            SELECT 
                f."ID" as face_id, 
                -- f."FaceGender" as gender,  -- Milvus'tan alınacak
                -- f."FaceAge" as age,        -- Milvus'tan alınacak
                -- f."DetectionScore" as score, -- Milvus'tan alınacak
                -- f."FaceBox" as facebox,    -- Milvus'tan alınacak
                bds."Domain" as source_domain, 
                pds."Path" as source_path, 
                eds."Etc" as source_etc,
                m."Protocol" as source_protocol,
                -- Resim URL için bileşenler
                bdi."Domain" as image_domain,
                pi."Path" as image_path,
                ei."Etc" as image_etc,
                m."ImageProtocol" as image_protocol,
                -- Diğer bilgiler
                ti."Title" as image_title,
                h."ImageHash" as image_hash,
                m."RiskLevel" as risk_level, -- Risk seviyesini de alalım
                img."BinaryImage" as binary_image -- Binary Image Data eklendi
            FROM "EyeOfWebFaceID" f
            -- ImageBasedMain'e bağlan (FaceID array'i içerir)
            JOIN "ImageBasedMain" m ON f."ID" = ANY(m."FaceID")
            -- Kaynak URL bileşenleri için JOIN'ler
            LEFT JOIN "BaseDomainID" bds ON m."BaseDomainID" = bds."ID"
            LEFT JOIN "UrlPathID" pds ON m."UrlPathID" = pds."ID"
            LEFT JOIN "UrlEtcID" eds ON m."UrlEtcID" = eds."ID"
            -- Resim URL bileşenleri için JOIN'ler
            LEFT JOIN "BaseDomainID" bdi ON m."ImageDomainID" = bdi."ID"
            LEFT JOIN "ImageUrlPathID" pi ON m."ImagePathID" = pi."ID"
            LEFT JOIN "ImageUrlEtcID" ei ON m."ImageUrlEtcID" = ei."ID"
            -- Diğer ID tabloları için JOIN'ler
            LEFT JOIN "ImageTitleID" ti ON m."ImageTitleID" = ti."ID"
            LEFT JOIN "ImageHashID" h ON m."HashID" = h."ID"
            LEFT JOIN "ImageID" img ON m."ImageID" = img."ID" -- ImageID tablosuna JOIN eklendi
            WHERE f."ID" = %s
            ORDER BY m."DetectionDate" DESC -- En yeni kaydı alabiliriz, emin olmak için
            LIMIT 1 
        """

        for result in search_results:
            res_face_id = result.get("id", None)
            if not res_face_id:
                print(f"Uyarı: Sonuç listesinde geçersiz face_id: {result}")
                continue

            # --- Veritabanından Ek Bilgileri Al (PostgreSQL - URL'ler, hash, risk vb.) ---
            cursor.execute(sql_query, (res_face_id,))  # sql_query güncellendi
            db_pg_data = cursor.fetchone()  # PostgreSQL'den gelen veri

            if not db_pg_data:
                print(
                    f"Uyarı: Veritabanında face_id veya ilişkili kayıt bulunamadı: {res_face_id}"
                )
                continue  # Bu sonucu atla

            # --- Milvus'tan Yüz Özniteliklerini Al ---
            milvus_attributes = None
            try:
                milvus_attributes = g.db_tools.get_milvus_face_attributes(
                    EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME, res_face_id
                )
                if not milvus_attributes:
                    current_app.logger.warning(
                        f"Milvus'tan {res_face_id} için öznitelik alınamadı."
                    )
            except Exception as e:
                current_app.logger.error(
                    f"Milvus'tan {res_face_id} için öznitelik alınırken hata: {e}"
                )

            # --- PDF Öğesini Oluştur ---
            title = f"Yüz ID: {res_face_id}"

            # Cinsiyet formatını düzelt (Milvus'tan)
            gender_bool = (
                milvus_attributes.get("face_gender") if milvus_attributes else None
            )
            gender_str = (
                "Erkek"
                if gender_bool is True
                else ("Kadın" if gender_bool is False else "N/A")
            )

            # Yaş, Skor, Facebox (Milvus'tan)
            age_from_milvus = (
                milvus_attributes.get("face_age") if milvus_attributes else None
            )
            score_from_milvus = (
                milvus_attributes.get("detection_score") if milvus_attributes else None
            )
            facebox_from_milvus = (
                milvus_attributes.get("face_box") if milvus_attributes else None
            )

            # Resim verisini veya URL'yi hazırla (PostgreSQL'den)
            image_data_b64 = None
            image_url = None
            binary_image_data = db_pg_data.get("binary_image")

            if binary_image_data:
                try:
                    decompressed_image_bytes = decompress_image(binary_image_data)
                    if decompressed_image_bytes:
                        image_data_b64 = base64.b64encode(
                            decompressed_image_bytes
                        ).decode("utf-8")
                    else:
                        current_app.logger.warning(
                            f"PDF Raporu (image_search): {res_face_id} için dekompresyon başarısız veya boş veri."
                        )
                except Exception as e:
                    current_app.logger.error(
                        f"PDF Raporu (image_search): {res_face_id} için dekompresyon/encode hatası: {e}"
                    )
            # Görsel Base64 olarak hazırlanamazsa, image_data_b64 None kalacak ve PDF'te görsel olmayacak.
            # URL fallback YOK.

            source_url = build_image_url(
                db_pg_data.get("source_protocol"),
                db_pg_data.get("source_domain"),
                db_pg_data.get("source_path"),
                db_pg_data.get("source_etc"),
            )

            pdf_item = {
                "title": title,
                "image_data_b64": image_data_b64,
                "image_url": image_url,  # Bu her zaman None olacak (yukarıdaki mantığa göre)
                "source_url": source_url,
                "hash": db_pg_data.get("image_hash", "N/A"),
                "count": result.get("count", 1),
                "score": score_from_milvus,
                "gender": gender_str,
                "age": age_from_milvus,
                "similarity": {
                    "name": f"Yüklenen Görsel ({image_name})",
                    "rate": result.get("similarity", 0),
                },
                "comprehensive_info": None,
                "facebox": facebox_from_milvus,
            }
            pdf_data.append(pdf_item)

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"PDF verisi hazırlanırken veritabanı hatası: {error}")
        print(traceback.format_exc())
        flash("Rapor verileri hazırlanırken bir veritabanı hatası oluştu.", "danger")
        # Hata durumunda bile bağlantıyı kapat
        if conn:
            g.db_tools.releaseConnection(conn, cursor)
        return redirect(url_for("web.search_by_image"))
    finally:
        # Bağlantıyı kapat
        if conn:
            g.db_tools.releaseConnection(conn, cursor)

    # --- PDF Raporunu Oluştur ve Gönder ---
    if not pdf_data:
        flash("Rapor için işlenecek geçerli veri bulunamadı.", "warning")
        return redirect(url_for("web.search_by_image"))

    pdf_bytes = generate_pdf_report(search_type, username, pdf_data)

    if pdf_bytes is None:
        flash("PDF raporu oluşturulurken bir hata oluştu.", "danger")
        return redirect(url_for("web.search_by_image"))

    # PDF dosyasını kullanıcıya gönder
    report_filename = (
        f"EyeOfWeb_GorselArama_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=report_filename,
    )


@web_bp.route("/face/<face_id>")
@login_required
def face_details(face_id):
    """Yüz detay sayfası"""
    # Yüz detaylarını al
    success, message, face_details = SearchController.get_face_details(face_id)

    if not success:
        flash(f"Yüz bilgileri alınamadı: {message}", "danger")
        return redirect(url_for("web.index"))

    # Facebox bilgisi zaten face_details içerisinde, facebox anahtarı ile erişilebilir
    # Ayrıca işleme gerek yok

    return render_template("face_details.html", face=face_details)


@web_bp.route("/search/similar/<face_id>", methods=["GET"])
@login_required
@limiter.limit("20/minute")
def search_similar(face_id):
    """Belirli bir yüze benzer yüzleri bulur"""
    # YENİ: Algoritma ve eşik değerini request args'dan al
    algorithm = request.args.get("algorithm", "cosine")
    try:
        # <<< DEĞİŞİKLİK: Varsayılan eşik 0.45 oldu >>>
        threshold = float(request.args.get("threshold", 0.45))
    except ValueError:
        flash("Geçersiz eşik değeri.", "danger")
        threshold = 0.45  # Fallback
    # YENİ: CUDA kullanımını config'den al
    use_cuda_backend = current_app.config.get("USE_CUDA", False)
    print(
        f"[ROUTE /search/similar GET] FaceID: {face_id}, Algorithm: {algorithm}, Threshold: {threshold}, Use CUDA: {use_cuda_backend}"
    )

    try:
        # Hedef yüz embedding'ini al
        target_face_id = int(face_id)

        # <<< YENİ: Embedding'i yeni metod ile al >>>
        target_embedding = g.db_tools.get_embedding_by_id(target_face_id)

        if target_embedding is None:
            flash(
                f"Hedef yüz (ID: {target_face_id}) için embedding verisi bulunamadı veya alınamadı.",
                "danger",
            )
            return redirect(url_for("web.index"))

        # <<< DEĞİŞİKLİK: Tekrar g.db_tools.findSimilarFacesWithImages kullan >>>
        similar_faces = g.db_tools.findSimilarFacesWithImages(
            face_embedding=target_embedding,  # <<< Doğru anahtar kelime: face_embedding
            algorithm=algorithm,
            use_cuda=use_cuda_backend,
        )

        # Sonuçları işle ve şablonu render et
        if similar_faces is None:
            flash("Benzer yüzler aranırken bir veritabanı hatası oluştu.", "danger")
            similar_faces = []  # Render için boş liste

        # <<< YENİ: Benzer yüzlerin görsellerini işle >>>
        processed_similar_faces = []
        if similar_faces:
            for face in similar_faces:
                image_id = face.get("image_id")
                image_info = face.get("image_info")  # URL bileşenlerini içeren dict
                face["image_data"] = None
                face["image_mime_type"] = None
                face["original_image_url"] = None  # Başlangıçta URL'yi de None yap

                # Öncelik: DB'den binary alıp base64 yap
                if image_id:
                    success_img, img_binary = g.db_tools.getImageBinaryByID(image_id)
                    if success_img and img_binary:
                        try:
                            img_binary = decompress_image(img_binary)
                            face["image_data"] = base64.b64encode(img_binary).decode(
                                "utf-8"
                            )
                            if img_binary.startswith(b"\x89PNG\r\n\x1a\n"):
                                face["image_mime_type"] = "image/png"
                            elif img_binary.startswith(b"\xff\xd8\xff"):
                                face["image_mime_type"] = "image/jpeg"
                            else:
                                face["image_mime_type"] = "image/jpeg"
                        except Exception as encode_err:
                            current_app.logger.error(
                                f"Similar face image (ID: {image_id}) encode error: {encode_err}"
                            )
                            face["image_data"] = None
                    # else:
                    #     current_app.logger.warning(f"Could not fetch image binary for similar face (FaceID: {face.get('id')}, ImageID: {image_id})")

                # Eğer Base64 alınamadıysa veya image_id yoksa, URL oluşturmayı dene
                if face["image_data"] is None and image_info:
                    # build_image_url helper fonksiyonunu kullanalım (varsa)
                    # Eğer yoksa, burada manuel olarak oluşturalım:
                    img_protocol = image_info.get("image_protocol", "http")
                    img_domain = image_info.get("image_domain")
                    img_path = image_info.get("image_path")
                    img_etc = image_info.get("image_etc")

                    if img_domain and img_path:
                        url = f"{img_protocol}://{img_domain}/{img_path.lstrip('/')}"
                        if img_etc:
                            url += f"?{img_etc}"
                        face["original_image_url"] = url
                        current_app.logger.debug(
                            f"Constructed URL for similar face {face.get('id')}: {url}"
                        )
                    else:
                        current_app.logger.warning(
                            f"Could not construct URL for similar face {face.get('id')} due to missing components in image_info: {image_info}"
                        )

                # Eğer image_id yoksa ve URL de oluşturulamadıysa logla
                if not image_id and face["original_image_url"] is None:
                    current_app.logger.warning(
                        f"Similar face (ID: {face.get('id')}) is missing image_id and valid image_info for URL."
                    )

                processed_similar_faces.append(face)
        # <<< Görsel İşleme Bitti >>>

        # Hedef yüz detaylarını al (şablonda göstermek için)
        # <<< DEĞİŞİKLİK: get_face_details yerine g.db_tools kullanabilir miyiz? >>>
        # SearchController.get_face_details'in ne yaptığına bağlı. Eğer sadece DB sorgusu ise,
        # g.db_tools.getFaceDetailsWithImage(target_face_id) gibi bir çağrı daha tutarlı olabilir.
        # Şimdilik SearchController'da bırakalım, ama tutarlılık için not düşelim.
        _, _, target_face_details = SearchController.get_face_details(target_face_id)
        if not target_face_details:
            target_face_details = {"id": target_face_id}  # Fallback

        # Store results in session for potential download
        # Session anahtarlarını daha açıklayıcı yapalım
        session["last_similar_search_results"] = similar_faces
        session["last_similar_search_face_id"] = target_face_id
        session["last_similar_search_threshold"] = threshold
        # Orijinal yüz detaylarını da session'a ekleyelim (PDF için)
        session["last_similar_search_original_face"] = target_face_details

        return render_template(
            "face_similarity.html",
            target_face=target_face_details,
            similar_faces=processed_similar_faces,  # <<< İşlenmiş listeyi gönder
            threshold=threshold,  # <<< Eşik değerini doğrudan gönderiyoruz
            algorithm=algorithm,
            use_cuda=use_cuda_backend,
            # stats değişkeni gönderilmiyor
        )

    except ValueError:
        flash(f"Geçersiz Yüz ID formatı: {face_id}", "danger")
        return redirect(url_for("web.index"))
    except Exception as e:
        current_app.logger.error(
            f"Benzer yüz arama hatası (Face ID: {face_id}): {e}\n{traceback.format_exc()}"
        )
        flash(
            f"Benzer yüzler aranırken beklenmedik bir hata oluştu: {str(e)}", "danger"
        )
        # Render a safe template, maybe the face details page itself with an error
        # Redirecting to index for now
        return redirect(url_for("web.index"))


# Yeni Rota: Benzer Yüz Arama Sonuçları için PDF İndirme
@web_bp.route("/download/similar_search_report", methods=["GET"])
@login_required
def download_similar_search_report():
    """Son benzer yüz arama sonuçları için PDF raporu oluşturur ve indirir."""
    search_results = session.get("last_similar_search_results")
    face_id = session.get("last_similar_search_face_id")
    threshold = session.get("last_similar_search_threshold", 0.6)
    original_face = session.get("last_similar_search_original_face")

    if not search_results or not face_id or not original_face:
        flash(
            "İndirilecek rapor verisi bulunamadı veya oturum süresi doldu.", "warning"
        )
        return redirect(url_for("web.index"))

    username = session.get("username", "Bilinmeyen Kullanıcı")
    if hasattr(g, "user") and g.user and "username" in g.user:
        username = g.user["username"]
    elif "username" in session:
        username = session["username"]

    # Orijinal yüzün adını veya ID'sini alalım
    original_face_desc = f"Yüz ID: {face_id}"
    if original_face.get("Name"):  # Session'daki original_face'den adı al
        original_face_desc = f"{original_face['Name']} (ID: {face_id})"

    search_type = (
        f"Benzer Yüz Araması (Kaynak: {original_face_desc}, Eşik: {threshold})"
    )

    # --- PDF Verisi Hazırlama ---
    pdf_data = []
    conn = None
    cursor = None
    try:
        conn = g.db_tools.connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # --- Güncellenmiş SQL Sorgusu ---
        # ImageID'den binary veriyi almak için LEFT JOIN ve SELECT eklendi
        # Yüz öznitelikleri (gender, age, score, facebox) Milvus'tan alınacağı için sorgudan çıkarıldı.
        sql_query = """ 
            SELECT 
                f."ID" as face_id, 
                -- f."FaceGender" as gender,  -- Milvus'tan alınacak
                -- f."FaceAge" as age,        -- Milvus'tan alınacak
                -- f."DetectionScore" as score, -- Milvus'tan alınacak
                -- f."FaceBox" as facebox,    -- Milvus'tan alınacak
                bds."Domain" as source_domain, 
                pds."Path" as source_path, 
                eds."Etc" as source_etc,
                m."Protocol" as source_protocol,
                -- Resim URL için bileşenler
                bdi."Domain" as image_domain,
                pi."Path" as image_path,
                ei."Etc" as image_etc,
                m."ImageProtocol" as image_protocol,
                -- Diğer bilgiler
                ti."Title" as image_title,
                h."ImageHash" as image_hash,
                m."RiskLevel" as risk_level, -- Risk seviyesini de alalım
                img."BinaryImage" as binary_image -- Binary Image Data eklendi
            FROM "EyeOfWebFaceID" f
            -- ImageBasedMain'e bağlan (FaceID array'i içerir)
            JOIN "ImageBasedMain" m ON f."ID" = ANY(m."FaceID")
            -- Kaynak URL bileşenleri için JOIN'ler
            LEFT JOIN "BaseDomainID" bds ON m."BaseDomainID" = bds."ID"
            LEFT JOIN "UrlPathID" pds ON m."UrlPathID" = pds."ID"
            LEFT JOIN "UrlEtcID" eds ON m."UrlEtcID" = eds."ID"
            -- Resim URL bileşenleri için JOIN'ler
            LEFT JOIN "BaseDomainID" bdi ON m."ImageDomainID" = bdi."ID"
            LEFT JOIN "ImageUrlPathID" pi ON m."ImagePathID" = pi."ID"
            LEFT JOIN "ImageUrlEtcID" ei ON m."ImageUrlEtcID" = ei."ID"
            -- Diğer ID tabloları için JOIN'ler
            LEFT JOIN "ImageTitleID" ti ON m."ImageTitleID" = ti."ID"
            LEFT JOIN "ImageHashID" h ON m."HashID" = h."ID"
            LEFT JOIN "ImageID" img ON m."ImageID" = img."ID" -- ImageID tablosuna JOIN eklendi
            WHERE f."ID" = %s
            ORDER BY m."DetectionDate" DESC -- En yeni kaydı al
            LIMIT 1 
        """

        # Yüzlerin kaynaklarını belirlemek için ek sorgular (Whitelist, EGM)
        def check_source(face_id_to_check):
            # WhiteList kontrolü
            cursor.execute(
                'SELECT 1 FROM "WhiteListFaces" WHERE "ID" = %s LIMIT 1',
                (face_id_to_check,),
            )
            if cursor.fetchone():
                return " [Beyaz Liste]"
            # EGM kontrolü
            cursor.execute(
                'SELECT 1 FROM "EgmArananlar" WHERE "ID" = %s LIMIT 1',
                (face_id_to_check,),
            )
            if cursor.fetchone():
                return " [EGM]"
            return ""

        for result in search_results:
            res_face_id = result.get("id", None)
            if not res_face_id:
                print(f"Uyarı: Sonuç listesinde geçersiz face_id: {result}")
                continue

            # --- Veritabanından Ek Bilgileri Al (PostgreSQL - URL'ler, hash, risk vb.) ---
            cursor.execute(sql_query, (res_face_id,))  # sql_query güncellendi
            db_pg_data = cursor.fetchone()  # PostgreSQL'den gelen veri

            if not db_pg_data:
                print(
                    f"Uyarı: Veritabanında face_id veya ilişkili kayıt bulunamadı: {res_face_id}"
                )
                continue  # Bu sonucu atla

            # --- Milvus'tan Yüz Özniteliklerini Al ---
            milvus_attributes = None
            try:
                milvus_attributes = g.db_tools.get_milvus_face_attributes(
                    EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME, res_face_id
                )
                if not milvus_attributes:
                    current_app.logger.warning(
                        f"Milvus'tan {res_face_id} için öznitelik alınamadı."
                    )
            except Exception as e:
                current_app.logger.error(
                    f"Milvus'tan {res_face_id} için öznitelik alınırken hata: {e}"
                )

            # --- PDF Öğesini Oluştur ---
            source_tag = check_source(res_face_id)  # Kaynağı kontrol et

            # Name alanı EyeOfWebFaceID'de olmadığından şimdilik sadece ID kullanıyoruz
            title = f"Yüz ID: {res_face_id}{source_tag}"

            # Cinsiyet formatını düzelt (Milvus'tan)
            gender_bool = (
                milvus_attributes.get("face_gender") if milvus_attributes else None
            )
            gender_str = (
                "Erkek"
                if gender_bool is True
                else ("Kadın" if gender_bool is False else "N/A")
            )

            # Yaş, Skor, Facebox (Milvus'tan)
            age_from_milvus = (
                milvus_attributes.get("face_age") if milvus_attributes else None
            )
            score_from_milvus = (
                milvus_attributes.get("detection_score") if milvus_attributes else None
            )
            facebox_from_milvus = (
                milvus_attributes.get("face_box") if milvus_attributes else None
            )

            # Resim verisini veya URL'yi hazırla (PostgreSQL'den)
            image_data_b64 = None
            image_url = None
            binary_image_data = db_pg_data.get("binary_image")

            if binary_image_data:
                try:
                    decompressed_image_bytes = decompress_image(binary_image_data)
                    if decompressed_image_bytes:
                        image_data_b64 = base64.b64encode(
                            decompressed_image_bytes
                        ).decode("utf-8")
                    else:
                        current_app.logger.warning(
                            f"PDF Raporu (image_search): {res_face_id} için dekompresyon başarısız veya boş veri."
                        )
                except Exception as e:
                    current_app.logger.error(
                        f"PDF Raporu (image_search): {res_face_id} için dekompresyon/encode hatası: {e}"
                    )
            # Görsel Base64 olarak hazırlanamazsa, image_data_b64 None kalacak ve PDF'te görsel olmayacak.
            # URL fallback YOK.

            source_url = build_image_url(
                db_pg_data.get("source_protocol"),
                db_pg_data.get("source_domain"),
                db_pg_data.get("source_path"),
                db_pg_data.get("source_etc"),
            )

            pdf_item = {
                "title": title,
                "image_data_b64": image_data_b64,
                "image_url": image_url,  # Bu her zaman None olacak (yukarıdaki mantığa göre)
                "source_url": source_url,
                "hash": db_pg_data.get("image_hash", "N/A"),
                "count": result.get("count", 1),
                "score": score_from_milvus,
                "gender": gender_str,
                "age": age_from_milvus,
                "similarity": {
                    "name": f"Kaynak Yüz ({original_face_desc})",
                    "rate": result.get("similarity", 0),
                },
                "comprehensive_info": None,
                "facebox": facebox_from_milvus,
            }
            pdf_data.append(pdf_item)

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"PDF verisi hazırlanırken veritabanı hatası: {error}")
        print(traceback.format_exc())
        flash("Rapor verileri hazırlanırken bir veritabanı hatası oluştu.", "danger")
        # Hata durumunda bile bağlantıyı kapat
        if conn:
            g.db_tools.releaseConnection(conn, cursor)
        return redirect(
            url_for("web.face_details", face_id=face_id)
        )  # Benzer arama için face_details'a yönlendir
    finally:
        # Bağlantıyı kapat
        if conn:
            g.db_tools.releaseConnection(conn, cursor)

    # --- PDF Raporunu Oluştur ve Gönder ---
    if not pdf_data:
        flash("Rapor için işlenecek geçerli veri bulunamadı.", "warning")
        return redirect(url_for("web.face_details", face_id=face_id))

    pdf_bytes = generate_pdf_report(search_type, username, pdf_data)

    if pdf_bytes is None:
        flash("PDF raporu oluşturulurken bir hata oluştu.", "danger")
        return redirect(url_for("web.face_details", face_id=face_id))

    report_filename = f"EyeOfWeb_BenzerArama_{face_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=report_filename,
    )


@web_bp.route("/dashboard")
@login_required
def dashboard():
    """İstatistik ve genel bakış sayfası"""
    # Admin kullanıcısı kontrolü
    if not session.get("is_admin", False):
        abort(403)  # Yetkisiz erişim

    # İstatistik verilerini al
    stats = {
        "total_faces": 0,
        "total_domains": 0,
        "total_images": 0,
        "high_risk": 0,
        "recent_scans": [],
        "table_stats": [],
        "db_size": {},
        "risk_levels_chart": [],
        "categories_chart": [],
    }

    try:
        # Güvenli veritabanı sorgularıyla istatistikleri çek
        # Toplam yüz sayısı
        result = g.db_tools.executeQuery(
            'SELECT COUNT(*) as count FROM "ImageBasedMain"'
        )
        if result and len(result) > 0:
            stats["total_faces"] = result[0]["count"]

        # Toplam domain sayısı
        result = g.db_tools.executeQuery(
            'SELECT COUNT(DISTINCT "BaseDomainID") as count FROM "ImageBasedMain"'
        )
        if result and len(result) > 0:
            stats["total_domains"] = result[0]["count"]

        # Toplam görsel sayısı
        result = g.db_tools.executeQuery(
            'SELECT COUNT(DISTINCT "ImageID") as count FROM "ImageBasedMain"'
        )
        if result and len(result) > 0:
            stats["total_images"] = result[0]["count"]

        # Yüksek riskli yüz sayısı
        result = g.db_tools.executeQuery(
            'SELECT COUNT(*) as count FROM "ImageBasedMain" WHERE "RiskLevel" = \'yüksek\''
        )
        if result and len(result) > 0:
            stats["high_risk"] = result[0]["count"]

        # Risk seviyesi dağılımı için veri
        risk_query = g.db_tools.executeQuery(
            """
            SELECT "RiskLevel" as risk_level, COUNT(*) as count 
            FROM "ImageBasedMain" 
            GROUP BY "RiskLevel" 
            ORDER BY 
                CASE 
                    WHEN "RiskLevel" = 'düşük' THEN 1 
                    WHEN "RiskLevel" = 'orta' THEN 2 
                    WHEN "RiskLevel" = 'yüksek' THEN 3 
                    WHEN "RiskLevel" = 'kritik' THEN 4
                    ELSE 5 
                END
        """
        )

        if risk_query and len(risk_query) > 0:
            stats["risk_levels_chart"] = risk_query

        # Kategori dağılımı için veri
        category_query = g.db_tools.executeQuery(
            """
            SELECT wc."Category" as category, COUNT(*) as count 
            FROM "ImageBasedMain" i
            LEFT JOIN "WebSiteCategoryID" wc ON i."CategoryID" = wc."ID"
            GROUP BY wc."Category"
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """
        )

        if category_query and len(category_query) > 0:
            stats["categories_chart"] = category_query

        # Tüm tabloların kayıt sayılarını al
        table_query = g.db_tools.executeQuery(
            """
            SELECT tablename FROM pg_catalog.pg_tables 
            WHERE schemaname = 'public' 
            ORDER BY tablename
        """
        )

        if table_query and len(table_query) > 0:
            for table in table_query:
                table_name = table["tablename"]
                count_query = g.db_tools.executeQuery(
                    f'SELECT COUNT(*) as count FROM "{table_name}"'
                )
                if count_query and len(count_query) > 0:
                    stats["table_stats"].append(
                        {"name": table_name, "count": count_query[0]["count"]}
                    )

        # Veritabanı boyutunu al
        db_size_query = g.db_tools.executeQuery(
            """
            SELECT 
                pg_size_pretty(pg_database_size(current_database())) as pretty_size,
                pg_database_size(current_database()) as size_bytes
            FROM pg_database
            WHERE datname = current_database()
        """
        )

        if db_size_query and len(db_size_query) > 0:
            stats["db_size"] = {
                "pretty_size": db_size_query[0]["pretty_size"],
                "size_bytes": db_size_query[0]["size_bytes"],
            }

        # Her bir tablonun boyutunu al
        table_sizes_query = g.db_tools.executeQuery(
            """
            SELECT 
                relname as table_name,
                pg_size_pretty(pg_total_relation_size(relid)) as pretty_size,
                pg_total_relation_size(relid) as size_bytes
            FROM pg_catalog.pg_statio_user_tables
            ORDER BY pg_total_relation_size(relid) DESC
        """
        )

        if table_sizes_query and len(table_sizes_query) > 0:
            stats["table_sizes"] = table_sizes_query

        # Son taramalar (en son 5 tarama)
        recent_scans = g.db_tools.executeQuery(
            """
            SELECT b.\"Domain\" as \"Domain\", a.\"DetectionDate\", COUNT(*) as faces_found 
            FROM \"ImageBasedMain\" a
            JOIN \"BaseDomainID\" b ON a.\"BaseDomainID\" = b.\"ID\"
            GROUP BY b.\"Domain\", a.\"DetectionDate\" 
            ORDER BY a.\"DetectionDate\" DESC 
            LIMIT 5
        """
        )

        if recent_scans and len(recent_scans) > 0:
            for scan in recent_scans:
                image_url = None
                # Son taranan domaine ait bir görsel bul
                img_result = g.db_tools.executeQuery(
                    """
                    SELECT i.\"BinaryImage\" as \"ImageUrl\" 
                    FROM \"ImageBasedMain\" a
                    JOIN \"BaseDomainID\" b ON a.\"BaseDomainID\" = b.\"ID\"
                    JOIN \"ImageID\" i ON a.\"ImageID\" = i.\"ID\"
                    WHERE b.\"Domain\" = %s AND a.\"DetectionDate\" = %s 
                    LIMIT 1
                """,
                    (scan["Domain"], scan["DetectionDate"]),
                )

                if img_result and len(img_result) > 0:
                    image_url = img_result[0]["ImageUrl"]

                stats["recent_scans"].append(
                    {
                        "domain": html.escape(scan["Domain"]),  # XSS koruması
                        "date": (
                            scan["DetectionDate"].strftime("%d.%m.%Y %H:%M")
                            if scan["DetectionDate"]
                            else ""
                        ),
                        "faces_found": scan["faces_found"],
                        "image_url": image_url,
                    }
                )

    except Exception as e:
        current_app.logger.error(f"Dashboard istatistikleri alınırken hata: {str(e)}")
        flash(f"İstatistik verileri yüklenirken bir hata oluştu", "danger")

    return render_template("dashboard.html", stats=stats)


@web_bp.route("/whitelist", methods=["GET", "POST"])
@login_required
@limiter.limit("20/minute")
def whitelist_search():
    """Beyaz liste yüzlerini arama sayfası"""
    if request.method == "POST":
        # Form verilerini al ve güvenli hale getir
        search_params = {}

        # Güvenli parametreleri ekle
        if request.form.get("face_name"):
            search_params["face_name"] = html.escape(request.form.get("face_name", ""))

        if request.form.get("institution"):
            search_params["institution"] = html.escape(
                request.form.get("institution", "")
            )

        if request.form.get("category"):
            search_params["category"] = html.escape(request.form.get("category", ""))

        # Tarih parametrelerini doğrula
        start_date = request.form.get("start_date")
        if start_date:
            try:
                # Tarihi doğrula
                datetime.datetime.strptime(start_date, "%Y-%m-%d")
                search_params["start_date"] = start_date
            except ValueError:
                flash(
                    "Başlangıç tarihi formatı geçersiz. YYYY-AA-GG formatında olmalıdır.",
                    "warning",
                )
                return redirect(url_for("web.whitelist_search"))

        end_date = request.form.get("end_date")
        if end_date:
            try:
                # Tarihi doğrula
                datetime.datetime.strptime(end_date, "%Y-%m-%d")
                search_params["end_date"] = end_date
            except ValueError:
                flash(
                    "Bitiş tarihi formatı geçersiz. YYYY-AA-GG formatında olmalıdır.",
                    "warning",
                )
                return redirect(url_for("web.whitelist_search"))

        # En az bir arama parametresi gerekli
        if not search_params:
            flash("En az bir arama kriteri belirtmelisiniz", "warning")
            return redirect(url_for("web.whitelist_search"))

        # Arama işlemini gerçekleştir
        success, message, results = SearchController.search_whitelist_faces(
            search_params
        )

        # Sonuçları göster
        if not success:
            flash(f"Arama sırasında hata oluştu: {message}", "danger")
            return redirect(url_for("web.whitelist_search"))

        return render_template(
            "whitelist_results.html", results=results, params=search_params
        )

    # GET isteği - Form sayfasını göster
    return render_template("whitelist_search.html")


@web_bp.route("/whitelist/yuzara/<int:face_id>", methods=["GET"])
@login_required
def whitelist_search_by_face(face_id):
    """Beyaz listedeki yüzü kullanarak benzer yüzleri ara"""
    try:
        # Eşik değerini al (varsayılan: 0.6)
        threshold = request.args.get("threshold", 0.6, type=float)

        # Yüz detaylarını al
        success, message, face_details = g.db_tools.getWhiteListFaceDetails(face_id)

        if not success or not face_details:
            flash("Belirtilen yüz bulunamadı.", "danger")
            return redirect(url_for("web.whitelist_search"))

        # Yüz embedding'i al
        face_embedding = face_details.get("face_embedding")
        if not face_embedding:
            flash("Yüz vektörü bulunamadı.", "danger")
            return redirect(url_for("web.whitelist_search"))

        # Benzer yüzleri ara
        success, message, results = SearchController.search_by_embedding(
            face_embedding, threshold
        )

        if not success:
            flash(message, "danger")
            return redirect(url_for("web.whitelist_search"))

        # Orijinal yüzün bilgilerini ekle
        original_face = {
            "id": face_details["id"],
            "face_name": face_details.get("face_name", "Bilinmeyen"),
            "image_data": face_details.get("image_data"),
            "institution": face_details.get("institution", ""),
            "category": face_details.get("category", ""),
        }

        return render_template(
            "whitelist_similar_results.html",
            results=results,
            original_face=original_face,
            threshold=threshold,
        )

    except Exception as e:
        flash(f"Arama sırasında bir hata oluştu: {str(e)}", "danger")
        return redirect(url_for("web.whitelist_search"))


@web_bp.route("/external", methods=["GET", "POST"])
@login_required
@limiter.limit("20/minute")
def external_search():
    """Dış yüz deposundaki yüzleri arama sayfası"""
    if request.method == "POST":
        # Form verilerini al
        search_params = {}
        for key in request.form:
            if key != "csrf_token" and request.form[key]:
                search_params[key] = request.form[key]

        # Alarm parametresini düzenle
        if "alarm" in search_params:
            if search_params["alarm"] == "any":
                search_params["alarm"] = None
            elif search_params["alarm"] == "true":
                search_params["alarm"] = True
            elif search_params["alarm"] == "false":
                search_params["alarm"] = False

        # En az bir arama parametresi gerekli
        valid_params = {
            k: v for k, v in search_params.items() if k != "alarm" or v is not None
        }
        if not valid_params:
            flash("En az bir arama kriteri belirtmelisiniz", "warning")
            return redirect(url_for("web.external_search"))

        # Arama işlemini gerçekleştir
        success, message, results = SearchController.search_external_faces(
            search_params
        )

        # Sonuçları göster
        if not success:
            flash(f"Arama sırasında hata oluştu: {message}", "danger")
            return redirect(url_for("web.external_search"))

        return render_template(
            "external_results.html", results=results, params=search_params
        )

    # GET isteği - Form verilerini hazırla
    return render_template("external_search.html")


@web_bp.route("/egm", methods=["GET", "POST"])
@login_required
def egm_search():
    """EGM arananlar listesindeki yüzleri arama sayfası"""
    try:
        # Örgüt tipleri ve seviyelerini al
        organizer_types = ["PKK/KCK", "FETÖ/PDY", "DHKP/C", "DEAŞ", "Diğer"]
        organizer_levels = ["Üst", "Orta", "Alt"]

        if request.method == "GET":
            return render_template(
                "egm_search.html",
                organizer_types=organizer_types,
                organizer_levels=organizer_levels,
            )

        # Form verilerini al ve güvenli hale getir
        search_params = {}

        # Güvenli parametreleri ekle
        if request.form.get("face_name"):
            search_params["face_name"] = html.escape(request.form.get("face_name", ""))

        if request.form.get("organizer"):
            organizer = request.form.get("organizer", "")
            # Sadece izin verilen değerleri kabul et
            if organizer in organizer_types:
                search_params["organizer"] = organizer

        if request.form.get("organizer_level"):
            organizer_level = request.form.get("organizer_level", "")
            # Sadece izin verilen değerleri kabul et
            if organizer_level in organizer_levels:
                search_params["organizer_level"] = organizer_level

        # Tarih parametrelerini doğrula
        start_date = request.form.get("start_date")
        if start_date:
            try:
                # Tarihi doğrula
                datetime.datetime.strptime(start_date, "%Y-%m-%d")
                search_params["start_date"] = start_date
            except ValueError:
                flash(
                    "Başlangıç tarihi formatı geçersiz. YYYY-AA-GG formatında olmalıdır.",
                    "warning",
                )
                return redirect(url_for("web.egm_search"))

        end_date = request.form.get("end_date")
        if end_date:
            try:
                # Tarihi doğrula
                datetime.datetime.strptime(end_date, "%Y-%m-%d")
                search_params["end_date"] = end_date
            except ValueError:
                flash(
                    "Bitiş tarihi formatı geçersiz. YYYY-AA-GG formatında olmalıdır.",
                    "warning",
                )
                return redirect(url_for("web.egm_search"))

        if not search_params:
            flash("Lütfen en az bir arama kriteri belirleyin.", "warning")
            return redirect(url_for("web.egm_search"))

        # Arama yap
        success, message, results = SearchController.search_egm_arananlar(search_params)

        if not success:
            flash(message, "danger")
            return redirect(url_for("web.egm_search"))

        if not results:
            flash("Arama kriterlerine uygun sonuç bulunamadı.", "info")

        return render_template(
            "egm_results.html", results=results, params=search_params
        )

    except Exception as e:
        flash(f"Arama sırasında bir hata oluştu: {str(e)}", "danger")
        return render_template(
            "egm_search.html",
            organizer_types=organizer_types,
            organizer_levels=organizer_levels,
        )


@web_bp.route("/egm_search_by_face/<face_id>", methods=["GET"])
def egm_search_by_face(face_id):
    try:
        # Varsayılan benzerlik eşiği
        threshold = request.args.get("threshold", default=0.6, type=float)

        # Orijinal EGM yüzünü getir
        original_face = g.db_tools.getEgmFaceDetails(face_id)

        if not original_face:
            flash("Belirtilen yüz bulunamadı.", "error")
            return redirect(url_for("web.egm_search"))

        # Yüz vektörünü numpy dizisine dönüştür
        if original_face.get("embedding"):
            face_embedding = np.array(
                ast.literal_eval(original_face["embedding"]), dtype=np.float32
            )

            # Benzer EGM yüzlerini bul
            similar_faces = g.db_tools.findSimilarEgmFaces(face_embedding, threshold)

            # Sonuçları yüz ID'sine göre filtrele (kendi kendini hariç tut)
            filtered_results = [
                face
                for face in similar_faces
                if str(face.get("id", "")) != str(face_id)
            ]

            return render_template(
                "egm_similar_results.html",
                original_face=original_face,
                results=filtered_results,
                threshold=threshold,
            )
        else:
            flash("Seçilen yüz için yüz vektörü bulunamadı.", "error")
            return redirect(url_for("web.egm_search"))

    except Exception as e:
        print(f"EGM yüz benzerliği aramasında hata: {str(e)}")
        flash(f"Arama sırasında bir hata oluştu: {str(e)}", "error")
        return redirect(url_for("web.egm_search"))


@web_bp.route("/search/upload", methods=["GET", "POST"])
@login_required
@limiter.limit("20/minute")
def upload_search():
    """Görsel yükleme ile arama"""
    if request.method == "POST":
        if "image_file" not in request.files:
            flash("Lütfen bir görsel yükleyin", "warning")
            return redirect(request.url)

        file = request.files["image_file"]
        # YENİ: Resim doğrulama ve temizleme
        sanitized_img, secure_name = validate_and_sanitize_image(file)

        if sanitized_img is None:  # Hata oluştu
            flash(secure_name, "danger")  # secure_name burada hata mesajını içerir
            return redirect(request.url)

        # Eşik değerini formdan al
        threshold = float(request.form.get("threshold", 0.6))

        # Arama yapılacak kaynakları belirle
        search_whitelist = "search_whitelist" in request.form
        search_egm = "search_egm" in request.form

        try:
            # Görsel dosyasını PIL Image olarak aç (ZATEN sanitized_img OLARAK ALINDI)
            # img = Image.open(file) # ESKİ KOD
            img = sanitized_img  # YENİ KOD

            # NumPy dizisine dönüştür (RGB)
            img_array = np.array(img.convert("RGB"))

            # Arama işlemini gerçekleştir
            success, message, results = SearchController.search_by_image(
                img_array,
                threshold=threshold,
                search_whitelist=search_whitelist,
                search_egm=search_egm,
            )

            if not success:
                flash(message, "danger")
                return redirect(request.url)

            # Sonuçları göster
            return render_template(
                "search_results.html",
                results=results,
                message=message,
                query_type="görsel",
                image_name=secure_name,
            )  # YENİ: Güvenli dosya adı eklendi
        except Exception as e:
            flash(f"Görsel işlenirken hata oluştu: {str(e)}", "danger")
            return redirect(request.url)

    # GET isteği - Form sayfasını göster
    return render_template("upload_search.html")


@web_bp.route("/whitelist_upload", methods=["GET", "POST"])
@login_required
@limiter.limit("20/minute")
def whitelist_upload_search():
    """Beyaz liste için görsel yükleme ile arama"""
    if request.method == "POST":
        if "image_file" not in request.files:
            flash("Lütfen bir görsel yükleyin", "warning")
            return redirect(request.url)

        file = request.files["image_file"]
        # YENİ: Resim doğrulama ve temizleme
        sanitized_img, secure_name = validate_and_sanitize_image(file)

        if sanitized_img is None:  # Hata oluştu
            flash(secure_name, "danger")  # secure_name burada hata mesajını içerir
            return redirect(request.url)

        # Eşik değerini formdan al
        threshold = float(request.form.get("threshold", 0.6))

        try:
            # Görsel dosyasını PIL Image olarak aç (ZATEN sanitized_img OLARAK ALINDI)
            # img = Image.open(file) # ESKİ KOD
            img = sanitized_img  # YENİ KOD

            # NumPy dizisine dönüştür (RGB)
            img_array = np.array(img.convert("RGB"))

            # Sorgu görseli için base64
            # BGR'den RGB'ye dönüşüm yapıyoruz (OpenCV BGR kullanır)
            # img_array zaten RGB, Pillow'dan geldiği için.
            # Eğer OpenCV'ye verilecekse BGR'ye çevrilmeli.
            # img_rgb = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR) # Eğer img_array hep RGB ise bu doğru
            # Buradaki img_array Pillow'dan geldiği ve RGB'ye dönüştürüldüğü için doğrudan kullanılabilir
            # ya da BGR'ye çevrilebilir eğer SearchController.search_by_image bunu bekliyorsa.
            # Şimdilik Pillow image'ından (sanitized_img) base64 oluşturalım.

            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")  # veya PNG
            query_face_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

            # Arama işlemini gerçekleştir - sadece whitelist'te ara
            success, message, results = SearchController.search_by_image(
                img_array, threshold=threshold, search_whitelist=True, search_egm=False
            )

            if not success:
                flash(message, "danger")
                return redirect(request.url)

            # Sadece beyaz liste sonuçlarını filtrele
            whitelist_results = [r for r in results if r.get("source") == "whitelist"]

            if not whitelist_results:
                flash(
                    "Yüklediğiniz görselde beyaz listeyle eşleşen yüzler bulunamadı.",
                    "info",
                )
                return redirect(request.url)

            # Sonuçları göster
            return render_template(
                "whitelist_results.html",
                results=whitelist_results,
                message=f"{len(whitelist_results)} adet beyaz liste eşleşmesi bulundu.",
                params={
                    "threshold": threshold,
                    "query_type": "görsel",
                    "image_name": secure_name,
                },
                query_face_image=query_face_b64,
            )
        except Exception as e:
            flash(f"Görsel işlenirken hata oluştu: {str(e)}", "danger")
            return redirect(request.url)

    # GET isteği - Form sayfasını göster
    return render_template("whitelist_upload.html")


@web_bp.route("/egm_upload", methods=["GET", "POST"])
@login_required
@limiter.limit("20/minute")
def egm_upload_search():
    """EGM arananlar için görsel yükleme ile arama"""
    if request.method == "POST":
        if "image_file" not in request.files:
            flash("Lütfen bir görsel yükleyin", "warning")
            return redirect(request.url)

        file = request.files["image_file"]
        # YENİ: Resim doğrulama ve temizleme
        sanitized_img, secure_name = validate_and_sanitize_image(file)

        if sanitized_img is None:  # Hata oluştu
            flash(secure_name, "danger")  # secure_name burada hata mesajını içerir
            return redirect(request.url)

        # Eşik değerini formdan al
        threshold = float(request.form.get("threshold", 0.6))

        try:
            # Görsel dosyasını PIL Image olarak aç (ZATEN sanitized_img OLARAK ALINDI)
            # img = Image.open(file) # ESKİ KOD
            img = sanitized_img  # YENİ KOD

            # NumPy dizisine dönüştür (RGB)
            img_array = np.array(img.convert("RGB"))

            # Sorgu görseli için base64 (whitelist_upload_search'teki gibi)
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            query_face_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

            # Arama işlemini gerçekleştir - sadece EGM'de ara
            success, message, results = SearchController.search_by_image(
                img_array, threshold=threshold, search_whitelist=False, search_egm=True
            )

            if not success:
                flash(message, "danger")
                return redirect(request.url)

            # Sadece EGM sonuçlarını filtrele
            egm_results = [r for r in results if r.get("source") == "egm"]

            if not egm_results:
                flash(
                    "Yüklediğiniz görselde EGM arananlar listesiyle eşleşen yüzler bulunamadı.",
                    "info",
                )
                return redirect(request.url)

            # Sonuçları göster
            return render_template(
                "egm_results.html",
                results=egm_results,
                message=f"{len(egm_results)} adet EGM arananlar listesi eşleşmesi bulundu.",
                params={
                    "threshold": threshold,
                    "query_type": "görsel",
                    "image_name": secure_name,
                },
                query_face_image=query_face_b64,
            )
        except Exception as e:
            flash(f"Görsel işlenirken hata oluştu: {str(e)}", "danger")
            return redirect(request.url)

    # GET isteği - Form sayfasını göster
    return render_template("egm_upload.html")


@web_bp.route("/face/detection", methods=["GET", "POST"])
@login_required
@limiter.limit("20/minute")
def face_detection():
    """Yüz tespiti sayfası"""
    report_available = False
    if request.method == "POST":
        if "image_file" not in request.files:
            flash("Lütfen bir görsel yükleyin", "warning")
            return redirect(request.url)

        file = request.files["image_file"]
        # YENİ: Resim doğrulama ve temizleme
        sanitized_img, secure_name = validate_and_sanitize_image(file)

        if sanitized_img is None:  # Hata oluştu
            flash(secure_name, "danger")  # secure_name burada hata mesajını içerir
            return redirect(request.url)

        try:
            # Görsel dosyasını PIL Image olarak aç (ZATEN sanitized_img OLARAK ALINDI)
            # img = Image.open(file) # ESKİ KOD
            img = sanitized_img  # YENİ KOD

            # NumPy dizisine dönüştür (RGB)
            img_array = np.array(img.convert("RGB"))

            # OpenCV için BGR'ye dönüştür (InsightFace BGR formatını kullanır)
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

            # Yüz tespiti yap
            success, message, results = SearchController.detect_faces(img_bgr)

            if not success:
                flash(message, "danger")
                return redirect(request.url)

            # --- PDF Rapor Verisi Hazırlama ---
            pdf_data = []
            processed_image_b64 = None
            if results and results.get("faces"):
                img_with_boxes = img_bgr.copy()
                img_height, img_width = img_with_boxes.shape[:2]

                for idx, face in enumerate(results["faces"]):
                    bbox = face.get("bbox")
                    if bbox and len(bbox) == 4:
                        x1, y1, x2, y2 = map(int, bbox)
                        # Draw rectangle
                        color = (255, 0, 0)  # Blue for detection
                        thickness = 2
                        cv2.rectangle(
                            img_with_boxes, (x1, y1), (x2, y2), color, thickness
                        )
                        # Add index number
                        text = f"#{idx+1}"
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        font_scale = 0.6
                        text_color = (255, 255, 255)
                        text_thickness = 1
                        (text_width, text_height), _ = cv2.getTextSize(
                            text, font, font_scale, text_thickness
                        )
                        text_x = x1
                        text_y = (
                            y1 - 5 if y1 - 5 > text_height else y1 + text_height + 5
                        )
                        cv2.rectangle(
                            img_with_boxes,
                            (text_x, text_y - text_height - 2),
                            (text_x + text_width + 2, text_y + 2),
                            color,
                            -1,
                        )
                        cv2.putText(
                            img_with_boxes,
                            text,
                            (text_x + 1, text_y - 1),
                            font,
                            font_scale,
                            text_color,
                            text_thickness,
                            cv2.LINE_AA,
                        )

                # Encode processed image to base64
                _, buffer = cv2.imencode(".jpg", img_with_boxes)
                processed_image_b64 = base64.b64encode(buffer).decode("utf-8")

                # Prepare data for each face
                for idx, face in enumerate(results["faces"]):
                    gender_str = (
                        "Erkek"
                        if face.get("gender") == 1
                        else ("Kadın" if face.get("gender") == 0 else "N/A")
                    )
                    pdf_item = {
                        "title": f"Tespit Edilen Yüz #{idx+1}",
                        "image_data_b64": processed_image_b64,  # Use the same processed image
                        "image_url": None,  # Ensure URL is None if base64 is provided
                        "source_url": f"Yüklenen Dosya: {secure_name}",  # YENİ: secure_name kullanıldı
                        "hash": "N/A",
                        "count": 1,  # Representing one detected face
                        "score": face.get("det_score"),
                        "gender": gender_str,
                        "age": face.get("age"),
                        "similarity": None,
                        "comprehensive_info": None,
                        # Pass facebox separately if needed, but it's drawn on image_data_b64
                        "facebox": face.get("bbox"),
                    }
                    pdf_data.append(pdf_item)

                # Store data in session for download
                username = session.get("username", "Bilinmeyen Kullanıcı")
                session["last_detection_report_data"] = {
                    "search_type": f"Yüz Tespiti (Dosya: {secure_name})",  # YENİ: secure_name kullanıldı
                    "username": username,
                    "pdf_data": pdf_data,
                }
                report_available = True  # Report is ready
            # --- PDF Hazırlama Bitti ---

            # Şablonu render et
            return render_template(
                "face_detection.html",
                results=results,
                message=message,
                report_available=report_available,
            )  # Pass the flag
        except Exception as e:
            flash(f"Görsel işlenirken hata oluştu: {str(e)}", "danger")
            current_app.logger.error(
                f"Yüz tespiti hatası: {str(e)}\n{traceback.format_exc()}"
            )
            return redirect(request.url)

    # GET isteği - Form sayfasını göster
    return render_template("face_detection.html", report_available=report_available)


@web_bp.route("/face/comparison", methods=["GET", "POST"])
@login_required
@limiter.limit("15/minute")
def face_comparison():
    """Yüz karşılaştırma sayfası"""
    report_available = False
    if request.method == "POST":
        if "image_file1" not in request.files or "image_file2" not in request.files:
            flash("Lütfen her iki görseli de yükleyin", "warning")
            return redirect(request.url)

        file1 = request.files["image_file1"]
        file2 = request.files["image_file2"]

        # YENİ: Resimleri doğrula ve temizle
        sanitized_img1, secure_name1 = validate_and_sanitize_image(file1)
        if sanitized_img1 is None:
            flash(f"İlk resim işlenirken hata: {secure_name1}", "danger")
            return redirect(request.url)

        sanitized_img2, secure_name2 = validate_and_sanitize_image(file2)
        if sanitized_img2 is None:
            flash(f"İkinci resim işlenirken hata: {secure_name2}", "danger")
            return redirect(request.url)

        # Eşik değeri parametresi
        threshold = float(request.form.get("threshold", 0.6))

        try:
            # 1. görseli işle (ZATEN sanitized_img1 OLARAK ALINDI)
            # img1 = Image.open(file1) # ESKİ KOD
            img1 = sanitized_img1  # YENİ KOD
            img1_array = np.array(img1.convert("RGB"))
            img1_bgr = cv2.cvtColor(img1_array, cv2.COLOR_RGB2BGR)

            # 2. görseli işle (ZATEN sanitized_img2 OLARAK ALINDI)
            # img2 = Image.open(file2) # ESKİ KOD
            img2 = sanitized_img2  # YENİ KOD
            img2_array = np.array(img2.convert("RGB"))
            img2_bgr = cv2.cvtColor(img2_array, cv2.COLOR_RGB2BGR)

            # Yüz karşılaştırma
            success, message, results = SearchController.compare_faces(
                img1_bgr, img2_bgr, threshold
            )

            if not success:
                flash(message, "danger")
                return redirect(request.url)

            # --- PDF Rapor Verisi Hazırlama ---
            pdf_data = []
            comparison_info_for_pdf = {}
            face1_cropped_b64 = None
            face2_cropped_b64 = None

            if results:
                img1_copy_for_crop = img1_bgr.copy()
                img2_copy_for_crop = img2_bgr.copy()
                img1_with_box = img1_bgr.copy()
                img2_with_box = img2_bgr.copy()

                # Extract face 1 cutout & draw box
                if results.get("face1") and results["face1"].get("bbox"):
                    bbox1 = results["face1"]["bbox"]
                    x1, y1, x2, y2 = map(int, bbox1)
                    # Crop face (ensure bounds are valid)
                    h1, w1 = img1_copy_for_crop.shape[:2]
                    fx1, fy1 = max(0, x1), max(0, y1)
                    fx2, fy2 = min(w1, x2), min(h1, y2)
                    if fy2 > fy1 and fx2 > fx1:
                        face1_crop = img1_copy_for_crop[fy1:fy2, fx1:fx2]
                        _, buffer_crop1 = cv2.imencode(".jpg", face1_crop)
                        face1_cropped_b64 = base64.b64encode(buffer_crop1).decode(
                            "utf-8"
                        )
                    # Draw box on the other copy
                    cv2.rectangle(img1_with_box, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Extract face 2 cutout & draw box
                if results.get("face2") and results["face2"].get("bbox"):
                    bbox2 = results["face2"]["bbox"]
                    x1, y1, x2, y2 = map(int, bbox2)
                    # Crop face (ensure bounds are valid)
                    h2, w2 = img2_copy_for_crop.shape[:2]
                    fx1, fy1 = max(0, x1), max(0, y1)
                    fx2, fy2 = min(w2, x2), min(h2, y2)
                    if fy2 > fy1 and fx2 > fx1:
                        face2_crop = img2_copy_for_crop[fy1:fy2, fx1:fx2]
                        _, buffer_crop2 = cv2.imencode(".jpg", face2_crop)
                        face2_cropped_b64 = base64.b64encode(buffer_crop2).decode(
                            "utf-8"
                        )
                    # Draw box on the other copy
                    cv2.rectangle(img2_with_box, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Encode full images with boxes
                _, buffer1 = cv2.imencode(".jpg", img1_with_box)
                image1_full_b64 = base64.b64encode(buffer1).decode("utf-8")
                _, buffer2 = cv2.imencode(".jpg", img2_with_box)
                image2_full_b64 = base64.b64encode(buffer2).decode("utf-8")

                # Prepare PDF data items
                pdf_item1 = {
                    "title": f"Karşılaştırılan Görsel 1 ({secure_name1})",  # YENİ: secure_name1
                    "image_data_b64": image1_full_b64,
                    "face_cropped_b64": face1_cropped_b64,
                    "image_url": None,
                    "source_url": "Yüklenen Dosya",
                    "hash": "N/A",
                    "count": 1,
                    "score": results.get("face1", {}).get("det_score"),
                    "gender": (
                        "Erkek"
                        if results.get("face1", {}).get("gender") == 1
                        else (
                            "Kadın"
                            if results.get("face1", {}).get("gender") == 0
                            else "N/A"
                        )
                    ),
                    "age": results.get("face1", {}).get("age"),
                    "similarity": None,
                    "comprehensive_info": None,
                    "facebox": results.get("face1", {}).get("bbox"),
                }
                pdf_item2 = {
                    "title": f"Karşılaştırılan Görsel 2 ({secure_name2})",  # YENİ: secure_name2
                    "image_data_b64": image2_full_b64,
                    "face_cropped_b64": face2_cropped_b64,
                    "image_url": None,
                    "source_url": "Yüklenen Dosya",
                    "hash": "N/A",
                    "count": 1,
                    "score": results.get("face2", {}).get("det_score"),
                    "gender": (
                        "Erkek"
                        if results.get("face2", {}).get("gender") == 1
                        else (
                            "Kadın"
                            if results.get("face2", {}).get("gender") == 0
                            else "N/A"
                        )
                    ),
                    "age": results.get("face2", {}).get("age"),
                    "similarity": None,
                    "comprehensive_info": None,
                    "facebox": results.get("face2", {}).get("bbox"),
                }
                pdf_data = [pdf_item1, pdf_item2]

                # Prepare comparison info for PDF header/intro
                comparison_info_for_pdf = {
                    "message": results.get("message", "Sonuç mesajı yok."),
                    "score": results.get("score", None),  # Similarity score
                    "threshold": threshold,
                }

                # Store data in session
                username = session.get("username", "Bilinmeyen Kullanıcı")
                session["last_comparison_report_data"] = {
                    "search_type": f"Yüz Karşılaştırma (Eşik: {threshold})",
                    "username": username,
                    "pdf_data": pdf_data,
                    "comparison_info": comparison_info_for_pdf,
                }
                report_available = True
            # --- PDF Hazırlama Bitti ---

            # Şablonu render et
            return render_template(
                "face_comparison.html",
                results=results,
                message=message,
                report_available=report_available,
            )  # Pass the flag
        except Exception as e:
            flash(f"Görsel işlenirken hata oluştu: {str(e)}", "danger")
            current_app.logger.error(
                f"Yüz karşılaştırma hatası: {str(e)}\n{traceback.format_exc()}"
            )
            return redirect(request.url)

    # GET isteği - Form sayfasını göster
    return render_template("face_comparison.html", report_available=report_available)


@web_bp.route("/search/text", methods=["GET", "POST"])
@login_required
@limiter.limit("30/minute")
def text_search():
    """Metin tabanlı arama sayfası - görsel başlıklarında Türkçe metin araması yapar"""
    if request.method == "POST":
        # Form verilerini al
        search_text = request.form.get("search_text", "").strip()
        start_date = request.form.get("start_date", "")
        end_date = request.form.get("end_date", "")
        category = request.form.get("category", "")

        # Arama metni gerekli
        if not search_text:
            flash("Arama metni girmeniz gerekli", "warning")
            return redirect(url_for("web.text_search"))

        # Arama işlemini gerçekleştir
        success, message, results = SearchController.search_by_text(
            search_text=search_text,
            start_date=start_date,
            end_date=end_date,
            category=category,
        )

        # Sonuçları göster
        if not success:
            flash(f"Arama sırasında hata oluştu: {message}", "danger")
            return redirect(url_for("web.text_search"))

        return render_template(
            "text_search_results.html",
            results=results,
            params={
                "search_text": search_text,
                "start_date": start_date,
                "end_date": end_date,
                "category": category,
            },
        )

    # GET isteği - Form verilerini hazırla
    try:
        # Kategorileri al
        _, _, categories = SearchController.get_categories()

        return render_template("text_search.html", categories=categories)
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Hata detayları: {error_details}")
        flash(f"Form bilgileri yüklenirken hata oluştu: {str(e)}", "danger")
        return render_template("text_search.html", categories=[])


@web_bp.route("/fetch_domain_faces", methods=["POST"])
@login_required
@limiter.limit("30/minute")
def fetch_domain_faces():
    """Face ID için yüz kutucuğunu ve ilgili görsel verilerini getirir"""
    domain = request.form.get("domain", "")
    face_id = request.form.get("face_id", "")

    if not face_id:
        return jsonify(
            {"success": False, "message": "Face ID parametresi gerekli", "faces": []}
        )

    try:
        # Face ID'yi tamsayıya dönüştür
        try:
            face_id_int = int(face_id)
        except ValueError:
            return jsonify(
                {
                    "success": False,
                    "message": f"Geçersiz Face ID formatı: {face_id}",
                    "faces": [],
                }
            )

        # Veritabanı bağlantısı
        conn = g.db_tools.connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # 1. Adım: EyeOfWebFaceID tablosundan face box verilerini al
        face_query = """
        SELECT f."ID" as face_id, f."FaceBox" as facebox
        FROM "EyeOfWebFaceID" f
        WHERE f."ID" = %s
        """

        cursor.execute(face_query, [face_id_int])
        face_result = cursor.fetchone()

        if not face_result:
            g.db_tools.releaseConnection(conn, cursor)
            return jsonify(
                {
                    "success": False,
                    "message": f"Face ID bulunamadı: {face_id}",
                    "faces": [],
                }
            )

        # Face Box verisi
        facebox = face_result["facebox"]

        # 2. Adım: ImageBasedMain tablosundan face_id'yi içeren kayıtları bul
        # Tüm URL bileşenlerini alacağız
        main_query = """
        SELECT 
            im."ImageProtocol", 
            im."ImageID",
            iup."Path" as image_path,
            iue."Etc" as image_url_etc,
            it."Title" as image_title,
            bd."Domain" as domain,
            img_bd."Domain" as image_domain
        FROM "ImageBasedMain" im
        JOIN "BaseDomainID" bd ON im."BaseDomainID" = bd."ID"
        LEFT JOIN "BaseDomainID" img_bd ON im."ImageDomainID" = img_bd."ID"
        LEFT JOIN "ImageUrlPathID" iup ON im."ImagePathID" = iup."ID"
        LEFT JOIN "ImageUrlEtcID" iue ON im."ImageUrlEtcID" = iue."ID"
        LEFT JOIN "ImageTitleID" it ON im."ImageTitleID" = it."ID"
        WHERE %s = ANY(im."FaceID")
        """

        if domain:
            main_query += ' AND bd."Domain" = %s'
            cursor.execute(main_query, [face_id_int, domain])
        else:
            cursor.execute(main_query, [face_id_int])

        main_result = cursor.fetchone()

        if not main_result:
            g.db_tools.releaseConnection(conn, cursor)
            return jsonify(
                {
                    "success": False,
                    "message": f"Face ID için ilişkili ImageBasedMain kaydı bulunamadı: {face_id}",
                    "faces": [],
                }
            )

        # 3. Adım: URL bileşenlerinden tam URL oluştur
        image_protocol = main_result["ImageProtocol"] or "http"
        image_domain = main_result["image_domain"] or ""
        image_path = main_result["image_path"] or ""
        image_url_etc = main_result["image_url_etc"] or ""
        image_title = main_result["image_title"] or ""

        # URL oluştur - Eğer etc varsa soru işareti ekle, yoksa ekleme
        image_url = build_image_url(
            image_protocol, image_domain, image_path, image_url_etc
        )

        domain = main_result["domain"]

        if not image_url:
            g.db_tools.releaseConnection(conn, cursor)
            return jsonify(
                {
                    "success": False,
                    "message": f"Görsel URL oluşturulamadı (Domain: {image_domain}, Path: {image_path})",
                    "faces": [],
                }
            )

        # Facebox verisi
        facebox_data = np.array(
            ast.literal_eval(facebox), dtype=np.float32
        ).tolist()  # JSON için listeye çevir

        # Sonuç
        face_data = {
            "face_id": face_id_int,
            "domain": domain,
            "original_image_url": image_url,  # Orijinal URL
            "image_title": image_title,
            "facebox": facebox_data,  # Facebox koordinatları
        }

        g.db_tools.releaseConnection(conn, cursor)

        return jsonify(
            {"success": True, "message": "Yüz verisi bulundu", "faces": [face_data]}
        )

    except Exception as e:
        current_app.logger.error(f"Yüz verisi alınırken hata: {str(e)}")
        return jsonify(
            {"success": False, "message": f"Hata oluştu: {str(e)}", "faces": []}
        )


@web_bp.route("/deep_insight/<face_id>", methods=["GET"])
@login_required
@limiter.limit("10/minute")
def deep_insight(face_id):
    """
    Deep Insight özelliği - Bir yüzün en çok hangi diğer yüzlerle beraber olduğunu analiz eder
    Bu analiz, sosyal ilişkileri ortaya çıkarmak için kullanılabilir
    """
    try:
        # Check if this is a default entry from the menu (face_id = 0)
        if face_id == "0":
            flash("Lütfen birliktelik analizi yapmak için bir yüz seçiniz.", "info")
            return redirect(url_for("web.search", analysis=True))

        # Validate and convert face_id to integer
        try:
            face_id = int(face_id)
        except ValueError:
            flash(f"Geçersiz Face ID formatı: {face_id}", "danger")
            return redirect(url_for("web.index"))

        # Seçilen yüzün bilgilerini getir
        success, message, face_details = SearchController.get_face_details(face_id)

        if not success:
            flash(f"Yüz bilgileri alınamadı: {message}", "danger")
            return redirect(url_for("web.index"))

        # Veritabanı bağlantısı
        conn = g.db_tools.connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # 1. Bu yüzün bulunduğu tüm görselleri bul
        images_query = """
        SELECT 
            im."ImageID",
            im."FaceID" as faces_in_image
        FROM "ImageBasedMain" im
        WHERE %s = ANY(im."FaceID")
        """

        cursor.execute(images_query, [face_id])
        image_results = cursor.fetchall()

        if not image_results:
            g.db_tools.releaseConnection(conn, cursor)
            flash(f"Bu yüzün bulunduğu görsel bulunamadı.", "warning")
            return render_template(
                "deep_insight.html", face=face_details, relationships=[], stats={}
            )

        # 2. Bu yüzle birlikte görülen diğer yüzleri bul ve say
        face_counter = Counter()
        image_count = 0
        face_co_occurrence_details = {}

        for image_result in image_results:
            image_count += 1
            faces_in_image = image_result["faces_in_image"]

            # Hedef yüz dışındaki yüzleri say
            for other_face_id in faces_in_image:
                if other_face_id != face_id:
                    face_counter[other_face_id] += 1

                    # Bu yüzün detaylarını sakla (eğer henüz yapılmadıysa)
                    if other_face_id not in face_co_occurrence_details:
                        # Bu yüzün bulunduğu görsellerden birini bul
                        face_query = """
                        SELECT 
                            f."ID" as face_id,
                            f."FaceGender" as gender,
                            f."FaceAge" as age,
                            f."DetectionScore" as score,
                            m."RiskLevel" as risk_level,
                            m."ImageID" as image_id,
                            m."ImageProtocol" as protocol,
                            bd."Domain" as domain,
                            iup."Path" as path,
                            iue."Etc" as url_etc,
                            f."FaceBox" as facebox
                        FROM "EyeOfWebFaceID" f
                        JOIN "ImageBasedMain" m ON f."ID" = ANY(m."FaceID")
                        JOIN "BaseDomainID" bd ON m."BaseDomainID" = bd."ID"
                        LEFT JOIN "ImageUrlPathID" iup ON m."ImagePathID" = iup."ID"
                        LEFT JOIN "ImageUrlEtcID" iue ON m."ImageUrlEtcID" = iue."ID"
                        WHERE f."ID" = %s
                        LIMIT 1
                        """

                        cursor.execute(face_query, [other_face_id])
                        face_result = cursor.fetchone()

                        if face_result:
                            # URL oluştur
                            image_url = build_image_url(
                                face_result["protocol"],
                                face_result["domain"],
                                face_result["path"],
                                face_result["url_etc"],
                            )

                            # Yüz detaylarını sakla
                            face_co_occurrence_details[other_face_id] = {
                                "face_id": other_face_id,
                                "gender": face_result["gender"],
                                "age": face_result["age"],
                                "score": face_result["score"],
                                "risk_level": face_result["risk_level"],
                                "original_image_url": image_url,
                                "domain": face_result["domain"],
                                "facebox": (
                                    np.array(
                                        ast.literal_eval(face_result["facebox"]),
                                        dtype=np.float32,
                                    ).tolist()
                                    if face_result["facebox"]
                                    else None
                                ),
                            }

        # En sık görülen 10 yüzü al
        most_common_faces = face_counter.most_common(10)

        # Sonuçları hazırla
        relationships = []

        for other_face_id, count in most_common_faces:
            if other_face_id in face_co_occurrence_details:
                face_info = face_co_occurrence_details[other_face_id]
                face_info["count"] = count
                face_info["percentage"] = round((count / image_count) * 100, 1)
                # image_data artık kullanılmıyor, facebox ve original_image_url gönderiliyor
                relationships.append(face_info)

        # İstatistikleri hesapla
        stats = {
            "total_images": image_count,
            "unique_faces": len(face_counter),
            "top_face_count": most_common_faces[0][1] if most_common_faces else 0,
            "top_face_id": most_common_faces[0][0] if most_common_faces else None,
        }

        g.db_tools.releaseConnection(conn, cursor)

        # Şablonu render et
        return render_template(
            "deep_insight.html",
            face=face_details,
            relationships=relationships,
            stats=stats,
        )

    except Exception as e:
        current_app.logger.error(f"Deep Insight analizi sırasında hata: {str(e)}")
        flash(f"Deep Insight analizi sırasında bir hata oluştu: {str(e)}", "danger")
        return redirect(url_for("web.index"))


@web_bp.route("/face_similarity_analysis/<face_id>", methods=["GET"])
@login_required
@limiter.limit("10 per minute")
def face_similarity_analysis(face_id):
    """
    Yüz benzerlik ve birliktelik analizi:
    - Hedef yüzün bulunduğu tüm görselleri bulur.
    - Bu görsellerdeki tüm yüz çiftlerinin benzerliğini hesaplar.
    - Belirli bir eşiği geçen ve birden fazla görselde birlikte görünen çiftleri listeler.
    """
    conn = None
    try:
        # Check if this is a default entry from the menu (face_id = 0)
        if face_id == "0":
            flash("Lütfen detaylı ilişki analizi yapmak için bir yüz seçiniz.", "info")
            return redirect(url_for("web.search", analysis=True))

        # Get similarity threshold from request arguments, default to 0.6
        similarity_threshold = float(request.args.get("threshold", 0.6))
        min_cooccurrence = int(
            request.args.get("min_cooccurrence", 2)
        )  # Min. birlikte görünme sayısı

        current_app.logger.debug(
            f"Benzerlik analizi başlıyor: Eşik={similarity_threshold}, Min. Birliktelik={min_cooccurrence}"
        )

        try:
            target_face_id = int(face_id)
        except ValueError:
            flash(f"Geçersiz Face ID formatı: {face_id}", "danger")
            return redirect(url_for("web.index"))

        # Hedef yüz bilgilerini al (şablonda göstermek için)
        success, message, target_face_details = SearchController.get_face_details(
            target_face_id
        )
        if not success:
            current_app.logger.warning(
                f"Hedef yüz detayları alınamadı (ID: {target_face_id}): {message}"
            )
            target_face_details = {"id": target_face_id}

        conn = g.db_tools.connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # 1. Hedef yüzün bulunduğu tüm görselleri ve içerdikleri yüzleri bul
        images_query = """
        SELECT im."ImageID", im."FaceID" as faces_in_image
        FROM "ImageBasedMain" im WHERE %s = ANY(im."FaceID")
        """
        cursor.execute(images_query, [target_face_id])
        image_results = cursor.fetchall()

        if not image_results:
            g.db_tools.releaseConnection(conn, cursor)
            flash(
                f"Hedef yüzün (ID: {target_face_id}) bulunduğu görsel bulunamadı.",
                "warning",
            )
            return render_template(
                "face_similarity_pairs.html",
                target_face=target_face_details,
                related_pairs=[],
                stats={
                    "threshold": similarity_threshold,
                    "min_cooccurrence": min_cooccurrence,
                },
            )

        # 2. Bu görsellerdeki tüm benzersiz yüzleri topla
        all_face_ids_in_related_images = set()
        image_face_map = {}  # image_id -> set(face_ids)
        for img_res in image_results:
            faces = set(img_res["faces_in_image"])
            image_face_map[img_res["ImageID"]] = faces
            all_face_ids_in_related_images.update(faces)

        current_app.logger.info(
            f"Analiz edilecek toplam {len(all_face_ids_in_related_images)} ilişkili yüz bulundu."
        )

        # 3. Tüm ilişkili yüzlerin embedding ve temel detaylarını al
        face_embeddings = {}
        face_details_cache = {}
        if all_face_ids_in_related_images:
            query_placeholders = ",".join(["%s"] * len(all_face_ids_in_related_images))
            details_query = f"""
            SELECT f."ID", f."FaceEmbeddingData", f."FaceGender", f."FaceAge"
            FROM "EyeOfWebFaceID" f WHERE f."ID" IN ({query_placeholders})
            """
            cursor.execute(details_query, list(all_face_ids_in_related_images))
            face_data_batch = cursor.fetchall()

            for face_data in face_data_batch:
                face_id = face_data["ID"]
                if face_data["FaceEmbeddingData"]:
                    try:
                        embedding = np.array(
                            ast.literal_eval(face_data["FaceEmbeddingData"]),
                            dtype=np.float32,
                        )
                        if embedding.size == 512:
                            face_embeddings[face_id] = embedding
                            face_details_cache[face_id] = {
                                "id": face_id,
                                "gender": (
                                    "Erkek" if face_data["FaceGender"] else "Kadın"
                                ),
                                "age": face_data["FaceAge"],
                            }
                        else:
                            current_app.logger.warning(
                                f"Yüz ID {face_id} için beklenmeyen embedding boyutu: {embedding.size}"
                            )
                    except Exception as emb_err:
                        current_app.logger.error(
                            f"Yüz ID {face_id} için embedding parse hatası: {emb_err}"
                        )
                else:
                    current_app.logger.warning(
                        f"Yüz ID {face_id} için embedding verisi bulunamadı."
                    )

        # 4. İlişkili yüz çiftlerinin benzerliğini hesapla
        face_pairs_above_threshold = {}
        valid_face_ids = list(face_embeddings.keys())
        total_combinations = len(list(itertools.combinations(valid_face_ids, 2)))
        current_app.logger.info(
            f"Hesaplanacak toplam ilişkili yüz çifti: {total_combinations}"
        )
        processed_combinations = 0

        for face_id1, face_id2 in itertools.combinations(valid_face_ids, 2):
            embedding1 = face_embeddings[face_id1]
            embedding2 = face_embeddings[face_id2]

            similarity = np.dot(embedding1, embedding2) / (
                np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
            )
            processed_combinations += 1
            if processed_combinations % 1000 == 0:
                current_app.logger.debug(
                    f"{processed_combinations}/{total_combinations} çift işlendi."
                )

            if similarity >= similarity_threshold:
                ordered_pair = tuple(sorted((face_id1, face_id2)))
                face_pairs_above_threshold[ordered_pair] = float(similarity)

        current_app.logger.info(
            f"Eşik ({similarity_threshold}) üzerinde {len(face_pairs_above_threshold)} ilişkili yüz çifti bulundu."
        )

        # 5. Eşiği geçen çiftlerin birlikte görünme sayısını hesapla
        pair_co_occurrence_count = Counter()
        for image_id, faces_in_this_image in image_face_map.items():
            valid_faces_in_image = faces_in_this_image.intersection(valid_face_ids)
            for face_id1, face_id2 in itertools.combinations(valid_faces_in_image, 2):
                ordered_pair = tuple(sorted((face_id1, face_id2)))
                if ordered_pair in face_pairs_above_threshold:
                    pair_co_occurrence_count[ordered_pair] += 1

        # 6. Sonuçları filtrele ve detayları ekle (URL ve Facebox için)
        final_related_pairs = []
        face_ids_to_fetch_details_for = set()
        for pair, count in pair_co_occurrence_count.items():
            if count >= min_cooccurrence:
                face_ids_to_fetch_details_for.update(pair)
                final_related_pairs.append(
                    {
                        "pair": pair,
                        "similarity": face_pairs_above_threshold[pair],
                        "co_occurrence_count": count,
                    }
                )

        # Toplu olarak ek detayları (URL bileşenleri ve FaceBox) al
        face_display_details = {}
        if face_ids_to_fetch_details_for:
            query_placeholders = ",".join(["%s"] * len(face_ids_to_fetch_details_for))
            details_query = f"""
                SELECT DISTINCT ON (f."ID") -- Her yüz için sadece bir satır al (ilk bulunan)
                    f."ID" as face_id,
                    f."FaceBox",
                    m."ImageProtocol",
                    bd_img."Domain" as image_domain,
                    im_path."Path" as image_path,
                    im_etc."Etc" as image_etc
                FROM "EyeOfWebFaceID" f
                JOIN "ImageBasedMain" m ON f."ID" = ANY(m."FaceID")
                LEFT JOIN "BaseDomainID" bd_img ON m."ImageDomainID" = bd_img."ID"
                LEFT JOIN "ImageUrlPathID" im_path ON m."ImagePathID" = im_path."ID"
                LEFT JOIN "ImageUrlEtcID" im_etc ON m."ImageUrlEtcID" = im_etc."ID"
                WHERE f."ID" IN ({query_placeholders})
            """
            cursor.execute(details_query, list(face_ids_to_fetch_details_for))
            detail_results = cursor.fetchall()

            # Detayları işle
            for row in detail_results:
                face_id = row["face_id"]
                original_url = build_image_url(
                    row["ImageProtocol"],
                    row["image_domain"],
                    row["image_path"],
                    row["image_etc"],
                )
                facebox = (
                    np.array(
                        ast.literal_eval(row["FaceBox"]), dtype=np.float32
                    ).tolist()
                    if row["FaceBox"]
                    else None
                )
                face_display_details[face_id] = {
                    "original_image_url": original_url,
                    "facebox": facebox,
                }

        # Sonuç listesini doldur
        for pair_info in final_related_pairs:
            face1_id, face2_id = pair_info["pair"]
            pair_info["face1"] = face_details_cache.get(face1_id, {"id": face1_id})
            pair_info["face2"] = face_details_cache.get(face2_id, {"id": face2_id})
            pair_info["face1"].update(face_display_details.get(face1_id, {}))
            pair_info["face2"].update(face_display_details.get(face2_id, {}))

        # 7. Sonuçları Sırala
        final_related_pairs.sort(
            key=lambda x: (x["co_occurrence_count"], x["similarity"]), reverse=True
        )

        # İstatistikler
        stats = {
            "total_images": len(image_results),
            "total_unique_faces": len(all_face_ids_in_related_images),
            "faces_with_embedding": len(valid_face_ids),
            "pairs_above_threshold": len(face_pairs_above_threshold),
            "final_related_pairs": len(final_related_pairs),
            "threshold": similarity_threshold,
            "min_cooccurrence": min_cooccurrence,
        }

        g.db_tools.releaseConnection(conn, cursor)
        current_app.logger.info(
            f"Yüz {target_face_id} için detaylı ilişki analizi tamamlandı. {len(final_related_pairs)} ilişkili çift bulundu."
        )

        # 8. Şablonu Render Et
        return render_template(
            "face_similarity_pairs.html",
            target_face=target_face_details,
            related_pairs=final_related_pairs,
            stats=stats,
        )

    except Exception as e:
        # Hata durumunda bağlantıyı kapatmayı unutma
        if conn:
            g.db_tools.releaseConnection(conn, cursor if "cursor" in locals() else None)
        current_app.logger.error(
            f"Yüz benzerlik analizi (ID: {face_id}) sırasında hata: {traceback.format_exc()}"
        )
        flash(f"Benzerlik analizi sırasında bir hata oluştu: {str(e)}", "danger")
        return redirect(url_for("web.index"))


@web_bp.route("/extended_face_analysis/<face_id>", methods=["GET"])
@login_required
@limiter.limit("10 per minute")
def extended_face_analysis(face_id):
    """
    Extended Face Analysis - treats all faces similar to the target face as the same person,
    then analyzes all images containing any of these faces to find relationships.
    DEPRECATED? Bu fonksiyonun işlevselliği comprehensive_person_analysis'a benziyor.
    """
    # Bu fonksiyonun içeriği comprehensive_person_analysis ile çok benzer ve
    # tablo isimleri ("Faces", "ImageData" vb.) güncel şemayla uyumsuz görünüyor.
    # Bu nedenle bu fonksiyonu şimdilik devre dışı bırakmak veya
    # comprehensive_person_analysis'a yönlendirmek daha doğru olabilir.
    flash(
        "Bu analiz aracı güncellenmektedir. Lütfen Kapsamlı Kişi Analizi\\'ni kullanın.",
        "info",
    )
    return redirect(url_for("web.comprehensive_person_analysis", face_id=face_id))


@web_bp.route("/comprehensive_person_analysis/<face_id>", methods=["GET"])
@login_required
@limiter.limit("10 per minute")
def comprehensive_person_analysis(face_id):
    """
    Kapsamlı Kişi Analizi:
    1. Hedef yüze benzer yüzleri bulur (aynı kişi kabul edilir) - MILVUS Entegrasyonu
    2. Bu kişinin bulunduğu tüm görselleri bulur (hash bazlı tekilleştirme)
    3. Bu görsellerdeki diğer yüzleri gruplar (benzerlik >= threshold olanları aynı kişi sayar)
    4. Her grup için hedef kişiyle kaç kez görüldüğünü hesaplar
    """
    conn = None
    cur = None
    target_milvus_data = None
    try:
        start_time = datetime.datetime.now()
        current_app.logger.info(f"Kapsamlı kişi analizi başlatıldı: Face ID {face_id}")

        if face_id == "0":
            flash("Lütfen kapsamlı analiz yapmak için bir yüz seçiniz.", "info")
            return redirect(url_for("web.search", analysis=True))

        similarity_threshold = float(request.args.get("threshold", 0.45))
        distance_threshold = 1 - similarity_threshold

        try:
            target_face_id = int(face_id)
        except ValueError:
            flash("Geçersiz yüz ID formatı", "error")
            return redirect(url_for("web.dashboard"))

        conn = g.db_tools.connect()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # 1. Hedef yüzün temel PostgreSQL bilgilerini (ID, örnek görsel ID) al
        # FaceEmbeddingData ve FaceBox buradan ÇIKARILDI!
        cur.execute(
            """ 
            SELECT f."ID", m."ImageID"
            FROM "EyeOfWebFaceID" f
            JOIN "ImageBasedMain" m ON f."ID" = ANY(m."FaceID")
            WHERE f."ID" = %s
            ORDER BY m."DetectionDate" DESC
            LIMIT 1
        """,
            (target_face_id,),
        )
        target_face_pg_info = cur.fetchone()

        if not target_face_pg_info:
            flash(
                f"Hedef yüz (ID: {target_face_id}) PostgreSQL'de bulunamadı.", "error"
            )
            if conn:
                g.db_tools.releaseConnection(conn, cur)
            return redirect(url_for("web.dashboard"))

        # target_face_id zaten elimizde, pg_info sadece ImageID için kullanıldı.
        target_image_id = target_face_pg_info.get("ImageID")

        # 2. Hedef yüzün Milvus verilerini (embedding, face_box vb.) al
        try:
            # Varsayım: g.db_tools.get_milvus_face_attributes(collection_name, face_id) -> dict
            # Dönen dict içinde 'face_embedding_data' (list/np.array) ve 'face_box' (list/np.array) olmalı.
            target_milvus_data = g.db_tools.get_milvus_face_attributes(
                EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME, target_face_id
            )
            if (
                not target_milvus_data
                or "face_embedding_data" not in target_milvus_data
            ):
                flash(
                    f"Hedef yüz (ID: {target_face_id}) için Milvus'ta embedding verisi bulunamadı.",
                    "error",
                )
                if conn:
                    g.db_tools.releaseConnection(conn, cur)
                return redirect(url_for("web.dashboard"))

            target_embedding_list = target_milvus_data["face_embedding_data"]
            if isinstance(target_embedding_list, str):
                target_embedding_list = ast.literal_eval(target_embedding_list)
            target_embedding = np.array(target_embedding_list, dtype=np.float32)

            if target_embedding.size != 512:
                raise ValueError(
                    f"Milvus'tan gelen beklenmeyen embedding boyutu: {target_embedding.size}"
                )

        except AttributeError as attr_err:
            current_app.logger.error(
                f"Milvus veri getirme fonksiyonu g.db_tools'da bulunamadı: {attr_err}"
            )
            flash(
                "Milvus altyapısında bir sorun var (get_milvus_face_attributes). Lütfen yönetici ile iletişime geçin.",
                "error",
            )
            if conn:
                g.db_tools.releaseConnection(conn, cur)
            return redirect(url_for("web.dashboard"))
        except Exception as milvus_fetch_err:
            current_app.logger.error(
                f"Hedef yüz ({target_face_id}) Milvus veri getirme hatası: {milvus_fetch_err}\\{traceback.format_exc()}"
            )
            flash(
                f"Hedef yüz için Milvus'tan veri alınırken hata: {str(milvus_fetch_err)}",
                "error",
            )
            if conn:
                g.db_tools.releaseConnection(conn, cur)
            return redirect(url_for("web.dashboard"))

        target_face_image_data = None
        target_face_mime_type = None
        if target_image_id:
            success_img, img_binary = g.db_tools.getImageBinaryByID(target_image_id)
            if success_img and img_binary:
                try:
                    decompressed_binary = decompress_image(img_binary)
                    if decompressed_binary:
                        target_face_image_data = base64.b64encode(
                            decompressed_binary
                        ).decode("utf-8")
                        target_face_mime_type = "image/png"
                    else:
                        current_app.logger.warning(
                            f"Hedef yüz ({target_face_id}) için dekompresyon boş veri döndürdü."
                        )
                except Exception as encode_err:
                    current_app.logger.error(
                        f"Hedef yüz ({target_face_id}) resim dekompres/encode hatası: {encode_err}"
                    )

        # 3. Hedef yüze benzer yüzleri bul (Milvus kullanarak)
        current_app.logger.info(
            f"Hedef yüze ({target_face_id}) benzer yüzler Milvus ile aranıyor (mesafe < {distance_threshold:.4f})..."
        )

        target_group_ids = {target_face_id}
        try:
            similar_face_ids_from_milvus = g.db_tools.find_similar_face_ids_in_milvus(
                collection_name=EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME,
                target_vector=target_embedding.tolist(),
                distance_threshold=distance_threshold,
                exclude_id=target_face_id,
                limit=200,  # Hedef kişinin tüm benzerlerini bulmak için yüksek limit (kullanıcı talebi)
            )
            if similar_face_ids_from_milvus:
                target_group_ids.update(similar_face_ids_from_milvus)
            current_app.logger.info(
                f"Milvus'tan hedef yüz grubu bulundu: {len(target_group_ids)} yüz (ID: {target_face_id} dahil). Bu kişinin tüm görüntüleri analiz edilecek."
            )

        except AttributeError as attr_err:
            current_app.logger.error(
                f"Milvus arama fonksiyonu g.db_tools'da bulunamadı: {attr_err}"
            )
            flash(
                "Milvus arama altyapısında bir sorun var (find_similar_face_ids_in_milvus). Lütfen yönetici ile iletişime geçin.",
                "error",
            )
            if conn:
                g.db_tools.releaseConnection(conn, cur)
            return redirect(url_for("web.dashboard"))
        except Exception as milvus_err:
            current_app.logger.error(
                f"Milvus arama sırasında genel hata: {milvus_err}\\{traceback.format_exc()}"
            )
            flash(
                f"Milvus ile benzer yüzler aranırken bir hata oluştu: {str(milvus_err)}",
                "error",
            )
            if conn:
                g.db_tools.releaseConnection(conn, cur)
            return redirect(url_for("web.dashboard"))

        avg_similarity = 0.0

        # 4. Bu yüzlerin bulunduğu tüm görselleri (PostgreSQL'den) bul
        current_app.logger.info(
            f"Hedef kişinin bulunduğu TÜM görselleri bulma aşaması başlıyor..."
        )
        target_images_query = """ 
        SELECT DISTINCT m."ImageID", m."FaceID", ih."ImageHash"
        FROM "ImageBasedMain" m
        JOIN "ImageHashID" ih ON m."HashID" = ih."ID"
        WHERE EXISTS (
            SELECT 1 FROM unnest(m."FaceID") face_id_unnest
            WHERE face_id_unnest = ANY(%s)
        )
        """
        cur.execute(target_images_query, (list(target_group_ids),))
        target_images = cur.fetchall()
        current_app.logger.info(
            f"Hedef grup yüzlerini içeren {len(target_images)} potansiyel görsel kaydı bulundu. Bu görüntülerde yer alan tüm kişiler için birlikte görülme analizi yapılacak."
        )

        # 5. Bu görsellerdeki tüm yüzleri topla (Hash'e göre tekilleştir)
        all_related_face_ids = set()
        image_hash_map = {}
        for img in target_images:
            img_hash = img.get("ImageHash")
            if not img_hash:
                continue
            if img_hash not in image_hash_map:
                image_hash_map[img_hash] = {
                    "image_id": img.get("ImageID"),
                    "faces": set(),
                }
            if img.get("FaceID"):
                image_hash_map[img_hash]["faces"].update(img["FaceID"])

        for img_hash, data in image_hash_map.items():
            all_related_face_ids.update(data["faces"])
        current_app.logger.info(
            f"Tekilleştirilmiş {len(image_hash_map)} görseldeki toplam yüz sayısı: {len(all_related_face_ids)}"
        )

        related_face_ids_to_group = all_related_face_ids - target_group_ids
        current_app.logger.info(
            f"Hedef grup dışındaki gruplanacak ilişkili yüz sayısı: {len(related_face_ids_to_group)}"
        )

        # 6. İlişkili yüzlerin embedding'lerini Milvus'tan al (Gruplama için)
        related_faces_milvus_data_for_grouping = []
        if related_face_ids_to_group:
            current_app.logger.info(
                f"Gruplama için {len(related_face_ids_to_group)} ilişkili yüzün Milvus verileri çekiliyor..."
            )
            # Toplu Milvus veri çekme (optimizasyon)
            batch_start_time = datetime.datetime.now()
            batch_milvus_data = g.db_tools.get_batch_milvus_face_attributes(
                collection_name=EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME,
                pg_face_ids=list(related_face_ids_to_group),
            )
            batch_end_time = datetime.datetime.now()
            current_app.logger.info(
                f"Toplu Milvus veri çekme tamamlandı. Süre: {batch_end_time - batch_start_time}. "
                f"{len(batch_milvus_data)}/{len(related_face_ids_to_group)} yüz verisi alındı."
            )

            # Alınan verileri işle
            for face_id, milvus_attrs in batch_milvus_data.items():
                if "face_embedding_data" in milvus_attrs:
                    emb_list = milvus_attrs["face_embedding_data"]
                    if isinstance(emb_list, str):
                        emb_list = ast.literal_eval(emb_list)
                    emb_vector = np.array(emb_list, dtype=np.float32)
                    if emb_vector.size == 512:
                        related_faces_milvus_data_for_grouping.append(
                            {"ID": face_id, "embedding_vector": emb_vector}
                        )
                    else:
                        current_app.logger.warning(
                            f"Gruplama için yüz {face_id} Milvus embedding boyutu geçersiz ({emb_vector.size}). Atlanıyor."
                        )
                else:
                    current_app.logger.warning(
                        f"Gruplama için yüz {face_id} Milvus embedding verisi bulunamadı. Atlanıyor."
                    )
        current_app.logger.info(
            f"Gruplama için {len(related_faces_milvus_data_for_grouping)} adet ilişkili yüzün Milvus embedding verisi başarıyla çekildi."
        )

        # 7. İlişkili yüzleri grupla (Python tabanlı, Milvus embeddinglerini kullanarak)
        face_groups = {}
        face_to_group = {}
        next_group_id = 0
        processed_count_grouping = 0

        start_grouping_time = datetime.datetime.now()
        current_app.logger.info(
            f"İlişkili yüz gruplama işlemi başlıyor. Toplam {len(related_faces_milvus_data_for_grouping)} yüz için gruplama yapılacak..."
        )
        for i, face1_data in enumerate(related_faces_milvus_data_for_grouping):
            face1_id = face1_data["ID"]
            if face1_id in face_to_group:
                continue

            face1_embedding = face1_data["embedding_vector"]

            current_group = {face1_id}
            face_groups[next_group_id] = current_group
            face_to_group[face1_id] = next_group_id

            for face2_data in related_faces_milvus_data_for_grouping[i + 1 :]:
                face2_id = face2_data["ID"]
                if face2_id in face_to_group:
                    continue

                face2_embedding = face2_data["embedding_vector"]

                try:
                    similarity = np.dot(face1_embedding, face2_embedding) / (
                        np.linalg.norm(face1_embedding)
                        * np.linalg.norm(face2_embedding)
                    )
                    processed_count_grouping += 1
                    if similarity >= similarity_threshold:
                        current_group.add(face2_id)
                        face_to_group[face2_id] = next_group_id
                except Exception as e:
                    current_app.logger.error(
                        f"Grup benzerlik hesaplama hatası ({face1_id}-{face2_id}): {e}"
                    )
            next_group_id += 1

        end_grouping_time = datetime.datetime.now()
        current_app.logger.info(
            f"İlişkili yüz gruplama tamamlandı. {next_group_id} grup oluşturuldu. Süre: {end_grouping_time - start_grouping_time}. Toplam {processed_count_grouping} karşılaştırma yapıldı."
        )

        # 8. Her grup için hedef kişiyle görülme sayısını hesapla (Hash bazlı)
        group_occurrences = defaultdict(int)
        current_app.logger.info(
            "Grup-hedef birliktelik sayısı hesaplanıyor: Hangi kişi grubu, hedef kişi ile kaç kez aynı fotoğrafta görülmüş..."
        )
        for img_hash, data in image_hash_map.items():
            current_faces = data["faces"]
            if any(
                face_id_check in target_group_ids for face_id_check in current_faces
            ):
                processed_groups_in_image = set()
                for face_id_in_img in current_faces:
                    if face_id_in_img in face_to_group:
                        group_id = face_to_group[face_id_in_img]
                        if group_id not in processed_groups_in_image:
                            group_occurrences[group_id] += 1
                            processed_groups_in_image.add(group_id)
        current_app.logger.info(
            f"{len(group_occurrences)} farklı ilişkili kişi/grup, hedef kişi ile en az bir kez birlikte görüldü. Bu sonuçlar analiz için kullanılacak."
        )

        # 9. Sonuçları hazırla
        final_related_faces = []
        current_app.logger.info(
            "Sonuçlar için detaylar (temsilci yüz, görsel vb.) çekiliyor..."
        )
        # Temsilci yüzleri belirle ve toplu şekilde al
        representative_face_ids = []
        group_to_representative = {}

        for group_id, occurrence_count in group_occurrences.items():
            if group_id not in face_groups or not face_groups[group_id]:
                current_app.logger.warning(
                    f"Grup {group_id} geçersiz veya boş! Atlanıyor."
                )
                continue
            representative_face_id = next(iter(face_groups[group_id]))
            representative_face_ids.append(representative_face_id)
            group_to_representative[group_id] = representative_face_id

        # Temsilci yüzler için toplu Milvus verisi çek
        rep_start_time = datetime.datetime.now()
        rep_milvus_data_batch = {}
        if representative_face_ids:
            rep_milvus_data_batch = g.db_tools.get_batch_milvus_face_attributes(
                collection_name=EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME,
                pg_face_ids=representative_face_ids,
            )
        rep_end_time = datetime.datetime.now()
        current_app.logger.info(
            f"Temsilci yüzler için toplu Milvus verisi çekildi. Süre: {rep_end_time - rep_start_time}. "
            f"{len(rep_milvus_data_batch)}/{len(representative_face_ids)} temsilci yüz verisi alındı."
        )

        # Temsilci yüzlerin PostgreSQL verilerini al (toplu SQL)
        pg_details_map = {}
        if representative_face_ids:
            placeholders = ",".join(["%s"] * len(representative_face_ids))
            pg_query = f""" 
                SELECT DISTINCT ON (f."ID")
                    f."ID" as face_id, 
                    m."RiskLevel" as risk_level,
                    m."ImageProtocol" as protocol,
                    m."ImageID" as image_id, 
                    img_domain."Domain" as image_domain, 
                    img_path."Path" as image_path,      
                    img_etc."Etc" as image_etc,         
                    first_domain."Domain" as first_seen_domain 
                FROM "EyeOfWebFaceID" f
                JOIN "ImageBasedMain" m ON f."ID" = ANY(m."FaceID")
                LEFT JOIN "BaseDomainID" img_domain ON m."ImageDomainID" = img_domain."ID"
                LEFT JOIN "ImageUrlPathID" img_path ON m."ImagePathID" = img_path."ID"
                LEFT JOIN "ImageUrlEtcID" img_etc ON m."ImageUrlEtcID" = img_etc."ID"
                LEFT JOIN "BaseDomainID" first_domain ON m."BaseDomainID" = first_domain."ID" 
                WHERE f."ID" IN ({placeholders})
                ORDER BY f."ID", m."DetectionDate" DESC 
            """
            cur.execute(pg_query, tuple(representative_face_ids))
            for row in cur.fetchall():
                pg_details_map[row["face_id"]] = row

        # Bilgileri birleştir ve sonuçları hazırla
        for group_id, occurrence_count in group_occurrences.items():
            if group_id not in face_groups or not face_groups[group_id]:
                continue

            representative_face_id = group_to_representative.get(group_id)
            if not representative_face_id:
                continue

            # Milvus verilerini al
            rep_milvus_attrs = rep_milvus_data_batch.get(representative_face_id)

            # PostgreSQL verilerini al
            pg_face_details = pg_details_map.get(representative_face_id)

            if pg_face_details:
                image_url = build_image_url(
                    pg_face_details["protocol"],
                    pg_face_details["image_domain"],
                    pg_face_details["image_path"],
                    pg_face_details["image_etc"],
                )

                related_image_id = pg_face_details.get("image_id")
                related_image_data = None
                related_mime_type = None
                if related_image_id:
                    success_rel_img, rel_img_binary = g.db_tools.getImageBinaryByID(
                        related_image_id
                    )
                    if success_rel_img and rel_img_binary:
                        try:
                            decompressed_binary = decompress_image(rel_img_binary)
                            if decompressed_binary:
                                related_image_data = base64.b64encode(
                                    decompressed_binary
                                ).decode("utf-8")
                                related_mime_type = "image/png"
                            else:
                                current_app.logger.warning(
                                    f"İlişkili yüz ({representative_face_id}) için dekompresyon boş veri döndürdü."
                                )
                        except Exception as rel_encode_err:
                            current_app.logger.error(
                                f"İlişkili yüz ({representative_face_id}) resim dekompres/encode hatası: {rel_encode_err}"
                            )

                facebox_from_milvus = None
                if rep_milvus_attrs and "face_box" in rep_milvus_attrs:
                    fb_data = rep_milvus_attrs["face_box"]
                    if isinstance(fb_data, str):
                        fb_data = ast.literal_eval(fb_data)
                    if fb_data and len(fb_data) == 4:
                        facebox_from_milvus = np.array(
                            fb_data, dtype=np.float32
                        ).tolist()

                face_info = {
                    "id": pg_face_details["face_id"],
                    "risk_level": pg_face_details["risk_level"],
                    "image_id": pg_face_details["image_id"],
                    "original_image_url": image_url,
                    "image_data": related_image_data,
                    "image_mime_type": related_mime_type,
                    "first_seen_domain": pg_face_details["first_seen_domain"],
                    "facebox": facebox_from_milvus,
                    "co_occurrence": occurrence_count,
                    "group_size": len(face_groups[group_id]),
                }
                final_related_faces.append(face_info)
            else:
                current_app.logger.warning(
                    f"Temsilci yüz {representative_face_id} için PG detayları bulunamadı. Sonuçlara eklenemedi."
                )

        final_related_faces.sort(key=lambda x: x["co_occurrence"], reverse=True)
        current_app.logger.info(
            f"Sonuçlar sıralandı. {len(final_related_faces)} ilişkili yüz grubu/temsilcisi bulundu."
        )

        target_face_box_display = None
        if target_milvus_data and "face_box" in target_milvus_data:
            fb_list = target_milvus_data["face_box"]
            if isinstance(fb_list, str):
                fb_list = ast.literal_eval(fb_list)
            if fb_list and len(fb_list) == 4:
                target_face_box_display = np.array(fb_list, dtype=np.float32).tolist()

        stats = {
            "total_similar_faces": len(target_group_ids),
            "total_related_groups": len(group_occurrences),
            "total_related_faces_processed": len(related_face_ids_to_group),
            "total_unique_images": len(image_hash_map),
            "threshold": similarity_threshold,
        }

        session_related_faces = []
        for face in final_related_faces:
            face_copy = face.copy()
            face_copy.pop("image_data", None)
            face_copy.pop("image_mime_type", None)
            session_related_faces.append(face_copy)

        session["last_comprehensive_analysis_results"] = {
            "target_face_id": target_face_id,
            "related_faces": session_related_faces,
            "stats": stats,
        }
        current_app.logger.info(
            "Sonuçlar PDF raporu için session'a kaydedildi (görsel verisi hariç)."
        )

        end_time = datetime.datetime.now()
        current_app.logger.info(
            f"Kapsamlı kişi analizi tamamlandı: Face ID {target_face_id}. Toplam süre: {end_time - start_time}"
        )

        return render_template(
            "comprehensive_analysis.html",
            target_face={
                "id": target_face_id,
                "image_data": target_face_image_data,
                "image_mime_type": target_face_mime_type,
                "face_box": target_face_box_display,
            },
            similar_faces=[],
            related_faces=final_related_faces,
            stats=stats,
        )

    except Exception as e:
        current_app.logger.error(
            f"Kapsamlı kişi analizi hatası: {str(e)}\\{traceback.format_exc()}"
        )
        flash(f"Analiz sırasında bir hata oluştu: {str(e)}", "danger")
        if conn:
            try:
                g.db_tools.releaseConnection(conn, cur)
            except Exception as cleanup_error:
                current_app.logger.error(
                    f"Kapsamlı analiz hata bloğunda bağlantı kapatma hatası: {cleanup_error}"
                )
        return redirect(url_for("web.dashboard"))
    finally:
        if conn and cur and not conn.closed:
            try:
                g.db_tools.releaseConnection(conn, cur)
            except Exception as final_cleanup_error:
                current_app.logger.error(
                    f"Kapsamlı analiz finally bloğunda bağlantı kapatma hatası: {final_cleanup_error}"
                )


# Yeni Rota: Kapsamlı Kişi Analizi Raporu İndirme
@web_bp.route("/download/comprehensive_analysis_report", methods=["GET"])
@login_required
def download_comprehensive_analysis_report():
    """Son kapsamlı kişi analizi sonuçları için PDF raporu oluşturur ve indirir."""
    analysis_data = session.get("last_comprehensive_analysis_results")

    if not analysis_data:
        flash(
            "İndirilecek rapor verisi bulunamadı veya oturum süresi doldu.", "warning"
        )
        return redirect(url_for("web.dashboard"))

    target_face_id = analysis_data.get("target_face_id")
    related_faces_data = analysis_data.get("related_faces", [])
    stats = analysis_data.get("stats", {})
    threshold = stats.get("threshold", 0.45)

    if not target_face_id or not related_faces_data:
        flash("Rapor için gerekli veriler eksik.", "warning")
        return redirect(url_for("web.dashboard"))

    username = session.get("username", "Bilinmeyen Kullanıcı")
    if hasattr(g, "user") and g.user and "username" in g.user:
        username = g.user["username"]
    elif "username" in session:
        username = session["username"]

    search_type = (
        f"Kapsamlı Kişi Analizi (Hedef ID: {target_face_id}, Eşik: {threshold})"
    )

    # --- PDF Verisi Hazırlama ---
    pdf_data = []
    conn = None
    cursor = None
    try:
        conn = g.db_tools.connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # --- SQL Sorgusu (Güncellendi) ---
        # ImageID'den binary veriyi almak için LEFT JOIN ve SELECT eklendi
        # Yüz öznitelikleri (gender, age, score, facebox) Milvus'tan alınacağı için sorgudan çıkarıldı.
        sql_query = """ 
            SELECT DISTINCT ON (f."ID") -- Her yüz için tek bir kayıt
                f."ID" as face_id, 
                -- f."FaceGender" as gender,  -- Milvus'tan alınacak
                -- f."FaceAge" as age,        -- Milvus'tan alınacak
                -- f."DetectionScore" as score, -- Milvus'tan alınacak
                -- f."FaceBox" as facebox_db, -- Milvus'tan alınacak (alias _db idi, şimdi direkt Milvus'tan)
                bds."Domain" as source_domain, 
                pds."Path" as source_path, 
                eds."Etc" as source_etc,
                m."Protocol" as source_protocol,
                -- Resim URL için bileşenler
                bdi."Domain" as image_domain,
                pi."Path" as image_path,
                ei."Etc" as image_etc,
                m."ImageProtocol" as image_protocol,
                -- Diğer bilgiler
                h."ImageHash" as image_hash,
                m."RiskLevel" as risk_level_db,
                img."BinaryImage" as binary_image -- Binary Image Data eklendi
            FROM "EyeOfWebFaceID" f
            JOIN "ImageBasedMain" m ON f."ID" = ANY(m."FaceID")
            LEFT JOIN "BaseDomainID" bds ON m."BaseDomainID" = bds."ID"
            LEFT JOIN "UrlPathID" pds ON m."UrlPathID" = pds."ID"
            LEFT JOIN "UrlEtcID" eds ON m."UrlEtcID" = eds."ID"
            LEFT JOIN "BaseDomainID" bdi ON m."ImageDomainID" = bdi."ID"
            LEFT JOIN "ImageUrlPathID" pi ON m."ImagePathID" = pi."ID"
            LEFT JOIN "ImageUrlEtcID" ei ON m."ImageUrlEtcID" = ei."ID"
            LEFT JOIN "ImageHashID" h ON m."HashID" = h."ID"
            LEFT JOIN "ImageID" img ON m."ImageID" = img."ID" -- ImageID tablosuna JOIN eklendi
            WHERE f."ID" = %s
            ORDER BY f."ID", m."DetectionDate" DESC -- En yeni kaydı al
        """

        # Filtreleme: Sadece 1'den fazla görünenleri al
        filtered_related_faces = [
            face for face in related_faces_data if face.get("co_occurrence", 0) > 1
        ]

        for face_info in filtered_related_faces:
            res_face_id = face_info.get("id")
            if not res_face_id:
                continue

            image_data_b64 = None
            image_url = None
            db_pg_data = (
                None  # db_extra_data yerine db_pg_data kullanalım tutarlılık için
            )

            # --- Veritabanından Ek Bilgileri Al (PostgreSQL) ---
            cursor.execute(sql_query, (res_face_id,))  # sql_query güncellendi
            db_pg_data = cursor.fetchone()  # PostgreSQL'den gelen veri

            # --- Milvus'tan Yüz Özniteliklerini Al ---
            milvus_attributes = None
            try:
                milvus_attributes = g.db_tools.get_milvus_face_attributes(
                    EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME, res_face_id
                )
                if not milvus_attributes:
                    current_app.logger.warning(
                        f"[PDF_COMP] Milvus'tan {res_face_id} için öznitelik alınamadı."
                    )
            except Exception as e:
                current_app.logger.error(
                    f"[PDF_COMP] Milvus'tan {res_face_id} için öznitelik alınırken hata: {e}"
                )

            # --- PDF Öğesini Oluştur ---
            title = f"Yüz ID: {res_face_id} (Görülme: {face_info.get('co_occurrence', 0)}, Grup: {face_info.get('group_size', 1)})"

            gender_str = "N/A"
            age_from_milvus = None
            score_from_milvus = None
            facebox_from_milvus = None
            # risk_level_from_session = face_info.get('risk_level') # Bu bilgi session'daki face_info'da olmayabilir, PG'den alacağız

            if milvus_attributes:
                gender_bool = milvus_attributes.get("face_gender")
                gender_str = (
                    "Erkek"
                    if gender_bool is True
                    else ("Kadın" if gender_bool is False else "N/A")
                )
                age_from_milvus = milvus_attributes.get("face_age")
                score_from_milvus = milvus_attributes.get("detection_score")
                facebox_from_milvus = milvus_attributes.get("face_box")

            # PostgreSQL'den gelen ve session/milvus'ta olmayan veriler için fallback
            age_final = age_from_milvus
            score_final = score_from_milvus
            risk_level_final = (
                db_pg_data.get("risk_level_db")
                if db_pg_data
                else face_info.get("risk_level")
            )  # session daki face_info dan risk_level alabiliriz

            facebox_final = facebox_from_milvus
            if facebox_final is None:
                facebox_from_session = face_info.get("facebox")
                if facebox_from_session:
                    facebox_final = facebox_from_session
                # facebox_db alias artık PG sorgusunda yok, bu yüzden db_pg_data.get('facebox_db') kullanılmamalı.
                # Eğer sessionda da yoksa ve Milvus'tan da gelmediyse None kalacak.

            binary_image_data = None
            if db_pg_data:
                binary_image_data = db_pg_data.get("binary_image")

            if binary_image_data:
                try:
                    image_data_b64 = base64.b64encode(binary_image_data).decode("utf-8")
                except Exception as b64_error:
                    current_app.logger.error(
                        f"[PDF_COMP] Error encoding binary image for face {res_face_id}: {b64_error}"
                    )
                    image_data_b64 = None
                    if db_pg_data:
                        image_url = build_image_url(
                            db_pg_data.get("image_protocol"),
                            db_pg_data.get("image_domain"),
                            db_pg_data.get("image_path"),
                            db_pg_data.get("image_etc"),
                        )
            elif db_pg_data:
                image_url = build_image_url(
                    db_pg_data.get("image_protocol"),
                    db_pg_data.get("image_domain"),
                    db_pg_data.get("image_path"),
                    db_pg_data.get("image_etc"),
                )

            source_url = None
            image_hash = "N/A"
            if db_pg_data:
                source_url = build_image_url(
                    db_pg_data.get("source_protocol"),
                    db_pg_data.get("source_domain"),
                    db_pg_data.get("source_path"),
                    db_pg_data.get("source_etc"),
                )
                image_hash = db_pg_data.get("image_hash", "N/A")

            pdf_item = {
                "title": title,
                "image_data_b64": image_data_b64,
                "image_url": image_url if not image_data_b64 else None,
                "source_url": source_url,
                "hash": image_hash,
                "count": face_info.get("co_occurrence", 0),
                "score": score_final,
                "gender": gender_str,
                "age": age_final,
                "similarity": None,
                "comprehensive_info": {
                    "risk_level": risk_level_final,
                    "group_size": face_info.get("group_size", 1),
                },
                "facebox": facebox_final,
            }
            pdf_data.append(pdf_item)

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Kapsamlı analiz PDF verisi hazırlanırken hata: {error}")
        print(traceback.format_exc())
        flash("Rapor verileri hazırlanırken bir hata oluştu.", "danger")
        if conn:
            g.db_tools.releaseConnection(conn, cursor)
        return redirect(
            url_for("web.comprehensive_person_analysis", face_id=target_face_id)
        )
    finally:
        if conn:
            g.db_tools.releaseConnection(conn, cursor)

    # --- PDF Raporunu Oluştur ve Gönder ---
    if not pdf_data:
        flash("Rapor için işlenecek (1'den fazla görünen) yüz bulunamadı.", "warning")
        return redirect(
            url_for("web.comprehensive_person_analysis", face_id=target_face_id)
        )

    pdf_bytes = generate_pdf_report(search_type, username, pdf_data)

    if pdf_bytes is None:
        # Hata mesajını genel tut
        flash("PDF raporu oluşturulurken bir hata oluştu.", "danger")
        return redirect(
            url_for("web.comprehensive_person_analysis", face_id=target_face_id)
        )

    # Dosya adında doğru ID'leri kullan
    report_filename = f"EyeOfWeb_KapsamliAnaliz_{target_face_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=report_filename,
    )


@web_bp.route("/face_relationship_details/<face_id>/<target_face_id>", methods=["GET"])
@login_required
@limiter.limit("20 per minute")
def face_relationship_details(face_id, target_face_id):
    """
    İki yüzün birlikte göründüğü tüm görselleri listeler.
    face_id: İlişkili yüzün ID'si
    target_face_id: Hedef yüzün ID'si
    """
    try:
        # ID'leri doğrula ve dönüştür
        try:
            face_id = int(face_id)
            target_face_id = int(target_face_id)
        except ValueError:
            flash("Geçersiz yüz ID formatı", "error")
            return redirect(url_for("web.dashboard"))

        # Grup ID'lerini al (benzer yüzleri de göster)
        similarity_threshold = float(request.args.get("threshold", 0.45))

        conn = g.db_tools.connect()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # 1. Hedef yüz ve ilgili yüzün embedding'lerini al
        cur.execute(
            """
            SELECT "ID", "FaceEmbeddingData"
            FROM "EyeOfWebFaceID"
            WHERE "ID" IN (%s, %s) AND "FaceEmbeddingData" IS NOT NULL
        """,
            (target_face_id, face_id),
        )

        embedding_data = cur.fetchall()
        if len(embedding_data) < 2:
            flash("Yüz veya gömme vektörü bulunamadı.", "error")
            g.db_tools.releaseConnection(conn, cur)
            return redirect(url_for("web.dashboard"))

        # Embedding'leri dictionary'e dönüştür
        face_embeddings = {}
        for data in embedding_data:
            face_embeddings[data["ID"]] = np.array(
                ast.literal_eval(data["FaceEmbeddingData"]), dtype=np.float32
            )

        # 2. Hedef yüze benzer yüzleri bul
        target_group_ids = {target_face_id}
        face_group_ids = {face_id}

        cur.execute(
            """
            SELECT "ID", "FaceEmbeddingData"
            FROM "EyeOfWebFaceID"
            WHERE "ID" != %s AND "ID" != %s AND "FaceEmbeddingData" IS NOT NULL
        """,
            (target_face_id, face_id),
        )

        all_other_faces = cur.fetchall()
        target_embedding = face_embeddings[target_face_id]
        face_embedding = face_embeddings[face_id]

        # Hedef yüze benzer yüzleri bul
        for other_face in all_other_faces:
            other_id = other_face["ID"]
            other_embedding = np.array(
                ast.literal_eval(other_face["FaceEmbeddingData"]), dtype=np.float32
            )
            if other_embedding.size == 512:
                # Hedef yüze benzerlik
                similarity_to_target = np.dot(target_embedding, other_embedding) / (
                    np.linalg.norm(target_embedding) * np.linalg.norm(other_embedding)
                )
                if similarity_to_target >= similarity_threshold:
                    target_group_ids.add(other_id)

                # İlişkili yüze benzerlik
                similarity_to_face = np.dot(face_embedding, other_embedding) / (
                    np.linalg.norm(face_embedding) * np.linalg.norm(other_embedding)
                )
                if similarity_to_face >= similarity_threshold:
                    face_group_ids.add(other_id)

        # 3. Bu iki gruptaki yüzlerin birlikte göründüğü tüm görselleri bul
        query = """
        SELECT DISTINCT 
            m."ImageID", 
            m."FaceID",
            m."ImageProtocol",
            m."BaseDomainID",
            m."DetectionDate",
            ih."ImageHash",
            bd."Domain" as domain_name,
            img_domain."Domain" as image_domain,
            img_path."Path" as image_path,
            img_etc."Etc" as image_etc,
            it."Title" as image_title
        FROM "ImageBasedMain" m
        JOIN "ImageHashID" ih ON m."HashID" = ih."ID"
        LEFT JOIN "BaseDomainID" bd ON m."BaseDomainID" = bd."ID"
        LEFT JOIN "BaseDomainID" img_domain ON m."ImageDomainID" = img_domain."ID"
        LEFT JOIN "ImageUrlPathID" img_path ON m."ImagePathID" = img_path."ID"
        LEFT JOIN "ImageUrlEtcID" img_etc ON m."ImageUrlEtcID" = img_etc."ID"
        LEFT JOIN "ImageTitleID" it ON m."ImageTitleID" = it."ID"
        WHERE 
            EXISTS (SELECT 1 FROM unnest(m."FaceID") target_face WHERE target_face = ANY(%s))
            AND
            EXISTS (SELECT 1 FROM unnest(m."FaceID") related_face WHERE related_face = ANY(%s))
        ORDER BY m."DetectionDate" DESC
        """

        cur.execute(query, (list(target_group_ids), list(face_group_ids)))
        images = cur.fetchall()

        current_app.logger.info(
            f"[REL_DETAILS] Found {len(images)} potential images containing faces from both groups."
        )

        # Attempt to get expected co_occurrence from session
        expected_co_occurrence = -1  # Default/fallback value
        try:
            analysis_data = session.get("last_comprehensive_analysis_results")
            if analysis_data and analysis_data.get("target_face_id") == target_face_id:
                related_faces_data = analysis_data.get("related_faces", [])
                for face_info in related_faces_data:
                    if face_info.get("id") == face_id:
                        expected_co_occurrence = face_info.get("co_occurrence", -1)
                        current_app.logger.info(
                            f"[REL_DETAILS] Found expected co_occurrence from session: {expected_co_occurrence}"
                        )
                        break
            else:
                current_app.logger.warning(
                    f"[REL_DETAILS] Session data mismatch or not found for target_face_id {target_face_id}."
                )
        except Exception as session_err:
            current_app.logger.error(
                f"[REL_DETAILS] Error reading session data: {session_err}"
            )

        # Prepare image details for display (processing loop)
        image_details = []  # This will store processed images for the template
        images_metadata_list = []  # ---> YENİ: PDF için meta veri listesi
        processed_hashes = set()

        # --- Yer Tutucu Görsel Oluşturma Fonksiyonu ---
        def create_placeholder_image(width=300, height=200, text="Görsel Yok"):
            placeholder = np.full(
                (height, width, 3), (220, 220, 220), dtype=np.uint8
            )  # Açık gri
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            text_color = (50, 50, 50)
            text_thickness = 1
            text_size, _ = cv2.getTextSize(text, font, font_scale, text_thickness)
            text_x = (width - text_size[0]) // 2
            text_y = (height + text_size[1]) // 2
            cv2.putText(
                placeholder,
                text,
                (text_x, text_y),
                font,
                font_scale,
                text_color,
                text_thickness,
                cv2.LINE_AA,
            )
            success_encode, buffer = cv2.imencode(".png", placeholder)  # PNG kullanalım
            if success_encode:
                return base64.b64encode(buffer).decode("utf-8")
            return None

        # --- Yer Tutucu Bitti ---

        # Process the images found by the query
        for img in images:  # Loop through rows from DB query
            image_hash = img.get("ImageHash")
            if image_hash and image_hash in processed_hashes:
                continue
            if image_hash:
                processed_hashes.add(image_hash)

            image_id = img.get("ImageID")
            domain_name = img.get("domain_name")
            image_title = img.get("image_title", "Başlıksız")
            detection_date = img.get("DetectionDate")
            faces_in_image_ids = img.get("FaceID", [])  # Get face IDs in the image
            processed_image_b64 = None
            is_placeholder = False
            placeholder_text = "Görsel Yok"
            cv_image = None
            image_source_info = f"ImageID: {image_id if image_id else 'N/A'}"
            original_url_for_meta = None  # Meta veri için URL

            try:  # Outer try for the entire image processing
                # 1. Try fetching from URL
                image_url = build_image_url(
                    img.get("ImageProtocol"),
                    img.get("image_domain"),
                    img.get("image_path"),
                    img.get("image_etc"),
                )
                original_url_for_meta = image_url  # Save URL for metadata

                if image_url:
                    image_source_info += f", URL: {image_url}"
                    current_app.logger.debug(
                        f"[REL_DETAILS_LOOP] Attempting download from URL: {image_url}"
                    )
                    try:  # Inner try for download operation
                        download_success, downloaded_data, _ = (
                            downloadImage_defaultSafe(image_url)
                        )
                        if download_success and downloaded_data is not None:
                            if (
                                isinstance(downloaded_data, np.ndarray)
                                and downloaded_data.size > 0
                            ):
                                cv_image = downloaded_data
                                current_app.logger.debug(
                                    f"[REL_DETAILS_LOOP] Got cv2 image directly for URL: {image_url}"
                                )
                            elif isinstance(downloaded_data, bytes):
                                image_array = np.frombuffer(
                                    downloaded_data, dtype=np.uint8
                                )
                                cv_image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                                if cv_image is None or cv_image.size == 0:
                                    current_app.logger.warning(
                                        f"[REL_DETAILS_LOOP] Failed to decode downloaded bytes from URL: {image_url}"
                                    )
                                    placeholder_text = "URL Decode Hatası"
                                else:
                                    current_app.logger.debug(
                                        f"[REL_DETAILS_LOOP] Successfully decoded downloaded bytes from URL: {image_url}"
                                    )
                            else:
                                current_app.logger.warning(
                                    f"[REL_DETAILS_LOOP] Unexpected data type from download ({type(downloaded_data)}) for URL: {image_url}"
                                )
                                cv_image = None
                                placeholder_text = "İndirme Veri Tipi Hatası"
                        else:
                            current_app.logger.warning(
                                f"[REL_DETAILS_LOOP] Download failed or empty data received for URL: {image_url}"
                            )
                            placeholder_text = "URL İndirme Hatası"
                            cv_image = None
                    except Exception as download_err:
                        current_app.logger.error(
                            f"[REL_DETAILS_LOOP] Error during URL download/processing {image_url}: {download_err}"
                        )
                        placeholder_text = "URL İşleme İstisnası"
                        cv_image = None
                else:
                    current_app.logger.debug(
                        f"[REL_DETAILS_LOOP] Image URL missing for {image_source_info}. Skipping URL."
                    )
                    placeholder_text = "URL Yok"
                    # cv_image is already None

                # 2. If URL failed or wasn't present, try fetching from DB via ImageID
                if cv_image is None and image_id:
                    current_app.logger.debug(
                        f"[REL_DETAILS_LOOP] URL failed/missing. Attempting DB fetch for ImageID: {image_id}"
                    )
                    try:  # Inner try for DB fetch
                        success_db, img_binary = g.db_tools.getImageBinaryByID(image_id)
                        if success_db and img_binary:
                            img_binary = decompress_image(img_binary)
                            image_array = np.frombuffer(img_binary, dtype=np.uint8)
                            cv_image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                            if cv_image is not None and cv_image.size > 0:
                                current_app.logger.debug(
                                    f"[REL_DETAILS_LOOP] Successfully decoded image from DB (ImageID: {image_id})."
                                )
                                placeholder_text = (
                                    ""  # Reset placeholder text if successful
                                )
                            else:
                                current_app.logger.warning(
                                    f"[REL_DETAILS_LOOP] Failed to decode image from DB (ImageID: {image_id})"
                                )
                                cv_image = None
                                placeholder_text = "DB Decode Hatası"
                        else:
                            current_app.logger.warning(
                                f"[REL_DETAILS_LOOP] Failed to fetch image from DB (ImageID: {image_id})"
                            )
                            placeholder_text = "DB Getirme Hatası"
                            cv_image = None  # Ensure cv_image is None if fetch fails
                    except Exception as db_fetch_err:
                        current_app.logger.error(
                            f"[REL_DETAILS_LOOP] Error fetching/decoding DB ImageID {image_id}: {db_fetch_err}"
                        )
                        cv_image = None
                        placeholder_text = "DB İstisnası"
                elif cv_image is None:
                    current_app.logger.warning(
                        f"[REL_DETAILS_LOOP] No image data source found for {image_source_info}"
                    )
                    # Placeholder text already indicates the reason

                # 3. Process image or set placeholder flag
                if cv_image is not None and cv_image.size > 0:
                    # Görsel işleme (yüz kutucuklarını çizme vb.)
                    img_height, img_width = cv_image.shape[:2]
                    if faces_in_image_ids:
                        query_placeholders = ",".join(["%s"] * len(faces_in_image_ids))
                        face_box_query = f'SELECT "ID", "FaceBox" FROM "EyeOfWebFaceID" WHERE "ID" IN ({query_placeholders})'
                        cur.execute(face_box_query, faces_in_image_ids)
                        face_boxes_results = cur.fetchall()
                        face_box_map = {
                            fb["ID"]: fb["FaceBox"] for fb in face_boxes_results
                        }

                        for face_id_in_image in faces_in_image_ids:
                            facebox_bytes = face_box_map.get(face_id_in_image)
                            if facebox_bytes:
                                is_target = face_id_in_image in target_group_ids
                                is_related = face_id_in_image in face_group_ids
                                if is_target or is_related:
                                    try:  # Inner try for facebox processing
                                        facebox = np.array(
                                            ast.literal_eval(facebox_bytes),
                                            dtype=np.float32,
                                        )
                                        if len(facebox) == 4:
                                            x1, y1, x2, y2 = map(int, facebox)
                                            x1 = max(0, min(x1, img_width - 1))
                                            y1 = max(0, min(y1, img_height - 1))
                                            x2 = max(0, min(x2, img_width - 1))
                                            y2 = max(0, min(y2, img_height - 1))
                                            if x2 > x1 and y2 > y1:
                                                color = (
                                                    (0, 255, 0)
                                                    if is_target
                                                    else (0, 0, 255)
                                                )
                                                thickness = 3
                                                cv2.rectangle(
                                                    cv_image,
                                                    (x1, y1),
                                                    (x2, y2),
                                                    color,
                                                    thickness,
                                                )
                                    except Exception as fb_err:
                                        current_app.logger.error(
                                            f"[REL_DETAILS_LOOP] Error processing facebox for face {face_id_in_image} in image {image_id}: {fb_err}"
                                        )

                    # İşlenmiş görseli base64'e dönüştür
                    success_encode, buffer = cv2.imencode(".jpg", cv_image)
                    if success_encode:
                        processed_image_b64 = base64.b64encode(buffer).decode("utf-8")
                    else:
                        current_app.logger.error(
                            f"[REL_DETAILS_LOOP] Failed to encode processed image: {image_source_info}"
                        )
                        is_placeholder = True
                        placeholder_text = "Encode Hatası"
                else:
                    is_placeholder = True
                    # placeholder_text zaten yukarıda ayarlanmıştı

            except Exception as processing_error:
                # ... (handle general processing error, set placeholder) ...
                is_placeholder = True
                placeholder_text = "Genel İşleme Hatası"

            # Sonuçları listelere ekle
            if is_placeholder or not processed_image_b64:
                # Placeholder ekle (hem gösterim hem meta veri için)
                placeholder_b64 = create_placeholder_image(text=placeholder_text)
                image_details.append(
                    {
                        "id": image_id,
                        "processed_image": placeholder_b64,
                        "is_placeholder": True,
                        "placeholder_message": placeholder_text,
                        "domain": domain_name,
                        "title": image_title,
                        "detection_date": detection_date,
                    }
                )
                # ---> YENİ: Placeholder için de meta veri ekle (az bilgiyle)
                images_metadata_list.append(
                    {
                        "id": image_id,
                        "url": original_url_for_meta,  # Orijinal URL (varsa)
                        "domain": domain_name,
                        "title": image_title,
                        "detection_date": (
                            detection_date.isoformat() if detection_date else None
                        ),  # ISO format for session
                        "faces": [],  # Placeholder'da yüz bilgisi yok
                        "hash": image_hash,
                        "error": placeholder_text,  # Hata mesajını ekle
                    }
                )
            else:
                # Başarılı işlenen görseli ekle
                image_details.append(
                    {
                        "id": image_id,
                        "processed_image": processed_image_b64,
                        "is_placeholder": False,
                        "domain": domain_name,
                        "title": image_title,
                        "detection_date": detection_date,
                    }
                )
                # ---> YENİ: Başarılı görsel için meta veri ekle
                # Yüz ID'lerini ve tiplerini belirle (PDF raporu için)
                faces_metadata_for_pdf = []
                if faces_in_image_ids:
                    for f_id in faces_in_image_ids:
                        f_type = (
                            "Hedef"
                            if f_id in target_group_ids
                            else ("İlişkili" if f_id in face_group_ids else "Diğer")
                        )
                        faces_metadata_for_pdf.append({"id": f_id, "type": f_type})

                images_metadata_list.append(
                    {
                        "id": image_id,
                        "url": original_url_for_meta,
                        "domain": domain_name,
                        "title": image_title,
                        "detection_date": (
                            detection_date.isoformat() if detection_date else None
                        ),  # ISO format for session
                        "faces": faces_metadata_for_pdf,  # Yüz ID'leri ve tipleri
                        "hash": image_hash,
                        "error": None,  # Hata yok
                    }
                )
        # ---> Görsel İşleme Döngüsü Bitti <---

        # Döngü bitti, istatistikleri hesapla
        stats = {
            "total_images": (
                expected_co_occurrence if expected_co_occurrence != -1 else len(images)
            ),
            "actual_images_found": len(image_details),
            "total_target_group": len(target_group_ids),
            "total_related_group": len(face_group_ids),
            "threshold": similarity_threshold,
        }
        current_app.logger.info(f"[REL_DETAILS] Stats prepared: {stats}")

        # Yüz detaylarını al (başlık ve görseller için)
        details_query = """
            SELECT DISTINCT ON (f."ID")
                f."ID",
                f."DetectionDate",
                m."RiskLevel",
                m."ImageProtocol",
                img_domain."Domain" as image_domain,
                img_path."Path" as image_path,
                img_etc."Etc" as image_etc
            FROM "EyeOfWebFaceID" f
            LEFT JOIN "ImageBasedMain" m ON f."ID" = ANY(m."FaceID")
            LEFT JOIN "BaseDomainID" img_domain ON m."ImageDomainID" = img_domain."ID"
            LEFT JOIN "ImageUrlPathID" img_path ON m."ImagePathID" = img_path."ID"
            LEFT JOIN "ImageUrlEtcID" img_etc ON m."ImageUrlEtcID" = img_etc."ID"
            WHERE f."ID" IN (%s, %s)
            ORDER BY f."ID", m."DetectionDate" DESC
        """
        cur.execute(details_query, (target_face_id, face_id))
        face_data = cur.fetchall()

        target_face_dict = None
        related_face_dict = None

        for row in face_data:
            face_dict = dict(row)
            face_dict["original_image_url"] = build_image_url(
                row.get("ImageProtocol"),
                row.get("image_domain"),
                row.get("image_path"),
                row.get("image_etc"),
            )
            if row["ID"] == target_face_id:
                face_dict["group_size"] = len(target_group_ids)
                target_face_dict = face_dict
            elif row["ID"] == face_id:
                face_dict["group_size"] = len(face_group_ids)
                related_face_dict = face_dict

        if not target_face_dict:
            target_face_dict = {"ID": target_face_id}
        if not related_face_dict:
            related_face_dict = {"ID": face_id}

        g.db_tools.releaseConnection(conn, cur)  # Bağlantıyı burada bırakalım

        # ---> YENİ: PDF Raporu için verileri Session'a kaydet <---
        try:
            session_key = f"last_relationship_details_{target_face_id}_{face_id}"
            session[session_key] = {
                "target_face_details": target_face_dict,  # Tam yüz detayları
                "related_face_details": related_face_dict,  # Tam yüz detayları
                "images_metadata": images_metadata_list,  # Sadece meta veri (base64 hariç)
                "stats": stats,
            }
            current_app.logger.info(
                f"[REL_DETAILS] Successfully saved data to session key: {session_key}"
            )
        except Exception as session_save_err:
            # Oturuma kaydetme hatası kritik değil, devam et ama logla
            current_app.logger.error(
                f"[REL_DETAILS] Failed to save relationship details to session: {session_save_err}"
            )
            flash(
                "Rapor verileri oturuma kaydedilemedi, PDF indirme çalışmayabilir.",
                "warning",
            )
        # ---> Session Kaydı Bitti <---

        # Şablonu render et
        return render_template(
            "face_relationship_details.html",
            target_face=target_face_dict,
            related_face=related_face_dict,
            images=image_details,  # İşlenmiş görselleri (veya yer tutucuları) gönder
            stats=stats,
        )

    except (psycopg2.Error, Exception) as e:
        current_app.logger.error(
            f"İlişki detayları hatası: {str(e)}\n{traceback.format_exc()}"
        )
        flash(f"İlişki detayları alınırken bir hata oluştu: {str(e)}", "danger")
        # Hata durumunda bağlantıyı kapatmayı dene
        try:
            if conn:
                g.db_tools.releaseConnection(conn, cur)
        except Exception as cleanup_err:
            current_app.logger.error(
                f"[REL_DETAILS] Error during cleanup in except block: {cleanup_err}"
            )
        # Kapsamlı analize geri yönlendir
        tfi = 0
        try:
            tfi = int(target_face_id)
        except (ValueError, TypeError):
            current_app.logger.warning(
                f"[REL_DETAILS] Could not convert target_face_id '{target_face_id}' to int for redirect."
            )
        return redirect(url_for("web.comprehensive_person_analysis", face_id=tfi))
    # finally bloğu artık gerekli değil

    # Bu kısım unreachable, kaldırılmalı veya finally'den önce olmalı
    # end_time = datetime.datetime.now()
    # current_app.logger.info(f"Kapsamlı kişi analizi tamamlandı: Face ID {target_face_id}. Toplam süre: {end_time - start_time}")

    # --- 8. Sonucu Döndürme ---
    # Bu blok da except veya finally sonrası olmamalı, return render_template ile bitti.
    # return render_template(
    #     'comprehensive_analysis.html',
    #     target_face={'id': target_face_id},
    #     similar_faces=[],
    #     related_faces=final_related_faces,
    #     stats=stats
    # )


# Yeni Rota: Yüz İlişki Detayları Raporu İndirme
@web_bp.route(
    "/download/relationship_details_report/<int:target_face_id>/<int:face_id>",
    methods=["GET"],
)
@login_required
def download_relationship_details_report(target_face_id, face_id):
    """İki yüzün birlikte göründüğü görseller için PDF raporu oluşturur ve indirir."""

    session_key = f"last_relationship_details_{target_face_id}_{face_id}"
    relationship_data = session.get(session_key)

    if not relationship_data:
        flash(
            "İndirilecek rapor verisi bulunamadı veya oturum süresi doldu.", "warning"
        )
        return redirect(
            url_for(
                "web.face_relationship_details",
                target_face_id=target_face_id,
                face_id=face_id,
            )
        )

    target_face_details = relationship_data.get("target_face_details")
    related_face_details = relationship_data.get("related_face_details")
    # Meta veriyi al (Doğru anahtar: images_metadata)
    images_metadata_list = relationship_data.get("images_metadata", [])
    stats = relationship_data.get("stats", {})
    threshold = stats.get("threshold", 0.45)

    # Kontrolü images_metadata_list üzerinden yap
    if not target_face_details or not related_face_details or not images_metadata_list:
        flash("Rapor için gerekli meta veriler eksik.", "warning")
        return redirect(
            url_for(
                "web.face_relationship_details",
                target_face_id=target_face_id,
                face_id=face_id,
            )
        )

    username = session.get("username", "Bilinmeyen Kullanıcı")
    if hasattr(g, "user") and g.user and "username" in g.user:
        username = g.user["username"]
    elif "username" in session:
        username = session["username"]

    # Arama tipinde URL'den alınan ID'leri kullan
    search_type = f"Yüz İlişki Detayları (Hedef: {target_face_id}, İlişkili: {face_id}, Eşik: {threshold})"

    # --- PDF Verisi Hazırlama (Görselleri Yeniden İşleyerek) ---
    pdf_data = []
    conn = (
        None  # Veritabanı bağlantısı gerekebilir (yüz kutucuklarını tekrar almak için)
    )
    cursor = None

    # --- Yer Tutucu Görsel Oluşturma Fonksiyonu ---
    def create_placeholder_image(width=300, height=200, text="Görsel Yok"):
        placeholder = np.full(
            (height, width, 3), (220, 220, 220), dtype=np.uint8
        )  # Açık gri
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        text_color = (50, 50, 50)
        text_thickness = 1
        text_size, _ = cv2.getTextSize(text, font, font_scale, text_thickness)
        text_x = (width - text_size[0]) // 2
        text_y = (height + text_size[1]) // 2
        cv2.putText(
            placeholder,
            text,
            (text_x, text_y),
            font,
            font_scale,
            text_color,
            text_thickness,
            cv2.LINE_AA,
        )
        success_encode, buffer = cv2.imencode(".png", placeholder)  # PNG kullanalım
        if success_encode:
            return base64.b64encode(buffer).decode("utf-8")
        return None

    # --- Yer Tutucu Bitti ---

    try:
        conn = g.db_tools.connect()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Yüz gruplarını yeniden oluştur (veya session'dan al, şimdilik yeniden oluşturalım)
        # Bu kısım /face_relationship_details içindeki mantıkla aynı olmalı
        # 1. Embedding'leri al
        cursor.execute(
            'SELECT "ID", "FaceEmbeddingData" FROM "EyeOfWebFaceID" WHERE "ID" IN (%s, %s)',
            (target_face_id, face_id),
        )
        embedding_data = cursor.fetchall()
        if len(embedding_data) < 2:
            raise ValueError("Hedef veya ilişkili yüz embedding bulunamadı")
        face_embeddings = {
            data["ID"]: np.array(
                ast.literal_eval(data["FaceEmbeddingData"]), dtype=np.float32
            )
            for data in embedding_data
        }

        # 2. Benzer yüzleri bul
        target_group_ids = {target_face_id}
        face_group_ids = {face_id}
        cursor.execute(
            'SELECT "ID", "FaceEmbeddingData" FROM "EyeOfWebFaceID" WHERE "ID" != %s AND "ID" != %s AND "FaceEmbeddingData" IS NOT NULL',
            (target_face_id, face_id),
        )
        all_other_faces = cursor.fetchall()
        target_embedding = face_embeddings[target_face_id]
        face_embedding = face_embeddings[face_id]

        for other_face in all_other_faces:
            other_id = other_face["ID"]
            other_embedding = np.array(
                ast.literal_eval(other_face["FaceEmbeddingData"]), dtype=np.float32
            )
            if other_embedding.size == 512:
                similarity_to_target = np.dot(target_embedding, other_embedding) / (
                    np.linalg.norm(target_embedding) * np.linalg.norm(other_embedding)
                )
                if similarity_to_target >= threshold:
                    target_group_ids.add(other_id)
                similarity_to_face = np.dot(face_embedding, other_embedding) / (
                    np.linalg.norm(face_embedding) * np.linalg.norm(other_embedding)
                )
                if similarity_to_face >= threshold:
                    face_group_ids.add(other_id)
        # --- Grup Oluşturma Bitti ---

        total_meta_items = len(images_metadata_list)
        processed_successfully = 0
        used_placeholder_count = 0
        current_app.logger.info(
            f"[PDF_REL_REPORT] Starting PDF generation for {total_meta_items} image metadata items."
        )

        for idx, img_meta in enumerate(images_metadata_list):
            log_prefix = (
                f"[PDF_REL_LOOP {idx+1}/{total_meta_items}]"  # Log prefix for this item
            )
            current_app.logger.info(
                f"{log_prefix} Processing image meta: ID={img_meta.get('id', 'N/A')}, URL={img_meta.get('url', 'N/A')}"
            )

            image_id = img_meta.get("id")
            original_url = img_meta.get("url")
            domain_name = img_meta.get("domain")
            image_title = img_meta.get("title", "Başlıksız")
            detection_date = img_meta.get(
                "detection_date"
            )  # Keep as string/datetime from session for now
            faces_metadata = img_meta.get("faces", [])
            image_hash = img_meta.get("hash", "N/A")
            source_url = f"http://{domain_name}" if domain_name else "N/A"
            session_error_msg = img_meta.get("error")

            cv_image = None
            processed_image_b64 = None
            is_placeholder = False
            placeholder_text = session_error_msg or "Görsel Yok"
            image_source_info = f"ImageID: {image_id if image_id else 'N/A'}"

            if session_error_msg:
                current_app.logger.warning(
                    f"{log_prefix} Skipping fetch, error from session: {session_error_msg}"
                )
                is_placeholder = True
            else:
                # --- Attempt to get image data ---
                try:
                    # 1. Try URL
                    if original_url:
                        image_source_info += f", URL: {original_url}"
                        current_app.logger.debug(
                            f"{log_prefix} Attempting download from URL..."
                        )
                        try:
                            dl_success, dl_data, _ = downloadImage_defaultSafe(
                                original_url
                            )
                            if dl_success and dl_data is not None:
                                if isinstance(dl_data, np.ndarray) and dl_data.size > 0:
                                    cv_image = dl_data
                                    current_app.logger.debug(
                                        f"{log_prefix} Success: Got cv2 image directly from URL."
                                    )
                                elif isinstance(dl_data, bytes):
                                    img_array = np.frombuffer(dl_data, dtype=np.uint8)
                                    cv_image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                                    if cv_image is None or cv_image.size == 0:
                                        current_app.logger.warning(
                                            f"{log_prefix} Failure: Could not decode bytes from URL."
                                        )
                                        placeholder_text = "URL Decode H."
                                    else:
                                        current_app.logger.debug(
                                            f"{log_prefix} Success: Decoded bytes from URL."
                                        )
                                else:
                                    current_app.logger.warning(
                                        f"{log_prefix} Failure: Unexpected data type from URL download: {type(dl_data)}"
                                    )
                                    cv_image = None
                                    placeholder_text = "URL Veri Tipi H."
                            else:
                                current_app.logger.warning(
                                    f"{log_prefix} Failure: Download failed or empty data from URL."
                                )
                                cv_image = None
                                placeholder_text = "URL İndirme H."
                        except Exception as download_err:
                            current_app.logger.error(
                                f"{log_prefix} Exception during URL download: {download_err}"
                            )
                            cv_image = None
                            placeholder_text = "URL İstisna H."
                    else:
                        current_app.logger.debug(
                            f"{log_prefix} URL missing in metadata."
                        )
                        placeholder_text = "URL Yok (Meta)"
                        cv_image = None

                    # 2. Try DB if URL failed and ImageID exists
                    if cv_image is None and image_id:
                        current_app.logger.debug(
                            f"{log_prefix} Attempting DB fetch for ImageID: {image_id}"
                        )
                        try:
                            success_db, img_binary = g.db_tools.getImageBinaryByID(
                                image_id
                            )
                            if success_db and img_binary:
                                image_array = np.frombuffer(img_binary, dtype=np.uint8)
                                cv_image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                                if cv_image is not None and cv_image.size > 0:
                                    current_app.logger.debug(
                                        f"{log_prefix} Success: Decoded image from DB."
                                    )
                                    placeholder_text = ""  # Reset if successful
                                else:
                                    current_app.logger.warning(
                                        f"{log_prefix} Failure: Failed to decode image from DB."
                                    )
                                    cv_image = None
                                    placeholder_text = "DB Decode H."
                            else:
                                current_app.logger.warning(
                                    f"{log_prefix} Failure: Failed to fetch image from DB."
                                )
                                cv_image = None
                                placeholder_text = "DB Getirme H."
                        except Exception as db_fetch_err:
                            current_app.logger.error(
                                f"{log_prefix} Exception during DB fetch: {db_fetch_err}"
                            )
                            cv_image = None
                            placeholder_text = "DB İstisna H."
                    elif cv_image is None:
                        current_app.logger.warning(
                            f"{log_prefix} No valid image source could be used (URL failed/missing and no ImageID)."
                        )

                    # --- Process image if obtained ---
                    if cv_image is not None and cv_image.size > 0:
                        current_app.logger.debug(
                            f"{log_prefix} Image obtained, processing faceboxes..."
                        )
                        try:
                            img_height, img_width = cv_image.shape[:2]
                            face_ids_in_image = [f["id"] for f in faces_metadata]
                            if face_ids_in_image:
                                query_placeholders = ",".join(
                                    ["%s"] * len(face_ids_in_image)
                                )
                                # Use tuple for query parameters
                                cursor.execute(
                                    f'SELECT "ID", "FaceBox" FROM "EyeOfWebFaceID" WHERE "ID" IN ({query_placeholders})',
                                    tuple(face_ids_in_image),
                                )
                                face_boxes_results = cursor.fetchall()
                                face_box_map = {
                                    fb["ID"]: fb["FaceBox"] for fb in face_boxes_results
                                }
                                drawn_boxes = 0
                                for face_meta in faces_metadata:
                                    face_id_in_image = face_meta.get("id")
                                    facebox_bytes = face_box_map.get(face_id_in_image)
                                    if facebox_bytes:
                                        try:
                                            is_target = (
                                                face_id_in_image in target_group_ids
                                            )
                                            is_related = (
                                                face_id_in_image in face_group_ids
                                            )
                                            if is_target or is_related:
                                                facebox = np.array(
                                                    ast.literal_eval(facebox_bytes),
                                                    dtype=np.float32,
                                                )
                                                if len(facebox) == 4:
                                                    x1, y1, x2, y2 = map(int, facebox)
                                                    x1, y1 = max(0, x1), max(0, y1)
                                                    x2, y2 = min(
                                                        img_width - 1, x2
                                                    ), min(img_height - 1, y2)
                                                    if x2 > x1 and y2 > y1:
                                                        color = (
                                                            (0, 255, 0)
                                                            if is_target
                                                            else (0, 0, 255)
                                                        )
                                                        thickness = 3
                                                        cv2.rectangle(
                                                            cv_image,
                                                            (x1, y1),
                                                            (x2, y2),
                                                            color,
                                                            thickness,
                                                        )
                                                        drawn_boxes += 1
                                        except Exception as fb_proc_err:
                                            current_app.logger.error(
                                                f"{log_prefix} Error processing facebox {face_id_in_image}: {fb_proc_err}"
                                            )
                                current_app.logger.debug(
                                    f"{log_prefix} Drew {drawn_boxes} boxes."
                                )

                            # Encode to base64
                            success_encode, buffer = cv2.imencode(".jpg", cv_image)
                            if success_encode:
                                processed_image_b64 = base64.b64encode(buffer).decode(
                                    "utf-8"
                                )
                                current_app.logger.debug(
                                    f"{log_prefix} Image successfully processed and encoded."
                                )
                                processed_successfully += 1
                            else:
                                current_app.logger.error(
                                    f"{log_prefix} Failed to encode processed image."
                                )
                                is_placeholder = True
                                placeholder_text = "Encode H."
                        except Exception as img_proc_err:
                            current_app.logger.error(
                                f"{log_prefix} Exception during image processing (boxes/encode): {img_proc_err}"
                            )
                            is_placeholder = True
                            placeholder_text = "İşleme Hatası"
                    else:
                        # Could not obtain image
                        current_app.logger.warning(
                            f"{log_prefix} Using placeholder as no valid image was obtained."
                        )
                        is_placeholder = True

                except Exception as outer_proc_error:
                    current_app.logger.error(
                        f"{log_prefix} Outer exception during image processing: {outer_proc_error}\n{traceback.format_exc()}"
                    )
                    is_placeholder = True
                    placeholder_text = "Genel Hata"

            # --- Create PDF Item ---
            if is_placeholder or not processed_image_b64:
                current_app.logger.warning(
                    f"{log_prefix} Final decision: Using placeholder ({placeholder_text})."
                )
                processed_image_b64 = create_placeholder_image(text=placeholder_text)
                used_placeholder_count += 1
                if not processed_image_b64:
                    current_app.logger.error(
                        f"{log_prefix} CRITICAL: Failed to create even placeholder image!"
                    )
                    processed_image_b64 = ""  # Use empty string as fallback

            # Format title with date
            title = f"Görsel ID: {image_id if image_id else '-'} - {image_title}"
            try:
                date_str = None
                if isinstance(detection_date, str):
                    try:
                        date_obj = datetime.datetime.fromisoformat(
                            detection_date.replace("Z", "+00:00")
                        )
                        date_str = date_obj.strftime("%d.%m.%Y %H:%M")
                    except ValueError:  # Handle non-ISO format if necessary
                        try:
                            date_obj = datetime.datetime.strptime(
                                detection_date, "%Y-%m-%d %H:%M:%S"
                            )
                            date_str = date_obj.strftime("%d.%m.%Y %H:%M")
                        except ValueError:
                            current_app.logger.warning(
                                f"{log_prefix} Unknown date format: {detection_date}"
                            )
                elif isinstance(detection_date, datetime.datetime):
                    date_str = detection_date.strftime("%d.%m.%Y %H:%M")
                if date_str:
                    title += f" ({date_str})"
            except Exception as date_fmt_err:
                current_app.logger.warning(
                    f"{log_prefix} Could not format detection date '{detection_date}': {date_fmt_err}"
                )

            # Format face info string
            face_info_str_parts = []
            for face in faces_metadata:
                f_id = face.get("id")
                f_type = (
                    "H"
                    if f_id in target_group_ids
                    else ("İ" if f_id in face_group_ids else "D")
                )
                face_info_str_parts.append(f"#{f_id}({f_type})")
            face_info_str = (
                ", ".join(face_info_str_parts) if face_info_str_parts else "Yok"
            )

            pdf_item = {
                "title": title,
                "image_data_b64": processed_image_b64,
                "image_url": original_url,
                "source_url": source_url,
                "hash": image_hash,
                "count": len(faces_metadata),
                "score": None,
                "gender": None,
                "age": None,
                "similarity": None,
                "comprehensive_info": {"faces_detected": face_info_str},
                "facebox": None,
            }
            pdf_data.append(pdf_item)

        # --- Loop End ---
        current_app.logger.info(
            f"[PDF_REL_REPORT] Loop finished. Processed: {processed_successfully}, Placeholders: {used_placeholder_count}/{total_meta_items}"
        )

    except (Exception, psycopg2.DatabaseError) as error:
        current_app.logger.error(
            f"Error preparing relationship PDF data: {error}\n{traceback.format_exc()}"
        )
        flash("PDF rapor verileri hazırlanırken bir hata oluştu.", "danger")
        if conn:
            g.db_tools.releaseConnection(conn, cursor)
        return redirect(
            url_for(
                "web.face_relationship_details",
                target_face_id=target_face_id,
                face_id=face_id,
            )
        )
    finally:
        if conn:
            g.db_tools.releaseConnection(conn, cursor)

    # --- Generate and Send PDF ---
    if not pdf_data:
        flash("Rapor için işlenecek görsel bulunamadı.", "warning")
        return redirect(
            url_for(
                "web.face_relationship_details",
                target_face_id=target_face_id,
                face_id=face_id,
            )
        )

    pdf_bytes = generate_pdf_report(search_type, username, pdf_data)

    if pdf_bytes is None:
        flash("PDF raporu oluşturulurken bir hata oluştu.", "danger")
        return redirect(
            url_for(
                "web.face_relationship_details",
                target_face_id=target_face_id,
                face_id=face_id,
            )
        )

    report_filename = f"EyeOfWeb_IliskiDetay_{target_face_id}_{face_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=report_filename,
    )


# Yeni Rota: Yüz Tespit Raporu İndirme
@web_bp.route("/download/detection_report", methods=["GET"])
@login_required
def download_detection_report():
    """Son yüz tespiti sonuçları için PDF raporu oluşturur ve indirir."""
    report_data = session.get("last_detection_report_data")

    if not report_data:
        flash(
            "İndirilecek rapor verisi bulunamadı veya oturum süresi doldu.", "warning"
        )
        return redirect(url_for("web.face_detection"))

    search_type = report_data.get("search_type", "Yüz Tespiti")
    username = report_data.get("username", "Bilinmeyen Kullanıcı")
    pdf_data_list = report_data.get("pdf_data", [])

    if not pdf_data_list:
        flash("Rapor için işlenecek geçerli yüz verisi bulunamadı.", "warning")
        return redirect(url_for("web.face_detection"))

    # PDF Raporunu Oluştur
    pdf_bytes = generate_pdf_report(search_type, username, pdf_data_list)

    if pdf_bytes is None:
        flash("PDF raporu oluşturulurken bir hata oluştu.", "danger")
        return redirect(url_for("web.face_detection"))

    # PDF dosyasını kullanıcıya gönder
    report_filename = (
        f"EyeOfWeb_YuzTespit_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=report_filename,
    )


# Yeni Rota: Yüz Karşılaştırma Raporu İndirme
@web_bp.route("/download/comparison_report", methods=["GET"])
@login_required
def download_comparison_report():
    """Son yüz karşılaştırma sonuçları için PDF raporu oluşturur ve indirir."""
    report_data = session.get("last_comparison_report_data")

    if not report_data:
        flash(
            "İndirilecek rapor verisi bulunamadı veya oturum süresi doldu.", "warning"
        )
        return redirect(url_for("web.face_comparison"))

    search_type = report_data.get("search_type", "Yüz Karşılaştırma")
    username = report_data.get("username", "Bilinmeyen Kullanıcı")
    pdf_data_list = report_data.get("pdf_data", [])
    comparison_details = report_data.get(
        "comparison_info", None
    )  # Get comparison details

    if not pdf_data_list:
        flash("Rapor için işlenecek geçerli görsel verisi bulunamadı.", "warning")
        return redirect(url_for("web.face_comparison"))

    # PDF Raporunu Oluştur (comparison_info ile birlikte)
    pdf_bytes = generate_pdf_report(
        search_type, username, pdf_data_list, comparison_info=comparison_details
    )

    if pdf_bytes is None:
        flash("PDF raporu oluşturulurken bir hata oluştu.", "danger")
        return redirect(url_for("web.face_comparison"))

    # PDF dosyasını kullanıcıya gönder
    report_filename = f"EyeOfWeb_YuzKarsilastirma_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=report_filename,
    )


@web_bp.route("/login_failed")  # Example route, might be replaced
def login_failed():
    return "Login failed. Please check credentials.", 401


@web_bp.route("/about")
@login_required
def about():
    """Hakkında sayfasını gösterir."""
    return render_template("about.html")
