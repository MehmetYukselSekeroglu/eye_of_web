# EyeOfWeb Crawler User Guide

This document provides detailed usage instructions for all crawlers in the EyeOfWeb system.

## 📋 Table of Contents

- [Crawler Types](#crawler-types)
- [Requirements](#requirements)
- [Crawler Details](#crawler-details)
  - [Single Domain Crawler](#1-single-domain-crawler)
  - [RSS Crawler](#2-rss-crawler)
  - [Google Search Crawler](#3-google-search-crawler)
  - [Google Images Crawler](#4-google-images-crawler)
  - [Twitter Crawler (File Based)](#5-twitter-crawler-file-based)
  - [Twitter Crawler (Google Based)](#6-twitter-crawler-google-based)
  - [Facebook Crawler](#7-facebook-crawler)
  - [Telegram Crawler (Pyrogram)](#8-telegram-crawler-pyrogram)
  - [Telegram Crawler (Telethon)](#9-telegram-crawler-telethon)
  - [Flickr Crawler](#10-flickr-crawler)
- [Docker vs Host OS](#docker-vs-host-os)
- [Common Parameters](#common-parameters)

---

## Crawler Types

| Crawler | Selenium | Docker | Description |
|---------|----------|--------|-------------|
| `single_domain.py` | ❌ | ✅ | Single domain/URL scanning |
| `rss_crawler.py` | ❌ | ✅ | RSS/Atom feed scanning |
| `google_search_crawler.py` | ❌ | ✅ | Google/DuckDuckGo search results |
| `google_images_crawler.py` | ✅ | ❌ | Google Images scanning |
| `twitter_crawler_file_based.py` | ✅ | ❌ | Twitter profile scanning (from file) |
| `twitter_crawler_google_based.py` | ✅ | ❌ | Twitter profile scanning (from Google) |
| `facebook_crawler.py` | ✅ | ❌ | Facebook profile scanning |
| `pyrogram_telegram_crawler_main.py` | ❌ | ✅ | Telegram scanning (Pyrogram API) |
| `telethon_telegram_crawler_main.py` | ❌ | ✅ | Telegram scanning (Telethon API) |
| `flicker_crawler.py` | ✅ | ❌ | Flickr image scanning |

---

## Requirements

### Docker Environment (Non-Selenium crawlers)
```bash
pip install -r docker_crawler_requirements.txt
```

### Host OS (Selenium crawlers)
```bash
pip install -r crawler_requirements.txt
# + Chrome/Firefox browser must be installed
```

### All Crawlers
- `config/config.json` file (auto-generated in Docker)
- PostgreSQL and Milvus connection
- InsightFace model (buffalo_l or antelopev2)

---

## Crawler Details

### 1. Single Domain Crawler

**File:** `single_domain.py`

Scans a single website or URL list, detecting faces in images.

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--url` | * | - | Single URL to scan |
| `--file` | * | - | File containing URL list |
| `--max-depth` | ✅ | - | Maximum crawl depth |
| `--risk-level` | ❌ | - | Risk level (low/medium/high) |
| `--category` | ❌ | - | Category tag |
| `--ignore-db` | ❌ | 0 | Skip database check (1/0) |
| `--ignore-content` | ❌ | 0 | Skip content check (1/0) |
| `--save-image` | ❌ | False | Save images locally |

> `*` = Either `--url` or `--file` is required

#### Usage Examples

```bash
# Single URL scan
python single_domain.py --url "https://example.com" --max-depth 3

# Scan from URL list file
python single_domain.py --file urls.txt --max-depth 2 --risk-level high

# Deep scan (all options)
python single_domain.py \
    --url "https://example.com" \
    --max-depth 5 \
    --risk-level medium \
    --category "news" \
    --ignore-db 0 \
    --save-image
```

#### URL File Format
```
https://example1.com
https://example2.com/page
https://example3.com/category/article
```

---

### 2. RSS Crawler

**File:** `rss_crawler.py`

Continuously scans RSS/Atom feeds and detects faces in news articles.

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--rss` | ❌ | rss.txt | RSS URLs file |
| `--risk-level` | ✅ | - | Risk level |
| `--category` | ✅ | - | Category tag |

#### Usage Examples

```bash
# Use default rss.txt file
python rss_crawler.py --risk-level low --category "news"

# Custom RSS file
python rss_crawler.py --rss my_feeds.txt --risk-level medium --category "tech"
```

#### RSS File Format (rss.txt)
```
https://feeds.bbci.co.uk/news/rss.xml
https://rss.nytimes.com/services/xml/rss/nyt/World.xml
https://www.theguardian.com/world/rss
```

#### How It Works
1. Reads URLs from RSS file
2. Parses each feed with feedparser
3. Scans each article with SingleNewsCrawler
4. Waits 1 hour and repeats (infinite loop)

> **Note:** Can be stopped with CTRL+C

---

### 3. Google Search Crawler

**File:** `google_search_crawler.py`

Scans websites from Google/DuckDuckGo search results.

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--query` | ✅ | - | Search query |
| `--num-results` | ❌ | 10 | Number of results |
| `--backend` | ❌ | playwright | Browser backend (`playwright` or `selenium`) |
| `--risk-level` | ❌ | - | Risk level |
| `--category` | ❌ | - | Category |

#### Playwright Backend Features (`--backend playwright`)
- **Speed:** Up to 10x faster than Selenium.
- **Parallel Scanning:** Concurrent page scanning using multi-tab (default 3 tabs) for search results.
- **Facebook Integration:** High-speed scanning for Facebook profiles and search results using optimized crawler.
- **Privacy:** Advanced anti-bot measures included.

#### Usage Examples


```bash
# Simple search
python google_search_crawler.py --query "example search"

# Advanced search
python google_search_crawler.py \
    --query "site:example.com inurl:profile" \
    --num-results 50 \
    --risk-level high
```

---

### 4. Google Images Crawler

**File:** `google_images_crawler.py`

> ⚠️ **Requires Selenium - Does NOT work in Docker**

Searches Google Images and performs face detection.

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--keyword` | ✅ | - | Search keyword |
| `--scroll_count` | ✅ | - | Page scroll count |

#### Usage Examples

```bash
python google_images_crawler.py --keyword "person name" --scroll_count 10
```

---

### 5. Twitter Crawler (File Based)

**File:** `twitter_crawler_file_based.py`

> ⚠️ **Requires Selenium - Does NOT work in Docker**

Reads Twitter/X profile URLs from a file and scans them.

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--file` | ✅ | - | Twitter URL/username file |
| `--threads` | ❌ | 3 | Thread count (max 3) |
| `--headless` | ❌ | True | Headless mode |
| `--driver_path` | ❌ | - | ChromeDriver path |
| `--temp_folder` | ❌ | temp | Temporary folder |

#### Usage Examples

```bash
python twitter_crawler_file_based.py --file twitter_users.txt

python twitter_crawler_file_based.py \
    --file twitter_users.txt \
    --threads 2 \
    --headless
```

#### Twitter File Format
```
https://twitter.com/user1
https://x.com/user2
@user3
user4
```

---

### 6. Twitter Crawler (Google Based)

**File:** `twitter_crawler_google_based.py`

> ⚠️ **Requires Selenium - Does NOT work in Docker**

Finds Twitter profiles from Google search results and scans them.

#### Usage
```bash
python twitter_crawler_google_based.py
```

---

### 7. Facebook Crawler

**File:** `facebook_crawler.py`

> ⚠️ **Requires Selenium - Does NOT work in Docker**

Searches for people/profiles on Facebook and scans profile photos.

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--keyword` | * | - | Search keyword |
| `--file` | * | - | Keywords file |
| `--scroll_count` | ❌ | 5 | Scroll count |
| `--scroll_pause_time` | ❌ | 2 | Scroll pause time (sec) |
| `--headless` | ❌ | True | Headless mode |
| `--driver_path` | ❌ | - | ChromeDriver path |
| `--temp_folder` | ❌ | temp | Temporary folder |
| `--backend` | ❌ | selenium | Browser backend (`selenium` or `playwright`) |

> `*` = Either `--keyword` or `--file` is required

#### Usage Examples

```bash
# Single keyword
python facebook_crawler.py --keyword "John Doe"

# Multiple keywords (comma-separated)
python facebook_crawler.py --keyword "John Doe,Jane Smith"

# Keywords from file
python facebook_crawler.py --file keywords.txt --scroll_count 10
```

---

### 8. Telegram Crawler (Pyrogram)

**File:** `pyrogram_telegram_crawler_main.py`

Scans Telegram groups and channels using Pyrogram API.

#### Requirements
- Telegram API ID and API Hash ([my.telegram.org](https://my.telegram.org))
- Telegram settings in `config/config.json`

#### Configuration

Edit these variables in the file:
```python
API_ID = 12345              # Telegram API ID
API_HASH = 'your_api_hash'  # Telegram API Hash
SESSION_NAME = 'session'    # Session file name
```

#### Usage
```bash
python pyrogram_telegram_crawler_main.py
```

#### How It Works
1. Connects to Telegram (asks for phone and code on first run)
2. Lists all groups and channels
3. Downloads images from messages and profile photos
4. Performs face detection with InsightFace
5. Saves to database

---

### 9. Telegram Crawler (Telethon)

**File:** `telethon_telegram_crawler_main.py`

Scans Telegram groups and channels using Telethon API. Alternative to Pyrogram.

#### Configuration

Edit these variables in the file:
```python
API_ID = 12345              # Telegram API ID
API_HASH = 'your_api_hash'  # Telegram API Hash
SESSION_NAME = 'session'    # Session file name
```

#### Modes

```python
PROCESS_REALTIME_MESSAGES = True   # Process real-time messages
PROCESS_ONLY_SENDER_PROFILES = True # Process only sender profiles
```

#### Usage
```bash
python telethon_telegram_crawler_main.py
```

---

### 10. Flickr Crawler

**File:** `flicker_crawler.py`

> ⚠️ **Requires Selenium - Does NOT work in Docker**

Searches Flickr for images and performs face detection.

#### Usage
```bash
python flicker_crawler.py --keyword "search term"
```

---

## Docker vs Host OS

### Running in Docker Container

```bash
# Connect to container
sudo docker exec -it eyeofweb_crawler bash

# Run NON-Selenium crawlers
python single_domain.py --url "https://example.com" --max-depth 3
python rss_crawler.py --risk-level low --category "news"
python google_search_crawler.py --query "search term"
python pyrogram_telegram_crawler_main.py
```

### Running on Host OS

```bash
# Virtual environment
python3 -m venv crawler_venv
source crawler_venv/bin/activate

# Install dependencies
pip install -r crawler_requirements.txt

# Run Selenium-based crawlers
python twitter_crawler_file_based.py --file users.txt
python google_images_crawler.py --keyword "search" --scroll_count 5
python facebook_crawler.py --keyword "person name"
```

---

## Common Parameters

### Risk Level (`--risk-level`)
- `low` - Low risk
- `medium` - Medium risk
- `high` - High risk
- `critical` - Critical risk

### Category (`--category`)
Custom categories can be defined:
- `news`
- `social_media`
- `technology`
- `sports`
- etc.

### Headless Mode
In Selenium-based crawlers, the browser runs invisibly. Use `--no-headless` for debugging.

---

## Troubleshooting

### Config File Error
```
Failed To Load Config File: config/config.json
```
**Solution:** Run `python generate_config.py` or restart Docker container.

### Selenium Error
```
WebDriverException: chromedriver not found
```
**Solution:** 
```bash
pip install webdriver-manager
# or download ChromeDriver manually
```

### InsightFace Model Error
```
Model not found: buffalo_l
```
**Solution:** Model downloads automatically, check internet connection.

---

**EyeOfWeb Crawler Suite** - Powered by InsightFace, Selenium & Telegram API 🕸️
