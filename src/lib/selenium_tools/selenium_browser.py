#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Author: Mehmet yüksel şekeroğlu
# @Date: 2025-04-22
# @Filename: selenium_browser.py
# @Last modified by: Mehmet yüksel şekeroğlu
# @Last modified time: 2025-04-22

import time
import os # os modülünü ekle
import shutil # shutil modülünü ekle
import uuid # uuid modülünü ekle
import tempfile # tempfile modülünü ekle
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
import os # os modülünü ekle

# Added imports for driver setup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
# webdriver-manager is recommended for easier driver management
# Install it using: pip install webdriver-manager
from webdriver_manager.chrome import ChromeDriverManager

DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

def get_chrome_driver(headless=True, user_agent=DEFAULT_USER_AGENT, profile_dir_path=None, executable_path=None, driver_path=None, temp_base_dir=None):
    """
    Creates and returns a Chrome WebDriver instance with options.

    Args:
        headless (bool): Whether to run in headless mode.
        user_agent (str): The User-Agent string to use.
        profile_dir_path (str, optional): Path for the user data directory.
                                          If None and temp_base_dir is None, a default profile is used.
                                          This is ignored if temp_base_dir is provided.
        executable_path (str, optional): Chrome tarayıcısının yürütülebilir dosya yolu.
        driver_path (str, optional): ChromeDriver'ın yolu. Belirtilirse webdriver-manager kullanılmaz.
        temp_base_dir (str, optional): Base directory for creating temporary profiles.
                                       If provided, a unique, clean profile directory will be created
                                       under this path for each driver instance.
    
    Returns:
        tuple: (driver, temp_user_data_dir) - driver instance and path to temp directory (if created)
    """
    print(f"Initializing Chrome driver (Headless: {headless})")
    options = ChromeOptions()
    # Common options for stability, especially in containers/headless
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu") # Often necessary for headless
    options.add_argument("--window-size=1280,720") # Define window size
    # Suppress INFO logs from DevTools if desired
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    # Track the temp directory we create so we can clean it up later
    temp_user_data_dir = None

    # Create unique user data directory to avoid conflicts between multiple instances
    if temp_base_dir:
        # Ensure temp_base_dir exists
        os.makedirs(temp_base_dir, exist_ok=True)
        # Create unique subdirectory for this instance
        temp_user_data_dir = os.path.join(temp_base_dir, f"chrome_profile_{uuid.uuid4().hex}")
        options.add_argument(f"--user-data-dir={temp_user_data_dir}")
        print(f"  -> Using unique user data directory: {temp_user_data_dir}")
    elif profile_dir_path:
        options.add_argument(f"--user-data-dir={profile_dir_path}")
        print(f"  -> Using specified user data directory: {profile_dir_path}")
        # Don't set temp_user_data_dir since we didn't create it
    else:
        # Create a temporary unique directory in system temp
        temp_user_data_dir = tempfile.mkdtemp(prefix="chrome_profile_")
        options.add_argument(f"--user-data-dir={temp_user_data_dir}")
        print(f"  -> Using temporary user data directory: {temp_user_data_dir}")

    if headless:
        options.add_argument("--headless=new") # Use the new headless mode
        print("  -> Headless mode enabled.")

    if user_agent:
        options.add_argument(f"user-agent={user_agent}")
        # print("  -> User-Agent set.") # Daha az log için kapatılabilir

    # Chrome tarayıcısının yolunu ayarla (varsa)
    if executable_path:
        options.binary_location = executable_path
        print(f"  -> Chrome executable path set to: {executable_path}")

    try:
        # ChromeDriver yolu belirtilmişse onu kullan, aksi takdirde webdriver-manager ile indir
        if driver_path:
            service = ChromeService(executable_path=driver_path)
        else:
            service = ChromeService(ChromeDriverManager().install())
        
        # print("  -> Creating WebDriver instance...")
        driver = webdriver.Chrome(service=service, options=options)
        
        # Store temp directory path in driver object for cleanup
        driver._temp_user_data_dir = temp_user_data_dir
        
        print("  -> Chrome driver initialized successfully.")
        return driver
    except Exception as e:
        # If driver creation fails, clean up the temp directory we created
        if temp_user_data_dir and os.path.exists(temp_user_data_dir):
            try:
                shutil.rmtree(temp_user_data_dir)
                print(f"  -> Cleaned up temp directory after error: {temp_user_data_dir}")
            except Exception as cleanup_error:
                print(f"  -> Warning: Could not clean up temp directory: {cleanup_error}")
        
        print(f"Error initializing Chrome driver: {e}")
        print("Please ensure ChromeDriver is installed and accessible, or webdriver-manager can install it.")
        raise


class BrowserToolkit():
    def __init__(self, driver:WebDriver):
        self.driver = driver

    def getUrl(self, url: str, timeout: int = 10) -> WebDriver:
        self.driver.set_page_load_timeout(timeout)
        self.driver.get(url)
        return self.driver

    def pageSource(self) -> str:
        return self.driver.page_source

    def close(self):
        # Clean up temp user data directory if it was created by us
        temp_dir = getattr(self.driver, '_temp_user_data_dir', None)
        
        try:
            self.driver.quit()
        except Exception as e:
            print(f"Error closing driver: {e}")
        
        # Clean up temp directory after driver is closed
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print(f"  -> Cleaned up temp user data directory: {temp_dir}")
            except Exception as e:
                print(f"  -> Warning: Could not clean up temp directory {temp_dir}: {e}")
        
    def scroll_page(self, scroll_amount: int = 1000):
        self.driver.execute_script(f"window.scrollTo(0, {scroll_amount});")













