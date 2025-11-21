# Path: app/routes/main.py
from flask import Blueprint, render_template
from flask_login import login_required
from app.models import Asset, AssetHistory

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def dashboard():
    stats = {
        'total': Asset.query.count(),
        'allocated': Asset.query.filter_by(status='Allocated').count(),
        'instock': Asset.query.filter_by(status='In Stock').count(),
        'repair': Asset.query.filter_by(status='Repair').count(),
        'transit': Asset.query.filter_by(status='In Transit').count(),
    }
    recent_activity = AssetHistory.query.order_by(AssetHistory.timestamp.desc()).limit(10).all()
    return render_template('main/dashboard.html', stats=stats, recent_activity=recent_activity)