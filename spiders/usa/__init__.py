# -*- coding: utf-8 -*-
"""
美国地区大学爬虫模块

已实现的大学:
    - 哈佛大学 (Harvard)

TODO: 待添加更多美国大学爬虫实现
可添加的大学示例:
    - 斯坦福大学 (Stanford)
    - 麻省理工学院 (MIT)
    - 加州大学伯克利分校 (UC Berkeley)
    - 哥伦比亚大学 (Columbia)
    等...
"""

from .harvard_spider import HarvardSpider
from .mit_spider import MITSpider
from .stanford_spider import StanfordSpider
from .nyu_spider import NYUSpider
from .duke_kunshan_spider import DukeKunshanSpider
from .maryland_spider import MarylandSpider
from .ucsc_spider import UCSCSpider
from .iowa_state_spider import IowaStateSpider
from .oregon_state_spider import OregonStateSpider

__all__ = ["HarvardSpider", "MITSpider", "StanfordSpider", "NYUSpider", "DukeKunshanSpider", "MarylandSpider", "UCSCSpider", "IowaStateSpider", "OregonStateSpider"]

