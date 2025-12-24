from flask import Blueprint, render_template
from flask_login import login_required
from app.models import Asset, AssetHistory, Branch

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def dashboard():
    # Helper to simplify queries
    def count_assets(**kwargs):
        return Asset.query.filter_by(**kwargs).count()

    # 1. Basic Stats
    total = Asset.query.count()
    allocated = count_assets(status='Allocated')
    instock = count_assets(status='In Stock')
    repair = count_assets(status='Repair')
    transit = count_assets(status='In Transit')

    # 2. Advanced Stats (HO vs Branches)
    # Assuming 'HO' is the name for Head Office. 
    ho_branch = Branch.query.filter_by(name='HO').first()
    ho_id = ho_branch.id if ho_branch else -1

    # HO Specific
    ho_stock = Asset.query.filter_by(status='In Stock', current_branch_id=ho_id).count()
    ho_allocated = Asset.query.filter_by(status='Allocated', current_branch_id=ho_id).count()

    # Other Branches (Total - HO)
    # We explicitly check for branch_id != ho_id to exclude HO
    branch_stock = Asset.query.filter(Asset.status == 'In Stock', Asset.current_branch_id != ho_id).count()
    branch_allocated = Asset.query.filter(Asset.status == 'Allocated', Asset.current_branch_id != ho_id).count()

    stats = {
        'total': total,
        'allocated': allocated,
        'instock': instock,
        'repair': repair,
        'transit': transit,
        'ho_stock': ho_stock,
        'ho_allocated': ho_allocated,
        'branch_stock': branch_stock,
        'branch_allocated': branch_allocated
    }
    
    recent_activity = AssetHistory.query.order_by(AssetHistory.timestamp.desc()).limit(10).all()
    return render_template('main/dashboard.html', stats=stats, recent_activity=recent_activity)