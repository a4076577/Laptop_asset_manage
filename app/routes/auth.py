# Path: app/routes/auth.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from app.extensions import db
from app.models import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('main.dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

# --- User Management ---
@auth_bp.route('/users')
@login_required
def manage_users():
    users = User.query.all()
    return render_template('auth/users.html', users=users)

@auth_bp.route('/users/add', methods=['POST'])
@login_required
def add_user():
    email = request.form.get('email')
    name = request.form.get('name')
    password = request.form.get('password')
    
    if User.query.filter_by(email=email).first():
        flash('Email already registered', 'error')
    else:
        new_user = User(email=email, name=name, password=password) # Hash in prod
        db.session.add(new_user)
        db.session.commit()
        flash('User added successfully', 'success')
    
    return redirect(url_for('auth.manage_users'))