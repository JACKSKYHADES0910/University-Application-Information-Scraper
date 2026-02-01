# -*- coding: utf-8 -*-
import requests
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from typing import Dict, Optional, List, Set

class DeepCrawler:
    """
    深度遍历爬虫 (DFS + Keyword Trigger)
    用于抓取详情页的 Deadline 和 Apply Link
    """
    
    # 关键词触发配置
    KEYWORDS_FOLLOW = [
        "admissions", "admission", "how to apply", "application", 
        "deadlines", "deadline", "dates", "apply now", 
        "learn more", "see program website", "requirements"
    ]
    
    KEYWORDS_APPLY = [
        "apply now", "start your application", "online application", 
        "application portal", "login", "register", "apply"
    ]
    
    # 增强的日期正则
    # 匹配: Jan 15, 2026 | January 15 | 15 Jan 2026 | 2026-01-15
    DATE_PATTERNS = [
        re.compile(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+(?:20\d{2})?', re.IGNORECASE),
        re.compile(r'\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?,?\s+(?:20\d{2})?', re.IGNORECASE),
        re.compile(r'20\d{2}-\d{2}-\d{2}'), # ISO format
    ]

    def __init__(self, max_depth: int = 3, timeout: int = 10):
        self.max_depth = max_depth
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                return BeautifulSoup(resp.content, 'html.parser')
        except:
            pass
        return None

    def _extract_date(self, text: str) -> Optional[str]:
        if not text:
            return None
        # 限定查找范围，避免匹配到 irrelevant dates (like "Copyright 2025")
        # 优先查找 "Deadline", "Dates" 附近的文本
        lines = text.split('\n')
        for line in lines:
            if len(line) > 200: continue # Skip long blocks
            for pattern in self.DATE_PATTERNS:
                match = pattern.search(line)
                if match:
                    # 简单的有效性检查 (比如排除单纯的 "May 2025" 如果我们需要具体日期，或者接受它)
                    return match.group(0)
        return None

    def crawl(self, start_url: str) -> Dict[str, str]:
        """
        开始深度遍历
        Returns: {"deadline": "...", "apply_link": "..."}
        """
        if not start_url or start_url.lower() == "n/a":
            return {"deadline": "N/A", "apply_link": "N/A"}

        visited = set()
        result = {"deadline": None, "apply_link": None}
        
        self._dfs(start_url, 0, visited, result)
        
        return {
            "deadline": result["deadline"] if result["deadline"] else "N/A",
            "apply_link": result["apply_link"] if result["apply_link"] else "N/A"
        }

    def _dfs(self, url: str, depth: int, visited: Set[str], result: Dict):
        """
        深度优先遍历核心逻辑
        """
        # 终止条件
        if depth >= self.max_depth:
            return
        if result["deadline"] and result["apply_link"]:
            return
        if url in visited:
            return
            
        visited.add(url)
        # print(f"  [Depth {depth}] Visiting: {url}") # Debug

        soup = self._get_soup(url)
        if not soup:
            return

        # 1. 提取信息 (Deadline & Apply Link)
        self._extract_info_from_page(soup, url, result)
        
        if result["deadline"] and result["apply_link"]:
            return

        # 2. 寻找下一步链接 (Keyword Trigger)
        if depth < self.max_depth - 1:
            next_links = self._get_next_links(soup, url)
            for link in next_links:
                if result["deadline"] and result["apply_link"]:
                    break
                self._dfs(link, depth + 1, visited, result)

    def _validate_page_content(self, url: str) -> bool:
        """
        验证页面是否包含 'log in' 或 'create an account'
        """
        if not url or "how-to-apply" in url or "application-process" in url: 
            return False # URL pattern check: explicit instruction to not stop at 'how-to-apply'
            
        try:
            resp = self.session.get(url, timeout=self.timeout)
            text = resp.text.lower()
            # 宽松匹配，确保包含登录相关术语
            return any(kw in text for kw in ["log in", "login", "sign in", "create an account", "start your application", "application portal"])
        except:
            return False

    def _extract_info_from_page(self, soup: BeautifulSoup, base_url: str, result: Dict):
        # 1. Apply Link
        if not result["apply_link"]:
            # 遍历所有链接，检查文本和链接
            for a in soup.find_all('a', href=True):
                text = a.get_text(" ", strip=True).lower()
                href = a.get('href')
                full_url = urljoin(base_url, href)
                
                # 排除无效链接
                if not full_url.startswith(('http', '/')) or 'pdf' in full_url: continue
                if full_url.startswith(('mailto:', 'tel:')): continue

                # 检查是否是 Apply 关键词触发
                is_apply_keyword = any(kw in text for kw in self.KEYWORDS_APPLY)
                
                if is_apply_keyword:
                    # 关键逻辑：如果链接本身包含 "how-to-apply" 或 "/applying"，或者只是 "admissions" 首页
                    # 即使文本是 "Apply Now" (例如导航栏上的)，它可能只是跳到说明页
                    if "how-to-apply" in full_url or "/applying" in full_url or "/admissions" in full_url:
                         # 这是一个路径，不是终点。DFS 会通过 _get_next_links 自动处理它（前提是 text 也在 KEYWORDS_FOLLOW 中）
                         # 为了保险，我们可以强制确保它被加入 visited/queue，但当前架构下依靠 DFS 自然发现即可
                         continue

                    # 验证目标页面内容 (必须包含 log in / create account)
                    if self._validate_page_content(full_url):
                        result["apply_link"] = full_url
                        break
        
        # 2. Deadline
        if not result["deadline"]:
            # 策略A: 查找含有 "Deadline" 的标题下的文本
            deadline_text = ""
            headers = soup.find_all(['h1', 'h2', 'h3', 'h4', 'th', 'strong', 'b'], string=re.compile(r'Deadline|Date', re.IGNORECASE))
            for h in headers:
                # 检查父容器文本或兄弟节点
                parent = h.find_parent()
                if parent:
                    deadline_text += parent.get_text(" ", strip=True) + "\n"
                # 检查 Next Sibling
                sibling = h.find_next_sibling()
                if sibling:
                    deadline_text += sibling.get_text(" ", strip=True) + "\n"
            
            extracted = self._extract_date(deadline_text)
            if extracted:
                result["deadline"] = extracted

    def _get_next_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        links = []
        # 只提取相关链接
        candidates = soup.find_all('a', href=True)
        for a in candidates:
            text = a.get_text(strip=True).lower()
            href = a.get('href')
            
            # 过滤无效链接
            if not href or href.startswith(('#', 'javascript', 'mailto', 'tel')):
                continue
                
            full_url = urljoin(base_url, href)
            # 简单的域限制 (可选)
            # if "nyu.edu" not in full_url: continue 
            
            # 关键词匹配
            for kw in self.KEYWORDS_FOLLOW:
                if kw in text:
                    links.append(full_url)
                    break 
        
        # 去重并限制数量 (避免广度过大)
        return list(dict.fromkeys(links))[:5] # 每个页面最多跟进5个最相关的链接
