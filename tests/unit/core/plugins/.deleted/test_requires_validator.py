"""
Unit tests for requires_validator.py

Session 11 - Phase 5: RequiresValidator tests.
"""

import pytest
from unittest.mock import Mock
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from archiverr.core.plugins.requires_validator import (
    RequiresValidator,
    RequiresResult,
)


@dataclass
class MockInputData:
    """Mock InputData for testing"""
    value: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockOutputData:
    """Mock OutputData for testing"""
    values: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockJobStatus:
    """Mock JobStatus for testing"""
    success: bool = True
    executed: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)


@dataclass
class MockJobState:
    """Mock JobState for testing"""
    id: str = "job_test_0"
    run_id: str = "run_test"
    index: int = 0
    input: MockInputData = field(default_factory=MockInputData)
    output: MockOutputData = field(default_factory=MockOutputData)
    status: MockJobStatus = field(default_factory=MockJobStatus)


class TestRequiresResult:
    """Test RequiresResult dataclass"""
    
    def test_satisfied_result(self):
        result = RequiresResult(satisfied=True, missing=[])
        assert result.satisfied is True
        assert result.missing == []
        assert bool(result) is True
    
    def test_unsatisfied_result(self):
        result = RequiresResult(satisfied=False, missing=["job.plugins.tmdb.movie"])
        assert result.satisfied is False
        assert len(result.missing) == 1
        assert bool(result) is False


class TestRequiresValidatorEmpty:
    """Test empty requires"""
    
    def test_empty_requires_satisfied(self):
        validator = RequiresValidator()
        job = MockJobState()
        
        result = validator.validate(job, [])
        
        assert result.satisfied is True
        assert result.missing == []
    
    def test_none_requires_treated_as_empty(self):
        validator = RequiresValidator()
        job = MockJobState()
        
        result = validator.validate(job, None)
        
        assert result.satisfied is True


class TestRequiresValidatorPluginPaths:
    """Test job.plugins.* paths"""
    
    @pytest.fixture
    def validator(self):
        return RequiresValidator()
    
    @pytest.fixture
    def job(self):
        return MockJobState()
    
    def test_plugin_data_exists(self, validator, job):
        plugin_data = {
            "renamer": {"parsed": {"movie": {"name": "Test Movie"}}}
        }
        
        result = validator.validate(
            job, 
            ["job.plugins.renamer.parsed.movie"],
            plugin_data
        )
        
        assert result.satisfied is True
        assert result.missing == []
    
    def test_plugin_data_missing(self, validator, job):
        plugin_data = {}
        
        result = validator.validate(
            job,
            ["job.plugins.renamer.parsed.movie"],
            plugin_data
        )
        
        assert result.satisfied is False
        assert "job.plugins.renamer.parsed.movie" in result.missing
    
    def test_partial_plugin_path(self, validator, job):
        """Plugin exists but path doesn't exist within it"""
        plugin_data = {
            "renamer": {"parsed": {}}  # No 'movie' key
        }
        
        result = validator.validate(
            job,
            ["job.plugins.renamer.parsed.movie"],
            plugin_data
        )
        
        assert result.satisfied is False
    
    def test_multiple_requires_all_satisfied(self, validator, job):
        plugin_data = {
            "renamer": {"parsed": {"movie": {"name": "Test"}}},
            "ffprobe": {"duration": 7200}
        }
        
        result = validator.validate(
            job,
            [
                "job.plugins.renamer.parsed.movie",
                "job.plugins.ffprobe.duration"
            ],
            plugin_data
        )
        
        assert result.satisfied is True
    
    def test_multiple_requires_partial_satisfied(self, validator, job):
        plugin_data = {
            "renamer": {"parsed": {"movie": {"name": "Test"}}}
            # No ffprobe
        }
        
        result = validator.validate(
            job,
            [
                "job.plugins.renamer.parsed.movie",
                "job.plugins.ffprobe.duration"
            ],
            plugin_data
        )
        
        assert result.satisfied is False
        assert len(result.missing) == 1
        assert "job.plugins.ffprobe.duration" in result.missing
    
    def test_plugin_data_is_none(self, validator, job):
        plugin_data = {
            "renamer": {"parsed": None}
        }
        
        result = validator.validate(
            job,
            ["job.plugins.renamer.parsed"],
            plugin_data
        )
        
        # None value should be treated as missing
        assert result.satisfied is False


class TestRequiresValidatorInputPaths:
    """Test job.input.* paths"""
    
    @pytest.fixture
    def validator(self):
        return RequiresValidator()
    
    def test_input_value_exists(self, validator):
        job = MockJobState()
        job.input.value = "/path/to/file.mkv"
        
        result = validator.validate(job, ["job.input.value"])
        
        assert result.satisfied is True
    
    def test_input_value_empty(self, validator):
        job = MockJobState()
        job.input.value = ""
        
        result = validator.validate(job, ["job.input.value"])
        
        # Empty string should be treated as not None
        assert result.satisfied is True  # "" is not None
    
    def test_input_data_nested(self, validator):
        job = MockJobState()
        job.input.data = {"filename": "test.mkv", "size": 1024}
        
        result = validator.validate(job, ["job.input.data.filename"])
        
        assert result.satisfied is True


class TestRequiresValidatorOutputPaths:
    """Test job.output.* paths"""
    
    @pytest.fixture
    def validator(self):
        return RequiresValidator()
    
    def test_output_values_exists(self, validator):
        job = MockJobState()
        job.output.values = ["/output/path"]
        
        result = validator.validate(job, ["job.output.values"])
        
        assert result.satisfied is True
    
    def test_output_data_nested(self, validator):
        job = MockJobState()
        job.output.data = {"destination": "/output"}
        
        result = validator.validate(job, ["job.output.data.destination"])
        
        assert result.satisfied is True


class TestRequiresValidatorBasicFields:
    """Test basic job fields"""
    
    @pytest.fixture
    def validator(self):
        return RequiresValidator()
    
    def test_job_id(self, validator):
        job = MockJobState(id="job_test_123")
        
        result = validator.validate(job, ["job.id"])
        
        assert result.satisfied is True
    
    def test_job_run_id(self, validator):
        job = MockJobState(run_id="run_abc")
        
        result = validator.validate(job, ["job.run_id"])
        
        assert result.satisfied is True
    
    def test_job_index(self, validator):
        job = MockJobState(index=5)
        
        result = validator.validate(job, ["job.index"])
        
        assert result.satisfied is True


class TestRequiresValidatorInvalidPaths:
    """Test invalid path formats"""
    
    @pytest.fixture
    def validator(self):
        return RequiresValidator()
    
    @pytest.fixture
    def job(self):
        return MockJobState()
    
    def test_path_not_starting_with_job(self, validator, job):
        result = validator.validate(job, ["plugins.renamer.parsed"])
        
        assert result.satisfied is False
    
    def test_single_part_path(self, validator, job):
        result = validator.validate(job, ["job"])
        
        assert result.satisfied is False
    
    def test_unknown_root(self, validator, job):
        result = validator.validate(job, ["job.unknown.field"])
        
        assert result.satisfied is False


class TestExtractPluginNames:
    """Test extract_plugin_names method"""
    
    def test_extract_single_plugin(self):
        validator = RequiresValidator()
        
        plugins = validator.extract_plugin_names([
            "job.plugins.renamer.parsed.movie"
        ])
        
        assert plugins == ["renamer"]
    
    def test_extract_multiple_plugins(self):
        validator = RequiresValidator()
        
        plugins = validator.extract_plugin_names([
            "job.plugins.renamer.parsed.movie",
            "job.plugins.tmdb.movie.id",
            "job.input.value"  # Should be ignored
        ])
        
        assert set(plugins) == {"renamer", "tmdb"}
    
    def test_extract_no_plugins(self):
        validator = RequiresValidator()
        
        plugins = validator.extract_plugin_names([
            "job.input.value",
            "job.output.values"
        ])
        
        assert plugins == []
    
    def test_extract_empty_list(self):
        validator = RequiresValidator()
        
        plugins = validator.extract_plugin_names([])
        
        assert plugins == []
