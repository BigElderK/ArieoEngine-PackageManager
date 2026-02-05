#!/usr/bin/env python3
"""
ArieoEngine Package Processor
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
import yaml

# Add script directory to path for imports
_script_dir = Path(__file__).parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from build_package import build_package
from install_package import install_package


def load_package_data(src_folder):
    """
    Load package data from arieo_package.json
    
    Args:
        src_folder: Path to the package source folder
        
    Returns:
        tuple: (src_path, package_data, package_name, package_version)
    """
    src_path = Path(src_folder).resolve()
    
    if not src_path.exists():
        error_msg = f"✗ Error: Source folder does not exist: {src_path}"
        print(error_msg)
        sys.exit(1)
    
    package_json_path = src_path / "arieo_package.json"
    if not package_json_path.exists():
        error_msg = f"✗ Error: arieo_package.json not found in {src_path}"
        print(error_msg)
        sys.exit(1)
    
    try:
        with open(package_json_path, 'r', encoding='utf-8') as f:
            package_data = json.load(f)
    except Exception as e:
        error_msg = f"✗ Error: Failed to read arieo_package.json: {e}"
        print(error_msg)
        sys.exit(1)
    
    package_name = package_data.get('name', 'unknown')
    package_version = package_data.get('version', '0.0.0')
    
    return src_path, package_data, package_name, package_version


def setup_environment(src_path, build_folder, install_folder, env_vars_map):
    """
    Setup environment variables for package build/install
    
    Args:
        src_path: Resolved source path
        build_folder: Build folder path
        install_folder: Install folder path
        env_vars_map: Additional environment variables
        
    Returns:
        dict: Environment variables dictionary
    """
    env = os.environ.copy()
    
    env['SOURCE_FOLDER'] = str(src_path)
    print(f"  SOURCE_FOLDER={src_path}")
    
    if build_folder:
        build_path = Path(build_folder).resolve()
        env['BUILD_FOLDER'] = str(build_path)
        print(f"  BUILD_FOLDER={build_path}")
    
    if install_folder:
        install_path = Path(install_folder).resolve()
        env['INSTALL_FOLDER'] = str(install_path)
        print(f"  INSTALL_FOLDER={install_path}")
    
    if env_vars_map:
        for env_name, env_value in env_vars_map.items():
            env[env_name] = env_value
            print(f"  {env_name}={env_value}")
    
    return env


def process_packages_from_lock(lock_file_path, package_filter=None, extra_env_vars=None, stage='build_and_install'):
    """
    Process (build and/or install) packages based on package.lock.json
    
    Args:
        lock_file_path: Path to the lock file
        package_filter: Optional list of package names to process (processes all if None)
        extra_env_vars: Optional dict of additional environment variables to set
        stage: Which stage to execute - 'build', 'install', or 'build_and_install'
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
    
    # Gather all public environment variables from all packages
    public_env_vars_map = {}
    for pkg_name, pkg_info in packages.items():
        environment_variables = pkg_info.get('environment_variables', [])
        for env_var in environment_variables:
            env_type = env_var.get('type', 'public')  # Default to public if not specified
            env_name = env_var.get('name')
            env_value = env_var.get('value')
            if env_type == 'public' and env_name and env_value:
                public_env_vars_map[env_name] = env_value
    
    # Add extra environment variables from command line (treated as public)
    if extra_env_vars:
        public_env_vars_map.update(extra_env_vars)
    
    for idx, pkg_name in enumerate(install_order, 1):
        if pkg_name not in packages:
            error_msg = f"✗ Error: Package {pkg_name} not found in lock file"
            print(error_msg)
            sys.exit(1)
        
        pkg_info = packages[pkg_name]
        
        stage_text = {'build': 'Building', 'install': 'Installing', 'build_and_install': 'Processing'}[stage]
        print(f"\n[{idx}/{len(install_order)}] {stage_text} {pkg_name} (tag: {pkg_info['tag']})")
        print("-" * 60)
        
        source_folder = pkg_info['source_folder']
        build_folder = pkg_info['build_folder']
        install_folder = pkg_info['install_folder']
        
        # Build package-specific env vars map: all public + this package's private
        package_env_vars_map = public_env_vars_map.copy()
        
        # Add private environment variables for the current package only
        environment_variables = pkg_info.get('environment_variables', [])
        for env_var in environment_variables:
            env_type = env_var.get('type', 'public')
            env_name = env_var.get('name')
            env_value = env_var.get('value')
            if env_type == 'private' and env_name and env_value:
                package_env_vars_map[env_name] = env_value
        
        # Load package data once
        src_path, package_data, package_name, package_version = load_package_data(source_folder)
        env = setup_environment(src_path, build_folder, install_folder, package_env_vars_map)
        
        # Execute build and/or install based on stage
        if stage == 'build':
            build_package(src_path, package_data, package_name, package_version, env)
        elif stage == 'install':
            install_package(src_path, package_data, package_name, package_version, env)
        else:  # stage == 'build_and_install'
            build_package(src_path, package_data, package_name, package_version, env)
            install_package(src_path, package_data, package_name, package_version, env)


def process_packages_from_manifest(manifest_file_path=None, package_filter=None, extra_env_vars=None, stage='build_and_install'):
    """
    Process packages from manifest file for all combinations of environment variables
    
    Args:
        manifest_file_path: Optional path to package manifest file
        package_filter: Optional list of package names to process (processes all if None)
        extra_env_vars: Optional dict of additional environment variables to set (can contain lists for multi-value)
        stage: Which stage to execute - 'build', 'install', or 'build_and_install'
    """
    # Try to load from specified or default manifest file
    if not manifest_file_path:
        yaml_path = Path("package.manifest.yaml")
        
        if yaml_path.exists():
            manifest_file_path = "package.manifest.yaml"
        else:
            error_msg = "✗ Error: package.manifest.yaml not found"
            print(error_msg)
            print("\nPlease specify the manifest file using --manifest option or ensure")
            print("package.manifest.yaml exists in the current directory.")
            print("\nExample: python process_packages.py --manifest=path/to/package.manifest.yaml")
            sys.exit(1)
    
    manifest_path = Path(manifest_file_path)
    
    # Check if manifest exists
    if not manifest_path.exists():
        error_msg = f"✗ Error: Manifest file not found at {manifest_path.resolve()}"
        print(error_msg)
        print("\nPlease specify the manifest file using --manifest option or ensure")
        print("the manifest file exists in the current directory.")
        print("\nExample: python process_packages.py --manifest=path/to/package.manifest.yaml")
        sys.exit(1)
    
    # Load manifest to get lock file location
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = yaml.safe_load(f)
        packages_install_folder = manifest.get('packages_install_folder', './_packages/published')
        lock_file_path = Path(packages_install_folder) / "package.lock.json"
    except Exception as e:
        error_msg = f"✗ Error: Failed to read manifest file: {e}"
        print(error_msg)
        sys.exit(1)
    
    lock_path = Path(lock_file_path)
    if not lock_path.exists():
        error_msg = f"✗ Error: package.lock.json not found at {lock_path.resolve()}"
        print(error_msg)
        print("\nPlease run init_packages.py first to download packages and generate the lock file.")
        if manifest_file_path:
            print(f"  python init_packages.py --manifest={manifest_file_path}")
        else:
            print(f"  python init_packages.py")
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
        print(f"PROCESSING COMBINATION {combo_idx}/{len(env_combinations)}")
        print(f"{'#'*60}")
        
        for key, value in env_combo.items():
            print(f"  {key} = {value}")
        
        print(f"{'#'*60}")
        
        # Process packages from lock file with this environment combination
        process_packages_from_lock(str(lock_path), package_filter, env_combo, stage)
    
    print(f"\n{'='*60}")
    print(f"✓ All {len(env_combinations)} combinations processed successfully")
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
        description='ArieoEngine Package Processor',
        epilog='''
Examples:
  # Build and install all packages
  python process_packages.py
  
  # Only build packages (skip install stage)
  python process_packages.py --stage=build
  
  # Only install packages (skip build stage)
  python process_packages.py --stage=install
  
  # Build specific packages
  python process_packages.py --package=ArieoEngine-BuildEnv --package=ArieoEngine-ThirdParties
  
  # Build with custom environment variables
  python process_packages.py --env{ARIEO_PACKAGE_BUILDENV_HOST_PRESET}=windows.x86_64 --env{ARIEO_PACKAGE_BUILDENV_HOST_BUILD_TYPE}=Release
  
  # Build with multi-value environment variables (builds all combinations)
  python process_packages.py --env{ARIEO_PACKAGE_BUILDENV_HOST_PRESET}=[windows.x86_64, ubuntu.x86_64] --env{ARIEO_PACKAGE_BUILDENV_HOST_BUILD_TYPE}=[Release, Debug]
  
  # Build with repeated environment variables (builds all combinations)
  python process_packages.py --env{ARIEO_PACKAGE_BUILDENV_HOST_PRESET}=windows.x86_64 --env{ARIEO_PACKAGE_BUILDENV_HOST_PRESET}=ubuntu.x86_64 --env{ARIEO_PACKAGE_BUILDENV_HOST_BUILD_TYPE}=Release --env{ARIEO_PACKAGE_BUILDENV_HOST_BUILD_TYPE}=Debug
  
  # Combine package filter and environment variables
  python process_packages.py --package=ArieoEngine-BuildEnv --env{ARIEO_PACKAGE_BUILDENV_HOST_PRESET}=windows.x86_64
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
        '--manifest',
        dest='manifest_file',
        default=None,
        help='Path to package.manifest.yaml (optional, defaults to package.manifest.yaml in current directory)'
    )
    
    parser.add_argument(
        '--stage',
        dest='stage',
        default='build_and_install',
        choices=['build', 'install', 'build_and_install'],
        help='Which stage to execute: build, install, or build_and_install (default: build_and_install)'
    )
    
    # Parse known args to handle --env{VAR}=value format
    args, unknown = parser.parse_known_args()
    
    # Parse environment variables from unknown args
    extra_env_vars = parse_env_args(unknown)
    
    # Check if there are any unrecognized arguments (not env variables)
    unrecognized = [arg for arg in unknown if not re.match(r'^--env\{[^}]+\}=', arg)]
    if unrecognized:
        parser.error(f"unrecognized arguments: {' '.join(unrecognized)}")
    
    # Process packages
    process_packages_from_manifest(args.manifest_file, args.packages, extra_env_vars, args.stage)
    sys.exit(0)
