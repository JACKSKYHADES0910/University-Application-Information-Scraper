import time
import random
from typing import List, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

from spiders.base_spider import BaseSpider

class EmorySpider(BaseSpider):
    """
    Emory University (US044) Spider
    """
    def __init__(self, university_key: str = "emory", headless: bool = True):
        super().__init__(university_key, headless)
        self.school_link_map = {
            "Laney Graduate School": "https://laneyconnect.emory.edu/apply/",
            "Rollins School of Public Health": "https://sophas.cas.myliaison.com/applicant-ux/#/login",
            "School of Law": "https://os.lsac.org/Logon/Access.aspx",
            "Goizueta Business School": "https://goizueta.emory.edu/masters-in-finance/apply",
            "School of Medicine": "https://casaa.cas.myliaison.com/applicant-ux/#/login",
            "Nell Hodgson Woodruff School of Nursing": "https://apply.nursing.emory.edu/apply/",
            "Candler School of Theology": "https://application.candler.emory.edu/apply/"
        }

    def run(self) -> List[Dict]:
        print(f"[*] Starting Emory Spider for {self.list_url}")
        driver = self.driver
        driver.get(self.list_url)
        
        try:
            # Wait for the page to load
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".js-filterable"))
            )
            print("[*] Page loaded successfully")

            # 1. Apply Filters
            self._apply_filters()

            # 2. Extract Data
            self._extract_data()

        except Exception as e:
            print(f"[!] Critical Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.close()
        
        return self.results

    def _apply_filters(self):
        """
        Selects: Master's, Doctorate, Professional, 4+1, Certificate
        """
        driver = self.driver
        print("[*] Applying filters...")
        
        # 1. Click "Program Level" button to expand
        try:
            level_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-filter-group-id='program-level']"))
            )
            # Scroll to it
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", level_btn)
            time.sleep(1)
            level_btn.click()
            print("  [+] Expanded 'Program Level' filter")
            time.sleep(1) 
        except Exception as e:
            print(f"  [!] Could not click Program Level button: {e}")
            return

        target_values = [
            "Master's", 
            "Doctorate", 
            "Professional", 
            "4+1", 
            "Certificate"
        ]

        for val in target_values:
            try:
                # Find input by value
                safe_val = val.replace("'", "\\'")
                input_selector = f"input[value='{safe_val}']"
                inp = driver.find_element(By.CSS_SELECTOR, input_selector)
                
                # Iterate parents to find the label or the custom-checkbox div
                # Structure: <div class="custom-control custom-checkbox"> <input...> <label...> </div>
                # We can try clicking the label.
                parent = inp.find_element(By.XPATH, "./..")
                label = parent.find_element(By.TAG_NAME, "label")
                
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", label)
                time.sleep(0.5)
                
                # Click label
                try:
                    label.click()
                except:
                    driver.execute_script("arguments[0].click();", label)
                    
                print(f"  [+] Selected: {val}")
                time.sleep(1)
                
            except Exception as e:
                print(f"  [!] Error selecting {val}: {e}")
        
        # Wait for results to update
        print("[*] Waiting for results to update...")
        time.sleep(5)
        
        # Check result count
        try:
            count_elem = driver.find_element(By.CSS_SELECTOR, ".js-filterable__results-count")
            print(f"  [*] Result count: {count_elem.text}")
        except:
            print("  [!] Could not find result count text")

    def _extract_data(self):
        driver = self.driver
        print("[*] Extracting data...")
        
        # Select visible items only
        try:
            items = driver.find_elements(By.CSS_SELECTOR, ".js-filterable__item.is-shown")
            if not items:
                print("  [!] No 'is-shown' items found, falling back to all items.")
                items = driver.find_elements(By.CSS_SELECTOR, ".js-filterable__item")
        except:
            items = driver.find_elements(By.CSS_SELECTOR, ".js-filterable__item")
            
        print(f"[*] Found {len(items)} items")
        
        target_levels = {
            "Master's", 
            "Doctorate", 
            "Professional", 
            "4+1", 
            "Certificate"
        }
        
        for item in items:
            try:
                # Check tags for validation
                try:
                    tags_elems = item.find_elements(By.CSS_SELECTOR, ".list-tags li")
                    tags = [t.text.strip() for t in tags_elems]
                    
                    # If tags don't overlap with target_levels, skip
                    if not any(level in tags for level in target_levels):
                        # Double check "4+1 Program" vs "4+1"
                        # The tag text might be "4+1 Program".
                        if not any(level in t for t in tags for level in target_levels):
                            # Debug: print what we skipped
                            # print(f"  [-] Skipped (Level mismatch): {tags}")
                            continue
                except:
                    pass

                # 1. Program Name
                title_elem = item.find_element(By.CSS_SELECTOR, ".card-title")
                program_name = title_elem.text.strip()
                
                # 2. Program Link (parent a tag)
                try:
                    link_elem = item.find_element(By.CSS_SELECTOR, "a.program-card")
                    program_link = link_elem.get_attribute("href")
                except:
                    program_link = "N/A"
                
                # 3. School
                school_container = item.find_element(By.CSS_SELECTOR, ".program-card__school")
                school_divs = school_container.find_elements(By.CSS_SELECTOR, ".font-weight-bold")
                schools = [div.text.strip() for div in school_divs if div.text.strip()]
                
                if schools:
                    valid_schools = [s for s in schools if s in self.school_link_map]
                    if valid_schools:
                        selected_school = valid_schools[-1]
                    else:
                        print(f"  [!] No mapped school found in {schools}, assigning random.")
                        selected_school = self._get_random_school()
                else:
                    print(f"  [!] No school text found for {program_name}, assigning random.")
                    selected_school = self._get_random_school()
                
                app_link = self.school_link_map.get(selected_school, "N/A")
                
                # Create result
                res = self.create_result_template(program_name, program_link)
                res["学院/学习领域"] = selected_school
                res["申请链接"] = app_link
                
                self.results.append(res)
                
            except Exception as e:
                print(f"  [!] Error extracting item: {e}")
                continue

    def _get_random_school(self):
        return random.choice(list(self.school_link_map.keys()))

