#!/bin/bash
# Quick deploy script for ag-claw on EC2
set -e

echo "🚀 Deploying ag-claw..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Navigate to app directory
APP_DIR="/home/ubuntu/ag-claw"
cd $APP_DIR

# Pull latest code
echo -e "${YELLOW}📥 Pulling latest code...${NC}"
git pull origin main

# Activate virtual environment
echo -e "${YELLOW}🔧 Installing dependencies...${NC}"
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Restart service
echo -e "${YELLOW}♻️  Restarting service...${NC}"
sudo systemctl restart ag-claw

# Wait for service to start
sleep 3

# Check service status
if sudo systemctl is-active --quiet ag-claw; then
    echo -e "${GREEN}✅ Service running${NC}"
else
    echo -e "\033[0;31m❌ Service failed to start${NC}"
    sudo systemctl status ag-claw
    exit 1
fi

# Test health endpoint
echo -e "${YELLOW}🏥 Testing health endpoint...${NC}"
if curl -s http://localhost:8000/health | grep -q "ok"; then
    echo -e "${GREEN}✅ Health check passed${NC}"
else
    echo -e "\033[0;31m❌ Health check failed${NC}"
    exit 1
fi

# Show recent logs
echo -e "${YELLOW}📋 Recent logs:${NC}"
sudo journalctl -u ag-claw -n 10 --no-pager

echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "📍 API available at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000"
echo "📚 Swagger docs: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000/docs"
