#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Twitter Profile Crawler Test Script

This script demonstrates how to use the TwitterProfileCrawler to download profile images.
"""

import os
import argparse
import sys
from lib.output.consolePrint import p_info, p_error, p_warn, p_log

# Add the project directory to path to make imports work
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    from lib.twitter_crawler.twitter_profile_crawler import TwitterProfileCrawler
except ImportError:
    p_error("Error importing TwitterProfileCrawler. Please ensure the module is properly installed.")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Twitter Profile Image Downloader')
    parser.add_argument('username', help='Twitter/X username (without @)')
    parser.add_argument('--output', '-o', dest='output_path', help='Output path for the image')
    parser.add_argument('--driver', '-d', dest='driver_path', help='Path to ChromeDriver')
    parser.add_argument('--chrome', '-c', dest='chrome_path', help='Path to Chrome executable')
    parser.add_argument('--visible', '-v', action='store_true', help='Show browser window (non-headless mode)')
    
    args = parser.parse_args()
    
    # Prepare output path
    if not args.output_path:
        args.output_path = f"{args.username}_profile_hd.jpg"
    
    # Prepare full Twitter URL
    profile_url = f"https://x.com/{args.username}"
    
    # Initialize the crawler
    p_info(f"Initializing crawler for {args.username}...")
    crawler = TwitterProfileCrawler(
        headless=not args.visible,
        driver_path=args.driver_path,
        executable_path=args.chrome_path,
        wait_timeout=30
    )
    
    if not crawler.driver:
        p_error("Failed to initialize Chrome driver. Please check ChromeDriver installation.")
        return 1
    
    try:
        # Download the profile image
        p_info(f"Attempting to download profile image for {args.username}...")
        image_binary, extension = crawler.download_profile_picture_return_binary(profile_url)
        
        if not image_binary:
            p_error(f"Failed to download profile image for {args.username}")
            return 1
        
        # Save the image
        with open(args.output_path, 'wb') as f:
            f.write(image_binary)
        
        p_info(f"Successfully downloaded profile image to {args.output_path}")
        return 0
    
    except Exception as e:
        p_error(f"Error during profile image download: {e}")
        return 1
    finally:
        # Always close the crawler
        crawler.close_driver()

if __name__ == "__main__":
    sys.exit(main()) 