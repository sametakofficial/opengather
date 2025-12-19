"""
Trigger Rule System - 

Provides dependency resolution with:
- Standard trigger rules (Airflow-inspired)
- Value-based trigger rules (inline checks)
- Plugin vs non-plugin validation
"""

from .evaluator import TriggerRuleEvaluator
from .manager import TriggerRuleManager
from .matcher import ValueMatcher

__all__ = ['TriggerRuleManager', 'TriggerRuleEvaluator', 'ValueMatcher']
