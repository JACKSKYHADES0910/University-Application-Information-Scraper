# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re
from spiders.base_spider import BaseSpider

class UCSCSpider(BaseSpider):
    def __init__(self, headless: bool = True):
        super().__init__("ucsc", headless)

    def run(self) -> List[Dict]:
        """
        Execute the crawl.
        """
        all_data = []
        
        # 1. Fetch deadlines from Google Sheet
        print("Fetching deadlines from Google Sheet...")
        deadline_map = self._fetch_deadlines()
        print(f"Loaded {len(deadline_map)} deadline entries.")
        
        url = self.list_url
        print(f"Fetching {url}")
        
        try:
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code != 200:
                print(f"Failed to load {url}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the main content area. UCSC wrapper usually.
            # Using a broad selector for links in the main content area
            main_content = soup.find('main')
            if not main_content:
                main_content = soup.find('body') # Fallback
                
            links = main_content.find_all('a', href=True)
            
            processed_programs = set()

            for link in links:
                href = link['href']
                text = link.get_text().strip()
                
                if not href or not text:
                    continue
                    
                # Filter URL: must contain graduate-programs/
                if 'graduate-programs/' not in href:
                    continue
                    
                # Filter Text
                if text in ["Graduate Programs", "Graduate Admissions", "Apply Now!", "Get to know UCSC"]:
                    continue
                    
                # Look for colon separator for Degree
                # Example: "Music: M.A., D.M.A., Ph.D."
                if ":" in text:
                    parts = text.split(":", 1)
                    program_name_part = parts[0].strip()
                    degrees_part = parts[1].strip()
                    
                    # Split degrees by comma
                    degrees = [d.strip() for d in degrees_part.split(",")]
                    
                    for degree in degrees:
                        full_program_name = f"{program_name_part}: {degree}"
                        
                        # Avoid duplicates
                        if full_program_name in processed_programs:
                            continue
                        processed_programs.add(full_program_name)
                        
                        detail_url = href
                        if not detail_url.startswith('http'):
                            detail_url = 'https://graduateadmissions.ucsc.edu' + detail_url
                            
                        # Lookup deadline from map
                        # Map keys are roughly (Program Name, Degree)
                        # We try to fuzzy match or direct match
                        deadline = self._match_deadline(deadline_map, program_name_part, degree)
                        
                        item = self.create_result_template(full_program_name, detail_url)
                        item["学院/学习领域"] = "Graduate Division" 
                        item["项目deadline"] = deadline if deadline else "N/A"
                        item["申请链接"] = self.university_info["apply_register_url"]
                        item["degree_level"] = self._map_degree_level(degree)
                        
                        all_data.append(item)
                        print(f"Added: {full_program_name} | Deadline: {item['项目deadline']}")
                else:
                    pass
                    
        except Exception as e:
            print(f"Error in UCSC run: {e}")
            
        self.results = all_data
        self.print_summary()
        return self.results

    def _fetch_deadlines(self) -> Dict[tuple, str]:
        """
        Fetch and parse the Google Sheet CSV.
        Returns: Dict[(Program, Degree), Deadline]
        """
        import csv
        import io
        
        deadlines = {}
        # URL for Google Sheet CSV export
        sheet_id = "1Q45Rw5fX2RY-HUl60JyCc3Wm9XEVlweBat3BXZYLJFw"
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=0"
        
        try:
            resp = requests.get(csv_url, timeout=10)
            if resp.status_code == 200:
                content = resp.content.decode('utf-8')
                reader = csv.reader(io.StringIO(content))
                # Skip header if present (assuming Row 1 is header)
                # Based on observation, headers might be specific. We'll check content.
                rows = list(reader)
                
                start_row = 0
                # Heuristic to find header row: look for 'Program' or 'Degree'
                for i, row in enumerate(rows[:5]):
                    row_str = "".join(row).lower()
                    if "program" in row_str or "degree" in row_str:
                        start_row = i + 1
                        break
                
                for row in rows[start_row:]:
                    if len(row) < 3:
                        continue
                    
                    # Assuming Column 0: Program, Column 1: Degree, Column 2: Deadline/Date
                    # Column indices might vary, let's be robust
                    prog = row[0].strip()
                    deg = row[1].strip()
                    date = row[2].strip()
                    
                    if not prog:
                        continue
                        
                    deadlines[(prog.lower(), deg.lower())] = date
            else:
                print(f"Failed to fetch CSV: {resp.status_code}")
                
        except Exception as e:
            print(f"Error fetching deadlines: {e}")
            
        return deadlines

    def _match_deadline(self, deadline_map: Dict[tuple, str], program: str, degree: str) -> Optional[str]:
        """
        Match the spider's program/degree to the CSV data.
        """
        p_lower = program.lower()
        d_lower = degree.lower()
        
        # 1. Exact match
        if (p_lower, d_lower) in deadline_map:
            return deadline_map[(p_lower, d_lower)]
            
        # 2. Degree normalization match
        # Spider degree might be "M.S." and CSV might be "M.S." or "MS"
        # We try to strip dots
        d_norm = d_lower.replace(".", "")
        
        for (csv_p, csv_d), date in deadline_map.items():
            csv_d_norm = csv_d.replace(".", "")
            if csv_p == p_lower and csv_d_norm == d_norm:
                return date
                
        # 3. Partial Program Match (if needed)
        # e.g., "Art: Environmental Art..." vs "Environmental Art..."
        # But for now, strict program name match is safer.
        
        return None

    def _map_degree_level(self, degree: str) -> str:
        degree = degree.lower()
        if "ph.d" in degree or "d.m.a" in degree or "doctor" in degree:
            return "Doctorate"
        if "m.a" in degree or "m.s" in degree or "m.f.a" in degree or "master" in degree:
            return "Master"
        return "Unknown"
