#!/bin/bash
# Setup environment for OpenWrt builds

set -e

echo "Setting up build environment for OpenWrt..."

# Update package lists
sudo apt-get update

# Install required packages for OpenWrt build system
sudo apt-get install -y build-essential clang flex bison g++ gawk \
    gcc-multilib g++-multilib gettext git libncurses-dev libssl-dev \
    python3-distutils rsync unzip zlib1g-dev file wget

# Additional dependencies that might be needed
sudo apt-get install -y libelf-dev quilt ccache fastjar java-propose-classpath

# Create directories
mkdir -p dl
mkdir -p output

echo "Build environment setup completed."
