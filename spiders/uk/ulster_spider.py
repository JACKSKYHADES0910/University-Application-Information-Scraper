# -*- coding: utf-8 -*-
"""
阿尔斯特大学 (Ulster University) 爬虫模块
负责抓取 Ulster Postgraduate 项目信息
"""

import time
import re
from typing import List, Dict
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from spiders.base_spider import BaseSpider
from utils.browser import get_driver
from utils.progress import CrawlerProgress, print_phase_start, print_phase_complete
from utils.selenium_utils import BrowserPool, safe_click
from config import MAX_WORKERS, PAGE_LOAD_WAIT


class UlsterSpider(BaseSpider):
    """
    阿尔斯特大学爬虫
    
    负责从 Ulster University 官网爬取所有 Postgraduate 项目的详细信息,包括:
    - 项目名称
    - 项目链接
    - 开始日期
    - 申请截止日期(如果有)
    - 统一的申请注册和登录链接
    
    使用示例:
        >>> with UlsterSpider() as spider:
        ...     data = spider.run()
        ...     print(f"爬取了 {len(data)} 条数据")
    """
    
    def __init__(self, headless: bool = True, max_workers: int = None):
        """
        初始化 Ulster 爬虫
        
        参数:
            headless (bool): 是否无头模式运行
            max_workers (int): 并发线程数,如果不指定则使用 config.py 中的配置
        """
        super().__init__("ulster", headless)
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
                print("❌ 未找到任何项目链接", flush=True)
                return []
            
            # 初始化浏览器池(Phase 2 使用)
            self.browser_pool = BrowserPool(size=self.max_workers, headless=True)
            self.browser_pool.initialize()
            
            # Phase 2: 并发抓取详情
            self._fetch_program_details()
            
        except KeyboardInterrupt:
            print("\n⚠️ 用户中断了爬取", flush=True)
        except Exception as e:
            print(f"❌ 爬取过程中发生错误: {e}", flush=True)
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
        Ulster 使用 start_rank 参数进行分页,每页40条
        """
        print_phase_start(
            "Phase 1", 
            "正在扫描项目列表(分页模式)...",
            total=None
        )
        print(f"   📍 目标地址: {self.list_url}", flush=True)
        
        try:
            page_num = 1
            start_rank = 1
            
            while True:
                # 构建分页URL
                if page_num == 1:
                    url = self.list_url
                else:
                    # 替换URL中的start_rank参数
                    url = re.sub(r'start_rank=\d+', f'start_rank={start_rank}', self.list_url)
                
                print(f"   📄 正在访问第 {page_num} 页...", flush=True)
                
                # 访问页面
                self.driver.get(url)
                time.sleep(2)  # 等待页面加载
                
                # 第一页时需要处理cookie banner
                if page_num == 1:
                    self._handle_cookie_banner()
                
                # 等待课程列表加载
                try:
                    WebDriverWait(self.driver, PAGE_LOAD_WAIT).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '.course-search-alpha__results'))
                    )
                except TimeoutException:
                    print(f"   ⚠️ 第 {page_num} 页加载超时,可能已到达最后一页", flush=True)
                    break
                
                # 提取当前页面的所有项目
                before_count = len(self.temp_links)
                self._extract_programs_from_current_page()
                after_count = len(self.temp_links)
                new_count = after_count - before_count
                
                print(f"   📄 第 {page_num} 页: 发现 {new_count} 个项目 (累计: {after_count})", flush=True)
                
                # 如果没有新项目,说明已到达最后一页
                if new_count == 0:
                    print(f"   ✅ 已到达最后一页", flush=True)
                    break
                
                # 检查是否有下一页
                if not self._has_next_page():
                    print(f"   ✅ 已到达最后一页", flush=True)
                    break
                
                # 准备下一页
                page_num += 1
                start_rank += 40  # Ulster每页40条
                
                # 短暂休息,避免请求过快
                time.sleep(0.5)
            
            print_phase_complete("Phase 1", len(self.temp_links))
            
        except Exception as e:
            print(f"❌ 获取项目列表失败: {e}", flush=True)
    
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
                "//button[contains(@class, 'cookie')]"
            ]
            
            for selector in selectors:
                try:
                    cookie_btn = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    cookie_btn.click()
                    print("   🍪 已接受Cookie", flush=True)
                    time.sleep(1)
                    return
                except TimeoutException:
                    continue
                    
        except Exception as e:
            # Cookie横幅可能不存在或已被接受
            pass
    
    def _has_next_page(self) -> bool:
        """
        检查是否有下一页
        
        Ulster的分页按钮结构:
        - 激活状态: <a> 标签,包含 <img alt="Pagination right icon">
        - 禁用状态: <div> 标签,class包含 --inactive,包含 <img alt="Pagination right icon deactivated">
        """
        try:
            # 查找包含 "Pagination right icon" 的右箭头按钮
            # 如果是 <a> 标签,说明可以点击(有下一页)
            # 如果是 <div> 标签,说明已禁用(最后一页)
            next_button = self.driver.find_elements(
                By.CSS_SELECTOR,
                'a.course-search-alpha__pagination__link'
            )
            
            # 检查是否存在激活的下一页链接
            for btn in next_button:
                try:
                    # 查找包含右箭头图标的按钮
                    img = btn.find_element(By.CSS_SELECTOR, 'img[alt*="right"]')
                    if img and 'deactivated' not in img.get_attribute('alt').lower():
                        return True
                except NoSuchElementException:
                    continue
            
            return False
            
        except Exception:
            return False
    
    def _extract_programs_from_current_page(self) -> None:
        """
        从当前页面提取项目信息
        
        Ulster 使用 Funnelback 搜索引擎,课程链接结构:
        - 选择器: .course-search-alpha__results__result
        - 标题: .course-search-alpha__results__heading
        - 链接: .course-search-alpha__results__result__link (Funnelback重定向)
        """
        # 去重处理
        seen_urls = set()
        
        # 查找所有课程项
        course_items = self.driver.find_elements(
            By.CSS_SELECTOR, 
            '.course-search-alpha__results__result'
        )
        
        for item in course_items:
            try:
                # 获取课程链接元素
                link_elem = item.find_element(
                    By.CSS_SELECTOR, 
                    '.course-search-alpha__results__result__link'
                )
                
                # 获取课程名称
                name_elem = item.find_element(
                    By.CSS_SELECTOR,
                    '.course-search-alpha__results__heading'
                )
                name = name_elem.text.strip()
                
                if not name or len(name) < 3:
                    continue
                
                # 获取链接href(这是Funnelback重定向URL)
                href = link_elem.get_attribute("href")
                
                if not href:
                    continue
                
                # 从Funnelback重定向URL中提取真实URL
                real_url = self._extract_real_url(href)
                
                if not real_url or not real_url.startswith('http'):
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
                    
            except NoSuchElementException:
                continue
            except Exception:
                continue
    
    def _extract_real_url(self, url: str) -> str:
        """
        从重定向URL中提取真实的课程URL
        
        Ulster的搜索结果链接格式:
        https://ulster-search.funnelback.squiz.cloud/s/redirect?...&url=https%3A%2F%2Fwww.ulster.ac.uk%2Fcourses%2F...
        """
        try:
            if 'funnelback' in url and '/redirect' in url:
                # 解析查询参数获取真实URL
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
                
                # 抓取start date信息
                result["项目opendate"] = self._extract_start_date(driver)
                
                # 抓取学院信息
                result["学院/学习领域"] = self._extract_faculty(driver)
                
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
    
    def _extract_start_date(self, driver) -> str:
        """
        提取开始日期
        
        从课程信息栏中提取 Start Date
        Selector: .ulster-course-info-bar__item__value
        """
        try:
            # 查找包含 "Start Date" 的信息项
            info_items = driver.find_elements(
                By.CSS_SELECTOR,
                '.ulster-course-info-bar__item'
            )
            
            for item in info_items:
                try:
                    label = item.find_element(By.CSS_SELECTOR, '.ulster-course-info-bar__item__label')
                    if 'start date' in label.text.lower():
                        value = item.find_element(By.CSS_SELECTOR, '.ulster-course-info-bar__item__value')
                        date_text = value.text.strip()
                        if date_text:
                            return date_text
                except NoSuchElementException:
                    continue
            
            # 备用方案: 直接查找所有值元素
            try:
                values = driver.find_elements(
                    By.CSS_SELECTOR,
                    '.ulster-course-info-bar__item__value'
                )
                # 通常Start Date是第三个值
                if len(values) >= 3:
                    return values[2].text.strip()
            except Exception:
                pass
            
            return "N/A"
            
        except Exception:
            return "N/A"
    
    def _extract_faculty(self, driver) -> str:
        """
        提取学院/院系信息
        
        从课程详情页中查找包含 Faculty、School、College 等关键词的信息
        策略: 
        1. 查找面包屑导航
        2. 查找包含学院关键词的文本
        3. 从URL路径提取
        """
        try:
            # 策略1: 从面包屑导航提取学院信息
            try:
                breadcrumbs = driver.find_elements(
                    By.CSS_SELECTOR,
                    '.breadcrumb a, nav.breadcrumb a, .ulster-breadcrumb a'
                )
                # 通常学院在第2或第3个位置
                for crumb in breadcrumbs[1:4]:
                    text = crumb.text.strip()
                    if text and any(keyword in text.lower() for keyword in ['faculty', 'school', 'college']):
                        return text
                # 如果没有明确的学院关键词，取第二个breadcrumb（通常是学院）
                if len(breadcrumbs) >= 2:
                    text = breadcrumbs[1].text.strip()
                    if text and len(text) > 3:
                        return text
            except Exception:
                pass
            
            # 策略2: 查找包含Faculty/School关键词的元素
            try:
                faculty_elements = driver.find_elements(
                    By.XPATH,
                    "//*[contains(text(), 'Faculty') or contains(text(), 'School') or contains(text(), 'College')]"
                )
                for elem in faculty_elements:
                    text = elem.text.strip()
                    # 确保不是太长的段落
                    if text and 10 < len(text) < 100:
                        # 过滤掉一些常见的非学院文本
                        if not any(exclude in text.lower() for exclude in ['contact', 'email', 'apply', 'deadline', 'start', '@']):
                            return text
            except Exception:
                pass
            
            # 策略3: 从URL中提取学院信息
            try:
                url = driver.current_url
                # Ulster的URL格式通常是: /courses/201234/msc-xxx
                # 有时候会有: /faculties/art-design-built-environment/courses/...
                if '/faculties/' in url:
                    parts = url.split('/faculties/')[1].split('/')[0]
                    # 转换URL格式为可读文本 (例如: art-design-built-environment -> Art Design Built Environment)
                    faculty_name = parts.replace('-', ' ').title()
                    return faculty_name
            except Exception:
                pass
            
            return "N/A"
            
        except Exception:
            return "N/A"
    
    def _extract_deadline(self, driver) -> str:
        """
        提取申请截止日期
        
        从课程内容中查找包含 "closing date" 的段落
        Selector: .ulster-course-tabs__tabs__content p
        """
        try:
            # 查找包含deadline关键词的段落
            keywords = ['closing date', 'deadline', 'application close', 'apply by']
            
            # 查找所有段落
            paragraphs = driver.find_elements(
                By.CSS_SELECTOR,
                '.ulster-course-tabs__tabs__content p'
            )
            
            for keyword in keywords:
                for para in paragraphs:
                    text = para.text.strip()
                    if keyword in text.lower() and len(text) < 500:
                        # 找到包含关键词的段落
                        return text
            
            # 备用方案: 查找特定的日期模式
            for para in paragraphs:
                text = para.text.strip()
                # 查找类似 "28th February 2026" 的日期
                if re.search(r'\d{1,2}(st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}', text):
                    if len(text) < 500:
                        return text
            
            return "N/A"
            
        except Exception:
            return "N/A"


if __name__ == "__main__":
    # 测试代码
    with UlsterSpider(headless=False) as spider:
        results = spider.run()
        
        print(f"\n抓取完成,共 {len(results)} 个项目")
        if results:
            import json
            print("\n前3个项目示例:")
            print(json.dumps(results[:3], indent=2, ensure_ascii=False))
