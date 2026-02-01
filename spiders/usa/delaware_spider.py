# -*- coding: utf-8 -*-
"""
University of Delaware Spider
Scrapes graduate programs from https://www.udel.edu/academics/colleges/grad/prospective-students/programs/
Features: Category mapping, degree splitting, deadline extraction
"""

import time
import re
import random
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple

from spiders.base_spider import BaseSpider
from utils.progress import CrawlerProgress, print_phase_complete

class DelawareSpider(BaseSpider):
    """
    University of Delaware graduate programs spider.
    Extracts program names, splits by degree type, collects deadlines, and assigns categories.
    """
    
    name = "delaware"
    
    # College-to-category mapping based on URL/keyword patterns
    COLLEGE_CATEGORY_MAP = {
        # Business & Economics
        'lerner': 'Business & Economics',
        'business': 'Business & Economics',
        'accounting': 'Business & Economics',
        'finance': 'Business & Economics',
        'entrepreneurship': 'Business & Economics',
        'marketing': 'Business & Economics',
        'hospitality': 'Business & Economics',
        
        # Biological & Health Sciences
        'canr': 'Biological & Health Sciences',
        'agriculture': 'Biological & Health Sciences',
        'animal': 'Biological & Health Sciences',
        'food-science': 'Biological & Health Sciences',
        'health': 'Biological & Health Sciences',
        'nursing': 'Biological & Health Sciences',
        'biology': 'Biological & Health Sciences',
        'biomedical': 'Biological & Health Sciences',
        'bioinformatics': 'Biological & Health Sciences',
        'biomechanics': 'Biological & Health Sciences',
        'kinesiology': 'Biological & Health Sciences',
        'physiology': 'Biological & Health Sciences',
        'exercise': 'Biological & Health Sciences',
        'nutrition': 'Biological & Health Sciences',
        'medical': 'Biological & Health Sciences',
        'plant': 'Biological & Health Sciences',
        'ecology': 'Biological & Health Sciences',
        'wildlife': 'Biological & Health Sciences',
        'entomology': 'Biological & Health Sciences',
        'neuroscience': 'Biological & Health Sciences',
        
        # Math, Physical Sciences & Engineering
        'engineering': 'Math, Physical Sciences & Engineering',
        'computer': 'Math, Physical Sciences & Engineering',
        'electrical': 'Math, Physical Sciences & Engineering',
        'mechanical': 'Math, Physical Sciences & Engineering',
        'chemical': 'Math, Physical Sciences & Engineering',
        'civil': 'Math, Physical Sciences & Engineering',
        'materials': 'Math, Physical Sciences & Engineering',
        'physics': 'Math, Physical Sciences & Engineering',
        'chemistry': 'Math, Physical Sciences & Engineering',
        'mathematics': 'Math, Physical Sciences & Engineering',
        'applied-math': 'Math, Physical Sciences & Engineering',
        'statistics': 'Math, Physical Sciences & Engineering',
        'data-science': 'Math, Physical Sciences & Engineering',
        'cybersecurity': 'Math, Physical Sciences & Engineering',
        'artificial-intelligence': 'Math, Physical Sciences & Engineering',
        'ocean': 'Math, Physical Sciences & Engineering',
        'environmental': 'Math, Physical Sciences & Engineering',
        'geography': 'Math, Physical Sciences & Engineering',
        'geology': 'Math, Physical Sciences & Engineering',
        
        # Social Sciences
        'education': 'Social Sciences',
        'psychology': 'Social Sciences',
        'sociology': 'Social Sciences',
        'political': 'Social Sciences',
        'economics': 'Social Sciences',
        'communication': 'Social Sciences',
        'public-policy': 'Social Sciences',
        'urban-affairs': 'Social Sciences',
        'criminology': 'Social Sciences',
        'human-development': 'Social Sciences',
        'family-studies': 'Social Sciences',
        'fashion': 'Social Sciences',
        'apparel': 'Social Sciences',
        'disaster-science': 'Social Sciences',
        
        # Arts & Humanities
        'art': 'Arts & Humanities',
        'music': 'Arts & Humanities',
        'theatre': 'Arts & Humanities',
        'history': 'Arts & Humanities',
        'english': 'Arts & Humanities',
        'philosophy': 'Arts & Humanities',
        'languages': 'Arts & Humanities',
        'linguistics': 'Arts & Humanities',
        'liberal': 'Arts & Humanities',
        'museum': 'Arts & Humanities',
        'preservation': 'Arts & Humanities',
        'winterthur': 'Arts & Humanities',
        'american-studies': 'Arts & Humanities',
    }
    
    def __init__(self, headless: bool = False):
        super().__init__(self.name, headless=False)

    def run(self) -> List[Dict]:
        """
        Main execution:
        Phase 1: Use Selenium + JS to get all program links
        Phase 2: Concurrent requests to fetch details and split degrees
        """
        self.start_time = time.time()
        
        try:
            # Navigate to programs page
            self.driver.get(self.list_url)
            print(f"Navigated to {self.list_url}")
            
            # Wait for initial page load
            time.sleep(5)
            
            # Click "VIEW ALL PROGRAMS" using pure JavaScript
            print("\n📋 Clicking 'VIEW ALL PROGRAMS'...")
            click_result = self.driver.execute_script("""
                const elements = Array.from(document.querySelectorAll('*'));
                const btn = elements.find(el => 
                    el.textContent && 
                    el.textContent.trim().toUpperCase() === 'VIEW ALL PROGRAMS'
                );
                if (btn) {
                    btn.scrollIntoView();
                    btn.click();
                    return true;
                }
                return false;
            """)
            
            if click_result:
                print("✅ 'VIEW ALL PROGRAMS' clicked successfully")
            else:
                print("⚠️ Could not find 'VIEW ALL PROGRAMS' button")
            
            # Wait for list to update
            time.sleep(3)
            
            # Extract all program links via JavaScript
            print("📂 Extracting program links...")
            links_data = self.driver.execute_script("""
                const links = Array.from(document.querySelectorAll('a[href*="/programs/"]'))
                    .filter(a => a.title && a.title.trim().length > 0);
                return links.map(a => ({
                    name: a.title.trim() || a.textContent.trim(),
                    url: a.href
                }));
            """)
            
            print(f"   Raw links found: {len(links_data)}")
            
            # Remove duplicates and assign categories
            seen = set()
            unique_items = []
            for item in links_data:
                if item['url'] not in seen and '/programs/' in item['url']:
                    if item['url'].rstrip('/').endswith('/programs'):
                        continue
                    seen.add(item['url'])
                    # Infer category from URL
                    item['category'] = self._infer_category_from_url(item['url'])
                    unique_items.append(item)
            
            print_phase_complete("Phase 1", len(unique_items))
            
            # Category stats
            cat_counts = {}
            for item in unique_items:
                cat = item.get('category', 'Unknown')
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
            print("📊 Category distribution:")
            for cat, count in sorted(cat_counts.items()):
                print(f"   • {cat}: {count} programs")
            
            if not unique_items:
                print("⚠️ No programs found!")
                return []
            
            # Phase 2: Fetch details with concurrency
            print("\n🔍 Phase 2: Fetching program details...")
            progress = CrawlerProgress(max_workers=24)
            processed_items = progress.run_tasks(
                items=unique_items,
                task_func=self._parse_program_details,
                task_name="Scraping Program Details",
                phase_name="Phase 2"
            )
            
            # Flatten results
            for sublist in processed_items:
                if sublist:
                    self.results.extend(sublist)
            
            return self.results
            
        finally:
            self.close()

    def _infer_category_from_url(self, url: str) -> str:
        """Infer category from URL patterns."""
        url_lower = url.lower()
        
        for keyword, category in self.COLLEGE_CATEGORY_MAP.items():
            if keyword in url_lower:
                return category
        
        return "Graduate Programs"

    def _parse_program_details(self, item: Dict) -> Tuple[List[Dict], float]:
        """
        Fetch program page and extract degrees.
        Returns list of result dicts (one per degree type).
        """
        start_time = time.time()
        
        url = item['url']
        raw_name = item['name']
        category = item.get('category', 'Graduate Programs')
        
        results_list = []
        
        try:
            time.sleep(random.uniform(0.3, 0.8))
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                raise Exception(f"Status {resp.status_code}")
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Update category from detail page links if still generic
            if category == "Graduate Programs":
                category = self._extract_category_from_page(soup, url)
            
            # Get H1 title - contains "Program: Degree1, Degree2"
            h1 = soup.find('h1')
            page_title = h1.get_text().strip() if h1 else ""
            
            # Extract degrees from page title
            degrees = []
            base_name = raw_name
            
            if ':' in page_title:
                parts = page_title.split(':', 1)
                base_name = parts[0].strip().title()
                degree_part = parts[1].strip()
                degrees = self._split_degrees(degree_part)
            
            # Fallback: scan content
            if not degrees:
                text = soup.get_text()[:5000]
                degrees = self._extract_degrees_from_text(text)
            
            # Extract deadline
            deadline = self._extract_deadline(soup)
            
            # Create result entries
            if degrees:
                for degree in degrees:
                    final_name = f"{base_name}: {degree}"
                    results_list.append(self._create_entry(final_name, url, deadline, category))
            else:
                results_list.append(self._create_entry(raw_name, url, deadline, category))
            
        except Exception as e:
            results_list.append(self._create_entry(raw_name, url, "See Website", category))
        
        duration = time.time() - start_time
        return results_list, duration

    def _extract_category_from_page(self, soup: BeautifulSoup, url: str) -> str:
        """Extract category from page content."""
        # Check links on the page
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            text = link.get_text().lower()
            combined = href + " " + text
            
            for keyword, category in self.COLLEGE_CATEGORY_MAP.items():
                if keyword in combined:
                    return category
        
        return "Graduate Programs"

    def _split_degrees(self, text: str) -> List[str]:
        """Split degree string by comma."""
        # Normalize "and" to comma
        text = re.sub(r'\s+and\s+', ', ', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*&\s*', ', ', text)
        
        tokens = [t.strip() for t in text.split(',')]
        
        result = []
        for token in tokens:
            token = token.strip()
            if token and len(token) >= 2:
                token = self._normalize_degree(token)
                if token:
                    result.append(token)
        
        return result

    def _normalize_degree(self, degree: str) -> str:
        """Normalize degree format."""
        degree = degree.strip()
        
        mappings = {
            r'^MS$': 'M.S.', r'^MA$': 'M.A.', r'^MBA$': 'M.B.A.',
            r'^PHD$': 'Ph.D.', r'^EDD$': 'Ed.D.', r'^MED$': 'M.Ed.',
            r'^MFA$': 'M.F.A.', r'^MPA$': 'M.P.A.', r'^MPP$': 'M.P.P.',
            r'^DNP$': 'D.N.P.', r'^DPT$': 'D.P.T.', r'^PSM$': 'P.S.M.',
        }
        
        upper = degree.upper().replace('.', '')
        for pattern, replacement in mappings.items():
            if re.match(pattern, upper):
                return replacement
        
        return degree

    def _extract_degrees_from_text(self, text: str) -> List[str]:
        """Extract degree keywords from text."""
        degrees = set()
        
        pattern = r'\b(?:M\.?S\.?|Ph\.?D\.?|M\.?A\.?|M\.?B\.?A\.?|M\.?Ed\.?|Ed\.?D\.?|D\.?P\.?T\.?|M\.?F\.?A\.?|M\.?P\.?A\.?|M\.?P\.?P\.?|D\.?N\.?P\.?|Ed\.?S\.?|P\.?S\.?M\.?|4\+1|3\+2|Certificate)\b'
        
        found = re.findall(pattern, text, re.IGNORECASE)
        for f in found:
            f = self._normalize_degree(f.strip())
            if f.lower() not in ['degree', 'degrees']:
                degrees.add(f)
        
        return list(degrees)

    def _extract_deadline(self, soup: BeautifulSoup) -> str:
        """Extract deadline information."""
        deadlines = []
        
        text = soup.get_text()[:8000]
        
        patterns = [
            r'(Fall|Spring|Summer)[\s:]*([A-Z][a-z]+ \d{1,2}(?:,? \d{4})?)',
            r'(International|Domestic)[\s:]*(?:deadline[:\s]*)?([A-Z][a-z]+ \d{1,2}(?:,? \d{4})?)',
            r'(?:Application\s+)?[Dd]eadline[:\s]*([A-Z][a-z]+ \d{1,2}(?:,? \d{4})?)',
            r'(Rolling|rolling)\s*(?:admission)?'
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
            "申请链接": "https://grad-admissions.udel.edu/apply/",
            "项目opendate": "N/A",
            "项目deadline": deadline,
            "学生案例": "",
            "面试问题": ""
        }
