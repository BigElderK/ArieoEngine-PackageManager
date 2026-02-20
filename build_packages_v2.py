#!/usr/bin/env python3
"""Build packages using CMake"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Build packages using CMake")
    parser.add_argument("--cmake", required=True, help="Path to CMakeLists.txt directory")
    parser.add_argument("--build_dir", required=False, help="Base build output directory (default: <cmake_dir>/build)")
    parser.add_argument("--preset", action="append", default=[], help="Build preset (can be specified multiple times)")
    parser.add_argument("--build_type", action="append", default=[], help="Build type (can be specified multiple times)")
    parser.add_argument("--package", action="append", default=[], help="Package to build (can be specified multiple times)")
    parser.add_argument("--env", action="append", default=[], help="Environment variable to set (format: VAR=VALUE)")

    args = parser.parse_args()

    cmake_dir = Path(args.cmake).resolve()
    base_build_dir = Path(args.build_dir).resolve() if args.build_dir else (cmake_dir / "build")
    presets = args.preset if args.preset else ["default"]
    build_types = args.build_type if args.build_type else ["Release"]
    packages = args.package

    packages_str = ";".join(packages) if packages else ""


    # Prepare environment variables with set, append, prepend support
    import os
    env = os.environ.copy()
    for env_arg in args.env:
        if '+=' in env_arg:
            k, v = env_arg.split('+=', 1)
            env[k] = env.get(k, '') + v
        elif '^=' in env_arg:
            k, v = env_arg.split('^=', 1)
            env[k] = v + env.get(k, '')
        elif '=' in env_arg:
            k, v = env_arg.split('=', 1)
            env[k] = v

    for preset in presets:
        for build_type in build_types:
            build_dir = base_build_dir / f"{preset}" / f"{build_type}"
            build_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n=== Configuring: preset={preset}, build_type={build_type}, packages={packages_str} ===")

            configure_cmd = [
                "cmake",
                "-G", "Ninja",
                "-S", str(cmake_dir),
                "-B", str(build_dir)
            ]

            # If preset is target from devenv, pass as -DCMAKE_CONFIGURE_PRESET, otherwise use --preset=xxx
            if preset.startswith("devenv."):
                preset = preset[len("devenv."):]
                configure_cmd += [
                    f"-DCMAKE_CONFIGURE_PRESET={preset}",
                ]
            else:
                configure_cmd += [
                    f"--preset={preset}",
                    f"-DCMAKE_BUILD_TYPE={build_type}",
                ]

            result = subprocess.run(configure_cmd, env=env)
            if result.returncode != 0:
                print(f"Configure failed for preset={preset}, build_type={build_type}")
                return result.returncode

            print(f"\n=== Building: preset={preset}, build_type={build_type}, packages={packages_str} ===")

            # Build
            build_cmd = [
                "cmake",
                "--build", 
                str(build_dir),
            ]
            # Add all packages as a single --target argument (space-separated)
            if packages:
                build_cmd.extend(["--target"] + packages)

            result = subprocess.run(build_cmd, env=env)
            if result.returncode != 0:
                print(f"Build failed for preset={preset}, build_type={build_type}")
                return result.returncode

    print("\n=== All builds completed successfully ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
