"""
State Manager

Dependency-injected state management.
Write-through to persistence layer.
"""

from typing import Dict, Any, Optional, List, TYPE_CHECKING
from datetime import datetime
from uuid import uuid4

from .models import ExecutionState, MatchState, PluginResult, ExecutionStatus

# Lazy import to avoid circular dependency
if TYPE_CHECKING:
    from archiverr.events import EventBus


class StateManager:
    """
    State manager with dependency injection.
    
    Design Principles:
    - Plugin-agnostic: Core doesn't know plugin names or structures
    - Flat structure: No nested globals wrappers
    - Write-through: Every change persisted immediately (when persistence configured)
    - Dependency Injection: All dependencies passed via constructor
    
    Usage:
        # DI pattern (recommended)
        state = StateManager(
            persistence=persistence,
            debugger=debugger,
            event_bus=event_bus
        )
        
        exec_id = state.start_execution(config)
        match = state.register_match(0, "/path/to/file.mkv")
        state.update_plugin_result(0, "scanner", result)
        state.complete_match(0)
        state.complete_execution()
    """
    
    def __init__(
        self,
        persistence=None,
        debugger=None,
        event_bus: Optional['EventBus'] = None
    ):
        """
        Initialize state manager with dependencies.
        
        Args:
            persistence: Persistence layer (MockPersistence, PyMongoPersistence, etc.)
            debugger: Debug logger instance
            event_bus: EventBus for emitting state change events
        """
        # Dependencies
        self._persistence = persistence
        self._debugger = debugger
        self._event_bus = event_bus
        
        # State storage
        self._execution: Optional[ExecutionState] = None
        self._matches: Dict[int, MatchState] = {}
    
    def configure(
        self, 
        persistence=None,
        debugger=None,
        event_bus: Optional['EventBus'] = None
    ):
        """
        Reconfigure state manager with new dependencies.
        
        Provided for backward compatibility. Prefer constructor injection.
        
        Args:
            persistence: Persistence layer (MockPersistence or MongoDBPersistence)
            debugger: Debug logger instance
            event_bus: EventBus for emitting state change events
        """
        if persistence is not None:
            self._persistence = persistence
        if debugger is not None:
            self._debugger = debugger
        if event_bus is not None:
            self._event_bus = event_bus
    
    def reset(self):
        """Reset state for new execution (useful for testing)"""
        self._execution = None
        self._matches = {}
    
    def _emit(self, event_name: str, data: Dict[str, Any] = None, source: str = "state"):
        """Emit event if event bus is configured"""
        if self._event_bus:
            self._event_bus.emit(event_name, data or {}, source)
    
    # ==================== EXECUTION ====================
    
    def start_execution(self, config: Dict[str, Any]) -> str:
        """
        Start new execution.
        
        Args:
            config: Full config.yml content (stored as snapshot)
            
        Returns:
            Execution ID
        """
        execution_id = self._generate_id()
        
        self._execution = ExecutionState(
            id=execution_id,
            started_at=datetime.now(),
            status=ExecutionStatus.RUNNING,
            config_snapshot=self._create_config_snapshot(config)
        )
        
        # Persist
        if self._persistence:
            self._persistence.save_execution(self._execution)
        
        self._log("debug", "execution", "Started execution", id=execution_id)
        
        # Emit event
        self._emit("execution.started", {
            "execution_id": execution_id,
            "config_keys": list(config.keys())
        })
        
        return execution_id
    
    def complete_execution(self, branch_name: str = "main") -> ExecutionState:
        """
        Complete current execution and create commit.
        
        Args:
            branch_name: Branch to commit to (default: "main")
        
        Returns:
            Final execution state
        """
        if not self._execution:
            raise RuntimeError("No active execution")
        
        self._execution.finished_at = datetime.now()
        self._execution.duration_ms = int(
            (self._execution.finished_at - self._execution.started_at).total_seconds() * 1000
        )
        self._execution.status = ExecutionStatus.COMPLETED
        self._execution.success = self._execution.failed_matches == 0
        
        # Persist execution
        if self._persistence:
            self._persistence.save_execution(self._execution)
            
            # Create branch if needed and commit
            self._create_commit(branch_name)
        
        self._log("info", "execution", "Execution completed",
                 matches=self._execution.total_matches,
                 errors=self._execution.failed_matches,
                 duration_ms=self._execution.duration_ms)
        
        # Emit event
        self._emit("execution.completed", {
            "execution_id": self._execution.id,
            "total_matches": self._execution.total_matches,
            "completed_matches": self._execution.completed_matches,
            "failed_matches": self._execution.failed_matches,
            "duration_ms": self._execution.duration_ms,
            "success": self._execution.success
        })
        
        return self._execution
    
    def _create_commit(self, branch_name: str = "main"):
        """
        Create branch (if needed) and commit for current execution.
        
        This implements git-like versioning:
        - Each execution becomes a commit
        - Commits are linked to branches
        - Default branch is "main"
        """
        if not self._persistence or not self._execution:
            return
        
        # Check if persistence supports versioning
        if not hasattr(self._persistence, 'create_branch'):
            self._log("debug", "state", "Persistence does not support versioning")
            return
        
        try:
            # Get or create branch (use name= keyword argument!)
            branch = self._persistence.get_branch(name=branch_name)
            
            if not branch:
                # Create branch
                branch = self._persistence.create_branch(
                    name=branch_name,
                    description=f"Default branch" if branch_name == "main" else f"Branch: {branch_name}",
                    is_default=(branch_name == "main")
                )
                self._log("info", "state", f"Created branch", branch=branch_name)
            else:
                self._log("debug", "state", f"Using existing branch", branch=branch_name)
            
            # Create commit
            branch_id = branch.get("_id")
            
            commit = self._persistence.create_commit(
                branch_id=branch_id,
                execution_id=self._execution.id,
                message=f"Execution {self._execution.id}: {self._execution.total_matches} matches",
                metadata={
                    "success": self._execution.success,
                    "total_matches": self._execution.total_matches,
                    "completed_matches": self._execution.completed_matches,
                    "failed_matches": self._execution.failed_matches,
                    "duration_ms": self._execution.duration_ms
                }
            )
            
            commit_id = commit.get("_id", "unknown")
            self._log("info", "state", f"Created commit", 
                     commit=commit_id, branch=branch_name)
            
        except Exception as e:
            self._log("warn", "state", f"Failed to create commit: {e}")
    
    @property
    def execution(self) -> Optional[ExecutionState]:
        """Get current execution state"""
        return self._execution
    
    @property
    def execution_id(self) -> Optional[str]:
        """Get current execution ID"""
        return self._execution.id if self._execution else None
    
    # ==================== MATCHES ====================
    
    def register_match(self, index: int, input_path: str) -> MatchState:
        """
        Register new match for processing.
        
        Args:
            index: Match index (0-based)
            input_path: Input file path
            
        Returns:
            MatchState object
        """
        if not self._execution:
            raise RuntimeError("No active execution")
        
        match = MatchState(
            index=index,
            input_path=input_path,
            execution_id=self._execution.id,
            started_at=datetime.now(),
            status=ExecutionStatus.RUNNING
        )
        
        self._matches[index] = match
        self._execution.total_matches = len(self._matches)
        
        # Persist
        if self._persistence:
            self._persistence.save_match(match)
            self._persistence.save_execution(self._execution)
        
        self._log("debug", "match", f"Registered match {index}", input_path=input_path)
        
        # Emit event
        self._emit("match.started", {
            "index": index,
            "input_path": input_path,
            "execution_id": self._execution.id
        })
        
        return match
    
    def get_match(self, index: int) -> Optional[MatchState]:
        """Get match by index"""
        return self._matches.get(index)
    
    def get_all_matches(self) -> Dict[int, MatchState]:
        """Get all matches"""
        return self._matches.copy()
    
    def update_plugin_result(
        self, 
        match_index: int, 
        plugin_name: str, 
        result: PluginResult
    ):
        """
        Update plugin result for a match.
        
        Args:
            match_index: Match index
            plugin_name: Plugin name (core doesn't validate this)
            result: PluginResult object
        """
        match = self._matches.get(match_index)
        if not match:
            raise ValueError(f"Match {match_index} not found")
        
        match.add_plugin_result(plugin_name, result)
        
        # Persist
        if self._persistence:
            self._persistence.save_plugin_result(
                self._execution.id,
                match_index,
                plugin_name,
                result.to_dict()
            )
        
        self._log("debug", "plugin", f"Plugin {plugin_name} completed for match {match_index}",
                 success=result.success)
        
        # Emit event
        event_name = "plugin.completed" if result.success else "plugin.failed"
        self._emit(event_name, {
            "match_index": match_index,
            "plugin_name": plugin_name,
            "success": result.success,
            "duration_ms": result.duration_ms,
            "error": result.error
        })
    
    def mark_plugin_not_supported(self, match_index: int, plugin_name: str):
        """Mark plugin as not supported for this match"""
        match = self._matches.get(match_index)
        if match:
            match.add_not_supported(plugin_name)
            
            # Emit event
            self._emit("plugin.skipped", {
                "match_index": match_index,
                "plugin_name": plugin_name,
                "reason": "not_supported"
            })
    
    def add_task_result(self, match_index: int, task_result: Dict[str, Any]):
        """Add task execution result to match"""
        match = self._matches.get(match_index)
        if match:
            match.add_task_result(task_result)
            
            # Persist
            if self._persistence:
                self._persistence.save_match(match)
    
    def complete_match(self, match_index: int):
        """
        Mark match as completed.
        
        Args:
            match_index: Match index
        """
        match = self._matches.get(match_index)
        if not match:
            raise ValueError(f"Match {match_index} not found")
        
        match.complete()
        
        # Update execution stats
        self._execution.completed_matches += 1
        if not match.success:
            self._execution.failed_matches += 1
        
        # Persist
        if self._persistence:
            self._persistence.save_match(match)
            self._persistence.save_execution(self._execution)
        
        self._log("debug", "match", f"Match {match_index} completed",
                 success=match.success, duration_ms=match.duration_ms)
        
        # Emit event
        event_name = "match.completed" if match.success else "match.failed"
        self._emit(event_name, {
            "index": match_index,
            "success": match.success,
            "duration_ms": match.duration_ms,
            "executed_plugins": match.executed_plugins,
            "failed_plugins": match.failed_plugins
        })
    
    # ==================== TEMPLATE CONTEXT ====================
    
    def build_template_context(self, match_index: int) -> Dict[str, Any]:
        """
        Build Jinja2 template context from state.
        
        This replaces the temp_api_response rebuild pattern!
        Context structure matches existing config.yml templates.
        
        Args:
            match_index: Current match index
            
        Returns:
            Template context dict
        """
        match = self._matches.get(match_index)
        if not match:
            return {}
        
        # Build globals (for {{ globals.status.matches }} etc.)
        globals_context = {
            "status": {
                "success": self._execution.success if self._execution else True,
                "matches": self._execution.total_matches if self._execution else 0,
                "completed": self._execution.completed_matches if self._execution else 0,
                "errors": self._execution.failed_matches if self._execution else 0
            },
            "summary": {
                "total_matches": self._execution.total_matches if self._execution else 0,
                "completed_matches": self._execution.completed_matches if self._execution else 0,
                "failed_matches": self._execution.failed_matches if self._execution else 0
            },
            "config": self._execution.config_snapshot if self._execution else {}
        }
        
        # Build match_globals (for {{ match_globals.input.path }} etc.)
        match_globals = {
            "index": match.index,
            "input": {
                "path": match.input_path,
                # Category from scanner/file_reader plugin if available
                "category": self._get_match_category(match)
            },
            "status": {
                "success": match.success,
                "executed_plugins": match.executed_plugins,
                "failed_plugins": match.failed_plugins
            }
        }
        
        # Build context
        context = {
            # Global access
            "globals": globals_context,
            
            # Match globals access
            "match_globals": match_globals,
            
            # Shorthand: {{ index }}
            "index": match.index,
            
            # Execution shorthand
            "execution": {
                "id": self._execution.id if self._execution else None,
                "started_at": self._execution.started_at.isoformat() if self._execution and self._execution.started_at else None
            },
            
            # Match shorthand
            "match": {
                "index": match.index,
                "input_path": match.input_path,
                "success": match.success,
                "plugins": match.plugins
            },
            
            # All matches for indexed access: {{ matches[0].plugins.tmdb.movie.title }}
            "matches": [
                {
                    "index": m.index,
                    "input_path": m.input_path,
                    "success": m.success,
                    "plugins": m.plugins
                }
                for m in sorted(self._matches.values(), key=lambda x: x.index)
            ]
        }
        
        # Plugin data flat access: {{ renamer.parsed.movie.name }}
        # This is what makes templates work without knowing full path
        for plugin_name, plugin_data in match.plugins.items():
            context[plugin_name] = plugin_data
        
        return context
    
    # ==================== API RESPONSE BUILD ====================
    
    def build_api_response_for_templates(self) -> Dict[str, Any]:
        """
        Build lightweight API response structure for template rendering.
        
        This is a fast alternative to builder.build() that uses in-memory state.
        Returns same structure as API response, but built from state directly.
        
        Use this for task execution during match processing.
        Use builder.build() only for final report generation.
        
        Returns:
            API response-like dict suitable for template_manager.render()
        """
        matches = []
        for idx in sorted(self._matches.keys()):
            match = self._matches[idx]
            matches.append({
                'globals': {
                    'index': match.index,
                    'input_path': match.input_path,
                    'status': {
                        'success': match.success,
                        'success_plugins': match.executed_plugins,
                        'failed_plugins': match.failed_plugins,
                        'not_supported_plugins': match.not_supported_plugins,
                        'started_at': match.started_at.isoformat() if match.started_at else None,
                        'finished_at': match.finished_at.isoformat() if match.finished_at else None,
                        'duration_ms': match.duration_ms
                    },
                    'output': {
                        'tasks': match.tasks
                    }
                },
                'plugins': match.plugins
            })
        
        return {
            'globals': {
                'status': {
                    'success': self._execution.success if self._execution else True,
                    'matches': self._execution.total_matches if self._execution else 0,
                    'completed': self._execution.completed_matches if self._execution else 0,
                    'errors': self._execution.failed_matches if self._execution else 0,
                    'started_at': self._execution.started_at.isoformat() if self._execution and self._execution.started_at else None,
                    'execution_id': self._execution.id if self._execution else None
                },
                'config': self._execution.config_snapshot if self._execution else {}
            },
            'matches': matches
        }
    
    # ==================== PRIVATE HELPERS ====================
    
    def _generate_id(self) -> str:
        """Generate unique ID"""
        return str(uuid4())[:8]
    
    def _create_config_snapshot(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create FULL config snapshot with masked sensitive values.
        
        - Stores complete plugin configurations
        - API keys stored as ${ENV_VAR} syntax, not actual values
        - Full reproducibility: snapshot + .env = same execution
        """
        from archiverr.utils.config_loader import create_config_snapshot, get_tracked_original
        
        # Get original config with ${ENV_VAR} syntax
        original_config = get_tracked_original()
        
        # Create snapshot with masked sensitive values
        return create_config_snapshot(config, original_config)
    
    def _get_match_category(self, match: MatchState) -> str:
        """
        Get category from any input plugin result.
        
        Plugin-agnostic: Searches all plugin results for a 'category' field
        instead of hardcoding specific plugin names.
        
        Args:
            match: MatchState with plugin results
            
        Returns:
            Category string or "unknown" if not found
        """
        # Generic: find category from any plugin that provides it
        for plugin_name, plugin_data in match.plugins.items():
            if isinstance(plugin_data, dict) and "category" in plugin_data:
                return plugin_data.get("category", "unknown")
        return "unknown"
    
    def _log(self, level: str, component: str, message: str, **kwargs):
        """Log if debugger available"""
        if self._debugger:
            log_func = getattr(self._debugger, level, self._debugger.debug)
            log_func(component, message, **kwargs)


# Backward compatibility alias
# DEPRECATED: Use StateManager with DI instead
GlobalStateManager = StateManager
