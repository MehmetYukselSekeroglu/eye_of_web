#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Author: Mehmet yüksel şekeroğlu
# @Date: 2025-04-22
# @Filename: single_domain_selenium_thread.py
# @Last modified by: Mehmet yüksel şekeroğlu
# @Last modified time: 2025-04-22

import concurrent.futures
from lib.output.consolePrint import p_info, p_error, p_warn, p_log
from insightface.app import FaceAnalysis
from lib.output.banner import printBanner
from lib.database_tools import DatabaseTools
from lib.url_parser import prepare_url
from lib.url_checker import is_safe_url__html
from lib.proccess_image import proccessImage
from lib.user_agent_tools import randomUserAgent
from HiveWebCrawler.Crawler import WebCrawler
from urllib.parse import urlparse, unquote, urlunparse
from lib.css_image_extractor import extract_css_background_images
from lib.selenium_tools import selenium_browser
import time
from lib.facebook.facebook_profile_crawler import FacebookProfileCrawler
from lib.selenium_tools.selenium_browser import BrowserToolkit,get_chrome_driver
import cv2
import numpy
import hashlib
from bs4 import BeautifulSoup
from lib.output.consolePrint import p_info, p_error, p_warn, p_log

def facebook_thread(
    currentTarget: str,
    self_databaseToolkit: DatabaseTools,
    self_insightFaceApp: FaceAnalysis,
    executable_path: str = None,
    driver_path: str = None,
    headless: bool = True,
    temp_folder: str = None,
    ):
    """
    Facebook tarama işlevini gerçekleştirir.
    
    Args:
        currentTarget: Taranacak URL
        self_databaseToolkit: Veritabanı araç kutusu
        self_insightFaceApp: Yüz analizi nesnesi
    """
    try:
        chromeDriver = get_chrome_driver(
            headless=headless, 
            executable_path=executable_path, 
            driver_path=driver_path,
            temp_base_dir=temp_folder
        )    
        
        facebookProfileCrawler = FacebookProfileCrawler(driver=chromeDriver)
        facebookProfileCrawler.toolkit.getUrl(currentTarget, timeout=30)
        time.sleep(2)
        pageSource = facebookProfileCrawler.toolkit.pageSource()

        username_base = facebookProfileCrawler._get_username_from_url(currentTarget)
        profile_soup = BeautifulSoup(pageSource, 'html.parser')
        main_pic_url = facebookProfileCrawler._get_main_picture_url(profile_soup)
        facebookProfileCrawler.close_driver()
        
        del profile_soup
        del pageSource
        del chromeDriver
        
        print(f"Username base: {username_base}")
        print(f"Main picture url: {main_pic_url}")
        
        if main_pic_url:
            image_binary, extension = facebookProfileCrawler.download_profile_picture_return_binary(currentTarget, main_pic_url)
        else:
            image_binary = None
            extension = None

        if image_binary is None:
            return
        
        imageOpencv = numpy.frombuffer(image_binary, dtype=numpy.uint8)
        imageOpencv = cv2.imdecode(imageOpencv, cv2.IMREAD_COLOR)
        _, imagePng = cv2.imencode(".png", imageOpencv)
        imagePng = imagePng.tobytes()
        imageHash = hashlib.sha1(imagePng).hexdigest()
        
        faces = self_insightFaceApp.get(imageOpencv)
        
        if len(faces) < 0:
            return
        
        baseDomain = urlparse(currentTarget).netloc
        baseDomain = baseDomain.split(":")[0]
        
        username_path = urlparse(currentTarget).path
        
        db_result = self_databaseToolkit.insertImageBased(
            protocol="https",
            baseDomain=baseDomain,
            urlPath=username_path,
            imageProtocol=None,
            imageDomain=None,
            imagePath=None,
            imagePathEtc=None,
            imageTitle=username_base,
            imageBinary=imagePng,
            imageHash=imageHash,
            faces=faces,
            riskLevel="normal",
            category="social",
            save_image=True,
            Source='facebook'
            )
        
        p_info(f"{currentTarget} -> {db_result}")
        
        return
        
    except KeyboardInterrupt as e:
        p_error(f"{currentTarget} -> {e}")
        return

