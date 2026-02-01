import time
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from spiders.base_spider import BaseSpider
import re

import logging

class VanderbiltSpider(BaseSpider):
    def __init__(self, headless: bool = True):
        super().__init__("vanderbilt", headless)
        self.program_school_map = {}
        self.logger = logging.getLogger("vanderbilt_spider")
        logging.basicConfig(level=logging.INFO)

    def _get_school_map(self):
        """
        Iterate through the school filter to map programs to schools.
        """
        self.logger.info("Building Program -> School mapping...")
        try:
            select_element = self.driver.find_element(By.ID, "school-select")
            select = Select(select_element)
            options = [opt for opt in select.options if opt.get_attribute("value") not in ["", "*"]]

            for option in options:
                school_name = option.text.strip()
                school_value = option.get_attribute("value")
                self.logger.info(f"Mapping school: {school_name}")

                # Select the school
                select.select_by_value(school_value)
                
                # Wait for filter to apply (give it a moment for animation/DOM update)
                time.sleep(1.5) 

                # Find all visible programs
                # The filter usually hides items by setting display: none
                visible_programs = self.driver.find_elements(By.CSS_SELECTOR, "details.program-finder__expandable")
                
                count = 0
                for prog in visible_programs:
                    if prog.is_displayed():
                        # Extract program name
                        try:
                            # The name is inside the summary -> div.program-finder__program-name
                            name_el = prog.find_element(By.CSS_SELECTOR, ".program-finder__program-name")
                            program_name = name_el.text.strip()
                            
                            # Store in map. If already exists, we keep the first one or overwrite.
                            # Usually a program belongs to one primary school in this context.
                            if program_name:
                                self.program_school_map[program_name] = school_name
                                count += 1
                        except Exception as ignored:
                            continue
                self.logger.info(f" -> Found {count} programs for {school_name}")

            # Reset filter to show all (usually the first option)
            try:
                select.select_by_index(0)
            except:
                pass
            time.sleep(2)
            
        except Exception as e:
            self.logger.error(f"Error building school map: {e}")

    def run(self):
        """
        Main scraper function
        """
        self.logger.info(f"Starting scraping for {self.school_name}")
        # Driver is lazy loaded
        self.driver.get(self.list_url)
        
        # 1. Build School Map
        self._get_school_map()

        programs = []
        # 2. Scrape Programs
        try:
            # Re-fetch the list elements after reset
            program_elements = self.driver.find_elements(By.CSS_SELECTOR, "details.program-finder__expandable")
            self.logger.info(f"Found {len(program_elements)} total program items.")

            for prog_el in program_elements:
                try:
                    if not prog_el.is_displayed():
                        continue
                        
                    # Scroll into view if needed
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", prog_el)
                    
                    # Extract Main Category Name
                    name_el = prog_el.find_element(By.CSS_SELECTOR, ".program-finder__program-name")
                    category_name = name_el.text.strip()
                    
                    # Get School from map
                    school = self.program_school_map.get(category_name, "Vanderbilt University")

                    # Open the details to see sub-programs
                    summary_el = prog_el.find_element(By.TAG_NAME, "summary")
                    # Check if already open (attribute 'open')
                    if not prog_el.get_attribute("open"):
                        self.driver.execute_script("arguments[0].click();", summary_el)
                        time.sleep(0.2)

                    # Look for sub-program links
                    detail_container = prog_el.find_element(By.CSS_SELECTOR, ".program-finder__program-details")
                    sub_links = detail_container.find_elements(By.TAG_NAME, "a")
                    
                    processed_subs = set()

                    for link in sub_links:
                        link_text = link.text.strip()
                        link_href = link.get_attribute("href")
                        
                        # Filter criteria
                        if "Bachelor" in link_text:
                            continue
                        
                        # Identify degree type
                        degree_type = ""
                        if "Master" in link_text:
                            degree_type = "Master's"
                        elif "Doctor" in link_text or "PhD" in link_text:
                            degree_type = "Doctoral"
                        
                        # Construct Sub-name
                        sub_name = link_text.replace("Learn more about", "").strip()
                        if not sub_name:
                            sub_name = degree_type if degree_type else "Graduate Program"

                        full_program_name = f"{category_name} - {sub_name}"
                        
                        if full_program_name in processed_subs:
                            continue
                        processed_subs.add(full_program_name)

                        program_item = {
                            "学校代码": self.school_code,
                            "学校名称": self.school_name,
                            "项目名称": full_program_name,
                            "学院/学习领域": school,
                            "项目官网链接": link_href,
                            "申请链接": "https://apply.vanderbilt.edu/apply/",
                            "项目opendate": "",
                            "项目deadline": "",
                            "学生案例": "",
                            "面试问题": ""
                        }
                        programs.append(program_item)

                except Exception as e:
                    self.logger.error(f"Error processing program category: {e}")
                    continue
            
            self.logger.info(f"Collected {len(programs)} programs. Starting concurrent deep scraping...")
            
            # 3. Concurrent Deep Scraping
            from concurrent.futures import ThreadPoolExecutor, as_completed
            MAX_WORKERS = 24  # Or import from config
            
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_item = {executor.submit(self._get_program_details, item): item for item in programs}
                for future in as_completed(future_to_item):
                    try:
                        result = future.result()
                        # BaseSpider usually stores results in self.results
                        self.results.append(result)
                    except Exception as e:
                        self.logger.error(f"Error in deep scraping: {e}")
            
            return self.results

        except Exception as e:
            self.logger.error(f"Critical error in run: {e}")
            return []
        finally:
            # We don't close here because BaseSpider logic might handle it or the caller does?
            # BaseSpider.run() doc says "Should implement", doesn't say "Should close".
            # But the 'main.py' likely handles spider lifecycle. 
            # I will ensure self.close() is called if this is the entry point, BUT usually runner calls close.
            # I'll leave close() to the caller or finally block if I owned the loop.
            # I'll manually call close() if exception, but generally leave it open?
            # Actually BaseSpider doc example: `spider.close()` called by user.
            pass

    def _get_program_details(self, program_item):
        """
        Deep scrape for deadline
        """
        url = program_item.get("项目官网链接")
        if not url:
            return program_item

        try:
            self.random_sleep(1, 2)
            # Use requests or a fresh driver? BaseSpider usually allows requests if simple, 
            # but configured with Selenium executor often. 
            # Let's try requests first for speed, fallback to selenium if needed?
            # BaseSpider structure suggests we might be inside a thread.
            # We'll use requests + BS4 for efficiency as implemented in other spiders.
            
            import requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                html = response.text
                soup = BeautifulSoup(html, 'html.parser')
                text_content = soup.get_text(separator=' ', strip=True)
            except:
                # Fallback to pure regex on whatever we got or skip
                return program_item

            # Extract raw text
            deadline_text = self._clean_deadline_text(text_content)
            program_item["项目deadline"] = deadline_text

        except Exception as e:
            self.logger.error(f"Error scraping details for {program_item['项目名称']}: {e}")

        return program_item

    def _clean_deadline_text(self, raw_text):
        """
        Cleans and extracts specific deadline information using Trigger-Centric Logic.
        """
        if not raw_text:
            return ""
        
        # 1. Normalize spaces
        # Replace punctuation that acts as separators with spaces/safe chars
        text = re.sub(r'[\r\n\t]+', ' ', raw_text)
        
        # 2. Define Date Regex
        date_pattern = r'\b(?:Jan(?:\.|uary)?|Feb(?:\.|ruary)?|Mar(?:\.|ch)?|Apr(?:\.|il)?|May|Jun(?:\.|e)?|Jul(?:\.|y)?|Aug(?:\.|ust)?|Sep(?:\.|t\.|tember)?|Oct(?:\.|ober)?|Nov(?:\.|ember)?|Dec(?:\.|ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?'
        
        # Keywords that anchor a semantic deadline
        strong_keywords = ["deadline", "decision", "round", "application", "admission", "priority", "rolling", "early", "regular", "spring", "fall", "summer", "winter", "term", "year"]
        
        found_entries = []
        seen_entries = set()
        
        matches = list(re.finditer(date_pattern, text, re.IGNORECASE))
        
        last_end = 0
        
        for match in matches:
            date_str = match.group()
            start_idx = match.start()
            
            # Region of interest: 
            # Look back up to ~80 chars, but stop at previous match end
            region_start = max(last_end, start_idx - 80)
            context_region = text[region_start:start_idx].strip()
            
            # Clean trailing separators from context
            context_region = re.sub(r'[:\-]+$', '', context_region).strip()
            
            label = "Deadline" # Default
            
            if context_region:
                tokens = context_region.split()
                
                # Find the right-most trigger word
                # Iterate backwards through tokens
                trigger_idx = -1
                for i in range(len(tokens)-1, -1, -1):
                    clean_t = tokens[i].lower().strip(".:;,")
                    if clean_t in strong_keywords:
                        trigger_idx = i
                        break
                
                if trigger_idx != -1:
                    # We found a semantic anchor!
                    # 1. Capture Prefix: 1-3 words before the trigger
                    #    But stop if we hit punctuation or very common noise
                    prefix_tokens = []
                    p_start = max(0, trigger_idx - 3)
                    for k in range(trigger_idx - 1, p_start - 1, -1):
                        t = tokens[k]
                        # Stop if it ends with sentence punctuation
                        if re.search(r'[.?!]$', t): 
                            break
                        prefix_tokens.insert(0, t)
                    
                    # 2. Capture Suffix: words between trigger and date
                    #    "Deadline for domestic students" -> Suffix "for domestic students"
                    #    Limit suffix length (e.g. 4 words) to avoid capturing previous sentence garbage
                    suffix_tokens = tokens[trigger_idx+1:]
                    
                    # Clean prefix/suffix
                    # Remove "is", "are" from end of suffix
                    while suffix_tokens and suffix_tokens[-1].lower() in ["is", "are", "on", ":", "-"]:
                        suffix_tokens.pop()
                        
                    # Assemble
                    label_parts = prefix_tokens + [tokens[trigger_idx]] + suffix_tokens
                    label = " ".join(label_parts)
                
                else:
                    # No trigger word found.
                    # Fallback: Check if capitalizing sequence at end
                    # e.g. "PhD Physics: Jan 15"
                    rev_buffer = []
                    for i in range(len(tokens)-1, -1, -1):
                        t = tokens[i]
                        if t[0].isupper() or t.lower() in ["for", "of"]:
                             rev_buffer.insert(0, t)
                        else:
                            break
                    
                    if len(rev_buffer) > 0:
                        label = " ".join(rev_buffer)

            # Cleanup
            label = re.sub(r'[,.;:]', '', label).strip()
            # Clean start: remove noise words and symbols
            label = re.sub(r'^[\W_]+', '', label) # Remove leading symbols like *
            label = re.sub(r'^(the|for|see|and|or|in)\s+', '', label, flags=re.IGNORECASE)
            
            if len(label) < 2: label = "Deadline"

            full_entry = f"{label}: {date_str}"
            
            if full_entry not in seen_entries:
                found_entries.append(full_entry)
                seen_entries.add(full_entry)
                
            last_end = match.end()

        if found_entries:
            return "; ".join(found_entries)
        
        return ""
