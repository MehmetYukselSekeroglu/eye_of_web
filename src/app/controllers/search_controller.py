#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app import face_app
from flask import current_app, g
import numpy as np
import cv2
import time
import base64
import traceback
from lib.face_detection import extract_and_encode_faces, draw_face_box
from lib.url_parser import prepare_url
from lib.url_image_download import get_ImageFromUrl
import datetime
from PIL import Image, ImageDraw
import html
import sys
import json
from lib.compress_tools import decompress_image

class SearchController:
    """Arama işlemlerini yöneten controller"""
    
    @staticmethod
    def search_faces(search_params, page=1, per_page=50):
        """Yüz arama işlemini gerçekleştirir (sayfalanmış)"""
        results = []
        total_count = 0
        
        print(f"[CONTROLLER search_faces] Params: {search_params}, Page: {page}, PerPage: {per_page}")
        
        # Arama parametrelerini doğrula
        if not search_params:
            return False, "Arama parametreleri gerekli", [], 0
        
        # Tarih aralığı kontrolü
        start_date = search_params.get('start_date')
        end_date = search_params.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                return False, "Başlangıç tarihi formatı geçersiz (YYYY-AA-GG olmalı)", [], 0
        
        if end_date:
            try:
                end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return False, "Bitiş tarihi formatı geçersiz (YYYY-AA-GG olmalı)", [], 0
        
        # Domain parametresi
        domain = search_params.get('domain', '')
        
        # Risk seviyesi parametresi
        risk_level = search_params.get('risk_level', '')
        
        # Kategori parametresi
        category = search_params.get('category', '')
        
        # Veritabanından yüz bilgilerini çek (sayfalanmış)
        try:
            # Call db_tools method with pagination args
            query_result, total_count = g.db_tools.searchFaces(
                domain=domain,
                start_date=start_date,
                end_date=end_date,
                risk_level=risk_level,
                category=category,
                page=page,
                per_page=per_page
            )
            
            print(f"[CONTROLLER search_faces] DB Result: len(query_result)={len(query_result)}, total_count={total_count}")
            
            if not query_result and total_count == 0:
                # No results found at all
                return True, "Sonuç bulunamadı", query_result, total_count
            
            # Results found (potentially empty list for this specific page, but total_count > 0)
            return True, "Arama başarılı", query_result, total_count
        except Exception as e:
            # Return 0 for total_count on error
            return False, f"Arama sırasında hata oluştu: {str(e)}", [], 0
    
    @staticmethod
    def search_by_image(image_data, threshold=0.6, algorithm='cosine', use_cuda=False, search_whitelist=False, search_egm=False):
        """Yüklenen görseldeki yüzlere göre arama yapar"""
        # Görsel verilerini kontrol et
        if image_data is None or image_data.size == 0:
            return False, "Görsel verisi gerekli", []
        
        try:
            # InsightFace uygulamasını al
            face_analyzer = None
            
            # 1. Global değişken üzerinden
            if face_app is not None:
                face_analyzer = face_app
            
            # 2. Flask current_app üzerinden (performans için tercih edilir)
            if face_analyzer is None:
                try:
                    if hasattr(current_app, 'face_app') and current_app.face_app is not None:
                        face_analyzer = current_app.face_app
                except Exception as app_error:
                    print(f"Flask uygulamasına erişim hatası: {str(app_error)}")
                    traceback.print_exc()
            
            # Eğer face_analyzer hala None ise, kullanıcıya hata mesajı dönüyor,
            # sistem tekrar başlatılana kadar bekleniyor
            if face_analyzer is None:
                return False, "Yüz tanıma sistemi başlatılmamış. Lütfen uygulamayı yeniden başlatın.", []
            
            # Görseldeki yüzleri tespit et
            print("Görseldeki yüzler tespit ediliyor...")
            detected_faces = face_analyzer.get(image_data)
            
            # Hiç yüz tespit edilmediyse
            if detected_faces is None or len(detected_faces) == 0:
                return False, "Görselde yüz tespit edilemedi", []
            
            # Birden fazla yüz tespit edilirse hata döndür
            if len(detected_faces) > 1:
                return False, "Görsel birden fazla yüz içeriyor. Lütfen sadece tek yüz içeren bir görsel yükleyin.", []
            
            print(f"{len(detected_faces)} adet yüz tespit edildi.")
            
            # Veritabanındaki yüzlerle karşılaştır
            results = []
            whitelist_results = []
            egm_results = []
            
            for face in detected_faces:
                # Normal site yüzlerini ara
                try:
                    # algorithm ve use_cuda parametrelerini ilet
                    similar_faces = g.db_tools.findSimilarFacesWithImages(
                        face_embedding=face.embedding,
                        threshold=threshold,
                        algorithm=algorithm,
                        use_cuda=use_cuda
                    )
                    if similar_faces is not None and len(similar_faces) > 0:
                        results.extend(similar_faces)
                except Exception as db_error:
                    # Veritabanı hatası oluştuğunda, ana hataya dönme
                    if "password authentication failed" in str(db_error):
                        return False, f"Veritabanı bağlantı hatası: Kullanıcı adı veya şifre hatalı. Lütfen yapılandırma ayarlarını kontrol edin.", []
                    elif "connection to server" in str(db_error):
                        return False, f"Veritabanı sunucusuna bağlanılamadı: {str(db_error)}", []
                    else:
                        print(f"Veritabanı hatası: {str(db_error)}")
                        traceback.print_exc()
                        return False, f"Veritabanı sorgusu sırasında hata: {str(db_error)}", []
                
                # WhiteList yüzlerini ara
                if search_whitelist:
                    try:
                        # algorithm ve use_cuda parametrelerini ilet
                        similar_whitelist_faces = g.db_tools.findSimilarWhiteListFaces(
                            face_embedding=face.embedding,
                            threshold=threshold,
                            algorithm=algorithm,
                            use_cuda=use_cuda
                        )
                        if similar_whitelist_faces is not None and len(similar_whitelist_faces) > 0:
                            # Whitelist kaynak bilgisini ekle
                            for face_result in similar_whitelist_faces:
                                face_result['source'] = 'whitelist'
                                # Tespit skoru ekle (eğer yoksa)
                                if 'detection_score' not in face_result and 'face_score' in face_result:
                                    face_result['detection_score'] = face_result['face_score']
                            whitelist_results.extend(similar_whitelist_faces)
                    except Exception as wl_error:
                        print(f"Beyaz liste arama hatası: {str(wl_error)}")
                        traceback.print_exc()

                # EGM arananlar listesini ara
                if search_egm:
                    try:
                        # algorithm ve use_cuda parametrelerini ilet
                        similar_egm_faces = g.db_tools.findSimilarEgmFaces(
                            face_embedding=face.embedding,
                            threshold=threshold,
                            algorithm=algorithm,
                            use_cuda=use_cuda
                        )
                        if similar_egm_faces is not None and len(similar_egm_faces) > 0:
                            # EGM kaynak bilgisini ekle
                            for face_result in similar_egm_faces:
                                face_result['source'] = 'egm'
                                # Tespit skoru ekle (eğer yoksa)
                                if 'detection_score' not in face_result and 'face_score' in face_result:
                                    face_result['detection_score'] = face_result['face_score']
                            egm_results.extend(similar_egm_faces)
                    except Exception as egm_error:
                        print(f"EGM arananlar arama hatası: {str(egm_error)}")
                        traceback.print_exc()
            
            # Tüm sonuçları birleştir
            combined_results = results + whitelist_results + egm_results
            
            if len(combined_results) == 0:
                return True, "Eşleşen yüz bulunamadı", []
            
            # Her bir sonuç için URL ve resim hazırla
            for result in combined_results:
                # Whitelist/EGM sonuçlarını şimdilik atla (veya özel işlem yap)
                if result.get("source") in ["whitelist", "egm"]:
                    result["image_url"] = None 
                    result["image_data"] = None
                    result.pop('image_mime_type', None)
                    result.pop('use_default_image', None)
                    result.pop('image_error', None)
                    continue

                # --- URL veya DB'den Resim Getirme (DB Fallback ile) --- 
                face_id_log = result.get("id", "N/A")
                img_protocol = result.get("image_protocol")
                img_domain = result.get("image_domain")
                img_path = result.get("image_path")
                image_id_from_main = result.get("image_id") 

                result['image_url'] = None # Başlangıçta None yap
                result['image_data'] = None
                result['image_mime_type'] = None
                result['use_default_image'] = True # Başlangıçta varsayılanı kullan
                result.pop('image_error', None) # Eski hatayı temizle
                final_error_message = None

                print(f"--- Processing FaceID: {face_id_log} (ImageID: {image_id_from_main}) ---")

                # 1. DB'den ImageID ile Dene (Öncelikli)
                if image_id_from_main is not None:
                    print(f"  INFO: Attempting DB fetch first for ImageID {image_id_from_main}.")
                    try:
                        success_db, img_binary_db = g.db_tools.getImageBinaryByID(image_id_from_main)
                        if success_db and img_binary_db:
                            print(f"  SUCCESS: DB fetch successful for ImageID {image_id_from_main}")
                            try:
                                # Decompress işlemi eklendi
                                decompressed_png_binary = decompress_image(img_binary_db)
                                if decompressed_png_binary:
                                    # Dekompres edilmiş PNG verisini decode et
                                    image_np = cv2.imdecode(np.frombuffer(decompressed_png_binary, np.uint8), cv2.IMREAD_COLOR)
                                    if image_np is None:
                                        raise ValueError("Dekompres edilmiş PNG verisi cv2 ile dekode edilemedi")
                                    
                                    # Encode the decompressed image to Base64 PNG
                                    success_encode, buffer = cv2.imencode('.png', image_np)
                                    if not success_encode:
                                        raise ValueError("Dekompres edilmiş PNG verisi Base64'e kodlanamadı")

                                    image_data_b64 = base64.b64encode(buffer).decode('utf-8')
                                    result['image_data'] = image_data_b64
                                    result['image_mime_type'] = 'image/png' # Decompress sonrası PNG döner
                                    result['use_default_image'] = False # Mark DB success
                                    final_error_message = None # Clear any prior error (like URL error)

                                else:
                                    raise ValueError("decompress_image boş veri döndürdü")
                            except Exception as decompress_err:
                                print(f"  ERROR: Decompression/Encoding failed for ImageID {image_id_from_main}: {decompress_err}")
                                traceback.print_exc()
                                # Ensure use_default_image remains True if processing fails
                                result['use_default_image'] = True
                                if not final_error_message: # Avoid overwriting a more specific DB fetch error
                                    final_error_message = f"Veritabanı resmi işlenemedi: {decompress_err}"
                                image_np = None # Ensure image_np is None if decompression fails
                        else:
                            print(f"  INFO: DB fetch failed or no data for ImageID {image_id_from_main}. Will try URL next.")
                            # DB'de bulunamadı veya hata oluştu, URL'yi deneyeceğiz. Hata mesajı henüz ayarlanmıyor.
                            result['use_default_image'] = True # Şimdilik varsayılan, URL başarılı olursa değişecek
                    except Exception as db_err:
                        print(f"  ERROR: DB fetch exception for ImageID {image_id_from_main}: {db_err}")
                        traceback.print_exc()
                        final_error_message = f"Veritabanı hatası: {db_err}"
                        result['use_default_image'] = True # DB hatası, URL denenecek ama muhtemelen varsayılan kalacak
                else:
                     print(f"  INFO: ImageID is None for FaceID {face_id_log}. Will try URL next.")
                     result['use_default_image'] = True # ImageID yok, URL denenmeli
                
                # 2. URL'den Dene (DB Başarısız Olduysa veya ImageID Yoksa)
                # Sadece DB denemesi başarısız olduysa veya hiç denenmediyse (ImageID yoksa) URL'yi dene.
                if result['use_default_image']: 
                    if img_protocol and img_domain and img_path:
                        result["image_url"] = f"{img_protocol}://{img_domain}/{img_path}"
                        result["source_url"] = f"{img_protocol}://{img_domain}" # source_url hala mantıklı olabilir
                        result['use_default_image'] = False # URL var, varsayılanı kullanma
                        print(f"  SUCCESS: image_url created as fallback: {result['image_url']}")
                        final_error_message = None # URL başarılıysa önceki DB hatasını temizle
                    else:
                        print(f"  FAILED: URL components also missing or DB failed previously.")
                        # Hem DB başarısız/yok hem de URL bilgisi eksikse hata mesajını ayarla
                        if not final_error_message: # Eğer DB hatası yoksa, URL hatası mesajını ekle
                           final_error_message = "Resim veritabanında bulunamadı ve URL bilgisi eksik."
                        result['use_default_image'] = True # Varsayılana dön
                
                # 3. Son Durum: Ne DB Ne URL Başarılıysa
                # Bu durum yukarıdaki mantıkla zaten handle ediliyor. 
                # result['use_default_image'] True ise ve final_error_message ayarlanmışsa hata gösterilecek.
                # Eğer final_error_message hala None ise (örn. ImageID yoktu ama URL de yoktu) genel hata ver.
                if result['use_default_image'] and not final_error_message:
                    final_error_message = "Resim kaynağı bilgisi bulunamadı."
                    print(f"  FAILED: No ImageID and no valid URL components for FaceID {face_id_log}. Using default.")

                # Hata mesajını ayarla (eğer varsa)
                if final_error_message:
                    result['image_error'] = final_error_message
                
                # Gereksiz alanları temizle (opsiyonel)
                # result.pop(...) 
                print(f"--- Finished Processing FaceID: {face_id_log} ---")

            # Benzerlik oranına göre sonuçları sırala
            combined_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
            
            # Return only three values: success, message, results
            return True, f"{len(combined_results)} eşleşme bulundu", combined_results
        except Exception as e:
            print(f"Görsel işleme hatası: {str(e)}")
            traceback.print_exc()
            # Return only three values on error as well
            return False, f"Görsel işleme sırasında hata oluştu: {str(e)}", []
    
    @staticmethod
    def search_by_embedding(face_embedding, threshold=0.6):
        """Yüz gömme vektörüne göre benzer yüzleri arar"""
        results = []
        
        # Gömme vektörünü kontrol et
        if face_embedding is None:
            return False, "Yüz gömme vektörü gerekli", []
        
        try:
            # Flask'ın g objesinden db_tools'a erişmek için
            from flask import g
            
            # Veritabanında benzer yüzleri ara
            similar_faces = g.db_tools.findSimilarFacesWithImages(face_embedding=face_embedding, threshold=threshold)
            
            if similar_faces is None or len(similar_faces) == 0:
                return True, "Eşleşen yüz bulunamadı", []
            
            # Her sonuç için image_url ve kaynak URL'yi düzenle
            for face in similar_faces:
                # Initialize fields
                face['image_url'] = None
                face['image_data'] = None
                face['image_mime_type'] = None
                face['use_default_image'] = True # Default to true
                face.pop('image_error', None) # Clear previous error
                final_error_message = None

                # Get components for URL and DB fallback
                img_protocol = face.get('image_protocol')
                img_domain = face.get('image_domain')
                img_path = face.get('image_path')
                image_id_from_main = face.get('image_id') # Get the ImageID

                # --- Image Source Logic ---
                # 1. Try building URL first
                if img_protocol and img_domain and img_path:
                    face['image_url'] = f"{img_protocol}://{img_domain}/{img_path}"
                    face['use_default_image'] = False # URL is available
                    print(f"DEBUG [search_by_embedding]: Using image_url: {face['image_url']}")
                else:
                    print(f"DEBUG [search_by_embedding]: URL components missing for face {face.get('id')}. Trying DB fallback.")
                    # 2. If URL components missing, try DB fallback using ImageID
                    if image_id_from_main is not None:
                        try:
                            success_db, img_binary_db = g.db_tools.getImageBinaryByID(image_id_from_main)
                            if success_db and img_binary_db:
                                print(f"DEBUG [search_by_embedding]: DB fetch successful for ImageID {image_id_from_main}")
                                try:
                                    # <<< YENİ: Decompress et >>>
                                    decompressed_binary = decompress_image(img_binary_db)
                                    if not decompressed_binary:
                                        raise ValueError("Decompression returned empty data.")

                                    # Dekompres edilmiş veriyi Base64'e çevir
                                    face['image_data'] = base64.b64encode(decompressed_binary).decode('utf-8')
                                    face['image_mime_type'] = 'image/png' # Decompress sonrası PNG
                                    
                                    # <<< Eski MIME türü belirleme kaldırıldı >>>
                                    # if img_binary_db.startswith(b'\x89PNG\r\n\x1a\n'): 
                                    #     face['image_mime_type'] = 'image/png'
                                    # elif img_binary_db.startswith(b'\xff\xd8\xff'): 
                                    #     face['image_mime_type'] = 'image/jpeg'
                                    # else: 
                                    #     face['image_mime_type'] = 'image/png' # Default assumption
                                    
                                    face['use_default_image'] = False # DB fetch successful
                                    print(f"DEBUG [search_by_embedding]: Using image_data from DB. MIME: {face['image_mime_type']}")
                                
                                except Exception as process_err: # Decompress veya encode hatası
                                    print(f"ERROR [search_by_embedding]: Failed to decompress/encode DB image for ImageID {image_id_from_main}: {process_err}")
                                    final_error_message = "Veritabanı resmi işlenemedi."
                                    face['use_default_image'] = True # Processing failed
                            else:
                                print(f"DEBUG [search_by_embedding]: DB fetch failed or no data for ImageID {image_id_from_main}.")
                                final_error_message = "Resim veritabanında bulunamadı."
                                face['use_default_image'] = True # DB fetch failed
                        except Exception as db_err:
                            print(f"ERROR [search_by_embedding]: DB fetch exception for ImageID {image_id_from_main}: {db_err}")
                            traceback.print_exc()
                            final_error_message = f"Veritabanı hatası: {db_err}"
                            face['use_default_image'] = True # DB fetch exception
                    else:
                         print(f"DEBUG [search_by_embedding]: ImageID is None for face {face.get('id')}. Cannot fallback to DB.")
                         final_error_message = "Resim URL bilgisi eksik ve veritabanı ID'si yok."
                         face['use_default_image'] = True # Cannot fetch from DB

                # 3. Set error message if default is still used
                if face['use_default_image']:
                     if not final_error_message: # Generic message if no specific error occurred
                          final_error_message = "Resim URL veya veritabanı yoluyla alınamadı."
                     face['image_error'] = final_error_message
                     print(f"DEBUG [search_by_embedding]: Using default image for face {face.get('id')}. Reason: {final_error_message}")


                # Kaynak URL'yi oluştur (Bu kısım değişmedi)
                if face.get('protocol') and face.get('domain'):
                    face['source_url'] = f"{face['protocol']}://{face['domain']}"
                    if face.get('url_path'):
                        face['source_url'] += f"/{face['url_path']}"
                else: 
                    face['source_url'] = None
                
                # DEBUGGING: Print the final face dictionary for the template
                print(f"DEBUG [search_by_embedding]: Final face data for template:\n{json.dumps(face, indent=2, default=str)}")

            return True, f"{len(similar_faces)} adet eşleşme bulundu", similar_faces
        except Exception as e:
            print(f"Benzerlik araması sırasında hata: {str(e)}")
            traceback.print_exc()
            return False, f"Benzer yüzler aranırken hata oluştu: {str(e)}", []
                
    @staticmethod
    def search_whitelist_faces(search_params):
        """Beyaz liste yüzlerini arama"""
        results = []
        
        # Arama parametrelerini doğrula
        if not search_params:
            return False, "Arama parametreleri gerekli", []
        
        # Tarih aralığı kontrolü
        start_date = search_params.get('start_date')
        end_date = search_params.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                return False, "Başlangıç tarihi formatı geçersiz (YYYY-AA-GG olmalı)", []
        
        if end_date:
            try:
                end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return False, "Bitiş tarihi formatı geçersiz (YYYY-AA-GG olmalı)", []
        
        # Diğer parametreleri güvenli şekilde al
        face_name = search_params.get('face_name', '')
        institution = search_params.get('institution', '')
        category = search_params.get('category', '')
        
        # SQL enjeksiyonunu önlemek için parametreleri temizle
        # Veritabanından yüz bilgilerini çek
        try:
            query_result = g.db_tools.searchWhiteListFaces(
                face_name=face_name,
                institution=institution,
                category=category,
                start_date=start_date,
                end_date=end_date
            )
            
            if not query_result:
                return True, "Sonuç bulunamadı", []
            
            # Sonuçları temizle ve döndür
            sanitized_results = []
            for result in query_result:
                # Döndürülen verileri XSS saldırılarına karşı temizle
                if 'face_name' in result and result['face_name']:
                    result['face_name'] = html.escape(str(result['face_name']))
                if 'institution' in result and result['institution']:
                    result['institution'] = html.escape(str(result['institution']))
                if 'category' in result and result['category']:
                    result['category'] = html.escape(str(result['category']))
                sanitized_results.append(result)
            
            return True, f"{len(sanitized_results)} adet sonuç bulundu", sanitized_results
        except Exception as e:
            print(f"WhiteList arama hatası: {str(e)}")
            return False, f"Arama sırasında hata oluştu", []
            
    @staticmethod
    def search_external_faces(search_params):
        """Dış yüz deposundaki yüzleri arama"""
        results = []
        
        # Arama parametrelerini doğrula
        if not search_params:
            return False, "Arama parametreleri gerekli", []
        
        # Tarih aralığı kontrolü
        start_date = search_params.get('start_date')
        end_date = search_params.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                return False, "Başlangıç tarihi formatı geçersiz (YYYY-AA-GG olmalı)", []
        
        if end_date:
            try:
                end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return False, "Bitiş tarihi formatı geçersiz (YYYY-AA-GG olmalı)", []
        
        # Yüz adı parametresi
        face_name = search_params.get('face_name', '')
        
        # Alarm parametresi
        alarm = search_params.get('alarm')
        if alarm is not None:
            if isinstance(alarm, str) and alarm.lower() in ['true', '1', 'yes']:
                alarm = True
            elif isinstance(alarm, str) and alarm.lower() in ['false', '0', 'no']:
                alarm = False
            elif not isinstance(alarm, bool):
                alarm = None
        
        # Veritabanından yüz bilgilerini çek
        try:
            query_result = g.db_tools.searchExternalFaces(
                face_name=face_name,
                start_date=start_date,
                end_date=end_date,
                alarm=alarm
            )
            
            if not query_result:
                return True, "Sonuç bulunamadı", []
            
            # Sonuçları döndür
            return True, f"{len(query_result)} adet sonuç bulundu", query_result
        except Exception as e:
            return False, f"Arama sırasında hata oluştu: {str(e)}", []
            
    @staticmethod
    def search_egm_arananlar(search_params):
        """EGM arananlar listesindeki yüzleri arama"""
        results = []
        
        # Arama parametrelerini doğrula
        if not search_params:
            return False, "Arama parametreleri gerekli", []
        
        # Tarih aralığı kontrolü
        start_date = search_params.get('start_date')
        end_date = search_params.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                return False, "Başlangıç tarihi formatı geçersiz (YYYY-AA-GG olmalı)", []
        
        if end_date:
            try:
                end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return False, "Bitiş tarihi formatı geçersiz (YYYY-AA-GG olmalı)", []
        
        # Diğer parametreler
        face_name = search_params.get('face_name', '')
        organizer = search_params.get('organizer', '')
        organizer_level = search_params.get('organizer_level', '')
        
        # Veritabanından yüz bilgilerini çek
        try:
            query_result = g.db_tools.searchEgmArananlar(
                face_name=face_name,
                organizer=organizer,
                organizer_level=organizer_level,
                start_date=start_date,
                end_date=end_date
            )
            
            if not query_result:
                return True, "Sonuç bulunamadı", []
            
            # Sonuçları temizle ve döndür
            sanitized_results = []
            for result in query_result:
                # Döndürülen verileri XSS saldırılarına karşı temizle
                if 'FaceName' in result and result['FaceName']:
                    result['FaceName'] = html.escape(str(result['FaceName']))
                if 'Organizer' in result and result['Organizer']:
                    result['Organizer'] = html.escape(str(result['Organizer']))
                if 'OrganizerLevel' in result and result['OrganizerLevel']:
                    result['OrganizerLevel'] = html.escape(str(result['OrganizerLevel']))
                if 'BirthDateAndLocation' in result and result['BirthDateAndLocation']:
                    result['BirthDateAndLocation'] = html.escape(str(result['BirthDateAndLocation']))
                sanitized_results.append(result)
            
            return True, f"{len(sanitized_results)} adet sonuç bulundu", sanitized_results
        except Exception as e:
            return False, f"Arama sırasında hata oluştu", []
    
    @staticmethod
    def detect_faces(image_data):
        """
        Yüklenen görseldeki yüzleri tespit eder ve bilgilerini döndürür
        
        Args:
            image_data: NumPy dizisi olarak görüntü
            
        Returns:
            success: İşlem başarılı mı?
            message: İşlem sonucu mesajı
            results: Tespit edilen yüzler hakkında bilgiler
        """
        # Görsel verilerini kontrol et
        if image_data is None or image_data.size == 0:
            return False, "Görsel verisi gerekli", []
        
        try:
            # Face analyzer'ı al - birden fazla yöntemle deneme
            face_analyzer = None
            
            # 1. Flask current_app üzerinden deneme
            try:
                from flask import current_app
                face_analyzer = current_app.face_app
                if face_analyzer is None:
                    face_analyzer = current_app.config.get('FACE_ANALYZER')
            except Exception as e:
                print(f"Flask app'ten analyzer alınamadı: {str(e)}")
                
            # 2. Global değişkenden almayı dene
            if face_analyzer is None:
                try:
                    import sys
                    # Global değişken "face_app"'e erişmeyi dene
                    if 'face_app' in globals():
                        face_analyzer = globals()['face_app']
                    # Modül seviyesinde değişkene erişmeyi dene
                    elif hasattr(sys.modules['__main__'], 'face_app'):
                        face_analyzer = sys.modules['__main__'].face_app
                    # app modülünden almayı dene
                    elif hasattr(sys.modules.get('app', None), 'face_app'):
                        face_analyzer = sys.modules['app'].face_app
                except Exception as e:
                    print(f"Global değişkenden analyzer alınamadı: {str(e)}")
            
            # 3. Son çare olarak yeni bir analyzer oluştur
            if face_analyzer is None:
                try:
                    print("Yeni InsightFace analyzer başlatılıyor...")
                    from lib.init_insightface import initilate_insightface
                    face_analyzer = initilate_insightface()
                except Exception as e:
                    print(f"Yeni analyzer oluşturulamadı: {str(e)}")
            
            # Analyzer hala None ise, hata döndür
            if face_analyzer is None:
                return False, "Yüz tanıma sistemi başlatılamadı. Lütfen yöneticinizle iletişime geçin.", None
            
            # Görseldeki yüzleri tespit et
            print("Görseldeki yüzler tespit ediliyor...")
            detected_faces = face_analyzer.get(image_data)
            
            # Hiç yüz tespit edilmediyse
            if detected_faces is None or len(detected_faces) == 0:
                return False, "Görselde yüz tespit edilemedi", []
            
            # Birden fazla yüz tespit edilirse hata döndür
            if len(detected_faces) > 1:
                return False, "Görsel birden fazla yüz içeriyor. Lütfen sadece tek yüz içeren bir görsel yükleyin.", []
            
            print(f"{len(detected_faces)} adet yüz tespit edildi.")
            
            # Tespit edilen yüzlerin bilgilerini döndür
            import cv2
            import base64
            import numpy as np
            
            results = []
            
            for idx, face in enumerate(detected_faces):
                # Yüz kutusu bilgilerini al
                bbox = face.bbox.astype(int).tolist()  # [x1, y1, x2, y2]
                facebox_data = {
                    "x1": bbox[0],
                    "y1": bbox[1],
                    "x2": bbox[2],
                    "y2": bbox[3]
                }
                
                # Yüz görüntüsünü kırp
                x1, y1, x2, y2 = bbox
                # Taşmaları önlemek için sınırları kontrol et
                height, width = image_data.shape[:2]
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(width, x2)
                y2 = min(height, y2)
                
                face_img = image_data[y1:y2, x1:x2]
                
                # Görüntüyü base64 formatına dönüştür
                _, buffer = cv2.imencode(".jpg", face_img)
                face_img_base64 = base64.b64encode(buffer).decode('utf-8')
                
                # Benzerlik skorları için boş dizi
                landmarks = None
                if hasattr(face, 'landmark_2d_106') and face.landmark_2d_106 is not None:
                    landmarks = face.landmark_2d_106.astype(int).tolist()
                
                # Yüz bilgilerini diziye ekle
                face_result = {
                    "id": idx + 1,
                    "detection_score": float(face.det_score),
                    "facebox": facebox_data,
                    "landmarks": landmarks,
                    "gender": "Erkek" if face.sex == 1 else "Kadın" if face.sex == 0 else "Bilinmiyor",
                    "age": int(face.age) if hasattr(face, 'age') else None,
                    "face_img": face_img_base64
                }
                
                results.append(face_result)
            
            # Görselin tamamına yüz kutularını çiz
            img_with_boxes = image_data.copy()
            for idx, face in enumerate(detected_faces):
                bbox = face.bbox.astype(int)
                cv2.rectangle(img_with_boxes, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)
                # Tespit skoru ve ID'yi ekle
                score = round(float(face.det_score), 2)
                cv2.putText(img_with_boxes, f"ID:{idx+1} Score:{score}", 
                            (bbox[0], bbox[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Kutu çizilmiş görseli base64'e dönüştür
            _, buffer = cv2.imencode(".jpg", img_with_boxes)
            full_img_base64 = base64.b64encode(buffer).decode('utf-8')
            
            return True, f"{len(detected_faces)} adet yüz tespit edildi", {
                "faces": results,
                "total_faces": len(detected_faces),
                "full_image": full_img_base64
            }
            
        except Exception as e:
            import traceback
            print(f"Yüz tespiti sırasında hata: {str(e)}")
            print(traceback.format_exc())
            return False, f"Yüz tespiti sırasında hata oluştu: {str(e)}", []
    
    @staticmethod
    def compare_faces(image1_data, image2_data, threshold=0.6):
        """İki görsel arasındaki yüzleri karşılaştırır"""
        if image1_data is None or image2_data is None:
            return False, "Lütfen iki görsel de yükleyin", None
        
        try:
            # Face analyzer'ı al - birden fazla yöntemle deneme
            face_analyzer = None
            
            # 1. Flask current_app üzerinden deneme
            try:
                from flask import current_app
                face_analyzer = current_app.face_app
                if face_analyzer is None:
                    face_analyzer = current_app.config.get('FACE_ANALYZER')
            except Exception as e:
                print(f"Flask app'ten analyzer alınamadı: {str(e)}")
                
            # 2. Global değişkenden almayı dene
            if face_analyzer is None:
                try:
                    import sys
                    # Global değişken "face_app"'e erişmeyi dene
                    if 'face_app' in globals():
                        face_analyzer = globals()['face_app']
                    # Modül seviyesinde değişkene erişmeyi dene
                    elif hasattr(sys.modules['__main__'], 'face_app'):
                        face_analyzer = sys.modules['__main__'].face_app
                    # app modülünden almayı dene
                    elif hasattr(sys.modules.get('app', None), 'face_app'):
                        face_analyzer = sys.modules['app'].face_app
                except Exception as e:
                    print(f"Global değişkenden analyzer alınamadı: {str(e)}")
            
            # 3. Son çare olarak yeni bir analyzer oluştur
            if face_analyzer is None:
                try:
                    print("Yeni InsightFace analyzer başlatılıyor...")
                    from lib.init_insightface import initilate_insightface
                    face_analyzer = initilate_insightface()
                except Exception as e:
                    print(f"Yeni analyzer oluşturulamadı: {str(e)}")
            
            # Analyzer hala None ise, hata döndür
            if face_analyzer is None:
                return False, "Yüz tanıma sistemi başlatılamadı. Lütfen yöneticinizle iletişime geçin.", None
            
            # Yüzleri tespit et - 1. görsel
            faces1 = face_analyzer.get(image1_data)
            
            # Yüzleri tespit et - 2. görsel
            faces2 = face_analyzer.get(image2_data)
            
            if len(faces1) == 0 and len(faces2) == 0:
                return False, "İki görselde de yüz tespit edilemedi", None
            elif len(faces1) == 0:
                return False, "1. görselde yüz tespit edilemedi", None
            elif len(faces2) == 0:
                return False, "2. görselde yüz tespit edilemedi", None
            
            # Görüntüleri BGR'den RGB'ye çevir (gösterme amaçlı)
            import cv2
            import numpy as np
            import base64
            
            # Yüz kutuları çiz - 1. görsel
            img1_with_boxes = image1_data.copy()
            for i, face in enumerate(faces1):
                box = face.bbox.astype(np.int32)
                color = (0, 255, 0)  # BGR, yeşil renk
                thickness = 2
                cv2.rectangle(img1_with_boxes, (box[0], box[1]), (box[2], box[3]), color, thickness)
                
                # Yüz ID'sini kutunun üzerine yaz
                cv2.putText(img1_with_boxes, f"#{i+1}", (box[0], box[1]-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, thickness)
            
            # Yüz kutuları çiz - 2. görsel
            img2_with_boxes = image2_data.copy()
            for i, face in enumerate(faces2):
                box = face.bbox.astype(np.int32)
                color = (0, 255, 0)  # BGR, yeşil renk
                thickness = 2
                cv2.rectangle(img2_with_boxes, (box[0], box[1]), (box[2], box[3]), color, thickness)
                
                # Yüz ID'sini kutunun üzerine yaz
                cv2.putText(img2_with_boxes, f"#{i+1}", (box[0], box[1]-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, thickness)
            
            # Full görseller için base64
            _, buffer1 = cv2.imencode('.jpg', img1_with_boxes)
            _, buffer2 = cv2.imencode('.jpg', img2_with_boxes)
            full_image1 = base64.b64encode(buffer1).decode('utf-8')
            full_image2 = base64.b64encode(buffer2).decode('utf-8')
            
            # Yüzleri karşılaştır
            threshold_percent = int(threshold * 100)
            total_matches = 0
            all_similarities = []  # Tüm benzerlik değerlerini toplamak için
            max_similarity = 0  # En yüksek benzerlik değeri
            
            results = []
            for i, face1 in enumerate(faces1):
                face_img1 = image1_data[int(face1.bbox[1]):int(face1.bbox[3]), 
                                       int(face1.bbox[0]):int(face1.bbox[2])]
                
                # Yüzü base64'e dönüştür
                _, buffer = cv2.imencode('.jpg', face_img1)
                face_img1_b64 = base64.b64encode(buffer).decode('utf-8')
                
                # Yüz 1 için cinsiyet ve yaş
                gender = "Erkek" if face1.sex == 1 else "Kadın"
                age = int(face1.age) if hasattr(face1, 'age') else None
                
                matches = []
                match_count = 0
                
                for j, face2 in enumerate(faces2):
                    face_img2 = image2_data[int(face2.bbox[1]):int(face2.bbox[3]), 
                                           int(face2.bbox[0]):int(face2.bbox[2])]
                    
                    # Yüzü base64'e dönüştür
                    _, buffer = cv2.imencode('.jpg', face_img2)
                    face_img2_b64 = base64.b64encode(buffer).decode('utf-8')
                    
                    # Yüz 2 için cinsiyet ve yaş
                    gender2 = "Erkek" if face2.sex == 1 else "Kadın"
                    age2 = int(face2.age) if hasattr(face2, 'age') else None
                    
                    # Benzerliği hesapla (kosinüs benzerliği)
                    from scipy.spatial.distance import cosine
                    similarity = 1 - cosine(face1.embedding, face2.embedding)
                    similarity_percent = int(similarity * 100)
                    
                    # Tüm benzerlik değerlerini kaydet
                    all_similarities.append(similarity_percent)
                    
                    # En yüksek benzerliği güncelle
                    if similarity >= threshold:
                        matches.append({
                            'face_id': j+1,
                            'similarity': similarity,
                            'similarity_percent': similarity_percent,
                            'face_img': face_img2_b64,
                            'gender': gender2,
                            'age': age2
                        })
                        match_count += 1
                        total_matches += 1
                
                # Sonuçları ekle
                results.append({
                    'face_id': i+1,
                    'face_img': face_img1_b64,
                    'gender': gender,
                    'age': age,
                    'matches': matches,
                    'match_count': match_count
                })
            
            # Ortalama benzerlik hesaplama
            avg_similarity = 0
            if all_similarities:
                avg_similarity = sum(all_similarities) / len(all_similarities)
            
            # Sonuç
            return True, f"{total_matches} adet yüz eşleşmesi bulundu.", {
                'full_image1': full_image1,
                'full_image2': full_image2,
                'faces1_count': len(faces1),
                'faces2_count': len(faces2),
                'total_matches': total_matches,
                'threshold': threshold,
                'threshold_percent': threshold_percent,
                'results': results,
                'avg_similarity': avg_similarity,
                'max_similarity': max_similarity
            }
        
        except Exception as e:
            import traceback
            print(f"Yüz karşılaştırma hatası: {str(e)}")
            print(traceback.format_exc())
            return False, f"Görsel işlenirken bir hata oluştu: {str(e)}", None
    
    @staticmethod
    def search_by_text(search_text, start_date=None, end_date=None, category=None):
        """
        Metin tabanlı arama yapar, resim başlıklarında Türkçe metinleri arar.
        Her görsel yalnızca bir kez gösterilir ve ilişkili tüm yüz ID'leri listelenir.
        
        Args:
            search_text: Aranacak metin
            start_date: Başlangıç tarihi (opsiyonel)
            end_date: Bitiş tarihi (opsiyonel)
            category: Kategori (opsiyonel)
            
        Returns:
            tuple: (başarı durumu, mesaj, sonuçlar)
        """
        results = []
        
        # Arama parametrelerini doğrula
        if not search_text or len(search_text.strip()) == 0:
            return False, "Arama metni gerekli", []
        
        # Tarih aralığı kontrolü
        if start_date:
            try:
                start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                return False, "Başlangıç tarihi formatı geçersiz (YYYY-AA-GG olmalı)", []
        
        if end_date:
            try:
                end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return False, "Bitiş tarihi formatı geçersiz (YYYY-AA-GG olmalı)", []
        
        # Arama metnini hazırla
        search_text = search_text.strip().lower()
        
        try:
            # Veritabanında resim başlıklarında arama yap
            # g.db_tools üzerinden arama yapan SQL sorgusunu çalıştır
            query = """
            SELECT i."ImageID", i."FaceID", t."Title" as image_title, bd."Domain" as domain, 
                   up."Path" as url_path, ip."Path" as image_path, id."Domain" as image_domain,
                   i."DetectionDate" as detection_date, i."RiskLevel" as risk_level,
                   i."Protocol" as protocol, i."ImageProtocol" as image_protocol
            FROM "ImageBasedMain" i
            JOIN "ImageTitleID" t ON i."ImageTitleID" = t."ID"
            JOIN "BaseDomainID" bd ON i."BaseDomainID" = bd."ID"
            LEFT JOIN "UrlPathID" up ON i."UrlPathID" = up."ID"
            LEFT JOIN "BaseDomainID" id ON i."ImageDomainID" = id."ID"
            LEFT JOIN "ImageUrlPathID" ip ON i."ImagePathID" = ip."ID"
            LEFT JOIN "WebSiteCategoryID" wc ON i."CategoryID" = wc."ID"
            WHERE LOWER(t."Title") LIKE %s
            """
            
            params = [f'%{search_text}%']
            
            # Filtreleme kriterleri ekle
            if start_date:
                query += " AND i.\"DetectionDate\" >= %s"
                params.append(start_date)
            
            if end_date:
                query += " AND i.\"DetectionDate\" <= %s"
                params.append(end_date)
            
            if category:
                query += " AND wc.\"Category\" = %s"
                params.append(category)
            
            # Tarihe göre sırala
            query += " ORDER BY i.\"DetectionDate\" DESC"
            
            # Sorguyu çalıştır
            search_results = g.db_tools.executeQuery(query, params)
            
            if not search_results or len(search_results) == 0:
                return True, "Eşleşen başlık bulunamadı", []
            
            # Sonuçları grupla (görsel başına bir sonuç olacak şekilde)
            grouped_results = {}
            
            for result in search_results:
                image_id_group_key = result.get('ImageID')
                
                # Initialize image variables for this specific group key
                img_data_for_group = None
                mime_type_for_group = None
                use_default_for_group = True # Default to true
                error_for_group = None
                image_url_for_group = None # Initialize image URL

                # Try getting image from URL first
                img_protocol = result.get('image_protocol', 'http')
                img_domain = result.get('image_domain')
                img_path = result.get('image_path')

                if img_domain and img_path:
                    image_url_for_group = f"{img_protocol}://{img_domain}/{img_path}"
                    # In text search, we don't download from URL, only use it if present
                    # If you need the image data here like in other searches, add download logic
                    # For now, we prioritize DB fetch if URL exists but we need data
                    pass # Keep URL, but DB might override data below if needed

                # If we don't have URL or need data (currently always need data from DB for text search display)
                # Try fetching from DB using ImageID
                if image_id_group_key is not None:
                    print(f"Text search: Attempting DB fetch for ImageID {image_id_group_key} (URL: {image_url_for_group})")
                    try:
                        success_db, img_binary = g.db_tools.getImageBinaryByID(image_id_group_key)
                        if success_db and img_binary:
                            try:
                                # <<< YENİ: Decompress et >>>
                                decompressed_binary = decompress_image(img_binary)
                                if not decompressed_binary:
                                    raise ValueError("Decompression returned empty data.")

                                # Dekompres edilmiş veriyi Base64'e çevir
                                img_data_for_group = base64.b64encode(decompressed_binary).decode('utf-8')
                                mime_type_for_group = 'image/png' # Decompress sonrası PNG

                                # <<< grouped_results'a ekle, 'face' değil >>>
                                if image_id_group_key in grouped_results:
                                    grouped_results[image_id_group_key]['image_data'] = img_data_for_group
                                    grouped_results[image_id_group_key]['image_mime_type'] = mime_type_for_group
                                    grouped_results[image_id_group_key]['use_default_image'] = False # DB fetch successful
                                    print(f"DEBUG [search_by_text]: Successfully processed DB image for group {image_id_group_key}.")

                            except Exception as db_process_err: # Decompress veya encode hatası
                                print(f"DB'den alınan resim (ID: {image_id_group_key}) işleme hatası: {db_process_err}")
                                error_for_group = "Resim verisi işlenemedi." # Daha genel hata
                                if image_id_group_key in grouped_results:
                                    grouped_results[image_id_group_key]['use_default_image'] = True # Processing failed
                                    grouped_results[image_id_group_key]['image_error'] = error_for_group # Hatayı kaydet
                        else:
                            print(f"Text search: DB'den resim alınamadı (ID: {image_id_group_key}).")
                            # Only set error if URL wasn't found either
                            if not image_url_for_group:
                                error_for_group = "Resim veritabanında bulunamadı."
                            # Keep use_default_for_group = True
                    except Exception as db_err:
                        print(f"Text search: DB'den resim alma hatası (ID: {image_id_group_key}): {db_err}")
                        traceback.print_exc()
                        # Only set error if URL wasn't found either
                        if not image_url_for_group:
                            error_for_group = "Veritabanı hatası."
                        # Keep use_default_for_group = True
                
                # If still no image data/url and no specific error yet
                elif not image_url_for_group:
                     print(f"Text search: Resim bilgisi eksik (ImageID: {image_id_group_key}, Domain: {img_domain}, Path: {img_path})")
                     error_for_group = "Resim kaynağı bilgisi yok."
                     use_default_for_group = True


                # Kaynak URL'yi oluştur
                source_url = None
                if result.get('domain'): # Use website domain/path for source link
                    protocol = result.get('protocol', 'http')
                    source_url_path = result.get('url_path', '') # Handle potential missing path
                    source_url = f"{protocol}://{result['domain']}"
                    if source_url_path:
                         source_url += f"/{source_url_path}"
                
                if image_id_group_key not in grouped_results:
                    # Yeni görsel öğesi oluştur
                    grouped_results[image_id_group_key] = {
                        'image_id': image_id_group_key,
                        'image_title': result.get('image_title'),
                        'domain': result.get('domain'),
                        'image_url': image_url_for_group, # Use URL if found
                        'image_data': img_data_for_group, # Use DB data if found
                        'image_mime_type': mime_type_for_group,
                        'use_default_image': use_default_for_group, # Use calculated default status
                        'image_error': error_for_group, # Use calculated error
                        'source_url': source_url,
                        'detection_date': result.get('detection_date').isoformat() if result.get('detection_date') else None,
                        'risk_level': result.get('risk_level'),
                        'face_ids': []
                    }
                
                # Görüntüdeki yüz ID'lerini ekle (assuming FaceID might be a single value or missing)
                face_id_value = result.get('FaceID')
                if face_id_value is not None and image_id_group_key in grouped_results:
                    # Ensure it's treated as a potential list element even if single
                    if isinstance(face_id_value, list):
                         for fid in face_id_value:
                              if fid not in grouped_results[image_id_group_key]['face_ids']:
                                   grouped_results[image_id_group_key]['face_ids'].append(fid)
                    elif face_id_value not in grouped_results[image_id_group_key]['face_ids']:
                         grouped_results[image_id_group_key]['face_ids'].append(face_id_value)

            # Gruplanmış sonuçları listeye çevir
            results = list(grouped_results.values())
            
            return True, f"{len(results)} adet görsel bulundu", results
            
        except Exception as e:
            print(f"Metin tabanlı arama hatası: {str(e)}")
            traceback.print_exc()
            return False, f"Arama sırasında hata oluştu: {str(e)}", [] 

    @staticmethod
    def get_face_details(face_id):
        """Belirli bir yüzün detaylarını getirir (ID'ye göre)."""
        # --- Implementation Start ---
        print(f"Details: Fetching details for FaceID: {face_id}")
        try:
            # Get face details from db_tools
            face_details = g.db_tools.getFaceDetailsWithImage(face_id)
            if face_details is None:
                return False, "Yüz bulunamadı", None

            # Initialize image variables
            image_np = None
            image_data_b64 = None
            image_mime_type = None
            use_default_image = True # Default to using placeholder
            final_error_message = None
            image_url = face_details.get('full_image_url')
            image_id_from_main = face_details.get('image_id')



            # 2. Try from DB if URL failed or wasn't present, or if image_np is still None
            if image_np is None and image_id_from_main is not None:
                print(f"Details: Attempting DB fetch for ImageID {image_id_from_main}")
                try:
                    success_db, img_binary_db = g.db_tools.getImageBinaryByID(image_id_from_main)
                    if success_db and img_binary_db:
                        print(f"Details: DB fetch successful for ImageID {image_id_from_main}")
                        # Decompress işlemi eklendi
                        try:
                            # Import etmeye gerek yok, başta edildi
                            decompressed_png_binary = decompress_image(img_binary_db)
                            if decompressed_png_binary:
                                # Dekompres edilmiş PNG verisini decode et
                                image_np = cv2.imdecode(np.frombuffer(decompressed_png_binary, np.uint8), cv2.IMREAD_COLOR)
                                if image_np is None:
                                    raise ValueError("Dekompres edilmiş PNG verisi cv2 ile dekode edilemedi")
                                image_mime_type = 'image/png' # Decompress sonrası PNG döner
                                use_default_image = False # Got image from DB
                                final_error_message = None # Clear URL error if DB succeeded
                            else:
                                raise ValueError("decompress_image boş veri döndürdü")
                        except Exception as decompress_err:
                             print(f"Details: Decompression failed for ImageID {image_id_from_main}: {decompress_err}")
                             traceback.print_exc()
                             # Keep use_default_image = True
                             if not final_error_message:
                                final_error_message = f"Veritabanı resmi açılamadı: {decompress_err}"
                             image_np = None # Ensure image_np is None if decompression fails
                    else:
                        print(f"Details: DB fetch failed for ImageID {image_id_from_main}")
                        if not final_error_message: # Don't overwrite URL error
                            final_error_message = "Resim veritabanında bulunamadı."
                        # Keep use_default_image = True
                except Exception as db_err:
                    print(f"Details: DB fetch/decompress exception for ImageID {image_id_from_main}: {db_err}")
                    traceback.print_exc()
                    if not final_error_message: # Don't overwrite URL error
                         final_error_message = f"Veritabanı hatası/açılamadı: {db_err}"
                    # Keep use_default_image = True
                    image_np = None # Ensure image_np is None on error

            
            
            # --- Image Source Logic ---
            # 1. Try from URL first
            elif image_url:
                print(f"Details: Attempting URL fetch from: {image_url}")
                try:
                    # Use the get_ImageFromUrl function from lib.url_image_download
                    from lib.url_image_download import get_ImageFromUrl
                    success, img_data, img_hash = get_ImageFromUrl(image_url)

                    if success and img_data is not None:
                        print(f"Details: URL fetch successful for {image_url}")
                        image_np = img_data  # img_data is already a cv2 image from get_ImageFromUrl
                        if image_np is None:
                            raise ValueError("URL'den alınan veri dekode edilemedi")
                        
                        # Determine mime type based on common image headers
                        # Note: We don't need to check binary headers as get_ImageFromUrl already returns cv2 image
                        # Default to PNG for safety
                        image_mime_type = 'image/png'
                        
                        use_default_image = False # We have image data
                    else:
                        print(f"Details: URL fetch failed for {image_url}. Reason: {img_data}")
                        final_error_message = "Resim URL'den indirilemedi."
                        # Proceed to DB check
                except Exception as url_err:
                    print(f"Details: URL fetch exception for {image_url}: {url_err}")
                    traceback.print_exc()
                    final_error_message = f"URL hatası: {url_err}"
                    # Proceed to DB check
            
            # 3. If still no image_np after URL and DB attempts
            elif image_np is None:
                print("Details: Image could not be loaded from URL or DB.")
                if not final_error_message:
                     final_error_message = "Resim kaynağı bulunamadı."
                use_default_image = True
            
            # --- Facebox Drawing and Final Encoding ---
            facebox = face_details.get('facebox')

            if image_np is not None and not use_default_image: # Only process if we have valid image data
                try:
                    if facebox: # Draw box if needed
                        print("Details: Drawing facebox.")
                        # Use a helper function (assuming it exists, e.g., draw_face_box)
                        # This function should take image_np (numpy array) and facebox list
                        # Replace 'draw_face_box' with your actual implementation
                        from lib.face_detection import draw_face_box
                        drawn_image_data_b64 = draw_face_box(image_np, facebox)
                        if drawn_image_data_b64:
                            image_data_b64 = drawn_image_data_b64
                            image_mime_type = 'image/jpeg' # draw_face_box returns JPEG
                        else:
                            print("Details: draw_face_box failed, using original image.")
                            # Fallback to encoding the original numpy array
                            success_encode, buffer = cv2.imencode('.jpg', image_np) # Encode as JPG for consistency
                            if success_encode:
                                image_data_b64 = base64.b64encode(buffer).decode('utf-8')
                                image_mime_type = 'image/jpeg' 
                            else:
                                print("Details: Fallback encoding failed.")
                                use_default_image = True # Mark as failed if encoding fails
                
                except Exception as process_err:
                    print(f"Details: Image processing/drawing error: {process_err}")
                    traceback.print_exc()
                    use_default_image = True
                    final_error_message = f"Resim işleme hatası: {process_err}"
            
            # Assign final values to face_details
            face_details['image_data'] = image_data_b64
            face_details['image_mime_type'] = image_mime_type
            face_details['use_default_image'] = use_default_image
            if final_error_message:
                face_details['image_error'] = final_error_message
            elif 'image_error' in face_details: # Clear previous error if successful
                 face_details.pop('image_error')

            # === YENİ BÖLÜM: Yüzün Görüldüğü Diğer Tüm Kaynakları Getir ===
            all_sources = []
            try:
                other_sources_query = """
                    SELECT
                        m."ID" as main_id,
                        m."Protocol",
                        bds."Domain" as source_domain,
                        pds."Path" as source_path,
                        eds."Etc" as source_etc,
                        m."DetectionDate"
                    FROM "ImageBasedMain" m
                    LEFT JOIN "BaseDomainID" bds ON m."BaseDomainID" = bds."ID"
                    LEFT JOIN "UrlPathID" pds ON m."UrlPathID" = pds."ID"
                    LEFT JOIN "UrlEtcID" eds ON m."UrlEtcID" = eds."ID"
                    WHERE %s = ANY(m."FaceID")
                    ORDER BY m."DetectionDate" DESC;
                """
                conn_sources = None
                cursor_sources = None
                try:
                    conn_sources = g.db_tools.connect()
                    from psycopg2.extras import DictCursor # Import here for safety
                    cursor_sources = conn_sources.cursor(cursor_factory=DictCursor)
                    cursor_sources.execute(other_sources_query, (int(face_id),)) # Ensure face_id is int
                    sources_data = cursor_sources.fetchall()
                finally:
                    if conn_sources:
                        g.db_tools.releaseConnection(conn_sources, cursor_sources)
                
                if sources_data:
                    for row_data in sources_data: # Renamed row to row_data to avoid conflict if row exists above
                        protocol = row_data.get('Protocol') or 'http'
                        domain = row_data.get('source_domain')
                        path = row_data.get('source_path') or ''
                        etc = row_data.get('source_etc') or ''
                        
                        current_source_url = None
                        if domain:
                            current_source_url = f"{protocol}://{domain}"
                            if path:
                                current_source_url += f"/{path.lstrip('/')}"
                            if etc:
                                current_source_url += f"?{etc}"
                        
                        all_sources.append({
                            'url': current_source_url,
                            'detection_date': row_data.get('DetectionDate').isoformat() if row_data.get('DetectionDate') else None
                        })
                face_details['all_sources'] = all_sources
                print(f"Details: Found {len(all_sources)} other sources for FaceID: {face_id}")

            except Exception as e_sources:
                current_app.logger.error(f"Hata (diğer kaynakları alırken - FaceID: {face_id}): {str(e_sources)}\n{traceback.format_exc()}")
                face_details['all_sources'] = [] # Hata durumunda boş liste
            # === YENİ BÖLÜM BİTTİ ===

            return True, "İşlem başarılı", face_details
        except Exception as e:
            current_app.logger.error(f"Yüz detayları getirme hatası (FaceID: {face_id}): {str(e)}\n{traceback.format_exc()}")
            return False, f"Sorgu sırasında hata oluştu: {str(e)}", None
        # --- End Implementation ---
    # pass # This pass is unnecessary here

    # ---> ADD MISSING METHODS HERE <---
    @staticmethod
    def get_domains():
        """Sistemdeki tüm domainleri getirir"""
        try:
            domains = g.db_tools.getAllDomains()
            return True, "İşlem başarılı", domains
        except Exception as e:
            return False, f"Domain sorgusu sırasında hata oluştu: {str(e)}", []
    
    @staticmethod
    def get_risk_levels():
        """Sistemdeki tüm risk seviyelerini getirir"""
        try:
            # Risk levels are likely static
            risk_levels = ["düşük", "orta", "yüksek", "kritik"]
            return True, "İşlem başarılı", risk_levels
        except Exception as e:
            # Should not happen for a static list, but include for safety
            return False, f"Risk seviyeleri alınırken hata oluştu: {str(e)}", []
    
    @staticmethod
    def get_categories():
        """Sistemdeki tüm kategorileri getirir"""
        try:
            categories = g.db_tools.getAllCategories()
            return True, "İşlem başarılı", categories
        except Exception as e:
            return False, f"Kategori sorgusu sırasında hata oluştu: {str(e)}", []
            
    @staticmethod
    def search_by_embedding(face_embedding, threshold=0.6):
        """Yüz gömme vektörüne göre benzer yüzleri arar"""
        results = []
        
        # Gömme vektörünü kontrol et
        if face_embedding is None:
            return False, "Yüz gömme vektörü gerekli", []
        
        try:
            # Flask'ın g objesinden db_tools'a erişmek için
            from flask import g
            
            # Veritabanında benzer yüzleri ara
            similar_faces = g.db_tools.findSimilarFacesWithImages(face_embedding=face_embedding, threshold=threshold)
            
            if similar_faces is None or len(similar_faces) == 0:
                return True, "Eşleşen yüz bulunamadı", []
            
            # Her sonuç için image_url ve kaynak URL'yi düzenle
            for face in similar_faces:
                # Initialize fields
                face['image_url'] = None
                face['image_data'] = None
                face['image_mime_type'] = None
                face['use_default_image'] = True # Default to true
                face.pop('image_error', None) # Clear previous error
                final_error_message = None

                # Get components for URL and DB fallback
                img_protocol = face.get('image_protocol')
                img_domain = face.get('image_domain')
                img_path = face.get('image_path')
                image_id_from_main = face.get('image_id') # Get the ImageID

                # --- Image Source Logic ---
                # 1. Try building URL first
                if img_protocol and img_domain and img_path:
                    face['image_url'] = f"{img_protocol}://{img_domain}/{img_path}"
                    face['use_default_image'] = False # URL is available
                    print(f"DEBUG [search_by_embedding]: Using image_url: {face['image_url']}")
                else:
                    print(f"DEBUG [search_by_embedding]: URL components missing for face {face.get('id')}. Trying DB fallback.")
                    # 2. If URL components missing, try DB fallback using ImageID
                    if image_id_from_main is not None:
                        try:
                            success_db, img_binary_db = g.db_tools.getImageBinaryByID(image_id_from_main)
                            if success_db and img_binary_db:
                                print(f"DEBUG [search_by_embedding]: DB fetch successful for ImageID {image_id_from_main}")
                                try:
                                    # <<< YENİ: Decompress et >>>
                                    decompressed_binary = decompress_image(img_binary_db)
                                    if not decompressed_binary:
                                        raise ValueError("Decompression returned empty data.")

                                    # Dekompres edilmiş veriyi Base64'e çevir
                                    face['image_data'] = base64.b64encode(decompressed_binary).decode('utf-8')
                                    face['image_mime_type'] = 'image/png' # Decompress sonrası PNG
                                    
                                    # <<< Eski MIME türü belirleme kaldırıldı >>>
                                    # if img_binary_db.startswith(b'\x89PNG\r\n\x1a\n'): 
                                    #     face['image_mime_type'] = 'image/png'
                                    # elif img_binary_db.startswith(b'\xff\xd8\xff'): 
                                    #     face['image_mime_type'] = 'image/jpeg'
                                    # else: 
                                    #     face['image_mime_type'] = 'image/png' # Default assumption
                                    
                                    face['use_default_image'] = False # DB fetch successful
                                    print(f"DEBUG [search_by_embedding]: Using image_data from DB. MIME: {face['image_mime_type']}")
                                
                                except Exception as process_err: # Decompress veya encode hatası
                                    print(f"ERROR [search_by_embedding]: Failed to decompress/encode DB image for ImageID {image_id_from_main}: {process_err}")
                                    final_error_message = "Veritabanı resmi işlenemedi."
                                    face['use_default_image'] = True # Processing failed
                            else:
                                print(f"DEBUG [search_by_embedding]: DB fetch failed or no data for ImageID {image_id_from_main}.")
                                final_error_message = "Resim veritabanında bulunamadı."
                                face['use_default_image'] = True # DB fetch failed
                        except Exception as db_err:
                            print(f"ERROR [search_by_embedding]: DB fetch exception for ImageID {image_id_from_main}: {db_err}")
                            traceback.print_exc()
                            final_error_message = f"Veritabanı hatası: {db_err}"
                            face['use_default_image'] = True # DB fetch exception
                    else:
                         print(f"DEBUG [search_by_embedding]: ImageID is None for face {face.get('id')}. Cannot fallback to DB.")
                         final_error_message = "Resim URL bilgisi eksik ve veritabanı ID'si yok."
                         face['use_default_image'] = True # Cannot fetch from DB

                # 3. Set error message if default is still used
                if face['use_default_image']:
                     if not final_error_message: # Generic message if no specific error occurred
                          final_error_message = "Resim URL veya veritabanı yoluyla alınamadı."
                     face['image_error'] = final_error_message
                     print(f"DEBUG [search_by_embedding]: Using default image for face {face.get('id')}. Reason: {final_error_message}")


                # Kaynak URL'yi oluştur (Bu kısım değişmedi)
                if face.get('protocol') and face.get('domain'):
                    face['source_url'] = f"{face['protocol']}://{face['domain']}"
                    if face.get('url_path'):
                        face['source_url'] += f"/{face['url_path']}"
                else: 
                    face['source_url'] = None
                
                # DEBUGGING: Print the final face dictionary for the template
                print(f"DEBUG [search_by_embedding]: Final face data for template:\n{json.dumps(face, indent=2, default=str)}")

            return True, f"{len(similar_faces)} adet eşleşme bulundu", similar_faces
        except Exception as e:
            print(f"Benzerlik araması sırasında hata: {str(e)}")
            traceback.print_exc()
            return False, f"Benzer yüzler aranırken hata oluştu: {str(e)}", [] 