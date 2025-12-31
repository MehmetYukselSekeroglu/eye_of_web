import json

from .env import CONFIG_FILE_PATH as __CONFIG_FILE_PATH__
from .output.consolePrint import (p_info,p_error,p_warn)

__MODULE_LOG_NAME__ ="LOAD_CONFIG"


def load_config_from_file(config_file:str=__CONFIG_FILE_PATH__) -> list[bool,dict]:
    try:
        if config_file != __CONFIG_FILE_PATH__:
            p_warn(f"Loading External Config File: {config_file}",__MODULE_LOG_NAME__)

        with open(config_file, "r") as confFile:
            _loaded_config = json.loads(confFile.read())
        
        p_info(f"Successfuly load config file: {config_file}",__MODULE_LOG_NAME__)    
        return [True, _loaded_config]
    
    
    except Exception as err:
        _err_msg = f"Failed To Load Config File: {config_file}, {err}"
        p_error(_err_msg, __MODULE_LOG_NAME__)
        return [False, _err_msg]




    
    
    
    
    
    
    
    
    
    
    
    
    