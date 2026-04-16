"""Template Context Builder - Extracted from GlobalStateManager.

This module handles building Jinja2 template contexts from state objects.
Follows Single Responsibility Principle by separating context building from state management.
"""

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .models import JobState, RunState


class TemplateContextBuilder:
    """
    Builds Jinja2 template contexts from run/job state.

    Extracted from GlobalStateManager to follow SRP.
    This class is stateless and only transforms state to context dicts.
    """

    def build_job_context(
        self,
        job: 'JobState',
        run: Optional['RunState'] = None,
        all_jobs: list['JobState'] | None = None
    ) -> dict[str, Any]:
        """
        Build Jinja2 template context for a job.

        Args:
            job: Current job state
            run: Optional run state for run-level context
            all_jobs: Optional list of all jobs for jobs array

        Returns:
            Complete template context dict
        """
        # Run context
        run_context = self._build_run_context(run)

        # Job context with status breakdown
        job_context = self._build_job_context_dict(job)

        return {
            "run": run_context,
            "job": job_context,
            "jobs": [self._job_to_summary(j) for j in (all_jobs or [])],
            "config": run.config if run else {},
            "options": run.config.get('options', {}) if run else {},
        }

    def _build_run_context(self, run: Optional['RunState']) -> dict[str, Any]:
        """Build run-level context dict."""
        if not run:
            return {
                "id": "",
                "status": {"success": True, "total_jobs": 0, "completed": 0, "failed": 0},
                "config": {}
            }

        return {
            "id": run.id,
            "status": {
                "success": run.status.success,
                "total_jobs": run.status.total_jobs,
                "completed": run.status.completed,
                "failed": run.status.failed
            },
            "config": run.config
        }

    def _build_job_context_dict(self, job: 'JobState') -> dict[str, Any]:
        """Build job-level context dict with status breakdown."""
        # Extract executed/failed/skipped from job.status.plugins
        executed, failed, skipped = self._categorize_plugins(job)

        return {
            "index": job.index,
            "id": job.id,
            "input": {
                "value": job.input.value,
                "data": job.input.data
            },
            "output": {
                "values": job.output.values,
                "data": job.output.data
            },
            "status": {
                "success": job.status.success,
                "executed": executed,
                "failed": failed,
                "skipped": skipped,
                "plugins": job.status.plugins
            },
            "plugins": job.plugins
        }

    def _categorize_plugins(self, job: 'JobState') -> tuple:
        """Categorize plugins by status (executed, failed, skipped)."""
        executed = []
        failed = []
        skipped = []

        for pname, pstatus in job.status.plugins.items():
            if isinstance(pstatus, dict):
                state = pstatus.get('state', '')
                if state == 'failed' or not pstatus.get('success', True):
                    failed.append(pname)
                elif state == 'skipped':
                    skipped.append(pname)
                elif state == 'completed':
                    executed.append(pname)

        return executed, failed, skipped

    def _job_to_summary(self, job: 'JobState') -> dict[str, Any]:
        """Convert job to summary context dict for jobs array."""
        return {
            "index": job.index,
            "id": job.id,
            "input": {
                "value": job.input.value,
                "data": job.input.data
            },
            "plugins": job.plugins
        }


