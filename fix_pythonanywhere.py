#!/usr/bin/env python
"""
Run this on PythonAnywhere's Bash console to fix all issues.
"""
import subprocess
import sys

commands = [
    "cd ~/Mini-POS",
    "git stash",
    "git pull",
    "pip install -r requirements.txt",
    "python -c \"\nimport os\nos.environ['FLASK_ENV'] = 'production'\nfrom app import create_app, db\nfrom app.models import User, TierConfig\napp = create_app()\nwith app.app_context():\n    db.drop_all()\n    db.create_all()\n    TierConfig.initialize_default_tiers()\n    admin = User(username='admin', email='admin@example.com', role='admin')\n    admin.set_password('admin123')\n    db.session.add(admin)\n    user = User(username='staff', email='staff@example.com', role='user')\n    user.set_password('staff123')\n    db.session.add(user)\n    db.session.commit()\n    print('✓ Database recreated with default users')\n\"",
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