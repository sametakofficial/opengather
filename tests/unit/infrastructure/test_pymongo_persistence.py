"""
Tests for PyMongoPersistence

Tests the sync PyMongo persistence layer.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


class TestPyMongoPersistenceImport:
    """Test that PyMongoPersistence can be imported."""
    
    def test_import_from_module(self):
        """Test import from database module."""
        from archiverr.infrastructure.database import PyMongoPersistence, PYMONGO_AVAILABLE
        assert PYMONGO_AVAILABLE is True
        assert PyMongoPersistence is not None
    
    def test_import_directly(self):
        """Test direct import."""
        from archiverr.infrastructure.database.pymongo_persistence import PyMongoPersistence
        assert PyMongoPersistence is not None


class TestPyMongoPersistenceInit:
    """Test initialization."""
    
    def test_init_with_defaults(self):
        """Test initialization with default values."""
        from archiverr.infrastructure.database.pymongo_persistence import PyMongoPersistence
        persistence = PyMongoPersistence()
        
        assert persistence._uri == "mongodb://localhost:27017"
        assert persistence._database_name == "archiverr"
        assert persistence._connected is False
    
    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        from archiverr.infrastructure.database.pymongo_persistence import PyMongoPersistence
        persistence = PyMongoPersistence(
            uri="mongodb://custom:27017",
            database="custom_db",
            ttl_days=30
        )
        
        assert persistence._uri == "mongodb://custom:27017"
        assert persistence._database_name == "custom_db"
        assert persistence._ttl_days == 30
    
    @patch.dict('os.environ', {
        'MONGODB_URI': 'mongodb://env:27017',
        'MONGODB_DATABASE': 'env_db'
    })
    def test_init_from_env(self):
        """Test initialization from environment variables."""
        from archiverr.infrastructure.database.pymongo_persistence import PyMongoPersistence
        persistence = PyMongoPersistence()
        
        assert persistence._uri == "mongodb://env:27017"
        assert persistence._database_name == "env_db"


class TestPyMongoPersistenceInterface:
    """Test that PyMongoPersistence implements PersistenceInterface."""
    
    def test_implements_interface(self):
        """Test that class implements required interface."""
        from archiverr.infrastructure.database.pymongo_persistence import PyMongoPersistence
        from archiverr.infrastructure.database.interface import PersistenceInterface
        
        persistence = PyMongoPersistence()
        assert isinstance(persistence, PersistenceInterface)
    
    def test_has_required_methods(self):
        """Test that class has all required methods."""
        from archiverr.infrastructure.database.pymongo_persistence import PyMongoPersistence
        
        persistence = PyMongoPersistence()
        
        # Core methods
        assert hasattr(persistence, 'connect')
        assert hasattr(persistence, 'disconnect')
        assert hasattr(persistence, 'save_execution')
        assert hasattr(persistence, 'save_match')
        assert hasattr(persistence, 'save_plugin_result')
        assert hasattr(persistence, 'get_execution')
        assert hasattr(persistence, 'get_matches')
        assert hasattr(persistence, 'get_plugin_results')
        assert hasattr(persistence, 'get_statistics')
        
        # Git-like versioning
        assert hasattr(persistence, 'create_branch')
        assert hasattr(persistence, 'get_branch')
        assert hasattr(persistence, 'list_branches')
        assert hasattr(persistence, 'delete_branch')
        assert hasattr(persistence, 'create_commit')
        assert hasattr(persistence, 'get_commit')
        assert hasattr(persistence, 'list_commits')


class TestDatabaseConnection:
    """Test DatabaseConnection factory with PyMongoPersistence."""
    
    @patch.dict('os.environ', {'ARCHIVERR_DB_BACKEND': 'mongodb'})
    def test_factory_creates_pymongo_persistence(self):
        """Test that factory creates PyMongoPersistence for mongodb backend."""
        from archiverr.infrastructure.database import DatabaseConnection
        from archiverr.infrastructure.database.pymongo_persistence import PyMongoPersistence
        
        # Reset singleton
        DatabaseConnection.reset()
        
        connection = DatabaseConnection.from_env()
        assert connection.config.backend == "mongodb"
        
        # Get persistence (but don't connect)
        with patch.object(PyMongoPersistence, 'connect', return_value=None):
            persistence = connection.get_persistence()
            assert isinstance(persistence, PyMongoPersistence)
        
        # Cleanup
        DatabaseConnection.reset()


class TestMockedPyMongoPersistence:
    """Test PyMongoPersistence with mocked MongoDB client."""
    
    @pytest.fixture
    def mock_client(self):
        """Create mock MongoDB client."""
        client = MagicMock()
        db = MagicMock()
        client.__getitem__ = Mock(return_value=db)
        db.command = Mock(return_value={'ok': 1})
        
        # Mock collections
        executions = MagicMock()
        matches = MagicMock()
        plugin_results = MagicMock()
        branches = MagicMock()
        commits = MagicMock()
        
        db.__getitem__ = Mock(side_effect=lambda name: {
            'executions': executions,
            'matches': matches,
            'plugin_results': plugin_results,
            'branches': branches,
            'commits': commits
        }.get(name, MagicMock()))
        
        return client, db
    
    @patch('archiverr.infrastructure.database.pymongo_persistence.MongoClient')
    def test_connect(self, mock_mongo_client, mock_client):
        """Test connection."""
        client, db = mock_client
        mock_mongo_client.return_value = client
        
        from archiverr.infrastructure.database.pymongo_persistence import PyMongoPersistence
        
        persistence = PyMongoPersistence()
        persistence.connect()
        
        assert persistence._connected is True
        mock_mongo_client.assert_called_once()
        db.command.assert_called_with('ping')
    
    @patch('archiverr.infrastructure.database.pymongo_persistence.MongoClient')
    def test_disconnect(self, mock_mongo_client, mock_client):
        """Test disconnection."""
        client, db = mock_client
        mock_mongo_client.return_value = client
        
        from archiverr.infrastructure.database.pymongo_persistence import PyMongoPersistence
        
        persistence = PyMongoPersistence()
        persistence.connect()
        persistence.disconnect()
        
        assert persistence._connected is False
        client.close.assert_called_once()
    
    @patch('archiverr.infrastructure.database.pymongo_persistence.MongoClient')
    def test_save_execution_with_dict(self, mock_mongo_client, mock_client):
        """Test saving execution with dict."""
        client, db = mock_client
        mock_mongo_client.return_value = client
        
        from archiverr.infrastructure.database.pymongo_persistence import PyMongoPersistence
        
        persistence = PyMongoPersistence()
        persistence.connect()
        
        execution = {
            "_id": "exec_test123",
            "status": "completed",
            "success": True
        }
        
        persistence.save_execution(execution)
        
        db['executions'].update_one.assert_called_once()
    
    @patch('archiverr.infrastructure.database.pymongo_persistence.MongoClient')
    def test_save_execution_with_object(self, mock_mongo_client, mock_client):
        """Test saving execution with object that has to_dict()."""
        client, db = mock_client
        mock_mongo_client.return_value = client
        
        from archiverr.infrastructure.database.pymongo_persistence import PyMongoPersistence
        
        persistence = PyMongoPersistence()
        persistence.connect()
        
        # Mock execution object
        execution = Mock()
        execution.to_dict.return_value = {
            "_id": "exec_test123",
            "status": "completed",
            "success": True
        }
        
        persistence.save_execution(execution)
        
        execution.to_dict.assert_called_once()
        db['executions'].update_one.assert_called_once()
    
    @patch('archiverr.infrastructure.database.pymongo_persistence.MongoClient')
    def test_get_execution(self, mock_mongo_client, mock_client):
        """Test getting execution."""
        client, db = mock_client
        mock_mongo_client.return_value = client
        
        expected_doc = {"_id": "exec_test123", "status": "completed"}
        db['executions'].find_one.return_value = expected_doc
        
        from archiverr.infrastructure.database.pymongo_persistence import PyMongoPersistence
        
        persistence = PyMongoPersistence()
        persistence.connect()
        
        result = persistence.get_execution("test123")
        
        assert result == expected_doc
        db['executions'].find_one.assert_called_with({"_id": "exec_test123"})
    
    @patch('archiverr.infrastructure.database.pymongo_persistence.MongoClient')
    def test_get_statistics(self, mock_mongo_client, mock_client):
        """Test getting statistics."""
        client, db = mock_client
        mock_mongo_client.return_value = client
        
        db['executions'].count_documents.return_value = 10
        db['matches'].count_documents.return_value = 50
        db['plugin_results'].count_documents.return_value = 200
        
        from archiverr.infrastructure.database.pymongo_persistence import PyMongoPersistence
        
        persistence = PyMongoPersistence()
        persistence.connect()
        
        stats = persistence.get_statistics()
        
        assert stats['backend'] == 'PyMongoPersistence'
        assert stats['executions'] == 10
        assert stats['matches'] == 50
        assert stats['plugin_results'] == 200


class TestPyMongoPersistenceNoAsyncIssues:
    """Verify PyMongoPersistence has no async/event loop issues."""
    
    def test_no_asyncio_imports(self):
        """Verify no asyncio imports in PyMongoPersistence."""
        import importlib.util
        import ast
        
        spec = importlib.util.find_spec('archiverr.infrastructure.database.pymongo_persistence')
        with open(spec.origin, 'r') as f:
            tree = ast.parse(f.read())
        
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        # Should NOT have asyncio or motor imports
        assert 'asyncio' not in imports
        assert 'motor' not in imports
        assert 'motor.motor_asyncio' not in imports
    
    def test_no_run_until_complete_pattern(self):
        """Verify no run_until_complete method calls in code."""
        import importlib.util
        import ast
        
        spec = importlib.util.find_spec('archiverr.infrastructure.database.pymongo_persistence')
        with open(spec.origin, 'r') as f:
            tree = ast.parse(f.read())
        
        # Check for method calls to run_until_complete, get_event_loop, new_event_loop
        dangerous_calls = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for attribute calls like loop.run_until_complete()
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ('run_until_complete', 'get_event_loop', 'new_event_loop'):
                        dangerous_calls.append(node.func.attr)
                # Check for function calls like asyncio.get_event_loop()
                elif isinstance(node.func, ast.Name):
                    if node.func.id in ('get_event_loop', 'new_event_loop'):
                        dangerous_calls.append(node.func.id)
        
        assert len(dangerous_calls) == 0, f"Found dangerous async patterns: {dangerous_calls}"
