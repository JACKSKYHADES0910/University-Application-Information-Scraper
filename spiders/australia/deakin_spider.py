# -*- coding: utf-8 -*-
"""
迪肯大学 (Deakin University) 爬虫模块
负责抓取 Deakin Postgraduate 项目信息
"""

import time
import re
from typing import List, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

from spiders.base_spider import BaseSpider
from utils.progress import CrawlerProgress, print_phase_start, print_phase_complete
from utils.selenium_utils import BrowserPool
from config import MAX_WORKERS, PAGE_LOAD_WAIT


class DeakinSpider(BaseSpider):
    """
    迪肯大学爬虫
    
    负责从 Deakin University 官网爬取所有 Postgraduate 项目的详细信息,包括:
    - 项目名称
    - 项目链接
    - 学习领域(Study area)
    - Key dates(截止日期)
    - 统一的申请注册和登录链接
    
    特点:
    - 使用"Study area"筛选器遍历所有学科领域
    - 直接记录Study area作为"学习领域"
    - 支持分页(每页12个项目)
    
    使用示例:
        >>> with DeakinSpider() as spider:
        ...     data = spider.run()
        ...     print(f"爬取了 {len(data)} 条数据")
    """
    
    def __init__(self, headless: bool = True, max_workers: int = None):
        """
        初始化 Deakin 爬虫
        
        参数:
            headless (bool): 是否无头模式运行
            max_workers (int): 并发线程数,如果不指定则使用 config.py 中的配置
        """
        super().__init__("deakin", headless)
        from config import MAX_WORKERS as CONFIG_MAX_WORKERS
        self.max_workers = max_workers if max_workers is not None else CONFIG_MAX_WORKERS
        self.temp_links: List[Dict] = []  # 临时存储项目链接列表(带学习领域信息)
        self.progress_manager: CrawlerProgress = None  # 进度管理器
        self.browser_pool: BrowserPool = None  # 浏览器池
        
        # Study area列表（学习领域）
        self.study_areas = [
            "Arts, humanities and social sciences",
            "Education and teaching",
            "Media and communications",
            "Film, television and animation",
            "Design and creative arts",
            "Accounting and finance",
            "Business and economics",
            "Law",
            "Management and MBA",
            "Medicine",
            "Nursing and midwifery",
            "Psychology and mental health",
            "Health and community services",
            "Food, nutrition and dietetics",
            "Architecture",
            "Construction and property",
            "Data science and analytics",
            "Engineering",
            "Environment and sustainability",
            "Information technology and cyber security",
            "Science",
            "Sport"
        ]
    
    def run(self) -> List[Dict]:
        """
        执行完整的爬取流程
        
        流程:
            1. Phase 1: 遍历所有Study area,获取每个分类下的项目列表
            2. Phase 2: 并发抓取每个项目的详细信息
        
        返回:
            List[Dict]: 所有项目的详细信息列表
        """
        self.start_time = time.time()
        self.results = []
        
        try:
            # Phase 1: 遍历所有Study area获取项目列表
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
        Phase 1: 直接遍历全量列表的所有分页，获取全部项目
        
        该方法会:
        1. 访问课程列表页
        2. 遍历所有分页提取项目
        3. 学习领域字段设为"N/A"(因不筛选无法确定)
        """
        print_phase_start(
            "Phase 1",
            f"正在扫描全量项目列表(175个项目)...",
            total=None
        )
        print(f"   📍 目标地址: {self.list_url}", flush=True)
        
        try:
            # 访问起始页面
            self.driver.get(self.list_url)
            time.sleep(3)  # 等待页面加载
            
            # 处理Cookie同意对话框
            self._handle_cookie_consent()
            
            # 遍历所有分页提取项目
            page_num = 1
            total_extracted = 0
            
            while True:
                print(f"\n   📄 正在处理第 {page_num} 页...", flush=True)
                
                # 提取当前页面的项目
                count = self._extract_programs_from_current_page()
                total_extracted += count
                
                print(f"      ✅ 第 {page_num} 页: 提取 {count} 个项目 (累计: {total_extracted})", flush=True)
                
                if count == 0:
                    print(f"      ⚠️ 当前页无项目，停止翻页", flush=True)
                    break
                
                # 检查是否有下一页
                if not self._has_next_page():
                    print(f"   ✅ 已到达最后一页", flush=True)
                    break
                
                # 点击下一页
                if not self._click_next_page():
                    print(f"   ⚠️ 无法点击下一页，停止翻页", flush=True)
                    break
                
                page_num += 1
                time.sleep(2)  # 等待下一页加载
            
            # 进行分类
            self._classify_programs()
            
            print_phase_complete("Phase 1", len(self.temp_links))
            
        except Exception as e:
            print(f"❌ 获取项目列表失败: {e}", flush=True)
    
    def _handle_cookie_consent(self) -> None:
        """处理Cookie同意对话框"""
        try:
            # 等待并尝试点击"OK"或"Accept"按钮
            accept_selectors = [
                "button.cc-dismiss",
                "button[aria-label*='accept']",
                "button[aria-label*='Accept']",
                "button#onetrust-accept-btn-handler",
                "a.cc-btn"
            ]
            
            for selector in accept_selectors:
                try:
                    accept_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    accept_button.click()
                    print("   ✅ 已接受 Cookie", flush=True)
                    time.sleep(1)
                    return
                except:
                    continue
            
            print("   ℹ️ 未找到 Cookie 对话框", flush=True)
            
        except Exception:
            pass
    
    def _apply_study_area_filter(self, study_area: str) -> None:
        """
        应用Study area筛选器
        
        参数:
            study_area (str): 要筛选的Study area名称
        """
        try:
            # 首先尝试关闭任何已打开的筛选器面板
            try:
                # 查找可能打开的筛选器面板并关闭
                # 点击"Study area"按钮如果它已经展开则会关闭
                # 或者查找关闭按钮/backdrop点击
                backdrop = self.driver.find_elements(By.CSS_SELECTOR, ".backdrop, [class*='backdrop']")
                if backdrop:
                    backdrop[0].click()
                    time.sleep(0.5)
            except:
                pass
            
            # 点击"Study area"按钮打开筛选器
            study_area_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Study area')]"))
            )
            
            # 滚动到按钮位置
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", study_area_button)
            time.sleep(0.5)
            
            # 使用JavaScript点击确保成功
            self.driver.execute_script("arguments[0].click();", study_area_button)
            time.sleep(1.5)  # 增加等待时间
            
            # 等待复选框出现
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='checkbox']"))
            )
            
            # 找到对应的复选框并点击
            # 复选框通常在label中,label文本包含study area名称
            checkbox_label = self.driver.find_element(
                By.XPATH,
                f"//label[contains(text(), '{study_area}')]"
            )
            
            # 滚动到复选框位置
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkbox_label)
            time.sleep(0.5)
            
            # 使用JavaScript点击复选框label
            self.driver.execute_script("arguments[0].click();", checkbox_label)
            time.sleep(0.5)
            
            # 点击"APPLY"按钮应用筛选
            apply_button = self.driver.find_element(
                By.XPATH,
                "//button[contains(text(), 'APPLY') or contains(text(), 'Apply')]"
            )
            
            # 使用JavaScript点击确保成功
            self.driver.execute_script("arguments[0].click();", apply_button)
            time.sleep(2)  # 等待筛选结果加载
            
            print(f"      ✅ 已应用筛选: {study_area}", flush=True)
            
        except Exception as e:
            print(f"      ⚠️ 应用筛选失败: {e}", flush=True)
            raise
    
    def _extract_all_programs_in_area(self, study_area: str) -> None:
        """
        提取当前Study area下的所有项目(处理分页)
        
        参数:
            study_area (str): 当前Study area名称
        """
        page_num = 1
        total_extracted = 0
        
        while True:
            # 提取当前页面的项目
            count = self._extract_programs_from_page(study_area)
            total_extracted += count
            
            print(f"      📄 第 {page_num} 页: 提取 {count} 个项目 (累计: {total_extracted})", flush=True)
            
            if count == 0:
                break
            
            # 检查是否有下一页
            if not self._has_next_page():
                print(f"      ✅ [{study_area}] 已到达最后一页", flush=True)
                break
            
            # 点击下一页
            if not self._click_next_page():
                print(f"      ⚠️ 无法点击下一页,停止翻页", flush=True)
                break
            
            page_num += 1
            time.sleep(2)  # 等待下一页加载
        
        print(f"      ✅ [{study_area}] 共提取 {total_extracted} 个项目", flush=True)
        
        # 重置筛选器,准备下一个Study area
        self._reset_filters()
    
    def _extract_programs_from_current_page(self) -> int:
        """
        从当前页面提取项目信息（不使用Study area筛选）
        
        返回:
            int: 提取的项目数量
        """
        extracted_count = 0
        
        try:
            # 等待课程卡片加载
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article, .course-card, a[href*='/course/']"))
            )
            
            # 查找所有课程链接
            course_links = self.driver.find_elements(
                By.CSS_SELECTOR,
                "a[href*='/course/']"
            )
            
            for link in course_links:
                try:
                    href = link.get_attribute("href")
                    
                    # 过滤掉非详情页链接
                    if not href or '/find-a-course/' in href:
                        continue
                    
                    # 确保是完整的课程详情页链接
                    if not re.match(r'https://www\.deakin\.edu\.au/course/[^/]+$', href):
                        continue
                    
                    # 获取课程名称
                    course_title = link.text.strip()
                    if not course_title or len(course_title) < 3:
                        course_title = link.get_attribute("title") or ""
                    
                    if not course_title or len(course_title) < 3:
                        continue
                    
                    # 清理课程名称
                    course_title = re.sub(r'\s+', ' ', course_title).strip()
                    
                    # 添加到列表（不筛选，学习领域设为N/A）
                    self.temp_links.append({
                        "name": course_title,
                        "link": href,
                        "study_area": "N/A"  # 不筛选时无法确定学习领域
                    })
                    extracted_count += 1
                    
                except Exception:
                    continue
            
        except TimeoutException:
            print(f"      ⚠️ 页面加载超时", flush=True)
        except Exception as e:
            print(f"      ⚠️ 提取项目失败: {e}", flush=True)
        
        return extracted_count
    
    def _extract_programs_from_page(self, study_area: str) -> int:
        """
        从当前页面提取项目信息
        
        参数:
            study_area (str): 当前Study area(将作为"学院"字段)
        
        返回:
            int: 提取的项目数量
        """
        extracted_count = 0
        # 移除去重逻辑，允许同一项目出现在多个Study area下
        
        try:
            # 等待课程卡片加载
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article, .course-card, a[href*='/course/']"))
            )
            
            # 查找所有课程链接
            # Deakin的课程链接格式: /course/xxx
            course_links = self.driver.find_elements(
                By.CSS_SELECTOR,
                "a[href*='/course/']"
            )
            
            for link in course_links:
                try:
                    href = link.get_attribute("href")
                    
                    # 过滤掉非详情页链接
                    if not href or '/find-a-course/' in href:
                        continue
                    
                    # 确保是完整的课程详情页链接
                    if not re.match(r'https://www\.deakin\.edu\.au/course/[^/]+$', href):
                        continue
                    
                    # 获取课程名称
                    # 尝试从文本或title属性提取
                    course_title = link.text.strip()
                    if not course_title or len(course_title) < 3:
                        course_title = link.get_attribute("title") or ""
                    
                    if not course_title or len(course_title) < 3:
                        continue
                    
                    # 清理课程名称(去除多余的换行和空格)
                    course_title = re.sub(r'\s+', ' ', course_title).strip()
                    
                    # 添加到列表（不去重，允许重复）
                    self.temp_links.append({
                        "name": course_title,
                        "link": href,
                        "study_area": study_area  # 直接使用Study area
                    })
                    extracted_count += 1
                    
                except Exception:
                    continue
            
        except TimeoutException:
            print(f"      ⚠️ 页面加载超时", flush=True)
        except Exception as e:
            print(f"      ⚠️ 提取项目失败: {e}", flush=True)
        
        return extracted_count
    
    def _has_next_page(self) -> bool:
        """检查是否有下一页"""
        try:
            # 策略: 查找 Next 按钮 (a.next)
            # 如果存在且父元素 li 没有 disabled 类，则表示有下一页
            next_link = self.driver.find_elements(By.CSS_SELECTOR, "a.next")
            
            if not next_link:
                return False
                
            # 检查父元素 li 是否 disabled
            try:
                parent_li = next_link[0].find_element(By.XPATH, "./..")
                li_class = parent_li.get_attribute("class") or ""
                if "disabled" in li_class:
                    return False
                return True
            except:
                # 无法获取父元素，假设如果有a.next就能点击
                return True
            
        except Exception:
            return False
    
    def _click_next_page(self) -> bool:
        """点击下一页按钮"""
        try:
            next_buttons = self.driver.find_elements(By.CSS_SELECTOR, "a.next")
            if not next_buttons:
                return False
            
            next_button = next_buttons[0]
            
            # 滚动到按钮位置
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            time.sleep(0.5)
            
            # 点击
            try:
                next_button.click()
            except ElementClickInterceptedException:
                self.driver.execute_script("arguments[0].click();", next_button)
            
            return True
            
        except Exception:
            return False
    
    def _reset_filters(self) -> None:
        """重置所有筛选器,准备下一个Study area"""
        try:
            # 查找并点击"RESET"按钮
            reset_button = self.driver.find_element(
                By.XPATH,
                "//button[contains(text(), 'RESET') or contains(text(), 'Reset')]"
            )
            
            reset_button.click()
            time.sleep(1.5)
            
            print(f"      🔄 已重置筛选器", flush=True)
            
        except Exception:
            # 如果没有RESET按钮,刷新页面
            print(f"      🔄 刷新页面以重置筛选器", flush=True)
            self.driver.get(self.list_url)
            time.sleep(2)

    def _collect_links_from_page(self) -> List[str]:
        """
        收集当前页面的所有项目链接
        """
        links = []
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article, .course-card, a[href*='/course/']"))
            )
            elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/course/']")
            for el in elements:
                try:
                    href = el.get_attribute("href")
                    if href and '/course/' in href and '/find-a-course/' not in href:
                         # 确保是完整的课程详情页链接
                        if re.match(r'https://www\.deakin\.edu\.au/course/[^/]+$', href):
                            links.append(href)
                except:
                    continue
        except:
            pass
        return links

    def _classify_programs(self) -> None:
        """
        Phase 1.5: 遍历Study Area筛选器，对已抓取的项目进行分类
        """
        print_phase_start("Phase 1.5", f"正在对 {len(self.temp_links)} 个项目进行分类...", total=len(self.study_areas))
        
        # 建立链接映射表 {link: item}
        # 使用 URL 作为键，方便快速查找
        link_map = {item['link']: item for item in self.temp_links}
        
        try:
            # 确保在列表页
            if "postgraduate-courses" not in self.driver.current_url:
                self.driver.get(self.list_url)
                time.sleep(2)
            
            for idx, area in enumerate(self.study_areas, 1):
                print(f"   📚 [{idx}/{len(self.study_areas)}] 正在扫描分类: {area}", flush=True)
                
                try:
                    self._apply_study_area_filter(area)
                    
                    # 遍历该分类下的所有分页
                    while True:
                        # 收集当前页链接
                        links = self._collect_links_from_page()
                        
                        # 更新分类信息
                        match_count = 0
                        for link in links:
                            if link in link_map:
                                item = link_map[link]
                                if item['study_area'] == "N/A":
                                    item['study_area'] = area
                                elif area not in item['study_area']:
                                    item['study_area'] += f", {area}"
                                match_count += 1
                        
                        # print(f"      - 本页匹配: {match_count}/{len(links)}", flush=True)
                        
                        if not self._has_next_page():
                            break
                            
                        if not self._click_next_page():
                            break
                            
                        time.sleep(1.5)
                        
                except Exception as e:
                    print(f"      ⚠️ 分类扫描失败: {e}", flush=True)
                
                self._reset_filters()
                time.sleep(1)
                
        except Exception as e:
            print(f"❌ 分类过程出错: {e}", flush=True)
    
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
        
        参数:
            item (Dict): 包含 name, link 和 study_area 的项目信息
        
        返回:
            tuple: (结果字典, 耗时秒数)
        """
        item_start = time.time()
        
        # 创建结果模板
        result = self.create_result_template(item['name'], item['link'])
        
        # 设置学习领域(直接使用Study area)
        result["学院/学习领域"] = item.get('study_area', 'N/A')
        
        # 设置统一的申请链接
        result["申请链接"] = self.university_info.get("apply_register_url", "N/A")
        
        # 从浏览器池获取实例
        with self.browser_pool.get_browser() as driver:
            try:
                # 访问项目详情页
                driver.get(item['link'])
                
                # 等待页面加载
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1, main"))
                )
                
                # 提取Key dates(deadline)
                result["项目deadline"] = self._extract_key_dates(driver)
                
                # Deakin的opendate通常在Key dates中一起显示
                # 这里可以进一步细化提取
                
            except TimeoutException:
                # 详情页加载超时
                pass
            except Exception:
                # 其他错误
                pass
        
        duration = time.time() - item_start
        return result, duration
    
    def _extract_key_dates(self, driver) -> str:
        """
        提取Key dates信息
        
        从详情页中查找"Key dates"部分,提取deadline信息
        """
        try:
            # 策略1: 查找特定标题标签 (h3, h4, strong) 包含 "Key dates"
            # 这样可以避免匹配到导航栏或其他无关区域的 "Key dates" 文本
            headers = driver.find_elements(
                By.XPATH,
                "//h3[contains(text(), 'Key dates')] | //h4[contains(text(), 'Key dates')] | //strong[contains(text(), 'Key dates')]"
            )
            
            for header in headers:
                try:
                    # 尝试1: 获取紧邻的下一个兄弟元素
                    # 通常 Key dates 标题下紧跟一个 p 标签含有具体日期
                    try:
                        sibling = header.find_element(By.XPATH, "following-sibling::*[1]")
                        text = sibling.text.strip()
                        if text and len(text) > 10:
                            return text
                    except:
                        pass
                    
                    # 尝试2: 如果没有兄弟元素或兄弟元素为空，尝试获取父容器的文本
                    parent = header.find_element(By.XPATH, "./..")
                    text = parent.text.strip()
                    
                    if text and len(text) > 10:
                        # 清理文本
                        cleaned_text = re.sub(r'\s+', ' ', text).strip()
                        # 移除"Key dates"标题本身
                        cleaned_text = cleaned_text.replace('Key dates', '').strip()
                        
                        # 简单的长度检查，避免获取到整个页面的文本
                        if cleaned_text and len(cleaned_text) < 500:
                            return cleaned_text
                            
                except Exception:
                    continue
            
            # 策略2: 保留原有的宽泛搜索作为后备，但增加过滤
            key_dates_section = driver.find_elements(
                By.XPATH,
                "//*[contains(text(), 'Key dates')]"
            )
            
            for section in key_dates_section:
                try:
                    # 跳过隐藏元素
                    if not section.is_displayed():
                        continue

                    # 获取父容器文本
                    parent = section.find_element(By.XPATH, "./..")
                    text = parent.text.strip()
                    
                    # 增加过滤：必须包含 "close" 或 "deadline" 或 "application"
                    if text and len(text) > 10:
                        cleaned_text = re.sub(r'\s+', ' ', text).strip()
                        cleaned_text = cleaned_text.replace('Key dates', '').strip()
                        
                        lower_text = cleaned_text.lower()
                        if ('close' in lower_text or 'deadline' in lower_text or 'application' in lower_text) and len(cleaned_text) < 300:
                             return cleaned_text

                except Exception:
                    continue

            return "N/A"
            
        except Exception:
            return "N/A"


if __name__ == "__main__":
    # 测试代码
    with DeakinSpider(headless=False) as spider:
        results = spider.run()
        
        print(f"\n抓取完成,共 {len(results)} 个项目")
        if results:
            import json
            print("\n前3个项目示例:")
            print(json.dumps(results[:3], indent=2, ensure_ascii=False))
