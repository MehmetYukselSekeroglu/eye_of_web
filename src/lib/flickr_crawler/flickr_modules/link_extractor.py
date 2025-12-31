#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flickr Link Extractor Module

This module provides a LinkExtractor class for extracting photo URLs from Flickr photostream pages.
"""

import os
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class LinkExtractor:
    """Class for extracting photo page URLs from a Flickr photostream page."""
    
    def __init__(self, driver):
        """
        Initialize the LinkExtractor.
        
        Args:
            driver: A Selenium WebDriver instance.
        """
        self.driver = driver
        self.logger = None  # Will be set by the crawler
    
    def set_logger(self, logger):
        """Set the logger for this extractor."""
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
    
    def extract_urls(self, page_url, timeout=30):
        """
        Extract photo page URLs from a Flickr photostream page.
        
        Args:
            page_url: The URL of the Flickr photostream page.
            timeout: Maximum time to wait for elements, in seconds.
            
        Returns:
            list: List of URL strings for individual photo pages.
        """
        extracted_urls = []
        self.log(f"Extracting photo URLs from: {page_url}")
        
        try:
            # Navigate to the page
            self.log("Navigating to page...")
            self.driver.get(page_url)
            self.driver.set_page_load_timeout(timeout)
            self.log("Page loaded.")
            
            # Scroll down to trigger lazy loading
            self.driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(2)
            
            # Try scrolling a bit more to ensure content is loaded
            self.driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(1)
            
            # Wait for photo containers with different selectors
            self._wait_for_photo_containers(timeout)
            
            # Get photo links
            photo_links = self._get_photo_links()
            
            if not photo_links:
                self.log("No photo links found with any selector", level='warning')
                return []
            
            # Extract URLs from link elements
            for link_element in photo_links:
                try:
                    href = link_element.get_attribute('href')
                    if href and '/photos/' in href:
                        # Ensure it's a valid photo link and construct full URL if relative
                        if href.startswith('/'):
                            full_url = f"https://www.flickr.com{href}"
                        else:
                            full_url = href
                        extracted_urls.append(full_url)
                except Exception as e:
                    self.log(f"Warning: Could not process a link element: {e}", level='warning')
            
            self.log(f"Successfully extracted {len(extracted_urls)} photo URLs.")
            
        except TimeoutException:
            self.log(f"Error: Timed out waiting for elements on {page_url}", level='error')
        except NoSuchElementException:
            self.log(f"Error: Could not find expected elements on {page_url}", level='error')
        except Exception as e:
            self.log(f"An unexpected error occurred during URL extraction: {e}", level='error')
            import traceback
            traceback.print_exc()
        
        return extracted_urls
    
    def _wait_for_photo_containers(self, timeout):
        """Wait for photo containers to be present in the page."""
        self.log("Waiting for photo containers...")
        wait = WebDriverWait(self.driver, timeout)
        
        container_selectors = [
            "div.photo-list-photo-view",
            "div.photo-list-photo-interaction",
            "div.overlay-target",
            "div.photo-list-photo"
        ]
        
        container_found = False
        for selector in container_selectors:
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                self.log(f"Photo containers found using selector: {selector}")
                container_found = True
                break
            except TimeoutException:
                self.log(f"No elements found with selector: {selector}", level='debug')
        
        if not container_found:
            self.log("Could not find any photo containers with available selectors", level='warning')
            debug_dir = os.path.join("output_flickr", "debug")
            os.makedirs(debug_dir, exist_ok=True)
            screenshot_path = os.path.join(debug_dir, f"container_not_found_{int(time.time())}.png")
            self.driver.save_screenshot(screenshot_path)
            self.log(f"Debug screenshot saved to {screenshot_path}")
    
    def _get_photo_links(self):
        """Find and return photo link elements using multiple selectors."""
        link_selectors = [
            "div.photo-list-photo-interaction a.overlay",
            "a.overlay",
            "a[href*='/photos/']",
            "div.photo-list-photo a[href*='/photos/']"
        ]
        
        photo_links = []
        for selector in link_selectors:
            photo_links = self.driver.find_elements(By.CSS_SELECTOR, selector)
            if photo_links:
                self.log(f"Found {len(photo_links)} potential photo links using selector: {selector}")
                break
        
        return photo_links
        
    def extract_pagination_links(self, base_url=None):
        """
        Extract pagination links from the current page.
        
        Args:
            base_url (str, optional): Base URL to prepend to relative paths. 
                                     If None, will extract from current page URL.
                                     
        Returns:
            dict: Dictionary containing:
                - 'current_page': Current page number
                - 'total_pages': Total number of pages (if available)
                - 'next_page': URL of next page (if available)
                - 'prev_page': URL of previous page (if available)
                - 'page_urls': Dictionary of {page_number: page_url} for all found pages
        """
        self.log("Extracting pagination links...")
        
        # Initialize result
        result = {
            'current_page': None,
            'total_pages': None,
            'next_page': None,
            'prev_page': None,
            'page_urls': {}
        }
        
        try:
            # Determine base URL if not provided
            if not base_url:
                current_url = self.driver.current_url
                # Strip existing page parameter if present
                base_url = re.sub(r'(/page\d+/?)', '/', current_url)
                if not base_url.endswith('/'):
                    base_url += '/'
            elif not base_url.endswith('/'):
                base_url += '/'
            
            self.log(f"Using base URL: {base_url}")
            
            # Find pagination elements using different selectors
            pagination_selectors = [
                "div.pagination a",  # Standard pagination links
                "a[href*='/page']",  # Links containing /page
                "a[data-track*='pagination']"  # Links with pagination tracking
            ]
            
            pagination_links = []
            for selector in pagination_selectors:
                pagination_links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if pagination_links:
                    self.log(f"Found {len(pagination_links)} pagination links using selector: {selector}")
                    break
            
            # Find current page
            current_page_elements = self.driver.find_elements(By.CSS_SELECTOR, "span.is-current")
            if current_page_elements:
                try:
                    current_page = int(current_page_elements[0].text.strip())
                    result['current_page'] = current_page
                    self.log(f"Current page: {current_page}")
                except (ValueError, IndexError):
                    self.log("Could not determine current page number", level='warning')
            
            # Extract page URLs from links
            for link in pagination_links:
                try:
                    href = link.get_attribute('href')
                    rel = link.get_attribute('rel')
                    
                    if href:
                        # Process the URL
                        if href.startswith('/'):
                            full_url = f"https://www.flickr.com{href}"
                        else:
                            full_url = href
                        
                        # Check if it's next/prev link
                        if rel == 'next':
                            result['next_page'] = full_url
                            self.log(f"Next page: {full_url}")
                        elif rel == 'prev':
                            result['prev_page'] = full_url
                            self.log(f"Previous page: {full_url}")
                        
                        # Extract page number from URL
                        page_match = re.search(r'/page(\d+)', href)
                        if page_match:
                            page_num = int(page_match.group(1))
                            result['page_urls'][page_num] = full_url
                            
                            # Update total pages if this is larger
                            if result['total_pages'] is None or page_num > result['total_pages']:
                                result['total_pages'] = page_num
                except Exception as e:
                    self.log(f"Error processing pagination link: {e}", level='debug')
            
            # If we found page URLs, sort and log them
            if result['page_urls']:
                self.log(f"Found links to {len(result['page_urls'])} pages")
                self.log(f"Total pages detected: {result['total_pages']}")
                
                # Check consistency - if we're missing pages in-between
                if result['total_pages'] and len(result['page_urls']) < result['total_pages']:
                    self.log("Note: Not all page links were found on this page", level='warning')
                    
                    # Fill in missing pages
                    for page_num in range(1, result['total_pages'] + 1):
                        if page_num not in result['page_urls']:
                            result['page_urls'][page_num] = f"{base_url}page{page_num}"
            else:
                self.log("No pagination links found", level='warning')
        
        except Exception as e:
            self.log(f"Error extracting pagination links: {e}", level='error')
            import traceback
            traceback.print_exc()
        
        return result
    
    def extract_all_pages_urls(self, start_url, max_pages=None):
        """
        Extract URLs for all available pages starting from a given URL.
        
        This method navigates to the start URL and extracts pagination information,
        then returns URLs for all detected pages.
        
        Args:
            start_url (str): Starting URL to extract pagination from
            max_pages (int, optional): Maximum number of pages to return
            
        Returns:
            list: List of page URLs
        """
        self.log(f"Extracting all page URLs from: {start_url}")
        
        try:
            # Navigate to the start URL
            self.driver.get(start_url)
            self.log("Page loaded.")
            
            # Extract pagination information
            pagination_info = self.extract_pagination_links()
            
            # If no pagination found, return just the start URL
            if not pagination_info['page_urls']:
                self.log("No pagination found, returning start URL only")
                return [start_url]
            
            # Prepare the list of page URLs
            total_pages = pagination_info['total_pages']
            if max_pages and max_pages < total_pages:
                total_pages = max_pages
                self.log(f"Limiting to {max_pages} pages as requested")
            
            page_urls = []
            for page_num in range(1, total_pages + 1):
                if page_num in pagination_info['page_urls']:
                    page_urls.append(pagination_info['page_urls'][page_num])
                else:
                    # Construct URL if missing
                    base_url = re.sub(r'(/page\d+/?)', '/', start_url)
                    if not base_url.endswith('/'):
                        base_url += '/'
                    page_urls.append(f"{base_url}page{page_num}")
            
            self.log(f"Extracted {len(page_urls)} page URLs")
            return page_urls
        
        except Exception as e:
            self.log(f"Error extracting all page URLs: {e}", level='error')
            import traceback
            traceback.print_exc()
            return [start_url]  # Return just the start URL in case of error 