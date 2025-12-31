#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Author: Mehmet yüksel şekeroğlu
# @Date: 2025-04-22
# @Filename: twitter_thread.py
# @Last modified by: Mehmet yüksel şekeroğlu
# @Last modified time: 2025-05-14

import time
from urllib.parse import urlparse
import cv2
import numpy
import hashlib
from bs4 import BeautifulSoup
from lib.output.consolePrint import p_info, p_error, p_warn, p_log
from lib.database_tools import DatabaseTools
from insightface.app import FaceAnalysis
# Import TwitterProfileCrawler directly - it has its own driver management now
try:
    from lib.twitter_crawler.twitter_profile_crawler import TwitterProfileCrawler
except ImportError:
    p_error("Error importing TwitterProfileCrawler. Please ensure the module is properly installed.")

def twitter_thread(
    currentTarget: str,
    self_databaseToolkit: DatabaseTools,
    self_insightFaceApp: FaceAnalysis,
    executable_path: str = None,
    driver_path: str = None,
    headless: bool = True,
    temp_folder: str = None,
    ):
    """
    Twitter tarama işlevini gerçekleştirir.
    
    Args:
        currentTarget: Taranacak URL
        self_databaseToolkit: Veritabanı araç kutusu
        self_insightFaceApp: Yüz analizi nesnesi
        executable_path: Chrome tarayıcısının yürütülebilir dosya yolu
        driver_path: ChromeDriver yolu
        headless: Tarayıcının başlıksız modda çalışıp çalışmayacağı
        temp_folder: Geçici dosyalar için klasör
    """
    try:
        # Initialize Twitter profile crawler directly with the driver path
        twitterProfileCrawler = TwitterProfileCrawler(
            headless=headless,
            driver_path=driver_path,
            executable_path=executable_path,
            wait_timeout=60
        )
        
        # Check if ChromeDriver was properly initialized
        if not twitterProfileCrawler.driver:
            p_error(f"Failed to initialize Chrome driver for {currentTarget}")
            return None
        
        # URL'den kullanıcı adını al
        username = twitterProfileCrawler._get_username_from_url(currentTarget)
        if not username:
            p_error(f"Could not extract username from URL: {currentTarget}")
            twitterProfileCrawler.close_driver()
            return None
            
        p_info(f"Extracted username: {username}")
        
        # Profil resmi indir
        image_binary, extension, image_url = twitterProfileCrawler.download_profile_picture_return_binary(currentTarget)
        twitterProfileCrawler.close_driver()
        
        if image_binary is None:
            p_error(f"Failed to download profile picture for {username}")
            return None
        
        # Görüntüyü işle
        imageOpencv = numpy.frombuffer(image_binary, dtype=numpy.uint8)
        imageOpencv = cv2.imdecode(imageOpencv, cv2.IMREAD_COLOR)
        _, imagePng = cv2.imencode(".png", imageOpencv)
        imagePng = imagePng.tobytes()
        imageHash = hashlib.sha1(imagePng).hexdigest()
        
        # Yüz tespiti yap
        faces = self_insightFaceApp.get(imageOpencv)
        
        if len(faces) < 1:
            p_warn(f"No faces detected in the profile picture for {username}")
        
        # URL parçalarını al
        parsedUrl = urlparse(currentTarget)
        baseDomain = parsedUrl.netloc.split(":")[0]
        username_path = parsedUrl.path
        
        parsedImageUrl = urlparse(image_url)
        imageDomain = parsedImageUrl.netloc
        imagePath = parsedImageUrl.path
        
        # Veritabanına kaydet
        db_result = self_databaseToolkit.insertImageBased(
            protocol="https",
            baseDomain=baseDomain,
            urlPath=username_path,
            imageProtocol="https",
            imageDomain=imageDomain,
            imagePath=imagePath,
            imagePathEtc=None,
            imageTitle=username,
            imageBinary=imagePng,
            imageHash=imageHash,
            faces=faces,
            riskLevel="normal",
            category="social",
            save_image=True,
            Source='x'
            )
        
        p_info(f"{currentTarget} -> {db_result}")
        return db_result
        
    except KeyboardInterrupt as e:
        p_error(f"User interrupted the process: {e}")
        return None
    except Exception as e:
        p_error(f"Error processing {currentTarget}: {e}")
        return None

