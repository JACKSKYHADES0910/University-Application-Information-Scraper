# -*- coding: utf-8 -*-
"""
东英吉利大学 (University of East Anglia) 爬虫模块
负责抓取 UEA Postgraduate 项目信息
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


class UEASpider(BaseSpider):
    """
    东英吉利大学爬虫
    
    负责从 University of East Anglia 官网爬取所有 Postgraduate 项目的详细信息,包括:
    - 项目名称
    - 项目链接
    - 课程开始日期
    - 统一的申请注册和登录链接
    
    网站特点:
    - 使用 Algolia 搜索引擎，内容通过 JavaScript 动态加载
    - 分页显示，每页约 12 个项目
    - 约 215 个研究生项目
    
    使用示例:
        >>> with UEASpider() as spider:
        ...     data = spider.run()
        ...     print(f"爬取了 {len(data)} 条数据")
    """
    
    def __init__(self, headless: bool = True, max_workers: int = None):
        """
        初始化 UEA 爬虫
        
        参数:
            headless (bool): 是否无头模式运行
            max_workers (int): 并发线程数,如果不指定则使用 config.py 中的配置
        """
        super().__init__("uea", headless)
        from config import MAX_WORKERS as CONFIG_MAX_WORKERS
        self.max_workers = max_workers if max_workers is not None else CONFIG_MAX_WORKERS
        self.temp_links: List[Dict] = []  # 临时存储项目链接列表
        self.progress_manager: CrawlerProgress = None  # 进度管理器
        self.browser_pool: BrowserPool = None  # 浏览器池
    
    def run(self) -> List[Dict]:
        """
        执行完整的爬取流程
        
        流程:
            1. Phase 1: 获取所有项目的列表(名称+链接) - 遍历所有分页
            2. Phase 2: 并发抓取每个项目的详细信息
        
        返回:
            List[Dict]: 所有项目的详细信息列表
        """
        self.start_time = time.time()
        self.results = []
        
        try:
            # Phase 1: 获取项目列表(遍历分页)
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
        
        该方法遍历所有分页获取项目
        UEA 网站使用 Algolia 搜索，内容通过 JavaScript 动态加载
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
            
            # 处理 Cookie 横幅
            self._handle_cookie_banner()
            
            # 等待搜索结果加载
            try:
                WebDriverWait(self.driver, PAGE_LOAD_WAIT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'h4 a[href*="/course/postgraduate/"]'))
                )
            except TimeoutException:
                print("   ⚠️ 搜索结果加载超时,尝试继续...")
            
            # 获取总页数
            total_pages = self._get_total_pages()
            print(f"   📊 检测到约 {total_pages} 页结果")
            
            # 遍历所有页面提取项目
            current_page = 1
            while current_page <= total_pages:
                print(f"   📄 正在处理第 {current_page}/{total_pages} 页...")
                
                # 等待当前页面加载
                time.sleep(1)
                
                # 提取当前页的项目
                self._extract_programs_from_page()
                
                # 尝试跳转到下一页
                if current_page < total_pages:
                    if not self._go_to_next_page():
                        print(f"   ⚠️ 无法跳转到第 {current_page + 1} 页,停止分页")
                        break
                    time.sleep(2)  # 等待 AJAX 加载
                
                current_page += 1
            
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
                    var acceptBtn = document.getElementById('ccc-notify-accept');
                    if (acceptBtn) {
                        acceptBtn.click();
                        return true;
                    }
                    // 尝试其他选择器
                    var btns = document.querySelectorAll('button');
                    for (var i = 0; i < btns.length; i++) {
                        if (btns[i].innerText.toLowerCase().includes('accept')) {
                            btns[i].click();
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
                    var overlay = document.getElementById('ccc-overlay');
                    if (overlay) overlay.style.display = 'none';
                    
                    // 移除 cookie 容器
                    var container = document.getElementById('ccc');
                    if (container) container.style.display = 'none';
                    
                    // 移除任何 modal backdrop
                    var modals = document.querySelectorAll('.ccc-overlay, .cookie-overlay, [class*="cookie"]');
                    modals.forEach(function(m) {
                        if (m.style) m.style.display = 'none';
                    });
                    
                    // 移除可能阻止滚动的 body 样式
                    document.body.style.overflow = 'auto';
                """)
                print("   🍪 已处理 Cookie 弹窗")
            except:
                pass
                    
        except Exception:
            # Cookie 横幅可能不存在或已被接受
            pass
    
    def _get_total_pages(self) -> int:
        """
        获取总页数
        
        返回:
            int: 总页数
        """
        try:
            # 确保 cookie overlay 被移除
            self._remove_overlay()
            
            # 查找分页按钮
            pagination_buttons = self.driver.find_elements(
                By.CSS_SELECTOR, 
                'button[aria-label*="Page"]'
            )
            
            # 提取页码数字
            page_numbers = []
            for btn in pagination_buttons:
                try:
                    label = btn.get_attribute("aria-label")
                    if label and "Page" in label:
                        # aria-label 格式: "Page 1" 或 "Current Page, Page 1"
                        text = btn.text.strip()
                        if text.isdigit():
                            page_numbers.append(int(text))
                except:
                    continue
            
            if page_numbers:
                # 初始时只能看到前几页,但可以通过点击"Last Page"来估算
                # 或者根据 "215 results" 计算: 215 / 12 ≈ 18 页
                max_visible = max(page_numbers)
                # 如果有 "Last Page" 按钮,可能还有更多页
                last_page_btn = self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    'button[aria-label="Last Page"]'
                )
                if last_page_btn:
                    # 使用 JavaScript 点击
                    self.driver.execute_script("arguments[0].click();", last_page_btn[0])
                    time.sleep(2)
                    
                    # 重新获取页码
                    new_buttons = self.driver.find_elements(
                        By.CSS_SELECTOR, 
                        'button[aria-label*="Page"]'
                    )
                    for btn in new_buttons:
                        try:
                            text = btn.text.strip()
                            if text.isdigit():
                                page_numbers.append(int(text))
                        except:
                            continue
                    
                    # 回到第一页
                    first_page_btn = self.driver.find_elements(
                        By.CSS_SELECTOR, 
                        'button[aria-label="First Page"]'
                    )
                    if first_page_btn:
                        self.driver.execute_script("arguments[0].click();", first_page_btn[0])
                        time.sleep(2)
                
                return max(page_numbers) if page_numbers else 18
            
            # 默认估算
            return 18
            
        except Exception as e:
            print(f"   ⚠️ 无法获取页数,使用默认值: {e}")
            return 18
    
    def _remove_overlay(self) -> None:
        """移除可能阻挡点击的 overlay"""
        try:
            self.driver.execute_script("""
                // 移除 cookie overlay
                var overlay = document.getElementById('ccc-overlay');
                if (overlay) overlay.remove();
                
                // 移除 cookie 容器
                var container = document.getElementById('ccc');
                if (container) container.remove();
                
                // 移除其他可能的 overlay
                var overlays = document.querySelectorAll('[id*="overlay"], [class*="overlay"]');
                overlays.forEach(function(o) {
                    if (o.id && o.id.toLowerCase().includes('ccc')) o.remove();
                });
                
                // 恢复 body 滚动
                document.body.style.overflow = 'auto';
            """)
        except:
            pass
    
    def _go_to_next_page(self) -> bool:
        """
        跳转到下一页
        
        返回:
            bool: 是否成功跳转
        """
        try:
            # 确保 overlay 被移除
            self._remove_overlay()
            
            next_btn = self.driver.find_element(
                By.CSS_SELECTOR, 
                'button[aria-label="Next Page"]'
            )
            
            if next_btn.is_enabled():
                # 滚动到按钮可见
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                time.sleep(0.5)
                
                # 使用 JavaScript 点击，避免 click interception
                self.driver.execute_script("arguments[0].click();", next_btn)
                
                # 等待新内容加载
                time.sleep(2)
                return True
            else:
                return False
                
        except NoSuchElementException:
            return False
        except Exception as e:
            print(f"   ⚠️ 翻页失败: {e}")
            return False
    
    def _extract_programs_from_page(self) -> None:
        """
        从当前页面提取项目信息
        
        UEA 使用 Algolia 搜索展示项目列表,每个项目在 h4 a 中
        """
        # 去重处理
        seen_urls = set(d['link'] for d in self.temp_links)
        
        # 查找所有课程链接
        course_selectors = [
            'h4 a[href*="/course/postgraduate/"]',
            'a[href*="/course/postgraduate/"]',
        ]
        
        course_links = []
        for selector in course_selectors:
            course_links = self.driver.find_elements(By.CSS_SELECTOR, selector)
            if course_links:
                break
        
        for link in course_links:
            try:
                # 获取课程名称
                name = link.text.strip()
                href = link.get_attribute("href")
                
                if not name or len(name) < 3:
                    continue
                    
                if not href:
                    continue
                
                # 过滤非课程链接
                if '/course/postgraduate/' not in href:
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
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
                )
                
                # 抓取开始日期作为 opendate
                result["项目opendate"] = self._extract_start_date(driver)
                
                # 尝试抓取 deadline 信息(UEA 通常没有)
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
        
        UEA 的课程开始日期通常在 Key Details 区域
        """
        try:
            # 方法1: 查找包含 "Course Start Date" 的元素
            elements = driver.find_elements(
                By.XPATH, 
                "//*[contains(text(), 'Course Start Date')]"
            )
            
            for elem in elements:
                try:
                    # 获取父元素文本
                    parent = elem.find_element(By.XPATH, "./..")
                    text = parent.text.strip()
                    if "Course Start Date" in text:
                        # 提取日期部分
                        lines = text.split('\n')
                        for i, line in enumerate(lines):
                            if 'Course Start Date' in line:
                                # 日期在下一行或同一行
                                if i + 1 < len(lines):
                                    return lines[i + 1].strip()
                                # 尝试从同一行提取
                                date_part = line.replace('Course Start Date', '').strip()
                                if date_part:
                                    return date_part
                except:
                    continue
            
            # 方法2: 查找 entry-point 下拉框的选中值
            try:
                select = driver.find_element(By.ID, "entry-point")
                selected = select.find_element(By.CSS_SELECTOR, "option:checked")
                if selected:
                    return selected.text.strip()
            except:
                pass
            
            # 方法3: 查找页面标题中的年份 (如 "MSc Economics 2026/27")
            try:
                title = driver.find_element(By.CSS_SELECTOR, "h1").text
                import re
                year_match = re.search(r'(\d{4}/\d{2})', title)
                if year_match:
                    return f"September {year_match.group(1).split('/')[0]}"
            except:
                pass
            
            return "N/A"
            
        except Exception:
            return "N/A"
    
    def _extract_deadline(self, driver) -> str:
        """
        提取申请截止日期
        
        注意: UEA 通常采用滚动招生,没有固定截止日期
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
                        text = elem.text.strip()
                        if text and len(text) > 5 and len(text) < 500:
                            return text
                            
                except NoSuchElementException:
                    continue
            
            return "N/A"
            
        except Exception:
            return "N/A"


if __name__ == "__main__":
    # 测试代码
    with UEASpider(headless=False) as spider:
        results = spider.run()
        
        print(f"\n抓取完成,共 {len(results)} 个项目")
        if results:
            import json
            print("\n前3个项目示例:")
            print(json.dumps(results[:3], indent=2, ensure_ascii=False))
