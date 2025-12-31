#! /usr/bin/env python3


from lib.load_config import load_config_from_file
from lib.database_tools import DirectConnectToDatabase, DirectReleaseConnection
import psycopg2.extras
import psycopg2.extensions
import sys

config = load_config_from_file()

if not config[0]:
    sys.exit(1)
    

databaseConfig = config[1]["database_config"]


conn:psycopg2.extensions.connection = DirectConnectToDatabase(dbConfig=databaseConfig)
cursor:psycopg2.extensions.cursor = conn.cursor()


cursor.execute("SELECT \"Domain\" FROM \"BaseDomainID\" WHERE \"Domain\" IS NOT NULL")

while True:
    domain = cursor.fetchone()
    if domain is None:
        break
    
    string_of_url = f"https://{domain[0]}/"
    with open("domain_list.txt", "a+") as f:
        f.write(string_of_url + "\n")
        



