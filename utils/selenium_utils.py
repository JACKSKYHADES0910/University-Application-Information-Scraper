# -*- coding: utf-8 -*-
"""
Selenium 通用工具模块
封装常用的 Selenium 操作，供所有爬虫复用
"""

import time
import queue
import threading
from typing import Optional, List, Callable
from contextlib import contextmanager

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from utils.browser import get_driver, close_driver


class BrowserPool:
    """
    浏览器实例池
    
    复用浏览器实例，避免频繁创建和销毁，大幅提升并发性能
    
    使用示例:
        >>> pool = BrowserPool(size=10)
        >>> with pool.get_browser() as driver:
        ...     driver.get("https://example.com")
        >>> pool.close_all()
    """
    
    def __init__(self, size: int = 8, headless: bool = True):
        """
        初始化浏览器池
        
        参数:
            size (int): 池大小（浏览器实例数量）
            headless (bool): 是否无头模式
        """
        self.size = size
        self.headless = headless
        self._pool: queue.Queue = queue.Queue()
        self._all_browsers: List[WebDriver] = []
        self._lock = threading.Lock()
        self._initialized = False
    
    def initialize(self) -> None:
        """
        预创建浏览器实例填充池
        比按需创建更快，因为可以并行初始化
        """
        if self._initialized:
            return
        
        print(f"🌐 正在预热浏览器池 ({self.size} 个实例)...")
        
        # 并行创建浏览器实例
        def create_browser():
            driver = get_driver(headless=self.headless)
            with self._lock:
                self._all_browsers.append(driver)
                self._pool.put(driver)
        
        threads = []
        for _ in range(self.size):
            t = threading.Thread(target=create_browser)
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        self._initialized = True
        print(f"✅ 浏览器池预热完成")
    
    @contextmanager
    def get_browser(self, timeout: float = 30):
        """
        从池中获取浏览器实例（上下文管理器）
        
        参数:
            timeout (float): 等待超时时间（秒）
        
        用法:
            with pool.get_browser() as driver:
                driver.get(url)
        """
        # 确保池已初始化
        if not self._initialized:
            self.initialize()
        
        driver = None
        try:
            driver = self._pool.get(timeout=timeout)
            yield driver
        finally:
            if driver:
                # 清理浏览器状态后归还
                try:
                    # 关闭所有额外窗口，只保留主窗口
                    if len(driver.window_handles) > 1:
                        main_window = driver.window_handles[0]
                        for handle in driver.window_handles[1:]:
                            driver.switch_to.window(handle)
                            driver.close()
                        driver.switch_to.window(main_window)
                    
                    # 清除 cookies 和本地存储
                    driver.delete_all_cookies()
                except:
                    pass
                
                self._pool.put(driver)
    
    def close_all(self) -> None:
        """
        关闭所有浏览器实例
        """
        print("🔒 正在关闭浏览器池...")
        for driver in self._all_browsers:
            try:
                close_driver(driver)
            except:
                pass
        self._all_browsers.clear()
        self._initialized = False
        print("✅ 浏览器池已关闭")


def wait_for_new_window(
    driver: WebDriver, 
    original_handles: set,
    timeout: float = 10,
    poll_interval: float = 0.5
) -> Optional[str]:
    """
    等待新窗口打开
    
    参数:
        driver: WebDriver 实例
        original_handles: 原始窗口句柄集合
        timeout (float): 超时时间（秒）
        poll_interval (float): 轮询间隔（秒）
    
    返回:
        str: 新窗口句柄，如果超时返回 None
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        current_handles = set(driver.window_handles)
        new_handles = current_handles - original_handles
        if new_handles:
            return new_handles.pop()
        time.sleep(poll_interval)
    return None


def safe_click(driver: WebDriver, element, use_js: bool = True) -> bool:
    """
    安全点击元素
    
    参数:
        driver: WebDriver 实例
        element: 要点击的元素
        use_js (bool): 是否使用 JavaScript 点击（更可靠）
    
    返回:
        bool: 是否成功点击
    """
    try:
        if use_js:
            driver.execute_script("arguments[0].click();", element)
        else:
            element.click()
        return True
    except Exception:
        return False


def wait_and_get_text(
    driver: WebDriver,
    locator: tuple,
    timeout: float = 10,
    default: str = "N/A"
) -> str:
    """
    等待元素出现并获取文本
    
    参数:
        driver: WebDriver 实例
        locator: 定位器元组，如 (By.XPATH, "//div")
        timeout (float): 超时时间
        default (str): 默认值
    
    返回:
        str: 元素文本或默认值
    """
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(locator)
        )
        return element.text.strip()
    except (TimeoutException, NoSuchElementException):
        return default


def wait_and_get_attribute(
    driver: WebDriver,
    locator: tuple,
    attribute: str,
    timeout: float = 10,
    default: str = "N/A"
) -> str:
    """
    等待元素出现并获取属性
    
    参数:
        driver: WebDriver 实例
        locator: 定位器元组
        attribute (str): 属性名
        timeout (float): 超时时间
        default (str): 默认值
    
    返回:
        str: 属性值或默认值
    """
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(locator)
        )
        return element.get_attribute(attribute) or default
    except (TimeoutException, NoSuchElementException):
        return default


def switch_to_new_window_and_get_url(
    driver: WebDriver,
    click_element,
    timeout: float = 10,
    wait_for_load: float = 2
) -> Optional[str]:
    """
    点击元素后切换到新窗口并获取 URL
    
    专门用于处理点击后打开新窗口的场景
    
    参数:
        driver: WebDriver 实例
        click_element: 要点击的元素
        timeout (float): 等待新窗口超时
        wait_for_load (float): 等待页面加载时间
    
    返回:
        str: 新窗口的 URL，失败返回 None
    """
    original_handles = set(driver.window_handles)
    main_window = driver.current_window_handle
    
    # 点击元素
    safe_click(driver, click_element)
    
    # 等待新窗口
    new_handle = wait_for_new_window(driver, original_handles, timeout)
    
    if new_handle:
        try:
            driver.switch_to.window(new_handle)
            time.sleep(wait_for_load)  # 等待页面加载
            url = driver.current_url
            
            # 关闭新窗口，回到原窗口
            driver.close()
            driver.switch_to.window(main_window)
            
            return url
        except:
            # 确保回到主窗口
            try:
                driver.switch_to.window(main_window)
            except:
                pass
    
    return None


def extract_final_apply_url(
    driver: WebDriver,
    apply_button_locator: tuple,
    intermediate_link_locator: tuple = None,
    timeout: float = 10
) -> str:
    """
    提取最终申请链接（处理多步骤跳转）
    
    专门处理类似 HKU 的复杂申请流程：
    1. 点击 Apply Now -> 打开说明页
    2. 点击 Applying 链接 -> 打开最终申请页
    
    参数:
        driver: WebDriver 实例
        apply_button_locator: Apply 按钮定位器
        intermediate_link_locator: 中间页面链接定位器（可选）
        timeout (float): 超时时间
    
    返回:
        str: 最终申请 URL 或 "N/A"
    """
    main_window = driver.current_window_handle
    final_url = "N/A"
    
    try:
        # Step 1: 点击 Apply Now 按钮
        apply_btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(apply_button_locator)
        )
        
        original_handles = set(driver.window_handles)
        safe_click(driver, apply_btn)
        
        # 等待第一个新窗口
        new_handle = wait_for_new_window(driver, original_handles, timeout)
        
        if not new_handle:
            # 没有新窗口，尝试获取按钮的 href
            return apply_btn.get_attribute("href") or "N/A"
        
        # 切换到新窗口（说明页）
        driver.switch_to.window(new_handle)
        time.sleep(1)
        
        # Step 2: 如果有中间链接，点击它
        if intermediate_link_locator:
            try:
                intermediate_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable(intermediate_link_locator)
                )
                
                # 记录当前窗口数
                handles_before_click = set(driver.window_handles)
                
                # 点击中间链接
                safe_click(driver, intermediate_btn)
                
                # 等待可能的新窗口（申请系统页面）
                final_handle = wait_for_new_window(driver, handles_before_click, timeout=5)
                
                if final_handle:
                    # 新窗口打开了，获取 URL
                    driver.switch_to.window(final_handle)
                    time.sleep(1)
                    final_url = driver.current_url
                    driver.close()
                else:
                    # 没有新窗口，当前页面就是申请页
                    time.sleep(1)
                    final_url = driver.current_url
                    
            except (TimeoutException, NoSuchElementException):
                # 没找到中间链接，当前页面 URL 作为结果
                final_url = driver.current_url
        else:
            # 没有中间链接，直接获取当前 URL
            final_url = driver.current_url
        
    except Exception as e:
        pass
    finally:
        # 清理：关闭所有额外窗口，回到主窗口
        try:
            current_handles = driver.window_handles
            for handle in current_handles:
                if handle != main_window:
                    driver.switch_to.window(handle)
                    driver.close()
            driver.switch_to.window(main_window)
        except:
            pass
    
    return final_url


# 导出的全局浏览器池实例（可选使用）
_global_pool: Optional[BrowserPool] = None


def get_browser_pool(size: int = 8, headless: bool = True) -> BrowserPool:
    """
    获取全局浏览器池实例（单例模式）
    
    参数:
        size (int): 池大小
        headless (bool): 是否无头模式
    
    返回:
        BrowserPool: 浏览器池实例
    """
    global _global_pool
    if _global_pool is None:
        _global_pool = BrowserPool(size=size, headless=headless)
    return _global_pool


def close_browser_pool() -> None:
    """
    关闭全局浏览器池
    """
    global _global_pool
    if _global_pool:
        _global_pool.close_all()
        _global_pool = None

