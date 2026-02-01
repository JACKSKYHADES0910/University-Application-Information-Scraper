# -*- coding: utf-8 -*-
"""
研究生项目信息爬虫 - 主程序入口

支持的大学:
    - 香港地区: hku, cuhk, cityu, polyu
    - 澳大利亚地区: anu
    - 英国地区: imperial
    - 美国地区: (待实现)

使用方法:
    python main.py              # 交互式选择地区和大学
    python main.py hku          # 直接爬取 HKU
    python main.py hku --debug  # 调试模式（显示浏览器）
"""

import sys
import argparse
import os

# 强制设置输出编码为 UTF-8，解决 Windows 下的 UnicodeEncodeError
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7 or filtered stdout
        pass

from typing import Optional, Type, Dict, List

# 设置标准输出编码为 UTF-8（解决 Windows 控制台 emoji 显示问题）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 导入爬虫类
from spiders.base_spider import BaseSpider
from spiders.hongkong import HKUSpider
from spiders.hongkong.cuhk_spider import CUHKSpider
from spiders.hongkong.cityu_spider import CityUSpider
from spiders.hongkong.polyu_spider import PolyUSpider
from spiders.australia.anu_spider import ANUSpider
from spiders.australia.uwa_spider import UWASpider
from spiders.australia.deakin_spider import DeakinSpider
from spiders.uk.imperial_spider import ImperialSpider
from spiders.uk.manchester_spider import ManchesterSpider
from spiders.uk.qub_spider import QUBSpider
from spiders.uk.aberdeen_spider import AberdeenSpider
from spiders.uk.uea_spider import UEASpider
from spiders.uk.strathclyde_spider import StrathclydeSpider
from spiders.uk.brunel_spider import BrunelSpider
from spiders.uk.mmu_spider import MMUSpider
from spiders.uk.royalholloway_spider import RoyalHollowaySpider
from spiders.uk.ulster_spider import UlsterSpider
from spiders.usa.harvard_spider import HarvardSpider
from spiders.usa.mit_spider import MITSpider
from spiders.usa.mit_spider import MITSpider
from spiders.usa.stanford_spider import StanfordSpider
from spiders.usa.nyu_spider import NYUSpider
from spiders.usa.duke_kunshan_spider import DukeKunshanSpider
from spiders.usa.maryland_spider import MarylandSpider
from spiders.usa.emory_spider import EmorySpider
from spiders.usa.vanderbilt_spider import VanderbiltSpider
from spiders.usa.indiana_bloomington_spider import IndianaBloomingtonSpider
from spiders.usa.virginia_spider import VirginiaSpider
from spiders.usa.virginia_spider import VirginiaSpider
from spiders.usa.ucsc_spider import UCSCSpider
from spiders.usa.uconn_spider import UConnSpider
from spiders.usa.kansas_spider import KansasSpider
from spiders.usa.delaware_spider import DelawareSpider
from spiders.usa.iowa_state_spider import IowaStateSpider
from spiders.usa.oregon_state_spider import OregonStateSpider
from spiders.ca.montreal_spider import MontrealSpider
from spiders.ca.calgary_spider import CalgarySpider
from spiders.ca.manitoba_spider import ManitobaSpider
from spiders.ca.guelph_spider import GuelphSpider

# 导入工具函数
from utils.data_saver import save_excel, preview_data

# 导入配置
from config import UNIVERSITY_INFO


# ==============================================================================
# 🟢【爬虫注册表】
# 在此注册所有可用的爬虫类
# 格式: "标识符": 爬虫类
# ==============================================================================
SPIDER_REGISTRY = {
    "hku": HKUSpider,
    "cuhk": CUHKSpider,
    "cityu": CityUSpider,
    "polyu": PolyUSpider,
    "anu": ANUSpider,
    "uwa": UWASpider,
    "imperial": ImperialSpider,
    "manchester": ManchesterSpider,
    "qub": QUBSpider,
    "aberdeen": AberdeenSpider,
    "uea": UEASpider,
    "strathclyde": StrathclydeSpider,
    "brunel": BrunelSpider,
    "mmu": MMUSpider,
    "royalholloway": RoyalHollowaySpider,
    "ulster": UlsterSpider,
    "deakin": DeakinSpider,
    "harvard": HarvardSpider,
    "mit": MITSpider,
    "stanford": StanfordSpider,
    "nyu": NYUSpider,
    "duke_kunshan": DukeKunshanSpider,
    "duke_kunshan": DukeKunshanSpider,
    "maryland": MarylandSpider,
    "emory": EmorySpider,
    "vanderbilt": VanderbiltSpider,
    "indiana_bloomington": IndianaBloomingtonSpider,
    "virginia": VirginiaSpider,
    "ucsc": UCSCSpider,
    "uconn": UConnSpider,
    "kansas": KansasSpider,
    "delaware": DelawareSpider,
    "iowa_state": IowaStateSpider,
    "oregon_state": OregonStateSpider,
    "montreal": MontrealSpider,
    "calgary": CalgarySpider,
    "manitoba": ManitobaSpider,
    "guelph": GuelphSpider,
    # "hkbu": HKBUSpider,
    # 添加新爬虫时在此注册:
    # "oxford": OxfordSpider,
    # "cambridge": CambridgeSpider,
}


# ==============================================================================
# 🟢【地区分类配置】
# 根据 spiders 文件夹结构自动识别地区
# ==============================================================================
REGION_INFO = {
    "hongkong": {
        "name": "🇭🇰 香港地区",
        "folder": "hongkong"
    },
    "australia": {
        "name": "🇦🇺 澳大利亚地区",
        "folder": "australia"
    },
    "uk": {
        "name": "🇬🇧 英国地区",
        "folder": "uk"
    },
    "usa": {
        "name": "🇺🇸 美国地区",
        "folder": "usa"
    },
    "canada": {
        "name": "🇨🇦 加拿大地区",
        "folder": "ca"
    }
}


def print_banner():
    """打印程序横幅"""
    print("""
╔═════════════════════════════════════════════════════════════════════════╗
║                  🎓 研究生项目信息爬虫 v1.0                             ║
║                  Graduate Program Spider                                ║
╚═════════════════════════════════════════════════════════════════════════╝
    """)


def print_available_regions():
    """打印所有可用的地区选项"""
    print("\n🌍 可用地区列表:")
    print("-" * 40)
    
    for idx, (region_key, region_info) in enumerate(REGION_INFO.items(), 1):
        print(f"  [{idx}] {region_info['name']}")
    
    print("-" * 40)
    print("  [q] 退出程序")


def get_display_width(text: str) -> int:
    """计算文本的显示宽度（中文占2字符，英文占1字符）"""
    width = 0
    for char in text:
        if ord(char) > 127:
            width += 2
        else:
            width += 1
    return width

def pad_text(text: str, width: int) -> str:
    """根据显示宽度填充空格"""
    display_width = get_display_width(text)
    padding = width - display_width
    if padding < 0:
        padding = 0
    return text + " " * padding


def print_region_universities(region_key: str):
    """打印指定地区的所有大学"""
    region_info = REGION_INFO.get(region_key)
    if not region_info:
        return
    
    print(f"\n📚 {region_info['name']} - 可用大学列表:")
    print("-" * 105)
    
    # 筛选该地区的大学（根据 spiders 文件夹结构）
    region_universities = {}
    for key, uni_info in UNIVERSITY_INFO.items():
        if region_key == "hongkong" and key in ["hku", "cuhk", "hkbu", "cityu", "polyu"]:
            region_universities[key] = uni_info
        elif region_key == "australia" and key in ["anu", "uwa", "deakin"]:
            region_universities[key] = uni_info
        elif region_key == "uk" and key in ["imperial", "manchester", "qub", "aberdeen", "uea", "strathclyde", "brunel", "mmu", "royalholloway", "ulster"]:
            region_universities[key] = uni_info
        elif region_key == "usa" and key in ["harvard", "mit", "stanford", "nyu", "duke_kunshan", "maryland", "emory", "vanderbilt", "indiana_bloomington", "virginia", "ucsc", "uconn", "kansas", "delaware", "iowa_state", "oregon_state"]:
            region_universities[key] = uni_info
        elif region_key == "canada" and key in ["montreal", "calgary", "manitoba", "guelph"]:
            region_universities[key] = uni_info
    
    if not region_universities:
        print("  ⚠️ 该地区暂无可用大学")
        return
    
    # 打印表头
    header_key = pad_text("代码 (Code)", 22)
    header_cn = pad_text("中文名称 (Name CN)", 25)
    header_en = pad_text("英文名称 (Name EN)", 42)
    print(f"  {header_key} | {header_cn} | {header_en} | 状态")
    print("-" * 105)

    for key, info in region_universities.items():
        status = "✅ 已实现" if key in SPIDER_REGISTRY else "⏳ 待实现"
        
        # 使用自定义填充函数
        key_str = pad_text(f"[{key}]", 22)
        name_cn_str = pad_text(info['name_cn'], 25)
        name_en_str = pad_text(info['name'], 42)
        
        print(f"  {key_str} | {name_cn_str} | {name_en_str} | {status}")
    
    print("-" * 105)
    print("  [0] 返回上级菜单")
    print("  [q] 退出程序")
    return region_universities


def get_spider_class(university_key: str) -> Optional[Type[BaseSpider]]:
    """
    根据大学标识获取对应的爬虫类
    
    参数:
        university_key (str): 大学标识（如 "hku"）
    
    返回:
        Optional[Type[BaseSpider]]: 爬虫类，如果未找到则返回 None
    """
    return SPIDER_REGISTRY.get(university_key.lower())


def interactive_select_university() -> Optional[str]:
    """
    交互式选择地区和大学
    
    返回:
        Optional[str]: 用户选择的大学标识，如果退出则返回 None
    """
    while True:
        # 第一步：选择地区
        print_available_regions()
        
        region_choice = input("\n🔹 请输入地区编号 (1-4, q退出): ").strip().lower()
        
        if region_choice == 'q':
            print("👋 已退出程序")
            sys.exit(0)
        
        if not region_choice.isdigit():
            print("⚠️ 请输入有效的数字")
            continue
        
        region_idx = int(region_choice)
        if region_idx < 1 or region_idx > len(REGION_INFO):
            print(f"⚠️ 无效的地区编号，请输入 1-{len(REGION_INFO)}")
            continue
        
        # 获取选中的地区
        region_key = list(REGION_INFO.keys())[region_idx - 1]
        
        # 第二步：选择该地区的大学
        while True:
            region_universities = print_region_universities(region_key)
            
            if not region_universities:
                print("❌ 该地区暂无可用大学")
                break
            
            uni_choice = input(f"\n🔹 请输入大学代码 (如 hku, 0返回, q退出): ").strip().lower()
            
            if uni_choice == 'q':
                print("👋 已退出程序")
                sys.exit(0)
                
            if uni_choice == '0':
                break # Break inner loop, return to region selection
            
            if not uni_choice:
                print("⚠️ 输入不能为空，请重试")
                continue
            
            if uni_choice not in region_universities:
                print(f"⚠️ 该地区没有代码为 '{uni_choice}' 的大学，请重试")
                continue
            
            if uni_choice in SPIDER_REGISTRY:
                return uni_choice
            else:
                print(f"⚠️ [{uni_choice}] 的爬虫尚未实现，请选择其他大学")



def run_spider(university_key: str, debug: bool = False):
    """
    运行指定大学的爬虫
    
    参数:
        university_key (str): 大学标识
        debug (bool): 是否开启调试模式（显示浏览器窗口）
    """
    # 获取爬虫类
    spider_class = get_spider_class(university_key)
    
    if spider_class is None:
        print(f"❌ 错误: 未找到 [{university_key}] 的爬虫实现")
        return
    
    # 获取大学信息
    uni_info = UNIVERSITY_INFO[university_key]
    
    print(f"\n🎯 准备爬取: {uni_info['name_cn']} ({uni_info['name']})")
    print(f"📍 目标网址: {uni_info['list_url']}")
    print(f"🔧 运行模式: {'调试模式 (显示浏览器)' if debug else '无头模式 (后台运行)'}")
    
    # 确认开始
    confirm = input("\n❓ 确认开始爬取? (Y/n): ").strip().lower()
    if confirm == 'n':
        print("❌ 已取消")
        return
    
    print("\n" + "=" * 50)
    print("✅ 确认成功！正在为您启动爬虫进程，首次运行可能需要几秒钟加载浏览器...")
    print("⏳ 请耐心等待，不要关闭弹出的窗口。")
    print("=" * 50 + "\n")
    
    # 使用 with 语句确保资源释放
    with spider_class(headless=not debug) as spider:
        # 执行爬取
        results = spider.run()
        
        if results:
            # 预览数据
            preview_data(results, rows=10)
            
            # 询问是否保存
            save_choice = input("\n💾 是否保存到 Excel? (Y/n): ").strip().lower()
            if save_choice != 'n':
                filepath = save_excel(
                    results, 
                    university_code=uni_info['code'],
                    university_name=uni_info['name']
                )
                if filepath:
                    print("\n✨ 任务完成！")
        else:
            print("\n⚠️ 未获取到任何数据")


def main():
    """主函数：解析命令行参数并运行爬虫"""
    parser = argparse.ArgumentParser(
        description="研究生项目信息爬虫 - 按地区分类选择大学",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python main.py              交互式选择地区和大学
  python main.py hku          直接爬取香港大学
  python main.py cuhk --debug 调试模式爬取香港中文大学
        """
    )
    
    parser.add_argument(
        'university',
        nargs='?',
        help='大学代码 (如 hku, cuhk)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='调试模式（显示浏览器窗口）'
    )
    
    args = parser.parse_args()
    
    # 打印横幅
    print_banner()
    
    # 确定要爬取的大学
    if args.university:
        # 直接模式
        university_key = args.university.lower()
        if university_key not in UNIVERSITY_INFO:
            print(f"❌ 未知的大学代码: '{args.university}'")
            print_available_regions()
            return
    else:
        # 交互模式
        university_key = interactive_select_university()
        if not university_key:
            return
    
    # 运行爬虫
    run_spider(university_key, debug=args.debug)


if __name__ == "__main__":
    main()
