"""
Tasker Plugin - Session 12 with Main Branch Template Logic

Combines:
- Session 12 plugin architecture (per_run, stages, state)
- Main branch template rendering (Jinja2, $ syntax, smart routing)
"""

from datetime import datetime
from typing import Any

from jinja2 import BaseLoader, Environment

from archiverr.core.plugins.sdk import OutputPlugin
from archiverr.core.plugins.sdk import PluginResult as SDKPluginResult
from archiverr.core.safety import safe_copy


class TaskerPlugin(OutputPlugin):
    """Task execution plugin with full Jinja2 + state access."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = "tasker"
        self.tasks = config.get('tasks', [])
        # Session 38 B4: removed dead config keys ``save_output`` and
        # ``output_dir``; the run-output JSON path was never wired to a
        # caller. Run-state persistence already lives in MongoDB.

        # Jinja2 environment. ``count`` is Jinja's built-in alias for
        # ``length``; we register it explicitly so the dependency is
        # visible and cannot be shadowed by a future env reset.
        self.env = Environment(loader=BaseLoader())
        self.env.filters['truncate'] = self._filter_truncate
        self.env.filters['format'] = lambda fmt, *args: fmt % args
        self.env.filters['count'] = self._filter_count

    def execute(self, job: Any, services: Any) -> SDKPluginResult:
        """Execute tasks for job, returning a modern PluginResult."""
        from archiverr.state.template_context import TemplateContextBuilder

        started_at = datetime.now()

        # Run-scope safety flags are owned by the orchestrator. We read them
        # once per job invocation and thread them down into individual tasks.
        run_safety = services.run_safety
        dry_run = run_safety["dry_run"]
        hardlink = run_safety["hardlink"]

        # Canonical template context comes from TemplateContextBuilder per
        # datasets/04-template-context.yml. Tasker no longer mutates the
        # render-time context (plugin.<name>.data surface lives upstream).
        run = services.get_run() if hasattr(services, "get_run") else None
        all_jobs = list(services.get_all_jobs()) if hasattr(services, "get_all_jobs") else []
        events_snapshot = services.events.snapshot() if hasattr(services, "events") else {}

        context = TemplateContextBuilder().build_job_context(
            job, run=run, all_jobs=all_jobs, events=events_snapshot
        )
        # `index` is documented as a top-level shortcut in 04-template-context.yml.
        # `total` is tasker-local convenience; not part of the canonical contract.
        context["index"] = getattr(job, "index", 0)
        context["total"] = len(all_jobs) if all_jobs else 1

        # Execute tasks
        task_results = {}
        output_values = []

        for task in self.tasks:
            result = self._execute_task(task, context, dry_run=dry_run, hardlink=hardlink)
            if result:
                task_name = result.get('name', 'unnamed')
                task_results[task_name] = result

                # Collect save destinations
                if result.get('type') == 'save' and result.get('destination'):
                    output_values.append(result['destination'])

        # Write to job.output via services (Session 12 pattern)
        if output_values:
            services.update_job(key="output.values", value=output_values)

        if task_results:
            # Store task results in output.data under 'tasks' key
            services.update_job(key="output.data", value={"tasks": task_results})

        # Also store in plugin data (plugin.tasker.data)
        services.update_plugin(data={
            "tasks": task_results,
            "output_values": output_values
        })

        # Session 38 B4: dead ``_track_run_output`` + ``save_run_output``
        # path removed; nothing in the orchestrator ever invoked the JSON
        # writer. State persistence is handled by MongoDB now.

        return SDKPluginResult(
            success=True,
            data={
                'tasks': task_results,
                'values': output_values,
            },
            started_at=started_at,
            finished_at=datetime.now(),
        )

    def _execute_task(
        self,
        task: dict[str, Any],
        context: dict[str, Any],
        *,
        dry_run: bool,
        hardlink: bool,
    ) -> dict[str, Any] | None:
        """Execute single task (print/save) against the rendered context."""
        task_name = task.get('name', 'unnamed')
        task_type = task.get('type', 'print')
        condition = task.get('condition')

        # Check condition
        if condition and not self._evaluate_condition(condition, context):
            return None

        # Execute by type
        try:
            if task_type == 'print':
                return self._execute_print(task, context, task_name)
            elif task_type == 'save':
                return self._execute_save(task, context, task_name, dry_run=dry_run, hardlink=hardlink)
            else:
                return None
        except Exception as e:
            self.error(f"Task {task_name} failed", error=str(e))
            return {
                'name': task_name,
                'type': task_type,
                'success': False,
                'error': str(e)
            }

    def _execute_print(self, task: dict[str, Any], context: dict[str, Any], task_name: str) -> dict[str, Any] | None:
        """Execute print task."""
        template = task.get('template', '')
        if not template:
            return None

        rendered = self._render_template(template, context)
        print(rendered)

        return {
            'name': task_name,
            'type': 'print',
            'success': True,
            'rendered': rendered
        }

    def _execute_save(
        self,
        task: dict[str, Any],
        context: dict[str, Any],
        task_name: str,
        *,
        dry_run: bool,
        hardlink: bool,
    ) -> dict[str, Any] | None:
        """Execute save task."""
        destination_template = task.get('destination', '')
        if not destination_template:
            return None

        # Get source from job
        source = context['job']['input']['value']
        if not source:
            return None

        destination = self._render_template(destination_template, context)
        if not destination:
            return None

        planned = safe_copy(
            source, destination,
            hardlink=hardlink, dry_run=dry_run, overwrite=False,
        )
        success = planned.op not in {"error"}
        if planned.op == "error":
            self.error(f"Save task failed: {planned.reason}")

        return {
            'name': task_name,
            'type': 'save',
            'success': success,
            'source': source,
            'destination': destination,
            'dry_run': dry_run,
            'planned_operation': planned.to_dict(),
        }

    def _render_template(self, template: str, context: dict[str, Any]) -> str:
        """Render Jinja2 template.

        Uses canonical Jinja syntax: ``{{ plugin.<name>.data.<field> }}``,
        ``{{ plugin.<name>.data.items | count }}``, ``{{ index }}``.
        """
        try:
            tmpl = self.env.from_string(template)
            return tmpl.render(**context)
        except Exception as e:
            error_msg = str(e)
            if "has no attribute" in error_msg:
                return ""
            return f"Template error: {error_msg}"

    def _evaluate_condition(self, condition: str, context: dict[str, Any]) -> bool:
        """Evaluate Jinja2 condition."""
        if not condition:
            return True

        try:
            result = self._render_template(condition, context)
            return bool(result.strip()) and not result.startswith("Template error")
        except Exception:
            return False

    def _filter_truncate(self, value: str, length: int = 50, end: str = '...') -> str:
        """Truncate filter."""
        if not value or len(value) <= length:
            return value
        return value[:length - len(end)] + end

    @staticmethod
    def _filter_count(value: Any) -> int:
        """Count filter: number of items in a list/dict/string, else 0."""
        if value is None:
            return 0
        try:
            return len(value)
        except TypeError:
            return 0

