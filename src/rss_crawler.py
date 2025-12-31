import feedparser
from lib.news_crawler import SingleNewsCrawler
from lib.output.consolePrint import p_info, p_error, p_title, p_warn, p_log
from lib.user_agent_tools import randomUserAgent
from lib.output.banner import printBanner
from lib.load_config import load_config_from_file
from lib.database_tools import DatabaseTools
import sys
import os
import psycopg2
from lib.init_insightface import initilate_insightface
import time
import timeit
import argparse

# Global değişkenler
CONFIG = None
ThreadSize = None
ConnPoolSize = None
insightFaceApp = None

# ------------------ LOAD CONFIG AND CHECK AREA ----------------------
# Main Config değişkeni
CONFIG = load_config_from_file()

# Config okuma durumunu kontrol et
if not CONFIG[0]:
    sys.exit(-1)

# Thread boyutu ve havuz boyutu tanımla
ThreadSize = CONFIG[1]["service"]["thread"]

# ------------------ END LOAD CONFIG AND CHECK AREA ----------------------

# Banner'ı yazdır
printBanner(CONFIG)

# ------------------ BEGIN DATABASE TOOLS AND CONNECTIONS --------------------
RSS_URL_FILE = "rss.txt"


argParser = argparse.ArgumentParser()
argParser.add_argument("--rss", type=str, help="RSS dosyasının yolunu belirtin", default="rss.txt",required=False)
argParser.add_argument("--risk-level", type=str, help="Risk seviyesini belirtin",required=True)
argParser.add_argument("--category", type=str, help="Kategoriyi belirtin", required=True)
args = argParser.parse_args()


if args.rss:
    RSS_URL_FILE = args.rss
if args.risk_level:
    RISK_LEVEL = args.risk_level
if args.category:
    CATEGORY = args.category



# Veritabanı araçlarını başlat
DatabaseTools = DatabaseTools(CONFIG[1]["database_config"])


RSS_URL_ARRAY = []

p_info(f"RSS dosyasından URL'ler yükleniyor: {str(RSS_URL_FILE)}")

try:
    with open(RSS_URL_FILE, "r", encoding="utf-8") as rssFile:
        for line in rssFile:
            line = line.strip()
            if line:  # Boş satırları atla
                RSS_URL_ARRAY.append(line)
except FileNotFoundError:
    p_error(f"RSS dosyası bulunamadı: {RSS_URL_FILE}")
    sys.exit(-1)
except Exception as e:
    p_error(f"RSS dosyası okunurken hata oluştu: {str(e)}")
    sys.exit(-1)

p_info(f"Toplam {str(len(RSS_URL_ARRAY))} RSS URL'si yüklendi")

# InsightFace modelini başlat
p_info("InsightFace modeli başlatılıyor...")
start_time = time.time()
try:
    insightFaceApp = initilate_insightface(main_conf=CONFIG)
    elapsed_time = time.time() - start_time
    p_info(f"InsightFace başarıyla yüklendi ({elapsed_time:.2f} saniye)")
except Exception as e:
    p_error(f"InsightFace başlatılamadı: {str(e)}")
    insightFaceApp = None








# Ana döngü
while True:
    p_info("RSS kaynaklarını tarama başlıyor...")
    
    for rssLink in RSS_URL_ARRAY:
        p_info(f"RSS kaynağı taranıyor: {rssLink}")
        
        try:
            feed = feedparser.parse(rssLink)
            if not feed.entries:
                p_warn(f"RSS kaynağında giriş bulunamadı: {rssLink}")
                continue
                
        except Exception as err:
            p_error(f"RSS kaynağı ayrıştırılırken hata oluştu: {str(err)}")
            time.sleep(1)
            continue
        
        for singleDict in feed.entries:
            try:
                entryTitle = singleDict.title
                entryLink = singleDict.link
                entryPublished = singleDict.get('published', 'Tarih bilgisi yok')
                
                p_info(f"Haber taranıyor: {entryTitle}")
                start = timeit.default_timer()
                
                WebEye = SingleNewsCrawler(
                    DatabaseToolkit_object=DatabaseTools,
                    FirstTargetAddress=entryLink,
                    ThreadSize=ThreadSize,
                    CONFIG=CONFIG,
                    ignore_db=False,
                    ignore_content=True,
                    NewsDate=entryPublished,
                    NewsTitle=entryTitle,
                    insightfaceApp=insightFaceApp
                )
                
                WebEye.startCrawl(
                    riskLevel=RISK_LEVEL,
                    category=CATEGORY,
                    save_image=False
                )
                
                end = timeit.default_timer()
                p_info(f"Haber tarama süresi: {str(round(end-start, 1))} saniye")
                
            except KeyboardInterrupt:
                p_warn("Tarama kullanıcı tarafından durduruldu (CTRL+C).")
                sys.exit(0)
            except Exception as err:
                p_error(f"Haber taranırken hata oluştu: {str(err)}")
                continue
    
    p_info(f"Tüm RSS kaynakları tarandı. 3600 saniye (1 saat) bekleniyor...")
    time.sleep(3600)
