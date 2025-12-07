"""
Trigger Rule System - Session 12

Provides dependency resolution with:
- Standard trigger rules (Airflow-inspired)
- Value-based trigger rules (inline checks)
- Plugin vs non-plugin validation
"""

from .manager import TriggerRuleManager
from .evaluator import TriggerRuleEvaluator
from .matcher import ValueMatcher

__all__ = ['TriggerRuleManager', 'TriggerRuleEvaluator', 'ValueMatcher']
