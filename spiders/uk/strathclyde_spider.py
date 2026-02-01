# -*- coding: utf-8 -*-
"""
斯特拉斯克莱德大学 (University of Strathclyde) 爬虫模块
负责抓取 Strathclyde Postgraduate Taught 项目信息
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


class StrathclydeSpider(BaseSpider):
    """
    斯特拉斯克莱德大学爬虫
    
    负责从 University of Strathclyde 官网爬取所有 Postgraduate Taught 项目的详细信息,包括:
    - 项目名称
    - 项目链接
    - 课程开始日期
    - 统一的申请注册和登录链接
    
    网站特点:
    - 使用无限滚动加载课程列表
    - 约 239 个研究生授课项目
    
    使用示例:
        >>> with StrathclydeSpider() as spider:
        ...     data = spider.run()
        ...     print(f"爬取了 {len(data)} 条数据")
    """
    
    def __init__(self, headless: bool = True, max_workers: int = None):
        """
        初始化 Strathclyde 爬虫
        
        参数:
            headless (bool): 是否无头模式运行
            max_workers (int): 并发线程数,如果不指定则使用 config.py 中的配置
        """
        super().__init__("strathclyde", headless)
        from config import MAX_WORKERS as CONFIG_MAX_WORKERS
        self.max_workers = max_workers if max_workers is not None else CONFIG_MAX_WORKERS
        self.temp_links: List[Dict] = []  # 临时存储项目链接列表
        self.progress_manager: CrawlerProgress = None  # 进度管理器
        self.browser_pool: BrowserPool = None  # 浏览器池
    
    def run(self) -> List[Dict]:
        """
        执行完整的爬取流程
        
        流程:
            1. Phase 1: 获取所有项目的列表(名称+链接) - 通过无限滚动加载
            2. Phase 2: 并发抓取每个项目的详细信息
        
        返回:
            List[Dict]: 所有项目的详细信息列表
        """
        self.start_time = time.time()
        self.results = []
        
        try:
            # Phase 1: 获取项目列表(通过无限滚动)
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
        
        该方法通过无限滚动加载所有课程
        Strathclyde 网站使用无限滚动,需要持续滚动直到所有课程加载完成
        """
        print_phase_start(
            "Phase 1", 
            "正在扫描项目列表 (无限滚动)...",
            total=None
        )
        print(f"   📍 目标地址: {self.list_url}")
        
        try:
            # 访问页面
            self.driver.get(self.list_url)
            time.sleep(3)  # 等待页面加载
            
            # 处理 Cookie 横幅
            self._handle_cookie_banner()
            
            # 等待课程列表加载
            try:
                WebDriverWait(self.driver, PAGE_LOAD_WAIT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.course-search-result__link'))
                )
            except TimeoutException:
                print("   ⚠️ 课程列表加载超时,尝试继续...")
            
            # 执行无限滚动加载所有课程
            self._scroll_to_load_all()
            
            # 提取所有项目
            self._extract_programs_from_page()
            
            print_phase_complete("Phase 1", len(self.temp_links))
            
        except Exception as e:
            print(f"❌ 获取项目列表失败: {e}")
    
    def _handle_cookie_banner(self) -> None:
        """处理 Cookie 横幅"""
        try:
            # 方法1: 使用 JavaScript 直接点击接受按钮
            try:
                self.driver.execute_script("""
                    // 尝试点击接受按钮
                    var acceptBtns = document.querySelectorAll('button');
                    for (var i = 0; i < acceptBtns.length; i++) {
                        var text = acceptBtns[i].innerText.toLowerCase();
                        if (text.includes('accept') || text.includes('agree') || text.includes('ok')) {
                            acceptBtns[i].click();
                            return true;
                        }
                    }
                    return false;
                """)
                time.sleep(1)
            except:
                pass
            
            # 方法2: 使用 JavaScript 移除/隐藏 overlay
            try:
                self.driver.execute_script("""
                    // 移除 cookie overlay
                    var overlays = document.querySelectorAll('[id*="cookie"], [class*="cookie"], [id*="consent"], [class*="consent"]');
                    overlays.forEach(function(o) {
                        o.style.display = 'none';
                    });
                    
                    // 恢复 body 滚动
                    document.body.style.overflow = 'auto';
                """)
                print("   🍪 已处理 Cookie 弹窗")
            except:
                pass
                    
        except Exception:
            # Cookie 横幅可能不存在或已被接受
            pass
    
    def _scroll_to_load_all(self) -> None:
        """
        通过无限滚动加载所有课程
        
        持续滚动直到没有新课程加载
        """
        print("   📜 正在执行无限滚动加载...")
        
        last_count = 0
        scroll_attempts = 0
        max_attempts = 50  # 最大滚动次数,防止无限循环
        no_change_count = 0
        
        while scroll_attempts < max_attempts:
            # 滚动到页面底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)  # 等待加载
            
            # 获取当前课程数量
            current_count = len(self.driver.find_elements(By.CSS_SELECTOR, '.course-search-result__link'))
            
            if current_count == last_count:
                no_change_count += 1
                if no_change_count >= 3:
                    # 连续3次没有变化,认为加载完成
                    print(f"   ✅ 滚动加载完成,共加载 {current_count} 个课程")
                    break
            else:
                no_change_count = 0
                print(f"   📊 已加载 {current_count} 个课程...", end='\r')
            
            last_count = current_count
            scroll_attempts += 1
        
        if scroll_attempts >= max_attempts:
            print(f"   ⚠️ 达到最大滚动次数,已加载 {last_count} 个课程")
    
    def _extract_programs_from_page(self) -> None:
        """
        从当前页面提取项目信息
        
        Strathclyde 使用 .course-search-result__link 展示项目列表
        标题在链接内的 h2 元素中
        """
        # 去重处理
        seen_urls = set()
        
        # 查找所有课程链接
        course_links = self.driver.find_elements(By.CSS_SELECTOR, '.course-search-result__link')
        
        print(f"   📊 发现 {len(course_links)} 个课程链接")
        
        extracted_count = 0
        errors_count = 0
        
        for link in course_links:
            try:
                # 获取链接 URL
                href = link.get_attribute("href")
                
                if not href:
                    continue
                
                # 过滤非研究生课程链接
                if '/courses/postgraduatetaught/' not in href:
                    continue
                
                # 获取课程名称 - 只从 h2 元素提取标题
                try:
                    title_elem = link.find_element(By.CSS_SELECTOR, 'h2')
                    name = title_elem.text.strip()
                except NoSuchElementException:
                    # 如果找不到 h2，回退到链接的第一行文本
                    full_text = link.text.strip()
                    name = full_text.split('\n')[0].strip() if full_text else ""
                except Exception as e:
                    errors_count += 1
                    continue
                
                if not name or len(name) < 3:
                    continue
                
                # 跳过已处理的 URL
                if href in seen_urls:
                    continue
                seen_urls.add(href)
                
                # 确保 URL 格式正确
                if not href.startswith('http'):
                    href = f"{self.base_url}{href}"
                
                self.temp_links.append({
                    "name": name,
                    "link": href
                })
                extracted_count += 1
                    
            except Exception as e:
                errors_count += 1
                continue
        
        if errors_count > 0:
            print(f"   ⚠️ 提取时发生 {errors_count} 个错误")
        print(f"   ✅ 成功提取 {extracted_count} 个研究生项目")
    
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
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
                )
                
                # 抓取开始日期作为 opendate
                result["项目opendate"] = self._extract_start_date(driver)
                
                # 尝试抓取 deadline 信息
                result["项目deadline"] = self._extract_deadline(driver)
                
            except TimeoutException:
                # 详情页加载超时,保持 N/A
                pass
            except Exception:
                # 其他错误,保持 N/A
                pass
        
        duration = time.time() - item_start
        return result, duration
    
    def _extract_start_date(self, driver) -> str:
        """
        提取课程开始日期
        
        Strathclyde 的课程开始日期通常在 Key Facts 区域
        """
        try:
            # 方法1: 查找 Key Facts 中的开始日期
            key_facts = driver.find_elements(By.CSS_SELECTOR, '.key-fact__text')
            
            for fact in key_facts:
                text = fact.text.strip()
                # 检查是否包含月份信息
                months = ['January', 'February', 'March', 'April', 'May', 'June', 
                         'July', 'August', 'September', 'October', 'November', 'December']
                for month in months:
                    if month in text:
                        return text
            
            # 方法2: 查找包含 "Start" 的元素
            start_elements = driver.find_elements(
                By.XPATH, 
                "//*[contains(text(), 'Start')]"
            )
            
            for elem in start_elements:
                try:
                    parent = elem.find_element(By.XPATH, "./..")
                    text = parent.text.strip()
                    if any(month in text for month in months):
                        # 提取日期部分
                        lines = text.split('\n')
                        for line in lines:
                            if any(month in line for month in months):
                                return line.strip()
                except:
                    continue
            
            return "N/A"
            
        except Exception:
            return "N/A"
    
    def _extract_deadline(self, driver) -> str:
        """
        提取申请截止日期
        
        优化策略:
        1. 查找包含 deadline 关键词的元素
        2. 检查父容器获取完整信息 (包含标签和日期值)
        3. 如果父容器为空，尝试获取相邻元素
        """
        try:
            # 查找包含 deadline 关键词的元素
            keywords = ['deadline', 'closing date', 'application close', 'apply by']
            
            for keyword in keywords:
                try:
                    elements = driver.find_elements(
                        By.XPATH, 
                        f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{keyword}')]"
                    )
                    
                    for elem in elements:
                        # 策略1: 尝试获取父容器的文本 (通常包含标签+值)
                        try:
                            parent = elem.find_element(By.XPATH, "./..")
                            parent_text = parent.text.strip()
                            
                            # 如果父容器文本比当前元素文本长，说明包含了更多信息
                            if parent_text and len(parent_text) > len(elem.text.strip()):
                                # 检查是否包含月份等日期信息
                                months = ['January', 'February', 'March', 'April', 'May', 'June', 
                                         'July', 'August', 'September', 'October', 'November', 'December',
                                         'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                                         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                                
                                if any(month in parent_text for month in months):
                                    # 清理换行符
                                    return parent_text.replace('\n', ' ').strip()
                        except:
                            pass
                        
                        # 策略2: 如果元素本身文本合理，直接返回
                        elem_text = elem.text.strip()
                        if elem_text and len(elem_text) > 5 and len(elem_text) < 500:
                            return elem_text
                            
                except NoSuchElementException:
                    continue
            
            return "N/A"
            
        except Exception:
            return "N/A"


if __name__ == "__main__":
    # 测试代码
    with StrathclydeSpider(headless=False) as spider:
        results = spider.run()
        
        print(f"\n抓取完成,共 {len(results)} 个项目")
        if results:
            import json
            print("\n前3个项目示例:")
            print(json.dumps(results[:3], indent=2, ensure_ascii=False))
