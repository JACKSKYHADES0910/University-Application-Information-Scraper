import requests
from bs4 import BeautifulSoup
import re

def translate_date(date_str):
    months_fr_to_en = {
        "janvier": "January", "février": "February", "mars": "March",
        "avril": "April", "mai": "May", "juin": "June",
        "juillet": "July", "août": "August", "septembre": "September",
        "octobre": "October", "novembre": "November", "décembre": "December",
        "1er": "1"
    }
    if not date_str:
        return ""
    for fr, en in months_fr_to_en.items():
        date_str = re.sub(r'\b' + fr + r'\b', en, date_str, flags=re.IGNORECASE)
    
    date_str = date_str.replace("Du", "From").replace("au", "to")
    return date_str.strip()

def check_list_language():
    url = "https://admission.umontreal.ca/en/programs-of-study/"
    print(f"Fetching List: {url}")
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = soup.select("a.stretched-link.gtm-titre")
        print(f"Found {len(links)} links. First 5:")
        for l in links[:5]:
            print(f" - {l.get('href')}")
    except Exception as e:
        print(f"Error: {e}")

def check_detail_and_deadline(url):
    print(f"\nFetching Detail: {url}")
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 1. Title
        h1 = soup.select_one("h1.title")
        title = h1.get_text(strip=True) if h1 else "N/A"
        print(f"Title: {title}")
        
        # 2. Deadline
        deadline = "Not Found"
        # Logic from spider
        deadline_header = soup.find(string=re.compile("Dates limites"))
        if deadline_header:
            print(f"Found 'Dates limites' text node.")
            parent = deadline_header.parent.parent
            if parent:
                full_text = parent.get_text(separator="\n")
                print(f"Context Text Preview: {full_text[:100]}...")
                if "Dates limites" in full_text:
                    deadline_part = full_text.split("Dates limites")[-1].strip()
                    lines = [line.strip() for line in deadline_part.split('\n') if line.strip()]
                    print(f"Lines after split: {lines}")
                    if lines:
                        # Improved logic: Search for "Du ... au ..." line specifically
                        for line in lines:
                             if "Du" in line and "au" in line:
                                 deadline = line
                                 break
                        if deadline == "Not Found" and lines:
                             deadline = lines[0] # Fallback
        
        print(f"Raw Deadline: {deadline}")
        print(f"Translated: {translate_date(deadline)}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_list_language()
    # Test with a likely French Link to see parsing
    # And check if we can guess the English one
    check_detail_and_deadline("https://admission.umontreal.ca/programmes/maitrise-en-mathematiques/") 
