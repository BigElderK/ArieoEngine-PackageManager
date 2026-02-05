#!/usr/bin/env python3
"""
ArieoEngine Package Builder
Handles building and installation of packages from package.lock.json
"""

import argparse
import json
import os
import re
import subprocess
import sys
from itertools import product
from pathlib import Path


def install_package_from_src_folder(src_folder, output_folder=None, env_vars_map=None):
    """
    Install a package from a source folder containing package.json
    
    Args:
        src_folder: Path to the package source folder (relative or absolute)
        output_folder: Path to the output folder (sets OUTPUT_FOLDER env var)
        env_vars_map: Dict mapping environment variable names to values
    """
    # Convert to Path object and resolve to absolute path
    src_path = Path(src_folder).resolve()
    
    if not src_path.exists():
        error_msg = f"✗ Error: Source folder does not exist: {src_path}"
        print(error_msg)
        sys.exit(1)
    
    # Look for package.json
    package_json_path = src_path / "arieo_package.json"
    if not package_json_path.exists():
        error_msg = f"✗ Error: arieo_package.json not found in {src_path}"
        print(error_msg)
        sys.exit(1)
    
    # Read package.json
    try:
        with open(package_json_path, 'r', encoding='utf-8') as f:
            package_data = json.load(f)
    except Exception as e:
        error_msg = f"✗ Error: Failed to read arieo_package.json: {e}"
        print(error_msg)
        sys.exit(1)
    
    package_name = package_data.get('name', 'unknown')
    package_version = package_data.get('version', '0.0.0')
    
    print(f"Installing package: {package_name} v{package_version}")
    print(f"Source folder: {src_path}")
    
    # Check if build_commands exists
    build_commands = package_data.get('build_commands', [])
    if not build_commands:
        print(f"Warning: No build_commands specified in arieo_package.json")
        return True
    
    # Execute build commands in the package directory
    try:
        # Change to package directory
        original_cwd = os.getcwd()
        os.chdir(src_path)
        
        # Set up environment variables
        env = os.environ.copy()
        
        # Apply all environment variables from the map
        if env_vars_map:
            for env_name, env_value in env_vars_map.items():
                env[env_name] = env_value
                print(f"  {env_name}={env_value}")
        
        # Legacy support: also set OUTPUT_FOLDER if provided directly
        if output_folder and (not env_vars_map or 'OUTPUT_FOLDER' not in env_vars_map):
            # Resolve to absolute path
            output_path = Path(output_folder).resolve()
            env['OUTPUT_FOLDER'] = str(output_path)
            print(f"  OUTPUT_FOLDER={output_path}")
        
        # Execute each build command
        for idx, build_command in enumerate(build_commands, 1):
            print(f"Executing command {idx}/{len(build_commands)}: {build_command}")
            result = subprocess.run(
                build_command,
                shell=True,
                capture_output=False,
                text=True,
                env=env
            )
            
            if result.returncode != 0:
                error_msg = f"✗ Failed to execute command {idx}: {build_command}"
                print(error_msg)
                os.chdir(original_cwd)
                sys.exit(1)
        
        # Restore original directory
        os.chdir(original_cwd)
        print(f"✓ Successfully installed {package_name}")
        return True
            
    except Exception as e:
        os.chdir(original_cwd)
        error_msg = f"✗ Error executing install command: {e}"
        print(error_msg)
        sys.exit(1)


def install_packages_from_lock(lock_file_path, package_filter=None, extra_env_vars=None):
    """
    Install packages based on package.lock.json
    
    Args:
        lock_file_path: Path to the lock file
        package_filter: Optional list of package names to build (builds all if None)
        extra_env_vars: Optional dict of additional environment variables to set
    """
    try:
        with open(lock_file_path, 'r', encoding='utf-8') as f:
            lock_data = json.load(f)
    except Exception as e:
        error_msg = f"✗ Error: Failed to read package.lock.json: {e}"
        print(error_msg)
        sys.exit(1)
    
    install_order = lock_data.get('install_order', [])
    packages = lock_data.get('packages', {})
    
    # Filter packages if requested
    if package_filter:
        install_order = [pkg for pkg in install_order if pkg in package_filter]
        if not install_order:
            error_msg = f"✗ Error: None of the specified packages found in lock file"
            print(error_msg)
            print(f"  Requested: {', '.join(package_filter)}")
            print(f"  Available: {', '.join(packages.keys())}")
            sys.exit(1)
    
    # Sort packages by build_index to ensure correct build order
    install_order.sort(key=lambda pkg_name: packages[pkg_name].get('build_index', 999))
    
    # Gather all environment variables from all packages into a single map
    global_env_vars_map = {}
    for pkg_name, pkg_info in packages.items():
        environment_variables = pkg_info.get('environment_variables', [])
        for env_var in environment_variables:
            env_name = env_var.get('name')
            env_value = env_var.get('value')
            if env_name and env_value:
                global_env_vars_map[env_name] = env_value
    
    # Add extra environment variables from command line
    if extra_env_vars:
        global_env_vars_map.update(extra_env_vars)
    
    for idx, pkg_name in enumerate(install_order, 1):
        if pkg_name not in packages:
            error_msg = f"✗ Error: Package {pkg_name} not found in lock file"
            print(error_msg)
            sys.exit(1)
        
        pkg_info = packages[pkg_name]
        
        print(f"\n[{idx}/{len(install_order)}] Building {pkg_name} (tag: {pkg_info['tag']})")
        print("-" * 60)
        
        source_folder = pkg_info['source_folder']
        output_folder = pkg_info['output_folder']
        
        install_package_from_src_folder(source_folder, output_folder, global_env_vars_map)


def build_all_packages(lock_file_path=None, manifest_file_path=None, package_filter=None, extra_env_vars=None):
    """
    Build all packages from package.lock.json for all combinations of environment variables
    
    Args:
        lock_file_path: Optional path to lock file. If not provided, derives from manifest or uses default
        manifest_file_path: Optional path to package manifest file
        package_filter: Optional list of package names to build (builds all if None)
        extra_env_vars: Optional dict of additional environment variables to set (can contain lists for multi-value)
    """
    # If no lock file specified, try to derive from manifest
    if not lock_file_path:
        # Try to load from specified or default manifest file
        if not manifest_file_path:
            manifest_file_path = "package.manifest.json"
        
        manifest_path = Path(manifest_file_path)
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                packages_output_folder = manifest.get('packages_output_folder', './_packages/published')
                lock_file_path = Path(packages_output_folder) / "package.lock.json"
            except Exception:
                pass
        
        # Fallback to default location
        if not lock_file_path or not Path(lock_file_path).exists():
            lock_file_path = "engine_packages/package.lock.json"
    
    lock_path = Path(lock_file_path)
    if not lock_path.exists():
        error_msg = f"✗ Error: package.lock.json not found at {lock_path}"
        print(error_msg)
        print("\nPlease run init_packages.py first to download packages and generate the lock file.")
        sys.exit(1)
    
    print("ArieoEngine Package Builder")
    print("=" * 60)
    print(f"Lock file: {lock_path.resolve()}")
    
    if package_filter:
        print(f"Package filter: {', '.join(package_filter)}")
    
    # Load lock file to get package information
    try:
        with open(lock_path, 'r', encoding='utf-8') as f:
            lock_data = json.load(f)
    except Exception as e:
        error_msg = f"✗ Error: Failed to read package.lock.json: {e}"
        print(error_msg)
        sys.exit(1)
    
    install_order = lock_data.get('install_order', [])
    packages = lock_data.get('packages', {})
    
    # Filter packages if requested
    if package_filter:
        install_order = [pkg for pkg in install_order if pkg in package_filter]
        if not install_order:
            error_msg = f"✗ Error: None of the specified packages found in lock file"
            print(error_msg)
            print(f"  Requested: {', '.join(package_filter)}")
            print(f"  Available: {', '.join(packages.keys())}")
            sys.exit(1)
    
    # Sort packages by build_index to ensure correct build order
    install_order.sort(key=lambda pkg_name: packages[pkg_name].get('build_index', 999))
    
    # Generate all combinations of environment variables
    env_combinations = generate_env_combinations(extra_env_vars) if extra_env_vars else [{}]
    
    print(f"\n{'='*60}")
    print("BUILD CONFIGURATION")
    print(f"{'='*60}")
    
    if extra_env_vars:
        print("Environment variables:")
        for key, value in extra_env_vars.items():
            if isinstance(value, list):
                print(f"  {key} = [{', '.join(value)}]  ({len(value)} values)")
            else:
                print(f"  {key} = {value}")
    
    print(f"\nTotal combinations: {len(env_combinations)}")
    
    print(f"\nPending build packages ({len(install_order)}):")
    for idx, pkg_name in enumerate(install_order, 1):
        pkg_info = packages[pkg_name]
        build_index = pkg_info.get('build_index') or pkg_info.get('install_index') or idx
        print(f"  [{build_index}] {pkg_name}")
    
    print(f"\nTotal builds: {len(env_combinations)} × {len(install_order)} = {len(env_combinations) * len(install_order)}")
    
    print(f"\n{'='*60}")
    input("Press Enter to start building...")
    
    # Build packages for each combination
    for combo_idx, env_combo in enumerate(env_combinations, 1):
        print(f"\n{'#'*60}")
        print(f"BUILDING COMBINATION {combo_idx}/{len(env_combinations)}")
        print(f"{'#'*60}")
        
        for key, value in env_combo.items():
            print(f"  {key} = {value}")
        
        print(f"{'#'*60}")
        
        # Build packages from lock file with this environment combination
        install_packages_from_lock(str(lock_path), package_filter, env_combo)
    
    print(f"\n{'='*60}")
    print(f"✓ All {len(env_combinations)} combinations built successfully")
    print(f"{'='*60}")


def parse_env_args(args):
    """
    Parse environment variable arguments in multiple formats:
    - Single value: --env{VAR_NAME}=value
    - Array syntax: --env{VAR_NAME}=[value1, value2, ...]
    - Repeated keys: --env{VAR_NAME}=value1 --env{VAR_NAME}=value2 ...
    
    Args:
        args: List of command-line arguments
        
    Returns:
        dict: Dictionary of environment variable names to values (string or list of strings)
    """
    env_vars = {}
    env_pattern = re.compile(r'^--env\{([^}]+)\}=(.*)$')
    
    for arg in args:
        match = env_pattern.match(arg)
        if match:
            var_name = match.group(1)
            var_value = match.group(2).strip()
            
            # Check if value is an array [value1, value2, ...]
            if var_value.startswith('[') and var_value.endswith(']'):
                # Parse array values
                array_content = var_value[1:-1].strip()
                if array_content:
                    # Split by comma and strip whitespace from each value
                    values = [v.strip() for v in array_content.split(',')]
                    env_vars[var_name] = values
                else:
                    env_vars[var_name] = []
            else:
                # Check if this variable already exists (repeated key syntax)
                if var_name in env_vars:
                    # Convert to list if not already
                    if not isinstance(env_vars[var_name], list):
                        env_vars[var_name] = [env_vars[var_name]]
                    # Append new value
                    env_vars[var_name].append(var_value)
                else:
                    # First occurrence - store as single value
                    env_vars[var_name] = var_value
    
    return env_vars


def generate_env_combinations(env_vars):
    """
    Generate all combinations of environment variables where some may have multiple values.
    
    Args:
        env_vars: Dict where values can be either strings or lists of strings
        
    Returns:
        List of dicts, each representing one combination of environment variables
    """
    if not env_vars:
        return [{}]
    
    # Separate variables with single values from those with multiple values
    multi_value_vars = {}
    single_value_vars = {}
    
    for key, value in env_vars.items():
        if isinstance(value, list):
            multi_value_vars[key] = value
        else:
            single_value_vars[key] = value
    
    # If no multi-value variables, return single combination
    if not multi_value_vars:
        return [env_vars.copy()]
    
    # Generate all combinations of multi-value variables
    var_names = list(multi_value_vars.keys())
    value_lists = [multi_value_vars[name] for name in var_names]
    
    combinations = []
    for value_combo in product(*value_lists):
        # Start with single-value variables
        combo_dict = single_value_vars.copy()
        # Add this combination of multi-value variables
        for var_name, var_value in zip(var_names, value_combo):
            combo_dict[var_name] = var_value
        combinations.append(combo_dict)
    
    return combinations


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='ArieoEngine Package Builder',
        epilog='''
Examples:
  # Build all packages
  python build_packages.py
  
  # Build specific packages
  python build_packages.py --package=ArieoEngine-BuildEnv --package=ArieoEngine-ThirdParties
  
  # Build with custom environment variables
  python build_packages.py --env{ARIEO_PACKAGE_BUILDENV_HOST_PRESET}=windows.x86_64 --env{ARIEO_PACKAGE_BUILDENV_HOST_BUILD_TYPE}=Release
  
  # Build with multi-value environment variables (builds all combinations)
  python build_packages.py --env{ARIEO_PACKAGE_BUILDENV_HOST_PRESET}=[windows.x86_64, ubuntu.x86_64] --env{ARIEO_PACKAGE_BUILDENV_HOST_BUILD_TYPE}=[Release, Debug]
  
  # Build with repeated environment variables (builds all combinations)
  python build_packages.py --env{ARIEO_PACKAGE_BUILDENV_HOST_PRESET}=windows.x86_64 --env{ARIEO_PACKAGE_BUILDENV_HOST_PRESET}=ubuntu.x86_64 --env{ARIEO_PACKAGE_BUILDENV_HOST_BUILD_TYPE}=Release --env{ARIEO_PACKAGE_BUILDENV_HOST_BUILD_TYPE}=Debug
  
  # Combine package filter and environment variables
  python build_packages.py --package=ArieoEngine-BuildEnv --env{ARIEO_PACKAGE_BUILDENV_HOST_PRESET}=windows.x86_64
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--package',
        action='append',
        dest='packages',
        help='Package name to build (can be specified multiple times). If not specified, builds all packages.'
    )
    
    parser.add_argument(
        '--lock-file',
        dest='lock_file',
        default=None,
        help='Path to package.lock.json (optional, will search default locations if not provided)'
    )
    
    parser.add_argument(
        '--manifest',
        dest='manifest_file',
        default=None,
        help='Path to package.manifest.json (optional, defaults to package.manifest.json in current directory)'
    )
    
    # Parse known args to handle --env{VAR}=value format
    args, unknown = parser.parse_known_args()
    
    # Parse environment variables from unknown args
    extra_env_vars = parse_env_args(unknown)
    
    # Check if there are any unrecognized arguments (not env variables)
    unrecognized = [arg for arg in unknown if not re.match(r'^--env\{[^}]+\}=', arg)]
    if unrecognized:
        parser.error(f"unrecognized arguments: {' '.join(unrecognized)}")
    
    # Build packages
    build_all_packages(args.lock_file, args.manifest_file, args.packages, extra_env_vars)
    sys.exit(0)
