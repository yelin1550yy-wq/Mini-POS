import sys
import os

# Dynamically determine project directory from this file's location
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Ensure instance directory exists
instance_dir = os.path.join(project_home, 'instance')
os.makedirs(instance_dir, exist_ok=True)
db_file = os.path.join(instance_dir, 'minipos.db').replace('\\', '/')

# Set environment variables BEFORE importing the app
os.environ['FLASK_ENV'] = 'production'
os.environ.setdefault('SECRET_KEY', 'momo-pajamas-production-secret-key-2024')
os.environ.setdefault('DATABASE_URL', f'sqlite:///{db_file}')

# Import the app factory and create the app
from app import create_app, db
from app.models import User
application = create_app()

with application.app_context():
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
