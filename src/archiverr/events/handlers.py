"""
Event Handlers - Standard handlers for common use cases

These handlers can be subscribed to the event bus for:
- Debug logging
- Progress reporting
- Statistics collection
"""

from collections.abc import Callable

from .bus import Event, Events


class DebugHandler:
    """
    Handler that logs all events to debugger.

    Usage:
        handler = DebugHandler(debugger)
        bus.subscribe("*", handler)
    """

    def __init__(self, debugger):
        self._debugger = debugger

    def __call__(self, event: Event) -> None:
        """Log event to debugger"""
        self._debugger.debug("event", event.name,
                           source=event.source,
                           **{k: str(v)[:50] for k, v in event.data.items()})


class ProgressHandler:
    """
    Handler that tracks and reports progress.

    Tracks plugin completions per job to calculate overall progress.

    Usage:
        handler = ProgressHandler(total_jobs=10)
        bus.subscribe(Events.PLUGIN_COMPLETED, handler)
        bus.subscribe(Events.PLUGIN_FAILED, handler)
        bus.subscribe(Events.RUN_STARTED, handler)
    """

    def __init__(self, total_jobs: int = 0, callback: Callable[[int, int], None] | None = None):
        self.total = total_jobs
        self.completed = 0
        self.failed = 0
        self._callback = callback

    def set_total(self, total: int) -> None:
        """Update total count (useful when total not known at init)"""
        self.total = total

    def __call__(self, event: Event) -> None:
        """Handle plugin completion events"""
        if event.name == Events.PLUGIN_COMPLETED:
            self.completed += 1
            if self._callback:
                self._callback(self.completed, self.total)

        elif event.name == Events.PLUGIN_FAILED:
            self.completed += 1
            self.failed += 1
            if self._callback:
                self._callback(self.completed, self.total)

        elif event.name == Events.RUN_STARTED:
            total_from_event = event.data.get('total_jobs', 0)
            if total_from_event:
                self.total = total_from_event
            self.completed = 0
            self.failed = 0

    @property
    def progress_percent(self) -> float:
        """Get progress as percentage"""
        if self.total == 0:
            return 0.0
        return (self.completed / self.total) * 100

    @property
    def success_rate(self) -> float:
        """Get success rate as percentage"""
        if self.completed == 0:
            return 100.0
        return ((self.completed - self.failed) / self.completed) * 100


class ConsoleProgressHandler:
    """
    Handler that prints progress to console.

    Usage:
        handler = ConsoleProgressHandler()
        bus.subscribe(Events.PLUGIN_COMPLETED, handler)
        bus.subscribe(Events.PLUGIN_FAILED, handler)
        bus.subscribe(Events.RUN_STARTED, handler)
    """

    def __init__(self, show_bar: bool = True):
        self._show_bar = show_bar
        self._total = 0
        self._completed = 0

    def __call__(self, event: Event) -> None:
        """Handle progress events"""
        if event.name == Events.RUN_STARTED:
            self._total = event.data.get('total_jobs', 0)
            self._completed = 0

        elif event.name in (Events.PLUGIN_COMPLETED, Events.PLUGIN_FAILED):
            self._completed += 1
            self._print_progress()

    def _print_progress(self) -> None:
        """Print progress bar or simple text"""
        if self._total == 0:
            return

        percent = (self._completed / self._total) * 100

        if self._show_bar:
            bar_width = 40
            filled = int(bar_width * self._completed / self._total)
            bar = '#' * filled + '-' * (bar_width - filled)
            print(f"\rProgress: [{bar}] {self._completed}/{self._total} ({percent:.1f}%)",
                  end="", flush=True)

            if self._completed >= self._total:
                print()
        else:
            print(f"\rProgress: {self._completed}/{self._total} ({percent:.1f}%)",
                  end="", flush=True)


class StatisticsHandler:
    """
    Handler that collects execution statistics.

    Usage:
        handler = StatisticsHandler()
        bus.subscribe("*", handler)

        # After execution
        print(handler.get_summary())
    """

    def __init__(self):
        self.stats = {
            'runs_started': 0,
            'runs_completed': 0,
            'stages_completed': 0,
            'stages_failed': 0,
            'plugins_completed': 0,
            'plugins_failed': 0,
            'plugins_skipped': 0,
            'db_syncs': 0,
            'db_errors': 0,
        }
        self._plugin_times: dict = {}

    def __call__(self, event: Event) -> None:
        """Collect statistics from events"""
        name = event.name

        if name == Events.RUN_STARTED:
            self.stats['runs_started'] += 1
        elif name == Events.RUN_COMPLETED:
            self.stats['runs_completed'] += 1
        elif name == Events.STAGE_COMPLETED:
            self.stats['stages_completed'] += 1
        elif name == Events.STAGE_FAILED:
            self.stats['stages_failed'] += 1
        elif name == Events.PLUGIN_COMPLETED:
            self.stats['plugins_completed'] += 1
            plugin_name = event.data.get('plugin_name', 'unknown')
            duration = event.data.get('duration_ms', 0)
            if plugin_name not in self._plugin_times:
                self._plugin_times[plugin_name] = []
            self._plugin_times[plugin_name].append(duration)
        elif name == Events.PLUGIN_FAILED:
            self.stats['plugins_failed'] += 1
        elif name == Events.PLUGIN_SKIPPED:
            self.stats['plugins_skipped'] += 1
        elif name == Events.DB_SYNCED:
            self.stats['db_syncs'] += 1
        elif name == Events.DB_ERROR:
            self.stats['db_errors'] += 1

    def get_summary(self) -> dict:
        """Get summary statistics"""
        return {
            **self.stats,
            'plugin_avg_times': {
                name: sum(times) / len(times) if times else 0
                for name, times in self._plugin_times.items()
            }
        }

    def reset(self) -> None:
        """Reset all statistics"""
        for key in self.stats:
            self.stats[key] = 0
        self._plugin_times = {}
