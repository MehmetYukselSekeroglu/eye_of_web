#! /usr/bin/env python3
#! -*- coding: utf-8 -*-
#! Author: Wesker
#! Date: 2025-03-19

import re
import cv2
import numpy as np
from lib.database_tools import DatabaseTools
from lib.url_parser import prepare_url
from lib.url_image_download import get_ImageFromUrl
from lib.output.consolePrint import p_info, p_error, p_warn
from insightface.app.face_analysis import FaceAnalysis
from lib.linkedin.linkedin_profile_crawler import extract_linkedin_profile_picture
import threading

def proccessImage(
        single_image_list: list,     
        parsedCurrentTarget: dict,
        self_databaseToolkit: DatabaseTools,
        self_insightFaceApp: FaceAnalysis,
        riskLevel: str,
        category: str,
        save_image: bool=False,
        stored_no_face_image_url_set:set=None,
        stored_no_face_image_url_lock:threading.Lock=None
        ):
    # URL'yi ayıkla ve düzgün formata getir
    _img_url = single_image_list[0] if isinstance(single_image_list, list) else single_image_list
    _img_url = str(_img_url)
    _img_title = single_image_list[1] if isinstance(single_image_list, list) and len(single_image_list) > 1 else ""
    # URL formatını kontrol et ve düzelt
    if not _img_url.startswith("http://") and not _img_url.startswith("https://"):
        if _img_url.startswith(parsedCurrentTarget["base_domain"]) or _img_url.startswith(parsedCurrentTarget["base_domain"].replace("www.","")):
            _img_url = f"{parsedCurrentTarget['protocol']}://{_img_url}"
        else:
            if _img_url.startswith("#/"):
                _img_url = _img_url[2:]
            
            _img_url = f"{parsedCurrentTarget['protocol']}://{parsedCurrentTarget['base_domain']}/{_img_url}"
    
    # URL'yi hazırla ve resmi indir
    _parsed_image_url = prepare_url(target_url=_img_url)
    
    BLACK_LIST_OF_IMAGE_EXTENSION = [
        ".svg",
        ".gif",
        ".ico"
    ]
    
    if _parsed_image_url["path"].endswith(tuple(BLACK_LIST_OF_IMAGE_EXTENSION)):
        p_warn(f"BLACK LISTED RESIM BULUNDU VE ATLANIYOR: {_img_url}")
        return
    
    if stored_no_face_image_url_set is not None and _img_url in stored_no_face_image_url_set:
        p_warn(f"Daha önce yüz bulunmayan resim atlandı (ön kontrol): {_img_url}")
        return
    
    _imageDataAndStatus = get_ImageFromUrl(target_url=_img_url)
    if _imageDataAndStatus[0]:
        _ ,_png_image = cv2.imencode(".png", _imageDataAndStatus[1])
        _png_image = _png_image.tobytes()
    else:
        _png_image = None
    
    
    if not _imageDataAndStatus[0]:
        p_error(f"URL'den resim alınamadı: {_img_url} -> {_imageDataAndStatus[1]}")
        return
    
    
    p_info(f"İşleniyor: {_img_url}")
    # Yüz tespiti yap
    _detectedFaces = None
    try:
        _detectedFaces = self_insightFaceApp.get(_imageDataAndStatus[1])
        if len(_detectedFaces) < 1:
            _detectedFaces = None
    except Exception as err:
        p_error(f"Yüz tespiti sırasında hata: {str(err)}")
        _detectedFaces = None
    
    
    if _detectedFaces is None:
        p_error(f"Resim içerisinde yüz bulunamadı: {_img_url}")
        if stored_no_face_image_url_set is not None and stored_no_face_image_url_lock is not None:
            with stored_no_face_image_url_lock:
                p_info(f"Adding to stored_no_face_image_url_set: {_img_url}")
                stored_no_face_image_url_set.add(_img_url)
        return
    
    
    ARRAY_OF_CDN_IMAGE = [
        "fbcdn.net",
        "media.licdn.com",
        "encrypted-tbn0.gstatic.com",
        "gstatic.com"
    ]    

    for cdn_image in ARRAY_OF_CDN_IMAGE:
        if re.search(cdn_image, _img_url, re.IGNORECASE):
            print(f"Found CDN Image: {cdn_image} | {_img_url}")
            save_image = True
            _parsed_image_url["etc"] = None
            _parsed_image_url["path"] = None
            _parsed_image_url["base_domain"] = None
            _parsed_image_url["protocol"] = None
            break
    
                
    
    # Resim başlığını al
    
    # Veritabanına kaydet
    _b = self_databaseToolkit.insertImageBased(
        protocol=parsedCurrentTarget["protocol"],
        baseDomain=parsedCurrentTarget["base_domain"],
        urlPath=parsedCurrentTarget["path"],
        urlPathEtc=parsedCurrentTarget["etc"],
        imageProtocol=_parsed_image_url["protocol"],
        imageDomain=_parsed_image_url["base_domain"],
        imagePath=_parsed_image_url["path"],
        imagePathEtc=_parsed_image_url["etc"],
        imageTitle=_img_title,
        imageBinary=_png_image,
        imageHash=_imageDataAndStatus[2],
        faces=_detectedFaces,
        riskLevel=riskLevel,
        category=category,
        save_image=save_image,
        Source='www'
    )
    
    p_info(_b, "")
    print("-" * 30)
    
    
    
    

