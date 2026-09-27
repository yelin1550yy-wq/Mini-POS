import sys
import os

# Add your project directory to the path
project_home = '/home/momopajamas33/Mini-POS'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables BEFORE importing the app
os.environ['FLASK_ENV'] = 'production'
os.environ['SECRET_KEY'] = 'your-secret-key-here'  # CHANGE THIS!
os.environ['DATABASE_URL'] = 'sqlite:////home/momopajamas33/Mini-POS/instance/minipos.db'

# Import the app factory and create the app
from app import create_app
application = create_app()

# Ensure database exists and create default users
with application.app_context():
    from app import db
    from app.models import User
    db.create_all()

    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", email="admin@example.com", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)

        user = User(username="staff", email="staff@example.com", role="user")
        user.set_password("staff123")
        db.session.add(user)

        db.session.commit()
        print("Default users created: admin/admin123, staff/staff123")