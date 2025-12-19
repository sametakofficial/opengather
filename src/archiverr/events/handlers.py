"""
Event Handlers - Standard handlers for common use cases

These handlers can be subscribed to the event bus for:
- Debug logging
- Progress reporting
- Future: SignalR/WebSocket updates
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
    
    Usage:
        handler = ProgressHandler(total_matches=10)
        bus.subscribe(Events.MATCH_COMPLETED, handler)
        
        # Check progress
        print(f"Progress: {handler.completed}/{handler.total}")
    """

    def __init__(self, total_matches: int = 0, callback: Callable[[int, int], None] | None = None):
        """
        Args:
            total_matches: Expected total matches
            callback: Optional callback(completed, total) called on each progress update
        """
        self.total = total_matches
        self.completed = 0
        self.failed = 0
        self._callback = callback

    def set_total(self, total: int) -> None:
        """Update total count (useful when total not known at init)"""
        self.total = total

    def __call__(self, event: Event) -> None:
        """Handle match completion events"""
        if event.name == Events.MATCH_COMPLETED:
            self.completed += 1
            if self._callback:
                self._callback(self.completed, self.total)

        elif event.name == Events.MATCH_FAILED:
            self.completed += 1
            self.failed += 1
            if self._callback:
                self._callback(self.completed, self.total)

        elif event.name == Events.EXECUTION_STARTED:
            # Reset counters on new execution
            total_from_event = event.data.get('total_matches', 0)
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
        bus.subscribe(Events.MATCH_COMPLETED, handler)
    """

    def __init__(self, show_bar: bool = True):
        self._show_bar = show_bar
        self._total = 0
        self._completed = 0

    def __call__(self, event: Event) -> None:
        """Handle progress events"""
        if event.name == Events.EXECUTION_STARTED:
            self._total = event.data.get('total_matches', 0)
            self._completed = 0

        elif event.name in (Events.MATCH_COMPLETED, Events.MATCH_FAILED):
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
            bar = '█' * filled + '░' * (bar_width - filled)
            print(f"\rProgress: [{bar}] {self._completed}/{self._total} ({percent:.1f}%)",
                  end="", flush=True)

            # Newline on completion
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
            'execution_started': 0,
            'execution_completed': 0,
            'matches_started': 0,
            'matches_completed': 0,
            'matches_failed': 0,
            'plugins_completed': 0,
            'plugins_failed': 0,
            'plugins_skipped': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'db_syncs': 0,
            'db_errors': 0
        }
        self._plugin_times: dict = {}  # plugin_name -> [durations]

    def __call__(self, event: Event) -> None:
        """Collect statistics from events"""
        name = event.name

        if name == Events.EXECUTION_STARTED:
            self.stats['execution_started'] += 1
        elif name == Events.EXECUTION_COMPLETED:
            self.stats['execution_completed'] += 1
        elif name == Events.MATCH_STARTED:
            self.stats['matches_started'] += 1
        elif name == Events.MATCH_COMPLETED:
            self.stats['matches_completed'] += 1
        elif name == Events.MATCH_FAILED:
            self.stats['matches_failed'] += 1
        elif name == Events.PLUGIN_COMPLETED:
            self.stats['plugins_completed'] += 1
            # Track plugin durations
            plugin_name = event.data.get('plugin_name', 'unknown')
            duration = event.data.get('duration_ms', 0)
            if plugin_name not in self._plugin_times:
                self._plugin_times[plugin_name] = []
            self._plugin_times[plugin_name].append(duration)
        elif name == Events.PLUGIN_FAILED:
            self.stats['plugins_failed'] += 1
        elif name == Events.PLUGIN_SKIPPED:
            self.stats['plugins_skipped'] += 1
        elif name == Events.TASK_COMPLETED:
            self.stats['tasks_completed'] += 1
        elif name == Events.TASK_FAILED:
            self.stats['tasks_failed'] += 1
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
