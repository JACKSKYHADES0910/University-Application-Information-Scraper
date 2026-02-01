from bs4 import BeautifulSoup
import re

html_content = """
<section class="programme-infos-par-trimestre" id="dates-limites">
    <div aria-labelledby="trimestre-4-2026-onglet" tabindex="0" role="tabpanel" class="row g-0">
        <div class="col-12">
            <section class="programme-date-limite">
                <section class="situation-titres">
                    <div>
                        <p class="h5 my-0">Dates limites</p>
                    </div>
                </section>

                <div class="mt-3">
                    <div>
                        <div class="icon-container">
                            <i class="udem-icon-depot-bleu" aria-hidden="true"></i>
                        </div>
                        <div>
                            <div class="mb-1">
                                Déposer la demande d'admission
                            </div>
                            <div class="situation-container">
                                <div class="situation-etudiant-container">
                                    <span class="situation-texte preference uppercase-first-letter " style="white-space: nowrap;">Du <span style="white-space: nowrap;">1<sup>er</sup> août 2025</span> au <span style="white-space: nowrap;">1<sup>er</sup> février 2026</span></span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    </div>
</section>
"""

months_fr_to_en = {
    "janvier": "January", "février": "February", "mars": "March",
    "avril": "April", "mai": "May", "juin": "June",
    "juillet": "July", "août": "August", "septembre": "September",
    "octobre": "October", "novembre": "November", "décembre": "December",
    "1er": "1"
}

def translate_date(date_str):
    if not date_str:
        return ""
    
    # 1. First cleanup "Du ... au ..." specifically
    date_str = re.sub(r'Du\s+', 'From ', date_str, flags=re.IGNORECASE)
    date_str = re.sub(r'\s+au\s+', ' to ', date_str, flags=re.IGNORECASE)
    
    # 1er -> 1st
    date_str = date_str.replace("1er", "1st") 

    # 2. Translate months
    for fr, en in months_fr_to_en.items():
        date_str = re.sub(r'\b' + fr + r'\b', en, date_str, flags=re.IGNORECASE)
    
    # Clean up any extra whitespace
    date_str = " ".join(date_str.split())
    return date_str.strip()

def test_extraction():
    soup = BeautifulSoup(html_content, 'html.parser')
    
    deadline = ""
    
    # Strategy 1: Targeted Selector
    situation_text = soup.select_one(".situation-texte")
    if situation_text:
        text = situation_text.get_text(separator=" ", strip=True)
        print(f"Selector Text: '{text}'")
        
        # Regex check
        if "Du" in text and "au" in text:
            deadline = text
            
    # Strategy 2: User's Text Layout (Du ... au ...)
    if not deadline:
        full_text = soup.get_text(separator="\n")
        match = re.search(r"(Du\s+.*?\s+au\s+.*?\d{4})", full_text, re.IGNORECASE) # removed \d check on start
        if match:
             deadline = match.group(1)
             print(f"Regex Match: '{deadline}'")

    print(f"Final Extracted: {deadline}")
    print(f"Translated: {translate_date(deadline)}")

if __name__ == "__main__":
    test_extraction()
