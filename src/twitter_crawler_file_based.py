#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File-Based Twitter/X Profile Crawler

This script:
1. Reads a file line by line.
2. Extracts Twitter/X profile URLs or usernames from each line using regex.
3. Uses a specified number of threads (max 3) to process profiles via twitter_thread.py
"""

import os
import re
import time
import argparse
import random
import threading
import queue
import sys
from urllib.parse import urlparse, urlunparse
from concurrent.futures import ThreadPoolExecutor # Kept for potential future use, but direct threading is used
from lib.output.consolePrint import p_info, p_error, p_warn, p_log
from lib.twitter_thread import twitter_thread

# Add the project directory to path to make imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class FileTwitterCrawler:
    """
    A class that reads Twitter/X profile identifiers from a file,
    extracts profile URLs, and processes them using twitter_thread.py.
    """
    
    # Regex to find Twitter/X profile URLs and capture username
    # Handles:
    # - http://twitter.com/username
    # - https://x.com/username
    # - https://www.twitter.com/username/status/123 (extracts username)
    # - x.com/username?s=20 (extracts username)
    # Also handles if a line just contains "username" or "@username"
    PROFILE_URL_REGEX = re.compile(
        r"((?:https?://)?(?:www\.|mobile\.)?(?:twitter\.com|x\.com)/([A-Za-z0-9_]{1,15})(?:[/?#&].*)?)|(?:^@?([A-Za-z0-9_]{1,15})$)",
        re.IGNORECASE
    )
    # Stricter regex for validating a username part if captured alone
    USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_]{1,15}$")

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
    
    def read_and_extract_from_file(self, file_path):
        """
        Reads a file line by line, extracts Twitter/X profile URLs.
        Each line can be a full URL, a username, or @username.
        
        Args:
            file_path (str): Path to the input file
            
        Returns:
            list: List of unique, normalized Twitter/X profile URLs
        """
        profile_urls = set()
        p_info(f"Reading and extracting Twitter/X profiles from: '{file_path}'")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'): # Skip empty lines or comments
                        continue
                    
                    match = self.PROFILE_URL_REGEX.search(line)
                    if match:
                        username = match.group(2) or match.group(3) # Get username from appropriate group
                        # Validate if the extracted part is a plausible username
                        if username and self.USERNAME_REGEX.match(username): # Ensure username is not None
                            profile_url = f"https://x.com/{username}"
                            if profile_url not in profile_urls:
                                profile_urls.add(profile_url)
                                p_log(f"Extracted profile URL: {profile_url} from line {line_num}: '{line}'")
                        else:
                            p_warn(f"Line {line_num}: Found potential match '{username}' but it's not a valid username pattern in '{line}'. Skipping.")
                    else:
                        p_warn(f"Line {line_num}: No valid Twitter/X username or URL found in '{line}'. Skipping.")
                        
        except FileNotFoundError:
            p_error(f"Error: Input file not found at '{file_path}'")
            return []
        except Exception as e:
            p_error(f"Error reading or parsing file '{file_path}': {e}")
            return []
        
        unique_urls_list = list(profile_urls)
        p_info(f"Extracted {len(unique_urls_list)} unique profile URLs from file.")
        return unique_urls_list
    
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
                    url = self.url_queue.get(timeout=5) # Check queue every 5s
                except queue.Empty:
                    p_log(f"Worker {worker_id}: Queue empty, exiting.")
                    break # Exit if queue is empty
                
                with self.lock:
                    if url in self.processed_urls or url in self.failed_urls: # Check failed_urls too
                        p_log(f"Worker {worker_id}: URL {url} already attempted or processed. Skipping.")
                        self.url_queue.task_done()
                        continue
                    # Add to processed_urls early to prevent re-queueing by other threads
                    # if it fails and gets re-added by some other logic (though not in current flow)
                    self.processed_urls.add(url) 
                
                p_info(f"Worker {worker_id}: Processing {url}")
                
                success = False
                max_retries = 3
                retry_count = 0
                
                while not success and retry_count < max_retries:
                    try:
                        if retry_count > 0:
                            p_info(f"Worker {worker_id}: Retry #{retry_count} for {url}")
                            time.sleep(retry_count * 3) # Exponential backoff
                            
                        result = twitter_thread(
                            currentTarget=url,
                            self_databaseToolkit=self.database_toolkit,
                            self_insightFaceApp=self.insightface_app,
                            executable_path=self.executable_path,
                            driver_path=self.driver_path,
                            headless=self.headless,
                            temp_folder=self.temp_folder
                        )
                        
                        if result: # Assuming twitter_thread returns True on success
                            p_info(f"Worker {worker_id}: Successfully processed {url}")
                            success = True
                        else:
                            p_warn(f"Worker {worker_id}: twitter_thread returned failure for {url} (attempt {retry_count+1}/{max_retries})")
                            retry_count += 1
                    
                    except Exception as e:
                        retry_count += 1
                        p_error(f"Worker {worker_id}: Exception processing {url} (attempt {retry_count}/{max_retries}): {e}")
                        if retry_count >= max_retries:
                             p_error(f"Worker {worker_id}: All retries failed for {url} due to exception.")
                
                if not success:
                    p_error(f"Worker {worker_id}: Failed to process {url} after {max_retries} attempts.")
                    with self.lock:
                        self.failed_urls.add(url) # Add to failed set
                        if url in self.processed_urls: # Remove from processed if it ultimately failed
                             self.processed_urls.remove(url)
                
                self.url_queue.task_done()
                time.sleep(random.uniform(2, 5)) # Random delay
        
        finally:
            p_info(f"Worker {worker_id} finished")
    
    def crawl_from_file(self, file_path, num_threads=3):
        """
        Main method to read a file and process resulting Twitter profiles.
        
        Args:
            file_path (str): Path to the input file
            num_threads (int): Number of threads to use for processing (max 3)
        """
        if num_threads > 3:
            p_warn(f"Requested {num_threads} threads, but maximum is 3. Using 3 threads.")
            num_threads = 3
        elif num_threads < 1:
            p_warn(f"Requested {num_threads} threads, which is invalid. Using 1 thread.")
            num_threads = 1

        profile_urls = self.read_and_extract_from_file(file_path)
        if not profile_urls:
            p_info("No profile URLs extracted from file. Exiting.")
            return
            
        self.enqueue_urls(profile_urls)
        
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=self.worker_thread, args=(i+1,))
            thread.daemon = True # Allow main program to exit even if threads are still running (after join timeout)
            thread.start()
            threads.append(thread)
        
        self.url_queue.join() # Wait for all items in the queue to be processed
        
        p_info("All URLs in queue have been processed. Waiting for worker threads to complete...")
        for thread in threads:
            thread.join(timeout=10) # Wait for threads to finish, with a timeout

        # Final summary
        successful_count = 0
        with self.lock: # Access shared sets safely
            # A URL is successful if it's in processed_urls AND NOT in failed_urls
            # However, current logic adds to processed_urls then to failed_urls if it fails.
            # More accurate: success = total_unique_urls_queued - len(self.failed_urls)
            # processed_urls will contain all urls that were picked by a worker.
            # failed_urls contains those that ultimately failed after retries.
            
            # Let's count successful ones by checking those in processed_urls but not in failed_urls
            # This assumes a URL, once picked, stays in processed_urls unless explicitly removed on final failure.
            # My worker logic: add to processed, if fail, add to failed AND remove from processed if it was there.
            # So, after all work, `processed_urls` should ideally contain only successfully processed ones.
            # However, a simpler count is total attempted minus failed.
            
            initial_queued_count = len(profile_urls) # Total unique URLs initially added to queue
            successful_count = initial_queued_count - len(self.failed_urls)


        p_info(f"Crawling complete! Attempted to process {initial_queued_count} unique profiles.")
        p_info(f"Successfully processed: {successful_count} profiles.")
        if self.failed_urls:
            p_warn(f"Failed to process {len(self.failed_urls)} profiles after all retries:")
            for url_idx, failed_url in enumerate(self.failed_urls):
                p_warn(f"  {url_idx+1}. {failed_url}")
        else:
            p_info("All queued profiles processed successfully (or no profiles to process).")


def main():
    parser = argparse.ArgumentParser(description='File-Based Twitter/X Profile Crawler')
    parser.add_argument('file_path', help='Path to the input file containing Twitter/X URLs or usernames (one per line)')
    parser.add_argument('--threads', '-t', dest='num_threads', type=int, default=3,
                        help='Number of threads to use for processing (default: 3, max: 3)')
    parser.add_argument('--driver', '-d', dest='driver_path', help='Path to ChromeDriver')
    parser.add_argument('--chrome', '-c', dest='chrome_path', help='Path to Chrome executable')
    parser.add_argument('--temp', dest='temp_folder', help='Temporary folder for Chrome')
    parser.add_argument('--visible', '-v', action='store_true', help='Show browser windows (non-headless mode)')
    
    args = parser.parse_args()

    if args.num_threads > 3:
        p_warn(f"Max 3 threads allowed. Setting threads to 3.")
        args.num_threads = 3
    elif args.num_threads < 1:
        p_warn(f"Minimum 1 thread required. Setting threads to 1.")
        args.num_threads = 1
        
    try:
        # These imports and initializations are based on the google_based_crawler
        # Ensure these paths and configurations are correct for your environment
        from lib.database_tools import DatabaseTools
        from lib.init_insightface import initilate_insightface
        from lib.load_config import load_config_from_file
        
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
        if not os.path.exists(config_path):
            p_error(f"Configuration file not found: {config_path}")
            p_error("Please ensure 'config/config.json' exists in the project root.")
            return 1
            
        config = load_config_from_file(config_path)
        if not config[0]:
            p_error(f"Failed to load config file: {config[1]}")
            return 1

        db_config = config[1]["database_config"]
        if not db_config:
            p_error("Key 'database_config' not found in configuration file.")
            return 1

        database_toolkit = DatabaseTools(dbConfig=db_config)
        insightface_app = initilate_insightface(config) # Assuming initilate_insightface handles its part of config
        
        crawler = FileTwitterCrawler(
            database_toolkit=database_toolkit,
            insightface_app=insightface_app,
            driver_path=args.driver_path,
            executable_path=args.chrome_path,
            headless=not args.visible,
            temp_folder=args.temp_folder
        )
        
        crawler.crawl_from_file(
            file_path=args.file_path,
            num_threads=args.num_threads
        )
        
    except ImportError as e:
        p_error(f"Error importing required modules: {e}")
        p_error("This script requires the full EyeOfWeb environment and its dependencies to run.")
        p_error("Ensure 'lib' directory is in PYTHONPATH or script is run from project root.")
        return 1
    except FileNotFoundError as e: # Catch specific file not found for config
        p_error(f"File not found during initialization: {e}")
        return 1
    except Exception as e:
        p_error(f"An unexpected error occurred during execution: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    p_info("Script finished.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
