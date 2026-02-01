import requests
from bs4 import BeautifulSoup
import re
import random

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
    
    # 1. Cleanup "Du ... au ..."
    # Case insensitive replace
    date_str = re.sub(r'\bDu\b', 'From', date_str, flags=re.IGNORECASE)
    date_str = re.sub(r'\bau\b', 'to', date_str, flags=re.IGNORECASE)
    date_str = date_str.replace("1er", "1st") # User example had 1er

    # 2. Translate months
    for fr, en in months_fr_to_en.items():
        date_str = re.sub(r'\b' + fr + r'\b', en, date_str, flags=re.IGNORECASE)
    
    return date_str.strip()

def inspect_page(url, session):
    print(f"\nProcessing: {url}")
    try:
        resp = session.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 1. Check Language & Look for Switcher
        html_lang = soup.find("html").get("lang", "unknown")
        print(f"  > Original Lang: {html_lang}")
        
        en_link = None
        # User provided snippet suggests: .link-translated-page a
        target_link = soup.select_one(".link-translated-page a")
        if target_link:
             en_link = target_link.get("href")
             if en_link.startswith("/"):
                 en_link = "https://admission.umontreal.ca" + en_link
             print(f"  > Found English Switch Link: {en_link}")
        else:
             print("  > No English Switch Link found (might be already English or missing)")

        # 2. Deadline Extraction
        # Look for "Dates limites" (FR) or "Application deadlines" (EN)
        deadline = "Not Found"
        
        # Test finding strict FR pattern "Du ... au ..."
        full_text = soup.get_text(separator="\n")
        
        # Regex for "Du ... au ..."
        # Du 1er août 2025 au 1er février 2026
        match = re.search(r"(Du\s+\d+.*?\s+au\s+\d+.*?\d{4})", full_text, re.IGNORECASE)
        if match:
            raw_deadline = match.group(1)
            print(f"  > Found Raw Deadline (Regex): {raw_deadline}")
            print(f"  > Translated: {translate_date(raw_deadline)}")
        else:
            print(f"  > No 'Du ... au ...' regex match.")
            # Standard search
            kw = "Dates limites" if "fr" in html_lang else "Application deadlines"
            if kw in full_text:
                 print(f"  > Found keyword '{kw}', parsing nearby text...")
            else:
                 print(f"  > Keyword '{kw}' not found.")

    except Exception as e:
        print(f"  > Error: {e}")

def run_check():
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    # 1. Get List
    print("Fetching Main List to get links...")
    list_url = "https://admission.umontreal.ca/en/programs-of-study/"
    # Note: Requests might not get links if JS rendered, but let's try.
    # If requests fails to get links, I'll use a hardcoded list of known FR urls from logs.
    
    # HARDCODED SAMPLES FROM PREVIOUS LOGS TO ENSURE WE TEST "Du ... au ..."
    # These are real pages found in the logs that were French
    sample_links = [
        "https://admission.umontreal.ca/programmes/maitrise-en-musique/",
        "https://admission.umontreal.ca/programmes/dess-en-education-option-generale/",
        "https://admission.umontreal.ca/programmes/maitrise-en-droit-option-droit-des-affaires-avec-memoire/",
        "https://admission.umontreal.ca/programmes/doctorat-en-neurosciences/",
        "https://admission.umontreal.ca/programmes/maitrise-en-pharmacologie/",
        "https://admission.umontreal.ca/programmes/dess-en-droit-international/",
        "https://admission.umontreal.ca/programmes/maitrise-en-histoire/",
        "https://admission.umontreal.ca/programmes/dess-en-recits-et-medias-autochtones/",
        "https://admission.umontreal.ca/programmes/biophysique-et-physiologie-moleculaire/",
        "https://admission.umontreal.ca/programmes/microprogramme-de-deuxieme-cycle-en-communication-de-la-science/"
    ]
    
    print(f"Checking {len(sample_links)} sample pages...")
    for link in sample_links:
        inspect_page(link, session)

if __name__ == "__main__":
    run_check()
