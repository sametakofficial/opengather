"""
Scanner Plugin - File/Directory Discovery

Session 11 - INPUT stage plugin (per_run mode).
Creates jobs via services.state.create_job() with proper input.value/input.data structure.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import os
from archiverr.core.plugins.sdk import InputPlugin


class ScannerPlugin(InputPlugin):
    """
    Input plugin that discovers media files from configured targets.
    
    Session 11 - Stage: INPUT, Mode: per_run
    
    Provides:
    - job.create: Creates jobs for each discovered file
    - fs.read: Reads filesystem to discover files
    - input.value: Sets job input path
    - input.data: Sets job input metadata
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "scanner"
    
    def execute_run(self, services: Any) -> Dict[str, Any]:
        """
        Execute scanner in per_run mode (Session 11).
        
        Discovers files and creates jobs via services.state.create_job().
        
        Args:
            services: PluginServices with state, events, logger, config
            
        Returns:
            PluginResult-like dict with count of created jobs
        """
        targets = self.config.get('targets', [])
        recursive = self.config.get('recursive', True)
        allow_virtual = self.config.get('allow_virtual_paths', False)
        
        self.debug("Starting scan (per_run mode)", targets=len(targets), recursive=recursive)
        
        created_jobs = 0
        
        for target in targets:
            # Skip .txt files (handled by file_reader)
            if target.endswith('.txt'):
                continue
            
            target_path = Path(target)
            
            # Direct file
            if target_path.is_file():
                self._create_job_for_file(services, target_path)
                created_jobs += 1
            
            # Directory scanning
            elif target_path.is_dir() and recursive:
                for ext in ['.mkv', '.mp4', '.avi', '.m4v', '.ts']:
                    for file in target_path.rglob(f'*{ext}'):
                        if file.is_file():
                            self._create_job_for_file(services, file)
                            created_jobs += 1
            
            # Virtual path support
            elif allow_virtual and not target_path.exists():
                self.debug("Virtual path detected", path=target)
                self._create_job_for_virtual(services, target)
                created_jobs += 1
        
        self.info("Scan complete (per_run)", jobs_created=created_jobs)
        
        return {
            'status': {'success': True},
            'data': {'count': created_jobs}
        }
    
    def _create_job_for_file(self, services: Any, file_path: Path) -> None:
        """
        Create a job for a file with proper input.value and input.data.
        
        Session 11 format:
        - input.value: Full file path
        - input.data: {filename, extension, size_bytes, modified_at, source}
        """
        # Build input.data with file metadata
        stat = file_path.stat()
        input_data = {
            'filename': file_path.name,
            'extension': file_path.suffix.lstrip('.'),
            'size_bytes': stat.st_size,
            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'source': 'filesystem'
        }
        
        # Session 12: Create job via PluginServices
        if hasattr(services, 'createJob'):
            services.createJob(
                input_value=str(file_path),
                input_data=input_data
            )
        elif hasattr(services, 'state') and hasattr(services.state, 'create_job'):
            # Legacy fallback
            services.state.create_job(
                input_value=str(file_path),
                input_data=input_data
            )
        else:
            self.debug("No job creation method available", path=str(file_path))
    
    def _create_job_for_virtual(self, services: Any, path: str) -> None:
        """Create a job for a virtual path."""
        input_data = {
            'filename': Path(path).name,
            'extension': Path(path).suffix.lstrip('.') if '.' in path else '',
            'size_bytes': 0,
            'modified_at': None,
            'source': 'virtual'
        }
        
        # Session 12: Create job via PluginServices
        if hasattr(services, 'createJob'):
            services.createJob(
                input_value=path,
                input_data=input_data
            )
        elif hasattr(services, 'state') and hasattr(services.state, 'create_job'):
            # Legacy fallback
            services.state.create_job(
                input_value=path,
                input_data=input_data
            )
    
    def execute(self, match_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Legacy execute method for backward compatibility.
        
        Returns list of matches in old format for existing executor.
        """
        return self.get_matches()
    
    def get_matches(self) -> List[Dict[str, Any]]:
        """
        Legacy method - returns matches in old format.
        
        Used by existing PluginExecutor.execute_input_plugins()
        """
        targets = self.config.get('targets', [])
        recursive = self.config.get('recursive', True)
        allow_virtual = self.config.get('allow_virtual_paths', False)
        
        self.debug("Starting scan (legacy mode)", targets=len(targets))
        
        results = []
        
        for target in targets:
            if target.endswith('.txt'):
                continue
            
            target_path = Path(target)
            
            if target_path.is_file():
                results.append(self._build_match(target_path))
            
            elif target_path.is_dir() and recursive:
                for ext in ['.mkv', '.mp4', '.avi', '.m4v', '.ts']:
                    for file in target_path.rglob(f'*{ext}'):
                        if file.is_file():
                            results.append(self._build_match(file))
            
            elif allow_virtual and not target_path.exists():
                results.append(self._build_virtual_match(target))
        
        self.info("Scan complete", found=len(results))
        return results
    
    def _build_match(self, file_path: Path) -> Dict[str, Any]:
        """Build match dict with Session 11 input format."""
        stat = file_path.stat()
        return {
            'status': {'success': True},
            'input': {
                'value': str(file_path),  # Session 11: value instead of path
                'path': str(file_path),   # Legacy: keep for backward compat
                'data': {
                    'filename': file_path.name,
                    'extension': file_path.suffix.lstrip('.'),
                    'size_bytes': stat.st_size,
                    'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'source': 'filesystem'
                }
            }
        }
    
    def _build_virtual_match(self, path: str) -> Dict[str, Any]:
        """Build match dict for virtual path."""
        return {
            'status': {'success': True},
            'input': {
                'value': path,
                'path': path,
                'data': {
                    'filename': Path(path).name,
                    'extension': Path(path).suffix.lstrip('.') if '.' in path else '',
                    'size_bytes': 0,
                    'modified_at': None,
                    'source': 'virtual'
                }
            }
        }
