import requests
from urllib.parse import urlparse
from lib.output.consolePrint import p_info, p_error, p_warn, p_log

def is_safe_url__html(url: str) -> bool:
    """
    Checks if a URL contains HTML content.
    
    Args:
        url (str): The URL to check
        
    Returns:
        bool: True if the URL contains HTML content, False otherwise
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Parse the URL to ensure it's valid
        parsed_url = urlparse(url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            p_warn(f"Invalid URL format: {url}")
            return False
        
        # Send a HEAD request first to check content type without downloading full content
        head_response = requests.head(url, timeout=5, allow_redirects=True,headers=headers)
        
        # Check content type from headers
        content_type = head_response.headers.get('Content-Type', '').lower()
        
        # If content type is not available or not clearly defined, make a GET request
        if not content_type or 'text/html' not in content_type:
            # Make a GET request with limited content to verify
            response = requests.get(url, timeout=5, stream=True,headers=headers)
            content = next(response.iter_content(chunk_size=1000)).decode('utf-8', errors='ignore')
            response.close()
            
            # Check if content contains basic HTML tags
            has_html_tags = any(tag in content.lower() for tag in ['<html', '<body', '<head', '<!doctype html'])
            
            if has_html_tags:
                return True
            else:
                p_warn(f"URL does not contain HTML content: {url}")
                return False
        
        return 'text/html' in content_type
        
    except requests.exceptions.RequestException as e:
        p_error(f"Error checking URL {url}: {str(e)}")
        return False
    except Exception as e:
        p_error(f"Unexpected error checking URL {url}: {str(e)}")
        return False
