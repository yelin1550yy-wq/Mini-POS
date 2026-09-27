#!/usr/bin/env python
"""
PythonAnywhere Free Tier Deployment Helper
Run this locally to generate the WSGI file and requirements for PythonAnywhere.
"""
import os
import sys

def generate_wsgi():
    return """import sys
import os

# Add your project directory to the path
project_home = '/home/yourusername/mini-pos'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables
os.environ['FLASK_ENV'] = 'production'
os.environ['SECRET_KEY'] = 'your-secret-key-here'  # CHANGE THIS!
os.environ['DATABASE_URL'] = 'sqlite:////home/yourusername/mini-pos/instance/minipos.db'

# Import the app
from run import app as application

# Ensure database exists
with application.app_context():
    from app import db
    db.create_all()

    # Create default users if they don't exist
    from app.models import User
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", email="admin@example.com", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)

        user = User(username="staff", email="staff@example.com", role="user")
        user.set_password("staff123")
        db.session.add(user)

        db.session.commit()
        print("Default users created: admin/admin123, staff/staff123")"""

def generate_requirements():
    with open('requirements.txt', 'r') as f:
        return f.read()

if __name__ == '__main__':
    print("=" * 60)
    print("PythonAnywhere Free Tier Deployment Helper")
    print("=" * 60)
    print()
    print("1. WSGI file content (save as /var/www/yourusername_pythonanywhere_com_wsgi.py):")
    print("-" * 60)
    print(generate_wsgi())
    print("-" * 60)
    print()
    print("2. requirements.txt (already exists):")
    print("-" * 60)
    print(generate_requirements())
    print("-" * 60)
    print()
    print("3. STEP-BY-STEP DEPLOYMENT ON PYTHONANYWHERE:")
    print("=" * 60)
    print("""
STEP 1: Create PythonAnywhere Account
-------------------------------------
- Go to https://www.pythonanywhere.com
- Sign up for FREE "Beginner" account
- Username: yourusername (this becomes yourusername.pythonanywhere.com)

STEP 2: Upload Code via Git
---------------------------
# In PythonAnywhere Bash console:
git clone https://github.com/yelin1550yy-wq/mini-pos.git
cd mini-pos

STEP 3: Install Dependencies
----------------------------
# In the same Bash console:
mkvirtualenv --python=/usr/bin/python3.10 mini-pos
pip install -r requirements.txt

STEP 4: Configure Web App
-------------------------
1. Go to "Web" tab in PythonAnywhere dashboard
2. Click "Add a new web app"
3. Choose "Manual configuration" -> Python 3.10
4. Set source code path: /home/yourusername/mini-pos
5. Set working directory: /home/yourusername/mini-pos
6. Edit the WSGI file (link provided):
   - Delete all content
   - Paste the WSGI content from above
   - Update paths:
     * project_home = '/home/yourusername/mini-pos'
     * SECRET_KEY = 'your-generated-secret'
     * DATABASE_URL = 'sqlite:////home/yourusername/mini-pos/instance/minipos.db'

STEP 5: Generate Secret Key
---------------------------
# In Bash console:
python -c "import secrets; print(secrets.token_hex(32))"
# Copy output and put in WSGI file

STEP 6: Initialize Database
---------------------------
# In Bash console (with venv activated):
cd ~/mini-pos
python -c "
from run import app
with app.app_context():
    from app import db
    db.create_all()
    from app.models import User
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@example.com', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        user = User(username='staff', email='staff@example.com', role='user')
        user.set_password('staff123')
        db.session.add(user)
        db.session.commit()
        print('Users created!')
"

STEP 7: Configure Static Files
------------------------------
In Web tab -> Static files:
URL: /static/
Path: /home/yourusername/mini-pos/app/static

STEP 7: Reload & Test
---------------------
1. Click "Reload" button in Web tab
2. Visit: https://yourusername.pythonanywhere.com
3. Login: admin / admin123

STEP 8: Change Default Passwords!
---------------------------------
IMMEDIATELY after first login:
- Change admin password
- Change staff password

STEP 9: (Optional) Custom Domain
---------------------------------
- Free tier: yourusername.pythonanywhere.com only
- Paid tier: custom domain + HTTPS

IMPORTANT LIMITATIONS (Free Tier):
----------------------------------
+ 1 web app (yourusername.pythonanywhere.com)
+ 1 SQLite/MySQL database
+ 512 MB disk space
+ CPU seconds limited (no heavy background tasks)
+ No custom domains
+ No always-on (sleeps after inactivity)
+ No SSH access

TIPS:
-----
- Use 'Web' tab -> 'Force HTTPS' for security
- Enable 'Static files' caching for performance
- Check 'Error log' in Web tab if issues
- Free tier sleeps after ~1 hour inactivity
  (first request after sleep takes 10-20s to wake up)
""")