# -*- coding: utf-8 -*-
"""
工具模块包
包含浏览器驱动管理、数据保存、进度显示和 Selenium 通用操作
"""

from .browser import get_driver
from .data_saver import save_excel, save_csv, preview_data, preview_full_data
from .progress import CrawlerProgress, print_phase_start, print_phase_complete
from .selenium_utils import (
    BrowserPool,
    get_browser_pool,
    close_browser_pool,
    wait_for_new_window,
    safe_click,
    wait_and_get_text,
    wait_and_get_attribute,
    switch_to_new_window_and_get_url,
    extract_final_apply_url
)

__all__ = [
    # 浏览器管理
    'get_driver',
    'BrowserPool',
    'get_browser_pool',
    'close_browser_pool',
    # 数据保存
    'save_excel', 
    'save_csv', 
    'preview_data', 
    'preview_full_data',
    # 进度显示
    'CrawlerProgress',
    'print_phase_start',
    'print_phase_complete',
    # Selenium 工具
    'wait_for_new_window',
    'safe_click',
    'wait_and_get_text',
    'wait_and_get_attribute',
    'switch_to_new_window_and_get_url',
    'extract_final_apply_url'
]

