import time
import re
from typing import List, Dict, Set
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from spiders.base_spider import BaseSpider

from selenium.common.exceptions import TimeoutException

class UConnSpider(BaseSpider):
    name = 'uconn'

    def __init__(self, headless: bool = True):
        super().__init__(self.name, headless)
        self.program_categories: Dict[str, Set[str]] = {}

    def _get_program_categories(self):
        """
        Iterate through 'Areas of Interest' checkboxes to map programs to their categories.
        """
        print("Mapping program categories...", flush=True)
        try:
            # Get all Area of Interest checkboxes
            checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input.aoi-filter")
            
            for checkbox in checkboxes:
                category_name = checkbox.get_attribute("id") # e.g., 'business', 'fine-arts'
                # Find the label text for better naming if possible
                label = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{category_name}']").text
                
                # print(f"Checking category: {label}", flush=True) 
                
                # Click to filter
                self.driver.execute_script("arguments[0].click();", checkbox)
                time.sleep(1.5) # Wait for DOM update
                
                # Get visible programs
                visible_programs = self.driver.find_elements(By.CSS_SELECTOR, "li.program-box:not([style*='display: none'])")
                
                for prog in visible_programs:
                    try:
                        name_el = prog.find_element(By.CSS_SELECTOR, ".program-name")
                        name = name_el.text.strip()
                        if name not in self.program_categories:
                            self.program_categories[name] = set()
                        self.program_categories[name].add(label)
                    except Exception:
                        continue
                
                # Uncheck to reset
                self.driver.execute_script("arguments[0].click();", checkbox)
                time.sleep(0.5)
                
        except Exception as e:
            print(f"Error mapping categories: {e}", flush=True)

    def _parse_deadline(self, url: str) -> str:
        """
        Fetch the detail page and extract deadline information.
        Expected format: "Month DD" or "Term: Month DD" (brief 2-5 words description).
        """
        if not url:
            return ""
            
        import requests
        from requests.packages.urllib3.exceptions import InsecureRequestWarning
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        
        from config import HEADERS, TIMEOUT
        
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
            if resp.status_code != 200:
                # Silently fail or simple message
                return "See Website"
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text(" ", strip=True)
            
            # Normalize spaces
            text = re.sub(r'\s+', ' ', text)
            
            # Regex for Deadlines
            # 1. Capture "Fall: Month DD" or "Summer: Month DD" 
            # 2. Capture just dates like "January 15", "Dec. 1", "March 1st"
            
            # Month names regex
            months = r"(?:Jan(?:uary|\.)?|Feb(?:ruary|\.)?|Mar(?:ch|\.)?|Apr(?:il|\.)?|May|Jun(?:e|\.)?|Jul(?:y|\.)?|Aug(?:ust|\.)?|Sep(?:t|tember|\.)?|Oct(?:ober|\.)?|Nov(?:ember|\.)?|Dec(?:ember|\.)?)"
            
            # Date Pattern: Month DD, YYYY? or DD Month YYYY?
            date_pattern = f"(?:{months}\\s+\\d{{1,2}}(?:,?\\s+\\d{{4}})?)"
            
            # Context Pattern: (Fall|Spring|Summer|Admission|Deadline|Apply by)[:\s]+[Date]
            context_pattern = r"(?:Fall|Spring|Summer|Winter|Admission|Deadline|Apply by)[:\s]+" + date_pattern
            
            # Search for context + date first (more specific)
            matches = re.findall(context_pattern, text, re.IGNORECASE)
            
            deadlines = []
            if matches:
                 # Take up to 2 unique patterns found
                for m in matches[:2]:
                    # Clean the match: remove extra colons/spaces
                    clean_m = re.sub(r'[:\s]+', ' ', m).strip()
                    if clean_m not in deadlines:
                        deadlines.append(clean_m)
            
            if not deadlines:
                # Search for isolated dates near "deadline" keyword
                deadline_idx = [m.start() for m in re.finditer(r'deadline', text, re.IGNORECASE)]
                for idx in deadline_idx:
                    # Look in a window after the keyword
                    window = text[idx:idx+100]
                    date_match = re.search(date_pattern, window, re.IGNORECASE)
                    if date_match:
                         # Try to find a term prefix in that window too
                         term_match = re.search(r"(Fall|Spring|Summer|Winter)", window, re.IGNORECASE)
                         d_str = date_match.group(0)
                         if term_match:
                             term = term_match.group(1)
                             final_str = f"{term}: {d_str}"
                         else:
                             final_str = d_str
                         
                         if final_str not in deadlines:
                             deadlines.append(final_str)
                             
                    if len(deadlines) >= 2: break
            
            if deadlines:
                # Join unique deadlines, max 2
                return " | ".join(deadlines[:2])
                
            return "See Website"
            
        except Exception:
            # On any error (connection, SSL, parsing), default to simple text
            return "See Website"

    def run(self) -> List[Dict]:
        print("Starting UConn Spider...", flush=True)
        # print(f"Navigating to {self.list_url}...", flush=True)
        try:
            self.driver.get(self.list_url)
        except TimeoutException:
            print("Page load timeout. Stopping loading and checking DOM...", flush=True)
            self.driver.execute_script("window.stop();")
            
        # print("Page loaded (or stopped). Waiting 5s...", flush=True)
        time.sleep(5) # Wait for full load/scripts
        
        # 1. Map Categories
        self._get_program_categories()
        
        # 2. Scrape All Programs
        print("Scraping all programs...", flush=True)
        # Ensure all filters are off/Reset -> Just reload to be safe
        self.driver.refresh()
        time.sleep(3)
        
        all_program_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.program-box")
        print(f"Found {len(all_program_elements)} total program cards.", flush=True)
        
        items_to_process = []
        
        for el in all_program_elements:
            try:
                name_el = el.find_element(By.CSS_SELECTOR, ".program-name")
                name = name_el.text.strip()
                link = name_el.get_attribute("href")
                
                degree_el = el.find_element(By.CSS_SELECTOR, ".degrees")
                degree_text = degree_el.text.strip() # e.g. "M.S., Ph.D."
                
                # Check for "Not Accepting" text
                details_text = el.text
                status_note = ""
                if "not accepting applications" in details_text.lower():
                    status_note = " (Not Accepting Applications)"
                
                # Split degrees
                # User example: "Certificate, M.F.A." -> Split
                raw_degrees = [d.strip() for d in degree_text.split(',')]
                
                categories = ", ".join(self.program_categories.get(name, ["Uncategorized"]))
                
                for deg in raw_degrees:
                    full_name = f"{name} - {deg}{status_note}"
                    
                    items_to_process.append({
                        "name": full_name,
                        "degree": deg,
                        "category": categories,
                        "link": link,
                        "orig_name": name
                    })
                    
            except Exception as e:
                print(f"Error parsing card: {e}", flush=True)
        
        self.driver.quit()
        
        # 3. Fetch Deadlines (Concurrent)
        print(f"Fetching deadlines for {len(items_to_process)} items...")
        final_results = []
        
        # Use a mapping to avoid fetching same URL multiple times
        url_deadline_map = {}
        unique_urls = set(item['link'] for item in items_to_process)
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(self._parse_deadline, url): url for url in unique_urls}
            
            count = 0
            total = len(unique_urls)
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    deadline = future.result()
                    url_deadline_map[url] = deadline
                except Exception as e:
                    url_deadline_map[url] = "Error"
                
                count += 1
                if count % 10 == 0:
                    print(f"Progress: {count}/{total}")
                    
        # 4. Build Final Results
        for item in items_to_process:
            deadline = url_deadline_map.get(item['link'], "")
            
            result = self.create_result_template(
                program_name=item['name'],
                program_link=item['link']
            )
            
            result['学院/学习领域'] = item['category']
            result['项目deadline'] = deadline
            result['项目opendate'] = "" # Not easily available
            result['申请链接'] = "https://connect.grad.uconn.edu/apply/"
            
            self.results.append(result)
            final_results.append(result)
            
        self.print_summary()
        return final_results
