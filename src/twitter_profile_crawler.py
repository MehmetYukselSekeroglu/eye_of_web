#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Filename: twitter_profile_crawler.py

import os
import time
import re
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Import BrowserToolkit and get_chrome_driver from the project's selenium_browser module
from lib.selenium_tools.selenium_browser import BrowserToolkit, get_chrome_driver

class TwitterProfileCrawler:
    """
    A class for crawling Twitter/X profiles and extracting profile images and other data.
    Uses the project's BrowserToolkit for browser operations.
    """
    
    # Twitter/X profile page element XPath - used to detect when profile content is loaded
    PROFILE_IMAGE_XPATH = '//*[@id="react-root"]/div/div/div[2]/main/div/div/div/div[1]/div/div[3]/div/div/div[1]/div/div[1]/div[1]/div[2]/div/div[2]/div/a/div[4]/div'
    
    def __init__(self, headless=True, driver_path=None, wait_timeout=30):
        """
        Initialize the crawler with browser settings.
        
        Args:
            headless (bool): Whether to run the browser in headless mode
            driver_path (str, optional): Path to the ChromeDriver executable
            wait_timeout (int): Maximum time to wait for elements to load (seconds)
        """
        self.wait_timeout = wait_timeout
        self.driver = None
        self.browser = None
        self.driver_path = driver_path
        self.headless = headless
    
    def _initialize_browser(self):
        """Initialize the browser if not already done."""
        if self.driver is None:
            self.driver = get_chrome_driver(
                headless=self.headless,
                driver_path=self.driver_path
            )
            self.browser = BrowserToolkit(self.driver)
    
    def close(self):
        """Close the browser and clean up resources."""
        if self.browser:
            self.browser.close()
            self.driver = None
            self.browser = None
    
    def get_profile_page_source(self, username):
        """
        Navigate to a Twitter/X profile and get the page source before the login redirect.
        
        Args:
            username (str): Twitter/X username without the @ symbol
            
        Returns:
            str: HTML source of the profile page or None if failed
        """
        self._initialize_browser()
        profile_url = f"https://x.com/{username}"
        
        try:
            print(f"Navigating to profile: {profile_url}")
            
            # Navigate to the URL
            self.browser.getUrl(profile_url)
            
            # Implement early detection to capture the page before any login redirect
            print("Attempting to capture profile content before login redirect...")
            start_time = time.time()
            found = False
            
            # Try to locate the profile image element quickly before page fully loads
            while time.time() - start_time < self.wait_timeout:
                try:
                    element = self.driver.find_element(By.XPATH, self.PROFILE_IMAGE_XPATH)
                    if element:
                        found = True
                        print("Profile image element found early during page load!")
                        break
                except NoSuchElementException:
                    time.sleep(0.1)
                    continue
            
            if found:
                # If element found, quickly grab the page source
                page_source = self.browser.pageSource()
                print("Page source captured successfully!")
                return page_source
            else:
                # Try one final explicit wait if early detection failed
                print(f"Element not found during early detection. Trying explicit wait...")
                try:
                    WebDriverWait(self.driver, max(0, self.wait_timeout - (time.time() - start_time))).until(
                        EC.presence_of_element_located((By.XPATH, self.PROFILE_IMAGE_XPATH))
                    )
                    print("Element found after explicit wait.")
                    page_source = self.browser.pageSource()
                    return page_source
                except TimeoutException:
                    print(f"Timeout: Element not found within {self.wait_timeout} seconds.")
                    return None
                
        except Exception as e:
            print(f"Error getting profile page: {e}")
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
        
        print("Could not find any profile image URL in the page source.")
        return None
    
    def _convert_to_hd_url(self, url):
        """
        Convert a Twitter profile image URL to high definition format.
        
        Args:
            url (str): Original profile image URL
            
        Returns:
            str: HD version of the URL
        """
        # Replace common size suffixes with larger or original size
        # Common formats: _normal, _200x200, _400x400, etc.
        url = re.sub(r'_(normal|mini|bigger|x\d+|200x200)', '', url)
        
        # If URL has format parameter, replace with large dimensions
        if '?format=' in url:
            url = re.sub(r'\?format=.*', '?format=jpg&name=4096x4096', url)
        
        # Replace extension specifications if needed
        url = re.sub(r'\.([a-zA-Z]+)$', '.jpg', url)
        
        return url
    
    def download_profile_image(self, username, output_path=None):
        """
        Download HD profile image for a given Twitter/X username.
        
        Args:
            username (str): Twitter/X username without the @ symbol
            output_path (str, optional): Path to save the image. If None, uses username.jpg in current directory.
            
        Returns:
            str: Path to the downloaded image or None if failed
        """
        if not output_path:
            output_path = f"{username}_profile_hd.jpg"
        
        # Get page source
        html_source = self.get_profile_page_source(username)
        if not html_source:
            print(f"Failed to get page source for {username}")
            return None
        
        # Extract profile image URL
        image_url = self.extract_profile_image_url(html_source)
        if not image_url:
            print(f"Could not find profile image URL for {username}")
            return None
        
        print(f"Found profile image URL: {image_url}")
        
        # Download the image
        try:
            response = requests.get(image_url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            
            print(f"Successfully downloaded profile image to {output_path}")
            return output_path
        except Exception as e:
            print(f"Error downloading image: {e}")
            return None
    
    def __enter__(self):
        """Support for context manager (with statement)."""
        self._initialize_browser()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting context."""
        self.close()


def download_twitter_profile_image(username, output_path=None, headless=True, driver_path=None):
    """
    Convenience function to download a Twitter profile image without manually managing the crawler.
    
    Args:
        username (str): Twitter/X username without the @ symbol
        output_path (str, optional): Path to save the image
        headless (bool): Whether to run the browser in headless mode
        driver_path (str, optional): Path to the ChromeDriver executable
        
    Returns:
        str: Path to the downloaded image or None if failed
    """
    with TwitterProfileCrawler(headless=headless, driver_path=driver_path) as crawler:
        return crawler.download_profile_image(username, output_path)


if __name__ == "__main__":
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser(description='Download Twitter/X profile images in HD')
    parser.add_argument('username', help='Twitter/X username (without @)')
    parser.add_argument('--output', '-o', dest='output_path', help='Output path for the image')
    parser.add_argument('--driver', '-d', dest='driver_path', help='Path to ChromeDriver')
    parser.add_argument('--visible', '-v', action='store_true', help='Show browser window (non-headless mode)')
    
    args = parser.parse_args()
    
    result = download_twitter_profile_image(
        args.username, 
        args.output_path, 
        headless=not args.visible,
        driver_path=args.driver_path
    )
    
    if result:
        print(f"Success! Profile image saved to: {result}")
    else:
        print("Failed to download profile image.") 