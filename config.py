import os
import shutil
import glob
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, 'instance')
os.makedirs(instance_dir, exist_ok=True)

# Standardize path for SQLite URI (forward slashes, absolute path)
db_file = os.path.join(instance_dir, 'minipos.db').replace('\\', '/')

# PythonAnywhere auto-discovery of database/backup if minipos.db is missing or empty (0 bytes)
if not os.path.exists(db_file) or os.path.getsize(db_file) == 0:
    pa_candidates = [
        '/home/momopajamas33/mini_pos_db_backup_20261020_154250.db',
        '/home/momopajamas33/Mini-POS/instance/minipos.db',
        '/home/momopajamas33/minipos.db'
    ]
    # Also look for any backup pattern in /home/momopajamas33/
    pa_candidates.extend(sorted(glob.glob('/home/momopajamas33/mini_pos_db_backup_*.db'), reverse=True))
    
    for candidate in pa_candidates:
        if os.path.exists(candidate) and os.path.getsize(candidate) > 0 and os.path.abspath(candidate) != os.path.abspath(db_file):
            try:
                shutil.copy2(candidate, db_file)
                print(f"[Database Init] Restored active DB from backup: {candidate}")
                break
            except Exception as e:
                print(f"[Database Init] Could not restore from {candidate}: {e}")

default_db_uri = f'sqlite:///{db_file}'

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', default_db_uri)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    PERMANENT_SESSION_LIFETIME = 3600
