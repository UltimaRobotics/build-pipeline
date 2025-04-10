# OpenWrt Build Pipeline

An automated CI/CD pipeline for building OpenWrt firmware and custom packages with versioned releases.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

## Features

- **Automated Builds**: Schedule and run OpenWrt firmware builds automatically
- **Custom Packages**: Add and manage custom package repositories
- **Target Selection**: Build for multiple hardware targets (x86_64, Raspberry Pi, etc.)
- **Web Dashboard**: Monitor build progress and view build logs
- **Versioned Releases**: Automatically create GitHub releases with artifacts
- **Package Management**: Select and configure packages to include in builds

## Quick Start

```bash
# Clone the repository
git clone https://github.com/UltimaRobotics/build-pipeline.git
cd build-pipeline

# Run the installation script
chmod +x install.sh
./install.sh

# Start the server
gunicorn --bind 0.0.0.0:5000 main:app
```

## Requirements

- Python 3.8+
- PostgreSQL (recommended) or SQLite
- Git

## Environment Variables

The application uses the following environment variables:

- `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://user:password@localhost/openwrt_builds`)
- `FLASK_SECRET_KEY`: Secret key for session encryption
- `WEBHOOK_SECRET`: Secret token for webhook validation
- `GITHUB_TOKEN`: GitHub token for API access (optional)

## Configuration

Configuration is stored in YAML files in the `config` directory:

- `openwrt.yml`: OpenWrt build targets and default settings
- `packages.yml`: Package repositories and package selection

## Documentation

The web interface provides documentation and examples for configuring builds and packages.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.