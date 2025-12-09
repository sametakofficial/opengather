#!/usr/bin/env python3
"""Test MongoDB connection"""

import sys
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

def test_connection():
    """Test MongoDB connection"""
    print("Testing MongoDB connection to localhost:27017...")
    
    try:
        client = MongoClient(
            "mongodb://localhost:27017",
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
        
        # Attempt to connect
        client.admin.command('ping')
        print("✓ Successfully connected to MongoDB!")
        
        # Get database info
        db_names = client.list_database_names()
        print(f"✓ Available databases: {db_names}")
        
        # Test archiverr database
        db = client['archiverr']
        collections = db.list_collection_names()
        print(f"✓ Collections in 'archiverr': {collections if collections else '(empty)'}")
        
        client.close()
        return 0
        
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"✗ Failed to connect to MongoDB: {e}")
        print("\nPossible solutions:")
        print("1. Start MongoDB with: sudo systemctl start mongod")
        print("2. Start Docker container with: docker-compose up -d")
        print("3. Check if port 27017 is in use: sudo ss -tlnp | grep 27017")
        return 1
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(test_connection())
