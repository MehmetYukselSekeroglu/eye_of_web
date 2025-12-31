#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flickr Image Downloader Module

This module provides an ImageDownloader class for extracting and downloading images from Flickr photo pages.
"""

import os
import time
import re
import requests
import shutil
import urllib.parse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, JavascriptException


class ImageDownloader:
    """Class for extracting and downloading images from Flickr photo pages."""
    
    def __init__(self, driver, output_dir="output_flickr", debug=True):
        """
        Initialize the ImageDownloader.
        
        Args:
            driver: A Selenium WebDriver instance.
            output_dir: Directory where images will be saved.
            debug: Whether to save debug information.
        """
        self.driver = driver
        self.output_dir = output_dir
        self.debug = debug
        self.debug_dir = os.path.join(output_dir, "debug") if debug else None
        self.logger = None  # Will be set by the crawler
        
        # Create output directories
        os.makedirs(output_dir, exist_ok=True)
        if debug:
            os.makedirs(self.debug_dir, exist_ok=True)
    
    def set_logger(self, logger):
        """Set the logger for this downloader."""
        self.logger = logger
    
    def log(self, message, level='info'):
        """Log a message if logger is available, otherwise print."""
        if self.logger:
            if level == 'info':
                self.logger.info(message)
            elif level == 'error':
                self.logger.error(message)
            elif level == 'debug':
                self.logger.debug(message)
            elif level == 'warning':
                self.logger.warning(message)
        else:
            print(message)
    
    def download_from_page(self, photo_page_url, timeout=30, save_to_disk=True, return_bytes=False):
        """
        Download the image from a Flickr photo page.
        
        Args:
            photo_page_url: URL of the Flickr photo page.
            timeout: Maximum time to wait for elements, in seconds.
            save_to_disk: Whether to save the image to disk.
            return_bytes: Whether to return the image bytes.
            
        Returns:
            If return_bytes is False (default):
                tuple: (success, file_path)
                    - success (bool): True if download was successful, False otherwise.
                    - file_path (str): Path to the downloaded file if successful, None otherwise.
            
            If return_bytes is True:
                tuple: (success, file_path, image_bytes, content_type)
                    - success (bool): True if processing was successful, False otherwise.
                    - file_path (str): Path to the downloaded file if save_to_disk=True, None otherwise.
                    - image_bytes (bytes): The image data as bytes if successful, None otherwise.
                    - content_type (str): MIME type of the image if successful, None otherwise.
        """
        self.log(f"Processing photo page: {photo_page_url}")
        downloaded_path = None
        image_bytes = None
        content_type = None
        
        try:
            # Navigate to the page
            self.driver.get(photo_page_url)
            
            # Wait for the page to load
            time.sleep(3)
            
            # Take initial debug screenshot if enabled
            photo_id = self._extract_photo_id(photo_page_url)
            if self.debug:
                debug_screenshot = os.path.join(self.debug_dir, f"{photo_id}_initial.png")
                self.driver.save_screenshot(debug_screenshot)
                self.log(f"Debug screenshot saved to {debug_screenshot}")
            
            # First try the known working selector based on the reference
            found_url = self._try_main_photo_selector(timeout)
            
            # If the first approach failed, try other methods
            if not found_url:
                found_url = self._try_multiple_selectors(timeout)
            
            # If still not found, try JavaScript extraction
            if not found_url:
                found_url = self._try_javascript_extraction()
            
            # If still not found, try Flickr API
            if not found_url:
                found_url = self._try_flickr_api(photo_id)
            
            # Process the image if URL was found
            success = False
            if found_url:
                # Process the URL (handle relative URLs, etc.)
                found_url = self._process_image_url(found_url)
                
                # Get image bytes if requested
                if return_bytes:
                    image_bytes, content_type = self._get_image_bytes(found_url)
                    if image_bytes:
                        self.log(f"✓ Successfully retrieved image bytes ({len(image_bytes)} bytes)")
                        success = True
                
                # Save to disk if requested
                if save_to_disk:
                    # Determine the file path
                    filename = self._get_filename(photo_id, found_url)
                    
                    # Download and save the image
                    if return_bytes and image_bytes:
                        # If we already have the bytes, write them directly to file
                        with open(filename, 'wb') as f:
                            f.write(image_bytes)
                        self.log(f"✓ Successfully saved bytes to {filename}")
                        downloaded_path = filename
                        success = True
                    else:
                        # Otherwise download directly to file
                        disk_success = self._download_image(found_url, filename)
                        if disk_success:
                            downloaded_path = filename
                            success = True
            
            # If we get here and couldn't process the image
            if not success:
                self.log(f"Failed to find image URL for {photo_page_url}", level='warning')
                if self.debug:
                    self._save_debug_info(photo_id)
                
                if return_bytes:
                    return False, downloaded_path, None, None
                else:
                    return False, None
            
            # Return appropriate values based on return_bytes flag
            if return_bytes:
                return success, downloaded_path, image_bytes, content_type
            else:
                return success, downloaded_path
            
        except Exception as e:
            self.log(f"Error processing {photo_page_url}: {e}", level='error')
            import traceback
            traceback.print_exc()
            
            if return_bytes:
                return False, None, None, None
            else:
                return False, None
    
    def _try_main_photo_selector(self, timeout):
        """Try the primary selector that's known to work well."""
        self.log("Trying primary selector: img.main-photo")
        try:
            wait = WebDriverWait(self.driver, timeout)
            img_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "img.main-photo")))
            src = img_element.get_attribute('src')
            if src and ('jpg' in src.lower() or 'jpeg' in src.lower() or 'png' in src.lower()):
                self.log(f"✓ Found image URL with primary selector: {src}")
                return src
            else:
                self.log("Found element with primary selector but no valid src attribute", level='warning')
        except TimeoutException:
            self.log("× Element not found with primary selector", level='debug')
        except Exception as e:
            self.log(f"× Error with primary selector: {e}", level='debug')
        return None
    
    def _try_multiple_selectors(self, timeout):
        """Try multiple CSS selectors to find the image element."""
        image_selectors = [
            "div.view.photo-notes-view img",
            "div.view.photo-well-view img", 
            "div.view.photo-notes-scrappy-view img",
            "div.main-photo img",
            "img.loaded",
            ".main-photo",
            "div.photo-well-media-scrappy-view img"
        ]
        
        for selector in image_selectors:
            self.log(f"Trying selector: {selector}")
            try:
                wait = WebDriverWait(self.driver, 5)  # Shorter timeout for checking selectors
                img_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
                
                src = img_element.get_attribute('src')
                if src and ('jpg' in src.lower() or 'jpeg' in src.lower() or 'png' in src.lower()):
                    self.log(f"✓ Found image URL with selector '{selector}': {src}")
                    return src
                else:
                    self.log(f"Found element with selector '{selector}' but no valid src attribute", level='debug')
            except TimeoutException:
                self.log(f"× Element not found with selector: {selector}", level='debug')
            except Exception as e:
                self.log(f"× Error with selector '{selector}': {e}", level='debug')
        
        return None
    
    def _try_javascript_extraction(self):
        """Use JavaScript to extract image URLs from the page."""
        self.log("Trying JavaScript extraction methods...")
        
        try:
            js_extraction = """
            function findImageURLs() {
                // Check if modelExport exists and contains photo data
                if (window.modelExport && window.modelExport.photo) {
                    const photo = window.modelExport.photo;
                    
                    // Build a collection of URLs from different locations in the object
                    const urls = [];
                    
                    // Try to get the largest size image
                    if (photo.sizes && photo.sizes.o) {
                        urls.push({
                            url: photo.sizes.o.url,
                            width: photo.sizes.o.width,
                            source: 'sizes.o'
                        });
                    }
                    
                    // Try other sizes in decreasing priority
                    const sizePriority = ['o', 'k', 'h', 'l', 'c', 'z', 'm', 'n', 's', 'q', 't', 'sq'];
                    if (photo.sizes) {
                        for (const size of sizePriority) {
                            if (photo.sizes[size] && photo.sizes[size].url) {
                                urls.push({
                                    url: photo.sizes[size].url,
                                    width: photo.sizes[size].width,
                                    source: `sizes.${size}`
                                });
                            }
                        }
                    }
                    
                    // Try the main URL if available
                    if (photo.url) {
                        urls.push({
                            url: photo.url,
                            width: -1,
                            source: 'url'
                        });
                    }
                    
                    // Try the primary if available
                    if (photo.primary) {
                        urls.push({
                            url: photo.primary,
                            width: -1,
                            source: 'primary'
                        });
                    }
                    
                    // Check media items if they exist
                    if (photo.mediaItems) {
                        for (const item of photo.mediaItems) {
                            if (item.url) {
                                urls.push({
                                    url: item.url,
                                    width: item.width || -1,
                                    source: 'mediaItems'
                                });
                            }
                        }
                    }
                    
                    return urls;
                }
                
                // Try to find images loaded in the DOM
                const images = document.querySelectorAll('img');
                const urls = [];
                
                for (const img of images) {
                    if (img.src && (img.src.includes('.jpg') || img.src.includes('.jpeg') || img.src.includes('.png'))) {
                        // Calculate a score based on image size and position
                        let score = img.width * img.height; // Size of image
                        
                        // Bonus for images in the middle of the page
                        const rect = img.getBoundingClientRect();
                        if (rect.top > 0 && rect.bottom < window.innerHeight) {
                            score += 5000; // Bonus for visible images
                        }
                        
                        urls.push({
                            url: img.src,
                            width: img.width,
                            score: score,
                            source: 'DOM img'
                        });
                    }
                }
                
                // Also check background images on divs
                const divs = document.querySelectorAll('div');
                for (const div of divs) {
                    const style = window.getComputedStyle(div);
                    const bgImage = style.backgroundImage;
                    
                    if (bgImage && bgImage !== 'none' && 
                        (bgImage.includes('.jpg') || bgImage.includes('.jpeg') || bgImage.includes('.png'))) {
                        const url = bgImage.replace(/url\\(['"](.+?)['"]/g, '$1');
                        
                        urls.push({
                            url: url,
                            width: div.offsetWidth,
                            score: div.offsetWidth * div.offsetHeight,
                            source: 'background-image'
                        });
                    }
                }
                
                return urls;
            }
            
            return findImageURLs();
            """
            
            result = self.driver.execute_script(js_extraction)
            
            if result and len(result) > 0:
                # Sort the results by size/score in descending order
                sorted_urls = sorted(result, 
                                   key=lambda x: x.get('width', 0) if 'width' in x else x.get('score', 0), 
                                   reverse=True)
                
                # Log all found URLs
                self.log(f"Found {len(result)} potential image URLs via JavaScript:")
                for i, item in enumerate(sorted_urls[:5]):  # Show top 5
                    url = item.get('url', 'N/A')
                    source = item.get('source', 'unknown')
                    width = item.get('width', 0)
                    self.log(f"  {i+1}. {url[:80]}... (source: {source}, width: {width})")
                
                # Use the largest/highest scored URL
                best_match = sorted_urls[0]
                found_url = best_match.get('url')
                self.log(f"Selected best image URL: {found_url[:80]}...")
                return found_url
                
        except JavascriptException as js_error:
            self.log(f"JavaScript extraction error: {js_error}", level='debug')
        except Exception as e:
            self.log(f"Error in JavaScript approach: {e}", level='debug')
        
        return None
    
    def _try_flickr_api(self, photo_id):
        """Try using Flickr API to get the image URL."""
        self.log(f"Trying Flickr API with photo ID: {photo_id}")
        
        try:
            js_api_extraction = """
            function getFlickrAPI(photoId) {
                return fetch(`https://www.flickr.com/services/rest/?method=flickr.photos.getSizes&api_key=7c41e3078be23fb6e229cff93884cd1e&photo_id=${photoId}&format=json&nojsoncallback=1`)
                    .then(response => response.json())
                    .catch(error => { 
                        return { error: error.message }; 
                    });
            }
            
            return getFlickrAPI(arguments[0]);
            """
            
            result = self.driver.execute_script(js_api_extraction, photo_id)
            
            if result and 'sizes' in result and 'size' in result['sizes']:
                sizes = result['sizes']['size']
                self.log(f"Found {len(sizes)} sizes via Flickr API")
                
                # Get the largest available size
                largest_size = max(sizes, key=lambda x: int(x.get('width', 0)) * int(x.get('height', 0)))
                found_url = largest_size.get('source')
                self.log(f"Selected largest size: {largest_size.get('label')} - {found_url}")
                return found_url
                
        except Exception as e:
            self.log(f"Error in API approach: {e}", level='debug')
        
        return None
    
    def _extract_photo_id(self, url):
        """Extract the photo ID from a Flickr photo URL."""
        match = re.search(r'/(\d+)/?$', url.strip('/'))
        return match.group(1) if match else f"image_{int(time.time()*1000)}"
    
    def _process_image_url(self, url):
        """Process the image URL to ensure it's usable."""
        # Handle relative URLs
        parsed_url = urllib.parse.urlparse(url)
        if not parsed_url.scheme:
            url = urllib.parse.urljoin("https://www.flickr.com", url)
        
        # Clean up any escape characters
        url = url.replace("\\", "")
        
        return url
    
    def _get_filename(self, photo_id, url):
        """Determine the output filename based on photo ID and URL."""
        # Determine file extension
        extension = '.jpg'  # Default
        if '.png' in url.lower():
            extension = '.png'
        elif '.gif' in url.lower():
            extension = '.gif'
        
        return os.path.join(self.output_dir, f"{photo_id}{extension}")
    
    def _download_image(self, url, filename):
        """Download an image from the URL and save it to the specified filename."""
        self.log(f"Downloading from {url[:80]}...")
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(filename, 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)
            
            self.log(f"✓ Successfully saved to {filename}")
            return True
        except requests.exceptions.RequestException as e:
            self.log(f"× Error downloading image: {e}", level='error')
            return False
    
    def _save_debug_info(self, photo_id):
        """Save debug information when image download fails."""
        if self.debug:
            # Take a final screenshot
            debug_screenshot = os.path.join(self.debug_dir, f"{photo_id}_final.png")
            self.driver.save_screenshot(debug_screenshot)
            
            # Save page source
            html_path = os.path.join(self.debug_dir, f"{photo_id}_page_source.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            self.log(f"Debug page source saved to {html_path}")
    
    def download_from_page_as_bytes(self, photo_page_url, timeout=30):
        """
        Download the image from a Flickr photo page and return it as bytes.
        
        Args:
            photo_page_url: URL of the Flickr photo page.
            timeout: Maximum time to wait for elements, in seconds.
            
        Returns:
            tuple: (success, image_bytes, content_type)
                - success (bool): True if download was successful
                - image_bytes (bytes): The image data as bytes if successful, None otherwise
                - content_type (str): MIME type of the image if successful, None otherwise
        """
        self.log(f"Processing photo page for bytes extraction: {photo_page_url}")
        
        try:
            # Navigate to the page
            self.driver.get(photo_page_url)
            
            # Wait for the page to load
            time.sleep(3)
            
            # Take initial debug screenshot if enabled
            photo_id = self._extract_photo_id(photo_page_url)
            if self.debug:
                debug_screenshot = os.path.join(self.debug_dir, f"{photo_id}_initial.png")
                self.driver.save_screenshot(debug_screenshot)
                self.log(f"Debug screenshot saved to {debug_screenshot}")
            
            # Find image URL using all available methods
            found_url = self._try_main_photo_selector(timeout)
            
            if not found_url:
                found_url = self._try_multiple_selectors(timeout)
            
            if not found_url:
                found_url = self._try_javascript_extraction()
            
            if not found_url:
                found_url = self._try_flickr_api(photo_id)
            
            # Get the image bytes if URL was found
            if found_url:
                found_url = self._process_image_url(found_url)
                image_bytes, content_type = self._get_image_bytes(found_url)
                if image_bytes:
                    self.log(f"✓ Successfully retrieved image bytes ({len(image_bytes)} bytes)")
                    return True, image_bytes, content_type
            
            # If we get here, all methods failed
            self.log(f"Failed to find or retrieve image from {photo_page_url}", level='warning')
            if self.debug:
                self._save_debug_info(photo_id)
            return False, None, None
            
        except Exception as e:
            self.log(f"Error processing {photo_page_url} for bytes: {e}", level='error')
            import traceback
            traceback.print_exc()
            return False, None, None
    
    def _get_image_bytes(self, url):
        """
        Get image bytes from URL without saving to disk.
        
        Args:
            url: URL of the image.
            
        Returns:
            tuple: (image_bytes, content_type)
                - image_bytes (bytes): The image data as bytes if successful, None otherwise
                - content_type (str): MIME type of the image if successful, None otherwise
        """
        self.log(f"Getting image bytes from {url[:80]}...")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Get content type from response headers
            content_type = response.headers.get('Content-Type', 'image/jpeg')
            
            # Return the image bytes
            return response.content, content_type
        except requests.exceptions.RequestException as e:
            self.log(f"× Error downloading image bytes: {e}", level='error')
            return None, None
    
    def get_image_bytes_from_url(self, image_url):
        """
        Directly download image bytes from a known image URL.
        
        Args:
            image_url: Direct URL to the image.
            
        Returns:
            tuple: (success, image_bytes, content_type)
                - success (bool): True if download was successful
                - image_bytes (bytes): The image data as bytes if successful, None otherwise
                - content_type (str): MIME type of the image if successful, None otherwise
        """
        try:
            # Process the URL (handle relative URLs, etc.)
            image_url = self._process_image_url(image_url)
            
            # Get image bytes
            image_bytes, content_type = self._get_image_bytes(image_url)
            
            if image_bytes:
                return True, image_bytes, content_type
            else:
                return False, None, None
                
        except Exception as e:
            self.log(f"Error getting image bytes from URL {image_url}: {e}", level='error')
            return False, None, None 