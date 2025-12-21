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
    "申请注册链接",   # 新用户注册入口
    "申请登录链接",   # 已有账户登录入口
    "项目opendate",  # 申请开放日期
    "项目deadline",  # 申请截止日期
    "学生案例",      # 成功案例(预留字段)
    "面试问题"       # 面试题目(预留字段)
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
    },
    "anu": {
        "code": "AUS006",
        "name": "The Australian National University",
        "name_cn": "澳大利亚国立大学",
        "base_url": "https://www.anu.edu.au",
        "list_url": "https://programsandcourses.anu.edu.au/catalogue?FilterByPrograms=true&Source=Breadcrumb",
        "allowed_domain": "anu.edu.au"
    },
    "imperial": {
        "code": "UK003",
        "name": "Imperial College London",
        "name_cn": "伦敦帝国学院",
        "base_url": "https://www.imperial.ac.uk",
        "list_url": "https://www.imperial.ac.uk/study/courses/?courseType=postgraduate+taught&keywords=",
        "allowed_domain": "imperial.ac.uk",
        # 统一的申请链接(全校共用)
        "apply_register_url": "https://myimperial.b2clogin.com/36573016-401a-40f6-86d9-686fc6635419/B2C_1_signupsigninflow/api/CombinedSigninAndSignup/unified?local=signup&csrf_token=RkVkOFVEcUhERXdXUWNTdlBYcUxNVVYxV1UwRHU2bFUzZzFITGJLNk9ncGJIdzY1SnJQa09mOElnblY4QzBqSXlLU1FpT2laWnE3NERRdWlScjRWcXc9PTsyMDI1LTEyLTE5VDA4OjEzOjExLjM5ODkwOTVaOzJYY1BSZkwyYW84cENQSmdORGRVb1E9PTt7Ik9yY2hlc3RyYXRpb25TdGVwIjoxfQ==&tx=StateProperties=eyJUSUQiOiJmMTYzYjBiYS04MjJlLTRhOGItOWY4Zi05M2U2NDdhOWQ1MDcifQ&p=B2C_1_signupsigninflow",
        "apply_login_url": "https://myimperial.b2clogin.com/36573016-401a-40f6-86d9-686fc6635419/b2c_1_signupsigninflow/oauth2/v2.0/authorize?client_id=2ebe03d8-3539-4f06-b15f-51617c94877c&redirect_uri=https%3A%2F%2Fmyimperial.powerappsportals.com%2FSignIn&response_type=code%20id_token&scope=openid&state=OpenIdConnect.AuthenticationProperties%3DKNzKNfIQFtqCy3DXOJpJVSSYqZbMFNG1DUvCr3DFoHhe8kl_E3Owt47bjNaDssaxw3xolf9k7Y8Kz8MsPP1TLzVssJt7nQcugLSyBEoS4ix0E41v3hqk08XCSwLiR9lCGqaB8FI4r0T8LaDwAVdMyVTFXILiGCXYIEBrVwM3XQv-yt0D8LrkAV0CIGmZUvdlJi_i4QdXctTtfWiTRTIhh0Hne9l8Hjxq_QCRf_Rp5Q35dl_52aDnvyQpMs2t1Ec4ZECUueaPPkpccBM-g0WMrcss7wBEou_tZqx6QKdpH8CX9V5r2iZ19-lpMye_yca_&response_mode=form_post&nonce=639017287749168068.ZTg0YzM2NDctMDE2Ni00ZGRhLTljMTktMzZkMGYwYzYyM2Q3NjZjYjkyODEtZmFjNy00NzM4LTgzMzktYzYzOGY0ZjM5NTcz&ui_locales=en-US&x-client-SKU=ID_NET472&x-client-ver=6.35.0.0"
    },
    "manchester": {
        "code": "UK007",
        "name": "The University of Manchester",
        "name_cn": "曼彻斯特大学",
        "base_url": "https://www.manchester.ac.uk",
        "list_url": "https://www.manchester.ac.uk/study/masters/courses/list/",
        "allowed_domain": "manchester.ac.uk",
        # 统一的申请链接(全校共用)
        "apply_register_url": "https://pgapplication.manchester.ac.uk/psc/apply/EMPLOYEE/SA/c/CIBAA_MNU.CIBAA_REG_CMP.GBL?Page=CIBAA_REG_PG&Action=A",
        "apply_login_url": "https://pgapplication.manchester.ac.uk/psc/apply/EMPLOYEE/SA/c/CIBAA_MNU.UMOAA_LOGIN_CMP.GBL?"
    }
}

# ==============================================================================
# 🟢【输出配置】
# ==============================================================================
# 默认输出文件夹
OUTPUT_DIR = "output"

# 文件名模板
FILENAME_TEMPLATE = "{university}_Projects_{timestamp}.xlsx"

