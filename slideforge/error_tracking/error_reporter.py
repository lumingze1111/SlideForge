"""
错误报告生成器 - 生成 HTML 格式的错误报告
"""

from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from slideforge.error_tracking.error_tracker import ErrorTracker, ErrorRecord, ErrorSeverity, ErrorType


class ErrorReporter:
    """错误报告生成器"""

    def __init__(self, error_tracker: ErrorTracker, topic: str, total_slides: int):
        self.error_tracker = error_tracker
        self.topic = topic
        self.total_slides = total_slides
        self.start_time = datetime.now()

    def generate_html_report(self) -> str:
        """生成 HTML 错误报告"""
        end_time = datetime.now()
        summary = self.error_tracker.get_summary()
        errors = self.error_tracker.errors

        # 按幻灯片索引分组
        errors_by_slide: Dict[int, List[ErrorRecord]] = {}
        errors_without_slide: List[ErrorRecord] = []

        for error in errors:
            if error.slide_index is not None:
                if error.slide_index not in errors_by_slide:
                    errors_by_slide[error.slide_index] = []
                errors_by_slide[error.slide_index].append(error)
            else:
                errors_without_slide.append(error)

        # 生成 HTML
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SlideForge 错误报告 - {self.topic}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; padding: 2rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: #1976D2; color: white; padding: 1.5rem; border-radius: 8px 8px 0 0; }}
        .header h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; }}
        .header .meta {{ font-size: 0.9rem; opacity: 0.9; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; padding: 1.5rem; background: white; }}
        .stat-card {{ background: #f5f5f5; padding: 1rem; border-radius: 6px; text-align: center; }}
        .stat-card .number {{ font-size: 2rem; font-weight: bold; margin-bottom: 0.5rem; }}
        .stat-card .label {{ font-size: 0.9rem; color: #666; }}
        .stat-card.error .number {{ color: #c62828; }}
        .stat-card.warning .number {{ color: #e65100; }}
        .stat-card.success .number {{ color: #2e7d32; }}
        .stat-card.info .number {{ color: #1565c0; }}
        .section {{ background: white; margin-top: 1.5rem; padding: 1.5rem; border-radius: 8px; }}
        .section h2 {{ margin-bottom: 1rem; font-size: 1.2rem; }}
        .error-item {{ border: 1px solid #ddd; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; }}
        .error-item .error-header {{ display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; }}
        .error-item .badge {{ padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; color: white; font-weight: bold; }}
        .error-item .badge.critical {{ background: #c62828; }}
        .error-item .badge.error {{ background: #ef5350; }}
        .error-item .badge.warning {{ background: #ffa726; }}
        .error-item .error-title {{ font-weight: bold; flex: 1; }}
        .error-item .timestamp {{ color: #666; font-size: 0.85rem; }}
        .error-item .details {{ color: #666; line-height: 1.6; margin-left: 1.5rem; font-size: 0.9rem; }}
        .error-item .recovery {{ margin-top: 0.5rem; padding: 0.5rem; background: #e8f5e9; border-radius: 4px; font-size: 0.85rem; }}
        .error-item .recovery.failed {{ background: #ffebee; }}
        .stack-trace {{ background: #f5f5f5; padding: 0.75rem; border-radius: 4px; font-family: monospace; font-size: 0.8rem; max-height: 200px; overflow-y: auto; margin-top: 0.5rem; }}
        .distribution-bar {{ display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.5rem; }}
        .distribution-bar .bar {{ height: 24px; border-radius: 4px; display: flex; align-items: center; padding: 0 0.5rem; color: white; font-size: 0.85rem; }}
        .no-errors {{ text-align: center; padding: 3rem; color: #666; }}
        .no-errors .icon {{ font-size: 3rem; margin-bottom: 1rem; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>SlideForge 错误报告</h1>
            <div class="meta">
                会话 ID: {self.error_tracker.session_id} |
                主题: {self.topic} |
                生成时间: {end_time.strftime("%Y-%m-%d %H:%M:%S")}
            </div>
        </div>

        <div class="stats">
            <div class="stat-card error">
                <div class="number">{summary['total_errors']}</div>
                <div class="label">总错误数</div>
            </div>
            <div class="stat-card warning">
                <div class="number">{summary['by_severity'].get('CRITICAL', 0) + summary['by_severity'].get('ERROR', 0)}</div>
                <div class="label">严重错误</div>
            </div>
            <div class="stat-card success">
                <div class="number">{sum(1 for e in errors if e.recovered)}</div>
                <div class="label">已恢复</div>
            </div>
            <div class="stat-card info">
                <div class="number">{int(summary['recovery_rate'] * 100)}%</div>
                <div class="label">恢复率</div>
            </div>
        </div>

        {self._generate_distribution_section(summary)}
        {self._generate_errors_by_slide_section(errors_by_slide, errors_without_slide)}
        {self._generate_all_errors_section(errors)}

        <div class="section">
            <p style="text-align: center; color: #666;">报告生成于 {end_time.strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    def _generate_distribution_section(self, summary: Dict[str, Any]) -> str:
        """生成错误分布部分"""
        if summary['total_errors'] == 0:
            return ""

        by_type = summary['by_type']
        total = summary['total_errors']

        bars_html = ""
        colors = {
            'API_ERROR': '#ef5350',
            'LLM_ERROR': '#ffa726',
            'CHART_ERROR': '#42a5f5',
            'NETWORK_ERROR': '#ab47bc',
            'TIMEOUT': '#ff7043',
            'REACT_ERROR': '#ec407a',
            'UNKNOWN': '#78909c'
        }

        for error_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total) * 100
            color = colors.get(error_type, '#78909c')
            bars_html += f"""
            <div class="distribution-bar">
                <div class="bar" style="background: {color}; width: {percentage}%;">{error_type} ({count})</div>
            </div>
            """

        return f"""
        <div class="section">
            <h2>错误分布（按类型）</h2>
            {bars_html}
        </div>
        """

    def _generate_errors_by_slide_section(
        self,
        errors_by_slide: Dict[int, List[ErrorRecord]],
        errors_without_slide: List[ErrorRecord]
    ) -> str:
        """生成按幻灯片分组的错误部分"""
        if not errors_by_slide and not errors_without_slide:
            return ""

        html = '<div class="section"><h2>按幻灯片分组</h2>'

        # 全局错误（不关联特定幻灯片）
        if errors_without_slide:
            html += '<h3 style="margin-top: 1rem; margin-bottom: 0.5rem;">全局错误</h3>'
            for error in errors_without_slide:
                html += self._generate_error_item(error)

        # 按幻灯片分组
        for slide_index in sorted(errors_by_slide.keys()):
            slide_errors = errors_by_slide[slide_index]
            html += f'<h3 style="margin-top: 1rem; margin-bottom: 0.5rem;">幻灯片 #{slide_index + 1} ({len(slide_errors)} 个错误)</h3>'
            for error in slide_errors:
                html += self._generate_error_item(error)

        html += '</div>'
        return html

    def _generate_all_errors_section(self, errors: List[ErrorRecord]) -> str:
        """生成所有错误详情部分"""
        if not errors:
            return """
            <div class="section">
                <div class="no-errors">
                    <div class="icon">✓</div>
                    <p>没有错误记录</p>
                </div>
            </div>
            """

        html = '<div class="section"><h2>错误详情</h2>'
        for error in errors:
            html += self._generate_error_item(error, show_stack_trace=True)
        html += '</div>'
        return html

    def _generate_error_item(self, error: ErrorRecord, show_stack_trace: bool = False) -> str:
        """生成单个错误条目的 HTML"""
        severity_class = error.severity.value.lower()
        badge_class = severity_class

        recovery_html = ""
        if error.recovery_action != "None":
            recovery_class = "recovery" if error.recovered else "recovery failed"
            status_icon = "✓" if error.recovered else "✗"
            recovery_html = f'<div class="{recovery_class}">{status_icon} 恢复措施: {error.recovery_action}</div>'

        stack_trace_html = ""
        if show_stack_trace and error.stack_trace:
            stack_trace_html = f'<div class="stack-trace">{error.stack_trace}</div>'

        slide_info = f'幻灯片 #{error.slide_index + 1} | ' if error.slide_index is not None else ''

        return f"""
        <div class="error-item">
            <div class="error-header">
                <span class="badge {badge_class}">{error.severity.value}</span>
                <span class="error-title">{error.message}</span>
                <span class="timestamp">{error.timestamp.split('T')[1].split('.')[0]}</span>
            </div>
            <div class="details">
                {slide_info}组件: {error.component} | 类型: {error.error_type.value} | ID: {error.error_id}
            </div>
            {recovery_html}
            {stack_trace_html}
        </div>
        """

    def save_report(self) -> Path:
        """保存错误报告到文件"""
        html = self.generate_html_report()
        report_path = self.error_tracker.output_dir / "report.html"
        report_path.write_text(html, encoding='utf-8')
        return report_path
