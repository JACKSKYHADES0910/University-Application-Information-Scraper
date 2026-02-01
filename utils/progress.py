# -*- coding: utf-8 -*-
"""
进度显示模块
封装 rich 库的进度条和统计显示功能，供所有爬虫复用
"""

import sys
import time
import signal
import threading
from typing import List, Dict, Callable, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, Future

# 尝试导入 rich 库
try:
    from rich.console import Console
    from rich.progress import (
        Progress, SpinnerColumn, BarColumn, TextColumn, 
        TimeElapsedColumn, TimeRemainingColumn, TaskProgressColumn
    )
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


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


class CrawlerProgress:
    """
    爬虫进度管理器
    
    封装了并发任务执行、进度显示、中断处理等功能
    支持 Ctrl+C 优雅中断，中断后显示已完成的结果
    
    使用示例:
        >>> progress = CrawlerProgress(max_workers=20)
        >>> results = progress.run_tasks(
        ...     items=program_list,
        ...     task_func=process_single_program,
        ...     task_name="抓取详情"
        ... )
    """
    
    def __init__(self, max_workers: int = 8):
        """
        初始化进度管理器
        
        参数:
            max_workers (int): 并发线程数
        """
        self.max_workers = max_workers
        self.results: List[Dict] = []
        self.failed_items: List[Dict] = []  # 存储失败的项目
        self.durations: List[float] = []
        self.is_interrupted = False  # 是否被中断
        self.lock = threading.Lock()
        
        # 统计信息
        self.completed_count = 0
        self.success_count = 0
        self.fail_count = 0
    
    def run_tasks(
        self, 
        items: List[Dict], 
        task_func: Callable[[Dict], tuple],
        task_name: str = "任务进度",
        phase_name: str = "Phase 2"
    ) -> List[Dict]:
        """
        并发执行任务并显示进度
        
        参数:
            items (List[Dict]): 要处理的项目列表
            task_func (Callable): 处理单个项目的函数，返回 (result_dict, duration)
            task_name (str): 任务名称（显示在进度条上）
            phase_name (str): 阶段名称
        
        返回:
            List[Dict]: 成功处理的结果列表
        """
        total = len(items)
        self._reset_stats()
        
        if RICH_AVAILABLE and console:
            return self._run_with_rich_progress(items, task_func, task_name, phase_name, total)
        else:
            return self._run_with_simple_progress(items, task_func, task_name, phase_name, total)
    
    def _reset_stats(self):
        """重置统计信息"""
        self.results = []
        self.failed_items = []
        self.durations = []
        self.is_interrupted = False
        self.completed_count = 0
        self.success_count = 0
        self.fail_count = 0
    
    def _run_with_rich_progress(
        self, 
        items: List[Dict], 
        task_func: Callable,
        task_name: str,
        phase_name: str,
        total: int
    ) -> List[Dict]:
        """
        使用 rich 进度条执行任务
        """
        # 显示启动信息
        console.print()
        console.print(Panel(
            f"[bold cyan]🔥 {phase_name}: 并发抓取详情[/bold cyan]\n"
            f"[yellow]并发线程数: {self.max_workers}[/yellow] | "
            f"[green]总任务数: {total}[/green]\n"
            f"[dim]按 Ctrl+C 可随时中断[/dim]",
            title="任务启动",
            border_style="cyan"
        ))
        console.print()
        
        # 设置中断处理
        original_handler = signal.signal(signal.SIGINT, self._interrupt_handler)
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40, complete_style="green", finished_style="bold green"),
                TaskProgressColumn(),
                TextColumn("•"),
                TimeElapsedColumn(),
                TextColumn("•"),
                TimeRemainingColumn(),
                TextColumn("• [cyan]成功: {task.fields[success]}[/cyan] [red]失败: {task.fields[fail]}[/red]"),
                console=console,
                expand=False
            ) as progress:
                
                task = progress.add_task(
                    task_name, 
                    total=total, 
                    success=0, 
                    fail=0
                )
                
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_item = {
                        executor.submit(task_func, item): item 
                        for item in items
                    }
                    
                    for future in as_completed(future_to_item):
                        if self.is_interrupted:
                            # 取消所有未完成的任务
                            for f in future_to_item:
                                f.cancel()
                            break
                        
                        item = future_to_item[future]
                        try:
                            data, duration = future.result(timeout=1)
                            self.results.append(data)
                            
                            with self.lock:
                                self.completed_count += 1
                                self.success_count += 1
                                self.durations.append(duration)
                            
                            progress.update(
                                task, 
                                advance=1,
                                success=self.success_count,
                                fail=self.fail_count
                            )
                            
                        except Exception as exc:
                            with self.lock:
                                self.completed_count += 1
                                self.fail_count += 1
                                self.failed_items.append({
                                    "name": item.get("name", "Unknown"),
                                    "link": item.get("link", ""),
                                    "error": str(exc)
                                })
                            
                            progress.update(
                                task, 
                                advance=1,
                                success=self.success_count,
                                fail=self.fail_count
                            )
        
        finally:
            # 恢复原始信号处理器
            signal.signal(signal.SIGINT, original_handler)
        
        # 显示统计和失败信息
        self._print_summary(total)
        
        return self.results
    
    def _run_with_simple_progress(
        self, 
        items: List[Dict], 
        task_func: Callable,
        task_name: str,
        phase_name: str,
        total: int
    ) -> List[Dict]:
        """
        使用简单文本显示进度（降级方案）
        """
        print(f"\n🔥 [{phase_name}] 启动 {self.max_workers} 个并发窗口进行后台抓取...", flush=True)
        print(f"按 Ctrl+C 可随时中断", flush=True)
        time.sleep(1)
        
        # 设置中断处理
        original_handler = signal.signal(signal.SIGINT, self._interrupt_handler)
        
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_item = {
                    executor.submit(task_func, item): item 
                    for item in items
                }
                
                print(f"⏳ 任务队列已建立，正在全力运行中...", flush=True)
                
                for future in as_completed(future_to_item):
                    if self.is_interrupted:
                        for f in future_to_item:
                            f.cancel()
                        break
                    
                    item = future_to_item[future]
                    try:
                        data, duration = future.result(timeout=1)
                        self.results.append(data)
                        self.completed_count += 1
                        self.success_count += 1
                        self.durations.append(duration)
                        
                        # 计算进度
                        percent = (self.completed_count / total) * 100
                        avg_time = sum(self.durations) / len(self.durations)
                        remaining = (total - self.completed_count) * avg_time / self.max_workers
                        
                        name_preview = data['项目名称'][:20] + "..." if len(data.get('项目名称', '')) > 20 else data.get('项目名称', '')
                        print(f"[{self.completed_count}/{total}] {percent:.1f}% ✅ {name_preview} | ⏱️ {duration:.2f}s | 预计剩余: {remaining:.0f}s", flush=True)
                        
                    except Exception as exc:
                        self.completed_count += 1
                        self.fail_count += 1
                        self.failed_items.append({
                            "name": item.get("name", "Unknown"),
                            "link": item.get("link", ""),
                            "error": str(exc)
                        })
                        print(f"❌ 任务异常: {item.get('name', '')[:20]} - {exc}", flush=True)
        
        finally:
            signal.signal(signal.SIGINT, original_handler)
        
        # 显示统计
        self._print_summary_simple(total)
        
        return self.results
    
    def _interrupt_handler(self, signum, frame):
        """
        处理 Ctrl+C 中断信号
        """
        self.is_interrupted = True
        if RICH_AVAILABLE and console:
            console.print("\n[bold yellow]⚠️ 检测到中断信号，正在优雅停止...[/bold yellow]")
        else:
            print("\n⚠️ 检测到中断信号，正在优雅停止...", flush=True)
    
    def _print_summary(self, total: int) -> None:
        """
        打印详细统计信息（rich 版本）
        """
        # 判断是否被中断
        status_title = "[bold yellow]⚠️ 任务被中断[/bold yellow]" if self.is_interrupted else "[bold green]✅ 任务完成[/bold green]"
        
        # 创建统计表格
        table = Table(title="📊 抓取统计", box=box.ROUNDED, show_header=True, header_style="bold magenta")
        table.add_column("指标", style="cyan", width=15)
        table.add_column("数值", style="green", width=20)
        
        table.add_row("总任务数", str(total))
        table.add_row("已完成", str(self.completed_count))
        table.add_row("成功数", f"[green]{self.success_count}[/green]")
        table.add_row("失败数", f"[red]{self.fail_count}[/red]" if self.fail_count > 0 else "0")
        
        if self.completed_count > 0:
            success_rate = (self.success_count / self.completed_count) * 100
            table.add_row("成功率", f"{success_rate:.1f}%")
        
        if self.durations:
            table.add_row("─" * 12, "─" * 15)
            avg_duration = sum(self.durations) / len(self.durations)
            table.add_row("平均耗时/任务", f"{avg_duration:.2f}s")
            table.add_row("最快任务", f"{min(self.durations):.2f}s")
            table.add_row("最慢任务", f"{max(self.durations):.2f}s")
            table.add_row("累计抓取时间", f"{sum(self.durations):.1f}s")
        
        console.print()
        console.print(Panel(table, title=status_title, border_style="yellow" if self.is_interrupted else "green"))
        
        # 显示失败项目摘要（不列出每个）
        if self.fail_count > 0:
            console.print()
            console.print(Panel(
                f"[red]共有 {self.fail_count} 个项目抓取失败[/red]\n"
                f"[dim]失败原因通常为: 页面加载超时、元素未找到等[/dim]",
                title="⚠️ 失败摘要",
                border_style="red"
            ))
        
        console.print()
    
    def _print_summary_simple(self, total: int) -> None:
        """
        打印统计信息（简单文本版本）
        """
        status = "⚠️ 任务被中断" if self.is_interrupted else "✅ 任务完成"
        
        print("\n" + "=" * 50, flush=True)
        print(f"📊 抓取统计 - {status}", flush=True)
        print("=" * 50, flush=True)
        print(f"  总任务: {total} | 已完成: {self.completed_count}", flush=True)
        print(f"  成功: {self.success_count} | 失败: {self.fail_count}", flush=True)
        
        if self.completed_count > 0:
            print(f"  成功率: {(self.success_count/self.completed_count)*100:.1f}%", flush=True)
        
        if self.durations:
            avg = sum(self.durations) / len(self.durations)
            print(f"  平均耗时: {avg:.2f}s | 最快: {min(self.durations):.2f}s | 最慢: {max(self.durations):.2f}s", flush=True)
        
        if self.fail_count > 0:
            print(f"\n⚠️ 共有 {self.fail_count} 个项目抓取失败", flush=True)
        
        print("=" * 50, flush=True)
    
    def get_failed_items(self) -> List[Dict]:
        """
        获取失败的项目列表
        
        返回:
            List[Dict]: 失败项目列表，包含 name, link, error
        """
        return self.failed_items
    
    def was_interrupted(self) -> bool:
        """
        检查是否被中断
        
        返回:
            bool: 是否被中断
        """
        return self.is_interrupted


def print_phase_start(phase_name: str, description: str, workers: int = None, total: int = None) -> None:
    """
    打印阶段开始信息
    
    参数:
        phase_name (str): 阶段名称
        description (str): 描述
        workers (int): 并发数（可选）
        total (int): 总任务数（可选）
    """
    if RICH_AVAILABLE and console:
        info_lines = [f"[bold cyan]{description}[/bold cyan]"]
        if workers:
            info_lines.append(f"[yellow]并发线程数: {workers}[/yellow]")
        if total:
            info_lines.append(f"[green]总任务数: {total}[/green]")
        
        console.print()
        console.print(Panel(
            "\n".join(info_lines),
            title=f"🚀 {phase_name}",
            border_style="cyan"
        ))
        console.print()
    else:
        print(f"\n🚀 [{phase_name}] {description}", flush=True)
        if workers:
            print(f"   并发线程数: {workers}", flush=True)
        if total:
            print(f"   总任务数: {total}", flush=True)


def print_phase_complete(phase_name: str, count: int) -> None:
    """
    打印阶段完成信息
    
    参数:
        phase_name (str): 阶段名称
        count (int): 完成数量
    """
    if RICH_AVAILABLE and console:
        console.print(f"[bold green]✅ [{phase_name}] 完成！共锁定 {count} 个项目[/bold green]")
    else:
        print(f"✅ [{phase_name}] 完成！共锁定 {count} 个项目", flush=True)


class SequentialCrawlerProgress:
    """
    顺序爬虫进度管理器 (Sequential Progress Manager)
    
    专为单线程/顺序执行的爬虫任务设计 (如 Selenium 循环抓取)。
    支持 rich 进度条和安全的日志打印。
    
    使用示例:
        >>> progress = SequentialCrawlerProgress(title="抓取任务")
        >>> with progress.create_progress(total=100) as p:
        ...     for i in range(100):
        ...         progress.log(f"正在处理 {i}")
        ...         p.update(advance=1)
    """
    
    def __init__(self, title: str = "任务进度"):
        self.title = title
        self.console = _get_console() if RICH_AVAILABLE else None
        self.progress = None
        self.task_id = None
        self.stats = {"success": 0, "fail": 0}

    def create_progress(self, total: int):
        """
        创建进度条上下文管理器
        """
        if RICH_AVAILABLE and self.console:
            return self._RichContext(self, total)
        else:
            return self._SimpleContext(self, total)

    def log(self, message: str, level: str = "info"):
        """
        在进度条上方打印日志，避免破坏进度条显示
        """
        if RICH_AVAILABLE and self.progress:
            style = "white"
            if level == "success": style = "green"
            elif level == "warning": style = "yellow"
            elif level == "error": style = "red"
            self.progress.console.print(f"[{style}]{message}[/{style}]")
        else:
            prefix = "✅" if level == "success" else "❌" if level == "error" else "ℹ️"
            print(f"{prefix} {message}", flush=True)

    def update(self, advance: int = 1, success: bool = True):
        """更新进度和统计"""
        if success:
            self.stats["success"] += 1
        else:
            self.stats["fail"] += 1
            
        if RICH_AVAILABLE and self.progress:
            self.progress.update(
                self.task_id, 
                advance=advance,
                success=self.stats["success"],
                fail=self.stats["fail"]
            )
        else:
            # Simple text mode update could go here if needed, but usually redundant with logs
            pass

    class _RichContext:
        def __init__(self, parent, total):
            self.parent = parent
            self.total = total
        
        def __enter__(self):
            self.parent.progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40, complete_style="green", finished_style="bold green"),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                TextColumn("• [green]成功: {task.fields[success]}[/green] [red]失败: {task.fields[fail]}[/red]"),
                console=self.parent.console,
                expand=False,
                transient=False 
            )
            self.parent.progress.start()
            self.parent.task_id = self.parent.progress.add_task(
                self.parent.title, 
                total=self.total, 
                success=0, 
                fail=0
            )
            return self.parent

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.parent.progress.stop()
            self.parent.progress = None

    class _SimpleContext:
        def __init__(self, parent, total):
            self.parent = parent
            self.total = total
        
        def __enter__(self):
            print(f"\n🚀 {self.parent.title} 开始 | 总任务数: {self.total}")
            return self.parent

        def __exit__(self, exc_type, exc_val, exc_tb):
            print(f"\n✅ {self.parent.title} 完成 | 成功: {self.parent.stats['success']} | 失败: {self.parent.stats['fail']}")
