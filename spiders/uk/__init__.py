# -*- coding: utf-8 -*-
"""
英国地区大学爬虫模块

包含的大学:
    - 帝国理工学院 (Imperial College)
    - 曼彻斯特大学 (Manchester)
    
TODO: 待添加英国大学爬虫实现
可添加的大学示例:
    - 牛津大学 (Oxford)
    - 剑桥大学 (Cambridge)
    - 伦敦大学学院 (UCL)
    - 伦敦政治经济学院 (LSE)
    等...
"""

from .manchester_spider import ManchesterSpider

__all__ = ["ManchesterSpider"]
