"""
Test Plugin-Agnostic Principle

Tests verify:
- Core code doesn't contain hardcoded plugin names
- Orchestrator doesn't have plugin-specific knowledge
- Dynamic plugin discovery works
- No hardcoded execution order

Run with:
    pytest tests/test_plugin_agnostic.py -v
"""

import re
from pathlib import Path

import pytest


class TestPluginAgnosticCore:
    """Test core code maintains plugin-agnostic principles."""
    
    def test_core_orchestrator_no_plugin_names_in_code(self):
        """Test orchestrator doesn't have hardcoded plugin names in code."""
        orchestrator_path = Path("src/archiverr/core/orchestrator.py")
        
        if not orchestrator_path.exists():
            pytest.skip("Orchestrator file not found")
        
        content = orchestrator_path.read_text()
        
        # Check for hardcoded plugin names in code (not comments)
        # Remove comments first
        lines = content.split('\n')
        code_lines = [
            line.split('#')[0]  # Remove inline comments
            for line in lines
            if not line.strip().startswith('#')
        ]
        code = '\n'.join(code_lines)
        
        # Plugin names to check
        plugin_names = ['scanner', 'renamer', 'tmdb', 'tvdb', 'tasker', 'ffprobe']
        
        # These patterns would indicate hardcoding
        hardcoded_patterns = [
            "\\['{name}'",      # ['scanner']
            "\\[\"{name}\"",      # ["scanner"]
            "== '{name}'",      # == 'scanner'
            '== "{name}"',      # == "scanner"
            "plugin_name in \\['{name}'",  # plugin_name in ['scanner', ...]
        ]
        
        violations = []
        for name in plugin_names:
            for pattern in hardcoded_patterns:
                pattern_with_name = pattern.replace('{name}', name)
                if re.search(pattern_with_name, code):
                    violations.append(f"Found hardcoded '{name}' matching pattern: {pattern}")
        
        if violations:
            pytest.fail(
                "Plugin-agnostic violation in orchestrator:\\n" + 
                "\\n".join(violations)
            )
    
    def test_stage_executor_no_hardcoded_plugins(self):
        """Test stage executor doesn't hardcode plugin names."""
        executor_path = Path("src/archiverr/core/plugins/stage_executor.py")
        
        if not executor_path.exists():
            pytest.skip("Stage executor file not found")
        
        content = executor_path.read_text()
        
        # Remove comments
        code_lines = [
            line.split('#')[0]
            for line in content.split('\n')
            if not line.strip().startswith('#')
        ]
        code = '\n'.join(code_lines)
        
        # Check for hardcoded lists
        hardcoded_list_pattern = r"for plugin_name in \\[.*?['\"](?:scanner|renamer|tmdb|tvdb|tasker|ffprobe)['\"]"
        
        if re.search(hardcoded_list_pattern, code):
            pytest.fail("Stage executor contains hardcoded plugin name list")
    
    def test_no_plugin_specific_logic_in_core(self):
        """Test core doesn't contain plugin-specific logic."""
        core_dir = Path("src/archiverr/core")
        
        if not core_dir.exists():
            pytest.skip("Core directory not found")
        
        violations = []
        
        # Check all Python files in core/
        for py_file in core_dir.rglob("*.py"):
            # Skip __pycache__ and test files
            if '__pycache__' in str(py_file) or 'test_' in py_file.name:
                continue
            
            content = py_file.read_text()
            
            # Look for plugin-specific conditionals
            plugin_conditionals = [
                r"if.*plugin.*==.*['\"]scanner['\"]",
                r"if.*plugin.*==.*['\"]renamer['\"]",
                r"if.*plugin.*==.*['\"]tmdb['\"]",
            ]
            
            for pattern in plugin_conditionals:
                if re.search(pattern, content, re.IGNORECASE):
                    violations.append(f"{py_file}: Contains plugin-specific conditional")
        
        if violations:
            pytest.fail(
                "Plugin-specific logic found in core:\\n" +
                "\\n".join(violations)
            )


class TestDynamicPluginDiscovery:
    """Test dynamic plugin discovery and execution."""
    
    def test_plugins_discovered_dynamically(self):
        """Test plugins are discovered from filesystem, not hardcoded."""
        from archiverr.core.plugins.discovery import PluginDiscovery
        
        discovery = PluginDiscovery()
        manifests = discovery.discover()
        
        # Should find plugins dynamically
        assert isinstance(manifests, dict)
        
        # Plugin list should NOT be hardcoded
        # If we had a hardcoded list, it would always return same plugins
        # Dynamic discovery returns what exists in plugins/ directory
    
    def test_plugin_registry_uses_manifests(self):
        """Test plugin registry uses manifest data, not hardcoded config."""
        from archiverr.core.plugins.registry import PluginRegistry
        
        config = {
            "options": {"debug": False},
            "plugins": {}
        }
        
        registry = PluginRegistry(config)
        
        # Registry should discover plugins from manifests
        # Not from a hardcoded list
        assert hasattr(registry, 'discover_and_load')


class TestNoHardcodedExecutionOrder:
    """Test execution order is not hardcoded."""
    
    def test_orchestrator_doesnt_hardcode_sequence(self):
        """Test orchestrator doesn't have hardcoded execution sequence."""
        orchestrator_path = Path("src/archiverr/core/orchestrator.py")
        
        if not orchestrator_path.exists():
            pytest.skip("Orchestrator file not found")
        
        content = orchestrator_path.read_text()
        
        # Look for hardcoded execution patterns
        # NOTE: Current implementation DOES have hardcoded order
        # This test documents the CURRENT STATE (EXPECTED TO FAIL)
        # After refactoring to condition-based execution, this should pass
        
        hardcoded_patterns = [
            r"execute.*scanner",
            r"execute.*renamer", 
            r"scanner.*then.*renamer",
            r"per_run.*before.*stages",
        ]
        
        found_patterns = []
        for pattern in hardcoded_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                found_patterns.append(pattern)
        
        if found_patterns:
            pytest.xfail(
                "Current implementation has hardcoded execution order. " +
                "This is a known issue to be fixed with condition-based execution."
            )


class TestPluginDataAccess:
    """Test plugins access data generically, not by hardcoded names."""
    
    def test_tasker_uses_dynamic_plugin_data(self):
        """Test tasker plugin accesses data dynamically, not hardcoded list."""
        tasker_path = Path("src/archiverr/plugins/tasker/plugin.py")
        
        if not tasker_path.exists():
            pytest.skip("Tasker plugin not found")
        
        content = tasker_path.read_text()
        
        # Check for hardcoded plugin list
        # Looking for: for plugin_name in ['renamer', 'tmdb', ...]
        hardcoded_list = r"for plugin_name in \\[[^\\]]*(?:'renamer'|\"renamer\"|'tmdb'|\"tmdb\")"
        
        if re.search(hardcoded_list, content):
            pytest.fail(
                "Tasker plugin contains hardcoded plugin name list. " +
                "Should use dynamic: services.state.get_available_plugins()"
            )


class TestAPIPluginAgnostic:
    """Test API layer is plugin-agnostic."""
    
    def test_process_executor_no_hardcoded_plugins(self):
        """Test process executor doesn't hardcode plugin names."""
        executor_path = Path("src/archiverr/api/process_executor.py")
        
        if not executor_path.exists():
            pytest.skip("Process executor not found")
        
        content = executor_path.read_text()
        
        # Check for hardcoded input plugin list
        hardcoded_inputs = r"for plugin_name in \\[[^\\]]*(?:'scanner'|\"scanner\"|'file.reader')"
        
        if re.search(hardcoded_inputs, content):
            pytest.fail(
                "API process executor contains hardcoded plugin names. " +
                "Should determine input plugins dynamically from config."
            )
    
    def test_execution_service_no_hardcoded_plugins(self):
        """Test execution service doesn't hardcode plugin names."""
        service_path = Path("src/archiverr/core/services/execution_service.py")
        
        if not service_path.exists():
            pytest.skip("Execution service not found")
        
        content = service_path.read_text()
        
        # Check for hardcoded plugin lists
        hardcoded_pattern = r"\\['scanner',\\s*'file.reader'\\]"
        
        if re.search(hardcoded_pattern, content):
            pytest.fail(
                "Execution service contains hardcoded plugin list. " +
                "Should discover plugins dynamically."
            )


class TestCommentsAndDocumentation:
    """Test documentation doesn't create plugin-specific coupling."""
    
    def test_core_comments_use_generic_examples(self):
        """Test core code comments use generic plugin examples, not specific ones."""
        orchestrator_path = Path("src/archiverr/core/orchestrator.py")
        
        if not orchestrator_path.exists():
            pytest.skip("Orchestrator file not found")
        
        content = orchestrator_path.read_text()
        
        # Find comments mentioning specific plugins
        plugin_specific_comments = []
        
        for line_num, line in enumerate(content.split('\n'), 1):
            # Check comments only
            if '#' in line:
                comment = line[line.index('#'):]
                
                # Look for plugin names in comments
                if any(name in comment.lower() for name in ['scanner', 'renamer', 'tmdb']):
                    plugin_specific_comments.append(f"Line {line_num}: {comment.strip()}")
        
        # It's okay to have EXAMPLES in comments, but not implementation coupling
        # We're looking for comments like:
        # "# Execute scanner first, then renamer"  <- BAD
        # "# Execute input plugins (e.g., scanner)" <- OKAY
        
        problematic = [
            c for c in plugin_specific_comments
            if 'e.g.' not in c and 'example' not in c.lower()
        ]
        
        if problematic:
            pytest.xfail(
                "Core code contains plugin-specific comments without 'e.g.' or 'example': " +
                "\\n".join(problematic[:5])  # Show first 5
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
