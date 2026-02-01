import requests
from bs4 import BeautifulSoup
from spiders.base_spider import BaseSpider
from urllib.parse import urljoin
import logging

class VirginiaSpider(BaseSpider):
    def __init__(self, headless: bool = True):
        super().__init__("virginia", headless)
        self.logger = logging.getLogger("virginia_spider")

    def run(self):
        self.logger.info("Starting scraping for University of Virginia")
        
        # We have two URLs to scrape
        urls = [
            ("https://records.ureg.virginia.edu/content.php?catoid=68&navoid=6160", False), # Graduate
            ("https://records.ureg.virginia.edu/content.php?catoid=68&navoid=6126", True)  # Certificates
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        for url, is_certificate in urls:
            try:
                self.logger.info(f"Fetching URL: {url}")
                response = requests.get(url, headers=headers, timeout=20)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Locate the main content container.
                # Usually in Acalog systems, it's td.block_content
                content_block = soup.find('td', class_='block_content')
                if not content_block:
                    self.logger.warning(f"Could not find td.block_content in {url}, trying body")
                    content_block = soup
                
                # Parsing logic:
                # Find all H2 headers which likely denote Schools (as per user/inspection).
                # The structure is flattened: Header -> Links -> Header -> Links
                
                # We will iterate through all children of content_block
                # Or find all headers and then traverse next_siblings
                
                # Let's try to find identifying headers first.
                # Confirmed from markdown: "Graduate School of Arts and Sciences" is H2.
                
                current_school = "University of Virginia" # Default
                
                # If we iterate children, we need to handle whitespace/navigable strings
                children = content_block.find_all(['h2', 'h3', 'a', 'strong', 'p'])
                
                # Better approach: Find all H2/H3 and process groups?
                # But links might be wrapped in P or just A.
                
                # Let's iterate all immediate children if possible, or flattened list.
                # Actually, find_all with recursive=True might mess up order if nested.
                # But typically Acalog is:
                # <h2>School</h2>
                # <p><a ...>Program</a> or <ul><li><a>...</a></li></ul></p>
                
                # Let's try to identify School Headers.
                # We'll treat any H2 or H3 containing "School" or "College" as a school header.
                
                # Current School defaults to "University of Virginia" if the section is Top-level.
                
                elements = content_block.select('h2, h3, a') # Select headers and links in document order
                
                for el in elements:
                    text = el.get_text(strip=True)
                    if not text:
                        continue
                    
                    if el.name in ['h2', 'h3']:
                        # Check if it looks like a school name
                        # "Graduate School of...", "School of..."
                        text_lower = text.lower()
                        if "school" in text_lower or "college" in text_lower or "department" in text_lower:
                            current_school = text
                            self.logger.info(f"Found School Section: {current_school}")
                        continue
                        
                    if el.name == 'a':
                        # Check if it's a program link
                        href = el.get('href')
                        if not href or 'preview_program.php' not in href:
                            continue
                            
                        program_name = text
                        
                        # Formatting
                        if is_certificate:
                            if not program_name.endswith("Certificates Offered"):
                                program_name = f"{program_name} - Certificates Offered"
                                
                        full_link = urljoin(url, href)
                        
                        item = self.create_result_template(program_name, full_link)
                        item['学院/学习领域'] = current_school
                        item['申请链接'] = self.university_info['apply_register_url']
                        
                        self.results.append(item)
                        
            except Exception as e:
                self.logger.error(f"Error processing {url}: {e}")
                
        return self.results
