#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# @Author: Mehmet yüksel şekeroğlu
# @Date: 2025-05-14
# @Filename: __init__.py
# @Last modified by: Mehmet yüksel şekeroğlu
# @Last modified time: 2025-05-14

"""
Twitter crawler module for EyeOfWeb to extract profile information from Twitter (X).
"""

from lib.twitter_crawler.twitter_profile_crawler import TwitterProfileCrawler

__all__ = [
    'TwitterProfileCrawler',
] 