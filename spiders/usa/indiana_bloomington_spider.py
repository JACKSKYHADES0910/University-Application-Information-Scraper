# -*- coding: utf-8 -*-
import time
import re
from typing import List, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

from spiders.base_spider import BaseSpider

class IndianaBloomingtonSpider(BaseSpider):
    def __init__(self, headless: bool = True):
        super().__init__("indiana_bloomington", headless)

    def run(self) -> List[Dict]:
        from rich.live import Live
        from rich.table import Table
        from rich.panel import Panel
        from rich.console import Console
        from rich import box
        
        self.driver.get(self.list_url)
        
        # Categories to scrape
        categories = [
            "Certificates: Graduate",
            "Diplomas: Artist and Performer",
            "Doctoral and professional degrees",
            "Master's degrees",
            "Post-master's/Specialist degrees",
            "Accelerated degrees"
        ]
        
        all_data = []
        total_collected = 0
        
        # Status variables for UI
        current_category = "Initializing..."
        current_page = 0
        category_count = 0
        status_msg = "Starting..."
        
        def generate_table():
            table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
            table.add_column("Current Category", style="cyan", width=40)
            table.add_column("Page", style="yellow", justify="center", width=10)
            table.add_column("Category Found", style="green", justify="center", width=15)
            table.add_column("Total Found", style="bold green", justify="center", width=15)
            table.add_column("Status", style="white")
            
            table.add_row(
                current_category,
                str(current_page),
                str(category_count),
                str(total_collected),
                status_msg
            )
            return Panel(table, title="[bold blue]Indiana University Bloomington Spider[/]", border_style="blue")

        with Live(generate_table(), refresh_per_second=4) as live:
            for category in categories:
                current_category = category
                current_page = 0
                category_count = 0
                status_msg = "Switching category..."
                live.update(generate_table())
                
                try:
                    # Refresh page for each category
                    self.driver.get(self.list_url)
                    time.sleep(1) # Short wait

                    # 1. Select the category
                    status_msg = "Selecting filter..."
                    live.update(generate_table())
                    
                    select_element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.ID, "program_type"))
                    )
                    select = Select(select_element)
                    select.select_by_visible_text(category)
                    
                    # 2. Click Apply Filters
                    status_msg = "Applying filters..."
                    live.update(generate_table())
                    
                    apply_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Apply filters')]")
                    self.driver.execute_script("arguments[0].click();", apply_btn)
                    
                    # 3. Wait for results
                    for i in range(5, 0, -1):
                        status_msg = f"Waiting for results... ({i}s)"
                        live.update(generate_table())
                        time.sleep(1)

                    page_count = 1
                    while True:
                        current_page = page_count
                        status_msg = f"Scanning page {page_count}..."
                        live.update(generate_table())
                        
                        # 4. Extract data
                        results = self._extract_page_data()
                        count_on_page = len(results)
                        
                        if count_on_page > 0:
                            all_data.extend(results)
                            category_count += count_on_page
                            total_collected += count_on_page
                            status_msg = f"Found {count_on_page} items"
                            live.update(generate_table())
                        
                        # 5. Pagination
                        status_msg = "Checking pagination..."
                        live.update(generate_table())
                        
                        next_page_found = False
                        try:
                            # Try standard 'Next' button
                            next_btn = self.driver.find_element(By.ID, "pagination-next")
                            
                            if next_btn.get_attribute("aria-disabled") == "true" or "disabled" in next_btn.get_attribute("class"):
                                break
                            
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                            time.sleep(0.5)
                            self.driver.execute_script("arguments[0].click();", next_btn)
                            next_page_found = True
                            
                        except NoSuchElementException:
                            # Fallback: Try numbered page link
                            next_page_num = page_count + 1
                            try:
                                next_page_btn = self.driver.find_element(By.ID, f"pagination-{next_page_num}")
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_page_btn)
                                time.sleep(0.5)
                                self.driver.execute_script("arguments[0].click();", next_page_btn)
                                next_page_found = True
                            except NoSuchElementException:
                                 pass
                        
                        if next_page_found:
                            # Wait for valid load
                            status_msg = "Loading next page..."
                            live.update(generate_table())
                            time.sleep(3)
                            page_count += 1
                        else:
                             status_msg = "End of category"
                             live.update(generate_table())
                             time.sleep(1)
                             break

                except Exception as e:
                    status_msg = f"[red]Error: {str(e)[:50]}...[/]"
                    live.update(generate_table())
                    time.sleep(2)
                    self.driver.get(self.list_url)
                    time.sleep(2)

        self.results = all_data
        self.print_summary()
        return self.results

    def _extract_page_data(self) -> List[Dict]:
        results = []
        cards = self.driver.find_elements(By.CSS_SELECTOR, ".rvt-card")
        
        for card in cards:
            try:
                # Program Name
                title_elem = card.find_element(By.CSS_SELECTOR, ".rvt-card__title a")
                program_raw = title_elem.text.strip()
                program_link = title_elem.get_attribute("href")
                
                # Degree Name (Eyebrow)
                degree_raw = ""
                try:
                    degree_elem = card.find_element(By.CSS_SELECTOR, ".rvt-card__eyebrow")
                    degree_raw = degree_elem.text.strip()
                except NoSuchElementException:
                    pass

                # School Info
                school_raw = ""
                try:
                    # The school info is in a div with .rvt-m-left-sm inside .rvt-card__content
                    # It might contain <br> tags which selenium .text handles by newlines usually
                    school_elem = card.find_element(By.CSS_SELECTOR, ".rvt-card__content div.rvt-m-left-sm")
                    school_raw = school_elem.text.strip().replace("\n", ", ")
                except NoSuchElementException:
                    pass
                
                # Tags (optional, but might be useful or requested implicitly as "info")
                # User example didn't explicitly ask for tags in columns, but "Society, Community, Culture Global Perspectives" was in the example text block.
                # The user request for P3 (Project 3?) example: 
                # [Doctor of Philosophy at IU Bloomington 
                # African American & African Diaspora Studies
                # College of Arts and Sciences
                # Graduate School
                # Society, Community, Culture Global Perspectives]
                # It seems he wants to combine things.
                
                # Construct Entry
                
                # Logic: "Program Name" = "African American..." + " - " + "Doctor of Philosophy" (cleaned)
                clean_degree = re.sub(r'(?i)\s+at iu bloomington', '', degree_raw).strip()
                final_program_name = f"{program_raw} - {clean_degree}" if clean_degree else program_raw
                
                # Logic: "School" = Combined school info
                # The .text extraction already handles newline -> join, but let's ensure comma separation
                # school_raw is likely "College of ... \n Graduate School" -> "College of ..., Graduate School"
                
                item = self.create_result_template(final_program_name, program_link)
                item["学院/学习领域"] = school_raw
                
                # Use the configured apply link
                item["申请链接"] = self.university_info["apply_register_url"]
                
                results.append(item)
                
            except Exception as e:
                print(f"Error extracting card: {e}")
                continue
                
        return results
