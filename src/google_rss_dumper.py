import googlesearch
import requests
import re
import os
import time
import colorama
import datetime
import html
import feedparser
import concurrent.futures
from lib.output.consolePrint import p_info, p_error, p_warn, p_log


def search_google(query, num_results=100):
    """
    Google arama sonuçlarını döndürür
    
    Args:
        query: Arama sorgusu
        num_results: Arama sonuçlarının sayısı
        
    Returns:
        list: Arama sonuçlarını içeren bir liste
    """
    try:
        search_results = googlesearch.search(query, num_results=num_results)
        return list(search_results)
    except Exception as e:
        p_error(f"Error searching Google: {e}")
        return []
    
    
def request_url(url):
    """
    URL'i istek yapar ve yanıtı döndürür
    
    Args:
        url: İstek yapılacak URL

    Returns:
        str: URL'in yanıtı
    """
    try:
        p_info(f"Requesting URL: {url}")
        response = requests.get(url)
        return response.text
    except Exception as e:
        p_error(f"Error requesting URL {url}: {e}")
        return None
    

def extract_rss_links(html_content):
    """
    HTML içinden RSS linklerini çıkarır
    
    Args:
        html_content: HTML içeriği

    Returns:
        list: RSS linklerini içeren bir liste
    """
    try:
        # RSS bağlantılarını bulmak için regex pattern oluştur
        # RSS bağlantıları genellikle .xml, /rss/, /feed/ gibi ifadeler içerir
        rss_patterns = [
            r'https?://[^\s"\'<>]+\.xml',  # .xml ile biten URL'ler
            r'https?://[^\s"\'<>]+/rss[^\s"\'<>]*',  # /rss içeren URL'ler
            r'https?://[^\s"\'<>]+/feed[^\s"\'<>]*',  # /feed içeren URL'ler
            r'https?://[^\s"\'<>]+/atom[^\s"\'<>]*'   # /atom içeren URL'ler
        ]
        
        rss_links = []
        
        # Her bir pattern için HTML içeriğini tara
        for pattern in rss_patterns:
            matches = re.findall(pattern, html_content)
            rss_links.extend(matches)
        
        # Tekrarlanan bağlantıları kaldır
        rss_links = list(set(rss_links))
        
        # Bağlantıları temizle (HTML entity'leri decode et)
        rss_links = [html.unescape(link) for link in rss_links]
        
        p_info(f"Found {len(rss_links)} RSS links")
        return rss_links
    except Exception as e:
        p_error(f"Error extracting RSS links: {e}")
        return []
    

def save_rss_links(rss_links, output_file):
    """
    RSS linklerini dosyaya kaydeder
    
    Args:
        rss_links: RSS linkleri
        output_file: Çıktı dosyası
    """
    try:
        with open(output_file, 'a') as f:
            for link in rss_links:
                f.write(link + '\n')
        p_info(f"RSS links saved to {output_file}")
    except Exception as e:
        p_error(f"Error saving RSS links: {e}")


def verify_rss_link(link):
    """
    Tek bir RSS linkini doğrular
    
    Args:
        link: RSS linki
        
    Returns:
        str or None: Doğrulanmış RSS linki veya None
    """
    try:
        p_info(f"Verifying RSS link: {link}")
        # RSS feed'i doğrulamak için feedparser kullan
        feed = feedparser.parse(link)
        
        # Feed'in başarılı bir şekilde çözümlendiğini kontrol et
        if not feed.entries:
            p_warn(f"Invalid RSS feed: {link}")
            return None
        else:
            p_info(f"Valid RSS feed found: {link}")
            return link
    except Exception as e:
        p_error(f"Error verifying RSS link {link}: {e}")
        return None


def process_search_result(result):
    """
    Bir arama sonucunu işler
    
    Args:
        result: İşlenecek arama sonucu
        
    Returns:
        list: Doğrulanmış RSS linkleri
    """
    html_content = request_url(result)
    if not html_content:
        return []
    
    rss_links = extract_rss_links(html_content)
    
    # RSS linklerini doğrula
    verified_links = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_link = {executor.submit(verify_rss_link, link): link for link in rss_links}
        for future in concurrent.futures.as_completed(future_to_link):
            link = future_to_link[future]
            try:
                verified_link = future.result()
                if verified_link:
                    verified_links.append(verified_link)
            except Exception as e:
                p_error(f"Error processing link {link}: {e}")
    
    return verified_links


def main():
    """
    Ana fonksiyon
    """
    try:
        # Çıktı dosyasını oluştur
        output_file = 'rss_links_google_search.txt'
        with open(output_file, 'w') as f:
            f.write(f"# RSS links found on {datetime.datetime.now()}\n")
        
        # Arama sorgusu
        query = "haberler rss bağlantıları"
        
        p_info(f"Starting Google search for: {query}")
        # Google arama sonuçlarını al
        search_results = search_google(query)
        p_info(f"Found {len(search_results)} search results")
        
        all_verified_links = []
        
        # ThreadPoolExecutor ile arama sonuçlarını paralel işle
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            p_info(f"Processing search results with 4 threads")
            future_to_result = {executor.submit(process_search_result, result): result for result in search_results}
            
            for i, future in enumerate(concurrent.futures.as_completed(future_to_result)):
                result = future_to_result[future]
                try:
                    verified_links = future.result()
                    all_verified_links.extend(verified_links)
                    p_info(f"Progress: {i+1}/{len(search_results)} search results processed")
                except Exception as e:
                    p_error(f"Error processing search result {result}: {e}")
        
        # Tekrarlanan linkleri kaldır
        all_verified_links = list(set(all_verified_links))
        p_info(f"Total verified RSS links found: {len(all_verified_links)}")
        
        # Tüm doğrulanmış linkleri kaydet
        save_rss_links(all_verified_links, output_file)
            
    except Exception as e:
        p_error(f"Error in main: {e}")

if __name__ == "__main__":
    main()