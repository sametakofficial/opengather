"""
Tasker Plugin - Session 12 with Main Branch Template Logic

Combines:
- Session 12 plugin architecture (per_run, stages, state)
- Main branch template rendering (Jinja2, $ syntax, smart routing)
"""

import json
import shutil
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from jinja2 import Environment, BaseLoader, TemplateError


class TaskerPlugin:
    """Task execution plugin with full Jinja2 + state access."""
    
    # Template function patterns (from main branch)
    _FUNCTION_PATTERN = re.compile(r'\b(index|count):([a-zA-Z0-9_.\[\]]*)')
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tasks = config.get('tasks', [])
        self.dry_run = config.get('dry_run', True)
        self.save_output = config.get('save_output', True)
        self.output_dir = config.get('output_dir', 'output')
        
        # Jinja2 environment
        self.env = Environment(loader=BaseLoader())
        self.env.filters['truncate'] = self._filter_truncate
        self.env.filters['format'] = lambda fmt, *args: fmt % args
        
        # Run output tracking
        self._run_output: Dict[str, Any] = {}
    
    def configure(self, global_config: Dict[str, Any]) -> None:
        """Configure with global config."""
        if 'dry_run' not in self.config:
            self.dry_run = global_config.get('options', {}).get('dry_run', True)
    
    def debug(self, msg: str, **kwargs):
        """Debug logging."""
        pass  # Plugin SDK will provide this
    
    def warn(self, msg: str, **kwargs):
        """Warning logging."""
        pass
    
    def error(self, msg: str, **kwargs):
        """Error logging."""
        print(f"ERROR: {msg}", kwargs)
    
    def execute(self, job: Any, services: Any) -> Dict[str, Any]:
        """
        Execute tasks for job (Session 12 interface).
        
        Args:
            job: JobState with input, plugins
            services: PluginServices with state access
            
        Returns:
            PluginResult compatible dict
        """
        started_at = datetime.now()
        
        # Get plugin data from job
        plugins_data = {}
        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            plugins_data = dict(job.plugins)
        
        # Fallback: services.state - get ALL plugin data dynamically
        if hasattr(services, 'state'):
            # Get all plugins that have data for this job (NO HARDCODING)
            available_plugins = services.state.get_job_plugin_names(job.id)
            for plugin_name in available_plugins:
                if plugin_name not in plugins_data:
                    try:
                        data = services.state.get_plugin_data(job.id, plugin_name)
                        if data:
                            plugins_data[plugin_name] = data
                    except Exception:
                        pass
        
        # Build template context (Main branch style)
        context = self._build_context(job, plugins_data, services)
        
        # Execute tasks
        task_results = {}
        output_values = []
        
        for task in self.tasks:
            result = self._execute_task(task, context, job)
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
        
        return {
            'success': True,
            'tasks': task_results,
            'values': output_values,
            'duration_ms': int((datetime.now() - started_at).total_seconds() * 1000)
        }
    
    def _build_context(self, job: Any, plugins_data: Dict[str, Any], services: Any) -> Dict[str, Any]:
        """
        Build Jinja2 context (Main branch pattern adapted to Session 12).
        
        Context includes:
        - plugin.{name}.data.* - Plugin data (Session 12 format)
        - job.* - Job data
        - config.* - Global config (via services.state)
        - index, total - Job index and total
        """
        # Get job index
        job_index = getattr(job, 'index', 0)
        
        # Build context
        context = {
            'job': {
                'id': getattr(job, 'id', 'unknown'),
                'index': job_index,
                'input': {
                    'value': getattr(job.input, 'value', '') if hasattr(job, 'input') else '',
                    'data': getattr(job.input, 'data', {}) if hasattr(job, 'input') else {}
                }
            },
            'index': job_index,
            'total': 1,  # Single job execution
        }
        
        # Session 17: Flat plugin data structure
        # - plugin.{name}.* (direct access, no 'data' wrapper)
        # - Also add plugin.{name}.data.* for backward compat with templates
        context['plugin'] = {}
        for plugin_name, plugin_info in plugins_data.items():
            if isinstance(plugin_info, dict):
                # Session 17: Flat structure - data is directly in plugin_info
                # Skip 'status' key if present (legacy cleanup)
                flat_data = {k: v for k, v in plugin_info.items() if k != 'status'}
                
                # Store in plugin.{name} for direct access
                context['plugin'][plugin_name] = flat_data
                
                # Also add plugin.{name}.data.* wrapper for backward compat with old templates
                context['plugin'][plugin_name]['data'] = flat_data
                
                # Add direct access at top level for convenience
                context[plugin_name] = flat_data
        
        # Add config access (if services has state)
        if hasattr(services, 'state'):
            try:
                config_state = services.state.get_config() if hasattr(services.state, 'get_config') else {}
                context['config'] = config_state
            except Exception:
                context['config'] = {}
        
        # Add renamer shortcuts for template compatibility
        if 'renamer' in plugins_data:
            # Session 17: Flat structure - parsed is directly in renamer data
            renamer_data = plugins_data['renamer'] if isinstance(plugins_data['renamer'], dict) else {}
            parsed = renamer_data.get('parsed', {})
            category = renamer_data.get('category', 'unknown')
            
            context['renamer'] = renamer_data
            if category == 'movie' and 'movie' in parsed:
                context['movie'] = parsed['movie']
            elif category == 'show' and 'show' in parsed:
                context['show'] = parsed['show']
        
        return context
    
    def _execute_task(self, task: Dict[str, Any], context: Dict[str, Any], job: Any) -> Optional[Dict[str, Any]]:
        """
        Execute single task (Main branch pattern).
        
        Args:
            task: Task config
            context: Template context
            job: Job data
            
        Returns:
            Task result or None
        """
        task_name = task.get('name', 'unnamed')
        task_type = task.get('type', 'print')
        condition = task.get('condition')
        
        # Check condition
        if condition:
            if not self._evaluate_condition(condition, context):
                return None
        
        # Execute by type
        try:
            if task_type == 'print':
                return self._execute_print(task, context, task_name)
            elif task_type == 'save':
                return self._execute_save(task, context, job, task_name)
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
    
    def _execute_print(self, task: Dict[str, Any], context: Dict[str, Any], task_name: str) -> Optional[Dict[str, Any]]:
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
    
    def _execute_save(self, task: Dict[str, Any], context: Dict[str, Any], job: Any, task_name: str) -> Optional[Dict[str, Any]]:
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
        
        success = False
        if not self.dry_run:
            try:
                dest_path = Path(destination)
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                success = True
            except Exception:
                success = False
        else:
            success = True
        
        return {
            'name': task_name,
            'type': 'save',
            'success': success,
            'source': source,
            'destination': destination,
            'dry_run': self.dry_run
        }
    
    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """
        Render Jinja2 template (Main branch logic).
        
        Supports:
        - {{ plugin.tmdb.data.movie.title }}
        - {{ renamer.parsed.movie.name }}
        - {% if movie %}...{% endif %}
        - Template functions: index:, count:
        - Error handling: Returns template error message on failure
        """
        try:
            # Process template functions (index:, count:)
            processed = self._process_functions(template, context)
            
            # Render with Jinja2
            tmpl = self.env.from_string(processed)
            result = tmpl.render(**context)
            return result
        except Exception as e:
            # Main branch pattern: Return error message but don't crash
            error_msg = str(e)
            # Extract meaningful part of error
            if "has no attribute" in error_msg:
                return f""  # Silent fail for missing attributes (like main branch)
            return f"Template error: {error_msg}"
    
    def _process_functions(self, template: str, context: Dict[str, Any]) -> str:
        """
        Process template functions (Main branch).
        
        - index: → current index
        - count:matches → not applicable in Session 12 (single job)
        - count:plugin.tmdb.data.movie.genres → count list items
        """
        def replacer(match):
            func_name = match.group(1)
            func_arg = match.group(2) if match.lastindex >= 2 else ''
            
            if func_name == 'index':
                return str(context.get('index', 0))
            
            elif func_name == 'count':
                if not func_arg:
                    return '0'
                
                # Resolve path and count
                try:
                    value = self._resolve_path(func_arg, context)
                    if isinstance(value, (list, dict)):
                        return str(len(value))
                    return '0'
                except Exception:
                    return '0'
            
            return match.group(0)
        
        return self._FUNCTION_PATTERN.sub(replacer, template)
    
    def _resolve_path(self, path: str, context: Dict[str, Any]) -> Any:
        """Resolve dot-notation path in context."""
        parts = path.split('.')
        current = context
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return None
            else:
                return None
        
        return current
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
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
    
    def _track_run_output(self, job: Any, task_results: Dict[str, Any], plugins_data: Dict[str, Any]) -> None:
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
    
    def save_run_output(self, run_id: str) -> Optional[str]:
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
            
            print(f"\n✓ Run output saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            print(f"\n✗ Failed to save run output: {e}")
            return None


# Plugin result helper for Session 12
class PluginResult:
    @staticmethod
    def success_result(data: Dict[str, Any], started_at: datetime = None) -> Dict[str, Any]:
        return {
            'success': True,
            'data': data,
            'duration_ms': int((datetime.now() - started_at).total_seconds() * 1000) if started_at else 0
        }
