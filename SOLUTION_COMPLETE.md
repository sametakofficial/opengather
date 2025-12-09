# ✅ MongoDB Connection Problem - SOLVED

## Problem Description

```
Failed to connect to MongoDB at mongodb://localhost:27017:
localhost:27017: [Errno 111] Connection refused
```

Archiverr application was unable to start due to MongoDB connection failure.

## Root Causes Identified

1. **MongoDB not running** - No MongoDB instance available on localhost:27017
2. **Missing collection constants** - Code bug causing AttributeError
3. **No management tools** - Difficult to start/manage MongoDB

## Solutions Implemented

### 1. MongoDB Container Setup ✅

- Created Docker container with MongoDB 7.0
- Configured persistent data storage
- Set up auto-restart policy
- Port mapping: 27017:27017
- Database: archiverr

### 2. Code Fix ✅

**File**: `src/archiverr/infrastructure/database/pymongo_persistence.py`

**Added missing constants**:

```python
# Legacy collection names (for backward compatibility)
EXECUTIONS = "executions"
MATCHES = "matches"
PLUGIN_RESULTS = "plugin_results"
```

### 3. Management Tools Created ✅

#### Helper Scripts

- **`start_mongodb.sh`** - Quick MongoDB startup with health checks
- **`mongo.sh`** - Comprehensive management CLI (start/stop/status/backup/restore)
- **`test_mongo_connection.py`** - Connection testing utility
- **`setup_mongodb.sh`** - Multi-platform MongoDB installer

#### Configuration Files

- **`docker-compose.yml`** - Docker Compose for easy deployment

#### Documentation

- **`MONGODB_SETUP.md`** - Complete setup and troubleshooting guide
- **`MONGODB_FIX_SUMMARY.md`** - Detailed fix documentation
- **`QUICKSTART.md`** - Quick start guide for users
- **`SOLUTION_COMPLETE.md`** - This file

## Verification Results

### ✅ MongoDB Container Status

```bash
$ ./mongo.sh status
MongoDB Status:
7ef932c15f18   mongo:7.0   "docker-entrypoint.s…"
Up 10 minutes   0.0.0.0:27017->27017/tcp   archiverr-mongodb
```

### ✅ Connection Test

```bash
$ ./mongo.sh test
Testing MongoDB connection to localhost:27017...
✓ Successfully connected to MongoDB!
✓ Available databases: ['admin', 'archiverr', 'config', 'local']
✓ Collections in 'archiverr': ['commits', 'jobs', 'plugins', 'runs', 'branches']
```

### ✅ Application Test

```bash
$ ./venv/bin/python -m archiverr
2025-12-09T23:30:39+03:00  INFO   system               Archiverr starting
2025-12-09T23:30:39+03:00  INFO   orchestrator         scanner completed: 1 jobs created
2025-12-09T23:30:39+03:00  INFO   orchestrator         Stage completed: parse
2025-12-09T23:30:42+03:00  INFO   orchestrator         Stage completed: data
2025-12-09T23:30:42+03:00  INFO   orchestrator         Stage completed: output
2025-12-09T23:30:42+03:00  INFO   execution            Execution completed
2025-12-09T23:30:42+03:00  INFO   system               Archiverr complete

Exit Code: 0 ✅
```

### ✅ Data Persistence

MongoDB collections created and populated:

- `runs` - Execution runs
- `jobs` - Processing jobs
- `plugins` - Plugin results
- `branches` - Version branches
- `commits` - Version commits

## Usage Instructions

### Start MongoDB

```bash
./start_mongodb.sh
# or
./mongo.sh start
# or
docker-compose up -d
```

### Run Archiverr

```bash
# Activate virtual environment
source venv/bin/activate

# Run CLI mode
python -m archiverr

# Run API server
python -m archiverr serve

# Run with custom port
python -m archiverr serve --port 8080
```

### Manage MongoDB

```bash
./mongo.sh status    # Check status
./mongo.sh logs      # View logs
./mongo.sh shell     # Open MongoDB shell
./mongo.sh backup    # Backup database
./mongo.sh stop      # Stop MongoDB
./mongo.sh restart   # Restart MongoDB
```

## System Architecture

```
┌─────────────────────────────────────────────┐
│           Archiverr Application             │
│  (Python 3.13 + PyMongo 4.15.5)            │
└──────────────────┬──────────────────────────┘
                   │ mongodb://localhost:27017
                   │
┌──────────────────▼──────────────────────────┐
│        MongoDB Docker Container             │
│         (mongo:7.0)                         │
│  Port: 27017                                │
│  Database: archiverr                        │
│  Volume: archiverr-mongodb-data            │
└─────────────────────────────────────────────┘
```

## Files Created

### Scripts (Executable)

- ✅ `start_mongodb.sh` - Quick start MongoDB
- ✅ `setup_mongodb.sh` - Comprehensive installer
- ✅ `mongo.sh` - Management CLI
- ✅ `test_mongo_connection.py` - Connection tester

### Configuration

- ✅ `docker-compose.yml` - Docker Compose setup

### Documentation

- ✅ `MONGODB_SETUP.md` - Complete setup guide
- ✅ `MONGODB_FIX_SUMMARY.md` - Fix details
- ✅ `QUICKSTART.md` - Quick start guide
- ✅ `SOLUTION_COMPLETE.md` - This summary

### Code Changes

- ✅ `src/archiverr/infrastructure/database/pymongo_persistence.py` - Added legacy constants

## Technical Details

### MongoDB Configuration

- **Image**: mongo:7.0
- **Container**: archiverr-mongodb
- **Port**: 27017
- **Database**: archiverr
- **URI**: mongodb://localhost:27017
- **Persistence**: Docker volume (archiverr-mongodb-data)
- **Auto-restart**: Enabled

### Python Dependencies

- **PyMongo**: 4.15.5 (installed)
- **dnspython**: 2.8.0 (PyMongo dependency)
- **Python**: 3.13 (via venv)

### Collections Schema

```javascript
// runs - Execution runs
{
  id: "run_XXXXXXXX",
  started_at: ISODate,
  status: { state: "completed", ... },
  config_snapshot: { ... }
}

// jobs - Processing jobs
{
  id: "job_XXXXXXXX_N",
  run_id: "run_XXXXXXXX",
  index: 0,
  input: { path: "...", ... }
}

// plugins - Plugin data
{
  job_id: "job_XXXXXXXX_N",
  plugin_name: "tmdb",
  data: { ... },
  status: { success: true, ... }
}
```

## Troubleshooting

### MongoDB Not Starting

```bash
# Check Docker
sudo systemctl status docker
sudo systemctl start docker

# Check port
sudo ss -tlnp | grep 27017

# Check logs
./mongo.sh logs
```

### Connection Refused

```bash
# Restart MongoDB
./mongo.sh restart

# Test connection
./mongo.sh test
```

### Application Error

```bash
# Check MongoDB status
./mongo.sh status

# View application logs
python -m archiverr 2>&1 | tee archiverr.log

# Enable debug mode in config.yml
options:
  log_level: DEBUG
```

## Performance Notes

- Connection pooling enabled (max 10, min 1)
- Indexes automatically created
- TTL enabled (90 days for plugin results)
- Pure sync operations (no event loop issues)

## Security Notes

- MongoDB running without authentication (localhost only)
- For production, enable authentication:
  ```bash
  docker run -d \
    --name archiverr-mongodb \
    -p 27017:27017 \
    -e MONGO_INITDB_ROOT_USERNAME=admin \
    -e MONGO_INITDB_ROOT_PASSWORD=secure_password \
    mongo:7.0
  ```

## Maintenance

### Regular Tasks

```bash
# Check status
./mongo.sh status

# Backup (daily recommended)
./mongo.sh backup

# Monitor logs
./mongo.sh logs

# Database statistics
./mongo.sh shell
> db.stats()
```

### Cleanup

```bash
# Remove old backups
rm -rf mongodb-backup-*

# Clean database (WARNING: deletes all data)
./mongo.sh clean
```

## Test Results Summary

| Test              | Status  | Details                     |
| ----------------- | ------- | --------------------------- |
| MongoDB Container | ✅ PASS | Running on port 27017       |
| Connection        | ✅ PASS | localhost:27017 accessible  |
| Database Creation | ✅ PASS | 'archiverr' database exists |
| Collections       | ✅ PASS | 5 collections created       |
| Application Start | ✅ PASS | No errors, exit code 0      |
| Data Persistence  | ✅ PASS | Data saved to MongoDB       |
| Code Fix          | ✅ PASS | No AttributeError           |

## Timeline

1. **Problem Identified** - MongoDB connection refused
2. **MongoDB Setup** - Docker container created and started
3. **Code Fix** - Added missing collection constants
4. **Testing** - All tests passed
5. **Documentation** - Complete guides created
6. **Verification** - System fully operational

**Total Time**: ~15 minutes
**Status**: ✅ COMPLETE

## Quick Reference Card

```bash
# MongoDB Management
./mongo.sh start      # Start
./mongo.sh stop       # Stop
./mongo.sh status     # Check
./mongo.sh test       # Test connection

# Run Archiverr
source venv/bin/activate
python -m archiverr                  # CLI mode
python -m archiverr serve            # API mode
python -m archiverr serve --port 8080

# Troubleshooting
./mongo.sh logs       # MongoDB logs
./mongo.sh shell      # MongoDB shell
./mongo.sh restart    # Restart MongoDB
```

## Success Criteria

All criteria met:

- ✅ MongoDB running and accessible
- ✅ Archiverr connects without errors
- ✅ Data persists to MongoDB
- ✅ Application runs successfully
- ✅ Exit code 0 (no errors)
- ✅ Management tools available
- ✅ Documentation complete

## Conclusion

The MongoDB connection issue has been completely resolved. The system is now:

1. **Operational** - MongoDB running, Archiverr connecting
2. **Persistent** - Data stored in MongoDB with backups available
3. **Manageable** - Helper scripts for all operations
4. **Documented** - Complete guides and troubleshooting
5. **Tested** - All components verified working

**System Status**: 🟢 FULLY OPERATIONAL

---

**Fix Completed**: December 9, 2025, 23:30 UTC+03:00
**Developer**: AI Assistant (Cascade)
**Result**: SUCCESS ✅

For support, refer to:

- [QUICKSTART.md](QUICKSTART.md) - Quick start
- [MONGODB_SETUP.md](MONGODB_SETUP.md) - Detailed setup
- [MONGODB_FIX_SUMMARY.md](MONGODB_FIX_SUMMARY.md) - Fix details
