# -*- coding: utf-8 -*-
"""
香港城市大学 (CityU) 爬虫
目标网址: https://www.cityu.edu.hk/pg/taught-postgraduate-programmes/list
"""

import time
from typing import List, Dict, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from spiders.base_spider import BaseSpider
from utils.progress import CrawlerProgress

class CityUSpider(BaseSpider):
    def __init__(self, headless: bool = True):
        # CityU 有极其严格的 Incapsula WAF 防护，无头模式(Headless)几乎必死
        # 因此这里强制覆盖传入的 headless 参数，必须使用有头模式
        print("🛡️ 检测到 CityU 安全防护，强制切换为有头模式(Headful)以绕过拦截...")
        super().__init__("cityu", headless=False)
        # 固定申请链接
        self.apply_url = "https://banweb.cityu.edu.hk/pls/PROD/hwskalog_cityu.P_DispLoginNon"

    def run(self) -> List[Dict]:
        """
        执行爬虫主流程
        """
        print(f"🚀 开始抓取 {self.university_info['name']}...")
        print(f"📍 列表页: {self.university_info['list_url']}")
        
        self.results = []
        
        try:
            # 第一阶段：收集项目链接
            print("🔍 正在收集项目列表...")
            items = self._collect_program_links()
            
            if not items:
                print("⚠️ 未找到任何项目，请检查网络或选择器")
                return []
            
            print(f"📦 共发现 {len(items)} 个项目，准备抓取详情...")
            
            # 第二阶段：并发抓取详情
            progress = CrawlerProgress(
                max_workers=self.university_info.get("max_workers", 12)
            )
            
            self.results = progress.run_tasks(
                items=items,
                task_func=self._fetch_details,
                task_name="抓取详情",
                phase_name="CityU Details"
            )
            
        finally:
            # BaseSpider 上下文管理器会自动关闭主 driver，无需手动关闭
            pass
            
        # 数据去重
        from utils.deduplicator import deduplicate_results
        self.results = deduplicate_results(self.results)
        
        self.print_summary()
        return self.results

    def _collect_program_links(self) -> List[Dict]:
        """
        从列表页收集所有项目链接
        策略: 快速拍照法 - 一次性抓取 HTML，避免频繁 Selenium 调用触发 WAF
        """
        self.driver.get(self.university_info['list_url'])
        
        # 增加通用等待
        try:
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except:
            print("⚠️ 页面加载基础内容超时")
        
        # 等待表格加载
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.table-responsive"))
            )
            # 稍作等待确保渲染完成
            time.sleep(5)
        except Exception as e:
            print(f"⚠️ 等待页面表格加载超时: {e}")
            return []

        # 🎯 关键优化：一次性抓取整个页面源代码
        print("📸 正在抓取页面快照（避免触发防火墙）...")
        page_html = self.driver.page_source
        
        # 使用 BeautifulSoup 离线解析
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(page_html, 'html.parser')
        
        items = []
        
        # 查找所有学院的表格容器
        college_containers = soup.select("div.table-responsive")
        print(f"DEBUG: 找到 {len(college_containers)} 个表格容器")
        
        for i, container in enumerate(college_containers):
            try:
                # 获取学院名称
                college_code = container.get("data-college") or f"未知学院_{i}"
                
                # 查找表格行
                rows = container.select("tr")
                
                for row in rows:
                    try:
                        # 查找项目链接和名称
                        link_els = row.select("td.col-prog-title a")
                        
                        if not link_els:
                            continue
                            
                        link_el = link_els[0]
                        name = self._clean_text(link_el.get_text(strip=True))
                        url = link_el.get("href")
                        
                        if not name or not url:
                            continue
                        
                        # 处理相对链接
                        if url.startswith("/"):
                            url = self.university_info['base_url'] + url
                            
                        items.append({
                            "name": name,
                            "link": url,
                            "college": college_code
                        })
                    except Exception as e:
                        # 不再打印每一行的错误（太吵）
                        continue
                        
            except Exception as e:
                print(f"⚠️ 处理学院表格时出错: {e}")
                continue
                
        print(f"✅ 总共收集到 {len(items)} 个项目")
        return items

    def _fetch_details(self, item: Dict) -> Tuple[Dict, float]:
        """
        抓取单个项目详情
        """
        # 注意：这里会由多线程调用，每个线程需要创建自己的 driver 
        # 但 BaseSpider 目前设计是单 driver 模式
        # 这里的 fetch_details 设计需要遵循 CrawlerProgress 的模式
        # 我们使用临时 driver
        
        from utils.browser import get_driver, close_driver
        
        start_time = time.time()
        result = self.create_result_template(item["name"], item["link"])
        result["项目申请链接"] = self.apply_url
        
        # 启动临时浏览器
        driver = get_driver(headless=True)
        
        try:
            driver.get(item['link'])
            
            # 等待内容加载
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "h1"))
                )
            except:
                pass
            
            # 这里需要根据实际页面结构解析
            # CityU 详情页通常包含：
            # - Application Deadline (通常在表格中或文本中)
            # - Combined mode / Full-time mode details
            
            # 获取页面所有文本用于简单匹配
            page_text = driver.find_element(By.TAG_NAME, "body").text
            
            # 尝试查找 Deadline
            # 常见格式: "Application Deadline: 31 May 2024" 或表格中的 "Application Deadline"
            deadline = self._extract_deadline(driver, page_text)
            if deadline:
                result["项目deadline"] = deadline
            
        except Exception as e:
            result["_error"] = str(e)
        finally:
            close_driver(driver)
            
        duration = time.time() - start_time
        return result, duration

    def _extract_deadline(self, driver, page_text: str) -> str:
        """
        尝试提取 Application Deadline
        """
        # 策略 1: 查找包含 "Application Deadline" 的表格行
        try:
            # 查找所有包含 "Deadline" 的 th 或 td
            deadline_labels = driver.find_elements(By.XPATH, "//*[contains(text(), 'Application Deadline')]")
            for label in deadline_labels:
                # 尝试找同行的下一个 td，或者父级 tr
                try:
                    # 检查是否是表格的一部分
                    parent_tr = label.find_element(By.XPATH, "./ancestor::tr")
                    # 获取该行所有文本
                    row_text = parent_tr.text
                    # 简单的文本处理: "Application Deadline 30 April 2024" -> "30 April 2024"
                    clean_text = row_text.replace("Application Deadline", "").replace("Closing Date", "").strip()
                    if len(clean_text) > 5:
                        return clean_text
                except:
                    continue
        except:
            pass
            
        # 策略 2: 在全文中搜索
        # (简单实现，后续可根据实际 HTML 优化)
        lines = page_text.split('\n')
        for line in lines:
            if "Application Deadline" in line or "Closing Date" in line:
                # 简单的截取
                parts = line.split(":")
                if len(parts) > 1:
                    val = parts[1].strip()
                    if len(val) > 5 and len(val) < 100:
                        return val
                        
        return "N/A"
