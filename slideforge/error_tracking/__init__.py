"""
SlideForge 错误追踪模块
"""

from slideforge.error_tracking.error_tracker import (
    ErrorTracker,
    ErrorRecord,
    ErrorType,
    ErrorSeverity,
    track_errors,
    get_error_tracker,
    set_error_tracker
)
from slideforge.error_tracking.error_reporter import ErrorReporter

__all__ = [
    "ErrorTracker",
    "ErrorRecord",
    "ErrorType",
    "ErrorSeverity",
    "track_errors",
    "get_error_tracker",
    "set_error_tracker",
    "ErrorReporter",
]
