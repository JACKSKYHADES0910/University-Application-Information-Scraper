"""
数据去重工具
用于移除爬取结果中的重复项目
"""
from typing import List, Dict, Set
from collections import OrderedDict


def deduplicate_results(results: List[Dict], key_fields: List[str] = None) -> List[Dict]:
    """
    对爬取结果进行智能去重
    
    默认策略：
    1. 优先使用 项目名称 + 项目链接 组合判断（最精确）
    2. URL 保留原始大小写（hash fragment 区分大小写）
    3. 项目名称标准化（去空格、统一空白符）
    
    Args:
        results: 爬取结果列表
        key_fields: 用于判断重复的字段列表，None 则使用默认策略
    
    Returns:
        去重后的结果列表
    """
    if not results:
        return []
    
    # 默认使用 名称+链接 组合（最精确）
    if key_fields is None:
        key_fields = ["项目名称", "项目链接"]
    
    seen_keys: Set[tuple] = set()
    unique_results = []
    duplicate_count = 0
    
    for item in results:
        # 构建唯一键
        key_values = []
        for field in key_fields:
            value = item.get(field, "")
            
            # 智能标准化
            if field == "项目链接":
                # URL: 去除首尾空格，但保留大小写（hash 区分大小写）
                value = value.strip()
            elif field == "项目名称":
                # 名称: 去除首尾空格，统一内部空白符
                value = " ".join(value.split())
            else:
                # 其他字段: 基础清理
                value = value.strip()
            
            key_values.append(value)
        
        unique_key = tuple(key_values)
        
        # 检查是否已存在
        if unique_key not in seen_keys:
            seen_keys.add(unique_key)
            unique_results.append(item)
        else:
            duplicate_count += 1
    
    if duplicate_count > 0:
        print(f"🔧 数据去重: 移除了 {duplicate_count} 条重复记录，保留 {len(unique_results)} 条唯一记录")
    
    return unique_results


def deduplicate_by_name(results: List[Dict]) -> List[Dict]:
    """
    仅根据项目名称去重（适用于同一学校的不同链接指向同一项目的情况）
    
    Args:
        results: 爬取结果列表
    
    Returns:
        去重后的结果列表
    """
    return deduplicate_results(results, key_fields=["项目名称"])


def deduplicate_by_link(results: List[Dict]) -> List[Dict]:
    """
    仅根据项目链接去重
    
    Args:
        results: 爬取结果列表
    
    Returns:
        去重后的结果列表
    """
    return deduplicate_results(results, key_fields=["项目链接"])
