import time
from typing import List, Dict
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from spiders.base_spider import BaseSpider
from config import UNIVERSITY_INFO

class StanfordSpider(BaseSpider):
    """
    斯坦福大学 (Stanford) 爬虫 (US003)
    
    数据来源: https://applygrad.stanford.edu/portal/explore-programs
    结构:
    1. 点击 Expand/Collapse All 展开所有项目
    2. 遍历每个 button.collapsible.h3 获取项目名称
    3. 在其兄弟 div 中提取 School、Program Website、子项目和 Deadline
    """
    
    def __init__(self, headless: bool = True):
        super().__init__("stanford", headless=headless)
        self.config = UNIVERSITY_INFO["stanford"]
        self.programs = []
        self.start_url = "https://applygrad.stanford.edu/portal/explore-programs"

    def run(self) -> List[Dict]:
        print(f"📄 开始爬取 {self.school_name} 的专业信息...")
        driver = self.driver
        
        try:
            # Phase 1: Access the main page
            print(f"📄 正在访问: {self.start_url}")
            driver.get(self.start_url)
            time.sleep(5)  # Wait for initial load

            # Click Expand/Collapse All button
            try:
                expand_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "expand"))
                )
                print("🔘 点击 'Expand/Collapse All' 按钮...")
                expand_button.click()
                time.sleep(3)  # Wait for expansion
            except Exception as e:
                print(f"⚠️ 无法找到全展开按钮或点击失败: {e}")
            
            # Phase 2: Extract data
            print("📄 开始提取项目信息...")
            content = driver.page_source
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find all program buttons (collapsible headers)
            program_buttons = soup.select("button.collapsible.h3")
            print(f"🔍 找到 {len(program_buttons)} 个项目")

            for button in program_buttons:
                try:
                    # 1. Main Program Name (e.g., "Aeronautics and Astronautics (MS)")
                    title_elem = button.select_one("h2.custom-h3-heading")
                    if not title_elem:
                        continue
                    main_program_name = title_elem.get_text(strip=True)
                    
                    # 2. Find the content div (next sibling of the button)
                    content_div = button.find_next_sibling("div")
                    if not content_div:
                        continue
                    
                    # 3. School Info (e.g., "School of Engineering")
                    school = "Unknown"
                    school_elem = content_div.select_one(".school a")
                    if school_elem:
                        school = school_elem.get_text(strip=True)
                    
                    # 4. Program Website
                    website_url = ""
                    website_elem = content_div.select_one("a[aria-label*='Program Website']")
                    if website_elem:
                        website_url = website_elem.get("href", "")
                    
                    # 5. Sub-programs and Deadlines
                    # Find all .section-block elements (exclude Testing Requirements)
                    section_blocks = content_div.select(".section-block")
                    
                    sub_items = []
                    for block in section_blocks:
                        sub_name_elem = block.select_one("h3.no-style-heading")
                        if not sub_name_elem:
                            continue
                        sub_name = sub_name_elem.get_text(strip=True)
                        
                        # Skip Testing Requirements
                        if "Testing Requirements" in sub_name:
                            continue
                        
                        # Extract deadline from table
                        deadline_text = ""
                        table = block.select_one("table")
                        if table:
                            rows = table.select("tbody tr")
                            deadline_parts = []
                            for row in rows:
                                th = row.select_one("th")
                                td = row.select_one("td")
                                if th and td:
                                    entry_term = th.get_text(strip=True)
                                    deadline_date = td.get_text(strip=True)
                                    deadline_parts.append(f"{entry_term}: {deadline_date}")
                            deadline_text = "; ".join(deadline_parts)
                        
                        sub_items.append({
                            "name": sub_name,
                            "deadline": deadline_text
                        })
                    
                    # If no sub-items found, create a default entry
                    if not sub_items:
                        sub_items.append({
                            "name": "",
                            "deadline": "Check Website"
                        })
                    
                    # Construct final items
                    for item in sub_items:
                        if item['name']:
                            full_name = f"{main_program_name} - {item['name']}"
                        else:
                            full_name = main_program_name
                        
                        program_item = {
                            "学校代码": self.config["code"],
                            "学校名称": self.config["name"],
                            "项目名称": full_name,
                            "学院/学习领域": school,
                            "项目官网链接": website_url,
                            "申请链接": self.config.get("apply_register_url", ""),
                            "项目opendate": "",
                            "项目deadline": item["deadline"],
                            "学生案例": "",
                            "面试问题": ""
                        }
                        self.programs.append(program_item)

                except Exception as e:
                    print(f"❌ 解析项目出错: {e}")

            print(f"✅ 共提取 {len(self.programs)} 个项目")

        except Exception as e:
            print(f"❌ 爬虫运行出错: {e}")
        
        return self.programs

if __name__ == "__main__":
    spider = StanfordSpider()
    spider.run()
