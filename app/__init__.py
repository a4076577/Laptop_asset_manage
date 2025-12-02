# Path: app/__init__.py
import os
from flask import Flask
from config import Config
from app.extensions import db, login_manager

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    db.init_app(app)
    login_manager.init_app(app)

    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.assets import assets_bp
    from app.routes.employees import employees_bp
    from app.routes.admin import admin_bp
    from app.routes.qr import qr_bp  # NEW

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(assets_bp, url_prefix='/assets')
    app.register_blueprint(employees_bp, url_prefix='/employees')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(qr_bp, url_prefix='/qr') # NEW

    with app.app_context():
        db.create_all()

    return app