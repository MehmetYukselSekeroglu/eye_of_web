#! /usr/bin/env python3
#! -*- coding: utf-8 -*-
#! author: Wesker
#! date: 2025-03-19
#! description: URL parser

from urllib.parse import urlparse
from urllib.parse import unquote



def prepare_url(target_url:str) -> dict:
    """
    Prepares the URL for the database

    Args:
        target_url (str): The URL to prepare

    Returns:
        dict: The prepared URL
    """
    decoded_url = unquote(target_url)
    parsed_url  = urlparse(decoded_url)
    return {
        "origin":decoded_url,
        "protocol":parsed_url.scheme,
        "base_domain":parsed_url.netloc,
        "path":parsed_url.path,
        "etc":parsed_url.params + parsed_url.query 
    }