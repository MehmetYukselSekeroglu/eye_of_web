import re 

def extract_emails(text:str) -> list:
    """
    Extracts email addresses from the given text.
    
    Args:
        text (str): The text to search for email addresses
        
    Returns:
        list: A list of found email addresses
        
    Example:
        >>> text = "Contact us at info@example.com or support@test.com"
        >>> extract_emails(text)
        ['info@example.com', 'support@test.com']
    """
    # Email regex pattern
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    
    # Find all email addresses in the text
    emails = re.findall(email_pattern, text)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_emails = [x for x in emails if not (x in seen or seen.add(x))]
    
    return unique_emails


def extract_phone_numbers(text:str) -> list:
    """
    Extracts phone numbers from the given text.
    Supports various formats:
    - International format: +90 555 123 4567
    - Turkish format: 0555 123 4567
    - Without spaces: 05551234567
    - With dashes: 0555-123-4567
    
    Args:
        text (str): The text to search for phone numbers
        
    Returns:
        list: A list of found phone numbers in standardized format
        
    Example:
        >>> text = "Call us at +90 555 123 4567 or 0555-123-4567"
        >>> extract_phone_numbers(text)
        ['+90 555 123 4567', '0555 123 4567']
    """
    # Phone number regex pattern
    phone_pattern = r'(?:\+90|0)?\s*([5][0-9]{2})\s*[-]?\s*([0-9]{3})\s*[-]?\s*([0-9]{4})'
    
    # Find all phone numbers in the text
    matches = re.finditer(phone_pattern, text)
    
    # Process and standardize the found numbers
    phone_numbers = []
    for match in matches:
        # Extract the groups
        groups = match.groups()
        
        # Reconstruct the number in a standard format
        if match.group(0).startswith('+90'):
            # International format
            formatted_number = f"+90 {groups[0]} {groups[1]} {groups[2]}"
        else:
            # Turkish format
            formatted_number = f"0{groups[0]} {groups[1]} {groups[2]}"
            
        phone_numbers.append(formatted_number)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_numbers = [x for x in phone_numbers if not (x in seen or seen.add(x))]
    
    return unique_numbers



def is_linkedin_profile_picture_url(url: str) -> bool:
    """
    Check if a URL is a LinkedIn profile picture URL.
    
    LinkedIn profile picture URLs typically follow a pattern like:
    https://media.licdn.com/dms/image/...
    
    Args:
        url: The URL to check
        
    Returns:
        bool: True if the URL is a LinkedIn profile picture URL, False otherwise
    """
    # Pattern for LinkedIn profile picture URLs
    linkedin_pattern = r"^https?://media\.licdn\.com/dms/image/.+/profile-displayphoto-shrink_.+$"
    
    return bool(re.match(linkedin_pattern, url))
