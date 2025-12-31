import duckduckgo_search
import argparse

def main():
    parser = argparse.ArgumentParser(description='Extract domain from Google search results')
    parser.add_argument('keyword', type=str, help='The keyword to search for')
    args = parser.parse_args()

    unique_domains = set()
    # Search for the domain
    search_results = duckduckgo_search.DDGS().text(args.keyword,max_results=400)
    with open('search_results.txt', 'w') as f:
        for result in search_results:
            if result['href'] not in unique_domains:
                f.write(result['href'] + '\n')
                unique_domains.add(result['href'])
                print(f"Writing {result['href']} to file")


if __name__ == "__main__":
    main()