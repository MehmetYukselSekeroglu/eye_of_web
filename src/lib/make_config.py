import json
import sys
import os

import onnxruntime


from .env import CONFIG_FILE_PATH as __CONFIG_FILE_PATH__

from .output.consolePrint import (p_info, p_error)


__MODULE_LOG_NAME__ = "MAKE_CONFIG_SCHEMA"
__BASE_DIR__ = os.getcwd() + os.path.sep
__TEMP_DIR__ = __BASE_DIR__ + "tmp" + os.path.sep
__DATA_DIR__ = __BASE_DIR__ + "data" + os.path.sep
__SQL_SCHMEA_PATH__ = __BASE_DIR__ + "sql" + os.path.sep + "postgresql_schema.sql"


__CONFIG_FILE_DATA__ = {
    
    "vendor":"WeKnow Developer Team",
    "name":"EyeOfWeb",
    "version":"0.0.0+1",
    "base_dir":__BASE_DIR__,
    "temp_dir":__TEMP_DIR__,
    "data_dir":__DATA_DIR__,
    "database_schema":__SQL_SCHMEA_PATH__,
    "remote_api_url":"",
    "telegram_channeld_id":"",
    
    "service":{
        "thread":4,
        "save_images":False  
    },
    
    "web_requests":{
      "timeout":10,
      "random_user_agent":True,
      "ssl_verification":True,  
    },
    "database_config":{
            "database":"WebEye",
            "user":"postgres",
            "password":"your_secret_password",
            "host":"127.0.0.1",
            "port":"5432",
    },
    "insightface":{
        "prepare":{
        "ctx_id":-1,
        "det_thresh":0.5,
        "det_size":(640,640),
        },
        "main":{
            "providers":onnxruntime.get_available_providers(),
            "name":"buffalo_l"
        }
    },
        
    
    "insightface_min_verification_sim":0.40,
    "similarity_calculator":"consine_sim",
    
    "api_config":{
        "port":"8080",
        "localhost_only":False
    },
    "initial_admin_user": {
        "username": "admin",
        "password": "your_secret_password"
    },
    "milvus": {
        "host": "localhost",
        "port": "19530",
        "user": "root",
        "password": "your_secret_password"
    }
}



if __name__ == "__main__":

    os.makedirs(f"{__BASE_DIR__+'config'}",exist_ok=True)
    try:
        with open(__CONFIG_FILE_PATH__,"w+") as conf_file:
            json.dump(__CONFIG_FILE_DATA__,conf_file,indent=4)
        
    except Exception as err:
        p_error(f"Failed to crate {__CONFIG_FILE_PATH__}, {err}",__MODULE_LOG_NAME__)
        sys.exit(-1)        

    p_info(f"{__CONFIG_FILE_PATH__} successfuly generated.",__MODULE_LOG_NAME__)
    sys.exit(0)














