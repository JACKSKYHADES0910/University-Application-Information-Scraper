import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from spiders.base_spider import BaseSpider

class MarylandSpider(BaseSpider):
    name = 'maryland'
    
    # Application link mapping based on university name
    UNIVERSITY_APP_LINKS = {
        "Bowie State University": "https://bulldogs.bowiestate.edu/apply/",
        "Salisbury University": "https://gogulls.salisbury.edu/portal/app_mgmt",
        "Towson University": "https://www.applyweb.com/towsong/index.ftl?_gl=1*148z6mb*_gcl_au*MTYyMDQyODIzLjE3Njg0NjM4ODY.*_ga*MTI5Mjc2MjYzNi4xNzY4NDYzODg3*_ga_6C0QDF6HTB*czE3Njg0NjM4ODYkbzEkZzEkdDE3Njg0NjM4OTAkajU2JGwwJGgw",
        "University of Baltimore": "https://ubalt.my.site.com/TX_SiteLogin?startURL=%2FTargetX_Portal__PB",
        "University of Maryland, Baltimore": "https://www.applyweb.com/cgi-bin/app?s=UMBCG2",
        "University of Maryland, Baltimore County": "https://www.applyweb.com/cgi-bin/app?s=UMBCG2",
        "University of Maryland, College Park": "https://www.applyweb.com/cgi-bin/app?s=UMBCG2",
        "University of Maryland Global Campus": "https://apply.umgc.edu/"
    }

    def safe_request(self, url):
        import requests
        from config import HEADERS, TIMEOUT, MAX_RETRIES
        import time
        
        for i in range(MAX_RETRIES):
            try:
                resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
                if resp.status_code == 200:
                    return resp
                print(f"Request failed with status {resp.status_code}")
            except Exception as e:
                print(f"Request exception: {e}")
            time.sleep(1)
        return None

    def __init__(self, headless: bool = True):
        super().__init__("maryland", headless)

    def _make_absolute_url(self, relative_url):
        from urllib.parse import urljoin
        if not relative_url:
            return ""
        if relative_url.startswith("http"):
            return relative_url
        return urljoin(self.base_url, relative_url)

    def _get_program_list(self) -> List[Dict]:
        """
        Extract program list from the main listing page using specific pagination URLs
        requested by user to ensure complete coverage.
        """
        all_programs = []
        base_url = "https://shadygrove.usmd.edu/academics/degree-programs?f%5B0%5D=level%3AGraduate&items_per_page=100"
        
        # User specified 6 pages (index 0 to 5)
        # Page 1: ...&items_per_page=100
        # Page 2: ...&items_per_page=100&page=1
        
        for page_index in range(6):
            if page_index == 0:
                current_url = base_url
            else:
                current_url = f"{base_url}&page={page_index}"
                
            print(f"Visiting page {page_index + 1}: {current_url}")
            
            response = self.safe_request(current_url)
            
            if not response:
                print(f"Failed to load page {page_index + 1}")
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the programs table or rows directly
            rows = soup.select('.views-row')
            if not rows:
                rows = soup.select('table tbody tr')
            
            if not rows:
                print(f"No rows found on page {page_index + 1}")
                continue
                
            programs_on_page = 0
            for row in rows:
                program_data = self._extract_program_from_row(row)
                if program_data:
                    all_programs.append(program_data)
                    programs_on_page += 1
                # Removed debug print for skipped rows to keep output clean for user
            
            print(f"Page {page_index + 1}: Found {programs_on_page} programs")
            self.random_sleep(1, 2)
            
        print(f"Total programs found: {len(all_programs)}")
        return all_programs

    def _extract_program_from_row(self, row) -> Optional[Dict]:
        """
        Extract program details from a table row
        """
        try:
            # Degree Type
            degree_type_elem = row.select_one('.views-field-field-degree-type')
            degree_type = degree_type_elem.get_text(strip=True) if degree_type_elem else ""
            
            # Level
            level_elem = row.select_one('.views-field-level')
            level = level_elem.get_text(strip=True) if level_elem else ""
            
            # We are targeting Graduate programs
            # Filter out Undergraduate programs
            if "Undergraduate" in level:
                return None
                
            # Program Name and Link
            title_elem = row.select_one('.views-field-title a')
            if not title_elem:
                return None
                
            program_name = title_elem.get_text(strip=True)
            program_url = self._make_absolute_url(title_elem.get('href', ''))
            
            # University/School
            uni_elem = row.select_one('.views-field-field-institution')
            university_name = uni_elem.get_text(strip=True) if uni_elem else ""
            
            # Map application link
            # Clean up university name if needed (remove extra spaces)
            university_name_clean = university_name.strip()
            app_link = self.UNIVERSITY_APP_LINKS.get(university_name_clean, "N/A")
            
            return {
                "program_name": program_name,
                "school": university_name_clean, # Mapping "Universities" column to "School/Academy"
                "degree_level": level,
                "degree_type": degree_type,
                "program_url": program_url,
                "application_link": app_link
            }
            
        except Exception as e:
            print(f"Error extracting row: {e}")
            return None

    def run(self) -> List[Dict]:
        """
        Main entry point for the spider
        """
        print("Starting Maryland Spider...")
        raw_programs = self._get_program_list()
        
        results = []
        for program in raw_programs:
            # Create base template
            item = self.create_result_template(
                program_name=program['program_name'],
                program_link=program['program_url']
            )
            
            # Fill in additional details
            item['学院/学习领域'] = program['school']
            item['申请链接'] = program['application_link']
            # We put Degree Type in the name or separate? 
            # Standard template usually implies Name, but let's append Degree Type to Name if useful, 
            # or usually Degree Type is filtered. 
            # Looking at other spiders, '项目名称' is usually the name.
            # We can also add degree type to the name to be more specific.
            # But for now, let's keep it clean.
            
            # Add extra fields if needed, but the template is fixed.
            # Usually we might want to store degree type in a custom way if needed, 
            # but for now let's just stick to the requested fields.
            
            self.results.append(item)
            results.append(item)
            
        self.print_summary()
        return results

    def _extract_program_details(self, program_url: str) -> Dict:
        """
        Placeholder for detail extraction.
        """
        return {}
