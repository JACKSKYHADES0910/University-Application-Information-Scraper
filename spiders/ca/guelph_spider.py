import time
import re
import requests
from bs4 import BeautifulSoup
from spiders.base_spider import BaseSpider
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

class GuelphSpider(BaseSpider):
    def __init__(self, headless=True):
        super().__init__("guelph", headless=headless)
        self.target_urls = [
            "https://www.uoguelph.ca/programs/graduate",
            "https://www.uoguelph.ca/programs/certificate-and-diploma"
        ]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def _parse_deadline(self, soup):
        try:
            # Strategies to find deadline block
            # 1. H2/H3/H4 headers with "Deadline"
            headers = soup.find_all(lambda t: t.name in ['h2','h3','h4','h5','strong'] and 'application deadline' in t.get_text(strip=True).lower())
            
            if not headers:
                # 2. Check for "Application Deadlines:" in simple p/div tags
                headers = soup.find_all(lambda t: t.name in ['p','div'] and 'application deadline:' in t.get_text(strip=True).lower())
            
            if not headers:
                return "See Website"

            all_deadlines = []
            seen_text = set()

            for header in headers:
                header_text = header.get_text(strip=True)
                chunk = []
                
                # If header is a block (div/p) and has substantial content, rely on it
                full_block_text = header.parent.get_text(strip=True) if header.name not in ['p','div'] else header_text
                
                if len(full_block_text) < 500 and len(full_block_text) > len(header_text) + 5:
                    text = full_block_text.replace(header_text, "").strip()
                    if text and text not in seen_text:
                        chunk.append(text)
                        
                # Look at siblings
                curr = header.find_next_sibling() if header.name not in ['strong'] else header.parent.find_next_sibling()
                if not curr and header.name == 'strong': 
                    curr = header.parent.find_next_sibling()

                count = 0
                while curr and count < 8:
                    if curr.name in ['h1','h2','h3','h4','h5', 'section', 'footer'] or 'contact' in curr.get_text(strip=True).lower():
                        break
                    
                    t = curr.get_text(strip=True)
                    # Filter out Program Title if it starts the line (common in descriptions)
                    if count == 0 and len(t) < 50 and any(w in t for w in ['MSc', 'PhD', 'Master', 'Doctor']):
                        pass # Valid deadline related text most likely
                    
                    if t:
                        if 'entry' in t.lower() or 'deadline' in t.lower() or any(m in t.lower() for m in ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december', 'summer', 'fall', 'winter', 'spring', 'ongoing']):
                             chunk.append(t)
                    
                    curr = curr.find_next_sibling()
                    count += 1
                
                if chunk:
                    combined = f"{header_text} {' '.join(chunk)}"
                    # Cleanup Program Name if it appears?
                    # Hard without knowing program name here, but acceptable.
                    if combined not in seen_text:
                        all_deadlines.append(combined)
                        seen_text.add(combined)

            if not all_deadlines:
                return "See Website"
            
            final_text = " | ".join(all_deadlines)
            return re.sub(r'\s+', ' ', final_text).strip()[:1000]

        except Exception:
            return "See Website"

    def _get_college(self, soup):
        try:
            college_tag = soup.find(string=re.compile("College:"))
            if college_tag:
                 text = college_tag.parent.get_text(strip=True)
                 return text.replace("College:", "").strip()
            return "University of Guelph"
        except:
            return "University of Guelph"

    def _get_degrees(self, soup, tile_text, title):
        degrees = []
        try:
            # 1. Detail Page "Degrees:" label (Relaxed regex)
            deg_node = soup.find(string=re.compile(r"Degrees:"))
            if deg_node:
                parent = deg_node.parent
                full_text = parent.get_text(strip=True)
                # "Degrees: GDip, MPAcc"
                if ":" in full_text:
                    clean = full_text.split(":", 1)[1]
                    degrees = [d.strip() for d in clean.split(",") if d.strip()]
            
            # 2. Extract from Tile Text if Detail failed
            if not degrees and tile_text:
                remainder = tile_text.replace(title, "").strip()
                tokens = remainder.split()
                # Exclude "Graduate" now
                exclude = ["Thesis-based", "Course-based", "Collaborative", "Specialization", "Diploma", "Graduate"] 
                
                possible = []
                for t in tokens:
                    t_clean = t.replace(",", "").strip()
                    if not t_clean: continue
                    if t_clean in exclude or "based" in t_clean: continue
                    if t_clean[0].isupper() and len(t_clean) < 10:
                        possible.append(t_clean)
                
                if possible:
                    degrees = possible

            # 3. Fallback: Check Headers
            if not degrees:
                headers = soup.find_all(lambda t: t.name in ['h4','strong'] and 'application deadline' in t.get_text(strip=True).lower())
                found_degs = set()
                for h in headers:
                    txt = h.get_text(strip=True)
                    before = txt.split("Application")[0]
                    parts = before.split(",")
                    for p in parts:
                        p = p.strip()
                        if p and p.lower() not in ["application", "deadline"]:
                            found_degs.add(p)
                if found_degs:
                    degrees = list(found_degs)

        except Exception:
            pass
            
        return degrees

    def fetch_detail_requests(self, item):
        link = item['link']
        results = []
        try:
            resp = requests.get(link, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                deadline = self._parse_deadline(soup)
                college = self._get_college(soup)
                degrees = self._get_degrees(soup, item.get('tile_text', ''), item.get('original_name', ''))
                
                if degrees:
                    for deg in degrees:
                        # Clean degree
                        d = deg.strip()
                        if not d: continue
                        
                        # Fix: Don't append if degree is already in name
                        full_name = f"{item['original_name']} - {d}"
                        
                        results.append({
                            "program_name": full_name,
                            "faculty": college,
                            "deadline": deadline,
                            "link": link
                        })
                else:
                     results.append({
                        "program_name": item['original_name'],
                        "faculty": college,
                        "deadline": deadline,
                        "link": link
                    })
            else:
                 results.append({
                    "program_name": item['original_name'],
                    "faculty": "Error",
                    "deadline": f"Error: {resp.status_code}",
                    "link": link
                })
        except Exception as e:
             results.append({
                "program_name": item['original_name'],
                "faculty": "Error",
                "deadline": f"Error: {e}",
                "link": link
            })
        return results

    def run(self):
        unique_links = {}
        
        for url in self.target_urls:
            print(f"Fetching list: {url}")
            try:
                resp = requests.get(url, headers=self.headers, timeout=15)
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                titles = soup.find_all("div", class_=lambda x: x and 'uofg-card-title' in x)
                print(f"Found {len(titles)} programs on {url}")
                
                for t in titles:
                    str_name = t.get_text(strip=True)
                    link_tag = t.find_parent("a")
                    if link_tag and link_tag.get('href'):
                        href = link_tag.get('href')
                        if href.startswith("/"):
                            href = "https://www.uoguelph.ca" + href
                        
                        # Grab full tile text for degree extraction
                        tile_text = link_tag.get_text(separator=' ', strip=True)

                        if href not in unique_links:
                            unique_links[href] = {
                                "original_name": str_name,
                                "link": href,
                                "tile_text": tile_text
                            }
            except Exception as e:
                print(f"Error scraping list {url}: {e}")

        print(f"Total unique programs: {len(unique_links)}")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total} | {task.fields[status]}"),
            TimeRemainingColumn(),
        ) as progress:
            
            task = progress.add_task("[cyan]Processing Details...", total=len(unique_links), status="Init")
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_item = {executor.submit(self.fetch_detail_requests, item): item for item in unique_links.values()}
                
                for future in as_completed(future_to_item):
                    try:
                        extracted_list = future.result()
                        for data in extracted_list:
                            item_template = self.create_result_template(data['program_name'], data['link'])
                            item_template.update({
                               "学院/学习领域": data['faculty'],
                               "项目deadline": data['deadline'],
                               "申请链接": "https://www.ouac.on.ca/apply/guelphgrad/en_CA/user/login"
                            })
                            self.results.append(item_template)
                        progress.update(task, status="OK")
                    except Exception as e:
                        progress.update(task, status="Fail")
                    
                    progress.advance(task)
        
        self.close()
        return self.results
