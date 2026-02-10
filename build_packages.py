#!/usr/bin/env python3
"""
Build packages using CMake ExternalProject_Add system
"""

import argparse
import json
import subprocess
import sys
import yaml
from pathlib import Path


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


def build_packages(cmake_file, build_folder, presets, build_types, packages, packages_info):
    """
    Build specified packages with given presets and build types
    
    Args:
        cmake_file: Path to CMakeLists.txt
        build_folder: Root build folder path
        presets: List of CMake presets (e.g., ["windows.x86_64"])
        build_types: List of build types (e.g., ["Debug", "Release"])
        packages: List of package names to build (e.g., ["Arieo-Core"])
        packages_info: Dict containing package information from packages_resolve.json
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
                run_command(configure_cmd, cwd=source_dir)
            except subprocess.CalledProcessError as e:
                print(f"\nError: CMake configuration failed for {preset}/{build_type}")
                print(f"Exit code: {e.returncode}")
                sys.exit(1)
            
            # Build each package
            for package in packages:
                print(f"\n{'-'*80}")
                print(f"Building package: {package}")
                print(f"{'-'*80}\n")
                
                build_cmd = [
                    "cmake",
                    "--build", str(build_dir),
                    "--config", build_type,
                    "--target", package
                ]
                
                try:
                    run_command(build_cmd, cwd=source_dir)
                    print(f"\n✓ Successfully built {package} ({preset}/{build_type})")
                except subprocess.CalledProcessError as e:
                    print(f"\nError: Build failed for {package} ({preset}/{build_type})")
                    print(f"Exit code: {e.returncode}")
                    sys.exit(1)
    
    print(f"\n{'='*80}")
    print(f"✓ All packages built successfully!")
    print(f"{'='*80}\n")


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
    if packages_resolve_file.exists():
        try:
            with open(packages_resolve_file, 'r') as f:
                resolve_data = json.load(f)
                packages_info = resolve_data.get('packages', {})
                print(f"Loaded {len(packages_info)} packages from resolve file")
        except Exception as e:
            print(f"Warning: Failed to read packages resolve file: {e}")
    else:
        print(f"Warning: Packages resolve file not found: {packages_resolve_file}")
    
    # Default to Release if no build types specified
    build_types = args.build_types if args.build_types else ["Release"]
    
    build_packages(
        cmake_file=cmake_file,
        build_folder=build_folder,
        presets=args.presets,
        build_types=build_types,
        packages=args.packages,
        packages_info=packages_info
    )


if __name__ == "__main__":
    main()
