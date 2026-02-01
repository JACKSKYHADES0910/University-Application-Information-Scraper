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
    "学院/学习领域",  # 统一字段：按学院分类→Faculty，按学习领域分类→Study Area
    "项目官网链接",   # 项目详情页链接
    "申请链接",       # 统一申请入口（注册/登录合并）
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
    },
    "uwa": {
        "code": "AUS007",
        "name": "The University of Western Australia",
        "name_cn": "西澳大学",
        "base_url": "https://www.uwa.edu.au",
        "list_url": "https://www.search.uwa.edu.au/s/search.html?f.Tabs%7Ccourses=Courses&f.Level+of+study%7CcourseStudyLevel=postgraduate&collection=uowa%7Esp-search",
        "allowed_domain": "uwa.edu.au",
        "apply_register_url": "https://www.uwa.edu.au/study/login",
        "apply_login_url": "https://www.uwa.edu.au/study/login"
    },
    "qub": {
        "code": "UK026",
        "name": "Queen's University Belfast",
        "name_cn": "贝尔法斯特女王大学",
        "base_url": "https://www.qub.ac.uk",
        "list_url": "https://www.qub.ac.uk/courses/?f.Study+Level%7CcourseLevel=Postgraduate+Taught&query=&num_ranks=100",
        "allowed_domain": "qub.ac.uk",
        "apply_register_url": "https://queensb2c.b2clogin.com/bdc53bdf-d9ac-45ee-b861-c6afba693dc0/B2C_1_qub_sign_up_and_sign_in/api/CombinedSigninAndSignup/unified?local=signup",
        "apply_login_url": "https://queensb2c.b2clogin.com/bdc53bdf-d9ac-45ee-b861-c6afba693dc0/b2c_1_qub_sign_up_and_sign_in/oauth2/v2.0/authorize?client_id=b30b1288-fe04-4719-96ee-2860aaa1a088&redirect_uri=https%3A%2F%2Fmyportal.qub.ac.uk%2Fsignin-aad-b2c_1"
    },
    "aberdeen": {
        "code": "UK030",
        "name": "University of Aberdeen",
        "name_cn": "阿伯丁大学",
        "base_url": "https://www.abdn.ac.uk",
        "list_url": "https://www.abdn.ac.uk/study/postgraduate-taught/degree-programmes/?limit=All",
        "allowed_domain": "abdn.ac.uk",
        "apply_register_url": "https://www.abdn.ac.uk/pgap/register.php",
        "apply_login_url": "https://www.abdn.ac.uk/pgap/login.php"
    },
    "uea": {
        "code": "UK034",
        "name": "University of East Anglia",
        "name_cn": "东英吉利大学",
        "base_url": "https://www.uea.ac.uk",
        "list_url": "https://www.uea.ac.uk/search/courses?primaryCategory%5B0%5D=Postgraduate",
        "allowed_domain": "uea.ac.uk",
        "apply_register_url": "https://uea.my.site.com/apply/TX_CommunitiesSelfReg?startURL=%2Fapply%2FTargetX_Base__Portal",
        "apply_login_url": "https://uea.my.site.com/apply/TX_SiteLogin?startURL=%2Fapply%2FTargetX_Base__Portal"
    },
    "strathclyde": {
        "code": "UK038",
        "name": "University of Strathclyde",
        "name_cn": "斯特拉斯克莱德大学",
        "base_url": "https://www.strath.ac.uk",
        "list_url": "https://www.strath.ac.uk/courses/postgraduatetaught/?level=Postgraduate+taught",
        "allowed_domain": "strath.ac.uk",
        "apply_register_url": "https://isc.strath.ac.uk/apply-now/apply-form#/",
        "apply_login_url": "https://isc.strath.ac.uk/apply-now/apply-form#/"
    },
    "brunel": {
        "code": "UK043",
        "name": "Brunel University London",
        "name_cn": "伦敦布鲁内尔大学",
        "base_url": "https://www.brunel.ac.uk",
        "list_url": "https://www.brunel.ac.uk/study/courses?courseLevel=0%2F2%2F24%2F28%2F44&pageSize=10000",
        "allowed_domain": "brunel.ac.uk",
        "apply_register_url": "https://evision.brunel.ac.uk/urd/sits.urd/run/SIW_IPP_LGN",
        "apply_login_url": "https://evision.brunel.ac.uk/urd/sits.urd/run/SIW_IPP_LGN"
    },
    "mmu": {
        "code": "UK055",
        "name": "Manchester Metropolitan University",
        "name_cn": "曼彻斯特城市大学",
        "base_url": "https://www.mmu.ac.uk",
        "list_url": "https://www.mmu.ac.uk/study/postgraduate/courses",
        "allowed_domain": "mmu.ac.uk",
        "apply_register_url": "https://www.mmu.ac.uk/study/postgraduate/register-your-interest#signup",
        "apply_login_url": "https://sm-portal-mmu.thesiscloud.com/application-portal-step-1/"
    },
    "royalholloway": {
        "code": "UK059",
        "name": "Royal Holloway University of London",
        "name_cn": "伦敦大学皇家霍洛威学院",
        "base_url": "https://www.royalholloway.ac.uk",
        "list_url": "https://www.royalholloway.ac.uk/studying-here/postgraduate-courses/",
        "allowed_domain": "royalholloway.ac.uk",
        "apply_register_url": "https://royalhollowayacuk.elluciancrmrecruit.com/Apply/Account/Create",
        "apply_login_url": "https://royalhollowayacuk.elluciancrmrecruit.com/Apply/Account/Login"
    },
    "ulster": {
        "code": "UK067",
        "name": "Ulster University",
        "name_cn": "阿尔斯特大学",
        "base_url": "https://www.ulster.ac.uk",
        "list_url": "https://www.ulster.ac.uk/courses?f.Level_u|Y=Postgraduate&query=&start_rank=1",
        "allowed_domain": "ulster.ac.uk",
        "apply_register_url": "https://srssb.ulster.ac.uk/PROD/bwskalog.p_disploginnew?in_id=&cpbl=&newid=",
        "apply_login_url": "https://srssb.ulster.ac.uk/PROD/bwskalog.P_DispLoginNon"
    },
    "deakin": {
        "code": "AUS011",
        "name": "Deakin University",
        "name_cn": "迪肯大学",
        "base_url": "https://www.deakin.edu.au",
        "list_url": "https://www.deakin.edu.au/study/find-a-course/postgraduate-courses",
        "allowed_domain": "deakin.edu.au",
        "apply_register_url": "https://student-deakin.studylink.com/index.cfm?event=registration.form",
        "apply_login_url": "https://student-deakin.studylink.com/index.cfm?event=security.showLogin&msg=eventsecured&fr=sp&en=default"
    },
    "harvard": {
        "code": "US002",
        "name": "Harvard University",
        "name_cn": "哈佛大学",
        "base_url": "https://www.harvard.edu",
        "list_url": "https://www.harvard.edu/programs/?degree_levels=graduate",
        "allowed_domain": "harvard.edu",
        "apply_register_url": "N/A",  # Harvard uses school-specific application systems
        "apply_login_url": "N/A"
    },
    "mit": {
        "code": "US001",
        "name": "Massachusetts Institute of Technology",
        "name_cn": "麻省理工学院",
        "base_url": "https://oge.mit.edu",
        "list_url": "https://oge.mit.edu/graduate-admissions/programs/fields-of-study/",
        "allowed_domain": "mit.edu",
        "apply_register_url": "N/A",  # Decentralized
        "apply_login_url": "N/A"
    },
    "stanford": {
        "code": "US003",
        "name": "Stanford University",
        "name_cn": "斯坦福大学",
        "base_url": "https://gradadmissions.stanford.edu",
        "list_url": "https://gradadmissions.stanford.edu/programs",
        "allowed_domain": "stanford.edu",
        "apply_register_url": "https://applygrad.stanford.edu/account/register?r=/portal/grad-app",
        "apply_login_url": "https://applygrad.stanford.edu/portal/grad-app"
    },
    "nyu": {
        "code": "US018",
        "name": "New York University",
        "name_cn": "纽约大学",
        "base_url": "https://bulletins.nyu.edu",
        "list_url": "https://bulletins.nyu.edu/programs/#filter=.filter_55",
        "allowed_domain": "nyu.edu",
        "apply_register_url": "https://admissions.stern.nyu.edu/apply/?sr=af9314e5-b47a-4166-b75c-e14a92e7f632&utm_source=site_5_de&utm_medium=top&utm_campaign=links&utm_term=MSA&utm_content=App",
        "apply_login_url": "https://admissions.stern.nyu.edu/apply/?sr=af9314e5-b47a-4166-b75c-e14a92e7f632&utm_source=site_5_de&utm_medium=top&utm_campaign=links&utm_term=MSA&utm_content=App"
    },
    "duke_kunshan": {
        "code": "US021",
        "name": "Duke Kunshan University",
        "name_cn": "昆山杜克大学",
        "base_url": "https://graduate.dukekunshan.edu.cn",
        "list_url": "https://graduate.dukekunshan.edu.cn/",
        "allowed_domain": "dukekunshan.edu.cn",
        "apply_register_url": "https://applygp.duke.edu/apply/?sr=d3abd676-a8c1-4bcc-aa53-2603fe10563b",
        "apply_login_url": "https://applygp.duke.edu/apply/?sr=d3abd676-a8c1-4bcc-aa53-2603fe10563b"
    },
    "maryland": {
        "code": "US043",
        "name": "University of Maryland, College Park",
        "name_cn": "马里兰大学帕克分校",
        "base_url": "https://shadygrove.usmd.edu",
        "list_url": "https://shadygrove.usmd.edu/academics/degree-programs?f%5B0%5D=level%3AGraduate&items_per_page=100",
        "allowed_domain": "shadygrove.usmd.edu",
        "apply_register_url": "N/A", # Application links vary by school
        "apply_login_url": "N/A"
    },
    "emory": {
        "code": "US044",
        "name": "Emory University",
        "name_cn": "埃默里大学",
        "base_url": "https://www.emory.edu",
        "list_url": "https://www.emory.edu/home/academics/degrees-programs.html",
        "allowed_domain": "emory.edu",
        "apply_register_url": "N/A", # Logic handled in spider
        "apply_login_url": "N/A"
    },
    "vanderbilt": {
        "code": "US045",
        "name": "Vanderbilt University",
        "name_cn": "范德堡大学",
        "base_url": "https://www.vanderbilt.edu",
        "list_url": "https://www.vanderbilt.edu/academics/program-finder/?degrees=masters%2Cdoctoral%2Conline",
        "allowed_domain": "vanderbilt.edu",
        "apply_register_url": "https://apply.vanderbilt.edu/apply/",
        "apply_login_url": "https://apply.vanderbilt.edu/apply/"
    },
    "indiana_bloomington": {
        "code": "US060",
        "name": "Indiana University Bloomington",
        "name_cn": "印第安纳大学伯明顿分校",
        "base_url": "https://bloomington.iu.edu",
        "list_url": "https://bloomington.iu.edu/academics/degrees-majors/index.html?campus=bloomington",
        "allowed_domain": "iu.edu",
        "apply_register_url": "https://iugraduate2026.cas.myliaison.com/applicant-ux/#/login",
        "apply_login_url": "https://iugraduate2026.cas.myliaison.com/applicant-ux/#/login"
    },
    "virginia": {
        "code": "US061",
        "name": "University of Virginia",
        "name_cn": "弗吉尼亚大学",
        "base_url": "https://records.ureg.virginia.edu",
        "list_url": "https://records.ureg.virginia.edu/content.php?catoid=68&navoid=6160",
        "allowed_domain": "virginia.edu",
        "apply_register_url": "https://applycentral.virginia.edu/apply/",
        "apply_login_url": "https://applycentral.virginia.edu/apply/"
    },
    "ucsc": {
        "code": "US062",
        "name": "University of California, Santa Cruz",
        "name_cn": "加州大学圣克鲁兹分校",
        "base_url": "https://graduateadmissions.ucsc.edu",
        "list_url": "https://graduateadmissions.ucsc.edu/graduate-programs/",
        "allowed_domain": "ucsc.edu",
        "apply_register_url": "https://applygrad.ucsc.edu/apply/",
        "apply_login_url": "https://applygrad.ucsc.edu/apply/"
    },
    "uconn": {
        "code": "US081",
        "name": "University of Connecticut",
        "name_cn": "康涅狄格大学",
        "base_url": "https://grad.uconn.edu",
        "list_url": "https://grad.uconn.edu/programs/",
        "allowed_domain": "uconn.edu",
        "apply_register_url": "https://connect.grad.uconn.edu/apply/",
        "apply_login_url": "https://connect.grad.uconn.edu/apply/"
    },
    "kansas": {
        "code": "US082",
        "name": "University of Kansas",
        "name_cn": "堪萨斯大学",
        "base_url": "https://gograd.ku.edu",
        "list_url": "https://gograd.ku.edu/portal/prog_website",
        "allowed_domain": "ku.edu",
        "apply_register_url": "https://gograd.ku.edu/apply/?_gl=1*vxcfti*_gcl_au*MTE2NTY1NDU1OC4xNzY4OTMzNDU2",
        "apply_login_url": "https://gograd.ku.edu/apply/?_gl=1*vxcfti*_gcl_au*MTE2NTY1NDU1OC4xNzY4OTMzNDU2"
    },
    "delaware": {
        "code": "US091",
        "name": "University of Delaware",
        "name_cn": "特拉华大学",
        "base_url": "https://www.udel.edu",
        "list_url": "https://www.udel.edu/academics/colleges/grad/prospective-students/programs/",
        "allowed_domain": "udel.edu",
        "apply_register_url": "https://grad-admissions.udel.edu/apply/",
        "apply_login_url": "https://grad-admissions.udel.edu/apply/"
    },
    "iowa_state": {
        "code": "US092",
        "name": "Iowa State University",
        "name_cn": "爱荷华州立大学",
        "base_url": "https://www.grad-college.iastate.edu",
        "list_url": "https://www.grad-college.iastate.edu/programs?title=&field_program_degrees_offered_target_id=All&field_online_program_value=All&field_coursework_only_value=All&field_interdepartmental_program_value=All&field_program_interest_area_target_id=All&sort_by=title&sort_order=ASC",
        "allowed_domain": "iastate.edu",
        "apply_url": "https://apps.admissions.iastate.edu/apply/online/"
    },
    "oregon_state": {
        "code": "US093",
        "name": "Oregon State University",
        "name_cn": "俄勒冈州立大学",
        "base_url": "https://graduate.oregonstate.edu",
        "list_url": "https://graduate.oregonstate.edu/programs",
        "allowed_domain": "oregonstate.edu",
        "apply_url": "https://advanced.oregonstate.edu/portal/gr-app"
    },
    "montreal": {
        "code": "CA007",
        "name": "Université de Montréal",
        "name_cn": "蒙特利尔大学",
        "base_url": "https://admission.umontreal.ca",
        "list_url": "https://admission.umontreal.ca/en/programs-of-study/",
        "allowed_domain": "umontreal.ca",
        "apply_url": "https://admission.umontreal.ca/en/application/"
    },
    "calgary": {
        "code": "CA008",
        "name": "University of Calgary",
        "name_cn": "卡尔加里大学",
        "base_url": "https://grad.ucalgary.ca",
        "list_url": "https://grad.ucalgary.ca/future-students/graduate/discover-opportunities/explore-programs",
        "allowed_domain": "ucalgary.ca",
        "apply_url": "https://cas.ucalgary.ca/cas/login?service=https://apply.ucalgary.ca/StudentAdmission/Login.aspx?AppType=A"
    },
    "manitoba": {
        "code": "CA018",
        "name": "University of Manitoba",
        "name_cn": "曼尼托巴大学",
        "base_url": "http://umanitoba.ca",
        "list_url": "http://umanitoba.ca/graduate-studies/admissions/programs-of-study",
        "allowed_domain": "umanitoba.ca",
        "apply_url": "https://applygrad.umanitoba.ca/apply/"
    },
    "guelph": {
        "code": "CA019",
        "name": "University of Guelph",
        "name_cn": "圭尔夫大学",
        "base_url": "https://www.uoguelph.ca",
        "list_url": "https://www.uoguelph.ca/programs/graduate",
        "allowed_domain": "uoguelph.ca",
        "apply_url": "https://www.ouac.on.ca/apply/guelphgrad/en_CA/user/login"
    }
}

# ==============================================================================
# 🟢【输出配置】
# ==============================================================================
# 默认输出文件夹
OUTPUT_DIR = "output"

# 文件名模板
FILENAME_TEMPLATE = "{university}_Projects_{timestamp}.xlsx"

