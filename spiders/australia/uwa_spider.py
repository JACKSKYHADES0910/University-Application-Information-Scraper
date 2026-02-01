# -*- coding: utf-8 -*-
"""
西澳大学 (UWA) 爬虫
抓取 Postgraduate 项目信息，支持分页遍历
"""

import time
import random
import concurrent.futures
import requests
from typing import List, Dict, Tuple
from urllib.parse import urljoin, urlencode
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from spiders.base_spider import BaseSpider
from config import HEADERS, TIMEOUT

# 降低并发数以避免被限流
UWA_MAX_WORKERS = 8
UWA_MAX_RETRIES = 3


class UWASpider(BaseSpider):
    """
    西澳大学爬虫
    
    抓取所有 Postgraduate 项目，包括博士和其他研究生项目
    使用分页机制获取完整列表
    """
    
    def __init__(self, headless: bool = True):
        super().__init__("uwa", headless=headless)
        # 从配置获取申请链接
        self.apply_register_url = self.university_info.get(
            "apply_register_url", "https://www.uwa.edu.au/study/login"
        )
        self.apply_login_url = self.university_info.get(
            "apply_login_url", "https://www.uwa.edu.au/study/login"
        )
        # 分页参数
        self.results_per_page = 10
    
    def run(self) -> List[Dict]:
        """执行爬取任务"""
        self.start_time = time.time()
        
        print(f"[-] 开始抓取 {self.university_info.get('name', 'UWA')}...", flush=True)
        print(f"[-] 列表页: {self.list_url}", flush=True)
        
        # 1. 获取所有项目链接（带分页）
        print("\n[-] 获取项目列表（支持分页）...", flush=True)
        all_programs = self._get_all_program_links()
        print(f"[-] 共找到 {len(all_programs)} 个 Postgraduate 项目\n", flush=True)
        
        if not all_programs:
            print("[!] 未找到任何项目", flush=True)
            return []
        
        # 2. 并发处理项目详情页
        print(f"[-] 启动并发处理 (线程数: {UWA_MAX_WORKERS})...", flush=True)
        self.results = self._process_programs_concurrently(all_programs)
        
        # 3. 打印摘要
        self.print_summary()
        
        return self.results
    
    def _get_all_program_links(self) -> List[Tuple[str, str]]:
        """
        获取所有项目链接
        
        使用 num_ranks=300 参数一次性获取所有结果，避免分页问题
        
        返回:
            List[Tuple[str, str]]: [(项目名称, 项目URL), ...]
        """
        # 使用 num_ranks 参数一次性获取所有结果
        full_url = f"{self.list_url}&num_ranks=300"
        print(f"[-] 使用 num_ranks=300 获取所有结果...", flush=True)
        
        self.driver.get(full_url)
        time.sleep(4)  # 等待较长时间确保所有结果加载
        
        # 获取总结果数
        total_results = self._get_total_results()
        if total_results:
            print(f"[-] 搜索结果总数: {total_results}", flush=True)
        
        # 提取所有项目
        all_programs = self._extract_programs_from_page()
        print(f"[-] 成功获取 {len(all_programs)} 个项目", flush=True)
        
        return all_programs
    
    def _get_total_results(self) -> int:
        """从页面获取搜索结果总数"""
        try:
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # 查找 "1 - 10 of 209 search results" 格式的文本
            summary = soup.find(class_='search-results__summary')
            if summary:
                text = summary.get_text()
                import re
                match = re.search(r'of\s+(\d+)\s+search', text)
                if match:
                    return int(match.group(1))
        except Exception as e:
            print(f"[!] 获取结果总数失败: {e}", flush=True)
        return 0
    
    def _extract_programs_from_page(self) -> List[Tuple[str, str]]:
        """
        从当前页面提取项目信息
        
        返回:
            List[Tuple[str, str]]: [(项目名称, 项目URL), ...]
        """
        programs = []
        
        try:
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # 查找所有项目容器
            items = soup.select('article.listing-item')
            
            for item in items:
                try:
                    # 提取标题
                    title_elem = item.find('h3')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    # 提取URL (从 cite 标签获取直接URL)
                    cite_elem = item.find('cite')
                    if cite_elem:
                        url = cite_elem.get_text(strip=True)
                        # 确保URL完整
                        if not url.startswith('http'):
                            url = 'https://' + url
                    else:
                        # 备选：从链接获取
                        link_elem = item.find('a', href=True)
                        if link_elem:
                            href = link_elem.get('href', '')
                            # 处理重定向URL
                            if '/s/redirect?' in href:
                                import re
                                url_match = re.search(r'url=([^&]+)', href)
                                if url_match:
                                    from urllib.parse import unquote
                                    url = unquote(url_match.group(1))
                                else:
                                    continue
                            else:
                                url = urljoin(self.base_url, href)
                        else:
                            continue
                    
                    if title and url:
                        programs.append((title, url))
                        
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"[!] 提取页面项目失败: {e}", flush=True)
        
        return programs
    
    def _process_programs_concurrently(self, programs: List[Tuple[str, str]]) -> List[Dict]:
        """
        并发处理所有项目
        
        参数:
            programs: [(项目名称, 项目URL), ...]
        
        返回:
            List[Dict]: 处理后的项目数据列表
        """
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=UWA_MAX_WORKERS) as executor:
            # 提交所有任务
            future_to_program = {
                executor.submit(self._process_program, name, url): (name, url)
                for name, url in programs
            }
            
            # 处理结果
            for idx, future in enumerate(concurrent.futures.as_completed(future_to_program), 1):
                name, url = future_to_program[future]
                
                try:
                    data = future.result()
                    if data:
                        results.append(data)
                        print(f"[{idx}/{len(programs)}] [+] 成功: {name[:50]}...", flush=True)
                    else:
                        print(f"[{idx}/{len(programs)}] [!] 跳过: {name[:50]}...", flush=True)
                except Exception as e:
                    print(f"[{idx}/{len(programs)}] [x] 失败: {name[:50]}... - {e}", flush=True)
        
        return results
    
    def _process_program(self, name: str, url: str) -> Dict:
        """
        处理单个项目（运行在线程中）
        包含重试机制以应对服务器限流
        
        参数:
            name: 项目名称
            url: 项目URL
        
        返回:
            Dict: 项目数据
        """
        for attempt in range(UWA_MAX_RETRIES):
            try:
                # 添加随机延迟避免触发限流
                time.sleep(random.uniform(0.1, 0.5))
                
                # 使用 requests 获取详情页
                response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 创建基础数据
                    program_data = self.create_result_template(name, url)
                    
                    # 设置申请链接
                    program_data["申请链接"] = self.apply_register_url
                    
                    # 尝试提取额外信息
                    extra_info = self._extract_extra_info(soup)
                    if extra_info:
                        program_data["学生案例"] = extra_info
                    
                    return program_data
                
                elif response.status_code in [429, 503]:  # Rate limited or service unavailable
                    wait_time = (attempt + 1) * 2  # 指数退避
                    time.sleep(wait_time)
                    continue
                else:
                    # 其他错误，重试一次
                    if attempt < UWA_MAX_RETRIES - 1:
                        time.sleep(1)
                        continue
                    return None
                    
            except requests.exceptions.Timeout:
                if attempt < UWA_MAX_RETRIES - 1:
                    time.sleep(1)
                    continue
                return None
            except Exception as e:
                if attempt < UWA_MAX_RETRIES - 1:
                    time.sleep(0.5)
                    continue
                raise e
        
        return None
    
    def _extract_extra_info(self, soup: BeautifulSoup) -> str:
        """
        从详情页提取额外信息
        
        参数:
            soup: BeautifulSoup 对象
        
        返回:
            str: 额外信息字符串
        """
        info_parts = []
        
        try:
            # 提取课程代码
            labels = soup.select('.card-details-label')
            for label in labels:
                label_text = label.get_text(strip=True)
                value_elem = label.find_next_sibling()
                if value_elem:
                    value_text = value_elem.get_text(strip=True)
                    
                    if 'Course Code' in label_text:
                        info_parts.append(f"代码: {value_text}")
                    elif 'Duration' in label_text:
                        info_parts.append(f"学时: {value_text}")
                    elif 'Delivery' in label_text:
                        info_parts.append(f"授课方式: {value_text}")
        except:
            pass
        
        return " | ".join(info_parts) if info_parts else ""
    
    def close(self):
        """关闭爬虫，释放资源"""
        super().close()


if __name__ == "__main__":
    # 测试运行
    spider = UWASpider(headless=False)
    results = spider.run()
    spider.close()
    
    print(f"\n抓取完成，共 {len(results)} 个项目")
    if results:
        import json
        print("\n前3个项目示例:")
        print(json.dumps(results[:3], indent=2, ensure_ascii=False))
