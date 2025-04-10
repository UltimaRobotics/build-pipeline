#!/usr/bin/env python3
"""
Version management script for OpenWrt builds
"""

import os
import re
import sys
from datetime import datetime

import git
import semver

def get_current_version():
    """
    Determine the current version based on git tags and commits
    Returns a SemVer compatible version string
    """
    try:
        repo = git.Repo(os.getcwd())
    except git.exc.InvalidGitRepositoryError:
        print("Error: Not a valid git repository", file=sys.stderr)
        return "0.1.0"
    
    # Get the latest tag
    try:
        tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)
        latest_tag = tags[-1] if tags else None
    except IndexError:
        latest_tag = None
    
    # If we have a tag, use it as base
    if latest_tag:
        tag_name = str(latest_tag)
        # Remove 'v' prefix if present
        if tag_name.startswith('v'):
            tag_name = tag_name[1:]
        
        # Check if it's a valid SemVer
        try:
            version_info = semver.VersionInfo.parse(tag_name)
            base_version = str(version_info)
        except ValueError:
            # Not a valid SemVer, fallback to default
            base_version = "0.1.0"
    else:
        # No tags found, start with 0.1.0
        base_version = "0.1.0"
    
    # Count commits since the tag
    if latest_tag:
        commit_count = sum(1 for _ in repo.iter_commits(f"{latest_tag}..HEAD"))
    else:
        commit_count = len(list(repo.iter_commits()))
    
    # If we're exactly on a tag, just return that version
    if commit_count == 0 and latest_tag:
        return base_version
    
    # Generate a development version with commit count
    # SemVer format: MAJOR.MINOR.PATCH-[pre-release]+[build]
    version_parts = base_version.split('.')
    
    # Increment patch version
    if len(version_parts) >= 3:
        patch_version = version_parts[2]
        # If patch version contains pre-release info, strip it
        match = re.match(r'^(\d+).*$', patch_version)
        if match:
            patch_number = int(match.group(1))
            version_parts[2] = str(patch_number)
    
    # Construct new version
    base_version = '.'.join(version_parts)
    
    # Add build metadata with commit count and date
    date_str = datetime.now().strftime("%Y%m%d")
    
    # Get short SHA
    sha = repo.head.commit.hexsha[:7]
    
    if commit_count > 0:
        # If we have commits since the tag, this is a development version
        pre_release = f"dev.{commit_count}"
        build_meta = f"{date_str}.{sha}"
        version = f"{base_version}-{pre_release}+{build_meta}"
    else:
        # Otherwise just add the build metadata
        build_meta = f"{date_str}.{sha}"
        version = f"{base_version}+{build_meta}"
    
    return version

if __name__ == "__main__":
    version = get_current_version()
    print(version)
