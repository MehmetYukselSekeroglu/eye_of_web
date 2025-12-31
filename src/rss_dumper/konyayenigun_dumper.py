#! /usr/bin/env python3

import requests
import bs4

STATIC_URL = "https://www.konyayenigun.com/rss-baglantilari"
CLASS_OF_RSS_LINK = "form-control rounded-0"


def fetch_rss_links():
    response = requests.get(STATIC_URL)
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    # Find input elements with the specified class
    rss_inputs = soup.find_all("input", class_=CLASS_OF_RSS_LINK)
    # Extract the 'value' attribute which contains the RSS link
    return [input_tag.get("value") for input_tag in rss_inputs if input_tag.get("value")]

def main():
    rss_links = fetch_rss_links()
    for rss_link in rss_links:
        print(rss_link)

if __name__ == "__main__":
    main()




