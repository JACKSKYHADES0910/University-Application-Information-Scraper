# -*- coding: utf-8 -*-
import time
import requests
import re
import concurrent.futures
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional, Set
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from spiders.base_spider import BaseSpider
from config import UNIVERSITY_INFO
from utils.progress import CrawlerProgress

class NYUSpider(BaseSpider):
    """
    纽约大学 (NYU) 爬虫 (US018)
    
    结构:
    1. 访问 Bulletins 页面，提取项目列表
    2. 动态构建 School 映射
    3. 并发深度爬取 (Deep Scraping) 每个项目页面以获取 Application Link
       - 包含特定链接替换规则
       - 包含递归查找 "how-to-apply" 页面
       - 验证申请链接包含 "log in" 或 "create an account"
    """

    # 替换规则表 (User specified)
    REPLACEMENT_RULES = {
        "apply.steinhardt.nyu.edu/portal/graduate_application": "https://apply.steinhardt.nyu.edu/portal/graduate_application?_ga=2.4617783.507695171.1768439682-1008657193.1768439677",
        "docs.google.com/forms/d/e/1FAIpQLSfjCR_pZAph-bmp5eTO_gXj2UjrUq5_FqkzTUs-78A4Sak4zQ/viewform": "https://apply.steinhardt.nyu.edu/portal/graduate_application?_ga=2.4617783.507695171.1768439682-1008657193.1768439677",
        "www.law.nyu.edu/graduateadmissions": "https://llm.lsac.org/login/access.aspx",
        "www.sps.nyu.edu/join/apply-now/apply-now-undergraduate-degrees.html": "https://apply.sps.nyu.edu/apply/?sr=9044ec14-eb84-4289-ab43-44e5c2df4f87",
        "www.nysed.gov/heds/irpsl1.html": "不接受申请",
        "gallatin.nyu.edu/admissions/graduate/applying.html": "https://apply.gallatin.nyu.edu/apply/"
    }

    # 学院级 Fallback 链接 (当找不到具体项目申请链接时优先使用)
    SCHOOL_FALLBACK_LINKS = {
        "Stern": "https://admissions.stern.nyu.edu/apply/",
        "Steinhardt": "https://apply.steinhardt.nyu.edu/portal/graduate_application",
        "Tisch": "https://apply.tisch.nyu.edu/apply/",
        "GSAS": "https://apply.gsas.nyu.edu/apply/",
        "Tandon": "https://apply.tandon.nyu.edu/apply/",
        "Wagner": "https://apply.wagner.nyu.edu/apply/",
        "Silver": "https://apply.socialwork.nyu.edu/apply/",
        "Gallatin": "https://apply.gallatin.nyu.edu/apply/",
        "SPS": "https://apply.sps.nyu.edu/apply/"
    }

    # Deep Scraping Config
    TIMEOUT = 15
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    def __init__(self, headless: bool = True):
        super().__init__("nyu", headless=headless)
        self.config = UNIVERSITY_INFO["nyu"]
        self.programs = []
        self.start_url = "https://bulletins.nyu.edu/programs/#filter=.filter_55"
        self.school_mapping = {}

    def _build_school_mapping(self, soup: BeautifulSoup):
        """
        从左侧筛选器构建 filter class 到 School Name 的映射
        """
        print("🔍 正在构建学院映射表...")
        try:
            school_fieldset = None
            fieldsets = soup.find_all("fieldset")
            for fs in fieldsets:
                legend = fs.find("legend")
                if legend and "School" in legend.get_text():
                    school_fieldset = fs
                    break
            
            if not school_fieldset:
                print("⚠️ 未找到 School 筛选区域")
                return

            filters = school_fieldset.select("div.filters__filter")
            for f in filters:
                input_tag = f.find("input")
                label_tag = f.find("label")
                
                if input_tag and label_tag:
                    value = input_tag.get("value", "")
                    name = label_tag.get_text(strip=True)
                    if value.startswith(".filter_"):
                        key = value.replace(".", "")
                        self.school_mapping[key] = name
            
            print(f"✅ 构建映射表完成，共 {len(self.school_mapping)} 项")
        except Exception as e:
            print(f"⚠️ 构建学院映射表失败: {e}")

    def _deep_scrape_program(self, program_item: Dict) -> Dict:
        """
        使用 DeepCrawler 进行深度抓取
        """
        from utils.deep_crawler import DeepCrawler
        
        start_url = program_item["项目官网链接"]
        crawler = DeepCrawler(max_depth=3)
        result = crawler.crawl(start_url)
        
        program_item["项目deadline"] = result["deadline"]
        apply_link = result["apply_link"]
        
        # 1. Check User Replacement Rules
        for key, val in self.REPLACEMENT_RULES.items():
            if key in apply_link:
                apply_link = val
                break
                
        # 2. Check Validity & School Fallback
        if apply_link == "N/A" or "how-to-apply" in apply_link:
            # Try school fallback
            school = program_item.get("学院/学习领域", "")
            for key, val in self.SCHOOL_FALLBACK_LINKS.items():
                if key in school:
                    apply_link = val
                    break
        
        # 3. Final Fallback to Config Default (if still needed, mostly handled by school fallback)
        if apply_link == "N/A":
             apply_link = self.config.get("apply_register_url", "N/A")

        program_item["申请链接"] = apply_link
             
        # Fallback logic for Deadline
        if program_item["项目deadline"] == "N/A":
             program_item["项目deadline"] = "See Program Website"
             
        return program_item

    def run(self) -> List[Dict]:
        print(f"📄 开始爬取 {self.school_name} 的专业信息...")
        driver = self.driver
        
        try:
            # Phase 1: Access the main page
            print(f"📄 正在访问: {self.start_url}")
            driver.get(self.start_url)
            
            # 等待列表加载
            print("⏳ 等待项目列表加载...")
            try:
                WebDriverWait(driver, 25).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#filters-grid-tab-content a"))
                )
                time.sleep(5)
            except Exception as e:
                print(f"⚠️ 等待列表加载超时或出错: {e}")
            
            # Phase 2: Extract data basics
            print("📄 开始提取项目列表...")
            content = driver.page_source
            soup = BeautifulSoup(content, 'html.parser')
            
            self._build_school_mapping(soup)
            
            program_links = soup.select("#filters-grid-tab-content a")
            print(f"🔍 页面共找到 {len(program_links)} 个潜在项目链接")

            initial_items = []
            
            for link in program_links:
                try:
                    li_element = link.find_parent("li")
                    if not li_element:
                        continue
                    classes = li_element.get("class", [])
                    if "filter_55" not in classes:
                        continue
                        
                    title_span = link.select_one("span.title")
                    if not title_span:
                        continue
                    program_name = title_span.get_text(strip=True)
                    
                    href = link.get("href", "")
                    full_link = f"https://bulletins.nyu.edu{href}" if href.startswith("/") else href
                        
                    school_name = "New York University"
                    ignored_filters = {"filter_55", "filter_1", "filter_2", "filter_3", "filter_4"}

                    for cls in classes:
                        if cls in self.school_mapping and cls not in ignored_filters:
                            candidate_name = self.school_mapping[cls]
                            if candidate_name not in ["Graduate", "Undergraduate", "In Person", "Online", "Masters", "Doctoral"]:
                                school_name = candidate_name
                                break
                    
                    program_item = {
                        "学校代码": self.config["code"],
                        "学校名称": self.config["name"],
                        "项目名称": program_name,
                        "学院/学习领域": school_name,
                        "项目官网链接": full_link,
                        "申请链接": "Searching...", # Placeholder
                        "项目opendate": "",
                        "项目deadline": "See Program Website",
                        "学生案例": "",
                        "面试问题": ""
                    }
                    initial_items.append(program_item)
                    
                except Exception as e:
                    print(f"❌ 解析单项基础信息出错: {e}")

            print(f"✅ 基础信息提取完成，共 {len(initial_items)} 个项目。开始并发深度爬取...")
            
            # Phase 3: Concurrent Deep Scraping
            def deep_scrape_wrapper(item):
                start = time.time()
                result = self._deep_scrape_program(item)
                return result, time.time() - start

            progress = CrawlerProgress(max_workers=24) # Increased workers for speed
            self.programs = progress.run_tasks(
                items=initial_items,
                task_func=deep_scrape_wrapper,
                task_name="Deep Scraping",
                phase_name="深度抓取"
            )
            
            print(f"✅ 所有项目爬取完成，共 {len(self.programs)} 个")

        except Exception as e:
            print(f"❌ 爬虫运行出错: {e}")
        
        return self.programs

if __name__ == "__main__":
    spider = NYUSpider(headless=True)
    spider.run()
