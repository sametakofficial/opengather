# MongoDB Connection Fix - Summary

## Problem

```
Failed to connect to MongoDB at mongodb://localhost:27017:
[Errno 111] Connection refused
```

Application was unable to start due to MongoDB not being available.

## Solution Implemented

### 1. MongoDB Container Setup ✅

Created and started MongoDB 7.0 container with:

- **Container name**: `archiverr-mongodb`
- **Port mapping**: `27017:27017`
- **Database**: `archiverr`
- **Auto-restart**: Enabled
- **Data persistence**: Docker volume `archiverr-mongodb-data`

### 2. Code Fix ✅

Fixed `PyMongoPersistence` class in:

```
src/archiverr/infrastructure/database/pymongo_persistence.py
```

**Issue**: Missing collection name constants

```python
AttributeError: 'PyMongoPersistence' object has no attribute 'EXECUTIONS'
```

**Fix**: Added legacy collection constants

```python
# Legacy collection names (for backward compatibility)
EXECUTIONS = "executions"
MATCHES = "matches"
PLUGIN_RESULTS = "plugin_results"
```

### 3. Helper Scripts Created ✅

#### `start_mongodb.sh`

Quick MongoDB startup script with health checks

#### `docker-compose.yml`

Docker Compose configuration for MongoDB

#### `test_mongo_connection.py`

Connection testing utility

#### `mongo.sh`

All-in-one MongoDB management script with commands:

- start, stop, restart
- status, logs
- shell access
- backup, restore
- clean (wipe data)

#### `setup_mongodb.sh`

Comprehensive setup script that tries multiple methods:

1. Docker container (preferred)
2. Native installation (Ubuntu/Debian, Fedora, Arch)

## Verification

### MongoDB Status

```bash
./mongo.sh status
```

✅ Container running: `archiverr-mongodb`
✅ Port: `0.0.0.0:27017->27017/tcp`

### Connection Test

```bash
./mongo.sh test
```

✅ Connection successful
✅ Database: `archiverr`
✅ Collections: `commits`, `jobs`, `plugins`, `runs`, `branches`

### Application Test

```bash
./venv/bin/python -m archiverr
```

✅ Application starts successfully
✅ Connects to MongoDB
✅ Processes files
✅ Stores data in MongoDB
✅ Exit code: 0

## Quick Reference

### Start MongoDB

```bash
./start_mongodb.sh
# or
./mongo.sh start
# or
docker-compose up -d
```

### Stop MongoDB

```bash
./mongo.sh stop
# or
docker-compose down
```

### Run Archiverr

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate

# CLI mode
python -m archiverr

# API server mode
python -m archiverr serve

# API with custom port
python -m archiverr serve --port 8080
```

### Access MongoDB Shell

```bash
./mongo.sh shell
```

### View Logs

```bash
./mongo.sh logs
```

### Test Connection

```bash
./mongo.sh test
```

## Files Created/Modified

### New Files

- ✅ `docker-compose.yml` - Docker Compose configuration
- ✅ `start_mongodb.sh` - Quick start script
- ✅ `setup_mongodb.sh` - Comprehensive setup script
- ✅ `test_mongo_connection.py` - Connection test utility
- ✅ `mongo.sh` - Management script
- ✅ `MONGODB_SETUP.md` - Full documentation
- ✅ `MONGODB_FIX_SUMMARY.md` - This file

### Modified Files

- ✅ `src/archiverr/infrastructure/database/pymongo_persistence.py`
  - Added legacy collection name constants

## Environment Configuration

### Default Configuration (Already Set)

```python
MONGODB_URI = "mongodb://localhost:27017"
MONGODB_DATABASE = "archiverr"
ARCHIVERR_DB_BACKEND = "mongodb"
```

### Override via Environment (Optional)

```bash
export MONGODB_URI="mongodb://localhost:27017"
export MONGODB_DATABASE="archiverr"
export ARCHIVERR_DB_BACKEND="mongodb"
```

## System Information

- **OS**: Arch Linux
- **Python**: 3.13 (via venv)
- **Docker**: Installed and running
- **PyMongo**: 4.15.5
- **MongoDB Image**: mongo:7.0

## Status: ✅ RESOLVED

MongoDB is now fully operational and integrated with Archiverr.

### Test Results

- ✅ MongoDB container running
- ✅ Connection successful
- ✅ Database created
- ✅ Collections created
- ✅ Application runs without errors
- ✅ Data persists correctly

## Maintenance

### Auto-start on Boot

MongoDB container is configured with `--restart unless-stopped`:

```bash
sudo docker update --restart unless-stopped archiverr-mongodb
```

### Backups

Regular backups recommended:

```bash
./mongo.sh backup
```

### Monitoring

Check status periodically:

```bash
./mongo.sh status
./mongo.sh logs
```

## Support

For issues:

1. Check container status: `./mongo.sh status`
2. View logs: `./mongo.sh logs`
3. Test connection: `./mongo.sh test`
4. Restart if needed: `./mongo.sh restart`
5. Refer to `MONGODB_SETUP.md` for troubleshooting

---

**Fix Completed**: December 9, 2025, 23:29 UTC+03:00
**Duration**: ~10 minutes
**Result**: Success ✅
