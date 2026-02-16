#!/usr/bin/env python3
"""
Build packages using CMake ExternalProject_Add system
"""

import argparse
import json
import os
import subprocess
import sys
import yaml
import platform
from pathlib import Path


def cleanup_empty_dirs(root_path):
    """
    Recursively remove empty directories from root_path.
    Walks bottom-up to ensure nested empty dirs are removed.
    
    Args:
        root_path: Path to the root directory to clean
    """
    root = Path(root_path)
    if not root.exists():
        return
    
    removed_count = 0
    # Walk bottom-up so we can remove nested empty dirs
    for dirpath in sorted(root.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        if dirpath.is_dir():
            try:
                # Check if directory is empty
                if not any(dirpath.iterdir()):
                    dirpath.rmdir()
                    removed_count += 1
            except OSError:
                pass  # Directory not empty or permission denied
    
    if removed_count > 0:
        print(f"Cleaned up {removed_count} empty directories from {root}")


def run_command(cmd, cwd=None, env=None, check=True):
    """
    Run a command and return the result
    
    Args:
        cmd: Command to run (list of strings)
        cwd: Working directory
        env: Environment variables
        check: Raise exception on non-zero exit code
        
    Returns:
        subprocess.CompletedProcess result
    """
    print(f"\n{'='*80}")
    print(f"Running: {' '.join(str(c) for c in cmd)}")
    if cwd:
        print(f"Working directory: {cwd}")
    print(f"{'='*80}\n")
    
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=check,
        text=True
    )
    
    return result


def parse_env_vars(envs=None, env_file=None, clear_env=False):
    """
    Parse environment variables from arguments and file
    
    Args:
        envs: List of "KEY=VALUE" strings
        env_file: Path to environment file
        clear_env: If True, start with empty env; otherwise inherit os.environ
    
    Returns:
        dict: Environment variables to use, or None if no modifications
    """
    # If no env options specified, return None to use default environment
    if not envs and not env_file and not clear_env:
        return None
    
    # Start with current environment or empty dict
    env = {} if clear_env else os.environ.copy()
    
    # Load from file if specified
    if env_file:
        env_path = Path(env_file)
        if env_path.exists():
            print(f"Loading environment variables from: {env_path}")
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, _, value = line.partition('=')
                        env[key.strip()] = value.strip()
        else:
            print(f"Warning: Environment file not found: {env_path}")
    
    # Override with command-line args
    if envs:
        for env_str in envs:
            if '=' in env_str:
                key, _, value = env_str.partition('=')
                env[key] = value
                print(f"Setting environment variable: {key}={value}")
            else:
                print(f"Warning: Invalid env format (expected KEY=VALUE): {env_str}")
    
    return env


def build_packages(cmake_file, build_folder, presets, build_types, packages, packages_info, packages_install_folder, env=None):
    """
    Build specified packages with given presets and build types
    
    Args:
        cmake_file: Path to CMakeLists.txt
        build_folder: Root build folder path
        presets: List of CMake presets (e.g., ["windows.x86_64"])
        build_types: List of build types (e.g., ["Debug", "Release"])
        packages: List of package names to build (e.g., ["Arieo-Core"])
        packages_info: Dict containing package information from packages_resolve.json
        packages_install_folder: Install folder path for package outputs
        env: Environment variables dict to use for subprocess calls
    """
    cmake_file = Path(cmake_file).resolve()
    source_dir = cmake_file.parent
    build_folder = Path(build_folder).resolve()
    
    if not cmake_file.exists():
        print(f"Error: CMakeLists.txt not found: {cmake_file}")
        sys.exit(1)
    
    print(f"\n{'='*80}")
    print(f"Building Packages")
    print(f"{'='*80}")
    print(f"Source directory: {source_dir}")
    print(f"Presets: {', '.join(presets)}")
    print(f"Build types: {', '.join(build_types)}")
    print(f"Packages: {', '.join(packages)}")
    print(f"{'='*80}\n")
    
    # Build for each combination of preset and build type
    for preset in presets:
        for build_type in build_types:
            print(f"\n{'#'*80}")
            print(f"# Building with preset: {preset}, build type: {build_type}")
            print(f"{'#'*80}\n")
            
            build_dir = build_folder / preset / build_type
            
            # Configure CMake SuperBuild (super-build doesn't use --preset, only passes preset to sub-projects)
            configure_cmd = [
                "cmake",
                "-G", "Ninja",
                "-S", str(source_dir),
                "-B", str(build_dir),
                f"-DCMAKE_BUILD_TYPE={build_type}",
                f"-DCMAKE_CONFIGURE_PRESET={preset}"
            ]
            
            try:
                run_command(configure_cmd, cwd=source_dir, env=env)
            except subprocess.CalledProcessError as e:
                print(f"\nError: CMake configuration failed for {preset}/{build_type}")
                print(f"Exit code: {e.returncode}")
                sys.exit(1)
            
            # Build all packages in a single command with parallel jobs
            print(f"\n{'-'*80}")
            print(f"Building packages: {', '.join(packages)}")
            print(f"{'-'*80}\n")
            
            build_cmd = [
                "cmake",
                "--build", str(build_dir),
                "--config", build_type,
                "-j", "8"
            ]
            
            # Add all package targets
            for package in packages:
                build_cmd.extend(["--target", package])
            
            try:
                run_command(build_cmd, cwd=source_dir, env=env)
                print(f"\n✓ Successfully built all packages ({preset}/{build_type})")
            except subprocess.CalledProcessError as e:
                print(f"\nError: Build failed for packages ({preset}/{build_type})")
                print(f"Exit code: {e.returncode}")
                sys.exit(1)
    
    print(f"\n{'='*80}")
    print(f"✓ All packages built successfully!")
    print(f"{'='*80}\n")

    # Cleanup empty directories from install folder
    if packages_install_folder:
        install_folder = Path(packages_install_folder)
        if install_folder.exists():
            print(f"Cleaning up empty directories...")
            cleanup_empty_dirs(install_folder)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Build packages using CMake ExternalProject_Add system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python build_packages.py \\
    --manifest=packages.manifest.yaml \\
    --preset=windows.x86_64 \\
    --preset=ubuntu.x86_64 \\
    --build_type=Debug \\
    --build_type=Release \\
    --package=Arieo-Core \\
    --package=Arieo-Interface-Main

  # With environment variables:
  python build_packages.py \\
    --manifest=packages.manifest.yaml \\
    --preset=android.armv8 \\
    --env=ANDROID_NDK_HOME=/path/to/ndk \\
    --env=JAVA_HOME=/path/to/jdk \\
    --package=Arieo-ThirdParties

  # Using an environment file:
  python build_packages.py \\
    --manifest=packages.manifest.yaml \\
    --preset=windows.x86_64 \\
    --env-file=build_env.txt \\
    --package=Arieo-Core
        """
    )
    
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to packages.manifest.yaml file"
    )
    
    parser.add_argument(
        "--preset",
        action="append",
        dest="presets",
        required=True,
        help="CMake preset to use (can be specified multiple times)"
    )
    
    parser.add_argument(
        "--build_type",
        action="append",
        dest="build_types",
        required=False,
        help="Build type: Debug, Release, RelWithDebInfo, MinSizeRel (can be specified multiple times, defaults to Release)"
    )
    
    parser.add_argument(
        "--package",
        action="append",
        dest="packages",
        required=True,
        help="Package name to build (can be specified multiple times)"
    )
    
    parser.add_argument(
        "--env",
        action="append",
        dest="envs",
        metavar="KEY=VALUE",
        help="Set environment variable for build process (can be specified multiple times)"
    )
    
    parser.add_argument(
        "--env-file",
        dest="env_file",
        help="Path to file containing environment variables (KEY=VALUE per line, # for comments)"
    )
    
    parser.add_argument(
        "--env-clear",
        action="store_true",
        dest="env_clear",
        help="Clear inherited environment variables (use only explicitly set vars)"
    )
    
    args = parser.parse_args()
    
    # Read manifest file
    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        print(f"Error: Manifest file not found: {manifest_path}")
        sys.exit(1)
    
    print(f"Reading manifest file: {manifest_path}")
    
    with open(manifest_path, 'r') as f:
        manifest = yaml.safe_load(f)
    
    # Get packages_cmake_list_file from manifest
    if 'packages_cmake_list_file' not in manifest:
        print("Error: 'packages_cmake_list_file' not found in manifest")
        sys.exit(1)
    
    # Get packages_build_folder from manifest
    if 'packages_build_folder' not in manifest:
        print("Error: 'packages_build_folder' not found in manifest")
        sys.exit(1)
    
    # Get packages_resolve_file from manifest
    packages_resolve_file_rel = manifest.get('packages_resolve_file', 'packages/packages_resolve.json')
    
    cmake_file_rel = manifest['packages_cmake_list_file']
    build_folder_rel = manifest['packages_build_folder']
    
    # Resolve path relative to manifest file location
    cmake_file = (manifest_path.parent / cmake_file_rel).resolve()
    build_folder = (manifest_path.parent / build_folder_rel).resolve()
    packages_resolve_file = (manifest_path.parent / packages_resolve_file_rel).resolve()
    
    print(f"CMake file from manifest: {cmake_file}")
    print(f"Build folder from manifest: {build_folder}")
    print(f"Packages resolve file: {packages_resolve_file}")
    
    # Load packages_resolve.json to get package information
    packages_info = {}
    packages_install_folder = None
    if packages_resolve_file.exists():
        try:
            with open(packages_resolve_file, 'r') as f:
                resolve_data = json.load(f)
                packages_info = resolve_data.get('packages', {})
                packages_install_folder = resolve_data.get('packages_install_folder')
                print(f"Loaded {len(packages_info)} packages from resolve file")
        except Exception as e:
            print(f"Warning: Failed to read packages resolve file: {e}")
    else:
        print(f"Warning: Packages resolve file not found: {packages_resolve_file}")
    
    # Default to Release if no build types specified
    build_types = args.build_types if args.build_types else ["Release"]

    # Filter presets based on host platform
    host = platform.system()
    filtered_presets = []
    for preset in args.presets:
        if preset.startswith("windows.") and host != "Windows":
            print(f"Skipping preset '{preset}': only supported on Windows host platform.")
            continue
        if preset.startswith("macos.") and host != "Darwin":
            print(f"Skipping preset '{preset}': only supported on macOS host platform.")
            continue
        filtered_presets.append(preset)
    if not filtered_presets:
        print("No supported presets for current host platform. Nothing to build.")
        sys.exit(0)
    
    # Parse environment variables
    env = parse_env_vars(
        envs=args.envs,
        env_file=args.env_file,
        clear_env=args.env_clear
    )
    
    build_packages(
        cmake_file=cmake_file,
        build_folder=build_folder,
        presets=filtered_presets,
        build_types=build_types,
        packages=args.packages,
        packages_info=packages_info,
        packages_install_folder=packages_install_folder,
        env=env
    )


if __name__ == "__main__":
    main()
