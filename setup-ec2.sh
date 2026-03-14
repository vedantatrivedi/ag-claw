#!/bin/bash
# First-time setup script for ag-claw on EC2
set -e

echo "🚀 Setting up ag-claw on EC2..."

# Check if running as ubuntu user
if [ "$USER" != "ubuntu" ]; then
    echo "⚠️  This script should be run as ubuntu user"
    exit 1
fi

# Update system
echo "📦 Updating system..."
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
echo "🐍 Installing Python 3.11..."
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Install other tools
echo "🛠️  Installing tools..."
sudo apt install -y git nginx curl

# Install pip
echo "📦 Installing pip..."
curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3.11

# Clone repository
echo "📥 Cloning repository..."
cd /home/ubuntu
if [ ! -d "ag-claw" ]; then
    git clone https://github.com/vedantatrivedi/ag-claw.git
fi
cd ag-claw

# Create virtual environment
echo "🔧 Creating virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install uvicorn gunicorn

# Setup environment file
echo "⚙️  Setting up environment..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file with your API keys!"
    echo "Run: nano /home/ubuntu/ag-claw/.env"
    echo ""
fi

# Create log directory
echo "📝 Creating log directory..."
sudo mkdir -p /var/log/ag-claw
sudo chown ubuntu:ubuntu /var/log/ag-claw

# Create systemd service
echo "🔧 Creating systemd service..."
sudo tee /etc/systemd/system/ag-claw.service > /dev/null <<EOF
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
ExecStart=/home/ubuntu/ag-claw/venv/bin/gunicorn \\
    shopping_agent.server:app \\
    --workers 4 \\
    --worker-class uvicorn.workers.UvicornWorker \\
    --bind 0.0.0.0:8000 \\
    --timeout 120 \\
    --access-logfile /var/log/ag-claw/access.log \\
    --error-logfile /var/log/ag-claw/error.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create Nginx config
echo "🌐 Creating Nginx configuration..."
sudo tee /etc/nginx/sites-available/ag-claw > /dev/null <<'EOF'
upstream ag-claw-api {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name _;

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

        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}
EOF

# Enable Nginx site
sudo ln -sf /etc/nginx/sites-available/ag-claw /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test and restart Nginx
echo "🌐 Configuring Nginx..."
sudo nginx -t
sudo systemctl restart nginx

# Setup firewall
echo "🔒 Configuring firewall..."
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable

# Enable and start service
echo "🚀 Starting ag-claw service..."
sudo systemctl daemon-reload
sudo systemctl enable ag-claw

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Edit .env file: nano /home/ubuntu/ag-claw/.env"
echo "2. Add your API keys (OPENAI_API_KEY, SERPAPI_KEY)"
echo "3. Start service: sudo systemctl start ag-claw"
echo "4. Check status: sudo systemctl status ag-claw"
echo "5. Test API: curl http://localhost:8000/health"
echo ""
echo "📍 After adding API keys and starting:"
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "🌐 API: http://$PUBLIC_IP"
echo "📚 Docs: http://$PUBLIC_IP/docs"
