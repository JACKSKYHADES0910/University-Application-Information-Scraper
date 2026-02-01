# -*- coding: utf-8 -*-
"""
阿伯丁大学 (University of Aberdeen) 爬虫模块
负责抓取 Aberdeen Postgraduate Taught 项目信息
"""

import time
from typing import List, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from spiders.base_spider import BaseSpider
from utils.progress import CrawlerProgress, print_phase_start, print_phase_complete
from utils.selenium_utils import BrowserPool
from config import MAX_WORKERS, PAGE_LOAD_WAIT


class AberdeenSpider(BaseSpider):
    """
    阿伯丁大学爬虫
    
    负责从 University of Aberdeen 官网爬取所有 Postgraduate Taught 项目的详细信息,包括:
    - 项目名称
    - 项目链接
    - 申请截止日期(如果有)
    - 统一的申请注册和登录链接
    
    使用示例:
        >>> with AberdeenSpider() as spider:
        ...     data = spider.run()
        ...     print(f"爬取了 {len(data)} 条数据")
    """
    
    def __init__(self, headless: bool = True, max_workers: int = None):
        """
        初始化 Aberdeen 爬虫
        
        参数:
            headless (bool): 是否无头模式运行
            max_workers (int): 并发线程数,如果不指定则使用 config.py 中的配置
        """
        super().__init__("aberdeen", headless)
        from config import MAX_WORKERS as CONFIG_MAX_WORKERS
        self.max_workers = max_workers if max_workers is not None else CONFIG_MAX_WORKERS
        self.temp_links: List[Dict] = []  # 临时存储项目链接列表
        self.progress_manager: CrawlerProgress = None  # 进度管理器
        self.browser_pool: BrowserPool = None  # 浏览器池
    
    def run(self) -> List[Dict]:
        """
        执行完整的爬取流程
        
        流程:
            1. Phase 1: 获取所有项目的列表(名称+链接) - 使用 limit=All
            2. Phase 2: 并发抓取每个项目的详细信息
        
        返回:
            List[Dict]: 所有项目的详细信息列表
        """
        self.start_time = time.time()
        self.results = []
        
        try:
            # Phase 1: 获取项目列表(一次性获取全部)
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
        
        该方法使用 limit=All 参数一次性获取所有项目
        Aberdeen 网站的列表页使用表格展示,每行包含项目名称和链接
        """
        print_phase_start(
            "Phase 1", 
            "正在扫描项目列表...",
            total=None
        )
        print(f"   📍 目标地址: {self.list_url}")
        
        try:
            # 访问页面
            self.driver.get(self.list_url)
            time.sleep(3)  # 等待页面加载
            
            # 处理可能的Cookie横幅
            self._handle_cookie_banner()
            
            # 等待表格加载
            try:
                WebDriverWait(self.driver, PAGE_LOAD_WAIT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'table.programme-list, .degree-listing, table'))
                )
            except TimeoutException:
                print("   ⚠️ 表格加载超时,尝试继续...")
            
            # 提取所有项目
            self._extract_programs_from_page()
            
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
                "//button[@id='onetrust-accept-btn-handler']",
                "//button[contains(text(), 'OK')]",
                "//button[contains(text(), 'Agree')]"
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
                    
        except Exception:
            # Cookie横幅可能不存在或已被接受
            pass
    
    def _extract_programs_from_page(self) -> None:
        """
        从当前页面提取项目信息
        
        Aberdeen 使用表格展示项目列表,每行包含:
        - 项目名称(链接)
        - 学位类型
        - 学习类型
        """
        # 去重处理
        seen_urls = set()
        
        # 方法1: 查找表格中的项目链接
        # Aberdeen 网站表格中项目链接格式: /study/postgraduate-taught/degree-programmes/{id}/{name}/
        program_selectors = [
            'table tbody tr td a[href*="/degree-programmes/"]',
            'a[href*="/study/postgraduate-taught/degree-programmes/"]',
            '.programme-list a[href*="/degree-programmes/"]',
            'table a[href*="/degree-programmes/"]'
        ]
        
        course_links = []
        for selector in program_selectors:
            course_links = self.driver.find_elements(By.CSS_SELECTOR, selector)
            if course_links:
                break
        
        print(f"   📊 发现 {len(course_links)} 个链接元素")
        
        for link in course_links:
            try:
                # 获取课程名称
                name = link.text.strip()
                href = link.get_attribute("href")
                
                if not name or len(name) < 3:
                    continue
                    
                if not href:
                    continue
                
                # 过滤无效的链接
                if '/degree-programmes/' not in href:
                    continue
                
                # 过滤分页和排序链接
                if '?page=' in href or '?limit=' in href or '?order_by=' in href or '?direction=' in href:
                    continue
                    
                # 过滤导航链接
                invalid_texts = ['next', 'previous', 'view all', 'simple view', 'detailed view', 
                                '1', '2', '3', '4', '5', '6', '7', '8', '→', '←', '>>', '<<']
                if name.lower() in invalid_texts:
                    continue
                
                # 跳过已处理的URL
                if href in seen_urls:
                    continue
                seen_urls.add(href)
                
                # 确保URL格式正确
                if not href.startswith('http'):
                    href = f"{self.base_url}{href}" if not href.startswith('/') else f"{self.base_url}{href}"
                
                # 去重检查 (与已有列表比对)
                if not any(d['link'] == href for d in self.temp_links):
                    self.temp_links.append({
                        "name": name,
                        "link": href
                    })
                    
            except Exception:
                continue
    
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
            keywords = ['deadline', 'closing date', 'application close', 'apply by', 'applications close']
            
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
            keywords = ['open date', 'opening date', 'applications open', 'apply from', 'start date']
            
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
    with AberdeenSpider(headless=False) as spider:
        results = spider.run()
        
        print(f"\n抓取完成,共 {len(results)} 个项目")
        if results:
            import json
            print("\n前3个项目示例:")
            print(json.dumps(results[:3], indent=2, ensure_ascii=False))
