#!/usr/bin/env python3
"""
ArieoEngine Package Installer
Handles installing packages by executing install_commands from arieo_package.json
"""

import os
import shutil
import subprocess
import sys


def install_package(src_path, package_data, package_name, package_version, env):
    """
    Install a package by executing its install_commands
    
    Args:
        src_path: Resolved package source path
        package_data: Loaded arieo_package.json data
        package_name: Package name
        package_version: Package version
        env: Pre-configured environment variables dictionary
        
    Returns:
        bool: True if successful
    """
    print(f"Installing package: {package_name} v{package_version}")
    print(f"Source folder: {src_path}")
    
    install_commands = package_data.get('install_commands', [])
    
    if not install_commands:
        print(f"  ⊘ No install_commands defined, skipping")
        return True
    
    original_cwd = os.getcwd()
    try:
        os.chdir(src_path)
        
        print(f"\n=== Install Stage ===")
        for idx, install_command in enumerate(install_commands, 1):
            print(f"[{idx}/{len(install_commands)}] {install_command}")
            result = subprocess.run(
                install_command,
                shell=True,
                capture_output=False,
                text=True,
                env=env
            )
            
            if result.returncode != 0:
                error_msg = f"✗ Install command failed: {install_command}"
                print(error_msg)
                os.chdir(original_cwd)
                sys.exit(1)
        
        os.chdir(original_cwd)
        print(f"✓ Install completed for {package_name}")
        return True
        
    except Exception as e:
        os.chdir(original_cwd)
        error_msg = f"✗ Error executing install commands: {e}"
        print(error_msg)
        sys.exit(1)
