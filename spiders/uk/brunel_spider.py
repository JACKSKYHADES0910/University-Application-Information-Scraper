# -*- coding: utf-8 -*-
"""
伦敦布鲁内尔大学 (Brunel University London) 爬虫模块
负责抓取 Brunel Postgraduate Taught 项目信息
"""

import time
from typing import List, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

from spiders.base_spider import BaseSpider
from utils.progress import CrawlerProgress, print_phase_start, print_phase_complete
from utils.selenium_utils import BrowserPool
from config import MAX_WORKERS, PAGE_LOAD_WAIT


class BrunelSpider(BaseSpider):
    """
    伦敦布鲁内尔大学爬虫
    
    负责从 Brunel University London 官网爬取所有 Postgraduate Taught 项目的详细信息,包括:
    - 项目名称
    - 项目链接
    - 课程开始日期
    - 具体的申请链接 (从 Apply now 折叠菜单中提取第一个)
    """
    
    def __init__(self, headless: bool = True, max_workers: int = None):
        """
        初始化 Brunel 爬虫
        """
        super().__init__("brunel", headless)
        from config import MAX_WORKERS as CONFIG_MAX_WORKERS
        self.max_workers = max_workers if max_workers is not None else CONFIG_MAX_WORKERS
        self.temp_links: List[Dict] = []
        self.progress_manager: CrawlerProgress = None
        self.browser_pool: BrowserPool = None
    
    def run(self) -> List[Dict]:
        """
        执行完整的爬取流程
        """
        self.start_time = time.time()
        self.results = []
        
        try:
            # Phase 1: 获取项目列表
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
            if self.browser_pool:
                self.browser_pool.close_all()
            self.close()
        
        self.print_summary()
        return self.results
    
    def _fetch_program_list(self) -> None:
        """
        Phase 1: 从列表页获取所有项目的名称和链接
        URL 参数 pageSize=10000 确保一页显示所有课程
        """
        print_phase_start(
            "Phase 1", 
            "正在扫描项目列表...",
            total=None
        )
        print(f"   📍 目标地址: {self.list_url}")
        
        try:
            self.driver.get(self.list_url)
            time.sleep(5)  # 等待页面初始渲染
            
            self._handle_cookie_banner()
            
            # 等待课程卡片加载
            try:
                WebDriverWait(self.driver, PAGE_LOAD_WAIT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.course-listing-card__link'))
                )
            except TimeoutException:
                print("   ⚠️ 课程列表加载超时,尝试继续...")
            
            # 提取所有项目
            self._extract_programs_from_page()
            
            print_phase_complete("Phase 1", len(self.temp_links))
            
        except Exception as e:
            print(f"❌ 获取项目列表失败: {e}")
    
    def _handle_cookie_banner(self) -> None:
        """处理 Cookie 横幅"""
        try:
            # 尝试点击接受按钮 - 通用选择器
            selectors = [
                 "button#onetrust-accept-btn-handler",
                 "button[class*='cookie-accept']",
                 "button[class*='agree']"
            ]
            
            for selector in selectors:
                try:
                    btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    btn.click()
                    time.sleep(1)
                    print("   🍪 已点击 Cookie 接受按钮")
                    return
                except:
                    continue
        except Exception:
            pass
    
    def _extract_programs_from_page(self) -> None:
        """
        从当前页面提取项目信息
        
        Selectors:
        - Link & Href: .course-listing-card__link
        - Title: h3.course-listing-card__title
        """
        course_cards = self.driver.find_elements(By.CSS_SELECTOR, '.course-listing-card__link')
        print(f"   📊 发现 {len(course_cards)} 个课程卡片")
        
        seen_urls = set()
        extracted_count = 0
        
        for card in course_cards:
            try:
                href = card.get_attribute("href")
                if not href:
                    continue
                    
                # 尝试获取标题
                title = ""
                try:
                    title_elem = card.find_element(By.CSS_SELECTOR, 'h3.course-listing-card__title')
                    title = title_elem.text.strip()
                except NoSuchElementException:
                    # 如果没有 h3，尝试直接获取文本
                    title = card.text.strip().split('\n')[0]
                
                if not title:
                    continue
                
                # 确保 URL 是绝对路径
                if not href.startswith('http'):
                    href = f"{self.base_url}{href}"
                
                if href in seen_urls:
                    continue
                seen_urls.add(href)
                
                self.temp_links.append({
                    "name": title,
                    "link": href
                })
                extracted_count += 1
                
            except Exception as e:
                continue
        
        print(f"   ✅ 成功提取 {extracted_count} 个项目")

    def _fetch_program_details(self) -> None:
        """Phase 2: 并发抓取所有项目的详细信息"""
        self.progress_manager = CrawlerProgress(max_workers=self.max_workers)
        self.results = self.progress_manager.run_tasks(
            items=self.temp_links,
            task_func=self._process_single_program,
            task_name="抓取进度",
            phase_name="Phase 2"
        )
    
    def _process_single_program(self, item: Dict) -> tuple:
        """
        处理单个项目的详情页抓取
        """
        item_start = time.time()
        
        result = self.create_result_template(item['name'], item['link'])
        
        # 默认使用配置中的统一申请链接
        result["申请链接"] = self.university_info.get("apply_register_url", "N/A")
        
        with self.browser_pool.get_browser() as driver:
            try:
                driver.get(item['link'])
                
                # 等待关键元素加载
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
                    )
                except TimeoutException:
                    pass

                # 提取开始日期
                result["项目opendate"] = self._extract_start_date(driver)
                
                # 提取申请链接 (覆盖默认值, 因为 Brunel 每个课程有特定代码)
                apply_link = self._extract_application_link(driver)
                if apply_link and apply_link != "N/A":
                    # 使用特定课程的申请入口
                    result["申请链接"] = apply_link
                
                # Brunel 的 Deadline 通常不明确或因项目而异，这里留 N/A 或尝试通用提取
                result["项目deadline"] = "N/A"
                
            except Exception as e:
                # print(f"Error processing {item['name']}: {e}")
                pass
        
        duration = time.time() - item_start
        return result, duration

    def _extract_start_date(self, driver) -> str:
        """
        提取课程开始日期
        通常在 .key-info 或类似区域
        """
        try:
            # 策略1: 查找包含 "Start date" 的 Label, 然后找其后续内容或父容器内容
            # 根据提供的截图, Start date 是一个 Hx 或 div label, 下面是日期
            
            # 查找所有文本为 Start date 的元素
            labels = driver.find_elements(By.XPATH, "//*[contains(text(), 'Start date')]")
            
            for label in labels:
                # 检查父元素的内容
                try:
                    parent = label.find_element(By.XPATH, "./..")
                    text = parent.text.strip()
                    
                    # 移除 label 本身
                    clean_text = text.replace("Start date", "").strip()
                    if len(clean_text) > 2 and any(m in clean_text for m in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']):
                        return clean_text.replace('\n', ' ').strip()
                except:
                    continue
            
            return "N/A"
        except Exception:
            return "N/A"

    def _extract_application_link(self, driver) -> str:
        """
        从 'Apply now' 手风琴 (Accordion) 中提取第一个申请链接
        注意: 需要点击才能展开
        """
        try:
            # 1. 找到 Apply now 按钮/标题
            # 常见的类名: .accordion__title 或包含 Apply now 文本的按钮
            apply_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Apply now')] | //a[contains(., 'Apply now')] | //div[contains(@class, 'accordion__title')][contains(., 'Apply now')]")
            
            target_btn = None
            for btn in apply_btns:
                if btn.is_displayed():
                    target_btn = btn
                    break
            
            if not target_btn:
                return "N/A"
            
            # 2. 点击展开 (如果未展开)
            # 检查 aria-expanded 属性或直接尝试点击
            try:
                # 滚动到元素位置
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_btn)
                time.sleep(1)
                
                # 尝试点击
                try:
                    target_btn.click()
                except ElementClickInterceptedException:
                    driver.execute_script("arguments[0].click();", target_btn)
                
                time.sleep(1) # 等待动画展开
            except Exception:
                pass
            
            # 3. 查找展开内容中的链接
            # 通常在按钮的兄弟节点或父节点的容器里
            # 先找最近的 accordion content
            try:
                # 尝试找紧邻的 accordion content
                content = target_btn.find_element(By.XPATH, "./following-sibling::*[contains(@class, 'accordion__content') or contains(@class, 'content')]")
                links = content.find_elements(By.TAG_NAME, 'a')
            except NoSuchElementException:
                # 可能结构不同, 尝试在整个 document 中找 Apply now 下方的链接
                # 或者父级容器下的链接
                container = target_btn.find_element(By.XPATH, "./..")
                links = container.find_elements(By.TAG_NAME, 'a')
                # 过滤掉 Apply now 按钮本身(如果是a标签)
                links = [l for l in links if "Apply now" not in l.text]
            
            # 4. 提取第一个有效的申请链接
            for link in links:
                href = link.get_attribute('href')
                if href and ("evision" in href or "apply" in href):
                    return href
            
            return "N/A"
            
        except Exception:
            return "N/A"


if __name__ == "__main__":
    # 测试代码
    with BrunelSpider(headless=False) as spider:
        results = spider.run()
        print(f"\n抓取完成,共 {len(results)} 个项目")
        if results:
            import json
            print("\n前3个项目示例:")
            print(json.dumps(results[:3], indent=2, ensure_ascii=False))
