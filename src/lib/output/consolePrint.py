import time
import sys
from .ansii_variables import (C_ORANGE, C_BLUE, C_GREEN, C_RESET, C_RED, T_BOLD, T_BOLD_RESET)


def _GetTime():
    """
    herhangi parametre almadan sisteme ait güncel zamanı 
    str: day/mount/year hour:min:sec olarak döndürür

    Returns:
        str: day/mount/year hour:min:sec
    """
    current_time = time.localtime()
    hour = current_time.tm_hour
    minute = current_time.tm_min
    second = current_time.tm_sec
    day_is = current_time.tm_mday
    mount_is = current_time.tm_mon
    year_is = current_time.tm_year
    
    formatted_time = f"{day_is}/{mount_is}/{year_is} {hour:02d}:{minute:02d}:{second:02d}"
    return formatted_time





# BILGILENDIRMELER ICIN 
def p_info(mesages:str, locations:str=None):
    sys.stdout.write(f"{C_GREEN}[{_GetTime()}]{T_BOLD}[INFO]: {T_BOLD_RESET}{mesages}\n")
    sys.stdout.flush()
    
# HATA MESAJLARI ICIN 
def p_error(mesages:str,locations:str=None):
    sys.stderr.write(f"{C_RED}[{_GetTime()}]{T_BOLD}[ERR]: {T_BOLD_RESET}{mesages}\n")
    sys.stdout.flush()
    
# Uyarıları için
def p_warn(mesages:str,locations:str=None):
    print(f"{C_ORANGE}[{_GetTime()}]{T_BOLD}[WARN]: {T_BOLD_RESET}{mesages}")

#Log mesajları için
def p_log(mesages:str,locations:str=None):
    return
    print(f"{C_BLUE}[{_GetTime()}][LOG]:{T_BOLD_RESET} {mesages}")

def p_title(your_title:str,locations:str=None):
    
        print(f"{T_BOLD}{C_BLUE}>> {your_title}{C_RESET}{T_BOLD_RESET}")     