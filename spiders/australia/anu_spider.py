# -*- coding: utf-8 -*-
"""
澳大利亚国立大学 (ANU) 爬虫
使用catalogue页面抓取Postgraduate项目并访问详情页
"""

import time
import concurrent.futures
import requests
from typing import List, Dict, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from spiders.base_spider import BaseSpider
from config import HEADERS, TIMEOUT, MAX_WORKERS


class ANUSpider(BaseSpider):
    def __init__(self, headless: bool = True):
        super().__init__("anu", headless=headless)
        self.apply_url = "https://student-anu.studylink.com/index.cfm?event=security.showLogin&msg=eventsecured&fr=sp&en=default"
    
    def run(self) -> List[Dict]:
        """执行爬取任务"""
        print(f"[-] 开始抓取 {self.university_info.get('name', 'ANU')}...", flush=True)
        print(f"[-] 列表页: {self.list_url}", flush=True)
        
        self.driver.get(self.list_url)
        time.sleep(3)
        
        # 滚动到Postgraduate区域
        print("\n[-] 滚动到Postgraduate区域...", flush=True)
        self._scroll_to_postgraduate()
        
        # 点击Show all results
        print("[-] 点击 'Show all results...'...", flush=True)
        self._click_show_all()
        time.sleep(5)  # 等待所有项目加载
        
        # 获取所有项目链接
        print("\n[-] 获取项目列表...", flush=True)
        program_links = self._get_program_links()
        print(f"[-] 找到 {len(program_links)} 个Postgraduate项目\n", flush=True)
        
        # 并发处理项目详情页
        print(f"[-] 启动并发下载 (线程数: {MAX_WORKERS})...", flush=True)
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # 提交所有任务
            future_to_item = {
                executor.submit(self._process_program, item): item 
                for item in program_links
            }
            
            # 处理结果
            for idx, future in enumerate(concurrent.futures.as_completed(future_to_item), 1):
                item = future_to_item[future]
                code, name, _ = item
                
                try:
                    data = future.result()
                    if data:
                        results.append(data)
                        print(f"[{idx}/{len(program_links)}] [+] 成功: {name} ({code})", flush=True)
                    else:
                        print(f"[{idx}/{len(program_links)}] [!] 跳过: {name} ({code})", flush=True)
                except Exception as e:
                    print(f"[{idx}/{len(program_links)}] [x] 失败: {name} ({code}) - {e}", flush=True)
        
        print(f"\n[+] 抓取完成！共获取 {len(results)} 个项目", flush=True)
        return results
    
    def _process_program(self, item: Tuple[str, str, str]) -> Dict:
        """
        处理单个项目（运行在线程中）
        
        参数:
            item: (code, name, url)
        """
        code, name, url = item
        
        try:
            # 使用 requests 获取详情页
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if response.status_code != 200:
                print(f"  [!] HTTP {response.status_code}: {url}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 创建基础数据
            program_data = self.create_result_template(name, url)
            program_data["项目申请链接"] = self.apply_url
            
            # 提取学时信息
            duration_text = ""
            duration_elements = soup.find_all(string=lambda t: t and ('year' in t.lower() or 'semester' in t.lower()))
            if duration_elements:
                duration_text = duration_elements[0].strip()
            
            # 提取学习方式
            mode_text = ""
            mode_keywords = ['in person', 'online', 'multi-modal', 'distance']
            for keyword in mode_keywords:
                if soup.find(string=lambda t: t and keyword.lower() in t.lower()):
                    mode_text = keyword.title()
                    break
            
            # 将额外信息存储到备注字段
            program_data["学生案例"] = f"代码: {code} | 学时: {duration_text} | 方式: {mode_text}"
            
            return program_data
            
        except Exception as e:
            # 记录具体的错误信息以便调试
            # print(f"Error processing {code}: {e}")
            raise e
    
    def _scroll_to_postgraduate(self):
        """滚动到Postgraduate区域"""
        try:
            # 使用JavaScript滚动到包含Postgraduate文本的位置
            script = """
                var elements = document.querySelectorAll('*');
                for (var i = 0; i < elements.length; i++) {
                    if (elements[i].textContent.includes('Postgraduate (')) {
                        elements[i].scrollIntoView({behavior: 'smooth', block: 'center'});
                        return true;
                    }
                }
                return false;
            """
            result = self.driver.execute_script(script)
            time.sleep(2)
            print(f"  [+] 已滚动到Postgraduate区域", flush=True)
        except Exception as e:
            print(f"  [!] 滚动失败: {e}", flush=True)
    
    def _click_show_all(self):
        """点击Show all results按钮"""
        try:
            # 方法1: 使用footerfilter属性
            button = self.driver.find_element(
                By.CSS_SELECTOR,
                'div[footerfilter="FilterByPostGraduate"] a'
            )
            self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
            time.sleep(1)
            button.click()
            print("  [+] 成功点击 Show all results", flush=True)
        except Exception as e:
            print(f"  [!] 点击失败: {e}，尝试其他方法...", flush=True)
            try:
                # 方法2: 查找包含"Show all results"文本的链接
                links = self.driver.find_elements(By.TAG_NAME, 'a')
                for link in links:
                    if 'Show all results' in link.text:
                        link.click()
                        print("  [+] 通过文本匹配点击成功", flush=True)
                        return
            except:
                print("  [x] 所有方法都失败了", flush=True)
    
    def _get_program_links(self) -> List[tuple]:
        """
        获取所有Postgraduate项目的链接
        
        返回:
            List[tuple]: [(code, name, url), ...]
        """
        html = self.driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        program_links = []
        
        # 查找所有表格行
        rows = soup.select('tr')
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 4:
                continue
            
            # 检查Career列是否为Postgraduate
            career_cell = cells[3] if len(cells) > 3 else None
            if not career_cell or 'Postgraduate' not in career_cell.get_text():
                continue
            
            # 提取代码
            code_link = cells[0].find('a')
            if not code_link:
                continue
            
            code = code_link.get_text(strip=True)
            detail_url = code_link.get('href', '')
            
            # 提取名称
            name_link = cells[1].find('a')
            name = name_link.get_text(strip=True) if name_link else cells[1].get_text(strip=True)
            
            # 构建完整URL
            if detail_url and not detail_url.startswith('http'):
                detail_url = "https://programsandcourses.anu.edu.au" + detail_url
            
            if detail_url:
                program_links.append((code, name, detail_url))
        
        return program_links
    
    # 删除了旧的 _extract_program_details 方法，因为已经被 _process_program 替代
    
    def close(self):
        super().close()



if __name__ == "__main__":
    spider = ANUSpider(headless=False)
    results = spider.run()
    spider.close()
    
    print(f"\n抓取完成，共 {len(results)} 个项目")
    if results:
        import json
        print("\n前3个项目示例:")
        print(json.dumps(results[:3], indent=2, ensure_ascii=False))
