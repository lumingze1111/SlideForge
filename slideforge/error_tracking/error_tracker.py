"""
错误追踪器 - 记录和管理所有错误
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum
import traceback
from functools import wraps


class ErrorType(str, Enum):
    """错误类型"""
    API_ERROR = "API_ERROR"
    LLM_ERROR = "LLM_ERROR"
    CHART_ERROR = "CHART_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    REACT_ERROR = "REACT_ERROR"
    UNKNOWN = "UNKNOWN"


class ErrorSeverity(str, Enum):
    """错误严重程度"""
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass
class ErrorRecord:
    """错误记录"""
    timestamp: str
    error_id: str
    error_type: ErrorType
    severity: ErrorSeverity
    component: str
    slide_index: Optional[int]
    message: str
    stack_trace: Optional[str]
    context: Dict[str, Any]
    recovery_action: str
    recovered: bool


class ErrorTracker:
    """错误追踪器"""

    def __init__(self, session_id: str, output_dir: Path):
        self.session_id = session_id
        self.output_dir = output_dir / "error_logs" / f"session_{session_id}"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.errors: List[ErrorRecord] = []
        self.errors_file = self.output_dir / "errors.jsonl"

    def record_error(
        self,
        error_type: ErrorType,
        severity: ErrorSeverity,
        component: str,
        message: str,
        slide_index: Optional[int] = None,
        stack_trace: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        recovery_action: str = "None",
        recovered: bool = False
    ) -> str:
        """
        记录一个错误

        Returns:
            错误 ID
        """
        error_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        error = ErrorRecord(
            timestamp=timestamp,
            error_id=error_id,
            error_type=error_type,
            severity=severity,
            component=component,
            slide_index=slide_index,
            message=message,
            stack_trace=stack_trace,
            context=context or {},
            recovery_action=recovery_action,
            recovered=recovered
        )

        self.errors.append(error)

        # 写入 JSONL 文件
        with open(self.errors_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(error), ensure_ascii=False) + '\n')

        return error_id

    def get_summary(self) -> Dict[str, Any]:
        """获取错误统计摘要"""
        if not self.errors:
            return {
                "total_errors": 0,
                "by_severity": {},
                "by_type": {},
                "by_component": {},
                "recovery_rate": 0.0
            }

        by_severity = {}
        by_type = {}
        by_component = {}
        recovered_count = 0

        for error in self.errors:
            # 按严重程度统计
            severity_key = error.severity.value
            by_severity[severity_key] = by_severity.get(severity_key, 0) + 1

            # 按类型统计
            type_key = error.error_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1

            # 按组件统计
            by_component[error.component] = by_component.get(error.component, 0) + 1

            # 恢复计数
            if error.recovered:
                recovered_count += 1

        return {
            "total_errors": len(self.errors),
            "by_severity": by_severity,
            "by_type": by_type,
            "by_component": by_component,
            "recovery_rate": recovered_count / len(self.errors) if self.errors else 0.0
        }


def track_errors(component: str, error_type: ErrorType = ErrorType.UNKNOWN):
    """
    装饰器：自动追踪函数中的错误

    Usage:
        @track_errors(component="image_search", error_type=ErrorType.API_ERROR)
        def search_image(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 尝试从参数中获取 error_tracker
                error_tracker = None
                if args and hasattr(args[0], 'error_tracker'):
                    error_tracker = args[0].error_tracker
                elif 'error_tracker' in kwargs:
                    error_tracker = kwargs['error_tracker']

                if error_tracker:
                    error_tracker.record_error(
                        error_type=error_type,
                        severity=ErrorSeverity.ERROR,
                        component=component,
                        message=str(e),
                        stack_trace=traceback.format_exc(),
                        context={"function": func.__name__},
                        recovery_action="Exception raised",
                        recovered=False
                    )

                raise

        return wrapper
    return decorator


# 全局错误追踪器实例
_global_error_tracker: Optional[ErrorTracker] = None


def get_error_tracker() -> Optional[ErrorTracker]:
    """获取全局错误追踪器"""
    return _global_error_tracker


def set_error_tracker(tracker: ErrorTracker):
    """设置全局错误追踪器"""
    global _global_error_tracker
    _global_error_tracker = tracker
