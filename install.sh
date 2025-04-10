#!/bin/bash
# Installation and deployment script for OpenWrt Build Pipeline

set -e  # Exit on any error

echo "========================================================"
echo " OpenWrt Build Pipeline - Installation and Setup Script "
echo "========================================================"

# Check for required utilities
for cmd in python3 pip git; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: $cmd not found. Please install it and try again."
        exit 1
    fi
done

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install or upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install Flask==2.3.3 Flask-SQLAlchemy==3.1.1 SQLAlchemy==2.0.23 gunicorn==21.2.0 PyYAML==6.0.1 GitPython==3.1.40 psycopg2-binary==2.9.9 requests==2.31.0 semver==3.0.2 Werkzeug==2.3.7 email-validator==2.1.0

# Initialize PostgreSQL database if not set via environment variables
if [ -z "$DATABASE_URL" ]; then
    echo "Warning: DATABASE_URL is not set. Using default SQLite database."
    echo "For production use, please set DATABASE_URL environment variable."
    export DATABASE_URL="sqlite:///instance/openwrt_builds.db"
fi

# Create configuration directories if needed
mkdir -p instance
mkdir -p config

# Check if config files exist, otherwise create defaults
if [ ! -f "config/openwrt.yml" ]; then
    echo "Creating default OpenWrt configuration..."
    cat > config/openwrt.yml << EOF
# OpenWrt build configuration
default_version: "23.05.0"  # Default OpenWrt version

# List of targets to build
targets:
  - name: "x86"
    subtarget: "64"
    description: "Generic x86_64 devices"
    subtargets:
      - name: "64"
        description: "64-bit (x86_64)"
        profiles:
          - name: "generic"
            description: "Generic x86_64"
          - name: "kvm_guest"
            description: "KVM Guest"
      - name: "generic"
        description: "Generic 32-bit (i386)"
        profiles:
          - name: "generic"
            description: "Generic i386"
  
  - name: "bcm27xx"
    subtarget: "bcm2711"
    description: "Raspberry Pi 4 Model B"
    subtargets:
      - name: "bcm2711"
        description: "BCM2711 boards (Raspberry Pi 4)"
        profiles:
          - name: "rpi-4"
            description: "Raspberry Pi 4 Model B"
      - name: "bcm2710"
        description: "BCM2710 boards (Raspberry Pi 3)"
        profiles:
          - name: "rpi-3"
            description: "Raspberry Pi 3 Model B/B+"

# Build settings
build:
  jobs: 4  # Number of parallel jobs for make
  kernel_config: # Custom kernel config options
    - "CONFIG_PACKAGE_kmod-usb-storage=y"
    - "CONFIG_PACKAGE_kmod-fs-ext4=y"
    - "CONFIG_PACKAGE_kmod-usb3=y"
  
  # Base packages to include in all builds
  base_packages:
    - "luci"
    - "luci-ssl"
    - "luci-app-opkg"
    - "luci-app-firewall"
    - "openssh-sftp-server"
EOF
fi

if [ ! -f "config/packages.yml" ]; then
    echo "Creating default packages configuration..."
    cat > config/packages.yml << EOF
# Custom packages configuration

# Git repositories with custom packages
repositories:
  - name: "example-packages"
    url: "https://github.com/example/openwrt-packages.git"
    branch: "main"
    packages:
      - "example-package-1"
      - "example-package-2"

# Packages to include in builds
include_packages:
  all:  # Packages to include in all builds
    - "curl"
    - "wget"
    - "htop"
    - "nano"
    
  x86_64:  # Packages specific to x86_64 builds
    - "qemu-ga"
    - "kmod-vmxnet3"
    
  bcm27xx_bcm2711:  # Packages specific to Raspberry Pi 4
    - "kmod-usb-net"
    - "kmod-usb-net-rtl8152"

# Packages to exclude from builds
exclude_packages:
  all:  # Packages to exclude from all builds
    - "ppp"
    - "ppp-mod-pppoe"
EOF
fi

# Create database tables
echo "Initializing database..."
export FLASK_APP=main.py
flask shell <<EOF
from app import db
db.create_all()
exit()
EOF

# Done!
echo ""
echo "Installation complete!"
echo ""
echo "To run the application:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Start the application: gunicorn --bind 0.0.0.0:5000 main:app"
echo ""
echo "For development, you can use: flask run --host=0.0.0.0"
echo ""

# Check if we're in a git repository
if [ -d ".git" ]; then
    echo "Git repository already initialized."
else
    echo "Initializing git repository..."
    git init
    echo "Adding remote repository..."
    git remote add origin https://github.com/UltimaRobotics/build-pipeline.git
fi

# Create .gitignore file
if [ ! -f ".gitignore" ]; then
    echo "Creating .gitignore file..."
    cat > .gitignore << EOF
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
ENV/
env/
.env
*.egg-info/

# Flask
instance/
.webassets-cache

# Development
.idea/
.vscode/
*.swp
*.swo

# Database
*.db
*.sqlite

# Logs
logs/
*.log

# OS specific
.DS_Store
Thumbs.db
EOF
fi

# Make script executable
chmod +x install.sh

echo "Installation script created with execute permissions."