from spiders.base_spider import BaseSpider
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException
import time
import re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

class ManitobaSpider(BaseSpider):
    def __init__(self, headless=True):
        super().__init__("manitoba", headless=headless)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def _parse_deadline_table(self, soup):
        """
        Parses the deadline table into a readable string format.
        """
        deadlines = []
        
        # Look for the Application deadlines section
        # Use regex for more flexibility in finding the header
        deadline_header = soup.find(lambda tag: tag.name in ["h2", "h3"] and "Application deadlines" in tag.get_text())
        
        if not deadline_header:
            return "See Website"

        # Start traversing siblings
        current_category = "General"
        sibling = deadline_header.find_next_sibling()
        
        while sibling:
            # SAFETY BREAK: specific known following headers or just too far
            if sibling.name in ["h2", "h3", "div"] and any(x in sibling.get_text() for x in ["Application fee", "Unofficial copies", "Letters", "Biographical"]):
                 # "Application fee" usually starts the next section or is part of requirements
                 # If we hit another H2/H3 that isn't sub-section, we probably stop.
                 # Actually, looking at the provided image/HTML, H3 is "Application deadlines". H4 is "Canadian...", H4 is "International..."
                 # So we should break on H2 or H3 that is NOT related to deadlines.
                 pass

            if sibling.name in ["h2", "h3"] and "Application deadlines" not in sibling.get_text():
                 break
            
            # Detect Category (H4, Strong, P)
            text = sibling.get_text(strip=True)
            if not text:
                sibling = sibling.find_next_sibling()
                continue
                
            if sibling.name in ["h4", "h5"] or (sibling.name == "p" and sibling.find("strong")):
                if "Canadian" in text or "International" in text:
                    current_category = text.replace(":", "").strip()
            
            # Parse Table
            if sibling.name == "table":
                rows = sibling.find_all("tr")
                for row in rows:
                    cols = row.find_all(["th", "td"])
                    cols_text = [c.get_text(strip=True) for c in cols]
                    
                    if len(cols_text) >= 2:
                        term = cols_text[0]
                        date = cols_text[-1]
                        
                        # Skip header rows
                        if "Term" in term or "Annual" in date:
                            continue
                            
                        deadlines.append(f"{current_category} - {term}: {date}")
                        
            # Parse Lists (sometimes they use lists instead of tables)
            elif sibling.name == "ul":
                 for li in sibling.find_all("li"):
                     li_text = li.get_text(strip=True)
                     deadlines.append(f"{current_category}: {li_text}")

            sibling = sibling.find_next_sibling()
            
        if not deadlines:
            return "See Website"
            
        return "; ".join(deadlines)

    def parse_detail(self, link, program_name, faculty):
        """
        Fetches and parses a detail page.
        """
        try:
            self.driver.get(link)
            # Wait for content to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "main"))
            )
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Extract Deadline
            deadline = self._parse_deadline_table(soup)
            
            # Clean up deadline text
            deadline = re.sub(r'\s+', ' ', deadline).strip()

            return {
                "program_name": program_name,
                "faculty": faculty,
                "deadline": deadline,
                "link": link
            }

        except Exception as e:
            print(f"Error parsing {link}: {e}")
            return {
                "program_name": program_name,
                "faculty": faculty,
                "deadline": "Error",
                "link": link
            }

    def run(self):
        # 1. Load Main List
        self.driver.set_page_load_timeout(60)
        self.driver.get(self.list_url)
        time.sleep(5) # Wait for Atomic components to hydrate
        
        # 2. Handle "Load more results"
        while True:
            try:
                # Use JS to find and click the button inside Shadow DOM
                clicked = self.driver.execute_script("""
                    const loadMore = document.querySelector('atomic-load-more-results');
                    if (!loadMore || !loadMore.shadowRoot) return false;
                    const btn = loadMore.shadowRoot.querySelector('button');
                    if (btn && !btn.disabled) {
                        btn.scrollIntoView({behavior: 'smooth', block: 'center'});
                        btn.click();
                        return true;
                    }
                    return false;
                """)
                
                if clicked:
                    print("Clicked 'Load more results' (JS)...")
                    time.sleep(3) # Wait for content to load
                    
                    # Optional: Check status text to see progress
                    status = self.driver.execute_script("""
                        const status = document.querySelector('atomic-query-summary');
                        return status && status.shadowRoot ? status.shadowRoot.textContent : '';
                    """)
                    print(f"Status: {status}")
                else:
                    print("No more clickable 'Load more' buttons found.")
                    break
                
            except Exception as e:
                print(f"Error clicking load more: {e}")
                break

        # 3. Extract Program List using JS (Shadow DOM traversal)
        print("Extracting programs from Shadow DOM...")
        # 3. Extract Program List using JS (Shadow DOM traversal)
        print("Extracting programs from Shadow DOM...")
        script_result = self.driver.execute_script("""
            const logs = [];
            const items = [];
            const resultLists = document.querySelectorAll('atomic-result-list');
            logs.push(`Found ${resultLists.length} atomic-result-list elements`);
            
            resultLists.forEach((list, listIndex) => {
                if (!list.shadowRoot) {
                    logs.push(`List ${listIndex} has no shadowRoot`);
                    return;
                }
                
                const results = list.shadowRoot.querySelectorAll('atomic-result');
                logs.push(`List ${listIndex} has ${results.length} atomic-result elements`);
                
                results.forEach((res, index) => {
                    if (!res.shadowRoot) return;
                    
                    // Title & Link
                    // Try finding link wrapper first
                    const linkWrapper = res.shadowRoot.querySelector('atomic-result-link');
                    let linkEl = null;

                    if (linkWrapper) {
                        linkEl = linkWrapper.querySelector('a[href]');
                        if (!linkEl && linkWrapper.shadowRoot) {
                            linkEl = linkWrapper.shadowRoot.querySelector('a[href]');
                        }
                    }
                    
                    if (!linkEl) {
                        linkEl = res.shadowRoot.querySelector('a[href]');
                    }

                    const titleEl = res.shadowRoot.querySelector('atomic-result-text[field="title"]');
                    const facEl = res.shadowRoot.querySelector('atomic-result-multi-value-text[field="um__pos_faculty_college_school"]');
                    
                    if (linkEl && titleEl) {
                        let name = titleEl.innerText || titleEl.textContent;
                        name = name.split('|')[0].trim();
                        
                        let faculty = "Faculty of Graduate and Postdoctoral Studies";
                        if (facEl) {
                            // Try Shadow DOM list first
                            let facText = "";
                            if (facEl.shadowRoot) {
                                const items = facEl.shadowRoot.querySelectorAll('li[part="result-multi-value-text-value"]');
                                const faculties = [];
                                items.forEach(item => {
                                    const text = item.textContent.trim();
                                    if (text && !text.includes('more...')) {
                                        faculties.push(text);
                                    }
                                });
                                if (faculties.length > 0) {
                                    facText = faculties.join(', ');
                                }
                            }
                            
                            // Fallback to text content if Shadow DOM extraction failed
                            if (!facText) {
                                // innerText might contain newlines or "more..." which we want to clean
                                let rawText = facEl.innerText || facEl.textContent;
                                if (rawText) {
                                     // Remove "more..." if present at the end
                                     rawText = rawText.replace('more...', '').trim();
                                     // Replace newlines causing issues with comma
                                     facText = rawText.replace(new RegExp('[\\n\\r]+', 'g'), ', ').replace(new RegExp('\\s+', 'g'), ' ').trim();
                                }
                            }
                            
                            if (facText && facText.trim()) {
                                faculty = facText;
                            }
                        }
                        
                        items.push({
                            name: name,
                            link: linkEl.href,
                            faculty: faculty.trim(),
                            listIndex: listIndex
                        });
                    } else {
                         // Only log first 5 errors to avoid spam
                         if (items.filter(i => i.error).length < 5) {
                             items.push({
                                 error: true,
                                 reason: !linkEl ? "No Link" : "No Title",
                                 listIndex: listIndex
                             });
                         }
                    }
                });
            });
            return {items: items, logs: logs};
        """)
        
        program_items = script_result['items']
        logs = script_result['logs']
        for log in logs:
            print(f"[JS Code]: {log}")

        # Filter out errors
        valid_items = [p for p in program_items if "error" not in p]
        
        print(f"Total valid items from JS: {len(valid_items)}")
        if valid_items:
            print(f"Sample item 0: {valid_items[0]}")
            if len(valid_items) > 1:
                print(f"Sample item 1: {valid_items[1]}")

        errors = [p for p in program_items if "error" in p]
        if errors:
            print(f"Skipped {len(errors)} items. Reasons: {[e['reason'] for e in errors[:5]]}")



        # Deduplicate
        unique_items = {p['link']: p for p in valid_items}.values()
        print(f"Extracted {len(unique_items)} unique programs.")
        
        # 4. Visit Detail Pages
        print("🚀 Starting threaded extraction of details...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total} | {task.fields[status]}"),
            TimeRemainingColumn(),
        ) as progress:
            
            task = progress.add_task("[cyan]Processing Details...", total=len(unique_items), status="Init")
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_item = {}
                for item in unique_items:
                    future = executor.submit(self.fetch_deadline_requests, item)
                    future_to_item[future] = item
                
                for future in as_completed(future_to_item):
                    try:
                        result = future.result()
                        # Add to results
                        data_item = self.create_result_template(result["program_name"], result["link"])
                        data_item.update({
                           "学院/学习领域": result["faculty"],
                           "项目deadline": result["deadline"],
                           "申请链接": "https://applygrad.umanitoba.ca/apply/" 
                        })
                        self.results.append(data_item)
                        progress.update(task, status="OK")
                    except Exception as e:
                        print(f"Failed item: {e}")
                        progress.update(task, status="Fail")
                    
                    progress.advance(task)

        self.close()
        return self.results

    def fetch_deadline_requests(self, item):
        """
        Helper to fetch deadline using requests (faster than Selenium switch).
        """
        import requests
        try:
            resp = requests.get(item['link'], headers=self.headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                deadline = self._parse_deadline_table(soup)
                # Cleanup
                deadline = re.sub(r'\s+', ' ', deadline).strip()

                # Try to extract specific faculty from detail page
                # Look for "Faculty of ..." or "School of ..."
                # Common pattern: Breadcrumbs or sidebar links
                specific_faculty = None
                
                # Check for "Faculty/School" label
                label = soup.find(lambda tag: tag.name in ["strong", "b", "h3", "h4"] and "Faculty" in tag.get_text())
                if label:
                    # Logic 1: The text is in the next sibling or parent's text
                    # Case: <strong>Faculty:</strong> Agricultural and Food Sciences
                    parent_text = label.parent.get_text(strip=True)
                    if ":" in parent_text:
                        parts = parent_text.split(":", 1)
                        if len(parts) > 1 and len(parts[1].strip()) > 3:
                            specific_faculty = parts[1].strip()
                
                if not specific_faculty:
                    # Logic 2: Search for links with specific faculty names (excluding the generic one)
                    fac_link = soup.find("a", string=re.compile(r"(Faculty|School) of (?!Graduate)"))
                    if fac_link:
                        specific_faculty = fac_link.get_text(strip=True)

                if specific_faculty:
                    item['faculty'] = specific_faculty

            else:
                deadline = "Error: " + str(resp.status_code)
        except Exception as e:
            deadline = f"Error: {e}"
            
        return {
            "program_name": item['name'],
            "faculty": item['faculty'],
            "deadline": deadline,
            "link": item['link']
        }

if __name__ == "__main__":
    spider = ManitobaSpider(headless=False)
    spider.run()
