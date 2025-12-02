# Path: app/models.py
from datetime import datetime
from flask_login import UserMixin
from app.extensions import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100))

class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100))
    employees = db.relationship('Employee', backref='branch', lazy=True)
    assets = db.relationship('Asset', backref='branch', lazy=True)

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='Active')
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=True)
    assets_holding = db.relationship('Asset', backref='holder', lazy=True)

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(100), unique=True, nullable=False)
    brand = db.Column(db.String(50))
    model = db.Column(db.String(100))
    purchase_date = db.Column(db.Date)
    status = db.Column(db.String(50), default='In Stock')
    current_branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=True)
    current_employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True)
    history = db.relationship('AssetHistory', backref='asset', lazy=True, order_by="desc(AssetHistory.timestamp)")
    
    qr_code_hash = db.Column(db.String(64), unique=True, nullable=True)
    is_qr_active = db.Column(db.Boolean, default=True)

class AssetHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    action = db.Column(db.String(50))
    from_detail = db.Column(db.String(200))
    to_detail = db.Column(db.String(200))
    courier_details = db.Column(db.String(200))
    notes = db.Column(db.String(500))
    document_path = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_action_status = db.Column(db.String(50))
    post_action_branch_id = db.Column(db.Integer)
    post_action_employee_id = db.Column(db.Integer)

class PreGeneratedQR(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    qr_hash = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id')) 
    status = db.Column(db.String(20), default='Available') 

class ScanLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    qr_hash = db.Column(db.String(64), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(200))
    linked_asset_id = db.Column(db.Integer, nullable=True)

class SystemSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(200))