# 🚀 Archiverr Quick Start Guide

## Prerequisites

### 1. Start MongoDB

MongoDB must be running before starting Archiverr:

```bash
./start_mongodb.sh
```

**Verify MongoDB is running:**

```bash
./mongo.sh status
./mongo.sh test
```

### 2. Activate Virtual Environment

```bash
source venv/bin/activate
```

## Running Archiverr

### CLI Mode (Default)

Process files according to config.yml:

```bash
python -m archiverr
```

### API Server Mode

Start the REST API server:

```bash
python -m archiverr serve
```

Access the API:

- **API Docs**: http://localhost:8000/docs
- **OpenAPI Spec**: http://localhost:8000/openapi.json

### Custom Port

```bash
python -m archiverr serve --port 8080
```

### Development Mode (Auto-reload)

```bash
python -m archiverr serve --reload
```

## Configuration

Edit `config.yml` to configure:

- **Log level**: DEBUG, INFO, WARNING, ERROR
- **Target paths**: Files to process
- **Plugins**: Enable/disable features
- **Output format**: Customize reports

Example:

```yaml
options:
  log_level: INFO # Change to DEBUG for verbose output
  dry_run: true

scanner:
  targets:
    - "/path/to/your/media"
  extensions: [mkv, mp4, avi]
```

## MongoDB Management

### Quick Commands

```bash
./mongo.sh start     # Start MongoDB
./mongo.sh stop      # Stop MongoDB
./mongo.sh restart   # Restart MongoDB
./mongo.sh status    # Check status
./mongo.sh logs      # View logs
./mongo.sh shell     # Open MongoDB shell
./mongo.sh test      # Test connection
./mongo.sh backup    # Backup database
```

### Manual Docker Commands

```bash
# Start
sudo docker start archiverr-mongodb

# Stop
sudo docker stop archiverr-mongodb

# Restart
sudo docker restart archiverr-mongodb

# View logs
sudo docker logs archiverr-mongodb --tail 50

# Access shell
sudo docker exec -it archiverr-mongodb mongosh archiverr
```

## Troubleshooting

### MongoDB Connection Error

```
ERROR: Failed to connect to MongoDB
```

**Solution:**

```bash
# Check if MongoDB is running
./mongo.sh status

# If not running, start it
./mongo.sh start

# Test connection
./mongo.sh test
```

### No Output / Logs

Set debug level in `config.yml`:

```yaml
options:
  log_level: DEBUG
```

### Import Errors

```bash
pip install -e .
```

### Port Already in Use

```bash
# For API server
python -m archiverr serve --port 8080

# For MongoDB
sudo docker stop archiverr-mongodb
./start_mongodb.sh
```

## Test Files

### Connection Test

```bash
./venv/bin/python test_mongo_connection.py
```

### Quick System Test

```bash
./QUICK_TEST.sh
```

### Direct Test

```bash
python test_direct.py
```

## Expected Output

### Successful Run (INFO level)

```
2025-12-09T23:30:00+03:00  DEBUG  config               Configuration validated
2025-12-09T23:30:00+03:00  INFO   system               Archiverr starting (Session 11 - 4-stage architecture)
2025-12-09T23:30:00+03:00  INFO   orchestrator         Executing stage: input
2025-12-09T23:30:00+03:00  INFO   orchestrator         scanner completed: 1 jobs created
2025-12-09T23:30:00+03:00  INFO   orchestrator         Executing stage: parse
2025-12-09T23:30:00+03:00  INFO   orchestrator         Stage completed: parse
2025-12-09T23:30:00+03:00  INFO   orchestrator         Executing stage: data
2025-12-09T23:30:03+03:00  INFO   orchestrator         Stage completed: data
2025-12-09T23:30:03+03:00  INFO   orchestrator         Executing stage: output
2025-12-09T23:30:03+03:00  INFO   orchestrator         Stage completed: output
✓ Run output saved: output/run_XXXXXXXX_YYYYMMDD_HHMMSS.json
2025-12-09T23:30:03+03:00  INFO   system               Archiverr complete
```

### Successful MongoDB Connection

```
Testing MongoDB connection to localhost:27017...
✓ Successfully connected to MongoDB!
✓ Available databases: ['admin', 'archiverr', 'config', 'local']
✓ Collections in 'archiverr': ['commits', 'jobs', 'plugins', 'runs', 'branches']
```

## Output Files

Results are saved to:

- **JSON output**: `output/run_XXXXXXXX_YYYYMMDD_HHMMSS.json`
- **MongoDB**: Database `archiverr`, collections `runs`, `jobs`, `plugins`

## API Endpoints (Server Mode)

### Core Endpoints

- `GET /` - API information
- `GET /health` - Health check
- `GET /docs` - Interactive API documentation

### Version 1 API

- `POST /api/v1/run` - Execute processing pipeline
- `GET /api/v1/runs` - List all runs
- `GET /api/v1/runs/{run_id}` - Get run details
- `GET /api/v1/jobs` - List all jobs
- `GET /api/v1/plugins` - List plugin data

### System

- `GET /api/v1/system/health` - System health
- `GET /api/v1/system/stats` - Database statistics

## Environment Variables (Optional)

Override defaults with environment variables:

```bash
export MONGODB_URI="mongodb://localhost:27017"
export MONGODB_DATABASE="archiverr"
export TMDB_API_KEY="your_tmdb_api_key"
export ARCHIVERR_DB_BACKEND="mongodb"  # or "mock" for testing
```

## Development

### Run Tests

```bash
pytest
pytest -v  # Verbose
pytest tests/unit/  # Unit tests only
```

### Code Coverage

```bash
pytest --cov=archiverr --cov-report=html
```

### Linting

```bash
pylint src/archiverr
```

## Documentation

- **MongoDB Setup**: [MONGODB_SETUP.md](MONGODB_SETUP.md)
- **Fix Summary**: [MONGODB_FIX_SUMMARY.md](MONGODB_FIX_SUMMARY.md)
- **Plugin SDK**: [docs/PLUGIN_SDK.md](docs/PLUGIN_SDK.md)
- **Final Status**: [FINAL_STATUS.md](FINAL_STATUS.md)

## Support

### Check Logs

```bash
# Application logs
cat archiverr.log

# MongoDB logs
./mongo.sh logs

# Docker logs
sudo docker logs archiverr-mongodb
```

### Database Shell

```bash
./mongo.sh shell
```

In MongoDB shell:

```javascript
// View all runs
db.runs.find().pretty();

// Count documents
db.runs.countDocuments();
db.jobs.countDocuments();
db.plugins.countDocuments();

// Latest run
db.runs.find().sort({ created_at: -1 }).limit(1).pretty();
```

## Next Steps

1. ✅ MongoDB is running
2. ✅ Application tested
3. Configure your media paths in `config.yml`
4. Run Archiverr: `python -m archiverr`
5. Check output in `output/` directory
6. View data in MongoDB: `./mongo.sh shell`

---

**Status**: System is operational and ready to use! 🎉
