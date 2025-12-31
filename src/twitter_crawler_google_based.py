#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google-Based Twitter/X Profile Crawler

This script:
1. Uses googlesearch module to search for keywords + 'twitter'
2. Extracts Twitter/X URLs from search results
3. Extracts usernames from those URLs
4. Uses 2 threads to process profiles via twitter_thread.py
"""

import os
import re
import time
import argparse
import random
import threading
import queue
import sys
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from lib.output.consolePrint import p_info, p_error, p_warn, p_log
from lib.twitter_thread import twitter_thread

# Add the project directory to path to make imports work
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    from googlesearch import search as google_search
except ImportError:
    p_error("Error importing googlesearch module. Please install it with 'pip install googlesearch-python'")
    sys.exit(1)

class GoogleTwitterCrawler:
    """
    A class that searches Google for Twitter profiles using the googlesearch module
    and processes them using twitter_thread.py.
    """
    
    def __init__(self, database_toolkit, insightface_app, driver_path=None, executable_path=None, headless=True, temp_folder=None):
        """
        Initialize the crawler.
        
        Args:
            database_toolkit: Database toolkit object for storing profile images
            insightface_app: InsightFace app object for face detection
            driver_path (str, optional): Path to ChromeDriver
            executable_path (str, optional): Path to Chrome browser
            headless (bool): Whether to run in headless mode
            temp_folder (str, optional): Temporary folder for Chrome
        """
        self.database_toolkit = database_toolkit
        self.insightface_app = insightface_app
        self.driver_path = driver_path
        self.executable_path = executable_path
        self.headless = headless
        self.temp_folder = temp_folder
        self.url_queue = queue.Queue()
        self.processed_urls = set()
        self.failed_urls = set()  # Keep track of URLs that failed all retries
        self.lock = threading.Lock()
    
    def search_google(self, keyword, num_results=20):
        """
        Search Google for keyword + 'twitter' using googlesearch module.
        
        Args:
            keyword (str): The keyword to search for
            num_results (int): Number of search results to retrieve
            
        Returns:
            list: List of extracted Twitter URLs
        """
        twitter_urls = []
        
        search_term = f"{keyword} twitter"
        p_info(f"Searching Google for: '{search_term}'")
        
        try:
            # Use googlesearch module to search
            # Note: The googlesearch-python package has a different API than the google package
            search_results = list(google_search(search_term, num_results=num_results))
            
            # Filter for Twitter/X URLs
            for url in search_results:
                if 'twitter.com/' in url or 'x.com/' in url:
                    twitter_urls.append(url)
                    p_info(f"Found Twitter URL: {url}")
                    
        except Exception as e:
            p_error(f"Error searching Google: {e}")
            # Try an alternative approach if the first one fails
            try:
                p_info("Trying alternative search approach...")
                # Simulate a pause to avoid being blocked
                time.sleep(2)
                # Try with a smaller number of results
                search_results = list(google_search(search_term, num_results=5))
                
                for url in search_results:
                    if 'twitter.com/' in url or 'x.com/' in url:
                        twitter_urls.append(url)
                        p_info(f"Found Twitter URL (alternative method): {url}")
            except Exception as e2:
                p_error(f"Alternative search also failed: {e2}")
        
        # Remove duplicates
        twitter_urls = list(set(twitter_urls))
        p_info(f"Found {len(twitter_urls)} unique Twitter URLs")
        
        return twitter_urls
    
    def filter_profile_urls(self, twitter_urls):
        """
        Filter Twitter/X URLs to keep only profile URLs.
        
        Args:
            twitter_urls (list): List of Twitter/X URLs
            
        Returns:
            list: List of filtered profile URLs
        """
        profile_urls = []
        
        for url in twitter_urls:
            try:
                # Parse URL and extract path
                parsed_url = urlparse(url)
                path = parsed_url.path.strip('/')
                
                # Skip Twitter URLs that aren't profiles
                skip_paths = ['search', 'hashtag', 'explore', 'home', 'notifications', 'messages', 'i', 'settings']
                if not path or path.split('/')[0] in skip_paths:
                    continue
                
                # Extract username (first path component)
                username = path.split('/')[0]
                
                # Check if it looks like a valid username (basic check)
                if username and re.match(r'^[A-Za-z0-9_]{1,15}$', username):
                    # Only keep the profile URL not any specific tweet
                    profile_url = f"https://x.com/{username}"
                    profile_urls.append(profile_url)
                    p_info(f"Found profile URL: {profile_url}")
            
            except Exception as e:
                p_error(f"Error filtering URL {url}: {e}")
                continue
        
        # Remove duplicates
        profile_urls = list(set(profile_urls))
        p_info(f"Found {len(profile_urls)} unique profile URLs")
        
        return profile_urls
    
    def enqueue_urls(self, urls):
        """
        Add URLs to the processing queue.
        
        Args:
            urls (list): List of Twitter profile URLs to process
        """
        for url in urls:
            self.url_queue.put(url)
    
    def worker_thread(self, worker_id):
        """
        Worker thread to process URLs from the queue using twitter_thread.
        
        Args:
            worker_id (int): ID of the worker thread
        """
        p_info(f"Worker {worker_id} started")
        
        try:
            while True:
                try:
                    # Get URL from queue with timeout
                    # If queue is empty for 5 seconds, exit thread
                    url = self.url_queue.get(timeout=5)
                except queue.Empty:
                    break
                
                # Check if already processed
                with self.lock:
                    if url in self.processed_urls:
                        self.url_queue.task_done()
                        continue
                    self.processed_urls.add(url)
                
                p_info(f"Worker {worker_id}: Processing {url}")
                
                # Use twitter_thread to process the URL - with retries
                success = False
                max_retries = 3
                retry_count = 0
                
                while not success and retry_count < max_retries:
                    try:
                        if retry_count > 0:
                            p_info(f"Worker {worker_id}: Retry #{retry_count} for {url}")
                            # Add increasing delay between retries
                            time.sleep(retry_count * 2)
                            
                        result = twitter_thread(
                            currentTarget=url,
                            self_databaseToolkit=self.database_toolkit,
                            self_insightFaceApp=self.insightface_app,
                            executable_path=self.executable_path,
                            driver_path=self.driver_path,
                            headless=self.headless,
                            temp_folder=self.temp_folder
                        )
                        
                        if result:
                            p_info(f"Worker {worker_id}: Successfully processed {url}")
                            success = True
                        else:
                            p_warn(f"Worker {worker_id}: Failed to process {url} (attempt {retry_count+1}/{max_retries})")
                            retry_count += 1
                    
                    except Exception as e:
                        retry_count += 1
                        if retry_count >= max_retries:
                            p_error(f"Worker {worker_id}: Error processing {url} after {max_retries} attempts: {e}")
                        else:
                            p_warn(f"Worker {worker_id}: Error processing {url} (attempt {retry_count}/{max_retries}): {e}")
                
                if not success:
                    p_error(f"Worker {worker_id}: Failed to process {url} after {max_retries} attempts")
                    with self.lock:
                        self.failed_urls.add(url)
                
                # Mark task as done
                self.url_queue.task_done()
                
                # Random delay between requests to avoid rate limiting
                time.sleep(random.uniform(1, 3))
        
        finally:
            p_info(f"Worker {worker_id} finished")
    
    def crawl_keywords(self, keywords, num_results=20, num_threads=2):
        """
        Main method to search for keywords and process resulting Twitter profiles.
        
        Args:
            keywords (list): List of keywords to search for
            num_results (int): Number of Google search results per keyword
            num_threads (int): Number of threads to use for processing
        """
        for keyword in keywords:
            # Search Google for Twitter URLs
            twitter_urls = self.search_google(keyword, num_results)
            
            # Filter to get only profile URLs
            profile_urls = self.filter_profile_urls(twitter_urls)
            
            # Add profile URLs to queue
            self.enqueue_urls(profile_urls)
        
        # Start worker threads
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=self.worker_thread, args=(i+1,))
            thread.start()
            threads.append(thread)
        
        # Wait for all tasks to be processed
        self.url_queue.join()
        
        # Wait for all threads to finish
        for thread in threads:
            thread.join()
        
        # Print summary
        p_info(f"Crawling complete! Processed {len(self.processed_urls)} Twitter profiles.")
        if self.failed_urls:
            p_warn(f"Failed to process {len(self.failed_urls)} profiles after all retries.")
            for url in self.failed_urls:
                p_warn(f"  - {url}")

def main():
    parser = argparse.ArgumentParser(description='Google-Based Twitter Profile Crawler')
    parser.add_argument('keywords', nargs='+', help='Keywords to search for')
    parser.add_argument('--results', '-r', dest='num_results', type=int, default=20,
                        help='Number of Google search results per keyword (default: 20)')
    parser.add_argument('--threads', '-t', dest='num_threads', type=int, default=2,
                        help='Number of threads to use for processing (default: 2)')
    parser.add_argument('--driver', '-d', dest='driver_path', help='Path to ChromeDriver')
    parser.add_argument('--chrome', '-c', dest='chrome_path', help='Path to Chrome executable')
    parser.add_argument('--temp', dest='temp_folder', help='Temporary folder for Chrome')
    parser.add_argument('--visible', '-v', action='store_true', help='Show browser windows (non-headless mode)')
    
    args = parser.parse_args()
    
    # Warning: This is just a placeholder. In a real implementation,
    # you would need to properly initialize these objects.
    try:
        # This is just for testing - in a real implementation, these would be properly initialized
        from lib.database_tools import DatabaseTools
        from lib.init_insightface import initilate_insightface
        from lib.load_config import load_config_from_file
        
        config = load_config_from_file("config/config.json")
        # Initialize database toolkit and insightface app
        database_toolkit = DatabaseTools(dbConfig=config[1]["database_config"])
        insightface_app = initilate_insightface(config)
        
        # Initialize crawler
        crawler = GoogleTwitterCrawler(
            database_toolkit=database_toolkit,
            insightface_app=insightface_app,
            driver_path=args.driver_path,
            executable_path=args.chrome_path,
            headless=not args.visible,
            temp_folder=args.temp_folder
        )
        
        # Start crawling
        crawler.crawl_keywords(
            keywords=args.keywords,
            num_results=args.num_results,
            num_threads=args.num_threads
        )
        
    except ImportError as e:
        p_error(f"Error importing required modules: {e}")
        p_error("This script requires the full EyeOfWeb environment to run.")
        return 1
    except Exception as e:
        p_error(f"Error during execution: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
