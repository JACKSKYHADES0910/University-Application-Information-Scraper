# -*- coding: utf-8 -*-
"""
爬虫基类模块
定义所有大学爬虫的通用接口和基础功能
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import time
import re
import random

from selenium.webdriver.remote.webdriver import WebDriver

# 尝试导入 rich 库
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from utils.browser import get_driver, close_driver
from config import UNIVERSITY_INFO

# 创建全局 Console 实例
console = Console() if RICH_AVAILABLE else None


class BaseSpider(ABC):
    """
    爬虫基类
    
    所有大学的爬虫都应该继承此类，并实现 run() 方法。
    
    属性:
        university_key (str): 大学标识（如 "hku", "hkbu"）
        university_info (dict): 大学相关配置信息
        driver (WebDriver): Selenium 浏览器驱动
        results (List[Dict]): 爬取结果列表
    
    使用示例:
        >>> class MySpider(BaseSpider):
        ...     def run(self):
        ...         # 实现具体爬取逻辑
        ...         pass
        >>> spider = MySpider("hku")
        >>> data = spider.run()
        >>> spider.close()
    """
    
    def __init__(self, university_key: str, headless: bool = True):
        """
        初始化爬虫实例
        
        参数:
            university_key (str): 大学标识（必须在 config.UNIVERSITY_INFO 中定义）
            headless (bool): 是否无头模式运行（默认 True）
        
        异常:
            ValueError: 如果 university_key 不存在于配置中
        """
        # 验证大学标识
        if university_key not in UNIVERSITY_INFO:
            available = ", ".join(UNIVERSITY_INFO.keys())
            raise ValueError(
                f"未知的大学标识: '{university_key}'\n"
                f"可用选项: {available}"
            )
        
        self.university_key = university_key
        self.university_info = UNIVERSITY_INFO[university_key]
        self.headless = headless
        
        # 初始化浏览器驱动（延迟加载）
        self._driver: Optional[WebDriver] = None
        
        # 存储爬取结果
        self.results: List[Dict] = []
        
        # 记录开始时间
        self.start_time: Optional[float] = None
        
        print(f"[-] 初始化爬虫: {self.university_info['name_cn']} ({self.university_info['name']})")
    
    @property
    def driver(self) -> WebDriver:
        """
        懒加载浏览器驱动
        只有在第一次访问时才会创建驱动实例
        """
        if self._driver is None:
            # 简化启动过程，避免 rich console 干扰
            print("🌐 正在启动浏览器 (Browser Launching)...")
            self._driver = get_driver(self.headless)
        return self._driver
    
    @property
    def base_url(self) -> str:
        """获取大学网站基础 URL"""
        return self.university_info['base_url']
    
    @property
    def list_url(self) -> str:
        """获取项目列表页 URL"""
        return self.university_info['list_url']
    
    @property
    def school_code(self) -> str:
        """获取学校代码"""
        return self.university_info['code']
    
    @property
    def school_name(self) -> str:
        """获取学校名称"""
        return self.university_info['name']
    
    def create_result_template(self, program_name: str, program_link: str) -> Dict:
        """
        创建结果数据模板
        
        参数:
            program_name (str): 项目名称
            program_link (str): 项目链接
        
        返回:
            Dict: 预填充了基本信息的结果字典
        """
        return {
            "学校代码": self.school_code,
            "学校名称": self.school_name,
            "项目名称": program_name,
            "学院/学习领域": "N/A",  # 统一字段：Faculty或Study Area
            "项目官网链接": program_link,
            "申请链接": "N/A",
            "项目opendate": "N/A",
            "项目deadline": "N/A",
            "学生案例": "",
            "面试问题": ""
        }
    
    @abstractmethod
    def run(self) -> List[Dict]:
        """
        执行爬取任务（子类必须实现）
        
        返回:
            List[Dict]: 爬取到的数据列表
        """
        pass
    
    def close(self) -> None:
        """
        关闭浏览器，释放资源
        
        在完成爬取后必须调用此方法来清理资源
        """
        if self._driver is not None:
            print("🔒 正在关闭浏览器...")
            close_driver(self._driver)
            self._driver = None
    
    def get_elapsed_time(self) -> float:
        """
        获取已运行时间（秒）
        
        返回:
            float: 已运行秒数
        """
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time
    
    def print_summary(self) -> None:
        """
        打印爬取结果摘要
        """
        elapsed = self.get_elapsed_time()
        
        # 格式化时间
        if elapsed >= 60:
            time_str = f"{elapsed/60:.2f} 分钟 ({elapsed:.1f} 秒)"
        else:
            time_str = f"{elapsed:.2f} 秒"
        
        if RICH_AVAILABLE and console:
            # 使用 rich 美化输出
            table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
            table.add_column("项目", style="cyan", width=12)
            table.add_column("值", style="green")
            
            table.add_row("🏫 目标学校", f"{self.university_info['name_cn']} ({self.university_info['name']})")
            table.add_row("📊 获取数据", f"[bold]{len(self.results)}[/bold] 条")
            table.add_row("⏱️ 总耗时", time_str)
            
            console.print()
            console.print(Panel(
                table,
                title="[bold green]🎉 爬取完成！[/bold green]",
                border_style="green",
                padding=(1, 2)
            ))
            console.print()
        else:
            # 简单文本输出
            print("\n" + "=" * 50)
            print(f"🎉 爬取完成！")
            print(f"🏫 目标学校: {self.university_info['name_cn']}")
            print(f"📊 获取数据: {len(self.results)} 条")
            print(f"⏱️ 总耗时: {time_str}")
            print("=" * 50)
    
    def _clean_text(self, text: str) -> str:
        """
        清洗文本：去空白、换行
        """
        if not text:
            return ""
        # 替换多余空白
        return re.sub(r'\s+', ' ', text).strip()

    def random_sleep(self, min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """
        随机休眠一段时间，模拟人类操作
        """
        sleep_time = random.uniform(min_seconds, max_seconds)
        time.sleep(sleep_time)

    def __enter__(self):
        """支持 with 语句"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出 with 语句时自动关闭浏览器"""
        self.close()
        return False

