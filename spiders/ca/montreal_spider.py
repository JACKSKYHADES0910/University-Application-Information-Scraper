from spiders.base_spider import BaseSpider
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
import time
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from deep_translator import GoogleTranslator

class MontrealSpider(BaseSpider):

    def __init__(self, headless=True):
        super().__init__("montreal", headless=headless)
        self.translator = GoogleTranslator(source='fr', target='en')
        self.session = requests.Session()
        self.session.headers.update({
             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.months_fr_to_en = {
            "janvier": "January", "février": "February", "mars": "March",
            "avril": "April", "mai": "May", "juin": "June",
            "juillet": "July", "août": "August", "septembre": "September",
            "octobre": "October", "novembre": "November", "décembre": "December",
            "1er": "1"
        }

    def _translate_to_english(self, text):
        """Translates French text to English using Google Translate."""
        if not text or len(text.strip()) < 2:
            return text
        try:
            # Skip if it looks like a URL or number
            if text.startswith("http") or text.isdigit():
                return text
            return self.translator.translate(text)
        except:
            return text

    def _translate_date(self, date_str):
        """Translates French date string to English (Regex + Keywords)."""
        if not date_str:
            return ""
        
        # Normalize whitespace (handles "1 er" from 1<sup>er</sup>)
        date_str = " ".join(date_str.split())
        
        # Replace keywords
        date_str = re.sub(r'Du\s+', 'From ', date_str, flags=re.IGNORECASE)
        date_str = re.sub(r'\s+au\s+', ' to ', date_str, flags=re.IGNORECASE)
        # Enhanced pattern to catch all variations: "1er", "1 er", "1  er"
        date_str = re.sub(r'1\s*er\b', '1st', date_str, flags=re.IGNORECASE)

        # Translate months
        for fr, en in self.months_fr_to_en.items():
            date_str = re.sub(r'\b' + fr + r'\b', en, date_str, flags=re.IGNORECASE)
        
        return date_str.strip()

    def parse_detail(self, link, list_title):
        """Fetches and parses a detail page."""
        try:
            # 1. Fetch original (could be French)
            resp = self.session.get(link, timeout=15)
            if resp.status_code != 200:
                return None
            
            soup_original = BeautifulSoup(resp.text, 'html.parser')

            # === CRITICAL: Extract deadline from ORIGINAL (French) page FIRST ===
            # Deadline info (.situation-texte) only exists on French pages!
            deadline = ""
            sit_text_elems = soup_original.select(".situation-texte")
            for elem in sit_text_elems:
                txt = elem.get_text(separator=" ", strip=True)
                if "Du" in txt and "au" in txt:
                    deadline = self._translate_date(txt)
                    break
            
            # Fallback regex
            if not deadline:
                page_text = soup_original.get_text(separator="\n", strip=True)
                match = re.search(r"(Du\s+.*?\s+au\s+.*?\d{4})", page_text, re.IGNORECASE)
                if match:
                    deadline = self._translate_date(match.group(1))
            
            if len(deadline) > 100: 
                deadline = deadline[:100]
            if not deadline or len(deadline) < 5: 
                deadline = "See Website"

            # === NOW try to switch to English page (for Faculty extraction) ===
            soup = soup_original  # Start with original
            is_english_page = False
            
            # Check current state
            if "en/" in link or soup.find("html", attrs={"lang": "en"}):
                is_english_page = True
                
            if not is_english_page:
                en_switch = soup.select_one(".link-translated-page a")
                if en_switch:
                    en_href = en_switch.get("href")
                    if en_href:
                        if en_href.startswith("/"):
                            en_href = "https://admission.umontreal.ca" + en_href
                        try:
                            resp_en = self.session.get(en_href, timeout=12)
                            if resp_en.status_code == 200:
                                soup = BeautifulSoup(resp_en.text, 'html.parser')
                                is_english_page = True
                        except:
                            pass

            # -- 3. DETAILS EXTRACTION --
            
            # PROGRAM NAME
            # Authority: List Title (from English interface)
            # Cleanup "(page in French)"
            program_name = list_title.replace("(page in French)", "").strip()
            
            # If list title was somehow empty, fallback to H1 + Translation
            if not program_name:
                h1_elem = soup.select_one("h1.title") or soup.select_one("h1")
                if h1_elem:
                    program_name = h1_elem.get_text(strip=True)
                    if not is_english_page:
                        program_name = self._translate_to_english(program_name)

            # Degree Analysis (Used for appending to name if needed)
            degree_map = {
                "Doctorat": "Doctorate", "PhD": "Doctorate", "Doctorate": "Doctorate",
                "Maîtrise": "Master's Degree", "Master": "Master's Degree", "M.Sc.": "Master's Degree",
                "D.E.S.S.": "Graduate Diploma", "Graduate Diploma": "Graduate Diploma"
            }
            degree = "Master/PhD"
            full_text_lower = soup.get_text().lower()
            for k, v in degree_map.items():
                if k.lower() in full_text_lower:
                    degree = v
                    break
            
            # Append degree if not present in simplified name
            if degree not in program_name and "master" not in program_name.lower() and "doctor" not in program_name.lower():
                 program_name = f"{program_name} - {degree}"

            # FACULTY
            # Must be English.
            faculty = "Université de Montréal"
            if is_english_page:
                fac_elem = soup.find(string=re.compile("Faculty")) or soup.find(string=re.compile("School"))
                if fac_elem: faculty = fac_elem.strip()
            else:
                # French Page -> Extract French Faculty -> Translate
                fac_elem = soup.find(string=re.compile("Faculté")) or soup.find(string=re.compile("École"))
                if fac_elem:
                    faculty = self._translate_to_english(fac_elem.strip())
            
            # DEADLINE was already extracted earlier from original French page

            return {
                "program_name": program_name,
                "faculty": faculty,
                "deadline": deadline,
                "link": link
            }

        except Exception as e:
            return None

    def run(self):
        # 1. Selenium List Loading
        self.driver.get(self.list_url)
        time.sleep(3) 

        while True:
            try:
                view_more_btn = WebDriverWait(self.driver, 5).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "button#btn-charger-plus"))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", view_more_btn)
                time.sleep(1)
                try:
                    view_more_btn.click()
                except ElementClickInterceptedException:
                    self.driver.execute_script("arguments[0].click();", view_more_btn)
                print("Clicked 'View More Results +', waiting...")
                time.sleep(2) 
            except TimeoutException:
                print("Finished loading list.")
                break
            except:
                break

        # 2. Extract Links AND Titles from List
        program_items = [] # List of tuples (link, title)
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR, "a.stretched-link.gtm-titre")
            for el in elements:
                link = el.get_attribute("href")
                title = el.text.strip()
                if link and title:
                    program_items.append((link, title))
            
            # Deduplicate by link
            seen_links = set()
            unique_items = []
            for link, title in program_items:
                if link not in seen_links:
                    seen_links.add(link)
                    unique_items.append((link, title))
            program_items = unique_items
            
            print(f"Found {len(program_items)} programs.")
            
        except Exception as e:
            print(f"Error extracting list: {e}")

        self.close()

        # 3. Concurrent Processing
        print("🚀 Starting threaded extraction (Names from List, Faculties Translated)...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total} | {task.fields[status]}"),
            TimeRemainingColumn(),
        ) as progress:
            
            task = progress.add_task("[cyan]Processing...", total=len(program_items), status="Init")
            
            with ThreadPoolExecutor(max_workers=8) as executor:
                # Pass tuple to parse_detail
                future_to_item = {
                    executor.submit(self.parse_detail, link, title): (link, title) 
                    for link, title in program_items
                }
                
                for future in as_completed(future_to_item):
                    try:
                        data = future.result()
                        if data:
                            item = self.create_result_template(data["program_name"], data["link"])
                            item.update({
                                "学院/学习领域": data["faculty"],
                                "申请链接": "https://admission.umontreal.ca/en/application/",
                                "项目deadline": data["deadline"]
                            })
                            self.results.append(item)
                            progress.update(task, status="OK")
                        else:
                            progress.update(task, status="Fail")
                        
                        progress.advance(task)
                    except:
                        progress.advance(task)
        
        return self.results

if __name__ == "__main__":
    spider = MontrealSpider()
    spider.run()
