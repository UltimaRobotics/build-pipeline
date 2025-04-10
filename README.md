# OpenWrt Build Pipeline

An automated CI/CD pipeline for building OpenWrt firmware and custom packages with versioned releases.

## Features

- Automated build system for OpenWrt firmware
- Custom package integration capabilities
- Version tracking and management
- Automated release creation and asset uploads
- Build status monitoring and notifications
- Basic error handling and logging

## Directory Structure

- `.github/workflows/` - GitHub Actions workflow definitions
- `config/` - Configuration files for OpenWrt and packages
- `scripts/` - Python and bash scripts for automation
- `templates/` - Flask templates for the web interface
- `static/` - Static assets for the web interface

## Configuration

### OpenWrt Configuration

Edit `config/openwrt.yml` to configure the OpenWrt build:

```yaml
default_version: "22.03.3"  # Default OpenWrt version

# List of targets to build
targets:
  - name: "x86"
    subtarget: "64"
    description: "Generic x86_64 devices"
    
  # Add more targets as needed...
