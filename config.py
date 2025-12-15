# -*- coding: utf-8 -*-
"""
项目配置文件
包含 Excel 表头定义和通用爬虫配置
"""

# ==============================================================================
# 🟢【Excel 表头配置】
# 定义导出 Excel 文件的列名和顺序
# ==============================================================================
EXCEL_COLUMNS = [
    "学校代码",      # 学校唯一标识码
    "学校名称",      # 学校全称
    "项目名称",      # 硕士/博士项目名称
    "项目官网链接",   # 项目详情页链接
    "项目申请链接",   # 在线申请入口链接
    "项目opendate",  # 申请开放日期
    "项目deadline",  # 申请截止日期
    "学生案例",      # 成功案例（预留字段）
    "面试问题"       # 面试题目（预留字段）
]

# ==============================================================================
# 🟢【浏览器配置】
# ==============================================================================
# 请求头配置，模拟真实浏览器
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

# 浏览器等待超时时间（秒）
TIMEOUT = 15

# 页面加载等待时间（秒）
PAGE_LOAD_WAIT = 20

# 最大重试次数
MAX_RETRIES = 3

# ==============================================================================
# 🟢【并发配置】
# ==============================================================================
# 并发线程数（你的配置 12600KF + 32GB 建议 20-24）
MAX_WORKERS = 24

# ==============================================================================
# 🟢【学校信息配置】
# 不同大学的基本信息
# ==============================================================================
UNIVERSITY_INFO = {
    "hku": {
        "code": "HK001",
        "name": "The University of Hong Kong",
        "name_cn": "香港大学",
        "base_url": "https://portal.hku.hk",
        "list_url": "https://portal.hku.hk/tpg-admissions/programme-listing",
        "allowed_domain": "hku.hk"
    },
    "hkbu": {
        "code": "HK006",
        "name": "Hong Kong Baptist University",
        "name_cn": "香港浸会大学",
        "base_url": "https://gs.hkbu.edu.hk",
        "list_url": "https://gs.hkbu.edu.hk/programmes",
        "allowed_domain": "hkbu.edu.hk"
    },
    "cityu": {
        "code": "HK003",
        "name": "City University of Hong Kong",
        "name_cn": "香港城市大学",
        "base_url": "https://www.cityu.edu.hk",
        "list_url": "https://www.cityu.edu.hk/pg/taught-postgraduate-programmes/list",
        "allowed_domain": "cityu.edu.hk"
    },
    "cuhk": {
        "code": "HK002",
        "name": "The Chinese University of Hong Kong",
        "name_cn": "香港中文大学",
        "base_url": "https://www.gs.cuhk.edu.hk",
        "list_url": "https://www.gs.cuhk.edu.hk/admissions/",
        "allowed_domain": "cuhk.edu.hk"
    },
    "polyu": {
        "code": "HK004",
        "name": "The Hong Kong Polytechnic University",
        "name_cn": "香港理工大学",
        "base_url": "https://www.polyu.edu.hk",
        "list_url": "https://www.polyu.edu.hk/study/pg/taught-postgraduate/find-your-programmes-tpg",
        "allowed_domain": "polyu.edu.hk"
    }
}

# ==============================================================================
# 🟢【输出配置】
# ==============================================================================
# 默认输出文件夹
OUTPUT_DIR = "output"

# 文件名模板
FILENAME_TEMPLATE = "{university}_Projects_{timestamp}.xlsx"

