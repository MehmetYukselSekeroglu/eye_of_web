#! /usr/bin/env python3
#! -*- coding: utf-8 -*-
#! author: Wesker
#! date: 2025-03-19
#! description: Hash functions for images


import hashlib




def hash_image_sha1(image_data: bytes) -> str:
    """
    Hashes the image data using SHA1 algorithm

    Args:
        image_data (bytes): Image data to hash

    Returns:
        str: Hashed image data
    """
    return hashlib.sha1(image_data).hexdigest()

def hash_image_sha256(image_data: bytes) -> str:
    """
    Hashes the image data using SHA256 algorithm

    Args:
        image_data (bytes): Image data to hash

    Returns:
        str: Hashed image data
    """
    return hashlib.sha256(image_data).hexdigest()


def hash_image_md5(image_data: bytes) -> str:
    """
    Hashes the image data using MD5 algorithm

    Args:
        image_data (bytes): Image data to hash

    Returns:
        str: Hashed image data
    """
    return hashlib.md5(image_data).hexdigest()


