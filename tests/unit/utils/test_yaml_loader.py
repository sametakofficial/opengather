"""
Unit tests for yaml_loader module.

Session 11 - Phase 6: !include directive tests.
"""

import pytest
from pathlib import Path

from archiverr.utils.yaml_loader import (
    load_yaml_with_includes,
    load_yaml_simple,
    IncludeError,
)


class TestLoadYamlSimple:
    """Tests for basic YAML loading without includes."""
    
    def test_load_simple_yaml(self, tmp_path):
        """Should load a simple YAML file."""
        yaml_file = tmp_path / "simple.yml"
        yaml_file.write_text("key: value\ncount: 42")
        
        result = load_yaml_simple(str(yaml_file))
        
        assert result["key"] == "value"
        assert result["count"] == 42
    
    def test_load_empty_yaml(self, tmp_path):
        """Should return empty dict for empty file."""
        yaml_file = tmp_path / "empty.yml"
        yaml_file.write_text("")
        
        result = load_yaml_simple(str(yaml_file))
        
        assert result == {}
    
    def test_load_nonexistent_raises(self):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_yaml_simple("/nonexistent/file.yml")


class TestIncludeSingleFile:
    """Tests for !include single file directive."""
    
    def test_include_single_file(self, tmp_path):
        """Should include content from a single file."""
        # Create included file
        db_yml = tmp_path / "db.yml"
        db_yml.write_text("host: localhost\nport: 27017")
        
        # Create main config
        config_yml = tmp_path / "config.yml"
        config_yml.write_text("database: !include ./db.yml")
        
        result = load_yaml_with_includes(str(config_yml))
        
        assert result["database"]["host"] == "localhost"
        assert result["database"]["port"] == 27017
    
    def test_include_absolute_path(self, tmp_path):
        """Should support absolute paths in include."""
        db_yml = tmp_path / "db.yml"
        db_yml.write_text("host: remote")
        
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(f"database: !include {db_yml}")
        
        result = load_yaml_with_includes(str(config_yml))
        
        assert result["database"]["host"] == "remote"
    
    def test_include_nested_structure(self, tmp_path):
        """Should include files with nested structures."""
        plugins_yml = tmp_path / "plugins.yml"
        plugins_yml.write_text("""
tmdb:
  api_key: xxx
  language: tr-TR
scanner:
  targets:
    - /movies
    - /shows
""")
        
        config_yml = tmp_path / "config.yml"
        config_yml.write_text("plugins: !include ./plugins.yml")
        
        result = load_yaml_with_includes(str(config_yml))
        
        assert result["plugins"]["tmdb"]["api_key"] == "xxx"
        assert len(result["plugins"]["scanner"]["targets"]) == 2
    
    def test_missing_include_raises(self, tmp_path):
        """Should raise IncludeError for missing include file."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text("data: !include ./nonexistent.yml")
        
        with pytest.raises(IncludeError) as exc_info:
            load_yaml_with_includes(str(config_yml))
        
        assert "not found" in str(exc_info.value)


class TestIncludeDirectory:
    """Tests for !include directory directive."""
    
    def test_include_directory(self, tmp_path):
        """Should include all YAML files from directory."""
        # Create tasks directory
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        
        (tasks_dir / "task1.yml").write_text("- name: task1\n  type: print")
        (tasks_dir / "task2.yml").write_text("- name: task2\n  type: save")
        
        # Create main config
        config_yml = tmp_path / "config.yml"
        config_yml.write_text("tasks: !include ./tasks/")
        
        result = load_yaml_with_includes(str(config_yml))
        
        assert len(result["tasks"]) == 2
        names = [t["name"] for t in result["tasks"]]
        assert "task1" in names
        assert "task2" in names
    
    def test_include_directory_sorted(self, tmp_path):
        """Should include files in sorted order."""
        dir_ = tmp_path / "sorted"
        dir_.mkdir()
        
        (dir_ / "c.yml").write_text("order: 3")
        (dir_ / "a.yml").write_text("order: 1")
        (dir_ / "b.yml").write_text("order: 2")
        
        config_yml = tmp_path / "config.yml"
        config_yml.write_text("items: !include ./sorted/")
        
        result = load_yaml_with_includes(str(config_yml))
        
        # Files should be sorted alphabetically
        orders = [item["order"] for item in result["items"]]
        assert orders == [1, 2, 3]
    
    def test_include_empty_directory(self, tmp_path):
        """Should return empty list for empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        config_yml = tmp_path / "config.yml"
        config_yml.write_text("items: !include ./empty/")
        
        result = load_yaml_with_includes(str(config_yml))
        
        assert result["items"] == []
    
    def test_include_directory_flattens_lists(self, tmp_path):
        """Should flatten lists from multiple files."""
        dir_ = tmp_path / "lists"
        dir_.mkdir()
        
        (dir_ / "a.yml").write_text("- item1\n- item2")
        (dir_ / "b.yml").write_text("- item3")
        
        config_yml = tmp_path / "config.yml"
        config_yml.write_text("items: !include ./lists/")
        
        result = load_yaml_with_includes(str(config_yml))
        
        assert result["items"] == ["item1", "item2", "item3"]


class TestNestedIncludes:
    """Tests for nested !include directives."""
    
    def test_nested_includes(self, tmp_path):
        """Should support includes within included files."""
        # Level 2: innermost file
        inner_yml = tmp_path / "inner.yml"
        inner_yml.write_text("deep: value")
        
        # Level 1: middle file includes inner
        middle_yml = tmp_path / "middle.yml"
        middle_yml.write_text("nested: !include ./inner.yml")
        
        # Level 0: main config includes middle
        config_yml = tmp_path / "config.yml"
        config_yml.write_text("outer: !include ./middle.yml")
        
        result = load_yaml_with_includes(str(config_yml))
        
        assert result["outer"]["nested"]["deep"] == "value"
    
    def test_circular_include_raises(self, tmp_path):
        """Should detect and raise error for circular includes."""
        a_yml = tmp_path / "a.yml"
        b_yml = tmp_path / "b.yml"
        
        # Create circular reference
        a_yml.write_text("b: !include ./b.yml")
        b_yml.write_text("a: !include ./a.yml")
        
        with pytest.raises(IncludeError) as exc_info:
            load_yaml_with_includes(str(a_yml))
        
        assert "Circular" in str(exc_info.value)
    
    def test_self_include_raises(self, tmp_path):
        """Should detect self-referential include."""
        self_yml = tmp_path / "self.yml"
        self_yml.write_text("me: !include ./self.yml")
        
        with pytest.raises(IncludeError) as exc_info:
            load_yaml_with_includes(str(self_yml))
        
        assert "Circular" in str(exc_info.value)


class TestYamlExtensions:
    """Tests for .yml and .yaml extension support."""
    
    def test_yaml_extension_in_directory(self, tmp_path):
        """Should include both .yml and .yaml files from directory."""
        dir_ = tmp_path / "mixed"
        dir_.mkdir()
        
        (dir_ / "a.yml").write_text("ext: yml")
        (dir_ / "b.yaml").write_text("ext: yaml")
        
        config_yml = tmp_path / "config.yml"
        config_yml.write_text("items: !include ./mixed/")
        
        result = load_yaml_with_includes(str(config_yml))
        
        exts = [item["ext"] for item in result["items"]]
        assert "yml" in exts
        assert "yaml" in exts
