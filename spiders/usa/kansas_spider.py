# -*- coding: utf-8 -*-
import time
import re
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from spiders.base_spider import BaseSpider
from utils.progress import print_phase_start, print_phase_complete, CrawlerProgress

class KansasSpider(BaseSpider):
    name = 'kansas'
    university = 'University of Kansas'
    school_code = 'US082'
    
    # 允许的域名
    allowed_domains = ['ku.edu']
    start_urls = ['https://gograd.ku.edu/portal/prog_website']

    def __init__(self, headless: bool = True):
        super().__init__(self.name, headless)

    def run(self):
        """
        Execute the scraping task with 2-phase optimization.
        """
        self.driver.get(self.start_urls[0])
        
        # Wait for table to load
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//table//tr[td]"))
            )
        except:
            print("Timeout waiting for program table")
            return self.results

        # Phase 1: Scan the list with Selenium
        rows = self.driver.find_elements(By.XPATH, "//table//tr[td]")
        print_phase_start("Phase 1", "Scanning program list...", total=len(rows))
        
        items_to_process = []
        
        for i, row in enumerate(rows):
            try:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 5:
                    continue
                    
                program_name = cols[0].text.strip()
                degree_type = cols[1].text.strip()
                
                # Skip if header row or combined garbage text
                if program_name == "Program" or "Degree Type" in program_name or len(program_name) > 200:
                    continue
                    
                location = cols[2].text.strip() 
                
                # 'Information' -> 'Learn More' link
                website = ""
                try:
                    learn_more = cols[4].find_element(By.TAG_NAME, "a")
                    website = learn_more.get_attribute("href")
                except:
                    website = self.start_urls[0]

                # Extract UUID for API
                program_uuid = ""
                try:
                    deadline_link = cols[3].find_element(By.PARTIAL_LINK_TEXT, "View Deadlines")
                    data_href = deadline_link.get_attribute("data-href")
                    if data_href and "program=" in data_href:
                        program_uuid = data_href.split("program=")[1]
                except:
                    pass

                item = self.create_result_template(program_name, website)
                item['学院/学习领域'] = location
                item['申请链接'] = "https://gograd.ku.edu/apply/?_gl=1*vxcfti*_gcl_au*MTE2NTY1NDU1OC4xNzY4OTMzNDU2"
                
                # Pass UUID to next phase
                item['_program_uuid'] = program_uuid
                
                items_to_process.append(item)
                
            except Exception:
                # Silent fail for row scan
                pass

        print_phase_complete("Phase 1", len(items_to_process))
        
        # Phase 2: Concurrent Deadline Fetching
        if items_to_process:
            progress = CrawlerProgress(max_workers=24)
            processed_items = progress.run_tasks(
                items=items_to_process,
                task_func=self._fetch_deadline,
                task_name="Fetching Deadlines",
                phase_name="Phase 2"
            )
            self.results = processed_items
        
        return self.results

    def _fetch_deadline(self, item):
        """
        Fetch deadline from API using concurrent requests.
        """
        start_time = time.time()
        
        uuid = item.get('_program_uuid')
        item['项目deadline'] = "" # Default empty
        
        if uuid:
            url = f"https://gograd.ku.edu/portal/prog_website?cmd=program_details&program={uuid}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://gograd.ku.edu/portal/prog_website"
            }
            try:
                # 3 retries
                for attempt in range(3):
                    try:
                        response = requests.get(url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            deadline_text = self._parse_deadlines_from_text(response.text)
                            item['项目deadline'] = deadline_text
                            break
                    except requests.RequestException:
                        if attempt == 2: raise
                        time.sleep(1)
            except Exception:
                pass
        
        # Clean up internal key
        if '_program_uuid' in item:
            del item['_program_uuid']
            
        duration = time.time() - start_time
        return item, duration

    def _extract_dates(self, text):
        """
        Extract dates from text effectively.
        """
        date_pattern = r'\b\d{1,2}/\d{1,2}/\d{4}\b'
        return re.findall(date_pattern, text)

    def _parse_deadlines_from_text(self, text):
        """
        Parse raw text/HTML from API response.
        """
        if "Deadlines" not in text and "Deadline" not in text:
            return ""
            
        soup = BeautifulSoup(text, 'html.parser')
        clean_text = soup.get_text('\n')
        
        lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
        deadlines_list = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            # Match Term (e.g., Spring 2026)
            if re.match(r'^(Fall|Spring|Summer)\s+\d{4}', line):
                term = line
                current_dates = []
                
                # Look ahead for dates in the next few lines
                j = 1
                while i + j < len(lines):
                    next_line = lines[i + j]
                    
                    # Stop if next line is another Term or "Close"
                    if re.match(r'^(Fall|Spring|Summer)\s+\d{4}', next_line) or next_line == "Close":
                        break
                        
                    found_dates = self._extract_dates(next_line)
                    if found_dates:
                        current_dates.extend(found_dates)
                    j += 1
                
                if current_dates:
                    # Deduplicate preserving order
                    unique = list(dict.fromkeys(current_dates))
                    deadlines_list.append(f"{term}: {', '.join(unique)}")
            i += 1
            
        # Deduplicate terms if any
        unique_deadlines = list(dict.fromkeys(deadlines_list))
        return "; ".join(unique_deadlines)
