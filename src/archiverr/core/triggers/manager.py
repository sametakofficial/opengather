"""
Trigger Rule Manager - 

Main interface for trigger rule evaluation.
Integrates ValueMatcher and TriggerRuleEvaluator.
"""

from typing import TYPE_CHECKING, Any

from .evaluator import TriggerRuleEvaluator
from .matcher import ValueMatcher

if TYPE_CHECKING:
    from archiverr.events import EventBus


class TriggerRuleManager:
    """
    Trigger Rule Manager.
    
    Main interface for dependency resolution with trigger rules.
    
    Responsibilities:
    - Validate requirements
    - Evaluate trigger rules
    - Resolve state values
    - Return run/skip decision
    
    Usage:
        manager = TriggerRuleManager()
        
        should_run, reason = manager.should_execute(
            trigger_rule="all_success",
            requirements=["plugin.tmdb.data:success"],
            state=global_state
        )
        
        if should_run:
            # Execute plugin
        else:
            # Skip plugin with reason
    """

    def __init__(self, event_bus: 'EventBus | None' = None):
        self._event_bus = event_bus
        self.evaluator = TriggerRuleEvaluator(event_bus=event_bus)
        self.matcher = ValueMatcher()

    def should_execute(
        self,
        trigger_rule: str,
        requirements: list[str],
        state: dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Determine if plugin should execute based on trigger rule.
        
        Args:
            trigger_rule: Standard trigger rule name
            requirements: List of requirement paths
            state: Global state dict
            
        Returns:
            (should_run, reason) tuple
            
        Examples:
            # All requirements must succeed (default)
            should_execute(
                "all_success",
                ["plugin.tmdb.data:success"],
                state
            )
            
            # At least one must succeed
            should_execute(
                "one_success",
                ["plugin.tmdb.data:success", "plugin.omdb.data:success"],
                state
            )
        """
        # Validate all requirements first
        for req in requirements:
            is_valid, error = self.matcher.validate_requirement(req)
            if not is_valid:
                return False, f"Invalid requirement '{req}': {error}"

        # Evaluate trigger rule
        return self.evaluator.evaluate(trigger_rule, requirements, state)

    def check_requirement(
        self,
        requirement: str,
        state: dict[str, Any]
    ) -> tuple[bool, bool, str | None]:
        """
        Check a single requirement.
        
        Args:
            requirement: Requirement string
            state: Global state dict
            
        Returns:
            (is_valid, matches, error) tuple
        """
        return self.matcher.match(state, requirement, event_bus=self._event_bus)

    def validate_requirements(
        self,
        requirements: list[str]
    ) -> tuple[bool, list[str]]:
        """
        Validate requirement syntax.
        
        Args:
            requirements: List of requirement strings
            
        Returns:
            (all_valid, errors) tuple
        """
        errors = []

        for req in requirements:
            is_valid, error = self.matcher.validate_requirement(req)
            if not is_valid:
                errors.append(f"{req}: {error}")

        return len(errors) == 0, errors

    def resolve_value(
        self,
        path: str,
        state: dict[str, Any]
    ) -> tuple[bool, Any]:
        """
        Resolve value from state.
        
        Args:
            path: Dot-notation path
            state: Global state dict
            
        Returns:
            (found, value) tuple
        """
        return self.matcher.resolve_value(state, path)
