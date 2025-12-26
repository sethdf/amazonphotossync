#!/bin/bash
set -e

echo "=========================================="
echo "Amazon Photos Sync VM Setup"
echo "=========================================="

# Update system
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install dependencies
echo "Installing dependencies..."
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    htop \
    tmux \
    unzip

# Install Playwright system dependencies
echo "Installing Playwright dependencies..."
sudo apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0

# Clone repository
echo "Cloning repository..."
cd ~
if [ -d "amazonphotossync" ]; then
    cd amazonphotossync
    git pull
else
    git clone https://github.com/sethdf/amazonphotossync.git
    cd amazonphotossync
fi

# Create virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Install Python packages
echo "Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers
echo "Installing Playwright Chromium..."
playwright install chromium

# Create data directory for downloads
echo "Creating data directory..."
mkdir -p ~/amazonphotossync/amazon_photos_backup

# Create convenience script
echo "Creating run script..."
cat > ~/run_sync.sh << 'SCRIPT'
#!/bin/bash
cd ~/amazonphotossync
source .venv/bin/activate

case "$1" in
    login)
        python amazon_headless_login.py
        ;;
    enumerate)
        python amazon_photos_sync.py enumerate --full
        ;;
    download)
        python amazon_photos_sync.py download
        ;;
    status)
        python amazon_photos_sync.py status
        ;;
    verify)
        python amazon_photos_sync.py verify
        ;;
    *)
        echo "Usage: $0 {login|enumerate|download|status|verify}"
        echo ""
        echo "Commands:"
        echo "  login      - Authenticate with Amazon (run first)"
        echo "  enumerate  - Scan Amazon Photos library"
        echo "  download   - Download all unique files"
        echo "  status     - Show sync status"
        echo "  verify     - Check for new files"
        exit 1
        ;;
esac
SCRIPT
chmod +x ~/run_sync.sh

# Create tmux session script for long-running tasks
cat > ~/start_download.sh << 'SCRIPT'
#!/bin/bash
tmux new-session -d -s amazon_sync "cd ~/amazonphotossync && source .venv/bin/activate && python amazon_photos_sync.py download"
echo "Download started in tmux session 'amazon_sync'"
echo "Attach with: tmux attach -t amazon_sync"
SCRIPT
chmod +x ~/start_download.sh

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Login to Amazon:"
echo "   ~/run_sync.sh login"
echo ""
echo "2. Enumerate library:"
echo "   ~/run_sync.sh enumerate"
echo ""
echo "3. Start download (in tmux for persistence):"
echo "   ~/start_download.sh"
echo ""
echo "4. Check status:"
echo "   ~/run_sync.sh status"
echo ""
