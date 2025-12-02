# Path: config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-fallback'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///production_assets.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Robust Upload Configuration for Production (AWS/Linux)
    # Uses the directory of this file as the base anchor
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024 # 16MB Max Size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx'}