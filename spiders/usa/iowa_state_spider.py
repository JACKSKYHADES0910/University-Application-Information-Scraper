# -*- coding: utf-8 -*-
"""
Iowa State University Spider
Scrapes graduate programs from https://www.grad-college.iastate.edu/programs
Features: Interest Area categorization, degree splitting, deadline extraction
"""

import time
import re
import random
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple, Set

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from spiders.base_spider import BaseSpider
from utils.progress import CrawlerProgress, print_phase_complete


class IowaStateSpider(BaseSpider):
    """
    Iowa State University graduate programs spider.
    Extracts program names with degree types and Interest Area categories.
    """
    
    name = "iowa_state"
    
    # Interest Area ID to category name mapping
    INTEREST_AREAS = {
        "1": "Animal Sciences",
        "2": "Art and Design",
        "3": "Biological Sciences",
        "4": "Business and Management",
        "5": "Computational",
        "6": "Educational",
        "7": "Engineering",
        "8": "Human Biological Sciences",
        "9": "Humanities",
        "10": "Mathematical Sciences",
        "11": "Physical Sciences",
        "12": "Plant Agriculture",
        "13": "Social Sciences"
    }
    
    def __init__(self, headless: bool = False):
        super().__init__(self.name, headless=False)
        self.apply_url = self.university_info.get('apply_url', 'https://apps.admissions.iastate.edu/apply/online/')
        self.program_categories: Dict[str, Set[str]] = {}  # program_url -> set of categories
    
    def run(self) -> List[Dict]:
        """
        Main execution:
        Phase 1: Extract all program links via Selenium
        Phase 2: Map Interest Areas to programs
        Phase 3: Fetch degrees and deadlines via concurrent requests
        """
        self.start_time = time.time()
        
        try:
            # Phase 1: Get all programs
            print("\n📋 Phase 1: Extracting program list...")
            self.driver.get(self.list_url)
            time.sleep(3)
            
            # Accept cookies if present
            try:
                cookie_btn = self.driver.find_element(By.CSS_SELECTOR, "button.privacy-consent__accept")
                cookie_btn.click()
                time.sleep(1)
            except:
                pass
            
            # Extract all program links
            programs = self._extract_all_programs()
            print_phase_complete("Phase 1", len(programs))
            
            if not programs:
                print("⚠️ No programs found!")
                return []
            
            # Phase 2: Map Interest Areas
            print("\n🏷️ Phase 2: Mapping Interest Area categories...")
            self._map_interest_areas()
            print_phase_complete("Phase 2", len(self.program_categories))
            
            # Phase 3: Fetch details with concurrency
            print("\n🔍 Phase 3: Fetching program details...")
            progress = CrawlerProgress(max_workers=24)
            processed_items = progress.run_tasks(
                items=programs,
                task_func=self._parse_program_details,
                task_name="Scraping Program Details",
                phase_name="Phase 3"
            )
            
            # Flatten results
            for sublist in processed_items:
                if sublist:
                    self.results.extend(sublist)
            
            return self.results
            
        finally:
            self.close()
    
    def _extract_all_programs(self) -> List[Dict]:
        """Extract all program names and URLs from the listing page."""
        programs_data = self.driver.execute_script("""
            const links = Array.from(document.querySelectorAll('a[href^="/programs/"]'))
                .filter(a => !a.href.includes('/programs?'))
                .filter(a => a.textContent.trim().length > 0);
            
            const seen = new Set();
            const result = [];
            
            for (const a of links) {
                const href = a.getAttribute('href');
                if (!seen.has(href) && href !== '/programs' && href !== '/programs/') {
                    seen.add(href);
                    result.push({
                        name: a.textContent.trim(),
                        url: a.href
                    });
                }
            }
            return result;
        """)
        
        print(f"   Found {len(programs_data)} unique programs")
        return programs_data
    
    def _map_interest_areas(self) -> None:
        """Map Interest Areas to programs by filtering through each category."""
        try:
            # First get all option values
            dropdown = Select(self.driver.find_element(By.ID, "edit-field-program-interest-area-target-id"))
            option_values = []
            for option in dropdown.options:
                value = option.get_attribute("value")
                text = option.text.strip()
                if value != "All" and text and text != "- Any -":
                    option_values.append((value, text))
            
            # Now iterate through each value
            for value, text in option_values:
                try:
                    # Re-fetch dropdown to avoid stale element
                    dropdown = Select(self.driver.find_element(By.ID, "edit-field-program-interest-area-target-id"))
                    dropdown.select_by_value(value)
                    
                    # Click Filter button
                    filter_btn = self.driver.find_element(By.ID, "edit-submit-programs")
                    filter_btn.click()
                    time.sleep(2)
                    
                    # Get programs under this category
                    links = self.driver.execute_script("""
                        return Array.from(document.querySelectorAll('a[href^="/programs/"]'))
                            .filter(a => !a.href.includes('/programs?'))
                            .map(a => a.href);
                    """)
                    
                    # Map each program to this category
                    for url in links:
                        if url not in self.program_categories:
                            self.program_categories[url] = set()
                        self.program_categories[url].add(text)
                    
                    print(f"   • {text}: {len(links)} programs")
                    
                except Exception as e:
                    print(f"   ⚠️ Error with {text}: {e}")
                    continue
            
            # Reset to All
            try:
                dropdown = Select(self.driver.find_element(By.ID, "edit-field-program-interest-area-target-id"))
                dropdown.select_by_value("All")
                filter_btn = self.driver.find_element(By.ID, "edit-submit-programs")
                filter_btn.click()
                time.sleep(1)
            except:
                pass
                
        except Exception as e:
            print(f"   ⚠️ Error mapping Interest Areas: {e}")
    
    def _parse_program_details(self, item: Dict) -> Tuple[List[Dict], float]:
        """
        Fetch program detail page and extract degrees and deadlines.
        Returns list of result dicts (one per degree type).
        """
        start_time = time.time()
        
        url = item['url']
        raw_name = item['name']
        
        # Get categories for this program
        categories = self.program_categories.get(url, set())
        category_str = "; ".join(sorted(categories)) if categories else "Graduate Programs"
        
        results_list = []
        
        try:
            time.sleep(random.uniform(0.2, 0.5))
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                raise Exception(f"Status {resp.status_code}")
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Extract degrees
            degrees = self._extract_degrees(soup)
            
            # Extract deadline
            deadline = self._extract_deadline(soup)
            
            # Create result entries for each degree
            if degrees:
                for degree in degrees:
                    final_name = f"{raw_name} - {degree}"
                    results_list.append(self._create_entry(final_name, url, deadline, category_str))
            else:
                # No degrees found, use raw name
                results_list.append(self._create_entry(raw_name, url, deadline, category_str))
            
        except Exception as e:
            results_list.append(self._create_entry(raw_name, url, "See Website", category_str))
        
        duration = time.time() - start_time
        return results_list, duration
    
    def _extract_degrees(self, soup: BeautifulSoup) -> List[str]:
        """Extract degree types from the detail page."""
        degrees = []
        
        # Known degree patterns to validate
        valid_degree_keywords = [
            'Ph.D.', 'PhD', 'M.S.', 'MS', 'M.A.', 'MA', 'Doctor', 'Master', 
            'M.B.A.', 'MBA', 'M.F.A.', 'MFA', 'M.Ed.', 'MEd', 'M.Eng', 
            'D.V.M.', 'DVM', 'D.M.A.', 'DMA', 'M.P.A.', 'MPA', 'M.L.A.', 
            'M.Arch', 'M.C.R.P.', 'Certificate'
        ]
        
        # Method 1: Find 'Degrees Offered:' heading and get adjacent UL
        for element in soup.find_all(['p', 'strong']):
            element_text = element.get_text().strip()
            if element_text == 'Degrees Offered:':
                # Get the parent and find the next sibling UL
                parent = element.parent if element.name == 'strong' else element
                next_sibling = parent.find_next_sibling()
                
                if next_sibling and next_sibling.name == 'ul':
                    for li in next_sibling.find_all('li', recursive=False):
                        degree_text = li.get_text().strip()
                        # Validate that this looks like a degree
                        if any(kw.lower() in degree_text.lower() for kw in valid_degree_keywords):
                            if degree_text not in degrees:
                                degrees.append(degree_text)
                    
                    if degrees:
                        return degrees
        
        # Method 2: Search in text near 'Degrees Offered'
        page_text = soup.get_text()
        if 'Degrees Offered' in page_text:
            # Extract section after 'Degrees Offered'
            match = re.search(r'Degrees Offered[:\s]*([\s\S]{0,500}?)(?:How long|Application|Admission|Learning)', page_text)
            if match:
                section = match.group(1)
                # Look for degree patterns
                degree_patterns = [
                    r'(Doctor of Philosophy\s*\(Ph\.?D\.?\))',
                    r'(Master of Science\s*\(M\.?S\.?\))',
                    r'(Master of Arts\s*\(M\.?A\.?\))',
                    r'(Master of Business Administration\s*\(M\.?B\.?A\.?\))',
                    r'(Master of Fine Arts\s*\(M\.?F\.?A\.?\))',
                    r'(Master of Engineering\s*\(M\.?Eng\.?\))',
                    r'(Master of Education\s*\(M\.?Ed\.?\))',
                    r'(Master of Public Administration\s*\(M\.?P\.?A\.?\))',
                    r'(Master of Landscape Architecture\s*\(M\.?L\.?A\.?\))',
                    r'(Master of Architecture\s*\(M\.?Arch\.?\))',
                    r'(Master of Community and Regional Planning\s*\(M\.?C\.?R\.?P\.?\))',
                    r'(Doctor of Veterinary Medicine\s*\(D\.?V\.?M\.?\))',
                    r'(Doctor of Musical Arts\s*\(D\.?M\.?A\.?\))',
                    r'(Graduate Certificate)',
                ]
                
                for pattern in degree_patterns:
                    found = re.findall(pattern, section, re.IGNORECASE)
                    for f in found:
                        if f and f not in degrees:
                            degrees.append(f)
        
        return degrees
    
    def _extract_deadline(self, soup: BeautifulSoup) -> str:
        """Extract application deadline information."""
        deadlines = []
        text = soup.get_text()
        
        # Look for Application Deadlines section
        patterns = [
            # International/Domestic with dates
            r'(International|Domestic)\s+(?:Applicants?\s+)?(?:should\s+)?(?:apply\s+)?(?:for\s+)?(?:priority\s+)?(?:consideration\s+)?by\s+([A-Z][a-z]+ \d{1,2})',
            # Priority/Final dates
            r'(priority|final)\s+(?:cutoff|deadline)[:\s]+([A-Z][a-z]+ \d{1,2})',
            # Fall/Spring with dates
            r'(Fall|Spring)\s+(?:semester|priority)?[:\s]*([A-Z][a-z]+ \d{1,2})',
            # Simple date patterns after deadline keywords
            r'(?:application\s+)?deadline[:\s]+([A-Z][a-z]+ \d{1,2}(?:,?\s+\d{4})?)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:2]:
                if isinstance(match, tuple):
                    deadline_text = f"{match[0]}: {match[1]}".strip()
                else:
                    deadline_text = match.strip()
                if deadline_text and len(deadline_text) > 3:
                    deadlines.append(deadline_text)
        
        if deadlines:
            # Deduplicate and limit
            unique = list(dict.fromkeys(deadlines))[:3]
            return "; ".join(unique)
        
        return "See Website"
    
    def _create_entry(self, name: str, url: str, deadline: str, category: str) -> Dict:
        """Create a result dictionary entry."""
        return {
            "学校代码": self.school_code,
            "学校名称": self.school_name,
            "项目名称": name,
            "学院/学习领域": category,
            "项目官网链接": url,
            "申请链接": self.apply_url,
            "项目opendate": "N/A",
            "项目deadline": deadline,
            "学生案例": "",
            "面试问题": ""
        }
