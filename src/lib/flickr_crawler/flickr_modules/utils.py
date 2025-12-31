#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flickr Crawler Utilities Module

This module provides utility functions for the Flickr crawler.
"""

import os
import re
import time
import json


def extract_photo_id(url):
    """
    Extract the photo ID from a Flickr photo URL.
    
    Args:
        url: The Flickr photo URL.
        
    Returns:
        str: The photo ID or a timestamp-based ID if extraction fails.
    """
    match = re.search(r'/(\d+)/?$', url.strip('/'))
    return match.group(1) if match else f"image_{int(time.time()*1000)}"


def save_stats(stats, output_dir):
    """
    Save crawler statistics to a JSON file.
    
    Args:
        stats: Dictionary containing statistics.
        output_dir: Directory where the stats file will be saved.
    """
    stats_file = os.path.join(output_dir, f"crawler_stats_{int(time.time())}.json")
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    return stats_file


def build_page_url(base_url, page_num):
    """
    Build a URL for a specific page in the photostream.
    
    Args:
        base_url: The base URL for the photostream.
        page_num: The page number.
        
    Returns:
        str: The URL for the specified page.
    """
    if page_num <= 1:
        return base_url
    
    # If the URL already has a page parameter, update it
    if 'page' in base_url:
        return re.sub(r'page\d+', f'page{page_num}', base_url)
    
    # If the URL doesn't have a page parameter, add it
    if base_url.endswith('/'):
        return f"{base_url}page{page_num}"
    else:
        return f"{base_url}/page{page_num}"


def format_time(seconds):
    """
    Format time in seconds to a human-readable string.
    
    Args:
        seconds: Time in seconds.
        
    Returns:
        str: Formatted time string.
    """
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.2f} hours" 