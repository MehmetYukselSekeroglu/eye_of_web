import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import re

def get_x_profile_page_source(username: str, target_xpath: str, driver_executable_path: str = None, wait_timeout: int = 30):
    """
    Navigates to an X (Twitter) profile, waits for a specific element, and returns the page source.

    Args:
        username (str): The X username (e.g., "elonmusk").
        target_xpath (str): The XPath of the element to wait for.
        driver_executable_path (str, optional): Path to the ChromeDriver. Defaults to None (Selenium tries to use system PATH).
        wait_timeout (int, optional): Maximum time in seconds to wait for the element. Defaults to 30.

    Returns:
        str: The page source HTML if successful, None otherwise.
    """
    profile_url = f"https://x.com/{username}"

    chrome_options = Options()
    #chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    chrome_options.add_argument("--page-load-strategy=eager")  # Interact with page as soon as DOM is ready

    if driver_executable_path:
        service = Service(executable_path=driver_executable_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        driver = webdriver.Chrome(options=chrome_options)

    page_source = None
    try:
        print(f"Navigating to {profile_url}...")
        driver.get(profile_url)

        print(f"Looking for element with XPath: {target_xpath} during page load")
        
        start_time = time.time()
        found = False
        
        while time.time() - start_time < wait_timeout:
            try:
                element = driver.find_element(By.XPATH, target_xpath)
                if element:
                    found = True
                    print("Element found early during page load!")
                    break
            except NoSuchElementException:
                time.sleep(0.1)
                continue
        
        if found:
            print("Capturing page source immediately...")
            page_source = driver.page_source
            print("Page source retrieved successfully before full page load.")
        else:
            print(f"Element not found during early detection phase. Trying one last time after {wait_timeout}s total wait or if page appears loaded.")
            # Fallback to WebDriverWait if early detection fails, to ensure we wait for the specified timeout or page load state
            try:
                WebDriverWait(driver, max(0, wait_timeout - (time.time() - start_time))).until(
                    EC.presence_of_element_located((By.XPATH, target_xpath))
                )
                print("Element found after explicit wait. Retrieving page source...")
                time.sleep(2) # Give a moment for any final JS rendering
                page_source = driver.page_source
                print("Page source retrieved successfully.")
            except TimeoutException:
                print(f"Timeout: Element with XPath not found within {wait_timeout} seconds even with explicit wait.")
            
    except TimeoutException:
        # This might be redundant if the inner try-except for WebDriverWait handles it, but good for general get() timeout
        print(f"Overall Timeout: Problem loading page or element with XPath not found within {wait_timeout} seconds.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("Closing WebDriver.")
        driver.quit()

    return page_source

def extract_profile_image_block(html_content: str):
    """
    Extracts the HTML block containing the profile image from the page source.

    Args:
        html_content (str): The HTML page source.

    Returns:
        str: The HTML block as a string if found, None otherwise.
    """
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the div with the background-image style for the profile picture
    # Example style: style="background-image: url(&quot;https://pbs.twimg.com/profile_images/...&quot;);
    image_divs = soup.find_all('div', style=lambda value: value and 'background-image' in value and 'pbs.twimg.com/profile_images/' in value)
    
    target_block = None

    for div in image_divs:
        # The direct parent of this div should be the one with aria-label="Opens profile photo"
        parent_aria_label_div = div.find_parent('div')
        if parent_aria_label_div and parent_aria_label_div.get('aria-label', '') == "Opens profile photo":
            # The parent of THAT div is the block we are interested in, matching user's snippet structure
            desired_block_parent = parent_aria_label_div.find_parent('div')
            if desired_block_parent:
                # Check if this parent has classes like r-1p0dtai (from user snippet example)
                # This is an additional check to be more specific, but can be optional
                if desired_block_parent.get('class') and any(cls in desired_block_parent.get('class') for cls in ['r-1p0dtai', 'r-1pi2tsx']):
                    target_block = desired_block_parent
                    break 
                elif not target_block: # If no specific class match yet, take it as a potential candidate
                    target_block = desired_block_parent 
            # If specific class check fails or is not strict, and we already found a block from a previous iteration, 
            # we might want to be careful not to overwrite a potentially better (more specific) match.
            # For now, the first one that fits the parent structure is taken or overwritten by one with specific classes.

    if target_block:
        # Extract the image URL from the target_block
        img_tag = target_block.find('img')
        if img_tag and img_tag.get('src'):
            url = img_tag.get('src')
            # Replace 200x200 with 400x400 in the URL
            url = url.replace('_200x200', '_400x400')
            return url
        
        # If img tag not found or doesn't have src, try to extract from background-image style
        div_with_bg = target_block.find('div', style=lambda value: value and 'background-image' in value)
        if div_with_bg:
            style_attr = div_with_bg.get('style', '')
            url_match = re.search(r'url\(["\']?(.*?)["\']?\)', style_attr)
            if url_match:
                url = url_match.group(1)
                # Replace 200x200 with 400x400 in the URL
                url = url.replace('_200x200', '_400x400')
                return url
        
        # If we still couldn't find the URL, return None
        return None
    else:
        # Fallback: Try finding the img tag directly as in twitter_crawler_test.py logic
        # This is to find the URL, not the block the user asked for now.
        # For this request, we focus on the block.
        print("Could not find the specific profile image block structure.")
        # As an alternative, try to find the div with aria-label="Opens profile photo" directly
        aria_div = soup.find('div', attrs={"aria-label": "Opens profile photo"})
        if aria_div:
            # And then its parent
            potential_block = aria_div.find_parent('div')
            if potential_block:
                print("Found an alternative block (parent of aria-label div):")
                return str(potential_block)
        return None

if __name__ == "__main__":
    # --- Configuration ---
    TARGET_USERNAME = "MehmetYSkroglu"
    ELEMENT_XPATH = '//*[@id="react-root"]/div/div/div[2]/main/div/div/div/div[1]/div/div[3]/div/div/div[1]/div/div[1]/div[1]/div[2]/div/div[2]/div/a/div[4]/div'
    DRIVER_PATH = "/bin/chromedriver"
    # --- End Configuration ---

    html_source = get_x_profile_page_source(TARGET_USERNAME, ELEMENT_XPATH, DRIVER_PATH)

    if html_source:
        output_filename = f"{TARGET_USERNAME}_page_source.html"
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(html_source)
        print(f"Page source saved to {output_filename}")

        print("\n--- Extracted Profile Image Block ---")
        image_block_html = extract_profile_image_block(html_source)
        if image_block_html:
            print(image_block_html)
        else:
            print("Profile image block not found in the page source.")
    else:
        print("Failed to retrieve page source.") 