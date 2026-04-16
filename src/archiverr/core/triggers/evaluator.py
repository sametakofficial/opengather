"""
Trigger Rule Evaluator - 

Evaluates standard trigger rules (Airflow-inspired):
- all_success: All requirements must succeed
- one_success: At least one requirement must succeed
- all_done: All requirements must be done (success or fail)
- all_fail: All requirements must fail
- none_fail: No requirements can fail
"""

from typing import TYPE_CHECKING, Any

from .matcher import ValueMatcher

if TYPE_CHECKING:
    from archiverr.events import EventBus


class TriggerRuleEvaluator:
    """
    trigger rule evaluator.
    
    Evaluates standard trigger rules based on requirement matches.
    
    Standard rules (Airflow-inspired):
    - all_success (default): All requirements must match
    - one_success: At least one requirement must match
    - all_done: All requirements checked (match or not)
    - all_fail: All requirements must not match
    - none_fail: No requirements can fail
    
    Usage:
        evaluator = TriggerRuleEvaluator()
        should_run, reason = evaluator.evaluate(
            trigger_rule="all_success",
            requirements=["plugin.tmdb.data:success"],
            state=global_state
        )
    """

    VALID_RULES = {
        'all_success',
        'one_success',
        'all_done',
        'all_fail',
        'none_fail'
    }

    def __init__(self, event_bus: 'EventBus | None' = None):
        self.matcher = ValueMatcher()
        self._event_bus = event_bus

    def evaluate(
        self,
        trigger_rule: str,
        requirements: list[str],
        state: dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Evaluate trigger rule against requirements.
        
        Args:
            trigger_rule: Standard rule name
            requirements: List of requirement strings
            state: Global state dict
            
        Returns:
            (should_run, reason) tuple
        """
        # Validate trigger rule
        if trigger_rule not in self.VALID_RULES:
            return False, f"Invalid trigger rule: {trigger_rule}"

        # Empty requirements - always run
        if not requirements:
            return True, "No requirements"

        # Match all requirements
        matches = []
        errors = []

        for req in requirements:
            is_valid, matched, error = self.matcher.match(
                state, req, event_bus=self._event_bus
            )

            if not is_valid:
                errors.append(f"{req}: {error}")
                continue

            matches.append({
                'requirement': req,
                'matched': matched
            })

        # If there were validation errors, don't run
        if errors:
            return False, f"Validation errors: {'; '.join(errors)}"

        # Evaluate rule
        if trigger_rule == 'all_success':
            return self._evaluate_all_success(matches)
        elif trigger_rule == 'one_success':
            return self._evaluate_one_success(matches)
        elif trigger_rule == 'all_done':
            return self._evaluate_all_done(matches)
        elif trigger_rule == 'all_fail':
            return self._evaluate_all_fail(matches)
        elif trigger_rule == 'none_fail':
            return self._evaluate_none_fail(matches)

        return False, f"Unknown trigger rule: {trigger_rule}"

    def _evaluate_all_success(self, matches: list[dict]) -> tuple[bool, str]:
        """
        All requirements must match.
        
        Returns:
            (should_run, reason) tuple
        """
        if not matches:
            return True, "No requirements"

        failed = [m['requirement'] for m in matches if not m['matched']]

        if failed:
            return False, f"Requirements not met: {', '.join(failed)}"

        return True, "All requirements met"

    def _evaluate_one_success(self, matches: list[dict]) -> tuple[bool, str]:
        """
        At least one requirement must match.
        
        Returns:
            (should_run, reason) tuple
        """
        if not matches:
            return True, "No requirements"

        succeeded = [m['requirement'] for m in matches if m['matched']]

        if not succeeded:
            return False, "No requirements met"

        return True, f"Requirements met: {', '.join(succeeded)}"

    def _evaluate_all_done(self, matches: list[dict]) -> tuple[bool, str]:
        """
        All requirements must be checked (done).
        
        For all_done, we just need to verify all paths exist.
        This is always true if matching succeeded.
        
        Returns:
            (should_run, reason) tuple
        """
        # If we got here, all requirements were checked
        return True, "All requirements checked"

    def _evaluate_all_fail(self, matches: list[dict]) -> tuple[bool, str]:
        """
        All requirements must not match (fail).
        
        Returns:
            (should_run, reason) tuple
        """
        if not matches:
            return False, "No requirements to fail"

        succeeded = [m['requirement'] for m in matches if m['matched']]

        if succeeded:
            return False, f"Some requirements succeeded: {', '.join(succeeded)}"

        return True, "All requirements failed as expected"

    def _evaluate_none_fail(self, matches: list[dict]) -> tuple[bool, str]:
        """
        No requirements can fail.
        
        This is similar to all_success but more lenient.
        Requirements can be skipped/not found, but if present, must succeed.
        
        Returns:
            (should_run, reason) tuple
        """
        if not matches:
            return True, "No requirements"

        # For none_fail, we check if any explicitly failed
        # A requirement "fails" if it was checked and didn't match
        # For plugin paths with :success, not matching means plugin failed

        failed = [m['requirement'] for m in matches if not m['matched']]

        if failed:
            return False, f"Requirements failed: {', '.join(failed)}"

        return True, "No requirements failed"
