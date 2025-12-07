"""
Tasker Plugin - Output task execution

Session 11: Replaces core/tasks system with a proper plugin.

This plugin runs in the OUTPUT stage and:
- Renders Jinja2 templates with job context
- Executes print tasks (stdout output)
- Executes save tasks (file operations)
- Supports external task files (!include)
"""

import shutil
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from jinja2 import Environment, BaseLoader


class TaskerPlugin:
    """
    Output plugin for task execution.
    
    Replaces the TaskManager from core/tasks.
    Runs after all data plugins have completed.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize TaskerPlugin.
        
        Args:
            config: Plugin config from config.yml tasker section
        """
        self.config = config
        self.tasks = config.get('tasks', [])
        self.dry_run = config.get('dry_run', True)
        self.provides = config.get('provides', [])
        
        # Jinja2 environment
        self._env = Environment(loader=BaseLoader())
        
        # Alias support
        self._aliases: Dict[str, str] = {}
    
    def configure(self, global_config: Dict[str, Any]) -> None:
        """
        Configure with global config (for aliases).
        
        Args:
            global_config: Full config.yml content
        """
        self._aliases = global_config.get('aliases', {})
        
        # Override dry_run from global options if not set in plugin config
        if 'dry_run' not in self.config:
            self.dry_run = global_config.get('options', {}).get('dry_run', True)
    
    def process(self, match: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute tasks for a single job (legacy interface).
        
        Args:
            match: Match data with plugin results
            context: Optional execution context
            
        Returns:
            Plugin result with task outputs
        """
        # Build job context for templates
        job_context = self._build_job_context(match, context or {})
        
        # Execute all tasks
        results = []
        for task_config in self.tasks:
            result = self._execute_task(task_config, job_context)
            if result:
                results.append(result)
        
        return {
            'success': True,
            'tasks': {r['name']: r for r in results},
            'task_count': len(results),
            'values': self._extract_output_values(results)
        }
    
    def execute(self, job: Any, services: Any) -> Dict[str, Any]:
        """
        Execute tasks for a job (Session 11 signature).
        
        Args:
            job: JobState with input and plugins
            services: PluginServices
            
        Returns:
            Plugin result with task outputs
        """
        # Get plugin data from job.plugins (primary source)
        plugins_data = {}
        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            plugins_data = dict(job.plugins)  # Copy to avoid mutation
        
        # Fallback: try services.state for any missing plugins
        if hasattr(services, 'state'):
            for plugin_name in ['renamer', 'ffprobe', 'tmdb', 'tvdb']:
                if plugin_name not in plugins_data or not plugins_data.get(plugin_name):
                    try:
                        data = services.state.get_plugin_data(job.id, plugin_name)
                        if data:
                            plugins_data[plugin_name] = data
                    except Exception:
                        pass
        
        # Build match-like structure for template processing
        input_value = ''
        input_data = {}
        if hasattr(job, 'input'):
            if hasattr(job.input, 'value'):
                input_value = job.input.value
            elif hasattr(job.input, 'path'):
                input_value = job.input.path
            if hasattr(job.input, 'data'):
                input_data = job.input.data or {}
        elif hasattr(job, 'input_path'):
            input_value = job.input_path
        
        match = {
            'input': {
                'value': input_value,
                'path': input_value,
                'data': input_data
            },
            'plugins': plugins_data,
            'index': getattr(job, 'index', 0)
        }
        
        # Build context from services (P0.2: Add provides and events)
        config = {}
        if hasattr(services, 'config'):
            if hasattr(services.config, 'get_all'):
                config = services.config.get_all()
            elif hasattr(services.config, '_config'):
                config = services.config._config
        
        # P0.2: Get provides registry data for {{ provides.* }}
        provides_dict = {}
        if hasattr(services, 'provides') and hasattr(services.provides, 'get_all'):
            provides_dict = services.provides.get_all()
        
        # P0.2: Get event bus data for {{ events.* }}
        events_dict = {}
        if hasattr(services, 'events') and hasattr(services.events, '_event_bus'):
            event_bus = services.events._event_bus
            if hasattr(event_bus, 'get_history_dict'):
                events_dict = event_bus.get_history_dict()
        
        context = {
            'config': config,
            'provides': provides_dict,
            'events': events_dict
        }
        
        # Execute tasks
        result = self.process(match, context)
        
        # Fill job.output.values and job.output.data (Session 11 requirement)
        output_values = result.get('values', [])
        output_data = {'tasks': result.get('tasks', {})}
        
        if hasattr(job, 'output'):
            if hasattr(job.output, 'values'):
                job.output.values = output_values
            if hasattr(job.output, 'data'):
                job.output.data = output_data
        
        return result
    
    def _build_job_context(self, match: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build template context for job.
        
        Args:
            match: Match data
            context: Execution context
            
        Returns:
            Template context dict
        """
        plugins = match.get('plugins', {})
        input_data = match.get('input', {})
        
        # Base context (P0.2: Include provides and events)
        job_context = {
            'job': {
                'index': match.get('index', 0),
                'input': input_data,
                'plugins': plugins
            },
            'config': context.get('config', {}),
            'options': context.get('config', {}).get('options', {}),
            'provides': context.get('provides', {}),  # P0.2: Provides registry
            'events': context.get('events', {}),      # P0.2: Event bus history
            'index': match.get('index', 0)
        }
        
        # Add plugin data directly for easy access
        # {{ tmdb.movie.title }} instead of {{ job.plugins.tmdb.movie.title }}
        for plugin_name, plugin_data in plugins.items():
            job_context[plugin_name] = plugin_data
        
        # Add parsed shortcuts from renamer
        if 'renamer' in plugins:
            renamer = plugins['renamer']
            parsed = renamer.get('parsed', {})
            job_context['p'] = parsed
            job_context['movie'] = parsed.get('movie')
            job_context['show'] = parsed.get('show')
        
        # Add metadata shortcuts
        if 'tmdb' in plugins:
            tmdb = plugins['tmdb']
            job_context['m'] = tmdb.get('movie') or tmdb.get('show')
        
        # Add user aliases
        for alias, target in self._aliases.items():
            resolved = self._resolve_path(target, job_context)
            if resolved is not None:
                job_context[alias] = resolved
        
        return job_context
    
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
    
    def _execute_task(self, task_config: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute a single task.
        
        Args:
            task_config: Task configuration
            context: Template context
            
        Returns:
            Task result or None
        """
        task_name = task_config.get('name', 'unnamed')
        is_external = task_config.get('external', False)
        
        # Handle external task
        if is_external:
            return self._execute_external_task(task_config, context)
        
        task_type = task_config.get('type', 'print')
        condition = task_config.get('condition')
        
        # Check condition
        if condition:
            if not self._evaluate_condition(condition, context):
                return None
        
        # Execute based on type
        if task_type == 'print':
            return self._execute_print_task(task_name, task_config, context)
        elif task_type == 'save':
            return self._execute_save_task(task_name, task_config, context)
        
        return None
    
    def _execute_print_task(
        self, 
        name: str, 
        config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute print task."""
        template = config.get('template', '')
        
        if not template:
            return {'name': name, 'type': 'print', 'success': False, 'error': 'No template'}
        
        try:
            rendered = self._render_template(template, context)
            print(rendered)
            
            return {
                'name': name,
                'type': 'print',
                'success': True,
                'rendered': rendered
            }
        except Exception as e:
            return {
                'name': name,
                'type': 'print',
                'success': False,
                'error': str(e)
            }
    
    def _execute_save_task(
        self, 
        name: str, 
        config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute save task."""
        path_template = config.get('path') or config.get('destination', '')
        
        if not path_template:
            return {'name': name, 'type': 'save', 'success': False, 'error': 'No path'}
        
        try:
            destination = self._render_template(path_template, context)
            
            # Skip empty paths (conditional templates that don't apply)
            if not destination or not destination.strip():
                return None
            
            # Get source from input
            source = context.get('job', {}).get('input', {}).get('value', '')
            
            result = {
                'name': name,
                'type': 'save',
                'source': source,
                'destination': destination,
                'dry_run': self.dry_run
            }
            
            if not self.dry_run and source:
                try:
                    dest_path = Path(destination)
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                    result['success'] = True
                except Exception as e:
                    result['success'] = False
                    result['error'] = str(e)
            else:
                result['success'] = True
            
            return result
            
        except Exception as e:
            return {
                'name': name,
                'type': 'save',
                'success': False,
                'error': str(e)
            }
    
    def _execute_external_task(
        self, 
        task_config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Execute external task from file."""
        task_name = task_config.get('name', 'unnamed')
        task_path = task_config.get('path')
        
        if not task_path:
            return {'name': task_name, 'type': 'external', 'success': False, 'error': 'No path'}
        
        # Handle !include syntax
        if task_path.startswith('!include '):
            task_path = task_path[9:].strip()
        
        external_file = Path(task_path)
        
        if not external_file.exists():
            return {
                'name': task_name, 
                'type': 'external', 
                'success': False, 
                'error': f'File not found: {task_path}'
            }
        
        try:
            with open(external_file, 'r') as f:
                external_config = yaml.safe_load(f)
            
            if not external_config:
                return None
            
            # Single task or list of tasks
            if isinstance(external_config, dict):
                if 'name' not in external_config:
                    external_config['name'] = task_name
                return self._execute_task(external_config, context)
            elif isinstance(external_config, list):
                results = []
                for sub_task in external_config:
                    result = self._execute_task(sub_task, context)
                    if result:
                        results.append(result)
                return {
                    'name': task_name,
                    'type': 'external',
                    'success': True,
                    'tasks': results
                }
            
        except Exception as e:
            return {
                'name': task_name,
                'type': 'external',
                'success': False,
                'error': str(e)
            }
    
    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """Render Jinja2 template with context."""
        try:
            tmpl = self._env.from_string(template)
            return tmpl.render(**context)
        except Exception as e:
            return f"Template error: {e}"
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate Jinja2 condition."""
        if not condition:
            return True
        
        try:
            result = self._render_template(condition, context)
            return bool(result.strip()) and not result.startswith("Template error:")
        except Exception:
            return False
    
    def _extract_output_values(self, results: List[Dict[str, Any]]) -> List[str]:
        """Extract output file paths from task results."""
        values = []
        for result in results:
            if result.get('type') == 'save' and result.get('success'):
                dest = result.get('destination')
                if dest:
                    values.append(dest)
        return values
    
    @staticmethod
    def supports(parsed: Dict[str, Any]) -> bool:
        """Always supports - output plugin runs for all jobs."""
        return True
