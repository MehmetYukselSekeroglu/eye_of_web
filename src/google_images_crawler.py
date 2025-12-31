#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# 2025-04-30
#

import argparse
from lib.google_images_crawler import GoogleImagesCrawler
from lib.database_tools import DatabaseTools
from lib.selenium_tools import selenium_browser
from lib.output.consolePrint import p_info, p_error, p_warn, p_log
from lib.init_insightface import initilate_insightface
from lib.load_config import load_config_from_file


configData = load_config_from_file()

if not configData[0]:
    p_error(configData[1])
    exit(1)


argparser = argparse.ArgumentParser()
argparser.add_argument("--keyword", type=str, required=True)
argparser.add_argument("--scroll_count", type=int, required=True)
args = argparser.parse_args()






insightFaceApp = initilate_insightface(configData)
databaseToolkit = DatabaseTools(configData[1]["database_config"])


Crawler = GoogleImagesCrawler(
    databaseToolkit=databaseToolkit,
    faceAnalysis=insightFaceApp
)
Crawler.start(keyword=args.keyword, scroll_attempts_limit=args.scroll_count,num_images=99999,headless=True)



















