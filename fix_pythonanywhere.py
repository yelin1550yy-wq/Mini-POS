#!/usr/bin/env python
"""
Run this on PythonAnywhere's Bash console to safely update code and patch database schema.
"""
import subprocess
import sys
import os

commands = [
    "git stash",
    "git pull",
    "pip install -r requirements.txt",
    "python patch_db_columns.py",
    "python -c \"from app import create_app; app = create_app(); print('App and database initialized successfully!')\""
]

for cmd in commands:
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    print(f"Exit code: {result.returncode}")
    print()
