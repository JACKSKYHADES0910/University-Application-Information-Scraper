# -*- coding: utf-8 -*-
"""
数据保存模块
封装 Excel 和 CSV 文件的保存逻辑
"""

import os
import sys
from datetime import datetime
from typing import List, Dict, Optional

import pandas as pd

# 尝试导入 rich 库用于美化输出
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    from rich.markup import escape as rich_escape
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    rich_escape = lambda x: x  # 降级：不转义

from config import EXCEL_COLUMNS, OUTPUT_DIR, FILENAME_TEMPLATE


def _get_console() -> Console:
    """
    获取 Console 实例
    每次调用时创建新实例，避免 stdout 重定向冲突
    """
    if not RICH_AVAILABLE:
        return None
    return Console(force_terminal=True, legacy_windows=False)


# 全局 console（兼容性保留，建议使用 _get_console()）
console = _get_console()


def _create_clickable_link(url: str, display_text: str) -> str:
    """
    创建可点击的链接文本（安全处理特殊字符）
    
    参数:
        url (str): 链接地址
        display_text (str): 显示文本
    
    返回:
        str 或 Text: 可点击的链接或纯文本
    """
    if not url or url == "N/A" or not url.startswith("http"):
        return "N/A"
    
    if RICH_AVAILABLE:
        # 使用 Text 对象创建链接，避免 markup 解析问题
        text = Text(display_text, style=f"link {url}")
        return text
    else:
        return display_text


def ensure_output_dir(output_dir: str = OUTPUT_DIR) -> str:
    """
    确保输出目录存在，如果不存在则创建
    
    参数:
        output_dir (str): 输出目录路径
    
    返回:
        str: 输出目录的绝对路径
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"📁 创建输出目录: {output_dir}")
    return output_dir


def generate_filename(university_code: str, university_name: str = "", extension: str = "xlsx") -> str:
    """
    生成文件名（格式: 学校代码 学校英文名称.xlsx）
    
    参数:
        university_code (str): 大学代码（如 "UK038"）
        university_name (str): 大学英文名称（如 "University of Strathclyde"）
        extension (str): 文件扩展名（默认 "xlsx"）
    
    返回:
        str: 完整的文件名
    
    示例:
        >>> generate_filename("UK038", "University of Strathclyde")
        "UK038 University of Strathclyde.xlsx"
    """
    # 新格式: 学校代码 学校英文名称.xlsx
    if university_name:
        filename = f"{university_code} {university_name}.{extension}"
    else:
        # 兼容旧调用方式（如果没有提供名称，使用代码）
        filename = f"{university_code}.{extension}"
    
    return filename


def prepare_dataframe(data_list: List[Dict]) -> pd.DataFrame:
    """
    将数据列表转换为标准格式的 DataFrame
    
    参数:
        data_list (List[Dict]): 爬取到的数据列表
    
    返回:
        pd.DataFrame: 格式化后的数据表
    """
    if not data_list:
        print("⚠️ 警告: 数据列表为空")
        return pd.DataFrame(columns=EXCEL_COLUMNS)
    
    # 创建 DataFrame
    df = pd.DataFrame(data_list)
    
    # 补全缺失的列
    for col in EXCEL_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    
    # 按照指定顺序排列列
    df = df[EXCEL_COLUMNS]
    
    return df


def save_excel(
    data_list: List[Dict], 
    filename: Optional[str] = None,
    university: str = "University",
    university_code: str = "",
    university_name: str = "",
    output_dir: str = OUTPUT_DIR
) -> Optional[str]:
    """
    将数据保存为 Excel 文件
    
    参数:
        data_list (List[Dict]): 爬取到的数据列表
        filename (Optional[str]): 指定文件名（如不指定则自动生成）
        university (str): 大学名称标识（兼容旧版，用于生成文件名）
        university_code (str): 大学代码（如 "UK038"）
        university_name (str): 大学英文名称（如 "University of Strathclyde"）
        output_dir (str): 输出目录
    
    返回:
        Optional[str]: 保存成功返回文件路径，失败返回 None
    
    使用示例:
        >>> data = [{"学校名称": "HKU", "项目名称": "Computer Science"}]
        >>> filepath = save_excel(data, university_code="HK001", university_name="The University of Hong Kong")
        >>> print(f"文件已保存到: {filepath}")
    """
    if not data_list:
        print("❌ 错误: 没有数据可保存")
        return None
    
    # 确保输出目录存在
    ensure_output_dir(output_dir)
    
    # 生成文件名
    if filename is None:
        # 优先使用新格式（code + name）
        if university_code and university_name:
            filename = generate_filename(university_code, university_name, "xlsx")
        elif university_code:
            filename = generate_filename(university_code, "", "xlsx")
        else:
            # 兼容旧版调用
            filename = generate_filename(university, "", "xlsx")
    
    # 构建完整路径
    filepath = os.path.join(output_dir, filename)
    
    # 准备数据
    df = prepare_dataframe(data_list)
    
    try:
        # 尝试保存为 Excel
        df.to_excel(filepath, index=False, engine='openpyxl')
        
        print("=" * 50)
        print(f"✅ 成功导出 Excel 文件！")
        print(f"📂 文件路径: {filepath}")
        print(f"📊 包含数据: {len(df)} 行")
        print("=" * 50)
        
        return filepath
        
    except ImportError:
        # 如果没有安装 openpyxl，提示用户
        print("⚠️ 检测到环境缺少 Excel 支持库 (openpyxl)")
        print("   请运行: pip install openpyxl")
        print("   正在切换为 CSV 格式保存...")
        return save_csv(data_list, filename.replace(".xlsx", ".csv"), university, output_dir)
        
    except Exception as e:
        print(f"❌ Excel 导出失败: {e}")
        return None


def save_csv(
    data_list: List[Dict], 
    filename: Optional[str] = None,
    university: str = "University",
    university_code: str = "",
    university_name: str = "",
    output_dir: str = OUTPUT_DIR
) -> Optional[str]:
    """
    将数据保存为 CSV 文件（兜底方案）
    
    参数:
        data_list (List[Dict]): 爬取到的数据列表
        filename (Optional[str]): 指定文件名（如不指定则自动生成）
        university (str): 大学名称标识（用于生成文件名）
        university_code (str): 大学代码（如 "UK038"）
        university_name (str): 大学英文名称（如 "University of Strathclyde"）
        output_dir (str): 输出目录
    
    返回:
        Optional[str]: 保存成功返回文件路径，失败返回 None
    """
    if not data_list:
        print("❌ 错误: 没有数据可保存")
        return None
    
    # 确保输出目录存在
    ensure_output_dir(output_dir)
    
    # 生成文件名
    if filename is None:
        # 优先使用新格式（code + name）
        if university_code and university_name:
            filename = generate_filename(university_code, university_name, "csv")
        elif university_code:
            filename = generate_filename(university_code, "", "csv")
        else:
            # 兼容旧版调用
            filename = generate_filename(university, "", "csv")
    
    # 构建完整路径
    filepath = os.path.join(output_dir, filename)
    
    # 准备数据
    df = prepare_dataframe(data_list)
    
    try:
        # 保存为 CSV（使用 utf-8-sig 编码以支持 Excel 直接打开中文）
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        
        print("=" * 50)
        print(f"✅ 成功导出 CSV 文件！")
        print(f"📂 文件路径: {filepath}")
        print(f"📊 包含数据: {len(df)} 行")
        print("=" * 50)
        
        return filepath
        
    except Exception as e:
        print(f"❌ CSV 导出失败: {e}")
        return None


def preview_data(data_list: List[Dict], rows: int = 10) -> None:
    """
    预览数据（在控制台打印前几行，支持可点击链接）
    
    参数:
        data_list (List[Dict]): 数据列表
        rows (int): 预览行数（默认 10 行）
    """
    if not data_list:
        print("⚠️ 没有数据可预览")
        return
    
    df = prepare_dataframe(data_list)
    preview_df = df.head(rows)
    
    if RICH_AVAILABLE and console:
        # 使用 rich 表格显示（支持可点击链接）
        _preview_with_rich(preview_df, len(df), rows)
    else:
        # 降级为普通打印
        print(f"\n↓↓↓ 数据预览（前 {min(rows, len(df))} 行）↓↓↓")
        print(preview_df.to_string())
        print()


def _preview_with_rich(df: pd.DataFrame, total_rows: int, preview_rows: int) -> None:
    """
    使用 rich 库显示带有可点击链接的表格预览
    
    参数:
        df (pd.DataFrame): 要预览的数据
        total_rows (int): 总数据行数
        preview_rows (int): 预览行数
    """
    # 创建表格
    table = Table(
        title=f"📊 数据预览（共 {total_rows} 条，显示前 {len(df)} 条）",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        title_style="bold yellow",
        expand=False
    )
    
    # 定义要显示的列及其宽度
    display_columns = [
        ("序号", 4),
        ("项目名称", 30),
        ("项目官网链接", 18),
        ("申请链接", 18),
        ("项目deadline", 22),
    ]
    
    # 添加列
    for col_name, width in display_columns:
        table.add_column(col_name, width=width, overflow="ellipsis")
    
    # 添加数据行
    for idx, row in df.iterrows():
        # 处理链接列 - 使用 Text 对象创建可点击链接（避免 markup 解析错误）
        official_link = str(row.get("项目官网链接", "N/A"))
        apply_link = str(row.get("申请链接", "N/A"))
        
        # 创建可点击链接（使用 Text 对象，更安全）
        official_display = _create_clickable_link(official_link, "🔗 点击查看")
        apply_display = _create_clickable_link(apply_link, "🔗 申请")
        
        # 项目名称截断并转义
        prog_name_raw = str(row.get("项目名称", ""))
        prog_name = prog_name_raw[:28]
        if len(prog_name_raw) > 28:
            prog_name += "..."
        prog_name = rich_escape(prog_name)  # 转义特殊字符
        
        # deadline 也需要转义
        deadline = rich_escape(str(row.get("项目deadline", "N/A"))[:20])
        
        table.add_row(
            str(idx + 1),
            prog_name,
            official_display,
            apply_display,
            deadline
        )
    
    # 打印表格
    console.print()
    console.print(table)
    console.print()
    
    # 打印提示
    console.print(
        Panel(
            "💡 [bold green]提示[/bold green]: 点击 [cyan]🔗 点击查看[/cyan]、[cyan]🔗 注册[/cyan] 或 [cyan]🔗 登录[/cyan] 可在浏览器中打开链接验证爬取结果",
            title="链接验证",
            border_style="green"
        )
    )
    console.print()


def preview_full_data(data_list: List[Dict]) -> None:
    """
    显示完整的数据预览（所有行，带分页提示）
    
    参数:
        data_list (List[Dict]): 数据列表
    """
    if not data_list:
        print("⚠️ 没有数据可预览")
        return
    
    df = prepare_dataframe(data_list)
    
    if RICH_AVAILABLE and console:
        # 显示完整表格（每 20 行分页）
        page_size = 20
        total_pages = (len(df) + page_size - 1) // page_size
        
        for page in range(total_pages):
            start_idx = page * page_size
            end_idx = min((page + 1) * page_size, len(df))
            page_df = df.iloc[start_idx:end_idx]
            
            _preview_with_rich(page_df, len(df), end_idx - start_idx)
            
            if page < total_pages - 1:
                input(f"按 Enter 查看下一页 ({page + 2}/{total_pages})...")
    else:
        print(df.to_string())
        print()

