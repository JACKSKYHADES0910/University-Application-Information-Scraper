# -*- coding: utf-8 -*-
"""
伦敦大学皇家霍洛威学院 (Royal Holloway University of London) 爬虫模块
负责抓取 Royal Holloway Postgraduate 项目信息
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


class RoyalHollowaySpider(BaseSpider):
    """
    伦敦大学皇家霍洛威学院爬虫
    
    负责从 Royal Holloway University of London 官网爬取所有 Postgraduate 项目的详细信息,包括:
    - 项目名称
    - 项目链接
    - 课程持续时间
    - 统一的申请注册和登录链接
    
    网站特点:
    - 使用 A-Z 字母导航分类展示课程
    - 点击字母动态加载内容(不改变URL)
    
    使用示例:
        >>> with RoyalHollowaySpider() as spider:
        ...     data = spider.run()
        ...     print(f"爬取了 {len(data)} 条数据")
    """
    
    def __init__(self, headless: bool = True, max_workers: int = None):
        """
        初始化 Royal Holloway 爬虫
        
        参数:
            headless (bool): 是否无头模式运行
            max_workers (int): 并发线程数,如果不指定则使用 config.py 中的配置
        """
        super().__init__("royalholloway", headless)
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
        Royal Holloway 网站使用 A-Z 导航,点击字母动态加载内容
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
            
            # 处理 Cookie 同意对话框
            self._handle_cookie_consent()
            
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
    
    def _handle_cookie_consent(self) -> None:
        """
        处理 Cookie 同意对话框
        
        Royal Holloway 网站有一个 Cookie 同意弹窗,需要先关闭才能点击其他元素
        """
        try:
            # 等待并尝试点击"接受所有 Cookie"按钮
            # 常见的选择器: Accept All, Accept, I Accept 等
            accept_buttons_selectors = [
                "button#ccc-recommended-settings",  # Royal Holloway 的接受按钮
                "button.ccc-notify-button",
                "button[aria-label*='Accept']",
                "button[aria-label*='accept']",
                "a.ccc-notify-link"
            ]
            
            for selector in accept_buttons_selectors:
                try:
                    accept_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    accept_button.click()
                    print("   ✅ 已接受 Cookie 同意")
                    time.sleep(1)  # 等待对话框消失
                    return
                except:
                    continue
            
            # 如果没找到接受按钮,可能已经接受过了
            print("   ℹ️ 未找到 Cookie 同意对话框")
            
        except Exception as e:
            print(f"   ⚠️ 处理 Cookie 对话框时出错: {e}")
    
    def _get_active_letters(self) -> List[str]:
        """
        获取所有包含课程的活跃字母
        
        返回:
            List[str]: 活跃字母列表 (例如: ['A', 'B', 'C', ...])
        """
        try:
            # 等待 A-Z 导航加载
            WebDriverWait(self.driver, PAGE_LOAD_WAIT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a.data'))
            )
            
            # 查找所有可点击的字母按钮 (使用 a.data 标签)
            active_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'a.data')
            
            letters = []
            for button in active_buttons:
                # 获取字母文本 (例如 "A" 或 "A 14" -> "A")
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
            # 找到对应的字母按钮并点击
            letter_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'a.data')
            
            for button in letter_buttons:
                button_text = button.text.strip().split()[0]
                if button_text.upper() == letter.upper():
                    # 滚动到按钮位置
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                    time.sleep(0.5)
                    
                    # 使用 JavaScript 点击来避免拦截
                    self.driver.execute_script("arguments[0].click();", button)
                    time.sleep(2)  # 等待内容加载
                    break
            
            # 等待课程列表加载
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/studying-here/postgraduate/"]'))
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
        course_links = self.driver.find_elements(
            By.CSS_SELECTOR, 
            'a[href*="/studying-here/postgraduate/"]'
        )
        
        extracted_count = 0
        
        for link in course_links:
            try:
                # 获取链接 URL
                href = link.get_attribute("href")
                
                # 排除课程列表页本身
                if not href or href in seen_urls or href.endswith('/postgraduate-courses/'):
                    continue
                
                # 获取课程名称
                try:
                    # 尝试从 title 属性提取
                    course_title = link.get_attribute("title")
                    if not course_title:
                        # 尝试从链接文本提取
                        course_title = link.text.strip()
                except:
                    course_title = link.text.strip()
                
                if not course_title or len(course_title) < 3:
                    continue
                
                # 确保 URL 格式正确
                if not href.startswith('http'):
                    href = f"{self.base_url}{href}"
                
                self.temp_links.append({
                    "name": course_title,
                    "link": href
                })
                seen_urls.add(href)
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
                
                # 抓取持续时间/开始日期
                result["项目opendate"] = self._extract_duration(driver)
                
                # Royal Holloway 通常没有明确的 deadline,使用滚动招生
                result["项目deadline"] = "N/A"
                
            except TimeoutException:
                # 详情页加载超时,保持 N/A
                pass
            except Exception:
                # 其他错误,保持 N/A
                pass
        
        duration = time.time() - item_start
        return result, duration
    
    def _extract_duration(self, driver) -> str:
        """
        提取课程持续时间
        
        Royal Holloway 的持续时间通常在 "Key information" 区域
        """
        try:
            # 方法1: 查找包含 "Duration" 的元素
            duration_elements = driver.find_elements(
                By.XPATH, 
                "//*[contains(text(), 'Duration')]"
            )
            
            for elem in duration_elements:
                try:
                    # 查找父元素或相邻元素
                    parent = elem.find_element(By.XPATH, "./..")
                    text = parent.text.strip()
                    
                    # 提取持续时间部分
                    if 'Duration:' in text:
                        lines = text.split('\n')
                        for line in lines:
                            if 'Duration:' in line:
                                # 移除 "Duration:" 标签,提取实际值
                                duration = line.replace('Duration:', '').strip()
                                return duration if duration else "N/A"
                except:
                    continue
            
            # 方法2: 查找包含 "year" 或 "month" 的文本
            time_keywords = ['year', 'month', 'full time', 'part time']
            for keyword in time_keywords:
                try:
                    keyword_elements = driver.find_elements(
                        By.XPATH,
                        f"//*[contains(text(), '{keyword}')]"
                    )
                    for elem in keyword_elements:
                        text = elem.text.strip()
                        # 确保文本不是太长(避免误匹配段落)
                        if text and len(text) < 50 and any(k in text.lower() for k in time_keywords):
                            return text
                except:
                    continue
            
            return "N/A"
            
        except Exception:
            return "N/A"


if __name__ == "__main__":
    # 测试代码
    with RoyalHollowaySpider(headless=False) as spider:
        results = spider.run()
        
        print(f"\n抓取完成,共 {len(results)} 个项目")
        if results:
            import json
            print("\n前3个项目示例:")
            print(json.dumps(results[:3], indent=2, ensure_ascii=False))
