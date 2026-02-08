#!/usr/bin/env python3
"""
ArieoEngine Package Initializer
Handles downloading packages and generating package resolve file with dependency resolution
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from collections import defaultdict
import yaml


def download_package_from_git(git_url, tag, dest_folder, category=None):
    """
    Clone a git repository and checkout specific tag/branch
    
    Args:
        git_url: Git repository URL
        tag: Tag or branch name to checkout
        dest_folder: Destination folder path
        category: Optional category subfolder (e.g., "00_build")
    
    Returns:
        dict: Contains 'folder_name' (relative path with category) and 'repo_name'
    """
    dest_path = Path(dest_folder)
    if category:
        dest_path = dest_path / category
    
    # Extract repository name from git URL
    repo_name = git_url.rstrip('/').split('/')[-1].replace('.git', '')
    # Append tag to folder name
    repo_folder_name = f"{repo_name}-{tag}"
    repo_path = dest_path / repo_folder_name
    
    print(f"Downloading package: {repo_name} (tag: {tag})")
    print(f"  URL: {git_url}")
    print(f"  Tag/Branch: {tag}")
    print(f"  Destination: {repo_path}")
    
    try:
        # Create destination folder if it doesn't exist
        dest_path.mkdir(parents=True, exist_ok=True)
        
        # Check if repository already exists
        if repo_path.exists():
            print(f"  Repository already exists, updating...")
            # Change to repo directory and pull
            original_cwd = os.getcwd()
            os.chdir(repo_path)
            
            # Fetch latest changes
            subprocess.run(['git', 'fetch', '--all'], check=True, capture_output=True)
            
            # Checkout the specified tag/branch
            result = subprocess.run(['git', 'checkout', tag], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  Warning: Could not checkout {tag}: {result.stderr}")
            
            # Pull latest if it's a branch
            subprocess.run(['git', 'pull'], capture_output=True)
            
            os.chdir(original_cwd)
            print(f"✓ Updated {repo_folder_name}")
            
            # Return relative path with category if provided
            if category:
                return {'folder_name': f"{category}/{repo_folder_name}", 'repo_name': repo_name}
            else:
                return {'folder_name': repo_folder_name, 'repo_name': repo_name}
        else:
            # Clone the repository
            result = subprocess.run(
                ['git', 'clone', git_url, str(repo_path)],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                error_msg = f"✗ Failed to clone repository: {repo_name}\nError: {result.stderr}"
                print(error_msg)
                sys.exit(1)
            
            # Checkout the specified tag/branch
            original_cwd = os.getcwd()
            os.chdir(repo_path)
            
            result = subprocess.run(['git', 'checkout', tag], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  Warning: Could not checkout {tag}: {result.stderr}")
            
            os.chdir(original_cwd)
            print(f"✓ Downloaded {repo_folder_name}")
        
        # Return relative path with category if provided
        if category:
            return {'folder_name': f"{category}/{repo_folder_name}", 'repo_name': repo_name}
        else:
            return {'folder_name': repo_folder_name, 'repo_name': repo_name}
        
    except Exception as e:
        error_msg = f"✗ Error downloading package: {repo_name}\nException: {str(e)}"
        print(error_msg)
        sys.exit(1)


def read_arieo_package_json(package_path):
    """
    Read arieo_package.json from a package folder
    
    Args:
        package_path: Path to the package folder
        
    Returns:
        dict: Package data or None if not found
    """
    arieo_package_json_path = Path(package_path) / "arieo_package.json"
    
    if not arieo_package_json_path.exists():
        print(f"  Warning: arieo_package.json not found in {package_path}")
        return None
    
    try:
        with open(arieo_package_json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        error_msg = f"✗ Error: Failed to read arieo_package.json in {package_path}: {e}"
        print(error_msg)
        sys.exit(1)


def check_dependency_conflicts(packages_data):
    """
    Check for version/tag conflicts in dependencies
    
    Args:
        packages_data: Dict mapping package name to package info
        
    Returns:
        None (exits on conflict)
    """
    # Track required versions for each dependency
    dependency_requirements = defaultdict(dict)  # {dep_name: {pkg_name: tag}}
    
    for pkg_name, pkg_info in packages_data.items():
        arieo_data = pkg_info.get('arieo_package_data')
        if not arieo_data:
            continue
            
        dependencies = arieo_data.get('dependencies', {})
        dep_packages = dependencies.get('packages', [])
        
        for dep in dep_packages:
            dep_git_url = dep.get('git_url', '')
            dep_tag = dep.get('tag', 'main')
            dep_name = dep_git_url.rstrip('/').split('/')[-1].replace('.git', '')
            
            dependency_requirements[dep_name][pkg_name] = dep_tag
    
    # Check for conflicts
    conflicts = []
    for dep_name, requirements in dependency_requirements.items():
        if len(set(requirements.values())) > 1:
            # Multiple different versions required
            conflicts.append((dep_name, requirements))
    
    if conflicts:
        error_msg = "✗ Error: Dependency version/tag conflicts detected!\n\n"
        for dep_name, requirements in conflicts:
            error_msg += f"Package '{dep_name}' has conflicting version requirements:\n"
            for pkg_name, tag in requirements.items():
                error_msg += f"  - Required by '{pkg_name}' with tag/version: '{tag}'\n"
            error_msg += "\n"
        
        error_msg += "Please resolve these conflicts by ensuring all packages depend on the same version/tag."
        print(error_msg)
        sys.exit(1)


def topological_sort(packages_data):
    """
    Perform topological sort on packages based on dependencies
    
    Args:
        packages_data: Dict mapping package name to package info
        
    Returns:
        list: Ordered list of package names
    """
    # Build dependency graph
    in_degree = defaultdict(int)
    graph = defaultdict(list)
    
    # Initialize all packages with in_degree 0
    for pkg_name in packages_data:
        in_degree[pkg_name] = 0
    
    # Build graph
    for pkg_name, pkg_info in packages_data.items():
        arieo_data = pkg_info.get('arieo_package_data')
        if not arieo_data:
            continue
            
        dependencies = arieo_data.get('dependencies', {})
        dep_packages = dependencies.get('packages', [])
        
        for dep in dep_packages:
            dep_git_url = dep.get('git_url', '')
            dep_name = dep_git_url.rstrip('/').split('/')[-1].replace('.git', '')
            
            if dep_name in packages_data:
                graph[dep_name].append(pkg_name)
                in_degree[pkg_name] += 1
    
    # Topological sort using Kahn's algorithm
    queue = [pkg for pkg in packages_data if in_degree[pkg] == 0]
    result = []
    
    while queue:
        current = queue.pop(0)
        result.append(current)
        
        for neighbor in graph[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    # Check for circular dependencies
    if len(result) != len(packages_data):
        error_msg = "✗ Error: Circular dependency detected!"
        print(error_msg)
        sys.exit(1)
    
    return result


def load_manifest(manifest_file_path=None):
    """
    Load package manifest file (YAML format)
    
    Args:
        manifest_file_path: Optional path to manifest file. If not provided, uses "package.manifest.yaml"
    
    Returns:
        dict: Manifest data or None if failed
    """
    if not manifest_file_path:
        yaml_path = Path("package.manifest.yaml")
        
        if yaml_path.exists():
            manifest_path = yaml_path
        else:
            error_msg = "✗ Error: package.manifest.yaml not found"
            print(error_msg)
            sys.exit(1)
    else:
        manifest_path = Path(manifest_file_path)
        if not manifest_path.exists():
            error_msg = f"✗ Error: Manifest file not found at {manifest_path}"
            print(error_msg)
            sys.exit(1)
    
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = yaml.safe_load(f) or {}
            manifest['_manifest_dir'] = str(manifest_path.parent.resolve())
            return manifest
    except Exception as e:
        error_msg = f"✗ Error: Failed to read manifest file: {e}"
        print(error_msg)
        sys.exit(1)


def generate_package_resolve_file(install_order, packages_data, packages_src_folder, packages_install_folder, packages_build_folder, package_resolve_file_path):
    """
    Generate package resolve file (package.lock.json or packages_resolve.json) with installation order and package details
    
    Args:
        install_order: List of package names in installation order
        packages_data: Dict mapping package name to package info
        packages_src_folder: Source folder path
        packages_install_folder: Output folder path
        packages_build_folder: Build folder path
        package_resolve_file_path: Path where to write the resolve file
        
    Returns:
        str: Path to generated resolve file
    """
    resolve_data = {
        "generated_at": subprocess.run(['date', '/T'], capture_output=True, text=True, shell=True).stdout.strip() if os.name == 'nt' else subprocess.run(['date'], capture_output=True, text=True).stdout.strip(),
        "packages_src_folder": str(Path(packages_src_folder).resolve()),
        "packages_install_folder": str(Path(packages_install_folder).resolve()),
        "packages_build_folder": str(Path(packages_build_folder).resolve()),
        "environment_variables": [
            {
                "type": "public",
                "name": "ARIEO_PACKAGE_ROOT_INSTALL_FOLDER",
                "value": str(Path(packages_install_folder).resolve())
            }
        ],
        "install_order": [],
        "packages": {}
    }
    
    # Build resolve data
    for idx, pkg_name in enumerate(install_order, 1):
        pkg_info = packages_data[pkg_name]
        arieo_data = pkg_info.get('arieo_package_data') or {}
        folder_name = pkg_info['folder_name']
        
        # Generate environment variable names from package name (without tag)
        # e.g., "Arieo-BuildEnv" -> "ARIEO_PACKAGE_BUILDENV_INSTALL_FOLDER" and "ARIEO_PACKAGE_BUILDENV_SOURCE_FOLDER"
        base_env_var_name = 'ARIEO_PACKAGE_' + pkg_name.upper().replace('-', '_').replace('ARIEOENGINE_', '').replace('ARIEO_', '')
        
        # Get the package name from arieo_package.json, fallback to repo name
        package_name = arieo_data.get('name', pkg_name)
        
        package_entry = {
            "build_index": idx,
            "name": package_name,
            "description": arieo_data.get('description', ''),
            "git_url": pkg_info.get('git_url', ''),
            "tag": pkg_info.get('tag', ''),
            "source_folder": str(pkg_info['path'].resolve()),
            "install_folder": str((Path(packages_install_folder).resolve() / pkg_info['folder_name'])),
            "build_folder": str((Path(packages_build_folder).resolve() / pkg_info['folder_name'])),
            "environment_variables": [
                {
                    "type": "public",
                    "name": base_env_var_name + '_INSTALL_FOLDER',
                    "value": str((Path(packages_install_folder).resolve() / pkg_info['folder_name']))
                },
                {
                    "type": "private",
                    "name": base_env_var_name + '_SOURCE_FOLDER',
                    "value": str(pkg_info['path'].resolve())
                },
                {
                    "type": "private",
                    "name": base_env_var_name + '_BUILD_FOLDER',
                    "value": str((Path(packages_build_folder).resolve() / pkg_info['folder_name']))
                },
                {
                    "type": "private",
                    "name": 'ARIEO_CUR_PACKAGE_SOURCE_FOLDER',
                    "value": str(pkg_info['path'].resolve())
                },
                {
                    "type": "private",
                    "name": 'ARIEO_CUR_PACKAGE_BUILD_FOLDER',
                    "value": str((Path(packages_build_folder).resolve() / pkg_info['folder_name']))
                },
                {
                    "type": "private",
                    "name": 'ARIEO_CUR_PACKAGE_INSTALL_FOLDER',
                    "value": str((Path(packages_install_folder).resolve() / pkg_info['folder_name']))
                },
                {
                    "type": "private",
                    "name": 'ARIEO_CUR_PACKAGE_NAME',
                    "value": package_name
                }
            ],
            "build_commands": arieo_data.get('build_commands', []),
            "install_commands": arieo_data.get('install_commands', []),
            "dependencies": []
        }
        
        # Extract dependencies
        dependencies = arieo_data.get('dependencies', {})
        dep_packages = dependencies.get('packages', [])
        for dep in dep_packages:
            dep_url = dep.get('git_url', '')
            dep_tag = dep.get('tag', 'main')
            dep_name = dep_url.rstrip('/').split('/')[-1].replace('.git', '')
            package_entry['dependencies'].append({
                "name": dep_name,
                "git_url": dep_url,
                "tag": dep_tag
            })
        
        resolve_data['install_order'].append(package_name)
        resolve_data['packages'][package_name] = package_entry
    
    # Write resolve file
    package_resolve_file_path = Path(package_resolve_file_path)
    try:
        # Create output folder if it doesn't exist
        package_resolve_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(package_resolve_file_path, 'w', encoding='utf-8') as f:
            json.dump(resolve_data, f, indent=4, ensure_ascii=False)
        print(f"✓ Generated {package_resolve_file_path.resolve()}")
        return str(package_resolve_file_path.resolve())
    except Exception as e:
        error_msg = f"✗ Error: Failed to write resolve file: {e}"
        print(error_msg)
        sys.exit(1)


def init_all_packages(manifest_file_path=None):
    """
    Download all packages from package.manifest.yaml with dependency resolution
    
    Args:
        manifest_file_path: Optional path to manifest file
    """
    manifest = load_manifest(manifest_file_path)
    
    manifest_dir = Path(manifest.get('_manifest_dir', '.')).resolve()

    def expand_manifest_path(value):
        if not value:
            return value
        expanded = value.replace('${CUR_MANIFEST_FILE_DIR}', str(manifest_dir))
        expanded = os.path.expandvars(expanded)
        return expanded

    packages_src_folder = expand_manifest_path(manifest.get('packages_src_folder', './_packages/src'))
    packages_install_folder = expand_manifest_path(manifest.get('packages_install_folder', './_packages/published'))
    packages_build_folder = expand_manifest_path(manifest.get('packages_build_folder', './_build'))
    packages_resolve_file = expand_manifest_path(manifest.get('packages_resolve_file', str(Path(packages_install_folder) / 'package.lock.json')))
    packages_dict = manifest.get('packages', {})
    
    # Count total packages across all categories
    total_packages = sum(len(pkg_list) for pkg_list in packages_dict.values())
    
    if total_packages == 0:
        print("No packages to download")
        return
    
    print(f"\n{'='*60}")
    print(f"STEP 1: Downloading {total_packages} package(s)")
    print(f"{'='*60}")
    
    # Download all packages first
    packages_data = {}
    pkg_counter = 0
    
    for category, package_list in packages_dict.items():
        for package in package_list:
            pkg_counter += 1
            print(f"\nDownloading package {pkg_counter}/{total_packages} [Category: {category}]")
            git_url = package.get('git_url')
            git_spec = package.get('git')
            local_path_raw = package.get('local')
            tag = package.get('tag', 'main')
            
            # Parse git@tag format if present
            if git_spec:
                if '@' in git_spec:
                    git_url, tag = git_spec.rsplit('@', 1)
                else:
                    git_url = git_spec
                    tag = 'main'
            
            if local_path_raw:
                local_path = Path(expand_manifest_path(local_path_raw))
                if not local_path.is_absolute():
                    local_path = (manifest_dir / local_path).resolve()
                if not local_path.exists():
                    error_msg = f"✗ Error: Local package path not found: {local_path}"
                    print(error_msg)
                    sys.exit(1)

                repo_name = local_path.name
                repo_folder_name = f"{category}/{repo_name}" if category else repo_name
                package_path = local_path
                git_url = None
                tag = 'local'
                print(f"  Using local package path: {local_path}")
            else:
                if not git_url:
                    error_msg = f"✗ Error: Package #{pkg_counter} missing git_url or local"
                    print(error_msg)
                    sys.exit(1)

                # Download package with category subfolder
                result = download_package_from_git(git_url, tag, packages_src_folder, category)
                repo_folder_name = result['folder_name']  # e.g., "00_build/Arieo-BuildEnv-main"
                repo_name = result['repo_name']  # e.g., "Arieo-BuildEnv"
                package_path = Path(packages_src_folder) / repo_folder_name
            
            # Read arieo_package.json
            arieo_data = read_arieo_package_json(package_path)
            
            packages_data[repo_name] = {
                'git_url': git_url,
                'tag': tag,
                'path': package_path,
                'folder_name': repo_folder_name,  # Includes category in path
                'arieo_package_data': arieo_data
            }
    
    print(f"\n{'='*60}")
    print(f"STEP 2: Resolving dependencies")
    print(f"{'='*60}")
    
    # Check for version/tag conflicts
    check_dependency_conflicts(packages_data)
    
    # Perform topological sort to determine installation order
    install_order = topological_sort(packages_data)
    
    print(f"\n{'='*60}")
    print(f"STEP 3: Generating package resolve file")
    print(f"{'='*60}")
    
    # Generate resolve file with installation details
    package_resolve_file_path = generate_package_resolve_file(install_order, packages_data, packages_src_folder, packages_install_folder, packages_build_folder, packages_resolve_file)
    
    # Display installation order
    print(f"\nBuild order:")
    for idx, pkg_name in enumerate(install_order, 1):
        pkg_info = packages_data[pkg_name]
        arieo_data = pkg_info.get('arieo_package_data')
        
        # Show source information in parentheses
        if pkg_info.get('git_url'):
            source_info = f"Git URL: {pkg_info['git_url']}, Tag: {pkg_info['tag']}"
        else:
            source_info = f"Local: {pkg_info['path'].resolve()}"
        
        print(f"  {idx}. {pkg_name} ({source_info})")
        
        # Show dependencies
        if arieo_data:
            dependencies = arieo_data.get('dependencies', {})
            dep_packages = dependencies.get('packages', [])
            if dep_packages:
                print(f"     Dependencies:")
                for dep in dep_packages:
                    dep_url = dep.get('git_url', 'unknown')
                    dep_name = dep_url.rstrip('/').split('/')[-1].replace('.git', '')
                    print(f"       - {dep_name}")
    
    return package_resolve_file_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='ArieoEngine Package Initializer - Downloads packages and generates package resolve file',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--manifest',
        dest='manifest_file',
        default=None,
        help='Path to package.manifest.yaml (optional, defaults to package.manifest.yaml in current directory)'
    )
    
    args = parser.parse_args()
    
    # Download and generate resolve file for all packages from manifest
    print("ArieoEngine Package Initializer")
    print("=" * 60)
    
    package_resolve_file_path = init_all_packages(args.manifest_file)
    
    print(f"\n{'='*60}")
    print("✓ All packages downloaded and resolve file generated")
    print(f"{'='*60}")
    sys.exit(0)
