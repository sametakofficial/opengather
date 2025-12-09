#!/bin/bash
set -e

echo "========================================="
echo "MongoDB Setup Script for Archiverr"
echo "========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Check OS
print_info "Detecting operating system..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VER=$VERSION_ID
    echo "  OS: $OS $VER"
else
    print_error "Cannot detect OS"
    exit 1
fi

# Method 1: Try Docker first
print_info "Method 1: Trying Docker..."
if command -v docker &> /dev/null; then
    print_success "Docker is installed"
    
    # Start Docker daemon if not running
    if ! sudo systemctl is-active --quiet docker; then
        print_info "Starting Docker daemon..."
        sudo systemctl start docker || print_error "Failed to start Docker"
    fi
    
    # Stop and remove existing MongoDB containers
    print_info "Cleaning up existing MongoDB containers..."
    sudo docker stop archiverr-mongodb 2>/dev/null || true
    sudo docker rm archiverr-mongodb 2>/dev/null || true
    
    # Pull and run MongoDB container
    print_info "Pulling MongoDB 7.0 image..."
    sudo docker pull mongo:7.0
    
    print_info "Starting MongoDB container..."
    sudo docker run -d \
        --name archiverr-mongodb \
        --restart always \
        -p 27017:27017 \
        -e MONGO_INITDB_DATABASE=archiverr \
        -v mongodb_data:/data/db \
        mongo:7.0
    
    # Wait for MongoDB to be ready
    print_info "Waiting for MongoDB to be ready..."
    for i in {1..30}; do
        if sudo docker exec archiverr-mongodb mongosh --eval "db.adminCommand('ping')" &>/dev/null; then
            print_success "MongoDB is ready!"
            sudo docker ps | grep archiverr-mongodb
            
            # Test connection
            print_info "Testing connection from host..."
            python3 test_mongo_connection.py
            exit 0
        fi
        sleep 1
    done
    
    print_error "MongoDB did not start in time"
    print_info "Showing container logs:"
    sudo docker logs archiverr-mongodb --tail 50
fi

# Method 2: Try native MongoDB installation
print_info "Method 2: Installing MongoDB natively..."

case "$OS" in
    ubuntu|debian)
        print_info "Installing MongoDB on Ubuntu/Debian..."
        
        # Import MongoDB GPG key
        curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
            sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg
        
        # Add MongoDB repository
        echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
            sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
        
        # Install MongoDB
        sudo apt-get update
        sudo apt-get install -y mongodb-org
        
        # Start MongoDB
        sudo systemctl start mongod
        sudo systemctl enable mongod
        
        print_success "MongoDB installed and started"
        ;;
        
    fedora|rhel|centos)
        print_info "Installing MongoDB on Fedora/RHEL/CentOS..."
        
        # Create repo file
        cat <<EOF | sudo tee /etc/yum.repos.d/mongodb-org-7.0.repo
[mongodb-org-7.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/\$releasever/mongodb-org/7.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://www.mongodb.org/static/pgp/server-7.0.asc
EOF
        
        # Install MongoDB
        sudo yum install -y mongodb-org
        
        # Start MongoDB
        sudo systemctl start mongod
        sudo systemctl enable mongod
        
        print_success "MongoDB installed and started"
        ;;
        
    arch|manjaro)
        print_info "Installing MongoDB on Arch/Manjaro..."
        
        # Install from AUR or official repos
        if command -v yay &> /dev/null; then
            yay -S --noconfirm mongodb-bin
        elif command -v paru &> /dev/null; then
            paru -S --noconfirm mongodb-bin
        else
            sudo pacman -S --noconfirm mongodb
        fi
        
        # Start MongoDB
        sudo systemctl start mongodb
        sudo systemctl enable mongodb
        
        print_success "MongoDB installed and started"
        ;;
        
    *)
        print_error "Unsupported OS: $OS"
        print_info "Please install MongoDB manually: https://www.mongodb.com/docs/manual/installation/"
        exit 1
        ;;
esac

# Test connection
print_info "Testing MongoDB connection..."
sleep 3
python3 test_mongo_connection.py

print_success "MongoDB setup complete!"
echo ""
echo "========================================="
echo "MongoDB is now running on localhost:27017"
echo "Database: archiverr"
echo "========================================="
