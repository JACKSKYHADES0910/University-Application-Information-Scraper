# -*- coding: utf-8 -*-
"""
曼彻斯特大学 (The University of Manchester) 爬虫模块
负责抓取 Manchester Taught Master Programme 项目信息
"""

import time
from typing import List, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from spiders.base_spider import BaseSpider
from utils.browser import get_driver
from utils.progress import CrawlerProgress, print_phase_start, print_phase_complete
from utils.selenium_utils import BrowserPool, safe_click
from config import MAX_WORKERS, PAGE_LOAD_WAIT


class ManchesterSpider(BaseSpider):
    """
    曼彻斯特大学爬虫
    
    负责从 Manchester 官网爬取所有 Taught Master 项目的详细信息,包括:
    - 项目名称
    - 项目链接
    - 学位类型 (MSc, MA, etc.)
    - 课程时长
    - 申请截止日期(如果有)
    - 统一的申请注册和登录链接
    
    使用示例:
        >>> with ManchesterSpider() as spider:
        ...     data = spider.run()
        ...     print(f"爬取了 {len(data)} 条数据")
    """
    
    def __init__(self, headless: bool = True, max_workers: int = None):
        """
        初始化 Manchester 爬虫
        
        参数:
            headless (bool): 是否无头模式运行
            max_workers (int): 并发线程数,如果不指定则使用 config.py 中的配置
        """
        super().__init__("manchester", headless)
        from config import MAX_WORKERS as CONFIG_MAX_WORKERS
        self.max_workers = max_workers if max_workers is not None else CONFIG_MAX_WORKERS
        self.temp_links: List[Dict] = []  # 临时存储项目链接列表
        self.progress_manager: CrawlerProgress = None  # 进度管理器
        self.browser_pool: BrowserPool = None  # 浏览器池
    
    def run(self) -> List[Dict]:
        """
        执行完整的爬取流程
        
        流程:
            1. Phase 1: 获取所有项目的列表(名称+链接) - 需要滚动加载
            2. Phase 2: 并发抓取每个项目的详细信息
        
        返回:
            List[Dict]: 所有项目的详细信息列表
        """
        self.start_time = time.time()
        self.results = []
        
        try:
            # Phase 1: 获取项目列表(滚动加载所有课程)
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
        
        该方法会滚动页面以触发懒加载,收集所有项目的基本信息
        """
        print_phase_start(
            "Phase 1", 
            "正在扫描项目列表(懒加载模式)...",
            total=None
        )
        print(f"   📍 目标地址: {self.list_url}")
        
        try:
            # 访问列表页
            self.driver.get(self.list_url)
            time.sleep(3)  # 等待初始加载
            
            # 处理Cookie横幅
            self._handle_cookie_banner()
            
            # 等待课程列表容器加载
            try:
                WebDriverWait(self.driver, PAGE_LOAD_WAIT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.course-list'))
                )
            except TimeoutException:
                print("   ⚠️ 课程列表加载超时")
                return
            
            # 滚动页面以加载所有课程(懒加载)
            self._scroll_to_load_all()
            
            # 提取所有课程
            self._extract_all_programs()
            
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
                "//a[contains(text(), 'Accept')]"
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
    
    def _scroll_to_load_all(self) -> None:
        """
        滚动页面以触发懒加载,加载所有课程
        """
        print("   📜 正在滚动页面加载所有课程...")
        
        last_count = 0
        max_scroll_attempts = 30  # 最大滚动次数
        stable_count = 0  # 连续稳定次数
        
        for attempt in range(max_scroll_attempts):
            # 滚动到页面底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)  # 等待加载
            
            # 统计当前课程数量
            courses = self.driver.find_elements(By.CSS_SELECTOR, "ul.course-list li")
            current_count = len(courses)
            
            if current_count == last_count:
                stable_count += 1
                if stable_count >= 3:  # 连续3次数量不变,认为加载完成
                    break
            else:
                stable_count = 0
                print(f"   📄 已加载 {current_count} 个课程...")
            
            last_count = current_count
        
        print(f"   ✅ 加载完成,共发现 {last_count} 个课程")
    
    def _extract_all_programs(self) -> None:
        """
        从当前页面提取所有项目信息
        """
        # 获取所有课程行
        courses = self.driver.find_elements(By.CSS_SELECTOR, "ul.course-list li")
        
        for course in courses:
            try:
                # 提取标题和链接
                title_elem = course.find_element(By.CSS_SELECTOR, "div.title a")
                name = title_elem.text.strip()
                link = title_elem.get_attribute("href")
                
                if not name or not link:
                    continue
                
                # 提取学位类型
                try:
                    degree = course.find_element(By.CSS_SELECTOR, "div.degree").text.strip()
                except NoSuchElementException:
                    degree = "N/A"
                
                # 提取时长
                try:
                    duration = course.find_element(By.CSS_SELECTOR, "div.duration").text.strip()
                except NoSuchElementException:
                    duration = "N/A"
                
                # 去重检查
                if not any(d['link'] == link for d in self.temp_links):
                    self.temp_links.append({
                        "name": name,
                        "link": link,
                        "degree": degree,
                        "duration": duration
                    })
                    
            except NoSuchElementException:
                continue
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
            item (Dict): 包含 name, link, degree, duration 的项目信息
        
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
        
        从 "Application and selection" 部分提取deadline信息
        Manchester使用分阶段录取,会有多个deadline
        """
        try:
            # 尝试找到Application and selection部分
            page_text = driver.page_source.lower()
            
            # 查找包含staged admissions的部分
            try:
                # 查找包含deadline信息的元素
                elements = driver.find_elements(By.XPATH, 
                    "//*[contains(text(), 'Stage 1') or contains(text(), 'deadline') or contains(text(), 'Deadline')]"
                )
                
                for elem in elements:
                    text = elem.text.strip()
                    if text and ('stage' in text.lower() or 'deadline' in text.lower()):
                        # 返回找到的第一个有效deadline信息
                        if len(text) > 10 and len(text) < 500:
                            return text
                            
            except NoSuchElementException:
                pass
            
            # 备选方案: 查找"How to apply"部分
            try:
                apply_section = driver.find_element(By.XPATH, 
                    "//h2[contains(text(), 'Application')]/.."
                )
                section_text = apply_section.text
                
                # 查找deadline相关行
                lines = section_text.split('\n')
                for line in lines:
                    if 'deadline' in line.lower() or 'stage' in line.lower():
                        return line.strip()
                        
            except NoSuchElementException:
                pass
            
            return "N/A"
            
        except Exception:
            return "N/A"


if __name__ == "__main__":
    # 测试代码
    with ManchesterSpider(headless=False) as spider:
        results = spider.run()
        
        print(f"\n抓取完成,共 {len(results)} 个项目")
        if results:
            import json
            print("\n前3个项目示例:")
            print(json.dumps(results[:3], indent=2, ensure_ascii=False))
