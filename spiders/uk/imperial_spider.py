# -*- coding: utf-8 -*-
"""
伦敦帝国学院 (Imperial College London) 爬虫模块
负责抓取 Imperial College Postgraduate Taught 项目信息
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


class ImperialSpider(BaseSpider):
    """
    伦敦帝国学院爬虫
    
    负责从 Imperial College 官网爬取所有 Postgraduate Taught 项目的详细信息,包括:
    - 项目名称
    - 项目链接
    - 申请截止日期(如果有)
    - 统一的申请注册和登录链接
    
    使用示例:
        >>> with ImperialSpider() as spider:
        ...     data = spider.run()
        ...     print(f"爬取了 {len(data)} 条数据")
    """
    
    def __init__(self, headless: bool = True, max_workers: int = None):
        """
        初始化 Imperial 爬虫
        
        参数:
            headless (bool): 是否无头模式运行
            max_workers (int): 并发线程数,如果不指定则使用 config.py 中的配置
        """
        super().__init__("imperial", headless)
        from config import MAX_WORKERS as CONFIG_MAX_WORKERS
        self.max_workers = max_workers if max_workers is not None else CONFIG_MAX_WORKERS
        self.temp_links: List[Dict] = []  # 临时存储项目链接列表
        self.progress_manager: CrawlerProgress = None  # 进度管理器
        self.browser_pool: BrowserPool = None  # 浏览器池
    
    def run(self) -> List[Dict]:
        """
        执行完整的爬取流程
        
        流程:
            1. Phase 1: 获取所有项目的列表(名称+链接)- 遍历15页
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
        
        该方法会遍历所有15页分页,收集所有项目的基本信息
        """
        print_phase_start(
            "Phase 1", 
            "正在扫描项目列表(共15页)...",
            total=None
        )
        print(f"   📍 目标地址: {self.list_url}")
        
        try:
            # 遍历15页(根据官网探索结果)
            for page_num in range(1, 16):
                # 构建页面URL
                if page_num == 1:
                    url = self.list_url
                else:
                    url = f"{self.list_url}&page={page_num}"
                
                print(f"   📄 正在访问第 {page_num}/15 页...")
                
                # 访问页面
                self.driver.get(url)
                time.sleep(2)  # 等待页面加载
                
                # 第一页时需要处理cookie banner
                if page_num == 1:
                    self._handle_cookie_banner()
                
                # 等待项目卡片加载完成
                try:
                    WebDriverWait(self.driver, PAGE_LOAD_WAIT).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '.course-card'))
                    )
                except TimeoutException:
                    print(f"   ⚠️ 第 {page_num} 页加载超时,跳过...")
                    continue
                
                # 提取当前页面的所有项目
                before_count = len(self.temp_links)
                self._extract_programs_from_current_page()
                after_count = len(self.temp_links)
                
                print(f"   📄 第 {page_num} 页: 发现 {after_count - before_count} 个项目 (累计: {after_count})")
                
                # 短暂休息,避免请求过快
                time.sleep(0.5)
            
            print_phase_complete("Phase 1", len(self.temp_links))
            
        except Exception as e:
            print(f"❌ 获取项目列表失败: {e}")
    
    def _handle_cookie_banner(self) -> None:
        """处理Cookie横幅,点击Accept All Cookies"""
        try:
            # 等待cookie横幅出现
            cookie_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept All Cookies')]"))  
            )
            cookie_btn.click()
            print("   🍪 已接受Cookie")
            time.sleep(1)
        except TimeoutException:
            # Cookie横幅可能已经被接受过了
            pass
        except Exception as e:
            print(f"   ⚠️ Cookie处理失败: {e}")
    
    def _extract_programs_from_current_page(self) -> None:
        """
        从当前页面提取项目信息
        """
        # 使用从官网探索得到的CSS选择器
        cards = self.driver.find_elements(By.CSS_SELECTOR, ".course-card")
        
        for card in cards:
            try:
                # 提取项目名称和链接
                title_elem = card.find_element(By.CSS_SELECTOR, "h4.course-card__title a")
                name = title_elem.text.strip()
                link = title_elem.get_attribute("href")
                
                if not name or not link:
                    continue
                
                # 去重检查
                if not any(d['link'] == link for d in self.temp_links):
                    self.temp_links.append({
                        "name": name,
                        "link": link
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
            item (Dict): 包含 name 和 link 的项目信息
        
        返回:
            tuple: (结果字典, 耗时秒数)
        """
        item_start = time.time()
        
        # 创建结果模板
        result = self.create_result_template(item['name'], item['link'])
        
        # 设置统一的申请链接(从配置读取)
        result["申请注册链接"] = self.university_info.get("apply_register_url", "N/A")
        result["申请登录链接"] = self.university_info.get("apply_login_url", "N/A")
        
        # 从浏览器池获取实例
        with self.browser_pool.get_browser() as driver:
            try:
                # 访问项目详情页
                driver.get(item['link'])
                
                # 等待页面关键元素加载
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "course-how-to-apply-id"))
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
        
        从 "How to apply" 部分提取deadline信息
        """
        try:
            # 定位到How to apply部分
            section = driver.find_element(By.ID, "course-how-to-apply-id")
            text = section.text
            
            # 查找包含deadline的行
            lines = text.split('\n')
            for line in lines:
                if 'deadline' in line.lower() or 'closes on' in line.lower():
                    return line.strip()
            
            # 如果没找到明确的deadline,返回N/A
            return "N/A"
            
        except NoSuchElementException:
            return "N/A"
        except Exception:
            return "N/A"


if __name__ == "__main__":
    # 测试代码
    with ImperialSpider(headless=False) as spider:
        results = spider.run()
        
        print(f"\n抓取完成,共 {len(results)} 个项目")
        if results:
            import json
            print("\n前3个项目示例:")
            print(json.dumps(results[:3], indent=2, ensure_ascii=False))
