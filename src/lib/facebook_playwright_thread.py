#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# Playwright-based Facebook Profile Thread
# Migrated from facebook_thread.py to support Playwright backend

import asyncio
import concurrent.futures
import time
import numpy as np
import cv2
import hashlib
from urllib.parse import urlparse

from lib.output.consolePrint import p_info, p_error, p_warn, p_log
from lib.database_tools import DatabaseTools
from insightface.app import FaceAnalysis
from lib.facebook.facebook_playwright_crawler import PlaywrightFacebookCrawler


def facebook_playwright_thread(
    current_target: str,
    database_toolkit: DatabaseTools,
    insightface_app: FaceAnalysis,
    headless: bool = True,
    temp_folder: str = None,
):
    """
    Facebook profile crawling thread using Playwright.

    Args:
        current_target: Profile URL to crawl
        database_toolkit: Database tools instance
        insightface_app: InsightFace application instance
        headless: Run headless
        temp_folder: Temporary folder (not used in async implementation but kept for interface compatibility)
    """
    try:
        p_info(f"Starting Playwright thread for: {current_target}")

        # Initialize crawler for single profile (conservative preset)
        crawler = PlaywrightFacebookCrawler(
            headless=headless,
            preset="conservative",
            download_folder=temp_folder or "downloaded_profile_pics",
        )

        # Get profile image data directly
        image_content, extension = crawler.get_profile_image_data(current_target)

        if not image_content:
            p_warn(f"No profile image found for {current_target}")
            return

        # Process image
        image_np = np.frombuffer(image_content, dtype=np.uint8)
        image_opencv = cv2.imdecode(image_np, cv2.IMREAD_COLOR)

        if image_opencv is None:
            p_error(f"Failed to decode image from {current_target}")
            return

        success, image_png = cv2.imencode(".png", image_opencv)
        if not success:
            return

        image_png_bytes = image_png.tobytes()
        image_hash = hashlib.sha1(image_png_bytes).hexdigest()

        # Detect faces
        faces = insightface_app.get(image_opencv)

        if len(faces) == 0:
            p_log(f"No faces detected in profile picture for {current_target}")
            return

        # Parse domain info
        parsed_url = urlparse(current_target)
        base_domain = parsed_url.netloc.split(":")[0]
        username_path = parsed_url.path
        username_base = crawler._get_username_from_url(current_target)

        # Save to database
        db_result = database_toolkit.insertImageBased(
            protocol="https",
            baseDomain=baseDomain,
            urlPath=username_path,
            imageProtocol=None,
            imageDomain=None,
            imagePath=None,
            imagePathEtc=None,
            imageTitle=username_base,
            imageBinary=image_png_bytes,
            imageHash=image_hash,
            faces=faces,
            riskLevel="normal",
            category="social",
            save_image=True,
            Source="facebook",
        )

        p_info(f"{current_target} -> {db_result}")

    except Exception as e:
        p_error(f"Error in Facebook Playwright thread for {current_target}: {e}")
