#!/bin/bash
# MongoDB Management Script for Archiverr

CONTAINER_NAME="archiverr-mongodb"

case "$1" in
    start)
        echo "Starting MongoDB..."
        ./start_mongodb.sh
        ;;
    stop)
        echo "Stopping MongoDB..."
        sudo docker stop $CONTAINER_NAME
        ;;
    restart)
        echo "Restarting MongoDB..."
        sudo docker restart $CONTAINER_NAME
        ;;
    status)
        echo "MongoDB Status:"
        sudo docker ps | grep $CONTAINER_NAME || echo "Container not running"
        ;;
    logs)
        echo "MongoDB Logs:"
        sudo docker logs $CONTAINER_NAME ${2:---tail 50}
        ;;
    shell)
        echo "Connecting to MongoDB shell..."
        sudo docker exec -it $CONTAINER_NAME mongosh archiverr
        ;;
    test)
        echo "Testing MongoDB connection..."
        ./venv/bin/python test_mongo_connection.py
        ;;
    backup)
        BACKUP_DIR="./mongodb-backup-$(date +%Y%m%d-%H%M%S)"
        echo "Backing up to $BACKUP_DIR..."
        sudo docker exec $CONTAINER_NAME mongodump --db archiverr --out /tmp/backup
        sudo docker cp $CONTAINER_NAME:/tmp/backup $BACKUP_DIR
        echo "Backup complete: $BACKUP_DIR"
        ;;
    restore)
        if [ -z "$2" ]; then
            echo "Usage: $0 restore <backup-directory>"
            exit 1
        fi
        echo "Restoring from $2..."
        sudo docker cp $2 $CONTAINER_NAME:/tmp/restore
        sudo docker exec $CONTAINER_NAME mongorestore --db archiverr /tmp/restore/archiverr
        echo "Restore complete"
        ;;
    clean)
        echo "Cleaning MongoDB data (removes ALL data)..."
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            sudo docker exec $CONTAINER_NAME mongosh archiverr --eval "db.dropDatabase()"
            echo "Database cleaned"
        else
            echo "Cancelled"
        fi
        ;;
    *)
        echo "MongoDB Management Script for Archiverr"
        echo ""
        echo "Usage: $0 {command}"
        echo ""
        echo "Commands:"
        echo "  start    - Start MongoDB container"
        echo "  stop     - Stop MongoDB container"
        echo "  restart  - Restart MongoDB container"
        echo "  status   - Show container status"
        echo "  logs     - Show container logs"
        echo "  shell    - Open MongoDB shell"
        echo "  test     - Test connection"
        echo "  backup   - Backup database"
        echo "  restore  - Restore database from backup"
        echo "  clean    - Remove all data (dangerous!)"
        echo ""
        echo "Examples:"
        echo "  $0 start"
        echo "  $0 logs"
        echo "  $0 shell"
        echo "  $0 backup"
        echo "  $0 restore ./mongodb-backup-20231209-120000"
        ;;
esac
