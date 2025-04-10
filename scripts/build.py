#!/usr/bin/env python3
"""
Build script for OpenWrt firmware and custom packages
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('build')

def parse_args():
    parser = argparse.ArgumentParser(description='Build OpenWrt firmware and packages')
    parser.add_argument('--target', required=True, help='OpenWrt target (e.g., x86)')
    parser.add_argument('--subtarget', required=True, help='OpenWrt subtarget (e.g., 64)')
    parser.add_argument('--openwrt-version', required=True, help='OpenWrt version to build')
    parser.add_argument('--version', required=True, help='Release version')
    parser.add_argument('--config-dir', default='./config', help='Configuration directory')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    return parser.parse_args()

def load_config(config_dir):
    """Load configuration files"""
    openwrt_config_file = os.path.join(config_dir, 'openwrt.yml')
    packages_config_file = os.path.join(config_dir, 'packages.yml')
    
    with open(openwrt_config_file, 'r') as f:
        openwrt_config = yaml.safe_load(f)
    
    with open(packages_config_file, 'r') as f:
        packages_config = yaml.safe_load(f)
    
    return openwrt_config, packages_config

def setup_openwrt_source(version):
    """Setup OpenWrt source code"""
    if not os.path.exists('openwrt'):
        logger.info(f"Cloning OpenWrt v{version}...")
        subprocess.run([
            'git', 'clone', 'https://git.openwrt.org/openwrt/openwrt.git'
        ], check=True)
        
        os.chdir('openwrt')
        subprocess.run([
            'git', 'checkout', f'v{version}'
        ], check=True)
    else:
        logger.info(f"Using existing OpenWrt source, checking out v{version}...")
        os.chdir('openwrt')
        subprocess.run(['git', 'fetch', '--all'], check=True)
        subprocess.run(['git', 'checkout', f'v{version}'], check=True)
    
    # Update feeds
    subprocess.run(['./scripts/feeds', 'update', '-a'], check=True)
    subprocess.run(['./scripts/feeds', 'install', '-a'], check=True)
    
    os.chdir('..')

def add_custom_package_feeds(packages_config):
    """Add custom package feeds"""
    os.chdir('openwrt')
    
    # Add custom package repositories to feeds.conf
    with open('feeds.conf.default', 'a') as f:
        for repo in packages_config.get('repositories', []):
            feed_line = f"src-git {repo['name']} {repo['url']};{repo['branch']}\n"
            logger.info(f"Adding feed: {feed_line.strip()}")
            f.write(feed_line)
    
    # Update and install all feeds
    subprocess.run(['./scripts/feeds', 'update', '-a'], check=True)
    subprocess.run(['./scripts/feeds', 'install', '-a'], check=True)
    
    os.chdir('..')

def create_config(openwrt_config, packages_config, target, subtarget, version):
    """Create OpenWrt config file (.config)"""
    os.chdir('openwrt')
    
    # Generate default config for target
    logger.info(f"Creating config for {target}/{subtarget}...")
    subprocess.run([
        'make', 'defconfig', 
        f'TARGET={target}', 
        f'SUBTARGET={subtarget}'
    ], check=True)
    
    # Add custom kernel options
    logger.info("Adding kernel configuration options...")
    with open('.config', 'a') as f:
        for option in openwrt_config.get('build', {}).get('kernel_config', []):
            f.write(f"{option}\n")
    
    # Add base packages for all targets
    with open('.config', 'a') as f:
        for package in openwrt_config.get('build', {}).get('base_packages', []):
            f.write(f"CONFIG_PACKAGE_{package}=y\n")
    
    # Add target-specific packages
    with open('.config', 'a') as f:
        # Add packages for all targets
        for package in packages_config.get('include_packages', {}).get('all', []):
            f.write(f"CONFIG_PACKAGE_{package}=y\n")
            
        # Add packages for specific target+subtarget
        target_key = f"{target}_{subtarget}"
        for package in packages_config.get('include_packages', {}).get(target_key, []):
            f.write(f"CONFIG_PACKAGE_{package}=y\n")
    
    # Add custom repository packages
    with open('.config', 'a') as f:
        for repo in packages_config.get('repositories', []):
            for package in repo.get('packages', []):
                f.write(f"CONFIG_PACKAGE_{package}=y\n")
    
    # Exclude packages
    with open('.config', 'a') as f:
        # Exclude packages for all targets
        for package in packages_config.get('exclude_packages', {}).get('all', []):
            f.write(f"# CONFIG_PACKAGE_{package} is not set\n")
            
        # Exclude packages for specific target+subtarget
        target_key = f"{target}_{subtarget}"
        for package in packages_config.get('exclude_packages', {}).get(target_key, []):
            f.write(f"# CONFIG_PACKAGE_{package} is not set\n")
    
    # Set version in the config
    with open('.config', 'a') as f:
        f.write(f'CONFIG_VERSION_NUMBER="{version}"\n')
        f.write(f'CONFIG_VERSION_CODE="{version}"\n')
    
    # Run make defconfig to normalize the config file
    subprocess.run(['make', 'defconfig'], check=True)
    
    os.chdir('..')

def build_firmware(openwrt_config, target, subtarget):
    """Build the OpenWrt firmware"""
    os.chdir('openwrt')
    
    # Get number of parallel jobs from config or default to CPU count
    jobs = openwrt_config.get('build', {}).get('jobs', os.cpu_count())
    
    # Start the build process
    logger.info(f"Building OpenWrt firmware for {target}/{subtarget} with {jobs} jobs...")
    start_time = time.time()
    
    # Create downloads directory if it doesn't exist
    if not os.path.exists('dl'):
        os.makedirs('dl')
    
    # Run the build
    build_cmd = [
        'make', 
        '-j', str(jobs),
        'V=s'  # Verbose output
    ]
    
    try:
        subprocess.run(build_cmd, check=True)
        logger.info(f"Build completed successfully in {time.time() - start_time:.1f} seconds")
    except subprocess.CalledProcessError as e:
        logger.error(f"Build failed: {e}")
        sys.exit(1)
    
    os.chdir('..')

def create_output_directory(target, subtarget, version):
    """Create and organize the output directory"""
    output_dir = f"output/{target}_{subtarget}_{version}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Copy firmware files
    firmware_path = f"openwrt/bin/targets/{target}/{subtarget}"
    for file in os.listdir(firmware_path):
        if file.endswith(('.bin', '.buildinfo', '.manifest')) or file == 'sha256sums':
            shutil.copy(
                os.path.join(firmware_path, file),
                os.path.join(output_dir, file)
            )
    
    # Create a version file
    with open(os.path.join(output_dir, 'version.txt'), 'w') as f:
        f.write(f"OpenWrt Custom Build\n")
        f.write(f"Version: {version}\n")
        f.write(f"Target: {target}\n")
        f.write(f"Subtarget: {subtarget}\n")
        f.write(f"Build date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    logger.info(f"Output saved to {output_dir}")
    return output_dir

def main():
    args = parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    logger.info(f"Starting OpenWrt build process for {args.target}/{args.subtarget}")
    logger.info(f"OpenWrt version: {args.openwrt_version}")
    logger.info(f"Release version: {args.version}")
    
    # Create necessary directories
    os.makedirs('output', exist_ok=True)
    
    # Load configuration
    openwrt_config, packages_config = load_config(args.config_dir)
    
    # Setup and build
    setup_openwrt_source(args.openwrt_version)
    add_custom_package_feeds(packages_config)
    create_config(openwrt_config, packages_config, args.target, args.subtarget, args.version)
    build_firmware(openwrt_config, args.target, args.subtarget)
    output_dir = create_output_directory(args.target, args.subtarget, args.version)
    
    logger.info(f"Build for {args.target}/{args.subtarget} completed successfully")
    logger.info(f"Output saved to {output_dir}")

if __name__ == "__main__":
    main()
