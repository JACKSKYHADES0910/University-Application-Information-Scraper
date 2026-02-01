from spiders.base_spider import BaseSpider
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

class CalgarySpider(BaseSpider):

    def __init__(self, headless=True):
        super().__init__("calgary", headless=headless)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        # Faculty mapping extracted from filter
        self.faculties = [
            "Cumming School of Medicine",
            "Faculty of Arts",
            "Faculty of Arts (Fine Arts)",
            "Faculty of Graduate Studies",
            "Faculty of Kinesiology",
            "Faculty of Law",
            "Faculty of Nursing",
            "Faculty of Science",
            "Faculty of Social Work",
            "Faculty of Veterinary Medicine",
            "Haskayne School of Business",
            "School of Architecture, Planning and Landscape (SAPL)",
            "School of Public Policy",
            "Schulich School of Engineering",
            "Werklund School of Education"
        ]

    def parse_detail(self, link):
        """Fetches and parses a program detail page."""
        try:
            resp = self.session.get(link, timeout=15)
            if resp.status_code != 200:
                return None
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # ===== 1. EXTRACT FACULTY =====
            faculty = "Faculty of Graduate Studies"  # Default 
            
            # Look for faculty in breadcrumb or page metadata
            breadcrumb = soup.select('.breadcrumb a, .breadcrumb__item a')
            for crumb in breadcrumb:
                text = crumb.get_text(strip=True)
                if 'Faculty' in text or 'School' in text:
                    faculty = text
                    break
            
            # Alternative: Look for "Home Faculty" or similar label
            if faculty == "Faculty of Graduate Studies":
                faculty_label = soup.find(string=lambda s: s and 'Home Faculty' in s)
                if faculty_label:
                    parent = faculty_label.find_parent(['p', 'div', 'li'])
                    if parent:
                        faculty_text = parent.get_text(strip=True).replace('Home Faculty:', '').replace('Home Faculty', '').strip()
                        if faculty_text:
                            faculty = faculty_text
            
            # Check page sidebar or info boxes
            if faculty == "Faculty of Graduate Studies":
                info_boxes = soup.select('.field-name-field-home-faculty, .program-details, .sidebar')
                for box in info_boxes:
                    text = box.get_text(strip=True)
                    for f in self.faculties:
                        if f in text:
                            faculty = f
                            break
                    if faculty != "Faculty of Graduate Studies":
                        break
            
            # ===== 2. EXTRACT DEADLINE =====
            deadline_parts = []
            
            # Look for deadline section
            deadline_keywords = ['Application deadlines', 'application deadline', 'Admission deadlines', 'Deadlines', 'Deadline']
            deadline_section = None
            
            for keyword in deadline_keywords:
                deadline_section = soup.find(['h2', 'h3', 'h4'], string=lambda s: s and keyword.lower() in s.lower())
                if deadline_section:
                    break
            
            if deadline_section:
                # Find the parent section that contains deadline info
                parent = deadline_section.find_parent(['div', 'section'])
                if not parent:
                    parent = deadline_section.find_next_sibling()
                
                if parent:
                    # Look for tables with deadline info
                    tables = parent.find_all('table')
                    for table in tables:
                        rows = table.find_all('tr')
                        for row in rows:
                            cells = row.find_all(['td', 'th'])
                            row_text = ' '.join([cell.get_text(' ', strip=True) for cell in cells])
                            if row_text and len(row_text) > 10:
                                if any(kw in row_text for kw in ['September', 'January', 'May', 'April', 'June', 'August', 'December', 
                                                                   'International', 'Domestic', 'Canadian', 'admission', 'student']):
                                    deadline_parts.append(row_text)
                    
                    # Also check for paragraphs with deadline info
                    paragraphs = parent.find_all(['p', 'div', 'li'])
                    for p in paragraphs:
                        text = p.get_text(' ', strip=True)
                        # Broader keywords based on debug findings
                        if text and any(kw in text for kw in ['For admission on', 'Deadline', 'International', 'Canadian', 'Domestic']):
                            # Clean up and add
                            text = text.replace('\n', ' ').strip()
                            if len(text) > 10 and len(text) < 300: # Increased limit slightly
                                deadline_parts.append(text)
            
            # Format deadline
            if deadline_parts:
                # Remove duplicates
                unique_deadlines = []
                seen = set()
                for dp in deadline_parts:
                    dp_clean = dp.strip()
                    if dp_clean and dp_clean not in seen:
                        # Simple dup check
                        seen.add(dp_clean)
                        unique_deadlines.append(dp_clean)
                
                deadline = '\n\n'.join(unique_deadlines)
            else:
                deadline = "N/A"
            
            # Limit length
            if len(deadline) > 600:
                deadline = deadline[:600] + "..."
            
            return {
                "faculty": faculty,
                "deadline": deadline,
                "link": link
            }

        except Exception as e:
            print(f"Error parsing {link}: {e}")
            return None

    def run(self):
        # Step 1: Load all programs
        print("\n📋 Loading all programs...")
        self.driver.get(self.list_url)
        time.sleep(3)
        
        # Click "Show all" button
        try:
            show_all_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Show all')]"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", show_all_btn)
            time.sleep(1)
            self.driver.execute_script("arguments[0].click();", show_all_btn)
            print("  ✓ Clicked 'Show all' button")
            time.sleep(3)
        except TimeoutException:
            print("  ! 'Show all' button not found, proceeding with current view")
        
        # Step 2: Extract all program links and names
        program_items = []  # List of tuples (link, name)
        try:
            # Get all program links
            elements = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/future-students/explore-programs/"]')
            for el in elements:
                href = el.get_attribute('href')
                name = el.text.strip()
                
                # Only keep the part after the degree level (e.g., "Anthropology - MA - Thesis")
                # The page shows "Master of Arts" on top, then "Anthropology - MA - Thesis" as link text
                if href and name and '/explore-programs/' in href:
                    # Filter out navigation/header links
                    if 'Explore programs' not in name and len(name) > 5:
                        program_items.append((href, name))
            
            # Deduplicate by link
            seen_links = set()
            unique_items = []
            for link, name in program_items:
                if link not in seen_links:
                    seen_links.add(link)
                    unique_items.append((link, name))
            program_items = unique_items
            
            print(f"  ✓ Found {len(program_items)} programs")
            
        except Exception as e:
            print(f"  ✗ Error extracting list: {e}")
        
        self.close()
        
        # Step 3: Concurrent processing of detail pages
        print("\n🚀 Starting concurrent extraction...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total} | {task.fields[status]}"),
            TimeRemainingColumn(),
        ) as progress:
            
            task = progress.add_task("[cyan]Processing programs...", total=len(program_items), status="Init")
            
            with ThreadPoolExecutor(max_workers=12) as executor:
                future_to_item = {
                    executor.submit(self.parse_detail, link): (link, name) 
                    for link, name in program_items
                }
                
                for future in as_completed(future_to_item):
                    link, name = future_to_item[future]
                    try:
                        data = future.result()
                        if data:
                            # Create result
                            item = self.create_result_template(name, link)
                            item.update({
                                "学院/学习领域": data["faculty"],
                                "申请链接": self.university_info['apply_url'],
                                "项目deadline": data["deadline"]
                            })
                            self.results.append(item)
                            progress.update(task, status="✓")
                        else:
                            progress.update(task, status="✗")
                        
                        progress.advance(task)
                    except Exception as e:
                        progress.update(task, status=f"✗ {str(e)[:20]}")
                        progress.advance(task)
        
        return self.results

if __name__ == "__main__":
    spider = CalgarySpider(headless=False)
    results = spider.run()
    print(f"\n✅ Extracted {len(results)} programs")
