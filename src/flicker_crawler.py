import argparse
import os
import sys
import time
import traceback
import logging
import requests
from lib.flickr_crawler_module import FlickrCrawlerModule
from lib.database_tools import DatabaseTools
from lib.init_insightface import initilate_insightface
from lib.load_config import load_config_from_file

CONFIG = load_config_from_file()

argparser = argparse.ArgumentParser()
argparser.add_argument("--url", type=str, help="URL of the page to crawl")
argparser.add_argument("--max-pages", type=int, help="Maximum number of pages to crawl")
argparser.add_argument("--driver-path", type=str, help="Path to the Chrome driver")
argparser.add_argument("--executable-path", type=str, help="Path to the Chrome executable")
argparser.add_argument("--risk-level", type=str, help="Risk level to use for image processing",required=True)
argparser.add_argument("--category", type=str, help="Category to use for image processing",required=True)

args = argparser.parse_args()


databaseTools = DatabaseTools(CONFIG[1]["database_config"])
insightFaceApp = initilate_insightface(CONFIG)



targetUrl = args.url
maxPages = args.max_pages
driver_path = args.driver_path
executable_path = args.executable_path
riskLevel = args.risk_level
category = args.category

if not maxPages:
    maxPages = 99999

crawler = FlickrCrawlerModule(
    databaseTools=databaseTools,
    insightFaceApp=insightFaceApp,
    targetUrl=targetUrl,
    maxPages=maxPages,
    driver_path=driver_path,
    executable_path=executable_path,
    riskLevel=riskLevel,
    category=category
)
crawler.start()






















