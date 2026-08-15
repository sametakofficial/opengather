"""
Tasker Plugin — minimal print/save engine.

S39 R15 §H4a: Tasker no longer imports Jinja2. Template + condition
rendering is delegated to the core ``ConfigRenderEngine`` accessed via
``services.render_engine``. The plugin itself just iterates tasks and
dispatches to print or save backends.

If ``services.render_engine`` is None (test fixture / stub), the plugin
self-instantiates a fallback engine so behaviour stays consistent across
test paths.
"""

from datetime import datetime
from typing import Any

from archiverr.core.plugins.sdk import OutputPlugin
from archiverr.core.plugins.sdk import PluginResult as SDKPluginResult
from archiverr.core.safety import safe_copy


class TaskerPlugin(OutputPlugin):
    """Task execution plugin (print/save)."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = "tasker"
        self.tasks = config.get('tasks', [])
        # Session 38 B4: removed dead config keys ``save_output`` and
        # ``output_dir``; the run-output JSON path was never wired to a
        # caller. Run-state persistence already lives in MongoDB.

        # S39 H4a: ``self.env`` is gone. Filter implementations and the
        # Jinja2 ``Environment`` live in ``archiverr.core.render``.
        # Older test code that did ``plugin.env.from_string(...)`` should
        # consume ``ConfigRenderEngine`` directly instead.

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
        # datasets/04-template-context.yml. Tasker does not mutate the
        # render-time context. S41: do not call deleted services getters;
        # read the orchestrator-owned state object when present.
        run, all_jobs = self._run_and_jobs(services)
        events_snapshot = services.events.snapshot() if hasattr(services, "events") else {}

        context = TemplateContextBuilder().build_job_context(
            job, run=run, all_jobs=all_jobs, events=events_snapshot
        )
        # `index` is documented as a top-level shortcut in 04-template-context.yml.
        # `total` is tasker-local convenience; not part of the canonical contract.
        context["index"] = getattr(job, "index", 0)
        context["total"] = len(all_jobs) if all_jobs else 1

        # S39 H4a: pull (or self-instantiate) the core render engine.
        engine = self._resolve_render_engine(services)

        # Execute tasks
        task_results = {}
        output_values = []

        for task in self.tasks:
            result = self._execute_task(
                task, context, engine,
                dry_run=dry_run, hardlink=hardlink,
            )
            if result:
                task_name = result.get('name', 'unnamed')
                task_results[task_name] = result

                # Collect save destinations
                if result.get('type') == 'save' and result.get('destination'):
                    output_values.append(result['destination'])

        if services.jobid:
            services.update_state({
                "jobs": {
                    services.jobid: {
                        "plugins": {
                            self.name: {
                                "tasks": task_results,
                                "output_values": output_values,
                            }
                        }
                    }
                }
            })

        return SDKPluginResult(
            success=True,
            data={
                'tasks': task_results,
                'values': output_values,
            },
            started_at=started_at,
            finished_at=datetime.now(),
        )

    @staticmethod
    def _resolve_render_engine(services: Any):
        """Return the shared engine, or create a local fallback.

        Plugin tests sometimes pass a Mock ``services`` whose
        ``render_engine`` attribute is itself a Mock. We detect that
        case and self-instantiate to keep behaviour consistent.
        """
        engine = getattr(services, "render_engine", None)
        # ``None`` and Mock objects without a real ``render_string``
        # method both fall back to a fresh engine.
        if engine is None or not hasattr(engine, "render_string") \
                or not callable(getattr(engine, "render_string", None)) \
                or type(engine).__name__ == "Mock":
            from archiverr.core.render import ConfigRenderEngine
            return ConfigRenderEngine()
        return engine

    @staticmethod
    def _run_and_jobs(services: Any) -> tuple[Any, list[Any]]:
        """Resolve run + jobs without the deleted S40 getters.

        Real PluginServices expose ``_state``. Test fixtures often only
        stub ``_state.run`` / ``_state.jobs``. Missing state is empty.
        """
        state = getattr(services, "_state", None)
        if state is None:
            return None, []
        run = getattr(state, "run", None)
        raw_jobs = getattr(state, "jobs", None)
        if raw_jobs is None:
            return run, []
        try:
            return run, list(raw_jobs)
        except TypeError:
            return run, []

    def _execute_task(
        self,
        task: dict[str, Any],
        context: dict[str, Any],
        engine: Any,
        *,
        dry_run: bool,
        hardlink: bool,
    ) -> dict[str, Any] | None:
        """Execute single task (print/save) against the rendered context."""
        task_name = task.get('name', 'unnamed')
        task_type = task.get('type', 'print')
        condition = task.get('condition')

        # Check condition via core engine.
        if condition and not engine.render_to_bool(condition, context):
            return None

        # Execute by type
        try:
            if task_type == 'print':
                return self._execute_print(task, context, engine, task_name)
            elif task_type == 'save':
                return self._execute_save(
                    task, context, engine, task_name,
                    dry_run=dry_run, hardlink=hardlink,
                )
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

    def _execute_print(
        self,
        task: dict[str, Any],
        context: dict[str, Any],
        engine: Any,
        task_name: str,
    ) -> dict[str, Any] | None:
        """Execute print task."""
        template = task.get('template', '')
        if not template:
            return None

        rendered = engine.render_string(template, context)
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
        engine: Any,
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

        destination = engine.render_string(destination_template, context)
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
