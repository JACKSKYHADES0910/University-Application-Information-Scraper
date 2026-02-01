# -*- coding: utf-8 -*-
import time
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from spiders.base_spider import BaseSpider
from config import UNIVERSITY_INFO

class DukeKunshanSpider(BaseSpider):
    """
    昆山杜克大学 (Duke Kunshan University) 爬虫 (US021)
    
    Target:
    1. Master of Engineering in Electrical and Computer Engineering
    2. Master of Environmental Policy
    3. Master of Management Studies
    4. Master of Science in Medical Physics
    5. Master of Science in Global Health
    
    Hardcoded deadlines and application links as per user request.
    Scrapes specific program URLs if available on the listing page.
    """

    def __init__(self, headless: bool = True):
        super().__init__("duke_kunshan", headless=headless)
        self.config = UNIVERSITY_INFO["duke_kunshan"]
        self.programs = []
        # Hardcoded list from user
        self.target_programs = [
            "Master of Engineering in Electrical and Computer Engineering",
            "Master of Environmental Policy",
            "Master of Management Studies",
            "Master of Science in Medical Physics",
            "Master of Science in Global Health"
        ]
        self.DEADLINES_TEXT = "Early Admission Deadline: December 15, 2025\nPriority Admission Deadline: January 15, 2026"
        self.APPLY_LINK = "https://applygp.duke.edu/apply/?sr=d3abd676-a8c1-4bcc-aa53-2603fe10563b"

    def run(self) -> List[Dict]:
        print(f"📄 开始爬取 {self.school_name} 的专业信息...")
        driver = self.driver
        
        try:
            print(f"📄 正在访问: {self.config['list_url']}")
            driver.get(self.config['list_url'])
            time.sleep(5)  # Wait for JS if any
            
            content = driver.page_source
            soup = BeautifulSoup(content, 'html.parser')
            
            all_links = soup.find_all('a')
            print(f"🔍 页面共找到 {len(all_links)} 个链接，正在匹配项目...")

            for program_name in self.target_programs:
                # Default values
                program_url = self.config['list_url']
                
                # Try to find a link that contains the program name (case insensitive)
                # Or matches significantly.
                # Simplify program name for matching (e.g. "Medical Physics")
                matched_link = None
                
                # Strategy: Identify unique keywords for each program to match links
                keywords = program_name
                if "Electrical and Computer Engineering" in program_name:
                    keywords = "Electrical and Computer Engineering"
                elif "Environmental Policy" in program_name:
                    keywords = "Environmental Policy"
                elif "Management Studies" in program_name:
                    keywords = "Management Studies"
                elif "Medical Physics" in program_name:
                    keywords = "Medical Physics"
                elif "Global Health" in program_name:
                    keywords = "Global Health"
                
                for a in all_links:
                    text = a.get_text(strip=True)
                    if not text:
                        continue
                        
                    if keywords.lower() in text.lower():
                        href = a.get('href')
                        if href:
                            if href.startswith('http'):
                                matched_link = href
                            elif href.startswith('/'):
                                matched_link = self.config['base_url'] + href
                            else:
                                matched_link = self.config['base_url'] + '/' + href
                            break
                            
                if matched_link:
                    program_url = matched_link
                    print(f"   ✅ 找到链接 (matches '{keywords}'): {program_url}")
                else:
                    print(f"   ⚠️ 未找到具体链接 for: {program_name}, 使用列表页链接")
                
                # Determine school/study area
                # For DKU, it's small, can assume they are under distinct research centers or just "Graduate Program"
                school_name = "Graduate Program"

                program_item = {
                    "学校代码": self.config["code"],
                    "学校名称": self.config["name"],
                    "项目名称": program_name,
                    "学院/学习领域": school_name,
                    "项目官网链接": program_url,
                    "申请链接": self.APPLY_LINK,
                    "项目opendate": "",
                    "项目deadline": self.DEADLINES_TEXT,
                    "学生案例": "",
                    "面试问题": ""
                }
                self.programs.append(program_item)

            print(f"✅ 所有项目提取完成，共 {len(self.programs)} 个")

        except Exception as e:
            print(f"❌ 爬虫运行出错: {e}")
        
        return self.programs

if __name__ == "__main__":
    spider = DukeKunshanSpider(headless=True)
    spider.run()
