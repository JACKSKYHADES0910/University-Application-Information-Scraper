# -*- coding: utf-8 -*-
"""
研究生项目信息爬虫 - 主程序入口

支持的大学:
    - 香港地区: hku, cuhk, cityu, polyu
    - 澳大利亚地区: anu
    - 英国地区: (待实现)
    - 美国地区: (待实现)

使用方法:
    python main.py              # 交互式选择地区和大学
    python main.py hku          # 直接爬取 HKU
    python main.py hku --debug  # 调试模式（显示浏览器）
"""

import sys
import argparse
import os
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
    }
}


def print_banner():
    """打印程序横幅"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║          🎓 研究生项目信息爬虫 v1.0                          ║
║          Graduate Program Spider                              ║
╚══════════════════════════════════════════════════════════════╝
    """)


def print_available_regions():
    """打印所有可用的地区选项"""
    print("\n🌍 可用地区列表:")
    print("-" * 40)
    
    for idx, (region_key, region_info) in enumerate(REGION_INFO.items(), 1):
        print(f"  [{idx}] {region_info['name']}")
    
    print("-" * 40)


def print_region_universities(region_key: str):
    """打印指定地区的所有大学"""
    region_info = REGION_INFO.get(region_key)
    if not region_info:
        return
    
    print(f"\n📚 {region_info['name']} - 可用大学列表:")
    print("-" * 60)
    
    # 筛选该地区的大学（根据 spiders 下的文件夹结构）
    region_universities = {}
    for key, uni_info in UNIVERSITY_INFO.items():
        # 简单判断：根据 spiders 目录下的结构，判断该大学属于哪个地区
        # 这里我们假设已经在 config.py 中设置好了，或者通过文件夹结构判断
        # 暂时使用简单判断：hku/cuhk/cityu 属于 hongkong
        if region_key == "hongkong" and key in ["hku", "cuhk", "hkbu", "cityu", "polyu"]:
            region_universities[key] = uni_info
        elif region_key == "australia" and key in ["anu"]:
            region_universities[key] = uni_info
        # 可扩展其他地区
    
    if not region_universities:
        print("  ⚠️ 该地区暂无可用大学")
        return
    
    for key, info in region_universities.items():
        status = "✅ 已实现" if key in SPIDER_REGISTRY else "⏳ 待实现"
        print(f"  [{key:6}] {info['name_cn']:15} | {info['name']:40} | {status}")
    
    print("-" * 60)
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


def interactive_select_university() -> str:
    """
    交互式选择地区和大学
    
    返回:
        str: 用户选择的大学标识
    """
    # 第一步：选择地区
    print_available_regions()
    
    while True:
        region_choice = input("\n🔹 请输入地区编号 (1-4): ").strip()
        
        if not region_choice.isdigit():
            print("⚠️ 请输入有效的数字")
            continue
        
        region_idx = int(region_choice)
        if region_idx < 1 or region_idx > len(REGION_INFO):
            print(f"⚠️ 无效的地区编号，请输入 1-{len(REGION_INFO)}")
            continue
        
        # 获取选中的地区
        region_key = list(REGION_INFO.keys())[region_idx - 1]
        break
    
    # 第二步：选择该地区的大学
    region_universities = print_region_universities(region_key)
    
    if not region_universities:
        print("❌ 该地区暂无可用大学")
        return None
    
    while True:
        uni_choice = input(f"\n🔹 请输入大学代码 (如 hku): ").strip().lower()
        
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
                filepath = save_excel(results, university=uni_info['code'])
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
