#!/usr/bin/env python3
"""
Package Lambda code and dependencies for deployment.

This script creates two zip files:
1. dependencies.zip - Contains all Python dependencies for the Lambda layer
2. app.zip - Contains the application code (Lambda handlers and tools)
"""

import os
import shutil
import subprocess
import zipfile
from pathlib import Path


def create_zip(source_path: Path, zip_path: Path, exclude_patterns=None, is_dependencies=False):
    """Create a zip file from a source directory."""
    exclude_patterns = exclude_patterns or []
    
    print(f"Creating {zip_path} from {source_path}")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_path):
            # Remove excluded directories from dirs list to prevent traversal
            dirs[:] = [d for d in dirs if not any(pattern in d for pattern in exclude_patterns)]
            
            for file in files:
                if not any(pattern in file for pattern in exclude_patterns):
                    file_path = Path(root) / file
                    if is_dependencies:
                        # Lambda layers require dependencies to be under python/ directory
                        arcname = Path("python") / file_path.relative_to(source_path)
                    else:
                        arcname = file_path.relative_to(source_path)
                    zipf.write(file_path, arcname)
    
    print(f"Created {zip_path} ({zip_path.stat().st_size} bytes)")


def main():
    """Main packaging function."""
    
    # Get project root directory
    project_root = Path(__file__).parent.parent
    packaging_dir = project_root / "packaging"
    lambda_dir = project_root / "lambda"
    
    # Create packaging directory
    packaging_dir.mkdir(exist_ok=True)
    
    # Clean up any existing packaging artifacts
    dependencies_dir = packaging_dir / "_dependencies"
    app_dir = packaging_dir / "_app"
    
    if dependencies_dir.exists():
        shutil.rmtree(dependencies_dir)
    if app_dir.exists():
        shutil.rmtree(app_dir)
    
    dependencies_dir.mkdir(exist_ok=True)
    app_dir.mkdir(exist_ok=True)
    
    print("=== Installing Python dependencies ===")
    
    # Install dependencies using pip with ARM64 architecture for Lambda
    subprocess.run([
        "pip", "install", 
        "-r", str(project_root / "requirements.txt"),
        "--python-version", "3.12",
        "--platform", "manylinux2014_aarch64",
        "--target", str(dependencies_dir),
        "--only-binary=:all:",
        "--upgrade"
    ], check=True)
    
    print("=== Packaging dependencies ===")
    
    # Create dependencies.zip (with python/ directory structure for Lambda layer)
    dependencies_zip = packaging_dir / "dependencies.zip"
    create_zip(
        dependencies_dir, 
        dependencies_zip,
        exclude_patterns=["__pycache__", ".pyc", ".DS_Store", "*.dist-info"],
        is_dependencies=True
    )
    
    print("=== Packaging application code ===")
    
    # Copy Lambda code to app directory
    for file in lambda_dir.glob("*.py"):
        shutil.copy2(file, app_dir)
    
    # Create app.zip
    app_zip = packaging_dir / "app.zip"
    create_zip(
        app_dir,
        app_zip,
        exclude_patterns=["__pycache__", ".pyc", ".DS_Store"],
        is_dependencies=False
    )
    
    print("=== Packaging complete ===")
    print(f"Dependencies: {dependencies_zip}")
    print(f"Application: {app_zip}")
    
    # Clean up temporary directories
    shutil.rmtree(dependencies_dir)
    shutil.rmtree(app_dir)
    
    print("Temporary directories cleaned up")


if __name__ == "__main__":
    main()
