"""
PerRunPluginExecutor - Executes per_run plugins before stages.

Extracted from Orchestrator for Single Responsibility Principle.
"""

from typing import TYPE_CHECKING, Any

from archiverr.core.exceptions import PluginError

if TYPE_CHECKING:
    from archiverr.core.plugins.registry import PluginRegistry
    from archiverr.core.provides_registry import ProvidesRegistry
    from archiverr.events import EventBus
    from archiverr.state.manager import GlobalStateManager
    from archiverr.utils.debug import Debugger


class PerRunPluginExecutor:
    """Executes per_run mode plugins (input stage) before stage execution.

    SCOPE NOTE (S37 PASS 5): per_run plugins do NOT write to the
    plugin_executions recovery surface today. See
    datasets/11-recovery.yml#out_of_scope.per_run_plugin_executions —
    deliberate scope-out, slim contract = today's truth.
    """

    def __init__(
        self,
        state: 'GlobalStateManager',
        plugin_registry: 'PluginRegistry',
        event_bus: 'EventBus',
        config: dict[str, Any],
        debugger: 'Debugger' = None,
        provides_registry: 'ProvidesRegistry | None' = None,
        run_safety: dict[str, bool] | None = None,
    ):
        self._state = state
        self._plugin_registry = plugin_registry
        self._event_bus = event_bus
        self._config = config
        self._debugger = debugger
        self._provides_registry = provides_registry
        self._run_safety = run_safety

    def execute(self) -> dict[str, Any]:
        """
        Execute all per_run plugins.
        
        Returns:
            Dict with execution results {plugin_name: result}
        """
        from archiverr.core.services.plugin_services import PluginServices

        all_plugins = self._plugin_registry.get_all_plugins()
        per_run_plugins = []

        for plugin_name, plugin_instance in all_plugins.items():
            manifest = self._plugin_registry.get_manifest(plugin_name)
            self._log("debug", f"Checking {plugin_name}: run_mode={manifest.get('run_mode') if manifest else 'NO_MANIFEST'}")
            if manifest and manifest.get('run_mode') == 'per_run':
                per_run_plugins.append((plugin_name, plugin_instance))

        if not per_run_plugins:
            self._log("debug", "No per_run plugins to execute")
            return {}

        self._log("info", f"Executing {len(per_run_plugins)} per_run plugins")

        results = {}
        for plugin_name, plugin_instance in per_run_plugins:
            try:
                self._log("debug", f"Executing per_run plugin: {plugin_name}")

                services = PluginServices(
                    state=self._state,
                    event_bus=self._event_bus,
                    logger=self._debugger,
                    config=self._config,
                    mode="per_run",
                    current_plugin_name=plugin_name,
                    provides_registry=self._provides_registry,
                    run_safety=self._run_safety,
                )

                result = plugin_instance.execute_run(services)
                results[plugin_name] = result
                self._log("info", f"{plugin_name} completed: {result.get('count', 0)} jobs created")

            except PluginError as e:
                self._log("error", f"Per_run plugin {plugin_name} error: {e}")
                results[plugin_name] = {"success": False, "error": str(e)}
            except Exception as e:
                self._log("error", f"Per_run plugin {plugin_name} unexpected error: {e}")
                results[plugin_name] = {"success": False, "error": str(e)}

        return results

    def _log(self, level: str, message: str, **kwargs) -> None:
        """Log with debugger."""
        if self._debugger:
            log_func = getattr(self._debugger, level, self._debugger.info)
            log_func("per_run_executor", message, **kwargs)
