"""
Dashboard module for forensic toolkit.
Contains all dashboard generation functions for different evidence types.
"""

from . import kpi
from . import chart_data
from . import html_generator
from . import photo_dashboard
from . import audio_dashboard
from . import vision_dashboard
from . import email_dashboard

__all__ = [
    'kpi',
    'chart_data',
    'html_generator',
    'photo_dashboard',
    'audio_dashboard',
    'vision_dashboard',
    'email_dashboard',
]