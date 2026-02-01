# -*- coding: utf-8 -*-
"""
Oregon State University Spider
Scrapes graduate programs from https://graduate.oregonstate.edu/programs
Features: College filtering, degree splitting, deadline extraction
"""

import time
import re
import random
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

# Try to import undetected_chromedriver
try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False
    print("⚠️ undetected-chromedriver not found, falling back to standard driver")

from spiders.base_spider import BaseSpider
from utils.progress import CrawlerProgress, print_phase_complete

class OregonStateSpider(BaseSpider):
    """
    Oregon State University graduate programs spider.
    Extracts program names, splits by degree type, collects deadlines, and assigns colleges.
    """
    
    name = "oregon_state"
    
    # College filter options (from website dropdown)
    COLLEGES = [
        "College of Agricultural Sciences",
        "College of Business",
        "College of Earth, Ocean, and Atmospheric Sciences",
        "College of Education",
        "College of Engineering",
        "College of Forestry",
        "College of Health",
        "College of Liberal Arts",
        "College of Pharmacy",
        "College of Science",
        "College of Veterinary Medicine",
        "Office of Graduate Education"
    ]
    
    # Common degree patterns for parsing
    DEGREE_PATTERNS = [
        r'Ed\.?M\.?', r'Ed\.?D\.?', r'Ph\.?D\.?', r'M\.?S\.?', r'M\.?A\.?',
        r'M\.?B\.?A\.?', r'M\.?F\.?A\.?', r'M\.?P\.?A\.?', r'M\.?P\.?P\.?',
        r'M\.?P\.?H\.?', r'M\.?Eng\.?', r'MEng', r'MNR', r'MF', r'MATrn',
        r'MAIS', r'MSB', r'MAT', r'MCoun', r'MHP', r'PSM', r'EMPP',
        r'CERT', r'minor', r'D\.?N\.?P\.?'
    ]
    
    # URL patterns to college mapping
    URL_COLLEGE_MAP = {
        'agricultural': 'College of Agricultural Sciences',
        'animal': 'College of Agricultural Sciences',
        'crop': 'College of Agricultural Sciences',
        'soil': 'College of Agricultural Sciences',
        'horticulture': 'College of Agricultural Sciences',
        'food-science': 'College of Agricultural Sciences',
        'fisheries': 'College of Agricultural Sciences',
        'rangeland': 'College of Agricultural Sciences',
        
        'business': 'College of Business',
        'mba': 'College of Business',
        'msb': 'College of Business',
        'accounting': 'College of Business',
        'supply-chain': 'College of Business',
        
        'ocean': 'College of Earth, Ocean, and Atmospheric Sciences',
        'atmospheric': 'College of Earth, Ocean, and Atmospheric Sciences',
        'geology': 'College of Earth, Ocean, and Atmospheric Sciences',
        'geography': 'College of Earth, Ocean, and Atmospheric Sciences',
        
        'education': 'College of Education',
        'teaching': 'College of Education',
        'counseling': 'College of Education',
        'adult-and-higher': 'College of Education',
        
        'engineering': 'College of Engineering',
        'computer-science': 'College of Engineering',
        'electrical': 'College of Engineering',
        'mechanical': 'College of Engineering',
        'chemical-eng': 'College of Engineering',
        'civil-eng': 'College of Engineering',
        'nuclear': 'College of Engineering',
        'robotics': 'College of Engineering',
        'materials': 'College of Engineering',
        'industrial': 'College of Engineering',
        'bioengineering': 'College of Engineering',
        'artificial-intelligence': 'College of Engineering',
        
        'forest': 'College of Forestry',
        'timber': 'College of Forestry',
        'natural-resources': 'College of Forestry',
        'wood': 'College of Forestry',
        
        'health': 'College of Health',
        'public-health': 'College of Health',
        'kinesiology': 'College of Health',
        'nutrition': 'College of Health',
        'athletic-training': 'College of Health',
        'human-development': 'College of Health',
        
        'liberal-arts': 'College of Liberal Arts',
        'anthropology': 'College of Liberal Arts',
        'communication': 'College of Liberal Arts',
        'creative-writing': 'College of Liberal Arts',
        'english': 'College of Liberal Arts',
        'history': 'College of Liberal Arts',
        'philosophy': 'College of Liberal Arts',
        'political': 'College of Liberal Arts',
        'psychology': 'College of Liberal Arts',
        'sociology': 'College of Liberal Arts',
        'ethnic-studies': 'College of Liberal Arts',
        'queer-studies': 'College of Liberal Arts',
        'public-policy': 'College of Liberal Arts',
        
        'pharmacy': 'College of Pharmacy',
        'pharmaceutical': 'College of Pharmacy',
        
        'science': 'College of Science',
        'biochemistry': 'College of Science',
        'biology': 'College of Science',
        'botany': 'College of Science',
        'chemistry': 'College of Science',
        'mathematics': 'College of Science',
        'microbiology': 'College of Science',
        'physics': 'College of Science',
        'statistics': 'College of Science',
        'integrative-biology': 'College of Science',
        'data-analytics': 'College of Science',
        
        'veterinary': 'College of Veterinary Medicine',
        'comparative-health': 'College of Veterinary Medicine',
        'toxicology': 'College of Veterinary Medicine',
    }
    
    def __init__(self, headless: bool = False):
        super().__init__(self.name, headless=headless)
        self.apply_url = self.university_info.get('apply_url', 'https://advanced.oregonstate.edu/portal/gr-app')
        
        # Initialize undetected-chromedriver if available
        if UC_AVAILABLE:
            print("🚀 Initializing undetected-chromedriver...")
            
            # FORCE Non-Headless for Cloudflare Bypass
            if headless:
                print("⚠️  Forcing Non-Headless mode to bypass Cloudflare challenge...")
                headless = False
            
            options = uc.ChromeOptions()
            # if headless: # Disabled for stability
            #     options.add_argument('--headless=new')
            
            # Anti-detection options
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-popup-blocking')
            options.add_argument('--incognito')
            
            try:
                # Explicitly set version to match installed Chrome (143) to avoid mismatch
                # Override self.driver with undetected-chromedriver
                self.driver = uc.Chrome(options=options, headless=False)
                self.driver.set_page_load_timeout(30)
                self.driver.implicitly_wait(5)
                print("✅ undetected-chromedriver initialized (Visible Mode for Cloudflare)")
            except Exception as e:
                print(f"⚠️  undetected-chromedriver failed to initialize: {e}")
                print("⚠️  Falling back to standard Selenium (Visible Mode).")
                print("    Note: Cloudflare might detect this driver. Manual interaction may be required.")
                # We already have a standard driver from super().__init__, but correct its timeouts
                self.driver.set_page_load_timeout(30)
                self.driver.implicitly_wait(5)

    def run(self) -> List[Dict]:
        """
        Main execution:
        Phase 1: Extract all programs from main page
        Phase 2: Sequential Selenium visits to fetch deadlines (to bypass Cloudflare)
        """
        self.start_time = time.time()
        
        try:
            # Phase 1: Extract all programs
            print("\n📋 Phase 1: Extracting programs...")
            all_programs = self._extract_all_programs()
            
            print_phase_complete("Phase 1", len(all_programs))
            
            if not all_programs:
                print("⚠️ No programs found!")
                return []
            
            # College distribution
            college_counts = {}
            for url, item in all_programs.items():
                col = item.get('college', 'Unknown')
                college_counts[col] = college_counts.get(col, 0) + 1
            print("\n📚 College distribution:")
            for col, cnt in sorted(college_counts.items(), key=lambda x: -x[1]):
                print(f"   • {col}: {cnt}")
            
            # Phase 2: Sequential processing with Selenium
            print("\n🔍 Phase 2: Processing programs and fetching deadlines (Sequential)...")
            
            # Flatten items to list
            items = list(all_programs.values())
            total_items = len(items)
            
            # Progress tracking
            for i, item in enumerate(items, 1):
                print(f"   [{i}/{total_items}] Processing {item.get('name', 'Unknown')}...")
                
                # Process single item
                try:
                    res, _ = self._process_program(item)
                    if res:
                        self.results.extend(res)
                except Exception as e:
                    print(f"      ⚠️ Error processing item: {e}")
                
                # Small delay to be polite
                if i % 10 == 0:
                    time.sleep(1)
            
            print(f"\n✅ Total programs extracted: {len(self.results)}")
            return self.results
            
        finally:
            self.close()

    def _extract_all_programs(self) -> Dict[str, Dict]:
        """
        Extract all programs from the main page.
        Returns dict keyed by program URL.
        """
        all_programs = {}
        
        # Navigate to main page
        self.driver.get(self.list_url)
        
        # Wait for page to load
        print("   Waiting for page to load...")
        time.sleep(5)
        
        # Check if we hit Cloudflare challenge
        page_source = self.driver.page_source.lower()
        if 'verify you are human' in page_source or 'cloudflare' in page_source:
            print("\n" + "=" * 60)
            print("⚠️  CLOUDFLARE CHALLENGE DETECTED")
            print("=" * 60)
            print("🤖 Attempting to auto-solve (Incognito Mode)...")
            
            # Initial attempt
            self._try_bypass_cloudflare()
            
            # Wait loop
            max_wait = 60
            waited = 0
            while waited < max_wait:
                time.sleep(5)
                waited += 5
                page_source = self.driver.page_source.lower()
                if 'verify you are human' not in page_source and 'cloudflare' not in page_source:
                    print(f"   ✅ Cloudflare verification completed after {waited}s")
                    break
                
                # Retry logic
                if waited % 10 == 0:
                     self._try_bypass_cloudflare()
                     
                print(f"   Waiting for verification... ({waited}/{max_wait}s)")
            
            time.sleep(2)

        # Wait for program links to appear
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/programs/"]'))
            )
        except:
            pass # Timeout handled by extraction result
        
        # Extract all program links
        print("   Extracting program links...")
        programs = self._extract_current_page_programs()
        
        for prog in programs:
            url = prog['url']
            if url not in all_programs:
                # Infer college from URL
                prog['college'] = self._infer_college_from_url(url)
                all_programs[url] = prog
        
        print(f"   Found {len(all_programs)} unique programs")
        return all_programs

    def _try_bypass_cloudflare(self):
        """Attempt to locate and click the Cloudflare verification checkbox."""
        from selenium.webdriver.common.by import By
        try:
            print("   🔎 Analyzing DOM structure...")
            
            # Debug/Context
            src_lower = self.driver.page_source.lower()
            if 'verify you are human' in src_lower:
                pass # Verified present
            
            # Check for Shadow Roots
            shadow_hosts = self.driver.execute_script("""
                return Array.from(document.querySelectorAll('*'))
                    .filter(el => el.shadowRoot)
                    .map(el => ({
                        tag: el.tagName,
                        id: el.id,
                        class: el.className
                    }));
            """)
            if shadow_hosts:
                print(f"   🔎 Found {len(shadow_hosts)} shadow hosts")
            
            # Check iframes
            iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
            if iframes:
                print(f"   🔎 Found {len(iframes)} iframes")
                for i, f in enumerate(iframes):
                    try:
                        src = f.get_attribute('src') or ''
                        if 'cloudflare' in src or 'turnstile' in src or 'challenge' in src:
                            print(f"      🎯 Target found: Frame {i}")
                            self.driver.switch_to.frame(f)
                            time.sleep(0.5)
                            try:
                                self.driver.find_element(By.TAG_NAME, "body").click()
                            except:
                                pass
                            try:
                                cb = self.driver.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                                if cb: cb.click()
                            except:
                                pass
                            self.driver.switch_to.default_content()
                    except:
                        pass

            # Shadow DOM brute force
            if shadow_hosts:
                for host in shadow_hosts:
                    try:
                        selector = host['tag']
                        if host['id']: selector += f"#{host['id']}"
                        elif host['class']: selector += f".{host['class'].split()[0]}"
                        
                        el = self.driver.find_element(By.CSS_SELECTOR, selector)
                        shadow = self.driver.execute_script("return arguments[0].shadowRoot", el)
                        try:
                            cb = self.driver.execute_script("return arguments[0].querySelector('input[type=\"checkbox\"]')", shadow)
                            if cb: cb.click()
                        except:
                            pass
                    except:
                        pass
            
            # Keyboard Interaction (Fallback)
            print("   ⌨️ Attempting blind keyboard interaction...")
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                from selenium.webdriver.common.keys import Keys
                
                action = ActionChains(self.driver)
                try:
                    self.driver.find_element(By.TAG_NAME, 'body').click()
                except:
                    pass
                time.sleep(0.5)
                
                # Tab + Space sequence
                print("      👉 Sending TAB + SPACE sequence...")
                action.send_keys(Keys.TAB).perform()
                time.sleep(0.2)
                action.send_keys(Keys.SPACE).perform()
                
                time.sleep(0.5)
                # Try double tab
                action.send_keys(Keys.TAB).perform()
                action.send_keys(Keys.TAB).perform()
                action.send_keys(Keys.SPACE).perform()
                
            except Exception as e:
                print(f"      ⚠️ Keyboard error: {e}")
                        
        except Exception as e:
            print(f"   ⚠️ Auto-click debugging failed: {e}")
            try:
                self.driver.switch_to.default_content()
            except:
                pass

    def _infer_college_from_url(self, url: str) -> str:
        """Infer college from URL patterns."""
        url_lower = url.lower()
        for pattern, college in self.URL_COLLEGE_MAP.items():
            if pattern in url_lower:
                return college
        return "Graduate Programs"

    def _extract_current_page_programs(self) -> List[Dict]:
        """Extract program names and links from current page."""
        programs = []
        
        try:
            data = self.driver.execute_script("""
                const links = Array.from(document.querySelectorAll('a[href*="/programs/"], a[href*="/minor/"], a[href*="/program/"]'));
                return links
                    .filter(a => {
                        const text = a.textContent.trim();
                        // Skip AMP, WRGP and other special links
                        if (['AMP', 'WRGP'].includes(text)) return false;
                        if (!text || text.length < 5) return false;
                        return true;
                    })
                    .map(a => ({
                        name: a.textContent.trim(),
                        url: a.href
                    }));
            """)
            
            # Deduplicate by URL
            seen = set()
            for item in data:
                url = item['url']
                if url not in seen and '/accelerated-masters' not in url and '/western-regional' not in url:
                    seen.add(url)
                    programs.append(item)
                    
        except Exception as e:
            print(f"   ⚠️ Error extracting programs: {e}")
        
        return programs

    def _process_program(self, item: Dict) -> Tuple[List[Dict], float]:
        """
        Process a program: split degrees and fetch deadline from detail page.
        Returns list of result dicts (one per degree type).
        """
        start_time = time.time()
        
        url = item['url']
        raw_name = item['name']
        college = item.get('college', 'Graduate Programs')
        
        results_list = []
        
        try:
            # Parse program name and degrees
            base_name, degrees = self._parse_program_name(raw_name)
            
            # Fetch deadline from detail page
            deadline = self._fetch_deadline(url)
            
            # Create entries for each degree
            if degrees:
                for degree in degrees:
                    final_name = f"{base_name} - {degree}"
                    results_list.append(self._create_entry(final_name, url, deadline, college))
            else:
                # No degree splitting needed
                results_list.append(self._create_entry(base_name, url, deadline, college))
            
        except Exception as e:
            # Fallback entry
            results_list.append(self._create_entry(raw_name, url, "N/A", college))
        
        duration = time.time() - start_time
        return results_list, duration

    def _parse_program_name(self, name: str) -> Tuple[str, List[str]]:
        """
        Parse program name like "Adult and Higher Education (Ed.M., Ed.D., Ph.D., minor)"
        Returns (base_name, list_of_degrees)
        """
        # Match pattern: Name (degrees)
        match = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', name)
        
        if not match:
            return name.strip(), []
        
        base_name = match.group(1).strip()
        degree_part = match.group(2).strip()
        
        # Split degrees by comma
        degrees = []
        for part in degree_part.split(','):
            degree = part.strip()
            if degree:
                # Normalize the degree
                degree = self._normalize_degree(degree)
                degrees.append(degree)
        
        return base_name, degrees

    def _normalize_degree(self, degree: str) -> str:
        """Normalize degree format."""
        degree = degree.strip()
        
        # Common normalizations
        mappings = {
            'MS': 'M.S.', 'MA': 'M.A.', 'MBA': 'M.B.A.',
            'PHD': 'Ph.D.', 'EDD': 'Ed.D.', 'EDM': 'Ed.M.',
            'MFA': 'M.F.A.', 'MPA': 'M.P.A.', 'MPP': 'M.P.P.',
            'MPH': 'M.P.H.', 'MENG': 'M.Eng.', 'MF': 'M.F.',
            'MNR': 'M.N.R.', 'MSB': 'M.S.B.', 'MAT': 'M.A.T.',
            'CERT': 'Certificate', 'MINOR': 'minor',
            'MATRN': 'M.A.Trn.', 'MCOUN': 'M.Coun.', 'MHP': 'M.H.P.',
            'PSM': 'P.S.M.', 'EMPP': 'E.M.P.P.', 'MAIS': 'M.A.I.S.'
        }
        
        upper = degree.upper().replace('.', '')
        if upper in mappings:
            return mappings[upper]
        
        return degree

    def _fetch_deadline(self, url: str) -> str:
        """Fetch deadline information from program detail page using Selenium."""
        try:
            # Normalize URL if needed
            if not url.startswith('http'):
                return "N/A"
                
            self.driver.get(url)
            # Wait for content to render
            time.sleep(random.uniform(1.0, 2.0))
            
            # Use Selenium source
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            deadlines = []
            
            # Look for deadlines section
            deadlines_header = soup.find(id='deadlines')
            if deadlines_header:
                # Find the Views container after the deadlines header
                container = deadlines_header.find_next('div', class_='views-element-container')
                if container:
                    # Parse Views rows containing deadline info
                    rows = container.find_all('div', class_='views-row')
                    for row in rows:
                        # Requirement: Capture ALL content, no truncation
                        full_text = row.get_text().strip()
                        # Clean up excessive whitespace but keep content
                        full_text = ' '.join(full_text.split())
                        if full_text:
                            deadlines.append(full_text)
                
                # Also check for tables (if not found in views)
                if not deadlines:
                    tables = deadlines_header.find_all_next('table', limit=2)
                    for table in tables:
                        rows = table.find_all('tr')
                        for row in rows:
                            cells = row.find_all(['th', 'td'])
                            if len(cells) >= 2:
                                term = cells[0].get_text().strip()
                                date = cells[1].get_text().strip()
                                if date and not date.lower().startswith(('term', 'deadline')):
                                    if term and term.lower() not in ('term', 'deadline type'):
                                        deadlines.append(f"{term}: {date}")
            
            if deadlines:
                # Join all unique deadlines with semicolon
                unique = list(dict.fromkeys(deadlines))
                return "; ".join(unique)
            
            # Fallback to text extraction from entire page
            text = soup.get_text()[:10000]
            return self._extract_deadline_from_text(text)
            
        except Exception as e:
            print(f"      ⚠️ Selenium error fetching deadline: {e}")
            return "N/A"

    def _extract_deadline_from_text(self, text: str) -> str:
        """Extract deadline from text content."""
        patterns = [
            r'(Priority|Final)\s+[Dd]eadline[:\s]*([A-Z][a-z]+ \d{1,2}(?:,? \d{4})?)',
            r'(Fall|Winter|Spring|Summer)[:\s]*([A-Z][a-z]+ \d{1,2}(?:,? \d{4})?)',
            r'(?:Application\s+)?[Dd]eadline[:\s]*([A-Z][a-z]+ \d{1,2}(?:,? \d{4})?)',
            r'(\d{1,2}/\d{1,2}/\d{2,4})',
        ]
        
        deadlines = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
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
        
        return "N/A"

    def _create_entry(self, name: str, url: str, deadline: str, college: str) -> Dict:
        """Create a result dictionary entry."""
        return {
            "学校代码": self.school_code,
            "学校名称": self.school_name,
            "项目名称": name,
            "学院/学习领域": college,
            "项目官网链接": url,
            "申请链接": self.apply_url,
            "项目opendate": "N/A",
            "项目deadline": deadline,
            "学生案例": "",
            "面试问题": ""
        }
