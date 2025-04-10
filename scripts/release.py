#!/usr/bin/env python3
"""
Create GitHub release and upload firmware assets
"""

import argparse
import glob
import hashlib
import logging
import os
import sys

import requests
import yaml

logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('release')

def parse_args():
    parser = argparse.ArgumentParser(description='Create GitHub release and upload assets')
    parser.add_argument('--version', required=True, help='Release version')
    parser.add_argument('--artifacts-dir', required=True, help='Directory containing build artifacts')
    parser.add_argument('--config-dir', default='./config', help='Configuration directory')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    return parser.parse_args()

def load_config(config_dir):
    """Load configuration files"""
    openwrt_config_file = os.path.join(config_dir, 'openwrt.yml')
    
    with open(openwrt_config_file, 'r') as f:
        openwrt_config = yaml.safe_load(f)
    
    return openwrt_config

def create_checksums(artifacts_dir):
    """Create SHA256 checksums for all firmware files"""
    checksum_file = os.path.join(artifacts_dir, 'sha256sums.txt')
    checksums = {}
    
    with open(checksum_file, 'w') as f:
        for root, _, files in os.walk(artifacts_dir):
            for file in files:
                if file.endswith(('.bin', '.buildinfo', '.manifest')):
                    file_path = os.path.join(root, file)
                    sha256 = hashlib.sha256()
                    with open(file_path, 'rb') as bin_file:
                        for chunk in iter(lambda: bin_file.read(4096), b''):
                            sha256.update(chunk)
                    checksum = sha256.hexdigest()
                    checksums[file] = checksum
                    f.write(f"{checksum}  {file}\n")
    
    logger.info(f"Created checksums file: {checksum_file}")
    return checksum_file, checksums

def create_release_notes(version, openwrt_config, artifacts_dir, checksums):
    """Create release notes markdown file"""
    notes_file = os.path.join(artifacts_dir, 'release_notes.md')
    
    with open(notes_file, 'w') as f:
        f.write(f"# OpenWrt Custom Build v{version}\n\n")
        f.write(f"OpenWrt Version: {openwrt_config.get('default_version', 'unknown')}\n\n")
        
        f.write("## Included Targets\n\n")
        for target in openwrt_config.get('targets', []):
            f.write(f"- **{target['name']}/{target['subtarget']}**: {target.get('description', '')}\n")
        
        f.write("\n## Included Packages\n\n")
        if 'build' in openwrt_config and 'base_packages' in openwrt_config['build']:
            for package in openwrt_config['build']['base_packages']:
                f.write(f"- {package}\n")
        
        f.write("\n## Firmware Files\n\n")
        for file, checksum in checksums.items():
            if file.endswith('.bin'):
                f.write(f"- **{file}** - SHA256: `{checksum}`\n")
        
        f.write("\n## Installation\n\n")
        f.write("Please follow the official OpenWrt documentation for flashing instructions:\n")
        f.write("https://openwrt.org/docs/guide-user/installation/start\n\n")
        
        f.write("## Verification\n\n")
        f.write("To verify the downloaded firmware files, run:\n\n")
        f.write("```bash\n")
        f.write("sha256sum -c sha256sums.txt\n")
        f.write("```\n")
    
    logger.info(f"Created release notes: {notes_file}")
    return notes_file

def create_github_release(version, release_notes_file, artifacts_dir):
    """Create GitHub release and upload assets"""
    # Get GitHub token from environment
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable not set")
        sys.exit(1)
    
    # Get repository info from GitHub Actions environment
    github_repository = os.environ.get('GITHUB_REPOSITORY', '')
    if not github_repository:
        logger.error("GITHUB_REPOSITORY environment variable not set")
        sys.exit(1)
    
    # GitHub API endpoints
    api_url = f"https://api.github.com/repos/{github_repository}"
    releases_url = f"{api_url}/releases"
    
    # Read release notes
    with open(release_notes_file, 'r') as f:
        release_notes = f.read()
    
    # Create release
    logger.info(f"Creating GitHub release for version {version}")
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    release_data = {
        'tag_name': f'v{version}',
        'name': f'OpenWrt Custom Build v{version}',
        'body': release_notes,
        'draft': False,
        'prerelease': '-' in version  # Treat versions with hyphen as pre-releases
    }
    
    response = requests.post(releases_url, headers=headers, json=release_data)
    if response.status_code not in (200, 201):
        logger.error(f"Failed to create release: {response.status_code} {response.text}")
        sys.exit(1)
    
    release_info = response.json()
    release_id = release_info['id']
    upload_url = release_info['upload_url'].split('{')[0]
    
    logger.info(f"Release created successfully. ID: {release_id}")
    
    # Upload assets
    for root, _, files in os.walk(artifacts_dir):
        for file in files:
            if file.endswith(('.bin', '.buildinfo', '.manifest', 'sha256sums.txt')):
                file_path = os.path.join(root, file)
                logger.info(f"Uploading asset: {file}")
                
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                
                headers['Content-Type'] = 'application/octet-stream'
                asset_url = f"{upload_url}?name={file}"
                response = requests.post(
                    asset_url,
                    headers=headers,
                    data=file_data
                )
                
                if response.status_code not in (200, 201):
                    logger.warning(f"Failed to upload asset {file}: {response.status_code} {response.text}")
                else:
                    logger.info(f"Successfully uploaded {file}")
    
    logger.info(f"Release process completed for version {version}")
    return release_info['html_url']

def main():
    args = parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    logger.info(f"Starting release process for version {args.version}")
    
    # Load configuration
    openwrt_config = load_config(args.config_dir)
    
    # Process artifacts
    checksum_file, checksums = create_checksums(args.artifacts_dir)
    release_notes_file = create_release_notes(args.version, openwrt_config, args.artifacts_dir, checksums)
    
    # Create GitHub release
    release_url = create_github_release(args.version, release_notes_file, args.artifacts_dir)
    
    logger.info(f"Release available at: {release_url}")

if __name__ == "__main__":
    main()
