# -*- coding: utf-8 -*-
"""
哈佛大学 (Harvard University) 爬虫模块
负责抓取 Harvard Graduate 项目信息

提取规则：
  - Phase 1: 从列表页 (Page 1-9) 获取所有大类及其详情页链接
  - Phase 2: 并发 (24线程) 处理每个大类：
      1. 直接访问大类详情页 (无需在列表页点击)
      2. 找到并展开 "Graduate" 折叠页
      3. 提取 "Graduate" 下的所有子项目 (Name, School, LearnMoreURL)
      4. 依次访问 LearnMoreURL，提取 Deadline
      5. 组合最终数据
"""

import sys
import time
import re
import concurrent.futures
from typing import List, Dict, Any, Tuple
from urllib.parse import urljoin

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.remote.webdriver import WebDriver

from spiders.base_spider import BaseSpider
from utils.progress import print_phase_start, print_phase_complete
from utils.selenium_utils import BrowserPool, safe_click
from config import PAGE_LOAD_WAIT, MAX_WORKERS

# 全局配置，允许外部覆盖
HARVARD_MAX_WORKERS = 24

def log(msg: str):
    """带刷新的打印函数，确保即时显示"""
    print(msg, flush=True)


class HarvardSpider(BaseSpider):
    """
    哈佛大学爬虫
    
    提取所有研究生项目的实际子项目信息
    """
    
    def __init__(self, headless: bool = True, max_workers: int = None):
        super().__init__("harvard", headless)
        self.max_workers = max_workers or HARVARD_MAX_WORKERS
        self.categories = []  # 存储大类信息
        self.programs_collected = []  # 存储最终项目
        self.browser_pool = None
    
    def run(self) -> List[Dict]:
        """
        执行完整的爬取流程
        """
        self.start_time = time.time()
        
        log(f"\n{'='*60}")
        log(f"🎓 开始爬取: {self.university_info['name_cn']}")
        log(f"📍 目标地址: {self.list_url}")
        log(f"{'='*60}\n")
        
        try:
            # Phase 1: 收集所有大类索引
            print_phase_start("Phase 1", "收集所有大类索引 (Pages 1-9)")
            self._collect_all_categories()
            print_phase_complete("Phase 1", len(self.categories))
            
            # Phase 2: 并发提取详情
            if self.categories:
                print_phase_start("Phase 2", "提取子项目详情 & Deadline", total=len(self.categories))
                self._extract_all_subprograms_concurrent()
                print_phase_complete("Phase 2", len(self.programs_collected))
            
            # 设置结果
            self.results = self.programs_collected
            
        except Exception as e:
            log(f"❌ 爬取过程中出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.browser_pool:
                self.browser_pool.close_all()
        
        self.print_summary()
        return self.results
    
    def _collect_all_categories(self):
        """Phase 1: 从所有分页收集大类索引信息"""
        total_pages = 9 
        
        for page_num in range(1, total_pages + 1):
            log(f"   📄 正在收集第 {page_num}/{total_pages} 页的大类...")
            self._collect_categories_from_page_url(page_num)
        
        log(f"   ✅ 共收集 {len(self.categories)} 个大类 (预期 ~134 个)")
    
    def _collect_categories_from_page_url(self, page_num: int):
        """直接访问指定页码的 URL 收集大类"""
        for attempt in range(3):
            try:
                # 构造带页码的 URL
                target_url = f"{self.list_url}&page={page_num}"
                self.driver.set_page_load_timeout(15) # 设置较短超时，防止卡死
                try:
                    self.driver.get(target_url)
                except TimeoutException:
                    pass
                
                # 恢复默认超时
                self.driver.set_page_load_timeout(60)
                
                try:
                    WebDriverWait(self.driver, 20).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.c-programs-item"))
                    )
                except TimeoutException:
                    if attempt < 2:
                        continue
                    log(f"   ⚠️ 第 {page_num} 页加载超时或无内容")
                    return

                # 临时降低隐式等待以加速查找不存在的元素
                self.driver.implicitly_wait(0.1)
                
                items = self.driver.find_elements(By.CSS_SELECTOR, "div.c-programs-item")
                
                count_on_page = 0
                for idx, item in enumerate(items):
                    try:
                        # 姓名
                        try:
                            name_elem = item.find_element(By.CSS_SELECTOR, "h2.c-programs-item__title")
                            name = name_elem.text.strip()
                        except NoSuchElementException:
                            # 尝试找任何 h2
                            try:
                                name = item.find_element(By.TAG_NAME, "h2").text.strip()
                            except:
                                continue

                        # 链接
                        url = None
                        try:
                            # 直接在 item 下找 a
                            link_elem = item.find_element(By.TAG_NAME, "a")
                            url = link_elem.get_attribute("href")
                        except NoSuchElementException:
                            pass
                            
                        if not name:
                            continue
                            
                        self.categories.append({
                            "name": name,
                            "url": url,
                            "page_num": page_num
                        })
                        count_on_page += 1
                    except Exception:
                        continue
                
                # 恢复隐式等待
                self.driver.implicitly_wait(5)
                
                # 成功收集，跳出重试
                return
                
            except Exception as e:
                log(f"   ⚠️ 收集第 {page_num} 页 (尝试 {attempt+1}/3) 出错: {e}")
                time.sleep(2)

    def _extract_all_subprograms_concurrent(self):
        """Phase 2: 使用 BrowserPool 并发提取详情"""
        total = len(self.categories)
        log(f"   📊 开始处理 {total} 个大类 (使用 {self.max_workers} 线程)...")
        
        self.browser_pool = BrowserPool(size=self.max_workers, headless=self.headless)
        self.browser_pool.initialize()
        
        extracted_count = 0
        current_done = 0
        
        # 使用 ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_cat = {
                executor.submit(self._process_single_category, cat): cat 
                for cat in self.categories
            }
            
            for future in concurrent.futures.as_completed(future_to_cat):
                try:
                    subprograms = future.result()
                    if subprograms:
                        self.programs_collected.extend(subprograms)
                        extracted_count += len(subprograms)
                except Exception as e:
                    pass
                
                current_done += 1
                if current_done % 1 == 0 or current_done == total:
                    print(f"   ... 进度: {current_done}/{total} 大类, 已获取 {extracted_count} 个子项目", end='\r')
        
        print("") 
        log(f"\n   ✅ 提取完成，共获取 {len(self.programs_collected)} 个子项目")

    def _process_single_category(self, category_info: Dict) -> List[Dict]:
        """
        在独立浏览器中处理单个大类
        """
        final_results = []
        name = category_info['name']
        cat_url = category_info.get('url')
        
        with self.browser_pool.get_browser() as browser:
            try:
                # --- Step 1: Open Detail Page ---
                # 设置较短超时，防止卡死
                browser.set_page_load_timeout(20)
                try:
                    if cat_url and "http" in cat_url:
                        browser.get(cat_url)
                    else:
                        # Fallback
                        slug = re.sub(r'[^a-z0-9\s-]', '', name.lower()).strip().replace(' ', '-')
                        fallback_url = f"https://www.harvard.edu/programs/{slug}/"
                        browser.get(fallback_url)
                except TimeoutException:
                    pass # 忽略加载超时，只要 DOM 稍微加载出来就行
                
                # 恢复默认超时
                browser.set_page_load_timeout(60)
                
                WebDriverWait(browser, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
                )

                # --- Step 2: Find "Graduate" Accordion ---
                basic_infos = []
                
                try:
                    # 等待一下 accordion 加载
                    WebDriverWait(browser, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".c-accordion__header"))
                    )
                    
                    headers = browser.find_elements(By.CSS_SELECTOR, ".c-accordion__header")
                    grad_header = None
                    for h in headers:
                        t = h.text.strip().lower()
                        # Strict match or ensure it starts with Graduate and not Undergraduate
                        if t == "graduate" or (t.startswith("graduate") and "undergraduate" not in t):
                            grad_header = h
                            break
                    
                    if grad_header:
                        # Expand if needed
                        is_expanded = grad_header.get_attribute("aria-expanded")
                        if is_expanded != "true":
                            safe_click(browser, grad_header)
                            time.sleep(1) # wait animation
                        
                        # Find content area
                        # 通常是紧邻的 sibling div with class c-accordion__content
                        try:
                            content_area = grad_header.find_element(By.XPATH, "following-sibling::div[contains(@class, 'c-accordion__content')]")
                        except:
                            # 尝试通过 aria-controls
                            controls_id = grad_header.get_attribute("aria-controls")
                            if controls_id:
                                content_area = browser.find_element(By.ID, controls_id)
                            else:
                                content_area = None
                        
                        if content_area:
                            basic_infos = self._extract_subprograms_from_content(content_area, name, browser)
                            
                except TimeoutException:
                    pass
                except Exception:
                    pass
                
                # --- Step 3: Visit Detail Pages for Deadline ---
                for program_name, school, url in basic_infos:
                    deadline = "N/A"
                    if url and url != "N/A" and url.startswith("http"):
                        try:
                            browser.get(url)
                            deadline = self._extract_deadline_from_page(browser)
                        except Exception:
                            deadline = "Error Fetching"
                    
                    # Construct Final Result
                    result = self.create_result_template(program_name, url)
                    result["学院/学习领域"] = school
                    result["项目deadline"] = deadline
                    
                    # Add hardcoded application link
                    result["申请链接"] = "https://apply.gsas.harvard.edu/account/register?r=/portal/apply_degree"
                    
                    final_results.append(result)

            except Exception as e:
                pass
                
        return final_results

    def _extract_subprograms_from_content(self, content_area, category_name, browser) -> List[Tuple[str, str, str]]:
        """从展开的内容区域提取子项目"""
        extracted = []
        try:
            # 查找所有子项目块
            blocks = content_area.find_elements(By.CSS_SELECTOR, ".c-programs-accordion-content__degree")
            if not blocks:
                blocks = content_area.find_elements(By.CSS_SELECTOR, ".c-programs-accordion-content__program")
            if not blocks:
                blocks = content_area.find_elements(By.CSS_SELECTOR, "div.c-programs-accordion-content > div")

            for block in blocks:
                try:
                    # Title
                    degree_title = ""
                    try:
                        title_el = block.find_element(By.CSS_SELECTOR, ".c-programs-accordion-content__degree__title")
                        degree_title = title_el.text.strip()
                    except:
                        try:
                            degree_title = block.find_element(By.TAG_NAME, "h3").text.strip()
                        except:
                            continue 

                    # School
                    school = "N/A"
                    try:
                        school_el = block.find_element(By.CSS_SELECTOR, ".c-programs-accordion-content__degree__subtitle")
                        school = school_el.text.strip()
                    except:
                        pass
                        
                    # Learn More URL
                    learn_more_url = "N/A"
                    try:
                        potential_links = []
                        
                        # 1. Check sibling container (Most likely structure: degree + links are siblings)
                        try:
                            # Use a broad check for any sibling with 'links' in class, or just the next sibling
                            # Using relative xpath to find the links container associated with this degree header
                            # Assuming standard structure: degree -> description -> links
                            # So looking for following-sibling::div[contains(@class, '__links')]
                            links_container = block.find_element(By.XPATH, "following-sibling::div[contains(@class, '__links')]")
                            potential_links.extend(links_container.find_elements(By.TAG_NAME, "a"))
                        except:
                            pass

                        # 2. Check inside the block (Fallback if structure is nested)
                        potential_links.extend(block.find_elements(By.TAG_NAME, "a"))
                        
                        # Process all candidates
                        for link in potential_links:
                            # Check aria-label
                            aria = link.get_attribute("aria-label") or ""
                            # Check text/innerText
                            txt = link.text or link.get_attribute("innerText") or ""
                            txt = txt.strip().lower()
                            aria = aria.lower()
                            
                            if "learn more" in txt or "visit program" in txt or "learn more" in aria:
                                learn_more_url = link.get_attribute("href")
                                break
                        
                        if learn_more_url != "N/A" and not learn_more_url.startswith('http'):
                             learn_more_url = urljoin("https://www.harvard.edu", learn_more_url)
                             
                    except Exception as e:
                        pass
                    
                    full_name = f"{category_name} - {degree_title}"
                    extracted.append((full_name, school, learn_more_url))
                    
                except Exception:
                    continue
        except Exception:
            pass
        return extracted


    def _extract_deadline_from_page(self, browser: WebDriver) -> str:
        """从详情页提取 Deadline"""
        try:
            WebDriverWait(browser, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(1)
            
            page_text = browser.find_element(By.TAG_NAME, "body").text
            lines = [l.strip() for l in page_text.split('\n') if l.strip()]

            # 1. GSAS Specific "APPLICATION DEADLINE" header
            for i, line in enumerate(lines):
                if "APPLICATION DEADLINE" in line.upper():
                    # Check next 3 lines for a date
                    for j in range(1, 4):
                        if i + j < len(lines):
                            candidate = lines[i+j]
                            # Match months (Dec, January, etc) and year 202X
                            if re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+202\d', candidate, re.IGNORECASE):
                                return candidate
                            # Also check simple "December 15, 2025" without abbreviated month if different
                    
            # 2. Field Label Exact match
            try:
                labels = browser.find_elements(By.CSS_SELECTOR, ".field-label")
                for lbl in labels:
                    if "deadline" in lbl.text.lower():
                        try:
                            parent = lbl.find_element(By.XPATH, "..")
                            value_div = parent.find_element(By.CSS_SELECTOR, ".field__item")
                            val = value_div.text.strip()
                            if val: return val
                        except:
                            pass
            except:
                pass

            # 3. GSD Specific (Important Dates / Calendar Accordion)
            try:
                # Look for the container that has "deadline" in the title
                # Structure: .calendar-accordion__toggle > .calendar-accordion__title (text "PhD application deadline")
                # Sibling: .calendar-accordion__date > .calendar-accordion__calendar (text "January 5, 2026")
                
                toggles = browser.find_elements(By.CSS_SELECTOR, ".calendar-accordion__toggle")
                for toggle in toggles:
                    try:
                        title = toggle.find_element(By.CSS_SELECTOR, ".calendar-accordion__title").text.lower()
                        if "deadline" in title:
                            # Extract date
                            date_div = toggle.find_element(By.CSS_SELECTOR, ".calendar-accordion__date")
                            # It might have multiple spans, join them
                            spans = date_div.find_elements(By.CSS_SELECTOR, ".calendar-accordion__calendar")
                            texts = [s.text.strip() for s in spans if s.text.strip()]
                            if texts:
                                return " ".join(texts)
                    except:
                        continue
            except:
                pass

            # 4. Fallback Keyword Search
            for line in lines:
                lower = line.lower()
                clean_line = line.strip()
                # Must contain "deadline" or similar AND a year 202X
                if (("application due" in lower) or ("apply by" in lower) or ("deadline" in lower)) and re.search(r'202[4-6]', lower):
                     if len(clean_line) < 150:
                        return clean_line

            return "N/A"
        except:
            return "N/A"


    def _navigate_with_retry(self, max_retries: int = 3):
        pass

if __name__ == "__main__":
    HARVARD_MAX_WORKERS = 24
    with HarvardSpider(headless=True) as spider:
        results = spider.run()
        print(f"\n抓取完成，共 {len(results)} 个项目")
