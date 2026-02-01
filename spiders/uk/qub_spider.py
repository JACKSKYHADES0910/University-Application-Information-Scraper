# -*- coding: utf-8 -*-
"""
贝尔法斯特女王大学 (Queen's University Belfast) 爬虫模块
负责抓取 QUB Postgraduate Taught 项目信息
"""

import time
import re
from typing import List, Dict
from urllib.parse import urljoin, urlparse, parse_qs
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from spiders.base_spider import BaseSpider
from utils.browser import get_driver
from utils.progress import CrawlerProgress, print_phase_start, print_phase_complete
from utils.selenium_utils import BrowserPool, safe_click
from config import MAX_WORKERS, PAGE_LOAD_WAIT


class QUBSpider(BaseSpider):
    """
    贝尔法斯特女王大学爬虫
    
    负责从 Queen's University Belfast 官网爬取所有 Postgraduate Taught 项目的详细信息,包括:
    - 项目名称
    - 项目链接
    - 申请截止日期(如果有)
    - 统一的申请注册和登录链接
    
    使用示例:
        >>> with QUBSpider() as spider:
        ...     data = spider.run()
        ...     print(f"爬取了 {len(data)} 条数据")
    """
    
    def __init__(self, headless: bool = True, max_workers: int = None):
        """
        初始化 QUB 爬虫
        
        参数:
            headless (bool): 是否无头模式运行
            max_workers (int): 并发线程数,如果不指定则使用 config.py 中的配置
        """
        super().__init__("qub", headless)
        from config import MAX_WORKERS as CONFIG_MAX_WORKERS
        self.max_workers = max_workers if max_workers is not None else CONFIG_MAX_WORKERS
        self.temp_links: List[Dict] = []  # 临时存储项目链接列表
        self.progress_manager: CrawlerProgress = None  # 进度管理器
        self.browser_pool: BrowserPool = None  # 浏览器池
    
    def run(self) -> List[Dict]:
        """
        执行完整的爬取流程
        
        流程:
            1. Phase 1: 获取所有项目的列表(名称+链接) - 遍历分页
            2. Phase 2: 并发抓取每个项目的详细信息
        
        返回:
            List[Dict]: 所有项目的详细信息列表
        """
        self.start_time = time.time()
        self.results = []
        
        try:
            # Phase 1: 获取项目列表(遍历所有分页)
            self._fetch_program_list()
            
            if not self.temp_links:
                print("❌ 未找到任何项目链接")
                return []
            
            # 初始化浏览器池(Phase 2 使用)
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
        
        该方法会遍历所有分页,收集所有项目的基本信息
        QUB 使用 start_rank 参数进行分页,每页100条
        """
        print_phase_start(
            "Phase 1", 
            "正在扫描项目列表(分页模式)...",
            total=None
        )
        print(f"   📍 目标地址: {self.list_url}")
        
        try:
            page_num = 1
            start_rank = 1
            
            while True:
                # 构建分页URL
                if page_num == 1:
                    url = self.list_url
                else:
                    url = f"{self.list_url}&start_rank={start_rank}"
                
                print(f"   📄 正在访问第 {page_num} 页...")
                
                # 访问页面
                self.driver.get(url)
                time.sleep(2)  # 等待页面加载
                
                # 第一页时需要处理cookie banner
                if page_num == 1:
                    self._handle_cookie_banner()
                
                # 等待课程列表加载 - 使用正确的选择器
                try:
                    WebDriverWait(self.driver, PAGE_LOAD_WAIT).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.search-results'))
                    )
                except TimeoutException:
                    # 尝试备用选择器
                    try:
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="search.qub.ac.uk/s/redirect"]'))
                        )
                    except TimeoutException:
                        print(f"   ⚠️ 第 {page_num} 页加载超时,可能已到达最后一页")
                        break
                
                # 提取当前页面的所有项目
                before_count = len(self.temp_links)
                self._extract_programs_from_current_page()
                after_count = len(self.temp_links)
                new_count = after_count - before_count
                
                print(f"   📄 第 {page_num} 页: 发现 {new_count} 个项目 (累计: {after_count})")
                
                # 如果没有新项目,说明已到达最后一页
                if new_count == 0:
                    print(f"   ✅ 已到达最后一页")
                    break
                
                # 检查是否有下一页
                if not self._has_next_page():
                    print(f"   ✅ 已到达最后一页")
                    break
                
                # 准备下一页
                page_num += 1
                start_rank += 100
                
                # 短暂休息,避免请求过快
                time.sleep(0.5)
            
            print_phase_complete("Phase 1", len(self.temp_links))
            
        except Exception as e:
            print(f"❌ 获取项目列表失败: {e}")
    
    def _handle_cookie_banner(self) -> None:
        """处理Cookie横幅"""
        try:
            # 尝试多种可能的Cookie接受按钮
            selectors = [
                "//button[contains(text(), 'Accept')]",
                "//button[contains(text(), 'accept')]",
                "//button[contains(@class, 'accept')]",
                "//a[contains(text(), 'Accept')]",
                "//button[@id='onetrust-accept-btn-handler']"
            ]
            
            for selector in selectors:
                try:
                    cookie_btn = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    cookie_btn.click()
                    print("   🍪 已接受Cookie")
                    time.sleep(1)
                    return
                except TimeoutException:
                    continue
                    
        except Exception as e:
            # Cookie横幅可能不存在或已被接受
            pass
    
    def _has_next_page(self) -> bool:
        """检查是否有下一页"""
        try:
            # 查找分页导航中的下一页按钮或链接
            next_selectors = [
                "//a[contains(@class, 'next')]",
                "//li[contains(@class, 'next')]/a",
                "//a[@aria-label='Next']",
                "//a[contains(text(), '→')]",
                "//a[contains(text(), '>')]"
            ]
            
            for selector in next_selectors:
                try:
                    next_btn = self.driver.find_element(By.XPATH, selector)
                    if next_btn.is_displayed() and next_btn.is_enabled():
                        return True
                except NoSuchElementException:
                    continue
            
            # 备用方案: 检查分页数字
            try:
                pagination = self.driver.find_element(By.CSS_SELECTOR, '.pagination, [class*="paging"]')
                current_page = pagination.find_element(By.CSS_SELECTOR, '.active, [aria-current="page"]')
                # 检查是否还有后续页码
                all_pages = pagination.find_elements(By.CSS_SELECTOR, 'a')
                return len(all_pages) > 0
            except NoSuchElementException:
                pass
            
            return False
            
        except Exception:
            return False
    
    def _extract_programs_from_current_page(self) -> None:
        """
        从当前页面提取项目信息
        
        QUB 使用 Funnelback 搜索引擎,课程链接结构:
        - 选择器: ul.search-results h4 a
        - 真实URL: 在链接的 title 属性中
        - href: 是 search.qub.ac.uk/s/redirect 重定向链接
        """
        # 去重处理
        seen_urls = set()
        
        # 方法1: 使用正确的选择器 - ul.search-results h4 a
        course_links = self.driver.find_elements(
            By.CSS_SELECTOR, 
            'ul.search-results h4 a'
        )
        
        # 如果没找到,尝试备用选择器
        if not course_links:
            course_links = self.driver.find_elements(
                By.CSS_SELECTOR, 
                'h4 a[href*="search.qub.ac.uk/s/redirect"]'
            )
        
        # 如果还是没找到,尝试更宽泛的选择器
        if not course_links:
            course_links = self.driver.find_elements(
                By.CSS_SELECTOR,
                'a[href*="search.qub.ac.uk/s/redirect"]'
            )
        
        for link in course_links:
            try:
                # 获取课程名称
                name = link.text.strip()
                
                if not name or len(name) < 3:
                    continue
                    
                # 过滤无效的链接文本
                if name.lower() in ['next', 'previous', '>', '<', '1', '2', '3', '→']:
                    continue
                
                # 优先从 title 属性获取真实URL
                real_url = link.get_attribute("title")
                
                # 如果 title 为空,从 href 的 url 参数中提取
                if not real_url or not real_url.startswith('http'):
                    href = link.get_attribute("href")
                    if href:
                        real_url = self._extract_real_url(href)
                
                if not real_url:
                    continue
                
                # 确保URL格式正确
                if not real_url.startswith('http'):
                    continue
                    
                # 跳过已处理的URL
                if real_url in seen_urls:
                    continue
                seen_urls.add(real_url)
                
                # 去重检查 (与已有列表比对)
                if not any(d['link'] == real_url for d in self.temp_links):
                    self.temp_links.append({
                        "name": name,
                        "link": real_url
                    })
                    
            except Exception:
                continue
    
    def _extract_real_url(self, url: str) -> str:
        """
        从重定向URL中提取真实的课程URL
        
        QUB的搜索结果链接格式:
        https://search.qub.ac.uk/s/redirect?...&url=https%3A%2F%2Fwww.qub.ac.uk%2Fcourses%2F...
        """
        try:
            if 'search.qub.ac.uk/s/redirect' in url:
                # 解析查询参数获取真实URL
                from urllib.parse import urlparse, parse_qs, unquote
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                if 'url' in params:
                    return unquote(params['url'][0])
            return url
        except Exception:
            return url
    
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
        
        使用浏览器池复用浏览器实例,提升性能
        
        参数:
            item (Dict): 包含 name 和 link 的项目信息
        
        返回:
            tuple: (结果字典, 耗时秒数)
        """
        item_start = time.time()
        
        # 创建结果模板
        result = self.create_result_template(item['name'], item['link'])
        
        # 设置统一的申请链接(从配置读取)
        result["申请链接"] = self.university_info.get("apply_register_url", "N/A")
        
        # 从浏览器池获取实例
        with self.browser_pool.get_browser() as driver:
            try:
                # 访问项目详情页
                driver.get(item['link'])
                
                # 等待页面加载
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "main"))
                )
                
                # 抓取deadline信息
                result["项目deadline"] = self._extract_deadline(driver)
                
                # 尝试抓取开放日期
                result["项目opendate"] = self._extract_open_date(driver)
                
            except TimeoutException:
                # 详情页加载超时,保持N/A
                pass
            except Exception:
                # 其他错误,保持N/A
                pass
        
        duration = time.time() - item_start
        return result, duration
    
    def _extract_deadline(self, driver) -> str:
        """
        提取申请截止日期
        """
        try:
            # 查找包含deadline关键词的元素
            keywords = ['deadline', 'closing date', 'application close', 'apply by']
            
            for keyword in keywords:
                try:
                    elements = driver.find_elements(
                        By.XPATH, 
                        f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{keyword}')]"
                    )
                    
                    for elem in elements:
                        text = elem.text.strip()
                        if text and len(text) > 5 and len(text) < 500:
                            # 尝试找到日期信息
                            parent = elem.find_element(By.XPATH, "./..")
                            parent_text = parent.text.strip()
                            if parent_text and len(parent_text) < 500:
                                return parent_text
                            return text
                            
                except NoSuchElementException:
                    continue
            
            # 备用方案: 查找 "How to apply" 或 "Apply" 部分
            try:
                apply_section = driver.find_element(
                    By.XPATH, 
                    "//h2[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]/.."
                )
                section_text = apply_section.text
                
                lines = section_text.split('\n')
                for line in lines:
                    if 'deadline' in line.lower() or 'date' in line.lower():
                        return line.strip()
                        
            except NoSuchElementException:
                pass
            
            return "N/A"
            
        except Exception:
            return "N/A"
    
    def _extract_open_date(self, driver) -> str:
        """
        提取申请开放日期
        """
        try:
            keywords = ['open date', 'opening date', 'applications open', 'apply from']
            
            for keyword in keywords:
                try:
                    elements = driver.find_elements(
                        By.XPATH, 
                        f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{keyword}')]"
                    )
                    
                    for elem in elements:
                        text = elem.text.strip()
                        if text and len(text) > 5 and len(text) < 300:
                            return text
                            
                except NoSuchElementException:
                    continue
            
            return "N/A"
            
        except Exception:
            return "N/A"


if __name__ == "__main__":
    # 测试代码
    with QUBSpider(headless=False) as spider:
        results = spider.run()
        
        print(f"\n抓取完成,共 {len(results)} 个项目")
        if results:
            import json
            print("\n前3个项目示例:")
            print(json.dumps(results[:3], indent=2, ensure_ascii=False))
