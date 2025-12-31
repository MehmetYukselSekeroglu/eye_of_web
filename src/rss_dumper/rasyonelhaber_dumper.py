#! /usr/bin/env python3

import requests
import bs4

STATIC_URL = "https://www.rasyonelhaber.com/rss/anasayfa/"

def fetch_rss_links():
    response = requests.get(STATIC_URL)
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    article = soup.find("article", class_="col-span-2")
    if not article:
        return []
    rss_links = article.find_all("a", href=lambda href: href and "/rss/" in href)
    return [link.get("href") for link in rss_links]

def main():
    rss_links = fetch_rss_links()
    unique_links = sorted(list(set(rss_links)))
    for rss_link in unique_links:
        print(rss_link)

if __name__ == "__main__":
    main()
        