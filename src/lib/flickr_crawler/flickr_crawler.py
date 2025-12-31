#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Author: Mehmet yüksel şekeroğlu
# @Date: 2025-05-01
# @Filename: flickr_crawler.py
"""
Flickr Crawler

This script crawls Flickr photostream pages and downloads photos.
Uses modular architecture with separate components for:
- Link extraction
- Image downloading
- Logging
- Utilities
"""

import sys
import os
import time
import argparse
from datetime import datetime

# Adjust sys.path to find the selenium_tools module
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))  # Moves up two levels (lib -> src)
sys.path.insert(0, project_root)

try:
    # Import selenium_tools
    from lib.selenium_tools.selenium_browser import get_chrome_driver
    
    # Import our modules
    from flickr_modules.link_extractor import LinkExtractor
    from flickr_modules.image_downloader import ImageDownloader
    from flickr_modules.logger import Logger
    from flickr_modules.utils import extract_photo_id, save_stats, build_page_url, format_time
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Ensure the script is run from the 'src' directory or 'src' is in PYTHONPATH.")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)


class FlickrCrawler:
    """Main class for crawling Flickr photostream pages and downloading photos."""
    
    def __init__(self, config):
        """
        Initialize the crawler with configuration.
        
        Args:
            config: Dictionary containing configuration parameters.
        """
        self.config = config
        self.output_dir = config['output_directory']
        self.debug = config['debug']
        
        # Create logger
        self.logger = Logger(self.output_dir)
        
        # Initialize statistics
        self.stats = {
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_urls_found": 0,
            "successful_downloads": 0,
            "failed_downloads": 0,
            "pages_processed": 0,
            "elapsed_time": 0
        }
        
        # Initialize driver
        self.logger.info("Initializing browser...")
        self.driver = get_chrome_driver(
            headless=config['run_headless'],
            user_agent=config.get('user_agent')
        )
        self.driver.set_page_load_timeout(config['timeout'])
        
        # Initialize components
        self.link_extractor = LinkExtractor(self.driver)
        self.link_extractor.set_logger(self.logger)
        
        self.image_downloader = ImageDownloader(
            self.driver, 
            output_dir=self.output_dir, 
            debug=self.debug
        )
        self.image_downloader.set_logger(self.logger)
    
    def crawl(self):
        """Run the crawler according to the configuration."""
        start_time = time.time()
        
        try:
            self.logger.info(f"\n{'='*50}")
            self.logger.info(f"Starting Flickr Crawler")
            self.logger.info(f"Target: {self.config['target_url']}")
            self.logger.info(f"Output directory: {os.path.abspath(self.output_dir)}")
            
            # Check if we should automatically paginate or use fixed page range
            if self.config.get('auto_paginate', False):
                self.logger.info(f"Mode: Auto-pagination")
                if self.config['max_pages'] > 0:
                    self.logger.info(f"Maximum pages: {self.config['max_pages']}")
                else:
                    self.logger.info(f"Maximum pages: All available")
                
                success = self.paginate_and_crawl()
            else:
                self.logger.info(f"Mode: Fixed page range")
                self.logger.info(f"Pages: {self.config['start_page']} to {self.config['end_page']}")
                
                # Process each page in the range
                for page_num in range(self.config['start_page'], self.config['end_page'] + 1):
                    success = self._process_page(page_num)
                    if not success and self.config['stop_on_empty_page']:
                        self.logger.warning(f"Stopping crawler due to empty page {page_num}")
                        break
                    
                    # Wait between pages
                    if page_num < self.config['end_page']:
                        self.logger.info(f"Waiting {self.config['wait_between_pages']} seconds before next page...")
                        time.sleep(self.config['wait_between_pages'])
            
            # Calculate elapsed time
            elapsed_time = time.time() - start_time
            self.stats['elapsed_time'] = round(elapsed_time, 2)
            
            # Print summary
            self._print_summary()
            
            # Save stats
            stats_file = save_stats(self.stats, self.output_dir)
            self.logger.info(f"Statistics saved to: {stats_file}")
            
            return True
            
        except KeyboardInterrupt:
            self.logger.warning("Crawler stopped by user (Ctrl+C)")
            return False
        except Exception as e:
            self.logger.error(f"An error occurred in the crawler: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Close the browser in any case
            self._cleanup()
    
    def paginate_and_crawl(self):
        """
        Automatically discover and process all pages using pagination links.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        self.logger.info("Starting auto-pagination crawler...")
        
        try:
            # Get all page URLs
            start_url = self.config['target_url']
            max_pages = self.config['max_pages'] if self.config['max_pages'] > 0 else None
            
            self.logger.info(f"Detecting pagination from: {start_url}")
            page_urls = self.link_extractor.extract_all_pages_urls(start_url, max_pages)
            
            if len(page_urls) <= 1:
                self.logger.warning("Could not detect multiple pages, processing as single page")
            else:
                self.logger.info(f"Detected {len(page_urls)} pages to process")
            
            # Process each page
            for i, page_url in enumerate(page_urls):
                page_num = i + 1  # 1-indexed page number
                self.logger.info(f"\n{'='*50}")
                self.logger.info(f"Processing page {page_num} of {len(page_urls)}: {page_url}")
                self.logger.info(f"{'='*50}")
                
                # Extract and process photos from this page
                photo_urls = self.link_extractor.extract_urls(page_url, timeout=self.config['timeout'])
                
                # Update statistics
                self.stats['total_urls_found'] += len(photo_urls)
                self.stats['pages_processed'] += 1
                
                if not photo_urls:
                    self.logger.warning(f"No photo URLs found on page {page_num}")
                    if self.config['stop_on_empty_page']:
                        self.logger.warning(f"Stopping crawler due to empty page {page_num}")
                        break
                    continue
                
                self.logger.info(f"\nFound {len(photo_urls)} photo URLs on page {page_num}")
                
                # Limit the number of items to process if needed
                if self.config['items_per_page'] > 0 and len(photo_urls) > self.config['items_per_page']:
                    self.logger.info(f"Limiting to {self.config['items_per_page']} photos for this page")
                    photo_urls = photo_urls[:self.config['items_per_page']]
                
                # Process each photo URL
                for j, url in enumerate(photo_urls):
                    # end parametresi yerine flush kullanarak yazma
                    msg = f"\n[{j+1}/{len(photo_urls)}] "
                    self.logger.flush(msg)
                    
                    # Örnekleri göster (return_bytes=False varsayılan davranıştır)
                    if i == 0 and j == 0 and self.config.get('show_bytes_example', False):
                        # İlk fotoğrafı hem indir hem de byte array olarak al
                        success, file_path, image_bytes, content_type = self.image_downloader.download_from_page(
                            url, 
                            timeout=self.config['timeout'],
                            return_bytes=True
                        )
                        
                        # Başarılı olursa bilgileri göster
                        if success and image_bytes:
                            self.logger.info(f"Örnek byte array uzunluğu: {len(image_bytes)} byte")
                            self.logger.info(f"İçerik türü: {content_type}")
                            self.logger.info(f"İlk 100 byte: {image_bytes[:100]}")
                            
                            # Byte array kullanımı örneği
                            self.logger.info("Byte array kullanım örneği:")
                            self.logger.info("  from PIL import Image")
                            self.logger.info("  import io")
                            self.logger.info("  image = Image.open(io.BytesIO(image_bytes))")
                            self.logger.info("  print(f'Resim boyutu: {image.size}')")
                    else:
                        # Normal indirme - sadece dosyaya kaydet
                        success, _ = self.image_downloader.download_from_page(
                            url, 
                            timeout=self.config['timeout']
                        )
                    
                    # Update statistics
                    if success:
                        self.stats['successful_downloads'] += 1
                    else:
                        self.stats['failed_downloads'] += 1
                    
                    # Wait between photos
                    if j < len(photo_urls) - 1:  # Don't wait after the last photo
                        time.sleep(self.config['wait_between_photos'])
                
                self.logger.info(f"\nCompleted processing page {page_num} of {len(page_urls)}")
                
                # Wait between pages
                if i < len(page_urls) - 1:  # Don't wait after the last page
                    self.logger.info(f"Waiting {self.config['wait_between_pages']} seconds before next page...")
                    time.sleep(self.config['wait_between_pages'])
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in paginate_and_crawl: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _process_page(self, page_num):
        """
        Process a single page of the photostream.
        
        Args:
            page_num: The page number to process.
            
        Returns:
            bool: True if the page was processed successfully and had photos, False otherwise.
        """
        # Build the URL for this page
        page_url = build_page_url(self.config['target_url'], page_num)
        
        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"Processing page {page_num} of {self.config['end_page']}: {page_url}")
        self.logger.info(f"{'='*50}")
        
        # Extract photo URLs from the page
        photo_urls = self.link_extractor.extract_urls(page_url, timeout=self.config['timeout'])
        
        # Update statistics
        self.stats['total_urls_found'] += len(photo_urls)
        self.stats['pages_processed'] += 1
        
        if not photo_urls:
            self.logger.warning(f"No photo URLs found on page {page_num}")
            return False
        
        self.logger.info(f"\nFound {len(photo_urls)} photo URLs on page {page_num}")
        
        # Limit the number of items to process if needed
        if self.config['items_per_page'] > 0 and len(photo_urls) > self.config['items_per_page']:
            self.logger.info(f"Limiting to {self.config['items_per_page']} photos for this page")
            photo_urls = photo_urls[:self.config['items_per_page']]
        
        # Process each photo URL
        for i, url in enumerate(photo_urls):
            # end parametresi yerine flush kullanarak yazma
            msg = f"\n[{i+1}/{len(photo_urls)}] "
            self.logger.flush(msg)
            
            # Örnekleri göster (return_bytes=False varsayılan davranıştır)
            if i == 0 and self.config.get('show_bytes_example', False):
                # İlk fotoğrafı hem indir hem de byte array olarak al
                success, file_path, image_bytes, content_type = self.image_downloader.download_from_page(
                    url, 
                    timeout=self.config['timeout'],
                    return_bytes=True
                )
                
                # Başarılı olursa bilgileri göster
                if success and image_bytes:
                    self.logger.info(f"Örnek byte array uzunluğu: {len(image_bytes)} byte")
                    self.logger.info(f"İçerik türü: {content_type}")
                    self.logger.info(f"İlk 100 byte: {image_bytes[:100]}")
                    
                    # Byte array kullanımı örneği
                    self.logger.info("Byte array kullanım örneği:")
                    self.logger.info("  from PIL import Image")
                    self.logger.info("  import io")
                    self.logger.info("  image = Image.open(io.BytesIO(image_bytes))")
                    self.logger.info("  print(f'Resim boyutu: {image.size}')")
            else:
                # Normal indirme - sadece dosyaya kaydet
                success, _ = self.image_downloader.download_from_page(
                    url, 
                    timeout=self.config['timeout']
                )
            
            # Update statistics
            if success:
                self.stats['successful_downloads'] += 1
            else:
                self.stats['failed_downloads'] += 1
            
            # Wait between photos
            if i < len(photo_urls) - 1:  # Don't wait after the last photo
                time.sleep(self.config['wait_between_photos'])
        
        self.logger.info(f"\nCompleted processing page {page_num}")
        return True
    
    def _print_summary(self):
        """Print a summary of the crawler results."""
        self.logger.info("\n" + "="*50)
        self.logger.info("Crawler Complete")
        self.logger.info("="*50)
        self.logger.info(f"Pages processed: {self.stats['pages_processed']}")
        self.logger.info(f"Total photo URLs found: {self.stats['total_urls_found']}")
        self.logger.info(f"Successful downloads: {self.stats['successful_downloads']}")
        self.logger.info(f"Failed downloads: {self.stats['failed_downloads']}")
        
        success_rate = self.stats['successful_downloads'] / max(self.stats['total_urls_found'], 1) * 100
        self.logger.info(f"Success rate: {success_rate:.1f}%")
        
        elapsed_formatted = format_time(self.stats['elapsed_time'])
        self.logger.info(f"Total time: {elapsed_formatted}")
        
        self.logger.info(f"Downloaded images are in: {os.path.abspath(self.output_dir)}")
        self.logger.info("="*50)
    
    def _cleanup(self):
        """Clean up resources."""
        if hasattr(self, 'driver') and self.driver:
            self.logger.info("Closing browser...")
            self.driver.quit()
            self.logger.info("Browser closed.")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Flickr Crawler")
    parser.add_argument("--url", dest="target_url", 
                        default="https://www.flickr.com/photos/hdpgenelmerkezi/page2",
                        help="Target Flickr photostream URL")
    parser.add_argument("--output", dest="output_directory", 
                        default="output_flickr",
                        help="Directory to save downloaded images")
    parser.add_argument("--headless", dest="run_headless", 
                        action="store_true", 
                        help="Run browser in headless mode")
    parser.add_argument("--start-page", dest="start_page", 
                        type=int, default=1,
                        help="Starting page number")
    parser.add_argument("--end-page", dest="end_page", 
                        type=int, default=3,
                        help="Ending page number (inclusive)")
    parser.add_argument("--items-per-page", dest="items_per_page", 
                        type=int, default=10,
                        help="Maximum number of items to process per page (0 for all)")
    parser.add_argument("--timeout", dest="timeout", 
                        type=int, default=45,
                        help="Timeout in seconds for waiting for elements")
    parser.add_argument("--wait-photos", dest="wait_between_photos", 
                        type=float, default=1.5,
                        help="Seconds to wait between processing individual photos")
    parser.add_argument("--wait-pages", dest="wait_between_pages", 
                        type=float, default=3,
                        help="Seconds to wait between processing pages")
    parser.add_argument("--no-debug", dest="debug", 
                        action="store_false", 
                        help="Disable debug mode (no screenshots and page source saving)")
    parser.add_argument("--stop-on-empty", dest="stop_on_empty_page", 
                        action="store_true", 
                        help="Stop crawling when an empty page is encountered")
    parser.add_argument("--show-bytes-example", dest="show_bytes_example", 
                        action="store_true", 
                        help="Show an example of image bytes for the first photo (Python usage)")
    parser.add_argument("--auto-paginate", dest="auto_paginate", 
                        action="store_true",
                        help="Automatically detect and process all pages (ignores --start-page and --end-page)")
    parser.add_argument("--max-pages", dest="max_pages", 
                        type=int, default=0,
                        help="Maximum number of pages to process when auto-paginate is enabled (0 = all)")
    
    return parser.parse_args()


def main():
    """Main entry point for the script."""
    # Get command line arguments
    args = parse_arguments()
    
    # Create configuration dictionary
    config = {
        "target_url": args.target_url,
        "output_directory": args.output_directory,
        "run_headless": args.run_headless,
        "start_page": args.start_page,
        "end_page": args.end_page,
        "items_per_page": args.items_per_page,
        "timeout": args.timeout,
        "wait_between_photos": args.wait_between_photos,
        "wait_between_pages": args.wait_between_pages,
        "debug": args.debug,
        "stop_on_empty_page": args.stop_on_empty_page,
        "show_bytes_example": args.show_bytes_example,
        "auto_paginate": args.auto_paginate,
        "max_pages": args.max_pages,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    # Create and run crawler
    crawler = FlickrCrawler(config)
    crawler.crawl()


if __name__ == "__main__":
    main()
