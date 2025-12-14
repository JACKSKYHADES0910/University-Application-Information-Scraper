# -*- coding: utf-8 -*-
"""
香港中文大学 (CUHK) 爬虫
目标：抓取 Taught Postgraduate Programmes
策略：
1. 入口页发现各学院 Programme 列表
2. 提取 hash 链接 + JS 弹窗详情
3. 并发处理
"""

import time
import re
from typing import List, Dict, Tuple
from urllib.parse import urljoin, urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

from spiders.base_spider import BaseSpider
from utils.progress import CrawlerProgress

class CUHKSpider(BaseSpider):
    def __init__(self, headless: bool = True):
        super().__init__("cuhk", headless)
        self.browser_pool = None

    def run(self) -> List[Dict]:
        print(f"🚀 开始抓取 {self.school_name}...")
        
        # 1. 发现学院页面
        faculty_links = self._get_faculty_links()
        
        # 2. 收集所有 Programme 链接 (Hash)
        program_items = self._collect_program_links(faculty_links)
        
        if not program_items:
            print("❌ 未发现任何项目链接，终止")
            return []
            
        print(f"📦 共发现 {len(program_items)} 个 Taught Programmes，准备抓取详情...")
        
        # 3. 并发抓取详情
        # 初始化浏览器池
        from utils.selenium_utils import BrowserPool
        from config import MAX_WORKERS
        
        # 使用配置的高并发数 (24)
        pool_size = self.university_info.get("max_workers", MAX_WORKERS)
        print(f"🚀 启动高并发模式: {pool_size} 线程")
        
        self.browser_pool = BrowserPool(size=pool_size, headless=self.headless)
        self.browser_pool.initialize()
        
        try:
            progress = CrawlerProgress(max_workers=pool_size)
            self.results = progress.run_tasks(
                items=program_items,
                task_func=self._fetch_details,
                task_name="抓取详情",
                phase_name="CUHK Details"
            )
        finally:
            if self.browser_pool:
                self.browser_pool.close_all()
        
        # 数据去重
        from utils.deduplicator import deduplicate_results
        self.results = deduplicate_results(self.results)
        
        self.print_summary()
        return self.results

    def _get_faculty_links(self) -> List[str]:
        """从入口页获取所有学院的 Programme 列表链接"""
        print("🔍 正在发现学院入口...")
        self.driver.get(self.list_url)
        
        # 等待加载
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/admissions/programme/']"))
            )
        except TimeoutException:
            print("⚠️ 入口页加载超时")
            
        # 提取链接
        links = set()
        elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/admissions/programme/']")
        for el in elements:
            href = el.get_attribute("href")
            if href and "/admissions/programme/" in href:
                # 排除完全重复或非列表页
                links.add(href)
        
        sorted_links = sorted(list(links))
        print(f"✅ 发现 {len(sorted_links)} 个学院入口")
        return sorted_links

    def _collect_program_links(self, faculty_links: List[str]) -> List[Dict]:
        """遍历学院页，收集所有 Taught Programme 的 Hash 链接"""
        all_items = []
        
        # 这里不需要并发，因为只是收集链接，且为了稳定性建议串行打开学院页
        for idx, link in enumerate(faculty_links):
            print(f"   [{idx+1}/{len(faculty_links)}]用于发现: {link}")
            try:
                self.driver.get(link)
                # 等待 Taught Programmes Tab 或列表加载
                time.sleep(2) # 稍作等待 JS 渲染
                
                # 筛选 Taught Programmes 的链接
                # Selector: a.programme-tb-link[data-ix="taught-programmes"]
                # 这种链接通常带有 href="#hash"
                # 修正：根据截图，属性是 data-ix="taught-programmes" 而不是 data-type
                elements = self.driver.find_elements(By.CSS_SELECTOR, "a.programme-tb-link[data-ix='taught-programmes']")
                
                count = 0
                for el in elements:
                    href = el.get_attribute("href")
                    text = el.text.strip()
                    
                    if not href or "#" not in href:
                        continue
                        
                    # 构造完整逻辑链接 (Faculty URL + Hash)
                    full_url = link.split("#")[0] + href[href.find("#"):]
                    hash_val = href[href.find("#"):]
                    
                    item = {
                        "name": text,   # 暂存名字，详情页会更新
                        "link": full_url,
                        "faculty_url": link.split("#")[0],
                        "hash": hash_val,
                        # 优先捕获 ID，这是最稳的定位方式
                        "trigger_id": el.get_attribute("id"),
                        "trigger_selector": f"a.programme-tb-link[href='{hash_val}']",
                        # 捕获弹窗 Selector
                        "popup_selector": el.get_attribute("data-popup")
                    }
                    all_items.append(item)
                    count += 1
                
                print(f"      -> 找到 {count} 个项目")
                
            except Exception as e:
                print(f"⚠️ 处理学院页失败 {link}: {e}")
        
        return all_items

    def _fetch_details(self, item: Dict) -> Tuple[Dict, float]:
        """
        抓取单个项目详情
        """
        start_time = time.time()
        
        result = self.create_result_template(item["name"], item["link"])
        result["项目申请链接"] = "https://www.gradsch.cuhk.edu.hk/OnlineApp/login_email.aspx"
        
        # 使用浏览器池
        with self.browser_pool.get_browser() as driver:
            try:
                # 1. 打开页面
                driver.get(item['link'])
                time.sleep(1) # 基础等待
                
                wait = WebDriverWait(driver, 10)
                
                # 2. 尝试触发弹窗
                try:
                    trigger = None
                    # 策略 A: 如果有 ID，直接用 ID (最稳)
                    if item.get("trigger_id"):
                        try:
                            trigger = wait.until(EC.presence_of_element_located((By.ID, item["trigger_id"])))
                        except:
                            pass
                    
                    # 策略 B: 用 Selector
                    if not trigger:
                        trigger = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, item["trigger_selector"])))
                
                except TimeoutException:
                    # 策略 C: 备用方案，通过 Hash 模糊匹配
                    try:
                        hash_val = item['hash']
                        xpath = f"//a[contains(@href, '{hash_val}')]"
                        trigger = driver.find_element(By.XPATH, xpath)
                    except Exception:
                        raise Exception(f"触发器彻底失踪: {item['trigger_selector']}")

                # 滚动并强制点击
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", trigger)
                    time.sleep(0.5)
                    # 强制 JS 点击穿透
                    driver.execute_script("arguments[0].click();", trigger)
                except Exception as e:
                    raise Exception(f"点击触发器失败: {e}")
                
                # 3. 等待弹窗内容出现
                try:
                    modal_el = None
                    
                    # 策略: 寻找可见的弹窗
                    # 优先使用 data-popup 
                    if item.get("popup_selector"):
                        try:
                            # data-popup 可能是 class，页面上可能有很多个这样的 hidden div
                            # 我们必须找到 *当前可见* 的那个
                            # 所以不能只用 find_element (它只返回第一个)，而是要 find_elements 并过滤
                            
                            # 等待任意一个可见 (手写轮询 logic)
                            end_time = time.time() + 10
                            while time.time() < end_time:
                                candidates = driver.find_elements(By.CSS_SELECTOR, item["popup_selector"])
                                for c in candidates:
                                    if c.is_displayed():
                                        modal_el = c
                                        break
                                if modal_el:
                                    break
                                time.sleep(0.5)
                        except:
                            pass
                    
                    # 备用：使用 ID
                    if not modal_el:
                         # 尝试 id='hash' (去掉了 #)
                        modal_id = item['hash'].replace("#", "")
                        try:
                            # 直接等待该 ID 可见
                            wait.until(EC.visibility_of_element_located((By.ID, modal_id)))
                            modal_el = driver.find_element(By.ID, modal_id)
                        except:
                            pass
                    
                    if not modal_el:
                         raise Exception(f"弹窗未弹出 (Selector: {item.get('popup_selector')})")

                    # 4. 解析内容 (在 Modal 内部找)
                    
                    # 4. 解析内容 (在 Modal 内部找)
                    # 确保获取的是 Modal 内的文本，防止获取到页面背景
                    text_content = modal_el.get_attribute("innerText")
                    
                    # 提取 Deadline
                    if "Application Deadline" in text_content:
                        parts = text_content.split("Application Deadline")
                        if len(parts) > 1:
                            deadline_chunk = parts[1].strip().split("\n")[0]
                            deadline_chunk = deadline_chunk.lstrip(":").strip()
                            result["项目deadline"] = deadline_chunk
                    
                    # 更新真正的标题 (Attempt to find h3/h4 in modal)
                    try:
                        title_el = modal_el.find_element(By.CSS_SELECTOR, "h3, h4, .programme-title")
                        if title_el.text:
                            result["项目名称"] = self._clean_text(title_el.text)
                    except:
                        pass
                        
                except TimeoutException:
                     # 截图留证 (可选，暂不实现)
                     raise Exception(f"弹窗未弹出 (Selector: {item.get('popup_selector')}, ID: {item.get('hash')})")

            except Exception as e:
                error_msg = str(e)
                print(f"❌ [失败] {item['name']}: {error_msg}")
                result["_error"] = error_msg
                raise e
        
        duration = time.time() - start_time
        return result, duration

    def _clean_text(self, text: str) -> str:
        """清洗文本：去空白、换行"""
        if not text:
            return ""
        # 替换多余空白
        return re.sub(r'\s+', ' ', text).strip()
