#!/bin/bash
# Quick MongoDB startup script

echo "Starting MongoDB container..."

# Stop and remove if exists
sudo docker stop archiverr-mongodb 2>/dev/null || true
sudo docker rm archiverr-mongodb 2>/dev/null || true

# Start fresh container
sudo docker run -d \
    --name archiverr-mongodb \
    --restart unless-stopped \
    -p 27017:27017 \
    -e MONGO_INITDB_DATABASE=archiverr \
    -v archiverr-mongodb-data:/data/db \
    mongo:7.0

echo "Waiting for MongoDB to be ready..."
for i in {1..30}; do
    if sudo docker exec archiverr-mongodb mongosh --eval "db.adminCommand('ping')" &>/dev/null; then
        echo "✓ MongoDB is ready and running!"
        echo ""
        echo "Container status:"
        sudo docker ps | grep archiverr-mongodb
        echo ""
        echo "MongoDB is available at: mongodb://localhost:27017"
        echo "Database name: archiverr"
        exit 0
    fi
    sleep 1
    echo -n "."
done

echo ""
echo "✗ MongoDB did not start in time. Checking logs..."
sudo docker logs archiverr-mongodb --tail 20
exit 1
