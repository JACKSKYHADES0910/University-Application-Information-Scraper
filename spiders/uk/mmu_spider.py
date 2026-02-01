# -*- coding: utf-8 -*-
"""
曼彻斯特城市大学 (Manchester Metropolitan University) 爬虫模块
负责抓取 MMU Postgraduate Taught 项目信息
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


class MMUSpider(BaseSpider):
    """
    曼彻斯特城市大学爬虫
    
    负责从 Manchester Metropolitan University 官网爬取所有 Postgraduate Taught 项目的详细信息,包括:
    - 项目名称
    - 项目链接
    - 课程开始日期
    - 统一的申请注册和登录链接
    
    网站特点:
    - 使用 A-Z 字母导航分类展示课程
    - 只有包含课程的字母按钮可点击
    
    使用示例:
        >>> with MMUSpider() as spider:
        ...     data = spider.run()
        ...     print(f"爬取了 {len(data)} 条数据")
    """
    
    def __init__(self, headless: bool = True, max_workers: int = None):
        """
        初始化 MMU 爬虫
        
        参数:
            headless (bool): 是否无头模式运行
            max_workers (int): 并发线程数,如果不指定则使用 config.py 中的配置
        """
        super().__init__("mmu", headless)
        from config import MAX_WORKERS as CONFIG_MAX_WORKERS
        self.max_workers = max_workers if max_workers is not None else CONFIG_MAX_WORKERS
        self.temp_links: List[Dict] = []  # 临时存储项目链接列表
        self.progress_manager: CrawlerProgress = None  # 进度管理器
        self.browser_pool: BrowserPool = None  # 浏览器池
    
    def run(self) -> List[Dict]:
        """
        执行完整的爬取流程
        
        流程:
            1. Phase 1: 获取所有项目的列表(名称+链接) - 通过 A-Z 导航
            2. Phase 2: 并发抓取每个项目的详细信息
        
        返回:
            List[Dict]: 所有项目的详细信息列表
        """
        self.start_time = time.time()
        self.results = []
        
        try:
            # Phase 1: 获取项目列表(通过 A-Z 导航)
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
        Phase 1: 从 A-Z 列表页获取所有项目的名称和链接
        
        该方法遍历所有可点击的字母,提取每个字母下的课程列表
        MMU 网站使用 A-Z 导航,每个字母对应一个单独的页面
        """
        print_phase_start(
            "Phase 1", 
            "正在扫描项目列表 (A-Z 导航)...",
            total=None
        )
        print(f"   📍 目标地址: {self.list_url}")
        
        try:
            # 访问起始页面
            self.driver.get(self.list_url)
            time.sleep(3)  # 等待页面加载
            
            # 获取所有可点击的字母按钮
            active_letters = self._get_active_letters()
            
            if not active_letters:
                print("   ⚠️ 未找到任何活跃字母")
                return
            
            print(f"   📊 发现 {len(active_letters)} 个活跃字母: {', '.join(active_letters)}")
            
            # 遍历每个字母
            for idx, letter in enumerate(active_letters, 1):
                print(f"\n   🔤 正在处理字母 [{letter}] ({idx}/{len(active_letters)})...")
                self._process_letter(letter)
                time.sleep(1)  # 礼貌延迟
            
            print_phase_complete("Phase 1", len(self.temp_links))
            
        except Exception as e:
            print(f"❌ 获取项目列表失败: {e}")
    
    def _get_active_letters(self) -> List[str]:
        """
        获取所有包含课程的活跃字母
        
        返回:
            List[str]: 活跃字母列表 (例如: ['A', 'B', 'C', ...])
        """
        try:
            # 等待 A-Z 导航加载
            WebDriverWait(self.driver, PAGE_LOAD_WAIT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.a-to-z-button'))
            )
            
            # 查找所有可点击的字母按钮 (使用 <a> 标签)
            active_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'a.a-to-z-button')
            
            letters = []
            for button in active_buttons:
                # 获取字母文本 (例如 "A 14" -> "A")
                text = button.text.strip().split()[0]
                if text and len(text) == 1 and text.isalpha():
                    letters.append(text.upper())
            
            return letters
            
        except Exception as e:
            print(f"   ⚠️ 获取活跃字母失败: {e}")
            return []
    
    def _process_letter(self, letter: str) -> None:
        """
        处理单个字母下的所有课程
        
        参数:
            letter (str): 字母 (例如 'A')
        """
        try:
            # 构建字母页面 URL
            letter_url = f"{self.list_url}/{letter.lower()}"
            self.driver.get(letter_url)
            
            # 等待课程列表加载
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/study/postgraduate/course/"]'))
                )
            except TimeoutException:
                print(f"      ⚠️ 字母 [{letter}] 页面加载超时")
                return
            
            # 提取课程信息
            self._extract_programs_from_page(letter)
            
        except Exception as e:
            print(f"      ❌ 处理字母 [{letter}] 时出错: {e}")
    
    def _extract_programs_from_page(self, letter: str) -> None:
        """
        从当前页面提取项目信息
        
        参数:
            letter (str): 当前字母
        """
        # 去重处理
        seen_urls = set(link["link"] for link in self.temp_links)
        
        # 查找所有课程链接
        course_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/study/postgraduate/course/"]')
        
        extracted_count = 0
        
        for link in course_links:
            try:
                # 获取链接 URL
                href = link.get_attribute("href")
                
                if not href or href in seen_urls:
                    continue
                
                # 获取课程名称 - 从 h4 元素提取
                try:
                    title_elem = link.find_element(By.CSS_SELECTOR, 'h4')
                    course_title = title_elem.text.strip()
                except NoSuchElementException:
                    # 如果找不到 h4，跳过
                    continue
                
                # 尝试获取学位类型 (MA, MSc, etc.)
                try:
                    award_elem = link.find_element(By.XPATH, "./div[1]")
                    award_text = award_elem.text.strip()
                    # 如果学位类型存在且合理，将其放在括号中
                    if award_text and len(award_text) <= 10:
                        name = f"{course_title} ({award_text})"
                    else:
                        name = course_title
                except:
                    name = course_title
                
                if not name or len(name) < 3:
                    continue
                
                # 确保 URL 格式正确
                if not href.startswith('http'):
                    href = f"{self.base_url}{href}"
                
                self.temp_links.append({
                    "name": name,
                    "link": href
                })
                extracted_count += 1
                    
            except Exception:
                continue
        
        print(f"      ✅ 字母 [{letter}]: 提取 {extracted_count} 个课程")
    
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
                
                # 抓取开始日期
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
        
        MMU 的课程开始日期通常在 "Fact file" 区域
        """
        try:
            # 方法1: 查找包含 "Start date" 的元素
            start_elements = driver.find_elements(
                By.XPATH, 
                "//*[contains(text(), 'Start date')]"
            )
            
            months = ['January', 'February', 'March', 'April', 'May', 'June', 
                     'July', 'August', 'September', 'October', 'November', 'December',
                     'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            
            for elem in start_elements:
                try:
                    # 查找父元素或相邻元素
                    parent = elem.find_element(By.XPATH, "./..")
                    text = parent.text.strip()
                    
                    # 检查是否包含月份信息
                    if any(month in text for month in months):
                        # 提取日期部分 (移除 "Start date" 标签)
                        lines = text.split('\n')
                        for line in lines:
                            if any(month in line for month in months):
                                return line.strip()
                except:
                    continue
            
            # 方法2: 直接查找包含月份的文本
            for month in months:
                try:
                    month_elements = driver.find_elements(
                        By.XPATH,
                        f"//*[contains(text(), '{month}')]"
                    )
                    for elem in month_elements:
                        text = elem.text.strip()
                        # 确保文本不是太长(避免误匹配段落)
                        if text and len(text) < 50 and any(m in text for m in months):
                            return text
                except:
                    continue
            
            return "N/A"
            
        except Exception:
            return "N/A"
    
    def _extract_deadline(self, driver) -> str:
        """
        提取申请截止日期
        
        MMU 采用滚动招生制度,所有课程统一返回 N/A
        """
        return "N/A"


if __name__ == "__main__":
    # 测试代码
    with MMUSpider(headless=False) as spider:
        results = spider.run()
        
        print(f"\n抓取完成,共 {len(results)} 个项目")
        if results:
            import json
            print("\n前3个项目示例:")
            print(json.dumps(results[:3], indent=2, ensure_ascii=False))
