# Deploying ag-claw to AWS EC2

Complete guide for deploying the shopping agent API to AWS EC2.

---

## Prerequisites

- AWS account with EC2 access
- SSH key pair for EC2
- Domain name (optional, for HTTPS)

---

## Step 1: Launch EC2 Instance

### 1.1 Create Instance

```bash
# Recommended specs:
- AMI: Ubuntu 22.04 LTS
- Instance type: t3.medium (2 vCPU, 4GB RAM)
- Storage: 20GB GP3
- Security group: Allow ports 22 (SSH), 80 (HTTP), 443 (HTTPS), 8000 (API)
```

### 1.2 Configure Security Group

```bash
# Inbound rules:
SSH       TCP  22    0.0.0.0/0
HTTP      TCP  80    0.0.0.0/0
HTTPS     TCP  443   0.0.0.0/0
Custom    TCP  8000  0.0.0.0/0   # API server
```

### 1.3 Connect to Instance

```bash
ssh -i your-key.pem ubuntu@your-ec2-public-ip
```

---

## Step 2: Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Install other tools
sudo apt install -y git nginx supervisor curl

# Install pip
curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3.11

# Verify installation
python3.11 --version
```

---

## Step 3: Clone and Setup Application

```bash
# Clone repository
cd /home/ubuntu
git clone https://github.com/vedantatrivedi/ag-claw.git
cd ag-claw

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install uvicorn gunicorn

# Set up environment variables
cp .env.example .env
nano .env
```

### 3.1 Configure .env

```bash
# Required
OPENAI_API_KEY=your-openai-key-here
SERPAPI_KEY=your-serpapi-key-here

# Optional
OPENAI_MODEL=gpt-4o-mini
PLANNER_TEMPERATURE=0.3
BROWSER_HEADLESS=true

# Amazon API (optional)
BROWSERBASE_API_KEY=your-key
BROWSERBASE_PROJECT_ID=your-id
```

---

## Step 4: Test Application

```bash
# Activate venv
source /home/ubuntu/ag-claw/venv/bin/activate

# Test the API server
cd /home/ubuntu/ag-claw
uvicorn shopping_agent.server:app --host 0.0.0.0 --port 8000

# Test from another terminal:
curl http://your-ec2-public-ip:8000/health
# Should return: {"status":"ok"}

# Stop with Ctrl+C
```

---

## Step 5: Setup Systemd Service (Production)

### 5.1 Create Service File

```bash
sudo nano /etc/systemd/system/ag-claw.service
```

Paste this configuration:

```ini
[Unit]
Description=ag-claw Shopping Agent API
After=network.target

[Service]
Type=notify
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/ag-claw
Environment="PATH=/home/ubuntu/ag-claw/venv/bin"
EnvironmentFile=/home/ubuntu/ag-claw/.env
ExecStart=/home/ubuntu/ag-claw/venv/bin/gunicorn \
    shopping_agent.server:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile /var/log/ag-claw/access.log \
    --error-logfile /var/log/ag-claw/error.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 5.2 Create Log Directory

```bash
sudo mkdir -p /var/log/ag-claw
sudo chown ubuntu:ubuntu /var/log/ag-claw
```

### 5.3 Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable on boot
sudo systemctl enable ag-claw

# Start service
sudo systemctl start ag-claw

# Check status
sudo systemctl status ag-claw

# View logs
sudo journalctl -u ag-claw -f
```

---

## Step 6: Setup Nginx Reverse Proxy

### 6.1 Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/ag-claw
```

Paste this configuration:

```nginx
upstream ag-claw-api {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or EC2 IP

    client_max_body_size 10M;

    location / {
        proxy_pass http://ag-claw-api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for long-running requests
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    location /docs {
        proxy_pass http://ag-claw-api/docs;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    location /openapi.json {
        proxy_pass http://ag-claw-api/openapi.json;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
```

### 6.2 Enable Site

```bash
# Create symlink
sudo ln -s /etc/nginx/sites-available/ag-claw /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

---

## Step 7: Setup HTTPS with Let's Encrypt (Optional)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is configured automatically
# Test renewal:
sudo certbot renew --dry-run
```

---

## Step 8: Test Deployment

```bash
# Test health endpoint
curl http://your-domain.com/health
# or
curl http://your-ec2-ip/health

# Test plan endpoint
curl -X POST http://your-domain.com/plan \
  -H "Content-Type: application/json" \
  -d '{"request": "wireless headphones under 5000"}'

# Test search endpoint
curl -X POST http://your-domain.com/serp/search \
  -H "Content-Type: application/json" \
  -d '{
    "items": [{
      "description": "Wireless earbuds",
      "quantity": 1,
      "intent": "Music",
      "required": true,
      "search_hints": ["wireless"],
      "constraints": [],
      "search_query": "wireless earbuds",
      "preferred_sites": ["amazon"]
    }]
  }'

# Access Swagger docs
open http://your-domain.com/docs
```

---

## Management Commands

### View Logs

```bash
# Service logs
sudo journalctl -u ag-claw -f

# Nginx access logs
sudo tail -f /var/log/nginx/access.log

# Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Application logs
sudo tail -f /var/log/ag-claw/error.log
```

### Restart Services

```bash
# Restart API
sudo systemctl restart ag-claw

# Restart Nginx
sudo systemctl restart nginx

# Restart both
sudo systemctl restart ag-claw nginx
```

### Update Application

```bash
# Pull latest code
cd /home/ubuntu/ag-claw
git pull origin main

# Install new dependencies
source venv/bin/activate
pip install -r requirements.txt

# Restart service
sudo systemctl restart ag-claw
```

---

## Monitoring

### Check Service Status

```bash
# API service
sudo systemctl status ag-claw

# Nginx
sudo systemctl status nginx

# Disk space
df -h

# Memory usage
free -h

# API process
ps aux | grep gunicorn
```

### Setup CloudWatch (Optional)

```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb

# Configure and start agent (follow AWS docs)
```

---

## Security Best Practices

### 1. Firewall

```bash
# Enable UFW
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

### 2. Fail2Ban (SSH Protection)

```bash
# Install
sudo apt install -y fail2ban

# Configure
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 3. Automatic Security Updates

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 4. Restrict API Access (Optional)

```nginx
# In /etc/nginx/sites-available/ag-claw
location / {
    # Whitelist specific IPs
    allow 1.2.3.4;
    allow 5.6.7.8;
    deny all;

    proxy_pass http://ag-claw-api;
    # ... rest of config
}
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
sudo journalctl -u ag-claw -n 50

# Check permissions
ls -la /home/ubuntu/ag-claw

# Check .env file
cat /home/ubuntu/ag-claw/.env

# Test manually
cd /home/ubuntu/ag-claw
source venv/bin/activate
uvicorn shopping_agent.server:app --host 0.0.0.0 --port 8000
```

### Nginx Errors

```bash
# Check config
sudo nginx -t

# Check logs
sudo tail -f /var/log/nginx/error.log

# Restart
sudo systemctl restart nginx
```

### High Memory Usage

```bash
# Reduce Gunicorn workers in service file
# Change --workers 4 to --workers 2

sudo nano /etc/systemd/system/ag-claw.service
sudo systemctl daemon-reload
sudo systemctl restart ag-claw
```

### API Timeouts

```bash
# Increase timeouts in service file
# Add: --timeout 180

# Increase Nginx timeouts (already configured above)
```

---

## Cost Optimization

### Instance Sizing

- **t3.micro** (1GB RAM): $7/month - Dev/testing only
- **t3.small** (2GB RAM): $15/month - Light production
- **t3.medium** (4GB RAM): $30/month - Production (recommended)

### Auto Scaling (Optional)

```bash
# Use Application Load Balancer + Auto Scaling Group
# Configure target tracking on CPU utilization (70%)
# Min: 1 instance, Max: 4 instances
```

---

## Alternative: Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "shopping_agent.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Deploy with Docker

```bash
# Build
docker build -t ag-claw .

# Run
docker run -d \
  --name ag-claw \
  -p 8000:8000 \
  -e OPENAI_API_KEY=your-key \
  -e SERPAPI_KEY=your-key \
  --restart unless-stopped \
  ag-claw
```

---

## Quick Deploy Script

Create `deploy.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Deploying ag-claw..."

# Pull latest code
cd /home/ubuntu/ag-claw
git pull origin main

# Install dependencies
source venv/bin/activate
pip install -r requirements.txt

# Restart service
sudo systemctl restart ag-claw

# Check status
sleep 2
sudo systemctl status ag-claw

echo "✅ Deployment complete!"
```

Make executable:
```bash
chmod +x deploy.sh
./deploy.sh
```

---

## Checklist

Before going live:

- [ ] EC2 instance launched and configured
- [ ] Security group allows necessary ports
- [ ] Python 3.11 installed
- [ ] Application cloned and dependencies installed
- [ ] .env file configured with API keys
- [ ] Systemd service created and running
- [ ] Nginx reverse proxy configured
- [ ] HTTPS certificate installed (if using domain)
- [ ] Health endpoint returns {"status":"ok"}
- [ ] API endpoints tested and working
- [ ] Logs are accessible and monitored
- [ ] Firewall configured
- [ ] Automatic updates enabled
- [ ] Backup strategy in place

---

**Your API will be available at:**
- HTTP: `http://your-ec2-ip` or `http://your-domain.com`
- HTTPS: `https://your-domain.com` (if configured)
- Swagger docs: `http://your-domain.com/docs`
