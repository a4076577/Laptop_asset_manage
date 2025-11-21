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
    status = db.Column(db.String(50), default='In Stock') # In Stock, Allocated, In Transit, Repair
    current_branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=True)
    current_employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True)
    history = db.relationship('AssetHistory', backref='asset', lazy=True, order_by="desc(AssetHistory.timestamp)")

class AssetHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    action = db.Column(db.String(50))
    from_detail = db.Column(db.String(200))
    to_detail = db.Column(db.String(200))
    courier_details = db.Column(db.String(200))
    notes = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))