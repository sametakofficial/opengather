"""
Tasker Plugin - Session 12 with Main Branch Template Logic

Combines:
- Session 12 plugin architecture (per_run, stages, state)
- Main branch template rendering (Jinja2, $ syntax, smart routing)
"""

import json
from datetime import datetime
from pathlib import Path
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
        self.save_output = config.get('save_output', True)
        self.output_dir = config.get('output_dir', 'output')

        # Jinja2 environment. ``count`` is Jinja's built-in alias for
        # ``length``; we register it explicitly so the dependency is
        # visible and cannot be shadowed by a future env reset.
        self.env = Environment(loader=BaseLoader())
        self.env.filters['truncate'] = self._filter_truncate
        self.env.filters['format'] = lambda fmt, *args: fmt % args
        self.env.filters['count'] = self._filter_count

        # Run output tracking
        self._run_output: dict[str, Any] = {}

    def execute(self, job: Any, services: Any) -> SDKPluginResult:
        """Execute tasks for job, returning a modern PluginResult."""
        from archiverr.state.template_context import TemplateContextBuilder

        started_at = datetime.now()

        # Run-scope safety flags are owned by the orchestrator. We read them
        # once per job invocation and thread them down into individual tasks.
        run_safety = services.run_safety
        dry_run = run_safety["dry_run"]
        hardlink = run_safety["hardlink"]

        plugins_data = {}
        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            plugins_data = dict(job.plugins)

        if hasattr(services, 'state'):
            available_plugins = services.state.get_job_plugin_names(job.id)
            for plugin_name in available_plugins:
                if plugin_name not in plugins_data:
                    try:
                        data = services.state.get_plugin_data(job.id, plugin_name)
                        if data:
                            plugins_data[plugin_name] = data
                    except Exception:
                        pass

        run = services.get_run() if hasattr(services, "get_run") else None
        all_jobs = list(services.get_all_jobs()) if hasattr(services, "get_all_jobs") else []

        events_snapshot = services.events.snapshot() if hasattr(services, "events") else {}

        context = TemplateContextBuilder().build_job_context(
            job, run=run, all_jobs=all_jobs, events=events_snapshot
        )
        context["plugin"] = {
            name: {"data": info if isinstance(info, dict) else {}}
            for name, info in plugins_data.items()
        }
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

        # Track for JSON output
        self._track_run_output(job, task_results, plugins_data)

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

    def _track_run_output(self, job: Any, task_results: dict[str, Any], plugins_data: dict[str, Any]) -> None:
        """
        Track run output for JSON save.

        Session 14 structure:
        - input: value + data (plugin sets)
        - output: values + data (plugin sets)
        - plugins: plugin data (each plugin has status + data)
        - tasks removed: tasker plugin stores task results in its own data
        """
        job_id = getattr(job, 'id', 'unknown')

        # Add task results to tasker plugin data
        if 'tasker' in plugins_data:
            plugins_data['tasker']['data']['tasks'] = task_results

        self._run_output[job_id] = {
            'job_id': job_id,
            'index': getattr(job, 'index', 0),
            'input': {
                'value': getattr(job.input, 'value', '') if hasattr(job, 'input') else '',
                'data': getattr(job.input, 'data', {}) if hasattr(job, 'input') else {}
            },
            'output': {
                'values': getattr(job.output, 'values', []) if hasattr(job, 'output') else [],
                'data': getattr(job.output, 'data', {}) if hasattr(job, 'output') else {}
            },
            'plugins': plugins_data,
            'success': True,
            'timestamp': datetime.now().isoformat()
        }

    def save_run_output(self, run_id: str) -> str | None:
        """Save run output to JSON file."""
        if not self.save_output or not self._run_output:
            return None

        try:
            output_dir = Path(self.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"run_{run_id}_{timestamp}.json"
            filepath = output_dir / filename

            output_data = {
                'run_id': run_id,
                'timestamp': datetime.now().isoformat(),
                'jobs': list(self._run_output.values()),
                'total_jobs': len(self._run_output)
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            return str(filepath)

        except OSError as e:
            self.error(f"Failed to save run output: {e}")
            return None

