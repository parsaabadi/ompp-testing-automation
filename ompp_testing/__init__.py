"""
OpenM++ Testing Automation

A Python toolkit for testing OpenM++ models across different versions.
"""

from .clone_repo import clone_repo
from .build_model import build_model
from .service_manager import start_oms, stop_oms, get_oms_status
from .get_output_tables import get_output_tables, get_table_data, get_model_runs
from .run_models import run_models
from .compare_model_runs import compare_model_runs
from .report_generator import generate_html_report

__version__ = "1.0.0"
__author__ = "Statistics Canada"

__all__ = [
    'clone_repo',
    'build_model', 
    'start_oms',
    'stop_oms',
    'get_oms_status',
    'get_output_tables',
    'get_table_data',
    'get_model_runs',
    'run_models',
    'compare_model_runs',
    'generate_html_report'
] 