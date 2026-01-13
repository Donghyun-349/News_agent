#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Timezone Utilities for Korean Standard Time (KST)

This module provides centralized timezone handling to ensure all date/time
operations across the News Agent use Korean Standard Time (UTC+9).
"""

from datetime import datetime
import pytz

# Korean Standard Time (UTC+9)
KST = pytz.timezone('Asia/Seoul')


def get_kst_now() -> datetime:
    """
    Get current datetime in Korean Standard Time (KST).
    
    Returns:
        datetime: Current time in KST timezone
    """
    return datetime.now(KST)


def format_kst_date(format_string: str = "%Y-%m-%d") -> str:
    """
    Get current date in KST formatted as a string.
    
    Args:
        format_string: strftime format string (default: "%Y-%m-%d")
    
    Returns:
        str: Formatted date string in KST
        
    Examples:
        >>> format_kst_date("%Y-%m-%d")
        '2026-01-13'
        >>> format_kst_date("%Y_%m_%d")
        '2026_01_13'
        >>> format_kst_date("%y%m%d")
        '260113'
    """
    return get_kst_now().strftime(format_string)


def format_kst_datetime(format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Get current datetime in KST formatted as a string.
    
    Args:
        format_string: strftime format string (default: "%Y-%m-%d %H:%M:%S")
    
    Returns:
        str: Formatted datetime string in KST
    """
    return get_kst_now().strftime(format_string)
