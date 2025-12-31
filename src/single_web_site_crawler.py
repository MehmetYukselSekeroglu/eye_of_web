#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import threading
from urllib.parse import urlparse
from HiveWebCrawler.Crawler import WebCrawler
from insightface.app import FaceAnalysis
from lib.single_domain_thread import single_domain_thread
from lib.database_tools import DatabaseTools
from lib.output.consolePrint import p_info, p_error, p_warn, p_log
from lib.output.banner import printBanner
from lib.load_config import load_config_from_file
from lib.init_insightface import initilate_insightface

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Crawl specific URLs from a file')
    parser.add_argument('-f', '--file', required=True, help='File containing URLs to crawl (one URL per line)')
    parser.add_argument('-r', '--risk', default="low", help='Risk level for crawling (default: low)')
    parser.add_argument('-c', '--category', default="general", help='Category for database entries (default: general)')
    parser.add_argument('-s', '--save-images', action='store_true', help='Save images found during crawling')
    parser.add_argument('-t', '--threads', type=int, default=5, help='Number of threads to use (default: 5)')
    args = parser.parse_args()

    # Check if file exists
    if not os.path.isfile(args.file):
        p_error(f"File not found: {args.file}")
        return

    # Print banner
    
    # Initialize tools
    crawler = WebCrawler()
    config = load_config_from_file()
    face_app = initilate_insightface(config)
    db_tools = DatabaseTools(config[1]['database_config'])
    printBanner(config=config)

    # Set for storing URLs with no faces
    no_face_urls = set()
    no_face_lock = threading.Lock()
    
    # Dummy function to handle URL additions (we won't be adding URLs to a queue)
    def dummy_add_url(url):
        p_log(f"URL found but not adding to queue (single page mode): {url}")
    
    # Read URLs from file
    urls = []
    with open(args.file, 'r') as f:
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
    
    p_info(f"Loaded {len(urls)} URLs from {args.file}")
    
    # Process URLs with thread pool
    import concurrent.futures
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads, thread_name_prefix="PageCrawler") as executor:
        future_to_url = {}
        
        for url in urls:
            try:
                # Get root domain from URL
                parsed_url = urlparse(url)
                if not parsed_url.netloc:
                    p_warn(f"Invalid URL format, skipping: {url}")
                    continue
                    
                root_domain = parsed_url.netloc
                
                # Submit task to thread pool
                future = executor.submit(
                    single_domain_thread,
                    currentTarget=url,
                    Crawler=crawler,
                    root_domain=root_domain,
                    add_url_func=dummy_add_url,
                    self_databaseToolkit=db_tools,
                    self_insightFaceApp=face_app,
                    ignore_content=False,
                    autoSubThread=True,
                    subThreadSize=2,
                    riskLevel=args.risk,
                    category=args.category,
                    save_image=True,
                    stored_no_face_image_url_set=no_face_urls,
                    stored_no_face_image_url_lock=no_face_lock,
                    current_depth=0,
                    max_depth=1  # Set to 1 to prevent recursive crawling
                )
                future_to_url[future] = url
                
            except Exception as e:
                p_error(f"Error submitting URL {url}: {str(e)}")
        
        # Process results as they complete
        completed = 0
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            completed += 1
            try:
                future.result()
                p_info(f"Completed {completed}/{len(urls)}: {url}")
            except Exception as e:
                p_error(f"Error processing {url}: {str(e)}")
    
    p_info("All URLs processed. Exiting...")

if __name__ == "__main__":
    main()






