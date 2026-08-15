"""Template Context Builder - Extracted from GlobalStateManager.

This module handles building Jinja2 template contexts from state objects.
Follows Single Responsibility Principle by separating context building from
state management.

Session 39 R15 §C1 — paradigm shift:

* The legacy ``plugin.<name>.{data,status}`` injected namespace has been
  removed (``_build_plugin_surface`` method deleted). Templates must now use
  full descent paths: ``{{ jobs[job_id].plugins.<name>.<field> }}`` or the
  ``data.<jobindex>.<category>.<path>`` resolver namespace populated by
  Phase D (``state/data_resolver.py`` + ``RunState.data``).
* ``jobs`` shape changed from a list of summaries to a dict keyed by
  ``job.id``. ``{{ jobs[job_id] }}`` lookup is now O(1) and matches the
  canonical ``data.<jobindex>...`` paradigm where the resolver substitutes
  ``<jobindex>`` from the live state context.
* New top-level shortcuts ``job_id`` and ``job_index`` mirror the active
  job for ergonomic templates.
* ``data`` namespace is exposed forward-looking; until Phase D wires
  ``RunState.data`` and ``_recompute_data_envelope``, it returns an empty
  dict (callers see undefined paths gracefully via ChainableUndefined once
  Phase H lands).
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
        all_jobs: list['JobState'] | None = None,
        events: dict[str, list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        """
        Build Jinja2 template context for a job.

        Args:
            job: Current job state.
            run: Optional run state for run-level context.
            all_jobs: Optional list of all jobs. Surfaced as a dict
                ``{job.id: summary}`` (Session 39 R15 §C1; previously a list).
            events: Optional event-bus snapshot
                (``EventBus.get_history_dict()`` shape) injected as
                ``{{ events }}`` per datasets/04-template-context.yml.

        Returns:
            Complete template context dict. Top-level keys:
            ``run``, ``job``, ``jobs`` (dict by id), ``config``, ``options``,
            ``events``, ``data`` (Phase D), ``job_id``, ``job_index``.
        """
        # Run context
        run_context = self._build_run_context(run)

        # Job context with status breakdown
        job_context = self._build_job_context_dict(job)

        # Jobs surface — dict keyed by job.id (R15 §C1; was list).
        jobs_by_id = {
            j.id: self._job_to_summary(j) for j in (all_jobs or [])
        }

        # Forward-looking data namespace (Phase D wires RunState.data).
        run_data = getattr(run, 'data', {}) if run else {}

        return {
            "run": run_context,
            "job": job_context,
            "jobs": jobs_by_id,
            "config": run.config if run else {},
            "options": run.config.get('options', {}) if run else {},
            "events": events or {},
            "data": run_data,
            "job_id": getattr(job, 'id', None),
            "jobid": getattr(job, 'id', None),
            "job_index": getattr(job, 'index', 0),
        }

    # NOTE (R15 §C1): ``_build_plugin_surface`` has been deleted.
    # The synthetic ``plugin.<name>.{data,status}`` namespace it built
    # is replaced by direct descent through ``jobs[job_id].plugins.<name>``
    # and the ``data.<jobindex>.<category>`` resolver (Phase D). Tasker
    # and any other render consumer must adopt the new paradigm.

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
        """Convert job to summary context dict for jobs dict (by id)."""
        return {
            "index": job.index,
            "id": job.id,
            "input": {
                "value": job.input.value,
                "data": job.input.data
            },
            "plugins": job.plugins
        }
