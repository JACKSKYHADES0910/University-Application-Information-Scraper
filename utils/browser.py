# -*- coding: utf-8 -*-
"""
浏览器驱动管理模块
封装 Selenium WebDriver 的初始化和配置
"""

import os
import json
import random
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# 解决 SSL 证书验证失败导致无法下载驱动的问题
os.environ['WDM_SSL_VERIFY'] = '0'

# 缓存 ChromeDriver 路径，避免重复下载检查
_cached_driver_path = None

# #region agent log
_DEBUG_LOG_PATH = r"d:\Project\MySpiderProject\.cursor\debug.log"
def _debug_log(hypothesis_id, location, message, data=None):
    import time
    # Ensure directory exists
    log_dir = os.path.dirname(_DEBUG_LOG_PATH)
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception:
            pass  # Fail silently if cannot create directory
            
    entry = {"hypothesisId": hypothesis_id, "location": location, "message": message, "data": data or {}, "timestamp": int(time.time()*1000), "sessionId": "debug-session"}
    try:
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Fail silently if cannot write to log
# #endregion


def get_driver(headless: bool = True, fast_mode: bool = True) -> webdriver.Chrome:
    """
    创建并返回一个配置好的 Chrome WebDriver 实例
    
    参数:
        headless (bool): 是否启用无头模式
            - True: 后台运行，看不到浏览器窗口（默认，推荐用于批量抓取）
            - False: 前台运行，可以看到浏览器窗口（用于调试）
        fast_mode (bool): 是否启用快速模式（禁用更多资源加载）
    
    返回:
        webdriver.Chrome: 配置好的 Chrome 驱动实例
    
    使用示例:
        >>> driver = get_driver(headless=True)
        >>> driver.get("https://example.com")
        >>> driver.quit()
    """
    # #region agent log
    _debug_log("START", "browser.py:entry", "get_driver called", {"headless": headless, "fast_mode": fast_mode})
    # #endregion
    
    global _cached_driver_path
    
    # 创建 Chrome 配置选项
    chrome_options = Options()
    
    # --- 基础配置 ---
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--disable-extensions")
    
    # 关键稳定性配置
    # chrome_options.add_argument("--remote-debugging-port=0")  # Removed: causing crash on some systems
    # chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    
    # 强制使用唯一临时配置目录，彻底解决冲突
    # user_data_dir = tempfile.mkdtemp(prefix="chrome_test_")
    # chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    
    # 基础性能优化
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--log-level=3")
    
    # --- 无头模式配置 ---
    if headless:
        # #region agent log
        _debug_log("A", "browser.py:headless", "Using headless mode", {"mode": "headless=new"})
        # #endregion
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-gpu") # Ensure GPU is disabled for stability
    
    # --- 简化的实验性选项 ---
    # chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    # chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # 基础 prefs - 仅禁用图片以加速
    # prefs = {
    #     "profile.managed_default_content_settings.images": 2,
    # }
    # chrome_options.add_experimental_option("prefs", prefs)
    
    # --- 创建驱动实例 ---
    # 使用 webdriver_manager 自动管理驱动 (更稳健)
    if _cached_driver_path is None or (_cached_driver_path != "AUTO" and not os.path.exists(_cached_driver_path)):
        try:
            print("🔍 正在检查/更新 ChromeDriver...")
            from webdriver_manager.chrome import ChromeDriverManager
            # Automatic detection
            _cached_driver_path = ChromeDriverManager().install()
            print(f"✅ Driver installed at: {_cached_driver_path}")
        except Exception as e:
            print(f"⚠️ webdriver_manager failed: {e}. Falling back to Selenium Manager.")
            _cached_driver_path = "AUTO"

    # 根据模式选择Service
    if _cached_driver_path == "AUTO":
        service = None  # 让 Selenium Manager 自动处理
        print("✅ 将使用 Selenium Manager 自动管理驱动")
    else:
        service = Service(_cached_driver_path)
        print(f"✅ 使用驱动: {_cached_driver_path}")
    
    # #region agent log
    _debug_log("C", "browser.py:before_create", "Creating Chrome driver", {"driver_path": _cached_driver_path})
    # #endregion
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        # #region agent log
        _debug_log("C", "browser.py:after_create", "Chrome driver created successfully", {})
        # #endregion
    except Exception as e:
        # #region agent log
        _debug_log("C", "browser.py:create_error", "Failed to create driver", {"error": str(e)})
        # #endregion
        raise
    
    # 设置页面加载策略为 eager（DOM 加载完成即可，不等待资源）
    try:
        # #region agent log
        _debug_log("D", "browser.py:before_cdp", "Executing CDP command", {})
        # #endregion
        driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "deny", "downloadPath": ""})
        # #region agent log
        _debug_log("D", "browser.py:after_cdp", "CDP command succeeded", {})
        # #endregion
    except Exception as e:
        # #region agent log
        _debug_log("D", "browser.py:cdp_error", "CDP command failed", {"error": str(e)})
        # #endregion
    
    # 减少隐式等待时间
    # #region agent log
    _debug_log("E", "browser.py:wait_config", "Setting wait times", {"implicit": 5, "page_load": 30})
    # #endregion
    driver.implicitly_wait(5)
    
    # 设置页面加载超时
    driver.set_page_load_timeout(30)
    
    # #region agent log
    _debug_log("ALL", "browser.py:return", "Driver ready", {})
    # #endregion
    return driver


def close_driver(driver: webdriver.Chrome) -> None:
    """
    安全关闭浏览器驱动
    
    参数:
        driver (webdriver.Chrome): 需要关闭的驱动实例
    """
    if driver:
        try:
            driver.quit()
        except Exception as e:
            print(f"⚠️ 关闭浏览器时出错: {e}")

