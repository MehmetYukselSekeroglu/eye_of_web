import argparse
from duckduckgo_search import DDGS
import time
import duckduckgo_search
import duckduckgo_search.exceptions

parser = argparse.ArgumentParser(description='Dump Twitter usernames from a web page')
parser.add_argument('--namelist', type=str, help='The name list file',required=True)
args = parser.parse_args()

NAME_LIST = set()
WRITE_LIST = set()

with open(args.namelist, 'r') as f:
    for line in f:
        if line.strip() not in NAME_LIST:
            NAME_LIST.add(line.strip())

print(f"Found {len(NAME_LIST)} unique names")




for name in NAME_LIST:
    print(f"Searching for {name}")
    with DDGS() as ddgs:
        try:
            for r in ddgs.text(f"{name} twitter", max_results=400):
                if "x.com" in r['href'].lower() or "twitter.com" in r['href'].lower():
                    if r['href'] not in WRITE_LIST:
                        with open('twitter_usernames.txt', 'a+') as f:
                            f.write(r['href'] + '\n')
                            print(f"Writing {r['href']} to file")
                            WRITE_LIST.add(r['href'])
            time.sleep(120)
        except duckduckgo_search.exceptions.DuckDuckGoSearchException as e:
            print(f"Error searching for {name}: {e}")
            print(f"Sleeping for 120 seconds")
            time.sleep(120)
    time.sleep(1)



