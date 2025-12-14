# -*- coding: utf-8 -*-
"""
浏览器驱动管理模块
封装 Selenium WebDriver 的初始化和配置
"""

import os
import json
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# 缓存 ChromeDriver 路径，避免重复下载检查
_cached_driver_path = None

# #region agent log
_DEBUG_LOG_PATH = r"d:\Project\MySpiderProject\.cursor\debug.log"
def _debug_log(hypothesis_id, location, message, data=None):
    import time
    entry = {"hypothesisId": hypothesis_id, "location": location, "message": message, "data": data or {}, "timestamp": int(time.time()*1000), "sessionId": "debug-session"}
    with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
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
    
    # --- 性能优化配置（核心加速）---
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--log-level=3")  # 只显示致命错误
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-default-apps")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-translate")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--disable-features=TranslateUI")
    chrome_options.add_argument("--metrics-recording-only")
    chrome_options.add_argument("--mute-audio")
    
    # 禁用渲染加速（减少资源占用）
    chrome_options.add_argument("--disable-accelerated-2d-canvas")
    chrome_options.add_argument("--disable-accelerated-jpeg-decoding")
    chrome_options.add_argument("--disable-accelerated-mjpeg-decode")
    chrome_options.add_argument("--disable-accelerated-video-decode")
    
    # --- 无头模式配置 ---
    if headless:
        # #region agent log
        _debug_log("A", "browser.py:headless", "Using headless mode", {"mode": "headless=new"})
        # #endregion
        chrome_options.add_argument("--headless=new")  # 使用新版无头模式
        chrome_options.add_argument("--window-size=1280,720")  # 减小窗口尺寸
    
    # --- 伪装配置 ---
    # --- 伪装配置 (随机 User-Agent) ---
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
    ]
    ua = random.choice(user_agents)
    
    # #region agent log
    _debug_log("F", "browser.py:ua_config", "Selected User-Agent", {"ua": ua})
    # #endregion
    
    chrome_options.add_argument(f"user-agent={ua}")
    
    # --- 快速模式额外优化 ---
    prefs = {
        # 禁止加载图片
        "profile.managed_default_content_settings.images": 2,
        # 禁用通知
        "profile.default_content_setting_values.notifications": 2,
        # 禁用地理位置
        "profile.default_content_setting_values.geolocation": 2,
        # 禁用自动填充
        "profile.password_manager_enabled": False,
        "credentials_enable_service": False,
    }
    
    if fast_mode:
        # 禁用 JavaScript（注意：某些页面可能需要 JS）
        # prefs["profile.managed_default_content_settings.javascript"] = 2
        # 禁用字体
        prefs["profile.managed_default_content_settings.fonts"] = 2
        # 禁用插件
        prefs["profile.managed_default_content_settings.plugins"] = 2
        # 禁用弹窗
        prefs["profile.managed_default_content_settings.popups"] = 2
        # 禁用 CSS（可能影响布局判断，谨慎使用）
        # prefs["profile.managed_default_content_settings.stylesheets"] = 2
    
    chrome_options.add_experimental_option("prefs", prefs)
    
    # 禁用自动化提示
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # --- 创建驱动实例 ---
    # 缓存 ChromeDriver 路径，避免重复检查
    if _cached_driver_path is None or not os.path.exists(_cached_driver_path):
        _cached_driver_path = ChromeDriverManager().install()
    
    service = Service(_cached_driver_path)
    
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

