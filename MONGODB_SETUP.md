# MongoDB Setup for Archiverr

## ✅ MongoDB Successfully Configured

MongoDB is now running and connected to Archiverr!

## Current Setup

### MongoDB Container

- **Container Name**: `archiverr-mongodb`
- **Image**: `mongo:7.0`
- **Port**: `27017` (localhost)
- **Database**: `archiverr`
- **Status**: Running with auto-restart

### Connection Details

```yaml
URI: mongodb://localhost:27017
Database: archiverr
Driver: PyMongo 4.15.5 (sync)
```

## Management Commands

### Start MongoDB

```bash
./start_mongodb.sh
```

### Stop MongoDB

```bash
sudo docker stop archiverr-mongodb
```

### Restart MongoDB

```bash
sudo docker restart archiverr-mongodb
```

### View MongoDB Logs

```bash
sudo docker logs archiverr-mongodb
```

### Check MongoDB Status

```bash
sudo docker ps | grep archiverr-mongodb
```

### Test Connection

```bash
./venv/bin/python test_mongo_connection.py
```

### Access MongoDB Shell

```bash
sudo docker exec -it archiverr-mongodb mongosh
```

Once in the shell:

```javascript
use archiverr;
show collections;
db.runs.find().pretty();
db.jobs.find().pretty();
db.plugins.find().pretty();
```

## Docker Compose

A `docker-compose.yml` file is provided for easy management:

```bash
# Start MongoDB
docker-compose up -d

# Stop MongoDB
docker-compose down

# View logs
docker-compose logs -f

# Restart
docker-compose restart
```

## Data Persistence

MongoDB data is persisted in a Docker volume:

- **Volume Name**: `archiverr-mongodb-data`
- **Location**: Docker managed volume (persistent across container restarts)

To backup data:

```bash
sudo docker exec archiverr-mongodb mongodump --db archiverr --out /tmp/backup
sudo docker cp archiverr-mongodb:/tmp/backup ./mongodb-backup
```

To restore data:

```bash
sudo docker cp ./mongodb-backup archiverr-mongodb:/tmp/restore
sudo docker exec archiverr-mongodb mongorestore --db archiverr /tmp/restore/archiverr
```

## Running Archiverr

### CLI Mode

```bash
./venv/bin/python -m archiverr
```

### API Server Mode

```bash
./venv/bin/python -m archiverr serve
```

### With Custom Port

```bash
./venv/bin/python -m archiverr serve --port 8080
```

### Development Mode (with auto-reload)

```bash
./venv/bin/python -m archiverr serve --reload
```

## Collections

Archiverr uses the following MongoDB collections:

### Session 11/12 Collections (Current)

- **runs**: Execution run metadata
- **jobs**: Individual processing jobs
- **plugins**: Plugin execution results
- **branches**: Git-like version branches
- **commits**: Git-like version commits

### Legacy Collections (Backward Compatibility)

- **executions**: Old execution format
- **matches**: Old match format
- **plugin_results**: Old plugin results format

## Configuration

MongoDB connection is configured via environment variables or defaults:

```bash
# Environment variables (optional)
export MONGODB_URI="mongodb://localhost:27017"
export MONGODB_DATABASE="archiverr"
export ARCHIVERR_DB_BACKEND="mongodb"  # "mongodb" or "mock"
```

Default values are already set in the code:

- URI: `mongodb://localhost:27017`
- Database: `archiverr`
- Backend: `mongodb`

## Troubleshooting

### MongoDB Connection Refused

```bash
# Check if container is running
sudo docker ps | grep archiverr-mongodb

# If not running, start it
./start_mongodb.sh

# Check logs for errors
sudo docker logs archiverr-mongodb
```

### Port Already in Use

```bash
# Check what's using port 27017
sudo ss -tlnp | grep 27017

# Stop conflicting service
sudo systemctl stop mongod  # if native MongoDB is running
```

### Container Won't Start

```bash
# Remove and recreate container
sudo docker stop archiverr-mongodb
sudo docker rm archiverr-mongodb
./start_mongodb.sh
```

### Permission Issues

Make sure Docker daemon is running:

```bash
sudo systemctl start docker
sudo systemctl enable docker  # Enable on boot
```

## Fixed Issues

### ✅ AttributeError: 'PyMongoPersistence' object has no attribute 'EXECUTIONS'

**Fixed**: Added missing legacy collection name constants to `PyMongoPersistence` class:

- `EXECUTIONS = "executions"`
- `MATCHES = "matches"`
- `PLUGIN_RESULTS = "plugin_results"`

**File**: `src/archiverr/infrastructure/database/pymongo_persistence.py`

### ✅ Connection Refused Error

**Fixed**: MongoDB container successfully created and started with:

- Proper Docker image (mongo:7.0)
- Correct port mapping (27017:27017)
- Data persistence via volumes
- Auto-restart policy

## Development Notes

- MongoDB is configured with a 90-day TTL on plugin results
- Connection pooling is enabled (max 10, min 1)
- Indexes are automatically created on connect
- The system supports both sync (PyMongo) and async (Motor) operations

## Next Steps

The MongoDB setup is complete and working. The application successfully:

1. ✅ Connects to MongoDB
2. ✅ Creates required indexes
3. ✅ Stores run data
4. ✅ Stores job data
5. ✅ Stores plugin results

You can now use Archiverr with full MongoDB persistence!
