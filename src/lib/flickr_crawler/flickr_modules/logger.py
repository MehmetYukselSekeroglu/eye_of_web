#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flickr Crawler Logger Module

This module provides a Logger class for the Flickr crawler.
"""

import os
import logging
import sys
from datetime import datetime


class Logger:
    """Logger class for the Flickr crawler."""
    
    def __init__(self, output_dir="output_flickr", log_level=logging.INFO):
        """
        Initialize the logger.
        
        Args:
            output_dir: Directory where log files will be stored.
            log_level: Logging level.
        """
        self.output_dir = output_dir
        self.log_level = log_level
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger("flickr_crawler")
        self.logger.setLevel(log_level)
        
        # Remove existing handlers to avoid duplicates
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter('%(message)s')  # Simple format for console
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Create file handler
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(output_dir, f"flickr_crawler_{timestamp}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        self.log_file_path = log_file
        
        # Show initialization message
        self.info(f"Logger initialized. Log file: {log_file}")
    
    def debug(self, message):
        """Log a debug message."""
        self.logger.debug(message)
    
    def info(self, message):
        """Log an info message."""
        self.logger.info(message)
    
    def warning(self, message):
        """Log a warning message."""
        self.logger.warning(message)
    
    def error(self, message):
        """Log an error message."""
        self.logger.error(message)
    
    def critical(self, message):
        """Log a critical message."""
        self.logger.critical(message)
        
    def flush(self, message, with_newline=False):
        """
        Print a message without logging and without newline.
        
        This is a workaround for end="" functionality.
        The message will be printed to stdout but not logged to file.
        
        Args:
            message: The message to print.
            with_newline: Whether to add a newline at the end.
        """
        if with_newline:
            print(message)
        else:
            print(message, end="", flush=True) 