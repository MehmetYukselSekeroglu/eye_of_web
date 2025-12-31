#! /usr/bin/env python3
#! -*- coding: utf-8 -*-
#! author: Wesker
#! date: 2025-03-19
#! description: URL image download and hash functions



from .user_agent_tools import randomUserAgent
from .hash import hash_image_sha1
from .numpy_tools import load_ImageFromContext
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def downloadImage_defaultSafe(target_url,timeout_sec=10,req_headers:dict=None,verify_ssl:bool=False) -> tuple:
        try:
            request_header = {
                "User-Agent":randomUserAgent()
            }            
            if req_headers is not None:
                request_header = req_headers
            
                
                
            send_request = requests.get(url=target_url,timeout=timeout_sec,headers=request_header,verify=verify_ssl)
            if not send_request.ok:
                return (False, send_request.status_code, None)
            
            _image_hash = hash_image_sha1(send_request.content) 
            _cv2_image = load_ImageFromContext(send_request.content)           
            
            return (True, _cv2_image, _image_hash)

            
        
        except Exception as err:
            return (False, err,None)

def get_ImageFromUrl(target_url,timeout_sec=10,req_headers:dict=None,verify_ssl:bool=False) -> tuple:
        try:
            
            """
            if not is_safe_image__any(target_url,timeout_sec=timeout_sec,req_headers=req_headers):
                return (False, "Not Safe Image URL!",None)
            """            
            request_header = {
                "User-Agent":randomUserAgent()
            }

                        
            if req_headers is not None:
                request_header = req_headers
            
                
                
            send_request = requests.get(url=target_url,timeout=timeout_sec,headers=request_header,verify=verify_ssl)
            if not send_request.ok:
                return (False, send_request.status_code, None)
            
            _image_hash = hash_image_sha1(send_request.content) 
            _cv2_image = load_ImageFromContext(send_request.content)           
            
            return (True, _cv2_image, _image_hash)

            
        
        except Exception as err:
            return (False, err,None)
            
            
            
