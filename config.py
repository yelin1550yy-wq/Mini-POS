import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'minipos.db')

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{db_path}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    PERMANENT_SESSION_LIFETIME = 3600