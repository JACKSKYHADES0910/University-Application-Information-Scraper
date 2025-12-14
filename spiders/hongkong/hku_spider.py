# -*- coding: utf-8 -*-
"""
香港大学 (HKU) 爬虫模块
负责抓取 HKU 研究生项目信息
"""

import time
import json
from typing import List, Dict
from urllib.parse import urljoin

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from spiders.base_spider import BaseSpider
from utils.browser import get_driver
from utils.progress import CrawlerProgress, print_phase_start, print_phase_complete
from utils.selenium_utils import (
    BrowserPool, 
    safe_click, 
    wait_for_new_window,
    wait_and_get_text
)
from config import MAX_WORKERS, PAGE_LOAD_WAIT

# #region agent log
_DEBUG_LOG_PATH = r"d:\Project\MySpiderProject\.cursor\debug.log"
def _debug_log(hypothesis_id, location, message, data=None):
    entry = {"hypothesisId": hypothesis_id, "location": location, "message": message, "data": data or {}, "timestamp": int(time.time()*1000), "sessionId": "debug-session"}
    with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
# #endregion


class HKUSpider(BaseSpider):
    """
    香港大学爬虫
    
    负责从 HKU 官网爬取所有研究生项目的详细信息，包括：
    - 项目名称
    - 项目链接
    - 申请开放日期
    - 申请截止日期
    - 在线申请链接
    
    使用示例:
        >>> with HKUSpider() as spider:
        ...     data = spider.run()
        ...     print(f"爬取了 {len(data)} 条数据")
    """
    
    def __init__(self, headless: bool = True, max_workers: int = None):
        """
        初始化 HKU 爬虫
        
        参数:
            headless (bool): 是否无头模式运行
            max_workers (int): 并发线程数，如果不指定则使用 config.py 中的配置
        """
        super().__init__("hku", headless)
        # 每次初始化时重新读取配置，避免缓存问题
        from config import MAX_WORKERS as CONFIG_MAX_WORKERS
        self.max_workers = max_workers if max_workers is not None else CONFIG_MAX_WORKERS
        self.temp_links: List[Dict] = []  # 临时存储项目链接列表
        self.progress_manager: CrawlerProgress = None  # 进度管理器
        self.browser_pool: BrowserPool = None  # 浏览器池
    
    def run(self) -> List[Dict]:
        """
        执行完整的爬取流程
        
        流程:
            1. Phase 1: 获取所有项目的列表（名称+链接）
            2. Phase 2: 并发抓取每个项目的详细信息
        
        返回:
            List[Dict]: 所有项目的详细信息列表
        """
        self.start_time = time.time()
        self.results = []
        
        try:
            # Phase 1: 获取项目列表
            self._fetch_program_list()
            
            if not self.temp_links:
                print("❌ 未找到任何项目链接")
                return []
            
            # 初始化浏览器池（Phase 2 使用）
            self.browser_pool = BrowserPool(size=self.max_workers, headless=True)
            self.browser_pool.initialize()
            
            # Phase 2: 并发抓取详情
            self._fetch_program_details()
            
        except KeyboardInterrupt:
            print("\n⚠️ 用户中断了爬取")
        except Exception as e:
            print(f"❌ 爬取过程中发生错误: {e}")
        finally:
            # 关闭浏览器池
            if self.browser_pool:
                self.browser_pool.close_all()
            self.close()
        
        self.print_summary()
        return self.results
    
    def _fetch_program_list(self) -> None:
        """
        Phase 1: 从列表页获取所有项目的名称和链接
        
        该方法会遍历所有分页，收集所有项目的基本信息
        """
        print_phase_start(
            "Phase 1", 
            "正在扫描项目列表...",
            total=None
        )
        print(f"   📍 目标地址: {self.list_url}")
        
        try:
            # #region agent log
            _debug_log("B", "hku_spider.py:before_get", "About to load page", {"url": self.list_url, "page_load_wait": PAGE_LOAD_WAIT})
            # #endregion
            
            # 访问列表页
            self.driver.get(self.list_url)
            
            # #region agent log
            _debug_log("B", "hku_spider.py:after_get", "Page loaded, waiting for elements", {})
            # #endregion
            
            # 等待项目链接加载完成
            WebDriverWait(self.driver, PAGE_LOAD_WAIT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="programme-details"]'))
            )
            
            # #region agent log
            _debug_log("B", "hku_spider.py:elements_found", "Elements found successfully", {})
            # #endregion
            
            page_num = 1
            # 遍历所有分页
            while True:
                # 获取当前页面的所有项目链接
                before_count = len(self.temp_links)
                self._extract_programs_from_current_page()
                after_count = len(self.temp_links)
                
                print(f"   📄 第 {page_num} 页: 发现 {after_count - before_count} 个项目 (累计: {after_count})")
                
                # 尝试点击下一页
                if not self._go_to_next_page():
                    break
                page_num += 1
            
            print_phase_complete("Phase 1", len(self.temp_links))
            
        except Exception as e:
            print(f"❌ 获取项目列表失败: {e}")
    
    def _extract_programs_from_current_page(self) -> None:
        """
        从当前页面提取项目信息
        """
        elements = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="programme-details"]')
        
        for elem in elements:
            try:
                link = elem.get_attribute("href")
                raw_text = elem.text.strip()
                
                if not link or not raw_text:
                    continue
                
                # 构建完整链接
                full_link = urljoin(self.base_url, link)
                
                # 解析项目名称（通常在第二行）
                lines = raw_text.split('\n')
                prog_name = lines[1].strip() if len(lines) > 1 else lines[0].strip()
                
                # 去重检查
                if not any(d['link'] == full_link for d in self.temp_links):
                    self.temp_links.append({
                        "name": prog_name,
                        "link": full_link
                    })
                    
            except Exception:
                continue
    
    def _go_to_next_page(self) -> bool:
        """
        点击下一页按钮
        
        返回:
            bool: 是否成功跳转到下一页
        """
        try:
            # 查找 "»" (下一页) 按钮
            next_btns = self.driver.find_elements(By.XPATH, "//a[contains(text(), '»')]")
            
            if not next_btns:
                return False
            
            btn = next_btns[0]
            
            # 检查按钮是否被禁用
            parent_class = btn.find_element(By.XPATH, "./..").get_attribute("class")
            if "disabled" in parent_class:
                return False
            
            # 点击下一页
            safe_click(self.driver, btn)
            time.sleep(0.8)  # 减少等待时间
            
            return True
            
        except Exception:
            return False
    
    def _fetch_program_details(self) -> None:
        """
        Phase 2: 并发抓取所有项目的详细信息
        
        使用进度管理器和浏览器池执行并发任务
        """
        # 创建进度管理器
        self.progress_manager = CrawlerProgress(max_workers=self.max_workers)
        
        # 执行并发抓取
        self.results = self.progress_manager.run_tasks(
            items=self.temp_links,
            task_func=self._process_single_program,
            task_name="抓取进度",
            phase_name="Phase 2"
        )
    
    def _process_single_program(self, item: Dict) -> tuple:
        """
        处理单个项目的详情页抓取
        
        使用浏览器池复用浏览器实例，提升性能
        
        参数:
            item (Dict): 包含 name 和 link 的项目信息
        
        返回:
            tuple: (结果字典, 耗时秒数)
        """
        item_start = time.time()
        
        # 创建结果模板
        result = self.create_result_template(item['name'], item['link'])
        
        # 从浏览器池获取实例
        with self.browser_pool.get_browser() as driver:
            try:
                # 访问项目详情页
                driver.get(item['link'])
                
                # 等待页面关键元素加载（减少超时时间）
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Start Date')]"))
                )
                
                # 抓取开始日期
                result["项目opendate"] = self._extract_start_date(driver)
                
                # 抓取截止日期
                result["项目deadline"] = self._extract_deadline(driver)
                
                # 抓取申请链接（优化后的流程）
                result["项目申请链接"] = self._extract_apply_link(driver)
                
            except Exception:
                pass
        
        duration = time.time() - item_start
        return result, duration
    
    def _extract_start_date(self, driver) -> str:
        """
        提取项目开始日期
        """
        try:
            elem = driver.find_element(
                By.XPATH, 
                "//*[contains(text(), 'Start Date')]/following-sibling::*"
            )
            return elem.text.strip()
        except Exception:
            return "N/A"
    
    def _extract_deadline(self, driver) -> str:
        """
        提取申请截止日期
        """
        try:
            elem = driver.find_element(
                By.XPATH, 
                "//*[contains(text(), 'Deadline')]/following-sibling::*"
            )
            # 处理多行文本，用 " | " 分隔
            return elem.text.strip().replace("\n", " | ")
        except Exception:
            return "N/A"
    
    def _extract_apply_link(self, driver) -> str:
        """
        提取在线申请链接（优化版）
        
        处理 HKU 复杂的多步骤申请流程：
        1. 点击 "Apply Now" 按钮 -> 打开项目说明页
        2. 在说明页点击 "Applying" (#a_application) -> 打开申请系统
        3. 获取最终的申请系统 URL
        """
        main_window = driver.current_window_handle
        final_url = "N/A"
        
        try:
            # Step 1: 找到并点击 Apply Now 按钮
            apply_btn = driver.find_element(By.XPATH, "//a[contains(text(), 'Apply Now')]")
            original_handles = set(driver.window_handles)
            
            safe_click(driver, apply_btn)
            
            # 等待新窗口（说明页）
            new_handle = wait_for_new_window(driver, original_handles, timeout=5)
            
            if not new_handle:
                # 没有新窗口，返回按钮的 href
                return apply_btn.get_attribute("href") or "N/A"
            
            # 切换到说明页窗口
            driver.switch_to.window(new_handle)
            time.sleep(0.5)  # 短暂等待页面加载
            
            # Step 2: 找到 #a_application 里的链接并点击
            try:
                # 等待 Applying 链接可点击
                applying_link = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "#a_application a"))
                )
                
                # 记录当前窗口
                handles_before = set(driver.window_handles)
                
                # 点击 Applying 链接（这会触发 online() JavaScript 函数）
                safe_click(driver, applying_link)
                
                # 等待申请系统窗口打开
                final_handle = wait_for_new_window(driver, handles_before, timeout=5)
                
                if final_handle:
                    # 新窗口打开了（申请系统页面）
                    driver.switch_to.window(final_handle)
                    time.sleep(0.5)
                    final_url = driver.current_url
                    driver.close()  # 关闭申请系统窗口
                else:
                    # 没有新窗口，当前页面可能就是申请页
                    final_url = driver.current_url
                    
            except Exception:
                # 没找到 Applying 链接，使用当前说明页 URL
                final_url = driver.current_url
                
        except Exception:
            pass
        finally:
            # 清理：关闭所有额外窗口，回到主窗口
            try:
                for handle in driver.window_handles:
                    if handle != main_window:
                        driver.switch_to.window(handle)
                        driver.close()
                driver.switch_to.window(main_window)
            except:
                pass
        
        return final_url
