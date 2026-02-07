#!/usr/bin/env python3
"""
ArieoEngine Package Builder
Handles building packages by executing build_commands from arieo_package.json
"""

import os
import subprocess
import sys


def build_package(src_path, package_data, package_name, package_version, env):
    """
    Build a package by executing its build_commands
    
    Args:
        src_path: Resolved package source path
        package_data: Loaded arieo_package.json data
        package_name: Package name
        package_version: Package version
        env: Pre-configured environment variables dictionary
        
    Returns:
        bool: True if successful
    """
    print(f"Building package: {package_name} v{package_version}")
    print(f"Source folder: {src_path}")
    
    build_commands = package_data.get('build_commands', [])
    
    if not build_commands:
        print(f"  ⊘ No build_commands defined, skipping")
        return True
    
    original_cwd = os.getcwd()
    try:
        os.chdir(src_path)
        
        # Set ARIEO_BUILDENV_BUILD_FOLDER from ARIEO_CUR_PACKAGE_BUILD_FOLDER if available
        if 'ARIEO_CUR_PACKAGE_BUILD_FOLDER' in env:
            env['ARIEO_BUILDENV_BUILD_FOLDER'] = env['ARIEO_CUR_PACKAGE_BUILD_FOLDER']
            print(f"  Setting ARIEO_BUILDENV_BUILD_FOLDER: {env['ARIEO_BUILDENV_BUILD_FOLDER']}")
        
        print(f"\n=== Build Stage ===")
        for idx, build_command in enumerate(build_commands, 1):
            # Expand environment variables for cross-platform compatibility
            # Support both $VAR, ${VAR} and $ENV{VAR} (CMake-style) syntax
            import re
            
            # Merge process environment with package environment for expansion
            full_env = os.environ.copy()
            full_env.update(env)
            
            # Manually expand variables for cross-platform compatibility
            expanded_command = build_command
            for key, value in full_env.items():
                expanded_command = expanded_command.replace(f'$ENV{{{key}}}', str(value))
                expanded_command = expanded_command.replace(f'${{{key}}}', str(value))
                expanded_command = expanded_command.replace(f'${key}', str(value))
            
            print(f"[{idx}/{len(build_commands)}] {expanded_command}")
            result = subprocess.run(
                expanded_command,
                shell=True,
                capture_output=False,
                env=full_env,
                cwd=src_path
            )
            
            if result.returncode != 0:
                error_msg = f"✗ Build command failed: {build_command}"
                print(error_msg)
                os.chdir(original_cwd)
                sys.exit(1)
        
        os.chdir(original_cwd)
        print(f"✓ Build completed for {package_name}")
        return True
        
    except Exception as e:
        os.chdir(original_cwd)
        error_msg = f"✗ Error executing build commands: {e}"
        print(error_msg)
        sys.exit(1)
