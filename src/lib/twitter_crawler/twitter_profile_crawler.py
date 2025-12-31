#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Author: Mehmet yüksel şekeroğlu
# @Date: 2025-05-14
# @Filename: twitter_profile_crawler.py
# @Last modified by: Mehmet yüksel şekeroğlu
# @Last modified time: 2025-05-14

import os
import time
import re
import requests
import cv2
import numpy
import hashlib
import sys
import platform
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from lib.output.consolePrint import p_info, p_error, p_warn, p_log

class TwitterProfileCrawler:
    """
    A class for crawling Twitter/X profiles and extracting profile images and other data.
    Uses its own driver management instead of the project's BrowserToolkit.
    """
    
    # Twitter/X profile page element XPath - used to detect when profile content is loaded
    PROFILE_IMAGE_XPATH = '//*[@id="react-root"]/div/div/div[2]/main/div/div/div/div[1]/div/div[3]/div/div/div[1]/div/div[1]/div[1]/div[2]/div/div[2]/div/a/div[4]/div'
    DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    
    def __init__(self, driver=None, headless=True, driver_path=None, executable_path=None, wait_timeout=30):
        """
        Initialize the crawler with browser settings.
        
        Args:
            driver: Existing WebDriver instance to use (optional)
            headless (bool): Whether to run the browser in headless mode
            driver_path (str, optional): Path to the ChromeDriver executable
            executable_path (str, optional): Path to the Chrome browser executable
            wait_timeout (int): Maximum time to wait for elements to load (seconds)
        """
        self.wait_timeout = wait_timeout
        self.driver = driver
        self.driver_path = driver_path
        self.executable_path = executable_path
        self.headless = headless
        self.driver_is_external = False
        
        # Initialize driver if not provided
        if driver is None:
            self._initialize_browser()
    
    def _find_chromedriver(self):
        """
        Attempt to locate ChromeDriver in common locations.
        
        Returns:
            str: Path to ChromeDriver or None if not found
        """
        # First check if driver_path is specified and valid
        if self.driver_path and os.path.isfile(self.driver_path) and os.access(self.driver_path, os.X_OK):
            return self.driver_path
            
        # Common paths by OS
        if platform.system() == "Windows":
            common_paths = [
                os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'chromedriver.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'chromedriver.exe'),
                os.path.join(os.getcwd(), 'chromedriver.exe'),
                os.path.join(os.environ.get('USERPROFILE', 'C:\\Users\\'), 'chromedriver.exe')
            ]
        else:  # Linux/Mac
            common_paths = [
                '/usr/local/bin/chromedriver',
                '/usr/bin/chromedriver',
                '/bin/chromedriver',
                '/opt/chromedriver',
                os.path.join(os.getcwd(), 'chromedriver'),
                os.path.join(os.path.expanduser('~'), 'chromedriver')
            ]
            
        # Check if chromedriver exists in common paths
        for path in common_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
                
        # Check in PATH
        for path_dir in os.environ.get('PATH', '').split(os.pathsep):
            chromedriver_path = os.path.join(path_dir, 'chromedriver')
            if platform.system() == "Windows":
                chromedriver_path += '.exe'
            if os.path.isfile(chromedriver_path) and os.access(chromedriver_path, os.X_OK):
                return chromedriver_path
                
        return None
    
    def _initialize_browser(self):
        """Initialize a new Chrome browser instance."""
        if self.driver is not None:
            # Driver is already initialized
            self.driver_is_external = True
            return
            
        p_info(f"Initializing Chrome driver (Headless: {self.headless})")
        
        # Set up Chrome options
        chrome_options = Options()
        
        # Common options for stability
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(f"user-agent={self.DEFAULT_USER_AGENT}")
        
        # Set Chrome executable path if provided
        if self.executable_path:
            chrome_options.binary_location = self.executable_path
        
        # Set headless mode if needed
        if self.headless:
            chrome_options.add_argument("--headless")
            p_info("  -> Headless mode enabled.")
            
        # Suppress INFO logs from DevTools
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        try:
            # Find ChromeDriver if path not explicitly provided
            if not self.driver_path:
                self.driver_path = self._find_chromedriver()
                
            if self.driver_path:
                p_info(f"Using ChromeDriver at: {self.driver_path}")
                service = Service(executable_path=self.driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                # Last resort: Try to let Selenium find ChromeDriver automatically
                p_warn("No ChromeDriver specified. Trying automatic detection...")
                self.driver = webdriver.Chrome(options=chrome_options)
                
            self.driver_is_external = False
            p_info("Chrome driver initialized successfully.")
        except WebDriverException as e:
            p_error(f"Error initializing Chrome driver: {e}")
            p_error("Please ensure ChromeDriver is installed and accessible.")
            
            # Provide helpful information on how to fix the issue
            p_info("\nTo fix ChromeDriver issues:")
            p_info("1. Download ChromeDriver matching your Chrome version from https://sites.google.com/chromium.org/driver/")
            p_info("2. Place it in a location in your PATH or provide the path when initializing TwitterProfileCrawler")
            p_info("3. Make it executable (chmod +x chromedriver on Linux/Mac)")
            
            # Avoid raising exception if possible, just return None driver
            self.driver = None
        except Exception as e:
            p_error(f"Unexpected error initializing Chrome driver: {e}")
            self.driver = None
    
    def close_driver(self):
        """Close the browser if we created it (not if externally provided)."""
        if self.driver and not self.driver_is_external:
            try:
                self.driver.quit()
            except Exception as e:
                p_error(f"Error closing driver: {e}")
            finally:
                self.driver = None
                p_info("Chrome driver closed.")
    
    def get_profile_page_source(self, profile_url):
        """
        Navigate to a Twitter/X profile and get the page source before the login redirect.
        
        Args:
            profile_url (str): Full URL to the Twitter/X profile
            
        Returns:
            str: HTML source of the profile page or None if failed
        """
        if not self.driver:
            p_error("No driver available. Initialize browser first.")
            return None
            
        try:
            p_info(f"Navigating to profile: {profile_url}")
            
            # Navigate to the URL
            self.driver.set_page_load_timeout(self.wait_timeout)
            self.driver.get(profile_url)
            
            # Implement early detection to capture the page before any login redirect
            p_info("Attempting to capture profile content before login redirect...")
            start_time = time.time()
            found = False
            
            # Try to locate the profile image element quickly before page fully loads
            while time.time() - start_time < self.wait_timeout:
                try:
                    element = self.driver.find_element(By.XPATH, self.PROFILE_IMAGE_XPATH)
                    if element:
                        found = True
                        p_info("Profile image element found early during page load!")
                        break
                except NoSuchElementException:
                    time.sleep(0.1)
                    continue
            
            if found:
                # If element found, quickly grab the page source
                page_source = self.driver.page_source
                p_info("Page source captured successfully!")
                return page_source
            else:
                # Try one final explicit wait if early detection failed
                p_info(f"Element not found during early detection. Trying explicit wait...")
                try:
                    WebDriverWait(self.driver, max(0, self.wait_timeout - (time.time() - start_time))).until(
                        EC.presence_of_element_located((By.XPATH, self.PROFILE_IMAGE_XPATH))
                    )
                    p_info("Element found after explicit wait.")
                    page_source = self.driver.page_source
                    return page_source
                except TimeoutException:
                    p_error(f"Timeout: Element not found within {self.wait_timeout} seconds.")
                    return None
                
        except Exception as e:
            p_error(f"Error getting profile page: {e}")
            return None
    
    def extract_profile_image_url(self, html_content):
        """
        Extract the profile image URL from the HTML content.
        
        Args:
            html_content (str): HTML content of the Twitter/X profile page
            
        Returns:
            str: URL of the profile image in high resolution format, or None if not found
        """
        if not html_content:
            return None
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Method 1: Find divs with background-image style containing profile image URL
        image_divs = soup.find_all('div', style=lambda value: value and 'background-image' in value 
                                   and 'pbs.twimg.com/profile_images/' in value)
        
        # Process each potential profile image div
        for div in image_divs:
            parent_div = div.find_parent('div')
            
            # Check if this is the profile photo element
            if parent_div and parent_div.get('aria-label', '') == "Opens profile photo":
                # Extract URL from background-image style
                style_attr = div.get('style', '')
                url_match = re.search(r'url\(["\']?(.*?)["\']?\)', style_attr)
                if url_match:
                    url = url_match.group(1)
                    # Convert to HD by removing size limitations (_200x200, etc.)
                    hd_url = self._convert_to_hd_url(url)
                    return hd_url
        
        # Method 2: Find img tag within profile photo element
        profile_img = soup.find('img', attrs={'alt': lambda value: value and 'profile photo' in value.lower()})
        if profile_img and profile_img.get('src', ''):
            url = profile_img.get('src', '')
            if 'pbs.twimg.com/profile_images/' in url:
                hd_url = self._convert_to_hd_url(url)
                return hd_url
        
        # Method 3: Find any img with src containing profile_images
        all_imgs = soup.find_all('img')
        for img in all_imgs:
            src = img.get('src', '')
            if 'pbs.twimg.com/profile_images/' in src:
                hd_url = self._convert_to_hd_url(src)
                return hd_url
        
        p_warn("Could not find any profile image URL in the page source.")
        return None
    
    def _convert_to_hd_url(self, url):
        """
        Convert a Twitter profile image URL to high definition format.
        
        Args:
            url (str): Original profile image URL
            
        Returns:
            str: HD version of the URL
        """
        # Remove any quote characters
        url = url.replace('&quot;', '').replace('"', '')

        # Replace common size suffixes with larger or original size
        # Common formats: _normal, _200x200, _400x400, etc.
        url = re.sub(r'_(normal|mini|bigger|x\d+|200x200)', '', url)
        
        # If URL has format parameter, replace with large dimensions
        if '?format=' in url:
            url = re.sub(r'\?format=.*', '?format=jpg&name=4096x4096', url)
        
        # Replace extension specifications if needed
        url = re.sub(r'\.([a-zA-Z]+)$', '.jpg', url)
        
        return url
    
    def _get_username_from_url(self, url):
        """
        Extract the username from a Twitter profile URL.
        
        Args:
            url (str): Twitter profile URL
            
        Returns:
            str: Username or None if not found
        """
        match = re.search(r'(?:twitter\.com|x\.com)/([^/?]+)', url)
        if match:
            return match.group(1)
        return None
        
    def download_profile_picture_return_binary(self, profile_url, image_url=None):
        """
        Download profile picture and return as binary data.
        
        Args:
            profile_url (str): Twitter profile URL
            image_url (str, optional): Profile image URL if already known
            
        Returns:
            tuple: (binary_data, extension) or (None, None) if failed
        """
        try:
            # Check if driver is available
            if not self.driver and not image_url:
                p_error("Driver initialization failed and no image URL provided.")
                return None, None, None
                
            # If image URL not provided, get page source and extract it
            if not image_url:
                html_source = self.get_profile_page_source(profile_url)
                if not html_source:
                    p_error(f"Failed to get page source for {profile_url}")
                    return None, None, None
                
                image_url = self.extract_profile_image_url(html_source)
                if not image_url:
                    p_error(f"Could not find profile image URL for {profile_url}")
                    return None, None, None
            
            p_info(f"Downloading profile image: {image_url}")
            
            # Download the image
            response = requests.get(image_url, stream=True)
            response.raise_for_status()
            
            # Get the binary data
            binary_data = response.content
            
            # Determine extension from the URL or content type
            extension = 'jpg'  # Default
            content_type = response.headers.get('content-type', '')
            if 'image/' in content_type:
                extension = content_type.split('/')[-1]
            elif '.' in image_url:
                extension = image_url.split('.')[-1].split('?')[0]
            
            p_info(f"Successfully downloaded profile image ({len(binary_data)} bytes)")
            return binary_data, extension, image_url
            
        except Exception as e:
            p_error(f"Error downloading profile image: {e}")
            return None, None, None
            
    def pageSource(self):
        """
        Get the current page source.
        For compatibility with the old toolkit-based interface.
        
        Returns:
            str: Current page source
        """
        if self.driver:
            return self.driver.page_source
        return None 