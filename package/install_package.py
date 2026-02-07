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
            # Expand environment variables for cross-platform compatibility
            # Support both $VAR, ${VAR} and $ENV{VAR} (CMake-style) syntax
            import re
            
            # Merge process environment with package environment for expansion
            full_env = os.environ.copy()
            full_env.update(env)
            
            # Manually expand variables for cross-platform compatibility
            expanded_command = install_command
            for key, value in full_env.items():
                expanded_command = expanded_command.replace(f'$ENV{{{key}}}', str(value))
                expanded_command = expanded_command.replace(f'${{{key}}}', str(value))
                expanded_command = expanded_command.replace(f'${key}', str(value))
            
            print(f"[{idx}/{len(install_commands)}] {expanded_command}")
            result = subprocess.run(
                expanded_command,
                shell=True,
                capture_output=False,
                env=full_env,
                cwd=src_path
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
