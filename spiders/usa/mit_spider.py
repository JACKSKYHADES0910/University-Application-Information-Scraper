# -*- coding: utf-8 -*-
import time
from typing import List, Dict, Optional
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin

from spiders.base_spider import BaseSpider
from config import UNIVERSITY_INFO

class MITSpider(BaseSpider):
    """
    麻省理工学院 (MIT) 爬虫 (US001)
    
    层级结构:
    1. 列表页 (School & Category): https://oge.mit.edu/graduate-admissions/programs/fields-of-study/
    2. 详情页 (Category Page): 包含 Application Opens, Deadline, 和 Degrees 下的子项目
    """
    
    def __init__(self, headless: bool = True):
        super().__init__(university_key="mit", headless=headless)
    
    def run(self) -> List[Dict]:
        """执行爬虫任务"""
        print(f"开始爬取 {self.school_name}...")
        
        # 第一阶段：获取Category列表和对应的School
        categories = self._get_categories()
        print(f"共发现 {len(categories)} 个项目大类")
        
        # 第二阶段：并发爬取详情
        all_programs = []
        if categories:
            all_programs = self._crawl_details_concurrent(categories)
            
        print(f"爬取完成，共获取 {len(all_programs)} 个项目信息")
        return all_programs

    def _get_categories(self) -> List[Dict]:
        """
        获取所有大类 (Categories) 及其所属学院 (Schools)
        URL: https://oge.mit.edu/graduate-admissions/programs/fields-of-study/
        结构: 表格形式
        Row (Header): School of ...
        Row (Item): Program Name | Opens | Deadline
        """
        print(f"正在获取项目大类列表: {self.list_url}")
        
        self.driver.get(self.list_url)
        time.sleep(5)
        
        html = self.driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        categories = []
        current_school = "MIT (Default)"
        
        # 尝试查找表格
        tables = soup.find_all('table')
        
        if tables:
            print(f"找到 {len(tables)} 个表格，正在解析...")
            for table in tables:
                rows = table.find_all('tr')
                # print(f"表格共有 {len(rows)} 行")
                
                for row in rows:
                    row_text = row.get_text(" ", strip=True)
                    
                    # 策略：
                    # 1. 检查是否是标题行 (含有 strong 且无有效链接，或者明确包含 School/College)
                    # 2. 检查是否是项目行 (含有有效链接)
                    
                    is_header = False
                    candidates = ["School of", "College of", "Sloan School", "Schwarzman College", "School"] # 扩展关键词
                    
                    # 排除表头行 "Program | Opens | Deadline"
                    if "deadline" in row_text.lower() or ("application" in row_text.lower() and "opens" in row_text.lower()):
                         continue

                    # 如果行文本包含 School/College 且没有链接(或链接不指向项目)
                    link = row.find('a')
                    strong_tag = row.find('strong')
                    
                    header_text_candidate = row_text
                    if strong_tag:
                         header_text_candidate = strong_tag.get_text(strip=True)
                         
                    # 判断是否是学院标题
                    has_school_keyword = any(c in header_text_candidate for c in candidates)
                    
                    # 逻辑：如果是 header 关键词 且 (没有link 或者 link不是项目link)
                    # 有时候 header 行可能根本没有 link tag
                    if has_school_keyword:
                        # 进一步确认不是普通项目行
                        # 比如 "School of X" 通常比较短
                        if len(header_text_candidate) < 100:
                             # 如果有链接，检查是否是无效链接(如空或者是锚点)
                             if not link or (link and not link.get('href', '').startswith('/programs/')):
                                 is_header = True
                                 current_school = header_text_candidate.replace("&", "and").strip()
                                 print(f"发现学院: {current_school}")
                                 continue
                    
                    # 处理项目
                    if link and link.get('href'):
                        href = link.get('href')
                        name = link.get_text(strip=True)
                        
                        if "mit.edu" in href or href.startswith("/"):
                            # 排除非项目链接
                            if "privacy" in href or "accessibility" in href:
                                continue
                                
                            full_url = urljoin(self.list_url, href)
                            categories.append({
                                "category_name": name,
                                "school": current_school,
                                "url": full_url
                            })
        else:
             print("未找到表格，尝试列表模式...")
             # ... (Keep existing list logic as backup or remove if confident)
             # 为了健壮性，保留一种基于 div 结构的简单遍历
             # 截图显示可能是 div table 或者 real table
             pass

        # 如果表格解析失败（categories为空），尝试之前的通用方法 但加上 School 识别
        if not categories:
             print("表格解析无结果，尝试通用 header/ul 提取...")
             # 重新使用之前的逻辑，但稍微改进
             content_area = soup.find('main') or soup.body
             elements = content_area.find_all(['h2', 'h3', 'h4', 'strong', 'ul', 'div']) # 包含 div 以防是 div-table
             
             for elem in elements:
                # 检查是否是 School 标题
                text = elem.get_text(strip=True)
                if ("School of" in text or "College" in text) and len(text) < 100:
                    current_school = text
                    print(f"发现学院 (Generic): {current_school}")
                
                # 检查链接
                if elem.name == 'ul':
                     for li in elem.find_all('li'):
                        a = li.find('a')
                        if a:
                            categories.append({
                                "category_name": a.get_text(strip=True),
                                "school": current_school,
                                "url": urljoin(self.list_url, a.get('href'))
                            })
        
        # 去重
        unique = []
        seen = set()
        for cat in categories:
            if cat['url'] not in seen:
                seen.add(cat['url'])
                unique.append(cat)
                
        return unique

    def _crawl_details_concurrent(self, categories: List[Dict]) -> List[Dict]:
        """并发爬取详情页"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from config import MAX_WORKERS
        
        programs = []
        total = len(categories)
        print(f"启动 {MAX_WORKERS} 个线程进行并发爬取...")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # 提交任务
            future_to_cat = {
                executor.submit(self._parse_category_page, cat): cat 
                for cat in categories
            }
            
            # 处理结果
            for i, future in enumerate(as_completed(future_to_cat)):
                cat = future_to_cat[future]
                try:
                    results = future.result()
                    if results:
                        programs.extend(results)
                        print(f"[{i+1}/{total}] 成功: {cat['category_name']} ({len(results)} 个子项目)")
                    else:
                        print(f"[{i+1}/{total}] 无数据: {cat['category_name']}")
                except Exception as e:
                    print(f"[{i+1}/{total}] 失败 {cat['category_name']}: {str(e)}")
                    
        return programs

    def _parse_category_page(self, category: Dict) -> List[Dict]:
        """
        解析 Category 详情页
        URL: category['url']
        
        需要提取:
        1. Application Opens (Date)
        2. Deadline (Date)
        3. Sub-programs from "Degrees" accordion
        """
        url = category['url']
        category_name = category['category_name']
        school = category['school']
        
        # 使用 requests 获取详情页，速度更快
        # 如果页面内容是动态加载的，可能需要用 Selenium
        # 根据描述 "Degree类似手风琴组件", 这些通常是 HTML 原生的 details/summary 或者简单的 JS toggle
        # 如果是简单的，requests 可能够用。为了保险起见，可以在 BaseSpider 里加一个 requests 方法
        # 但既然我们有 24 线程的 Selenium pool 能力 (在 base_spider 中没有显式 pool，
        # 但通常我们是在 process 里新开 driver 或者是用 requests)。
        # 用户提示 "需要的时候登录网站... 24线程"，通常 implies requests efficiency or selenium grid.
        # 查看 BaseSpider 结构，它是单 driver 的。
        # 如果要并发，通常是在线程里创建新的 driver 或者使用 requests。
        # 这里为了效率，优先尝试 requests。如果 content 在源码里，就用 requests。
        
        import requests
        from config import HEADERS, TIMEOUT
        
        results = []
        
        try:
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if response.status_code != 200:
                print(f"请求失败 {url}: {response.status_code}")
                return []
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. 提取 Deadline (和 Open Date)
            # 用户描述：有 application open date 和 application deadline date
            # 截图显示：右侧栏或主要区域有红色的字 "Deadline", "Application Opens"
            
            # 查找包含 "Deadline" 的文本
            deadline_text = "N/A"
            open_date_text = "N/A"
            
            # 策略：查找包含 "Deadline" 的 label 或 h?, 然后取其后的文本
            # 常见结构: <strong>Deadline:</strong> December 1
            for strong in soup.find_all(['strong', 'b', 'h4', 'h5', 'h6']):
                text = strong.get_text(strip=True).lower()
                if "deadline" in text:
                    # 尝试获取包含该 strong 的父元素文本，或者下一个兄弟节点
                    # 比如 parent text: "Deadline: December 1"
                    full_text = strong.parent.get_text(" ", strip=True)
                    # 简单的字符串处理
                    if ":" in full_text:
                        parts = full_text.split(":", 1)
                        if len(parts) > 1:
                            deadline_text = parts[1].strip()
                    else:
                        # 可能是 strong 是 label，下一个 sibling 是值
                        next_sib = strong.next_sibling
                        if next_sib:
                            deadline_text = next_sib.get_text(strip=True)
                            
                elif "application opens" in text or "opens" in text:
                    full_text = strong.parent.get_text(" ", strip=True)
                    if ":" in full_text:
                        parts = full_text.split(":", 1)
                        if len(parts) > 1:
                            open_date_text = parts[1].strip()
            
            # 2. 提取子项目 (Degrees)
            # 用户描述："Degree" 类似手风琴组件下面放的就是具体“子项目”信息
            # Browser inspection shows: .accordion-item -> button(Degrees) ... .accordion-body -> .field-item
            
            sub_programs = []
            
            # 查找包含 "Degrees" 的 Header 元素
            # 可能是 button.accordion-button 或其他标签
            degrees_headers = soup.find_all(lambda tag: tag.name in ['button', 'h2', 'h3', 'h4', 'div', 'span'] and tag.get_text(strip=True) in ["Degrees", "Degree", "Degree Program(s)"])
            
            degrees_section = None
            for header in degrees_headers:
                # 尝试找到其所在的 accordion-item 容器
                accordion_item = header.find_parent(class_=['accordion-item', 'card'])
                
                if accordion_item:
                    # 获取 accordion body
                    body = accordion_item.find(class_='accordion-body')
                    if not body:
                        # 有时候结构是 .field-items -> items, 没有 accordion-body
                        # 或者 accordion-body 就是 current div if structural change
                        body = accordion_item
                    
                    # 综合查找策略：
                    # 我们直接收集所有可能的学位列表项标签
                    # 1. Computational Science: <p><strong>Standalone...</strong></p> <ul><li>...</li></ul>
                    # 2. Media Arts: <div class="field-item">...</div> <div><hr></div> <h2>...</h2>
                    # 3. Architecture: <div class="field-item">...</div>
                    # 4. Economics: <p>...</p>
                    
                    # 收集所有潜在标签
                    candidates = body.find_all(['li', 'p', 'div', 'h2', 'h3', 'h4', 'h5', 'h6'])
                    
                    for c in candidates:
                        # 过滤掉非目标元素
                        # 1. 忽略包含 "Standalone Program", "Joint Program" 的标题/文本 (通常在 strong 或 p 标签中)
                        text = c.get_text(strip=True)
                        if "Standalone Program" in text or "Joint Program" in text:
                            continue
                            
                        # 2. 忽略以 * 开头的注释文本 (Media Arts)
                        if text.startswith('*'):
                            continue
                        
                        # 3. 如果是 div，必须要有 field-item class，或者是 container 但不含子 field-item (防止重复)
                        if c.name == 'div':
                            if 'field-item' not in c.get('class', []):
                                continue
                        
                        # 4. 如果是 p 标签，且父级是 li (防止重复收集 li 内部的 p)
                        if c.name == 'p' and c.find_parent('li'):
                            continue
                        
                        # Add valid item
                        if text:
                            clean_name = text.replace('*', '').strip()
                            if clean_name and clean_name not in sub_programs:
                                sub_programs.append(clean_name)
                                
                # (Same logic for next_div fallback if needed, but usually redundant given broad search)
                next_div = header.find_next_sibling('div')
                if next_div and not sub_programs:
                     candidates = next_div.find_all(['li', 'p', 'div', 'h2', 'h3', 'h4', 'h5', 'h6'])
                     for c in candidates:
                        text = c.get_text(strip=True)
                        if "Standalone Program" in text or "Joint Program" in text: continue
                        if text.startswith('*'): continue
                        if c.name == 'div' and 'field-item' not in c.get('class', []): continue
                        if c.name == 'p' and c.find_parent('li'): continue
                        
                        if text:
                            clean_name = text.replace('*', '').strip()
                            if clean_name and clean_name not in sub_programs:
                                sub_programs.append(clean_name)

            if sub_programs:
                # Deduplicate again just in case overlap
                sub_programs = list(dict.fromkeys(sub_programs))

            
            # 备用策略：如果找不到 Degrees Header，能否直接找 .accordion-body .field-item?
            # 风险在于可能会抓到其他部分的内容（如 "Entry Term" 也可能用同样的结构）
            # 所以这就够了。
            
            # 如果没找到子项目，使用 Category Name 作为 fallback
            if not sub_programs:
                print(f"在 {category_name} 未找到 Degree 列表，将使用 Category 名")
                sub_programs.append(category_name)
                
            # 构造结果
            for sub_prog in sub_programs:
                # 3. 项目名称：大类名称 + 子项目名称
                # 如果子项目名已经包含了大类名（有时候会），可以去重，
                # 但用户要求 "大类名称 + 子项目名称"
                # 示例: Aeronautics and Astronautics - Master of Science...
                
                # 避免重复: 如果 sub_prog 已经以 category_name 开头，就不加了
                if sub_prog.lower().startswith(category_name.lower()):
                    full_name = sub_prog
                else:
                    full_name = f"{category_name} - {sub_prog}"
                
                item = {
                    "学校代码": UNIVERSITY_INFO["mit"]["code"],
                    "学校名称": UNIVERSITY_INFO["mit"]["name"],
                    "项目名称": full_name,
                    "学院/学习领域": school, # 要求的 "项目页面下面放的是对应学院"
                    "项目官网链接": url,
                    "申请链接": "https://apply.mit.edu/account/register?r=https%3a%2f%2fapply.mit.edu%2fapply%2f",
                    "项目opendate": open_date_text,
                    "项目deadline": deadline_text,
                    "学生案例": "",
                    "面试问题": ""
                }
                results.append(item)
                
        except Exception as e:
            print(f"解析详情页出错 {url}: {e}")
            
        return results
