#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import urllib.parse
from bs4 import BeautifulSoup
import logging
import requests
from urllib.parse import urljoin, urlparse
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class CSSImageExtractor:
    """
    CSS ile arkaplanlara gömülmüş resimleri çıkartan ve domain ile birleştiren sınıf.
    """
    
    def __init__(self):
        # CSS URL pattern: any url(...) pattern in CSS
        self.css_url_pattern = re.compile(r'url\(["\']?(.*?)["\']?\)', re.IGNORECASE)
        # CSS import pattern: @import statements
        self.css_import_pattern = re.compile(r'@import\s+["\']([^"\']+)["\']', re.IGNORECASE)
        # Extensions to look for
        self.image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
        # User agent
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    
    def extract_images_from_css(self, current_target, html_content):
        """
        CSS arkaplanlarındaki resimleri çıkarır ve domain ile birleştirir
        
        Args:
            current_target (str): Mevcut hedef URL
            html_content (str): HTML içeriği
            
        Returns:
            list: Bulunan resim URL'lerinin listesi
        """
        try:
            # Parse the base URL for joining relative paths
            base_url = self._get_base_url(current_target)
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Initialize the result list
            image_urls = []
            
            # Extract CSS from style tags
            style_tags = soup.find_all('style')
            for style in style_tags:
                if style.string:
                    images = self._extract_urls_from_css(style.string, base_url)
                    image_urls.extend(images)
            
            # Extract CSS from style attributes
            elements_with_style = soup.find_all(attrs={'style': True})
            for element in elements_with_style:
                style_attr = element.get('style', '')
                images = self._extract_urls_from_css(style_attr, base_url)
                image_urls.extend(images)
            
            # Extract CSS from linked stylesheets
            css_links = soup.find_all('link', rel='stylesheet')
            for link in css_links:
                href = link.get('href')
                if href:
                    css_url = urljoin(base_url, href)
                    try:
                        css_content = self._fetch_css(css_url)
                        if css_content:
                            images = self._extract_urls_from_css(css_content, base_url)
                            image_urls.extend(images)
                    except Exception as e:
                        logger.error(f"CSS dosyasını indirirken hata: {css_url} - {str(e)}")
            
            # Remove duplicates and non-image URLs
            return list(set(self._filter_image_urls(image_urls)))
            
        except Exception as e:
            logger.error(f"CSS arkaplan resimlerini çıkarırken hata: {str(e)}")
            return []
    
    def _get_base_url(self, url):
        """URL'nin temel kısmını (domain ve protokol) döndürür."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    
    def _fetch_css(self, css_url):
        """CSS dosyasını indirir."""
        try:
            headers = {'User-Agent': self.user_agent}
            response = requests.get(css_url, headers=headers, timeout=10,verify=False)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            logger.error(f"CSS dosyasını indirirken hata: {css_url} - {str(e)}")
        return None
    
    def _extract_urls_from_css(self, css_content, base_url):
        """CSS içeriğinden URL'leri çıkarır ve tam yollarla birleştirir."""
        if not css_content:
            return []
        
        urls = []
        
        # Find all url() patterns
        matches = self.css_url_pattern.findall(css_content)
        for match in matches:
            # Clean the URL (remove quotes, etc.)
            clean_url = match.strip()
            # Skip data URLs
            if clean_url.startswith('data:'):
                continue
            # Join with base URL if it's relative
            full_url = urljoin(base_url, clean_url)
            urls.append(full_url)
        
        # Process @import statements to find more CSS files
        import_matches = self.css_import_pattern.findall(css_content)
        for css_file in import_matches:
            css_url = urljoin(base_url, css_file)
            try:
                imported_css = self._fetch_css(css_url)
                if imported_css:
                    nested_urls = self._extract_urls_from_css(imported_css, base_url)
                    urls.extend(nested_urls)
            except Exception as e:
                logger.error(f"İçe aktarılan CSS dosyasını işlerken hata: {css_url} - {str(e)}")
        
        return urls
    
    def _filter_image_urls(self, urls):
        """URL'leri filtreler ve sadece resim uzantılarına sahip olanları döndürür."""
        image_urls = []
        for url in urls:
            # Parse the URL
            parsed_url = urlparse(url)
            # Check if the path has an image extension
            path = parsed_url.path.lower()
            if any(path.endswith(ext) for ext in self.image_extensions):
                image_urls.append(url)
            # Some URLs might be images without extensions, using content negotiation
            # We might need additional checks for those
        return image_urls


def extract_css_background_images(current_target, html_content):
    """
    CSS arkaplanlarındaki resimleri çıkarır ve domain ile birleştirir.
    Ana kodla uyumlu fonksiyon arayüzü.
    
    Args:
        current_target (str): Mevcut hedef URL
        html_content (str): HTML içeriği
        
    Returns:
        list: Bulunan resim URL'lerinin listesi
    """
    extractor = CSSImageExtractor()
    return extractor.extract_images_from_css(current_target, html_content)
